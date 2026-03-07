"""Workflow Orchestrator - 多 Agent 工作流协调器 (Enhanced)

实现自动化的 需求→代码→测试→(重分析) 循环控制。
参考 LangGraph、AutoGen、CrewAI 等现代多 Agent 框架的最佳实践。

核心架构:
```
┌─────────────────────────────────────────────────────────┐
│                    Orchestrator                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │              State Machine                       │    │
│  │  PENDING → ANALYZING → PLANNING → IMPLEMENTING  │    │
│  │                             ↓    ↑              │    │
│  │                        TESTING ←┘               │    │
│  │                             ↓                   │    │
│  │                        VERIFYING → COMPLETED    │    │
│  └─────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────┐    │
│  │           ParallelScheduler                      │    │
│  │  - Agent 级并行 (max 3)                          │    │
│  │  - Tool 级并行 (max 3)                           │    │
│  │  - asyncio.Semaphore 并发控制                    │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   Blackboard                             │
│  ┌─────────────┬─────────────┬─────────────┐            │
│  │  Shared     │  Artifact   │   Error     │            │
│  │  Context    │  Store      │   History   │            │
│  └─────────────┴─────────────┴─────────────┘            │
└─────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│  Planner      │ │   Coder       │ │   Tester      │
│  Agent        │ │   Agent       │ │   Agent       │
│               │ │               │ │               │
│ Tools:        │ │ Tools:        │ │ Tools:        │
│ - Read        │ │ - Read/Write  │ │ - Read        │
│ - Search      │ │ - Command     │ │ - Command     │
│ - WebFetch    │ │ - Edit        │ │ - Pytest      │
└───────────────┘ └───────────────┘ └───────────────┘
```

死循环检测与恢复策略:
```
测试失败
    │
    ├─ 实现细节问题 (类型错误、语法错误)
    │   └─→ 重试实现 (保持计划不变)
    │
    └─ 架构/逻辑问题 (断言失败、设计缺陷)
        └─→ 重新规划 (清除旧计划，重新分析)
```
"""

import asyncio
import logging
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable

from mini_coder.agents.enhanced import (
    Blackboard,
    Event,
    EventType,
    BaseEnhancedAgent,
    PlannerAgent,
    CoderAgent,
    TesterAgent,
    EnhancedAgentResult,
)

from mini_coder.agents.base import (
    ExplorerAgent,
    ReviewerAgent,
    BashAgent,
)

from mini_coder.agents.mailbox import (
    TaskBrief,
    SubagentResult,
    ParallelTaskGroup,
    ParallelResultGroup,
    FAIL_STRATEGY_CONTINUE,
    DEFAULT_MAX_CONCURRENCY,
    DEFAULT_AGENT_TIMEOUT,
)

from mini_coder.agents.scheduler import ParallelScheduler
from mini_coder.tools.filter import BashRestrictedFilter

logger = logging.getLogger(__name__)


class SubAgentType(Enum):
    """子代理类型枚举

    与 prompts/system/main-agent.md 中定义的子代理列表保持一致。
    """
    EXPLORER = "explorer"          # 只读探索
    PLANNER = "planner"            # TDD 规划
    CODER = "coder"                # 代码实现
    REVIEWER = "reviewer"          # 代码评审
    BASH = "bash"                  # 终端执行与测试验证
    MINI_CODER_GUIDE = "mini_coder_guide"  # Mini-coder 使用指南
    GENERAL_PURPOSE = "general_purpose"    # 通用只读分析


class IntentResult:
    """意图分析结果"""

    def __init__(self, agent_type: SubAgentType, confidence: float, reason: str):
        self.agent_type = agent_type
        self.confidence = confidence
        self.reason = reason

    def __repr__(self) -> str:
        return f"IntentResult(agent={self.agent_type.value}, confidence={self.confidence:.2f})"


class WorkflowState(Enum):
    """工作流状态枚举"""
    PENDING = "pending"           # 等待开始
    ANALYZING = "analyzing"       # 需求分析中
    PLANNING = "planning"         # 规划中
    IMPLEMENTING = "implementing"  # 实现中
    TESTING = "testing"           # 测试中
    VERIFYING = "verifying"       # 验证中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败
    NEEDS_INTERVENTION = "needs_intervention"  # 需要人工介入
    RETRYING = "retrying"         # 重试中
    REPLANNING = "replanning"     # 重新规划中


class FailureType(Enum):
    """失败类型枚举"""
    TEST_FAILURE = "test_failure"
    TYPE_ERROR = "type_error"
    LINT_ERROR = "lint_error"
    SYNTAX_ERROR = "syntax_error"
    RUNTIME_ERROR = "runtime_error"
    TIMEOUT = "timeout"
    AGENT_ERROR = "agent_error"
    LOOP_DETECTED = "loop_detected"


@dataclass
class WorkflowConfig:
    """工作流配置"""
    max_retries: int = 4
    timeout_seconds: float = 600  # 10 分钟
    loop_detection_enabled: bool = True
    auto_retry: bool = True
    verbose: bool = False
    # 并行调度配置
    max_agent_concurrency: int = DEFAULT_MAX_CONCURRENCY
    # Tool 级并发由 ToolScheduler 独立管理


@dataclass
class WorkflowContext:
    """工作流上下文 - 使用 Blackboard 模式管理

    特性:
    - 所有 Agent 通过黑板共享信息
    - 工件（计划、代码、报告）存储在黑板上
    - 事件日志记录所有重要操作
    - 错误历史用于死循环检测
    """
    task_id: str
    requirement: str
    config: WorkflowConfig = field(default_factory=WorkflowConfig)
    current_state: WorkflowState = WorkflowState.PENDING
    retry_count: int = 0
    start_time: float = field(default_factory=time.time)

    # 黑板引用
    blackboard: Optional[Blackboard] = field(default=None)

    # 错误历史
    error_history: List[Dict[str, Any]] = field(default_factory=list)
    error_counts: Dict[str, int] = field(default_factory=dict)

    # 决策历史
    decision_history: List[Dict[str, str]] = field(default_factory=list)

    def __post_init__(self):
        if self.blackboard is None:
            self.blackboard = Blackboard(self.task_id)
        # 初始化黑板上下文
        self.blackboard.set_context("requirement", self.requirement)
        self.blackboard.set_context("task_id", self.task_id)

    def add_error(self, error_data: Dict[str, Any]) -> str:
        """添加错误并返回错误 key"""
        self.error_history.append(error_data)

        # 生成错误签名 key
        key = f"{error_data.get('file', 'unknown')}:{error_data.get('line', 0)}:{error_data.get('type', 'unknown')}"
        self.error_counts[key] = self.error_counts.get(key, 0) + 1

        # 记录到黑板事件日志
        self.blackboard.log_event(Event(
            type=EventType.ERROR_OCCURRED,
            data={**error_data, "count": self.error_counts[key]},
            source="orchestrator"
        ))

        return key

    def is_loop_detected(self) -> bool:
        """检测是否陷入死循环"""
        if not self.config.loop_detection_enabled:
            return False
        for count in self.error_counts.values():
            if count >= self.config.max_retries:
                return True
        return False

    def record_decision(self, decision: str, reason: str) -> None:
        """记录决策"""
        self.decision_history.append({
            "decision": decision,
            "reason": reason,
            "timestamp": str(time.time())
        })

    def reset_for_replan(self) -> None:
        """重置以重新规划"""
        self.current_state = WorkflowState.REPLANNING
        self.retry_count += 1
        self.record_decision("replan", "测试失败，需要重新规划")
        logger.info(f"Reset for replan (attempt {self.retry_count}/{self.config.max_retries})")

    def reset_for_retry(self) -> None:
        """重置以重试实现"""
        self.current_state = WorkflowState.RETRYING
        self.retry_count += 1
        self.record_decision("retry", "测试失败，重试实现")
        logger.info(f"Reset for retry (attempt {self.retry_count}/{self.config.max_retries})")

    @property
    def elapsed_time(self) -> float:
        """获取已用时间"""
        return time.time() - self.start_time

    @property
    def plan(self) -> Optional[str]:
        """获取计划"""
        artifact = self.blackboard.get_artifact("implementation_plan.md")
        return artifact.content if artifact else None

    @property
    def code_artifacts(self) -> Dict[str, str]:
        """获取所有代码工件"""
        result = {}
        for artifact in self.blackboard.list_artifacts(content_type="code"):
            name = artifact.name.replace("code:", "")
            result[name] = artifact.content
        return result

    def get_summary(self) -> Dict[str, Any]:
        """获取上下文摘要"""
        return {
            "task_id": self.task_id,
            "requirement": self.requirement[:100] + "..." if len(self.requirement) > 100 else self.requirement,
            "state": self.current_state.value,
            "retry_count": self.retry_count,
            "elapsed_time": round(self.elapsed_time, 2),
            "loop_detected": self.is_loop_detected(),
            "error_count": len(self.error_history),
        }


class WorkflowOrchestrator:
    """工作流协调器

    核心职责:
    1. 状态机管理 - 控制工作流状态转换
    2. Agent 协调 - 调用 Planner/Coder/Tester
    3. 死循环检测 - 识别重复失败模式
    4. 智能恢复 - 决定重试还是重新规划

    使用示例:
    ```python
    orchestrator = WorkflowOrchestrator(llm_service, config)
    result = orchestrator.execute_workflow("实现一个计算器")
    ```
    """

    def __init__(
        self,
        llm_service: Any,
        config: Optional[WorkflowConfig] = None,
        command_executor: Optional[Callable] = None,
    ) -> None:
        """初始化

        Args:
            llm_service: LLM 服务实例
            config: 工作流配置
            command_executor: 命令执行函数 (command, timeout) -> (success, stdout, stderr)
        """
        self.llm_service = llm_service
        self.config = config or WorkflowConfig()
        self.command_executor = command_executor

        # 当前上下文
        self._context: Optional[WorkflowContext] = None

        # 并行调度器
        self._scheduler = ParallelScheduler(
            max_agent_concurrency=self.config.max_agent_concurrency,
            default_agent_timeout=self.config.timeout_seconds,
        )

        # Tool 调度器（独立实例）
        self._tool_scheduler = None  # 延迟初始化

        # 状态回调
        self._state_callbacks: Dict[WorkflowState, List[Callable]] = {
            state: [] for state in WorkflowState
        }

        # Agent 回调 (用于 TUI 显示)
        self._agent_callbacks: List[Callable] = []

        # Tool 回调 (用于 TUI 显示)
        self._tool_callbacks: List[Callable] = []

        logger.info(f"WorkflowOrchestrator initialized (max_retries={self.config.max_retries})")

    def execute_workflow(self, requirement: str, task_id: Optional[str] = None) -> EnhancedAgentResult:
        """执行完整工作流

        自动执行：需求分析 → 规划 → 实现 → 测试 → 验证

        Args:
            requirement: 需求描述
            task_id: 可选的任务 ID

        Returns:
            EnhancedAgentResult: 执行结果
        """
        import uuid
        task_id = task_id or str(uuid.uuid4())

        # 创建/复用上下文：若已有上下文且 task_id 相同，则复用 Blackboard 以便在交互式场景下跨轮共享工件
        if self._context is not None and self._context.task_id == task_id:
            self._context.requirement = requirement
            self._context.blackboard.set_context("requirement", requirement)
            self._context.current_state = WorkflowState.PENDING
            self._context.retry_count = 0
            self._context.start_time = time.time()
            self._context.error_history.clear()
            self._context.error_counts.clear()
            self._context.decision_history.clear()
        else:
            self._context = WorkflowContext(
                task_id=task_id,
                requirement=requirement,
                config=self.config
            )

        self._notify_state_change(WorkflowState.PENDING)
        logger.info(f"Starting workflow [{task_id[:8]}]: {requirement[:80]}...")

        try:
            # 主循环
            while self._context.current_state not in (
                WorkflowState.COMPLETED,
                WorkflowState.FAILED,
                WorkflowState.NEEDS_INTERVENTION
            ):
                # 检查超时
                if self._context.elapsed_time > self.config.timeout_seconds:
                    return self._fail(FailureType.TIMEOUT, f"Timeout after {self._context.elapsed_time:.1f}s")

                # 检查死循环
                if self._context.is_loop_detected():
                    return self._fail(
                        FailureType.LOOP_DETECTED,
                        f"Loop detected: {self.config.max_retries} identical failures",
                        needs_user_decision=True,
                        decision_reason="检测到死循环，需要人工决策"
                    )

                # 检查最大重试
                if self._context.retry_count >= self.config.max_retries:
                    return self._fail(
                        FailureType.AGENT_ERROR,
                        f"Max retries ({self.config.max_retries}) exceeded",
                        needs_user_decision=True,
                        decision_reason="已达到最大重试次数"
                    )

                # 执行当前阶段
                result = self._execute_current_stage()

                # 如果需要用户决策，直接返回
                if result.needs_user_decision:
                    return result

            # 完成
            return self._create_final_result()

        except Exception as e:
            logger.exception("Workflow error")
            return self._fail(FailureType.AGENT_ERROR, str(e))

    def ensure_interactive_context(self, task_id: str, requirement_seed: str = "interactive") -> None:
        """确保存在可复用的交互式上下文（用于 TUI 跨轮共享 Blackboard）。

        TUI 的 dispatch 路径默认不创建 WorkflowContext，会导致每轮新建 Blackboard；
        该方法用于在交互式会话中创建一个长期存活的 WorkflowContext，从而复用同一个 Blackboard。
        """
        if self._context is not None and self._context.task_id == task_id:
            return
        self._context = WorkflowContext(
            task_id=task_id,
            requirement=requirement_seed,
            config=self.config,
        )

    def _execute_current_stage(self) -> EnhancedAgentResult:
        """执行当前阶段"""
        state = self._context.current_state

        handlers = {
            WorkflowState.PENDING: self._execute_analyzing,
            WorkflowState.ANALYZING: self._execute_planning,
            WorkflowState.PLANNING: self._execute_implementing,
            WorkflowState.RETRYING: self._execute_implementing,
            WorkflowState.REPLANNING: self._execute_planning,
            WorkflowState.IMPLEMENTING: self._execute_testing,
            WorkflowState.TESTING: self._execute_verifying,
            WorkflowState.VERIFYING: self._complete,
        }

        handler = handlers.get(state)
        if handler:
            return handler()
        else:
            return self._fail(FailureType.AGENT_ERROR, f"Unknown state: {state}")

    def _execute_analyzing(self) -> EnhancedAgentResult:
        """需求分析阶段"""
        logger.info(f"[{self._context.task_id[:8]}] ANALYZING")
        self._notify_state_change(WorkflowState.ANALYZING)

        try:
            agent = PlannerAgent(self.llm_service, self._context.blackboard)
            result = agent.execute(f"Analyze: {self._context.requirement}")

            if result.success:
                self._context.current_state = WorkflowState.PLANNING
            else:
                self._context.current_state = WorkflowState.FAILED

            return result

        except Exception as e:
            self._context.current_state = WorkflowState.FAILED
            return self._fail(FailureType.AGENT_ERROR, str(e))

    def _execute_planning(self) -> EnhancedAgentResult:
        """规划阶段"""
        logger.info(f"[{self._context.task_id[:8]}] PLANNING")
        self._notify_state_change(WorkflowState.PLANNING)

        try:
            agent = PlannerAgent(self.llm_service, self._context.blackboard)

            # 如果是重新规划，清除旧计划
            if self._context.current_state == WorkflowState.REPLANNING:
                logger.info("Replanning - clearing old plan")
                # 黑板上的计划会被新计划覆盖

            result = agent.execute(f"Plan: {self._context.requirement}")

            if result.success:
                self._context.current_state = WorkflowState.IMPLEMENTING
            else:
                self._context.current_state = WorkflowState.FAILED

            return result

        except Exception as e:
            self._context.current_state = WorkflowState.FAILED
            return self._fail(FailureType.AGENT_ERROR, str(e))

    def _execute_implementing(self) -> EnhancedAgentResult:
        """实现阶段"""
        logger.info(f"[{self._context.task_id[:8]}] IMPLEMENTING (attempt {self._context.retry_count + 1})")
        self._notify_state_change(WorkflowState.IMPLEMENTING)

        try:
            agent = CoderAgent(self.llm_service, self._context.blackboard)
            result = agent.execute(f"Implement: {self._context.requirement}")

            if result.success:
                self._context.current_state = WorkflowState.TESTING
            else:
                self._context.add_error({
                    "file": "unknown",
                    "line": 0,
                    "type": result.failure_type or "coding_error",
                    "message": result.error[:200]
                })
                self._context.current_state = WorkflowState.FAILED

            return result

        except Exception as e:
            self._context.current_state = WorkflowState.FAILED
            return self._fail(FailureType.AGENT_ERROR, str(e))

    def _execute_testing(self) -> EnhancedAgentResult:
        """测试阶段 - 关键决策点"""
        logger.info(f"[{self._context.task_id[:8]}] TESTING")
        self._notify_state_change(WorkflowState.TESTING)

        try:
            agent = TesterAgent(
                self.llm_service,
                self._context.blackboard,
                self.command_executor
            )
            result = agent.execute(f"Test: {self._context.requirement}")

            if result.success:
                self._context.current_state = WorkflowState.VERIFYING
            else:
                # 测试失败 - 决定 retry 还是 replan
                decision = self._analyze_test_failure(result)
                error_key = self._context.add_error({
                    "file": self._extract_error_file(result.error),
                    "line": self._extract_error_line(result.error),
                    "type": self._classify_failure_type(result.error),
                    "message": result.error[:300]
                })

                if decision == "retry":
                    self._context.reset_for_retry()
                else:
                    self._context.reset_for_replan()

                logger.info(f"Test failure decision: {decision} (error_key={error_key})")

            return result

        except Exception as e:
            self._context.current_state = WorkflowState.FAILED
            return self._fail(FailureType.AGENT_ERROR, str(e))

    def _execute_verifying(self) -> EnhancedAgentResult:
        """验证阶段"""
        logger.info(f"[{self._context.task_id[:8]}] VERIFYING")
        self._notify_state_change(WorkflowState.VERIFYING)

        try:
            agent = TesterAgent(
                self.llm_service,
                self._context.blackboard,
                self.command_executor
            )
            result = agent.execute(f"Final verification: {self._context.requirement}")

            if result.success:
                self._context.current_state = WorkflowState.COMPLETED
            else:
                # 验证失败 - 通常重试实现
                self._context.add_error({
                    "file": "verification",
                    "line": 0,
                    "type": self._classify_failure_type(result.error),
                    "message": result.error[:300]
                })
                self._context.reset_for_retry()

            return result

        except Exception as e:
            self._context.current_state = WorkflowState.FAILED
            return self._fail(FailureType.AGENT_ERROR, str(e))

    def _complete(self) -> EnhancedAgentResult:
        """完成工作流"""
        self._context.current_state = WorkflowState.COMPLETED
        self._notify_state_change(WorkflowState.COMPLETED)

        return EnhancedAgentResult(
            success=True,
            output="Workflow completed successfully",
            artifacts={k: v.content for k, v in self._context.blackboard._artifacts.items() if isinstance(k, str)},
            elapsed_time=self._context.elapsed_time,
        )

    # ==================== Subagent Dispatch Methods ====================

    def _analyze_intent(self, intent: str) -> SubAgentType:
        """分析用户意图并派发对应的子代理

        基于关键词匹配的意图分析：
        1. 快速路径：关键词匹配
        2. 简单问候语：直接使用 GENERAL_PURPOSE
        3. 兜底：LLM 决策模糊意图（如果 LLM 不可用则默认 CODER）

        Args:
            intent: 用户请求/意图描述

        Returns:
            SubAgentType: 派发的子代理类型
        """
        intent_lower = intent.lower().strip()

        # 快速路径：简单问候语（不触发 LLM 调用）
        simple_greetings = [
            "你好", "您好", "hi", "hello", "hey", "嗨", "哈喽",
            "早上好", "下午好", "晚上好", "good morning", "good afternoon",
            "怎么样", "如何", "help", "帮助", "?", "？",
        ]
        if intent_lower in simple_greetings or len(intent_lower) <= 3:
            logger.info("Intent analysis: GENERAL_PURPOSE (simple greeting or short input)")
            return SubAgentType.GENERAL_PURPOSE

        # Mini-Coder Guide 关键词 (最高优先级，因为这是项目特定问题)
        guide_keywords = ["mini-coder", "minicoder", "如何使用", "怎么运行", "配置", "tui", "agent 角色", "工作流", "prompt", "subagent"]
        if any(kw in intent_lower for kw in guide_keywords):
            logger.info("Intent analysis: MINI_CODER_GUIDE (keywords match)")
            return SubAgentType.MINI_CODER_GUIDE

        # General Purpose 关键词 (快速搜索，通用查询)
        general_keywords = ["快速查找", "fast search", "general search", "代码搜索", "code search", "文件发现", "file discovery"]
        if any(kw in intent_lower for kw in general_keywords):
            logger.info("Intent analysis: GENERAL_PURPOSE (keywords match)")
            return SubAgentType.GENERAL_PURPOSE

        # Explorer 关键词
        explorer_keywords = ["看看", "找找", "探索", "explore", "search", "find", "查看", "分析结构", "codebase structure"]
        if any(kw in intent_lower for kw in explorer_keywords):
            logger.info("Intent analysis: EXPLORER (keywords match)")
            return SubAgentType.EXPLORER

        # Planner 关键词
        planner_keywords = ["规划", "计划", "拆解", "plan", "design", "架构", "任务分解"]
        if any(kw in intent_lower for kw in planner_keywords):
            logger.info("Intent analysis: PLANNER (keywords match)")
            return SubAgentType.PLANNER

        # 不再用关键词单独判「写入本地」→ BASH，交给下方 LLM 按意图区分（BASH=执行命令/保存到本地，CODER=写代码/编辑内容）

        # Coder 关键词（写代码、实现功能）
        coder_keywords = ["实现", "添加", "修改", "implement", "create", "write", "add", "feature", "功能"]
        if any(kw in intent_lower for kw in coder_keywords):
            logger.info("Intent analysis: CODER (keywords match)")
            return SubAgentType.CODER

        # Reviewer 关键词
        reviewer_keywords = ["评审", "检查", "review", "quality", "代码质量", "架构对齐"]
        if any(kw in intent_lower for kw in reviewer_keywords):
            logger.info("Intent analysis: REVIEWER (keywords match)")
            return SubAgentType.REVIEWER

        # Bash 关键词
        bash_keywords = ["测试", "运行", "execute", "test", "bash", "验证", "verify"]
        if any(kw in intent_lower for kw in bash_keywords):
            logger.info("Intent analysis: BASH (keywords match)")
            return SubAgentType.BASH

        # 兜底：使用 LLM 决策模糊意图
        logger.info("Intent analysis: using LLM for ambiguous intent")
        return self._llm_analyze_intent(intent)

    def _llm_analyze_intent(self, intent: str) -> SubAgentType:
        """使用 LLM 分析模糊意图

        如果 LLM 服务不可用或调用失败，返回默认的 GENERAL_PURPOSE。
        """
        # 安全检查：LLM 服务是否可用
        if self.llm_service is None:
            logger.warning("LLM service not available, defaulting to GENERAL_PURPOSE")
            return SubAgentType.GENERAL_PURPOSE

        prompt = f"""Analyze the user request and determine which subagent should handle it.

User Request: {intent}

Available Subagents (choose by intent, not by keywords only):
- EXPLORER: Read-only codebase search (find files, understand structure). No code writing, no command execution.
- PLANNER: Requirements analysis, task breakdown, TDD plan creation (e.g. implementation_plan.md).
- CODER: Code implementation — write or edit source code / file content (implement features, create or modify files). Content-centric.
- REVIEWER: Code quality and architecture alignment review (read-only, no command execution).
- BASH: Execute terminal commands (run tests e.g. pytest, type check mypy, lint; or perform "save/write to local" as running a command). Choose BASH only when the user intent is "run a command" or "execute/verify/save to local"; if the intent is "write code" or "implement feature" or "create file content", choose CODER. Command-centric; see command-prefix semantics for safety.
- GENERAL_PURPOSE: Fast read-only search, quick code discovery.
- MINI_CODER_GUIDE: Answer questions about mini-coder usage, config, workflow.

Respond with only one word: EXPLORER, PLANNER, CODER, REVIEWER, BASH, GENERAL_PURPOSE, or MINI_CODER_GUIDE."""

        try:
            logger.debug(f"Calling LLM for intent analysis: {intent[:50]}...")
            response = self.llm_service.chat(prompt)
            if not response:
                logger.warning("LLM returned empty response, defaulting to GENERAL_PURPOSE")
                return SubAgentType.GENERAL_PURPOSE

            response = response.strip().upper()
            logger.debug(f"LLM intent analysis response: {response}")

            if "MINI_CODER_GUIDE" in response or "GUIDE" in response:
                return SubAgentType.MINI_CODER_GUIDE
            elif "GENERAL_PURPOSE" in response or "GENERAL" in response:
                return SubAgentType.GENERAL_PURPOSE
            elif "EXPLORER" in response:
                return SubAgentType.EXPLORER
            elif "PLANNER" in response:
                return SubAgentType.PLANNER
            elif "CODER" in response:
                return SubAgentType.CODER
            elif "REVIEWER" in response:
                return SubAgentType.REVIEWER
            elif "BASH" in response:
                return SubAgentType.BASH
            else:
                logger.warning(f"LLM returned unknown agent type: {response}, defaulting to GENERAL_PURPOSE")
                return SubAgentType.GENERAL_PURPOSE
        except Exception as e:
            logger.error(f"LLM intent analysis error: {e}", exc_info=True)
            return SubAgentType.GENERAL_PURPOSE  # 兜底

    def _create_subagent(self, agent_type: SubAgentType) -> Any:
        """创建子代理实例

        Args:
            agent_type: 子代理类型

        Returns:
            子代理实例
        """
        from mini_coder.agents.base import AgentConfig
        from mini_coder.agents.base import (
            GeneralPurposeAgent,
            MiniCoderGuideAgent,
        )

        blackboard = self._context.blackboard if self._context else Blackboard("dispatch")

        # 创建 Agent 事件回调（用于转发工具调用事件到 TUI）
        agent_event_callback = self._create_agent_event_callback(agent_type)

        if agent_type == SubAgentType.EXPLORER:
            return ExplorerAgent(self.llm_service)
        elif agent_type == SubAgentType.PLANNER:
            return PlannerAgent(
                self.llm_service,
                blackboard=blackboard,
                event_callback=agent_event_callback,
            )
        elif agent_type == SubAgentType.CODER:
            return CoderAgent(
                self.llm_service,
                blackboard=blackboard,
                event_callback=agent_event_callback,
            )
        elif agent_type == SubAgentType.REVIEWER:
            return ReviewerAgent(self.llm_service)
        elif agent_type == SubAgentType.BASH:
            return BashAgent(
                self.llm_service,
                config=AgentConfig(
                    name="BashAgent",
                    description="Terminal execution and test verification",
                    tool_filter=BashRestrictedFilter(),
                    max_iterations=10,
                ),
                command_executor=self.command_executor,
            )
        elif agent_type == SubAgentType.GENERAL_PURPOSE:
            return GeneralPurposeAgent(self.llm_service)
        elif agent_type == SubAgentType.MINI_CODER_GUIDE:
            return MiniCoderGuideAgent(self.llm_service)
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")

    def dispatch(
        self,
        intent: str,
        context: Optional[Dict[str, Any]] = None,
        stream_callback: Optional[Any] = None,
    ) -> EnhancedAgentResult:
        """直接派发子代理执行任务

        使用示例:
        ```python
        # 探索代码库
        result = orchestrator.dispatch("探索代码库，找出所有认证相关的文件")

        # 规划任务
        result = orchestrator.dispatch("规划任务：实现用户登录功能")

        # 实现代码
        result = orchestrator.dispatch("实现用户登录 API")

        # 代码评审
        result = orchestrator.dispatch("评审刚实现的代码质量")

        # 运行测试
        result = orchestrator.dispatch("运行所有测试并生成质量报告")
        ```

        Args:
            intent: 用户请求/意图
            context: 可选的上下文信息

        Returns:
            EnhancedAgentResult: 执行结果
        """
        # 1. 分析意图
        agent_type = self._analyze_intent(intent)
        logger.info(f"Dispatching to {agent_type.value}")

        # 记录交互式上下文（若存在），便于子代理共享
        if self._context is not None:
            self._context.blackboard.set_context("last_user_input", intent)
            if context is not None:
                self._context.blackboard.set_context("last_dispatch_context", context)

        # 2. 发送 Agent 开始事件
        self._notify_agent_started(agent_type)

        # 3. 创建子代理
        agent = self._create_subagent(agent_type)

        # 4. 执行任务（base 系 agent 需传入含 work_dir 的 context；stream_callback 用于 TUI 流式输出与首字耗时）
        if isinstance(agent, BaseEnhancedAgent):
            result = agent.execute(intent, stream_callback=stream_callback)
        else:
            dispatch_context = context or {}
            if self._context is not None:
                wd = self._context.blackboard.get_context("work_dir")
                if wd is not None:
                    dispatch_context = {**dispatch_context, "work_dir": str(wd)}
            result = agent.execute(intent, context=dispatch_context, stream_callback=stream_callback)

        # 5. 发送 Agent 完成事件
        self._notify_agent_completed(agent_type, result)

        return result

    def dispatch_with_agent(
        self,
        agent_type: SubAgentType,
        intent: str,
        context: Optional[Dict[str, Any]] = None,
        stream_callback: Optional[Any] = None,
    ) -> EnhancedAgentResult:
        """按指定子代理类型执行一次派发（用于结构化路由）。

        与 dispatch() 相同，但跳过 _analyze_intent，直接使用传入的 agent_type。
        """
        logger.info(f"Dispatching to {agent_type.value} (forced)")
        if self._context is not None:
            self._context.blackboard.set_context("last_user_input", intent)
            if context is not None:
                self._context.blackboard.set_context("last_dispatch_context", context)
        self._notify_agent_started(agent_type)
        agent = self._create_subagent(agent_type)
        if isinstance(agent, BaseEnhancedAgent):
            result = agent.execute(intent, stream_callback=stream_callback)
        else:
            dispatch_context = context or {}
            if self._context is not None:
                wd = self._context.blackboard.get_context("work_dir")
                if wd is not None:
                    dispatch_context = {**dispatch_context, "work_dir": str(wd)}
            result = agent.execute(intent, context=dispatch_context, stream_callback=stream_callback)
        self._notify_agent_completed(agent_type, result)
        return result

    # ==================== Async Dispatch Methods ====================

    async def dispatch_async(
        self,
        intent: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> EnhancedAgentResult:
        """异步派发子代理执行任务。

        使用 ParallelScheduler 进行调度，支持并发控制。

        Args:
            intent: 用户请求/意图
            context: 可选的上下文信息

        Returns:
            EnhancedAgentResult: 执行结果
        """
        agent_type = self._analyze_intent(intent)
        logger.info(f"Async dispatching to {agent_type.value}")

        # 记录交互式上下文
        if self._context is not None:
            self._context.blackboard.set_context("last_user_input", intent)
            if context is not None:
                self._context.blackboard.set_context("last_dispatch_context", context)

        # 创建 TaskBrief
        import uuid
        task_brief = TaskBrief(
            task_id=str(uuid.uuid4()),
            intent=intent,
            context_refs=[],
            extra=context or {},
        )

        # 发送 Agent 开始事件
        self._notify_agent_started(agent_type)

        # 创建 Agent 工厂函数
        def agent_factory(agent_type_str: str) -> Any:
            return self._create_subagent(SubAgentType(agent_type_str))

        # 使用调度器执行
        subagent_result = await self._scheduler.schedule_agent_single(
            task_brief,
            lambda at: self._create_subagent(SubAgentType(at)),
            timeout=self.config.timeout_seconds,
        )

        # 转换为 EnhancedAgentResult
        result = EnhancedAgentResult(
            success=subagent_result.success,
            output=subagent_result.summary,
            error=subagent_result.error,
            elapsed_time=subagent_result.metrics.get("elapsed_time", 0) if subagent_result.metrics else 0,
        )

        # 发送 Agent 完成事件
        self._notify_agent_completed(agent_type, result)

        return result

    async def dispatch_parallel_async(
        self,
        intents: List[str],
        context: Optional[Dict[str, Any]] = None,
        fail_strategy: str = FAIL_STRATEGY_CONTINUE,
    ) -> ParallelResultGroup:
        """异步并行派发多个子代理任务。

        使用 ParallelScheduler 进行并行调度，支持并发控制。

        Args:
            intents: 用户请求/意图列表
            context: 可选的共享上下文信息
            fail_strategy: 失败策略 ("continue" 或 "fail_fast")

        Returns:
            ParallelResultGroup: 并行执行结果
        """
        import uuid
        logger.info(f"Parallel dispatching {len(intents)} tasks")

        # 创建任务组
        tasks = []
        for i, intent in enumerate(intents):
            tasks.append(TaskBrief(
                task_id=f"task_{i}_{uuid.uuid4().hex[:8]}",
                intent=intent,
                context_refs=[],
                extra=context or {},
            ))

        group = ParallelTaskGroup(
            group_id=f"group_{uuid.uuid4().hex[:8]}",
            tasks=tasks,
            max_concurrency=self.config.max_agent_concurrency,
            timeout_per_task=self.config.timeout_seconds,
            fail_strategy=fail_strategy,
        )

        # 记录交互式上下文
        if self._context is not None:
            self._context.blackboard.set_context("last_parallel_intents", intents)

        # 使用调度器执行
        result_group = await self._scheduler.schedule_agent_batch(
            group,
            lambda at: self._create_subagent(SubAgentType(at)),
        )

        logger.info(
            f"Parallel dispatch completed: "
            f"success={result_group.success_count}, "
            f"failure={result_group.failure_count}, "
            f"elapsed={result_group.elapsed_time:.2f}s"
        )

        return result_group

    def get_scheduler_status(self) -> Dict[str, Any]:
        """获取调度器状态。"""
        status = self._scheduler.get_status()
        return {
            "running_agents": status.running_agents,
            "waiting_agents": status.waiting_agents,
            "max_agent_concurrency": status.max_agent_concurrency,
        }

    def cancel_all_tasks(self) -> int:
        """取消所有运行中的任务。

        Returns:
            int: 取消的任务数量
        """
        return self._scheduler.cancel_all()

    def execute_command(self, command: str, require_confirm: bool = True) -> Dict[str, Any]:
        """执行终端命令（带安全检查）

        命令安全策略:
        - 白名单命令：直接执行
        - 需确认命令：需要用户确认
        - 黑名单命令：直接拒绝

        Args:
            command: 要执行的命令
            require_confirm: 是否需要确认（对于需要确认的命令）

        Returns:
            Dict: 执行结果 {success, stdout, stderr, status}
        """
        from mini_coder.tools.filter import BashRestrictedFilter

        filter = BashRestrictedFilter()
        status = filter.get_command_status(command)

        if status == "denied":
            logger.warning(f"Command denied by security filter: {command}")
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Command denied by security policy: {command}",
                "status": "denied"
            }

        if status == "needs_confirm" and require_confirm:
            # 需要用户确认
            logger.info(f"Command requires user confirmation: {command}")
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Command requires user confirmation: {command}",
                "status": "needs_confirm"
            }

        # 白名单命令，直接执行
        if self.command_executor:
            try:
                success, stdout, stderr = self.command_executor(command, timeout=120)
                return {
                    "success": success,
                    "stdout": stdout,
                    "stderr": stderr,
                    "status": "allowed"
                }
            except Exception as e:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": str(e),
                    "status": "error"
                }
        else:
            # 模拟执行
            logger.info(f"Command executed (simulated): {command}")
            return {
                "success": True,
                "stdout": f"Command executed (simulated): {command}",
                "stderr": "",
                "status": "allowed"
            }

    def _analyze_test_failure(self, result: EnhancedAgentResult) -> str:
        """分析测试失败，决定 retry 还是 replan

        决策逻辑:
        - 类型错误、语法错误 → retry (实现细节问题)
        - 断言失败、逻辑错误 → replan (架构问题)
        """
        error_text = (result.error + result.output).lower()

        # 需要 replan 的情况
        replan_indicators = [
            "assertionerror", "assertion error", "assert ",
            "keyerror", "attributeerror", "indexerror",
        ]

        # 只需 retry 的情况
        retry_indicators = [
            "typeerror", "type error", "syntaxerror", "invalid syntax",
            "nameerror", "importerror", "module not found",
        ]

        for indicator in replan_indicators:
            if indicator in error_text:
                logger.info(f"Failure suggests replan: {indicator}")
                return "replan"

        for indicator in retry_indicators:
            if indicator in error_text:
                logger.info(f"Failure suggests retry: {indicator}")
                return "retry"

        return "retry"  # 默认 retry

    def _classify_failure_type(self, error_text: str) -> str:
        """分类失败类型"""
        error_lower = error_text.lower()

        if "typeerror" in error_lower or "incompatible type" in error_lower:
            return "type_error"
        elif "syntaxerror" in error_lower or "invalid syntax" in error_lower:
            return "syntax_error"
        elif "assertionerror" in error_lower or "assert " in error_text:
            return "test_failure"
        elif "importerror" in error_lower or "module not found" in error_lower:
            return "runtime_error"
        else:
            return "test_failure"

    def _extract_error_file(self, error_text: str) -> str:
        """从错误中提取文件路径"""
        import re
        match = re.search(r'File "([^"]+)"', error_text)
        if match:
            return match.group(1)
        match = re.search(r'([^:\s]+\.py):\d+:', error_text)
        if match:
            return match.group(1)
        return "unknown"

    def _extract_error_line(self, error_text: str) -> int:
        """从错误中提取行号"""
        import re
        match = re.search(r'line (\d+)', error_text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        match = re.search(r':(\d+):', error_text)
        if match:
            return int(match.group(1))
        return 0

    def _fail(
        self,
        failure_type: FailureType,
        error: str,
        needs_user_decision: bool = False,
        decision_reason: str = ""
    ) -> EnhancedAgentResult:
        """标记失败并返回结果"""
        self._context.current_state = WorkflowState.FAILED
        self._notify_state_change(WorkflowState.FAILED)

        return EnhancedAgentResult(
            success=False,
            error=error,
            failure_type=failure_type.value,
            needs_user_decision=needs_user_decision,
            decision_reason=decision_reason,
            elapsed_time=self._context.elapsed_time,
        )

    def _create_final_result(self) -> EnhancedAgentResult:
        """创建最终结果"""
        return EnhancedAgentResult(
            success=True,
            output=f"Completed in {self._context.elapsed_time:.2f}s",
            artifacts={
                "plan": self._context.plan,
                **self._context.code_artifacts,
            },
            elapsed_time=self._context.elapsed_time,
        )

    def _notify_state_change(self, new_state: WorkflowState) -> None:
        """通知状态变更"""
        self._context.current_state = new_state

        # 记录到黑板
        self._context.blackboard.log_event(Event(
            type=EventType.STATE_CHANGED,
            data={"new_state": new_state.value},
            source="orchestrator"
        ))

        # 调用回调
        for callback in self._state_callbacks.get(new_state, []):
            try:
                callback(self._context, new_state)
            except Exception:
                logger.exception("State callback error")

    def register_state_callback(self, state: WorkflowState, callback: Callable) -> None:
        """注册状态回调"""
        self._state_callbacks[state].append(callback)

    def register_agent_callback(self, callback: Callable) -> None:
        """注册 Agent 事件回调 (用于 TUI 显示)

        Args:
            callback: 回调函数，签名 (agent_type: SubAgentType, event_type: str, result: Optional[EnhancedAgentResult] = None)
        """
        self._agent_callbacks.append(callback)

    def register_tool_callback(self, callback: Callable) -> None:
        """注册 Tool 事件回调 (用于 TUI 显示)

        Args:
            callback: 回调函数，签名 (tool_name: str, args: str, status: str, duration: float, result: Optional[str] = None)
        """
        self._tool_callbacks.append(callback)

    def _create_agent_event_callback(self, agent_type: SubAgentType) -> Callable[[EventType, Dict], None]:
        """创建 Agent 事件回调，将事件转换为 TUI 友好的格式

        Args:
            agent_type: Agent 类型

        Returns:
            事件回调函数
        """
        def callback(event_type: EventType, data: Dict) -> None:
            # 将 EnhancedAgent 事件转换为 TUI 工具事件
            if event_type in (EventType.TOOL_STARTING, EventType.TOOL_FAILED, EventType.TOOL_COMPLETED):
                tool_name = data.get("tool", "unknown")
                args = data.get("args", "")
                status = data.get("status", "unknown")
                duration = data.get("duration", 0.0)
                result = data.get("result")

                # 调用 tool 回调
                for tool_callback in self._tool_callbacks:
                    try:
                        tool_callback(tool_name, args, status, duration, result)
                    except Exception:
                        logger.exception("Tool callback error")

        return callback

    def _notify_agent_started(self, agent_type: SubAgentType) -> None:
        """通知 Agent 开始执行"""
        for callback in self._agent_callbacks:
            try:
                callback(agent_type, "started", None)
            except Exception:
                logger.exception("Agent started callback error")

    def _notify_agent_completed(self, agent_type: SubAgentType, result: EnhancedAgentResult) -> None:
        """通知 Agent 执行完成"""
        for callback in self._agent_callbacks:
            try:
                callback(agent_type, "completed", result)
            except Exception:
                logger.exception("Agent completed callback error")

    def get_context(self) -> Optional[WorkflowContext]:
        """获取当前上下文"""
        return self._context

    def get_status(self) -> Dict[str, Any]:
        """获取状态摘要"""
        if not self._context:
            return {"status": "idle"}
        return self._context.get_summary()
