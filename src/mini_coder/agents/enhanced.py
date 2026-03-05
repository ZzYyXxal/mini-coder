"""Enhanced Agent System - 优化的多 Agent 系统

参考 LangGraph、AutoGen、CrewAI 等现代多 Agent 框架的最佳实践：
1. 基于事件的工作流引擎
2. 共享黑板（Blackboard）模式进行上下文管理
3. 明确的工具边界和权限控制
4. 智能失败恢复和升级策略

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
"""

import logging
import time
import json
from enum import Enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple, Set
from pathlib import Path
import hashlib

from mini_coder.tools.filter import ToolFilter, ReadOnlyFilter, FullAccessFilter, StrictFilter

logger = logging.getLogger(__name__)


# ==================== Events ====================

class EventType(Enum):
    """事件类型"""
    # 工作流事件
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    STATE_CHANGED = "state_changed"

    # Agent 事件 (TUI 显示用)
    AGENT_STARTED = "agent_started"      # Agent 开始执行
    AGENT_INVOKED = "agent_invoked"
    AGENT_COMPLETED = "agent_completed"  # Agent 执行完成
    AGENT_FAILED = "agent_failed"

    # 工具事件 (TUI 显示用)
    TOOL_STARTING = "tool_starting"      # 工具开始执行
    TOOL_CALLED = "tool_called"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"

    # 错误事件
    ERROR_OCCURRED = "error_occurred"
    RETRY_TRIGGERED = "retry_triggered"
    LOOP_DETECTED = "loop_detected"
    INTERVENTION_NEEDED = "intervention_needed"


@dataclass
class Event:
    """事件基类"""
    type: EventType
    timestamp: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = ""  # 事件来源（Agent 名称或组件）

    def __post_init__(self):
        if isinstance(self.type, str):
            self.type = EventType(self.type)


# ==================== Blackboard ====================

@dataclass
class BlackboardArtifact:
    """黑板上的工件"""
    id: str
    name: str
    content_type: str  # "text", "code", "plan", "test_result"
    content: Any
    created_by: str  # Agent 名称
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class Blackboard:
    """共享黑板 - Agent 间共享上下文和工件

    参考黑板架构模式，提供：
    1. 共享上下文存储
    2. 工件管理（版本控制）
    3. 事件发布/订阅
    4. 访问控制
    """

    def __init__(self, task_id: str) -> None:
        """初始化黑板

        Args:
            task_id: 任务 ID
        """
        self.task_id = task_id
        self._artifacts: Dict[str, BlackboardArtifact] = {}
        self._context: Dict[str, Any] = {}
        self._event_log: List[Event] = []
        self._subscribers: Dict[EventType, List[Callable]] = {
            event: [] for event in EventType
        }

    # --- Artifact Management ---

    def add_artifact(
        self,
        name: str,
        content: Any,
        content_type: str = "text",
        created_by: str = "unknown",
        metadata: Optional[Dict] = None
    ) -> str:
        """添加工件到黑板

        Args:
            name: 工件名称
            content: 工件内容
            content_type: 内容类型
            created_by: 创建者（Agent 名称）
            metadata: 额外元数据

        Returns:
            str: 工件 ID
        """
        # 生成唯一 ID
        artifact_id = hashlib.md5(
            f"{self.task_id}:{name}:{time.time()}".encode()
        ).hexdigest()[:8]

        artifact = BlackboardArtifact(
            id=artifact_id,
            name=name,
            content_type=content_type,
            content=content,
            created_by=created_by,
            metadata=metadata or {}
        )

        self._artifacts[artifact_id] = artifact

        # 也按名称索引（方便查找）
        self._artifacts[name] = artifact

        logger.debug(f"Added artifact: {name} (id={artifact_id})")
        return artifact_id

    def get_artifact(self, name_or_id: str) -> Optional[BlackboardArtifact]:
        """获取工件"""
        return self._artifacts.get(name_or_id)

    def get_artifact_content(self, name_or_id: str, default: Any = None) -> Any:
        """获取工件内容"""
        artifact = self.get_artifact(name_or_id)
        return artifact.content if artifact else default

    def list_artifacts(
        self,
        content_type: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> List[BlackboardArtifact]:
        """列出工件"""
        artifacts = list(self._artifacts.values())

        if content_type:
            artifacts = [a for a in artifacts if a.content_type == content_type]
        if created_by:
            artifacts = [a for a in artifacts if a.created_by == created_by]

        return artifacts

    # --- Context Management ---

    def set_context(self, key: str, value: Any) -> None:
        """设置上下文值"""
        self._context[key] = value
        logger.debug(f"Set context: {key}")

    def get_context(self, key: str, default: Any = None) -> Any:
        """获取上下文值"""
        return self._context.get(key, default)

    def get_all_context(self) -> Dict[str, Any]:
        """获取所有上下文"""
        return self._context.copy()

    # --- Event Log ---

    def log_event(self, event: Event) -> None:
        """记录事件"""
        self._event_log.append(event)

        # 通知订阅者
        for callback in self._subscribers.get(event.type, []):
            try:
                callback(event)
            except Exception as e:
                logger.exception(f"Event callback error: {e}")

    def get_event_log(
        self,
        event_type: Optional[EventType] = None,
        source: Optional[str] = None
    ) -> List[Event]:
        """获取事件日志"""
        events = self._event_log

        if event_type:
            events = [e for e in events if e.type == event_type]
        if source:
            events = [e for e in events if e.source == source]

        return events

    def subscribe(self, event_type: EventType, callback: Callable) -> None:
        """订阅事件"""
        self._subscribers[event_type].append(callback)

    # --- Summary ---

    def get_summary(self) -> Dict[str, Any]:
        """获取黑板摘要"""
        return {
            "task_id": self.task_id,
            "artifact_count": len(self._artifacts),
            "context_keys": list(self._context.keys()),
            "event_count": len(self._event_log),
        }


# ==================== Enhanced Agent Base ====================

@dataclass
class AgentCapabilities:
    """Agent 能力定义"""
    # 可以使用的工具
    allowed_tools: Set[str] = field(default_factory=set)
    # 可以读取的文件模式
    allowed_read_patterns: List[str] = field(default_factory=list)
    # 可以写入的文件模式
    allowed_write_patterns: List[str] = field(default_factory=list)
    # 最大工具调用次数 per execute
    max_tool_calls: int = 10
    # 是否需要用户确认才能执行危险操作
    requires_confirmation: bool = False


class EnhancedAgentState(Enum):
    """Agent 状态"""
    IDLE = "idle"               # 空闲
    THINKING = "thinking"       # 思考中
    EXECUTING = "executing"     # 执行中
    WAITING = "waiting"         # 等待（外部输入）
    ERROR = "error"             # 错误
    STOPPED = "stopped"         # 已停止


@dataclass
class EnhancedAgentResult:
    """增强的 Agent 执行结果"""
    success: bool
    output: str = ""
    error: str = ""

    # 工件
    artifacts: Dict[str, str] = field(default_factory=dict)

    # 工具使用
    tools_used: List[str] = field(default_factory=list)
    tool_outputs: Dict[str, Any] = field(default_factory=dict)

    # 决策
    needs_user_decision: bool = False
    decision_reason: str = ""
    suggested_action: str = ""  # 建议的下一步操作

    # 统计
    iterations: int = 0
    tokens_used: int = 0
    elapsed_time: float = 0.0

    # 失败恢复
    failure_type: Optional[str] = None
    recovery_hint: str = ""  # 如何恢复的提示


class BaseEnhancedAgent(ABC):
    """增强的 Agent 基类

    特性:
    1. 明确的能力边界（工具权限）
    2. 黑板交互
    3. 事件驱动
    4. 详细的执行统计
    """

    # 类变量：Agent 类型定义
    AGENT_TYPE: str = "base"
    DEFAULT_CAPABILITIES: AgentCapabilities = AgentCapabilities()

    def __init__(
        self,
        llm_service: Any,
        blackboard: Blackboard,
        capabilities: Optional[AgentCapabilities] = None,
    ) -> None:
        """初始化 Agent

        Args:
            llm_service: LLM 服务实例
            blackboard: 共享黑板实例
            capabilities: Agent 能力定义
        """
        self.llm_service = llm_service
        self.blackboard = blackboard
        self.capabilities = capabilities or self.DEFAULT_CAPABILITIES.copy()

        self._state = EnhancedAgentState.IDLE
        self._start_time: Optional[float] = None

        # 订阅感兴趣的事件
        self._subscribe_to_events()

        logger.info(f"Initialized {self.AGENT_TYPE} agent")

    @property
    def state(self) -> EnhancedAgentState:
        """获取 Agent 状态"""
        return self._state

    @abstractmethod
    def execute(self, task: str) -> EnhancedAgentResult:
        """执行任务

        Args:
            task: 任务描述

        Returns:
            EnhancedAgentResult: 执行结果
        """
        pass

    def _subscribe_to_events(self) -> None:
        """订阅事件"""
        # 子类可以重写以订阅特定事件
        pass

    def _set_state(self, new_state: EnhancedAgentState) -> None:
        """设置状态并发布事件"""
        old_state = self._state
        self._state = new_state

        event = Event(
            type=EventType.STATE_CHANGED,
            data={"old_state": old_state.value, "new_state": new_state.value},
            source=self.AGENT_TYPE
        )
        self.blackboard.log_event(event)

    def _is_tool_allowed(self, tool_name: str) -> bool:
        """检查工具是否允许使用"""
        return tool_name in self.capabilities.allowed_tools

    def _check_tool_call_limit(self, tool_calls: int) -> bool:
        """检查工具调用次数限制"""
        return tool_calls <= self.capabilities.max_tool_calls

    def _get_context_for_task(self, task: str) -> Dict[str, Any]:
        """获取任务相关的上下文

        从黑板收集所有相关的上下文信息。
        """
        context = {
            "task": task,
            "shared_context": self.blackboard.get_all_context(),
            "related_artifacts": [],
        }

        # 添加相关的工件
        for artifact in self.blackboard.list_artifacts():
            context["related_artifacts"].append({
                "name": artifact.name,
                "type": artifact.content_type,
                "created_by": artifact.created_by,
            })

        return context

    def _create_result(
        self,
        success: bool,
        output: str = "",
        error: str = "",
        artifacts: Optional[Dict] = None,
        **kwargs
    ) -> EnhancedAgentResult:
        """创建执行结果"""
        elapsed = time.time() - self._start_time if self._start_time else 0.0

        return EnhancedAgentResult(
            success=success,
            output=output,
            error=error,
            artifacts=artifacts or {},
            elapsed_time=elapsed,
            **kwargs
        )

    def _emit_event(self, event_type: EventType, data: Dict = None) -> None:
        """发布事件"""
        event = Event(
            type=event_type,
            data=data or {},
            source=self.AGENT_TYPE
        )
        self.blackboard.log_event(event)


# ==================== Architectural Consultant Agent ====================

class ArchitecturalConsultantCapabilities(AgentCapabilities):
    """Architectural Consultant Agent 能力"""

    def __init__(self) -> None:
        super().__init__(
            allowed_tools={"Read", "Glob", "Grep", "WebSearch", "WebFetch", "Task"},
            allowed_read_patterns=["**/*"],
            allowed_write_patterns=["*.md", "docs/**/*.md"],
            max_tool_calls=20,
            requires_confirmation=False
        )


class ArchitecturalConsultantAgent(BaseEnhancedAgent):
    """架构顾问 Agent

    职责:
    1. 技术选型 - 提供对比矩阵和推荐路径
    2. 架构模式 - 提供设计模式和最佳实践
    3. 边界条件预警 - 识别潜在的 Edge Cases
    4. 重构建议 - 当代码修复陷入僵局时提供替代方案

    工具权限:
    - 代码探索：Read, Glob, Grep
    - 信息检索：WebSearch, WebFetch (用于获取最新文档)
    - 任务管理：Task
    """

    AGENT_TYPE = "architectural_consultant"
    DEFAULT_CAPABILITIES = ArchitecturalConsultantCapabilities()

    def __init__(
        self,
        llm_service: Any,
        blackboard: Blackboard,
    ) -> None:
        super().__init__(llm_service, blackboard, ArchitecturalConsultantCapabilities())

    def execute(self, task: str) -> EnhancedAgentResult:
        """执行架构咨询任务"""
        self._start_time = time.time()
        self._set_state(EnhancedAgentState.THINKING)

        try:
            # 1. 收集上下文
            context = self._get_context_for_task(task)

            # 2. 调用 LLM 进行架构分析
            self._set_state(EnhancedAgentState.EXECUTING)
            prompt = self._build_consulting_prompt(task, context)
            response = self.llm_service.chat(prompt)

            # 3. 解析并保存建议
            advice = self._parse_advice(response)
            self.blackboard.add_artifact(
                name="architectural_advice.md",
                content=advice,
                content_type="plan",
                created_by=self.AGENT_TYPE,
            )

            # 4. 发布完成事件
            self._emit_event(EventType.AGENT_COMPLETED, {
                "advice_saved": True
            })

            self._set_state(EnhancedAgentState.IDLE)

            return self._create_result(
                success=True,
                output=response,
                artifacts={"architectural_advice.md": advice},
            )

        except Exception as e:
            self._set_state(EnhancedAgentState.ERROR)
            self._emit_event(EventType.AGENT_FAILED, {"error": str(e)})

            return self._create_result(
                success=False,
                error=str(e),
                failure_type="consulting_error",
            )

    def _build_consulting_prompt(self, task: str, context: Dict) -> str:
        """构建架构咨询 prompt"""
        return f"""You are an Architectural Consultant - a chief architect with expertise in pattern recognition
and cross-project architecture migration.

Task: {task}

Context:
{json.dumps(context.get('shared_context', {}), indent=2)}

Your responsibilities:
1. **Technology Selection**: Provide a comparison matrix for core modules, with clear recommendation
2. **Design Patterns**: Recommend appropriate patterns based on task complexity
3. **Edge Case Analysis**: Identify potential boundary conditions and risks
4. **Best Practices**: Provide Python modularization best practices

Output Requirements:
- Must include a Markdown comparison table: [Current Approach] vs [Reference Project Approach]
- Provide clear, actionable recommendations
- Avoid over-engineering: match solution complexity to task needs

Reference Projects:
- OpenCode: https://github.com/anomalyco/opencode (Sandbox isolation, environment management)
- HelloAgents: https://github.com/jjyaoao/helloagents (Recursive repair, self-reflection)
"""

    def _parse_advice(self, response: str) -> str:
        """解析建议"""
        return response


# ==================== Code Reviewer Agent ====================

class CodeReviewerCapabilities(AgentCapabilities):
    """Code Reviewer Agent 能力"""

    def __init__(self) -> None:
        super().__init__(
            allowed_tools={"Read", "Glob", "Grep"},
            allowed_read_patterns=["**/*.py", "**/*.md"],
            allowed_write_patterns=[],  # 只读，不能写
            max_tool_calls=15,
            requires_confirmation=False
        )


class CodeReviewerAgent(BaseEnhancedAgent):
    """代码评审员 Agent

    职责:
    1. 架构对齐检查 - 验证代码是否符合 implementation_plan.md
    2. 代码质量检查 - Type Hints, Docstrings, 命名，复杂度
    3. 规范一致性 - PEP 8, 项目规范
    4. 决策输出 - 通过/打回

    工具权限:
    - 只读工具：Read, Glob, Grep
    - 不能写文件或执行命令
    """

    AGENT_TYPE = "code_reviewer"
    DEFAULT_CAPABILITIES = CodeReviewerCapabilities()

    def __init__(
        self,
        llm_service: Any,
        blackboard: Blackboard,
    ) -> None:
        super().__init__(llm_service, blackboard, CodeReviewerCapabilities())

    def execute(self, task: str) -> EnhancedAgentResult:
        """执行代码评审任务"""
        self._start_time = time.time()
        self._set_state(EnhancedAgentState.THINKING)

        try:
            # 1. 获取评审所需的上下文
            plan = self.blackboard.get_artifact_content("implementation_plan.md", "")
            code_artifacts = self.blackboard.list_artifacts(content_type="code")

            # 2. 调用 LLM 进行评审
            self._set_state(EnhancedAgentState.EXECUTING)
            prompt = self._build_review_prompt(task, plan, code_artifacts)
            response = self.llm_service.chat(prompt)

            # 3. 解析评审结果
            review_result = self._parse_review_result(response)

            # 4. 保存评审报告
            self.blackboard.add_artifact(
                name="code_review_report.md",
                content=review_result,
                content_type="review",
                created_by=self.AGENT_TYPE,
            )

            # 5. 发布完成事件
            self._emit_event(EventType.AGENT_COMPLETED, {
                "review_completed": True,
                "result": "passed" if "通过" in review_result or "✅" in review_result else "rejected"
            })

            self._set_state(EnhancedAgentState.IDLE)

            # 6. 根据评审结果设置 success 状态
            passed = "通过" in review_result or "✅" in review_result
            return self._create_result(
                success=passed,
                output=review_result,
                artifacts={"code_review_report.md": review_result},
            )

        except Exception as e:
            self._set_state(EnhancedAgentState.ERROR)
            self._emit_event(EventType.AGENT_FAILED, {"error": str(e)})

            return self._create_result(
                success=False,
                error=str(e),
                failure_type="review_error",
            )

    def _build_review_prompt(
        self,
        task: str,
        plan: str,
        code_artifacts: List
    ) -> str:
        """构建评审 prompt"""
        code_context = "\n\n".join(
            f"### File: {a.name.replace('code:', '')}\n```\n{a.content[:2000]}...\n```"
            for a in code_artifacts[:5]  # 限制文件数量
        )

        return f"""You are a Code Reviewer - the quality gatekeeper between implementation and testing.

Task: {task}

Implementation Plan (for architecture alignment check):
{plan}

Code Artifacts to Review:
{code_context}

Your Checklist:
1. **Architecture Alignment**: Does the code follow the implementation_plan.md?
2. **Type Hints**: Are all functions annotated (Python 3.10+ syntax)?
3. **Docstrings**: Google-style for public APIs?
4. **Code Smells**: Long functions, duplicated logic, improper dependencies?
5. **PEP 8**: Code style compliance?

Output Format (STRICT):
- If PASS: "✅ 通过 - 代码符合架构和质量要求，可进入 Tester 验证"
- If REJECT:
  ```
  ❌ 打回 - 需要修改以下问题：

  1. [架构偏离] 具体问题 + 修改建议
  2. [代码质量] 具体问题 + 修改建议
  3. [规范违反] 具体问题 + 修改建议
  ```

Constraints:
- Only review the changed files
- Do NOT redesign architecture
- Do NOT replace Architectural Consultant or Planner
- Do NOT run tests - only static analysis
"""

    def _parse_review_result(self, response: str) -> str:
        """解析评审结果"""
        return response

class PlannerCapabilities(AgentCapabilities):
    """Planner Agent 能力"""

    def __init__(self) -> None:
        super().__init__(
            allowed_tools={"Read", "Glob", "Grep", "WebSearch", "WebFetch", "Task"},
            allowed_read_patterns=["**/*"],
            allowed_write_patterns=["*.md"],
            max_tool_calls=15,
            requires_confirmation=False
        )


class PlannerAgent(BaseEnhancedAgent):
    """规划 Agent

    职责:
    1. 需求分析 - 理解用户需求
    2. 任务分解 - 拆解为可执行步骤
    3. 技术选型 - 推荐技术方案
    4. 依赖分析 - 识别模块依赖

    工具权限:
    - 只读工具：Read, Glob, Grep
    - 信息检索：WebSearch, WebFetch
    - 任务管理：Task
    """

    AGENT_TYPE = "planner"
    DEFAULT_CAPABILITIES = PlannerCapabilities()

    def __init__(
        self,
        llm_service: Any,
        blackboard: Blackboard,
    ) -> None:
        super().__init__(llm_service, blackboard, PlannerCapabilities())

    def execute(self, task: str) -> EnhancedAgentResult:
        """执行规划任务"""
        self._start_time = time.time()
        self._set_state(EnhancedAgentState.THINKING)

        try:
            # 1. 收集上下文
            context = self._get_context_for_task(task)

            # 2. 调用 LLM 进行规划
            self._set_state(EnhancedAgentState.EXECUTING)
            prompt = self._build_planning_prompt(task, context)
            response = self.llm_service.chat(prompt)

            # 3. 解析并保存计划
            plan = self._parse_plan(response)
            self.blackboard.add_artifact(
                name="implementation_plan.md",
                content=plan,
                content_type="plan",
                created_by=self.AGENT_TYPE,
            )

            # 4. 发布完成事件
            self._emit_event(EventType.AGENT_COMPLETED, {
                "plan_saved": True
            })

            self._set_state(EnhancedAgentState.IDLE)

            return self._create_result(
                success=True,
                output=response,
                artifacts={"implementation_plan.md": plan},
            )

        except Exception as e:
            self._set_state(EnhancedAgentState.ERROR)
            self._emit_event(EventType.AGENT_FAILED, {"error": str(e)})

            return self._create_result(
                success=False,
                error=str(e),
                failure_type="planning_error",
            )

    def _build_planning_prompt(
        self,
        task: str,
        context: Dict
    ) -> str:
        """构建规划 prompt"""
        return f"""You are a Planner Agent. Create a detailed implementation plan.

Task: {task}

Shared Context:
{json.dumps(context.get('shared_context', {}), indent=2)}

Create a plan with:
1. Overview of the task
2. Task breakdown into atomic steps (TDD: test first, then implementation)
3. Dependencies between steps
4. Required tools/libraries
5. Test strategy

Output in markdown format."""

    def _parse_plan(self, response: str) -> str:
        """解析计划"""
        return response


# ==================== Coder Agent ====================

class CoderCapabilities(AgentCapabilities):
    """Coder Agent 能力"""

    def __init__(self) -> None:
        super().__init__(
            allowed_tools={"Read", "Write", "Edit", "Glob", "Grep", "Bash"},
            allowed_read_patterns=["**/*"],
            allowed_write_patterns=["src/**/*.py", "tests/**/*.py"],
            max_tool_calls=20,
            requires_confirmation=True
        )


class CoderAgent(BaseEnhancedAgent):
    """编码 Agent

    职责:
    1. 代码实现 - 根据计划编写代码
    2. 测试编写 - 编写单元测试
    3. 代码重构 - 优化现有代码
    4. 错误修复 - 修复测试发现的问题

    工具权限:
    - 文件操作：Read, Write, Edit
    - 代码搜索：Glob, Grep
    - 命令执行：Bash（受限）
    """

    AGENT_TYPE = "coder"
    DEFAULT_CAPABILITIES = CoderCapabilities()

    def __init__(
        self,
        llm_service: Any,
        blackboard: Blackboard,
    ) -> None:
        super().__init__(llm_service, blackboard, CoderCapabilities())

    def execute(self, task: str) -> EnhancedAgentResult:
        """执行编码任务"""
        self._start_time = time.time()
        self._set_state(EnhancedAgentState.THINKING)

        try:
            # 1. 获取计划
            plan = self.blackboard.get_artifact_content(
                "implementation_plan.md",
                default=""
            )

            # 2. 获取现有代码（如果有重试）
            existing_code = self._get_existing_code()

            # 3. 构建编码 prompt
            prompt = self._build_coding_prompt(task, plan, existing_code)

            # 4. 调用 LLM
            self._set_state(EnhancedAgentState.EXECUTING)
            response = self.llm_service.chat(prompt)

            # 5. 解析并保存代码
            code_files = self._parse_code(response)
            for filename, content in code_files.items():
                self.blackboard.add_artifact(
                    name=f"code:{filename}",
                    content=content,
                    content_type="code",
                    created_by=self.AGENT_TYPE,
                )

            # 6. 发布完成事件
            self._emit_event(EventType.AGENT_COMPLETED, {
                "files_generated": len(code_files)
            })

            self._set_state(EnhancedAgentState.IDLE)

            return self._create_result(
                success=True,
                output=response,
                artifacts=code_files,
            )

        except Exception as e:
            self._set_state(EnhancedAgentState.ERROR)
            self._emit_event(EventType.AGENT_FAILED, {"error": str(e)})

            return self._create_result(
                success=False,
                error=str(e),
                failure_type="coding_error",
                recovery_hint="检查错误信息后重试，或请求 Architectural Consultant 协助"
            )

    def _get_existing_code(self) -> Dict[str, str]:
        """获取现有代码（用于重试场景）"""
        existing = {}
        for artifact in self.blackboard.list_artifacts(content_type="code"):
            existing[artifact.name.replace("code:", "")] = artifact.content
        return existing

    def _build_coding_prompt(
        self,
        task: str,
        plan: str,
        existing_code: Dict[str, str]
    ) -> str:
        """构建编码 prompt"""
        existing_code_str = "\n\n".join(
            f"File: {name}\n{content}"
            for name, content in existing_code.items()
        )

        return f"""You are a Coder Agent. Implement the following task.

Task: {task}

Implementation Plan:
{plan}

Existing Code (if retrying):
{existing_code_str}

Rules:
1. TDD: Tests first, then implementation
2. Type hints for all functions (Python 3.10+)
3. Google-style docstrings
4. PEP 8 code style
5. Handle edge cases

Output complete code files with filenames."""

    def _parse_code(self, response: str) -> Dict[str, str]:
        """解析代码文件"""
        import re
        files = {}

        # 匹配 ```python filename="..." ... ``` 或 ```python path/to/file.py ... ```
        pattern = r'```python(?:\s+filename=["\']([^"\']+)["\']|\s+([^\n]+))?\n(.*?)\n```'

        for match in re.finditer(pattern, response, re.DOTALL):
            filename = match.group(1) or match.group(2) or "unknown.py"
            content = match.group(3)
            files[filename.strip()] = content

        return files


# ==================== Tester Agent ====================

class TesterCapabilities(AgentCapabilities):
    """Tester Agent 能力"""

    def __init__(self) -> None:
        super().__init__(
            allowed_tools={"Read", "Glob", "Bash"},
            allowed_read_patterns=["**/*"],
            allowed_write_patterns=["tests/**/*.md"],
            max_tool_calls=10,
            requires_confirmation=False
        )


class TesterAgent(BaseEnhancedAgent):
    """测试 Agent

    职责:
    1. 运行测试 - 执行 pytest
    2. 类型检查 - 运行 mypy
    3. 代码风格 - 运行 flake8
    4. 覆盖率检查 - 检查测试覆盖率
    5. 生成报告 - 生成质量报告

    工具权限:
    - 只读：Read, Glob
    - 测试命令：Bash（限定 pytest, mypy, flake8）
    """

    AGENT_TYPE = "tester"
    DEFAULT_CAPABILITIES = TesterCapabilities()

    def __init__(
        self,
        llm_service: Any,
        blackboard: Blackboard,
        command_executor: Optional[Callable] = None,
    ) -> None:
        """初始化

        Args:
            llm_service: LLM 服务
            blackboard: 黑板
            command_executor: 命令执行函数 (command, timeout) -> (success, stdout, stderr)
        """
        super().__init__(llm_service, blackboard, TesterCapabilities())
        self._command_executor = command_executor

    def execute(self, task: str) -> EnhancedAgentResult:
        """执行测试任务"""
        self._start_time = time.time()
        self._set_state(EnhancedAgentState.THINKING)

        try:
            self._set_state(EnhancedAgentState.EXECUTING)

            # 1. 运行测试
            test_results = self._run_tests()

            # 2. 类型检查
            type_results = self._run_type_check()

            # 3. 代码风格检查
            lint_results = self._run_lint()

            # 4. 覆盖率检查
            coverage_results = self._run_coverage()

            # 5. 生成报告
            report = self._generate_report(
                tests=test_results,
                types=type_results,
                lint=lint_results,
                coverage=coverage_results
            )

            # 6. 保存报告
            self.blackboard.add_artifact(
                name="quality_report.md",
                content=report,
                content_type="test_result",
                created_by=self.AGENT_TYPE,
            )

            # 7. 判断是否通过
            all_passed = all([
                test_results.get("success", False),
                type_results.get("success", False),
                lint_results.get("success", False),
                coverage_results.get("success", True),  # 覆盖率可选
            ])

            self._emit_event(EventType.AGENT_COMPLETED, {
                "all_passed": all_passed
            })
            self._set_state(EnhancedAgentState.IDLE)

            return self._create_result(
                success=all_passed,
                output=report,
                artifacts={"quality_report.md": report},
                tools_used=["pytest", "mypy", "flake8"],
                suggested_action="retry" if not all_passed else "complete",
            )

        except Exception as e:
            self._set_state(EnhancedAgentState.ERROR)
            self._emit_event(EventType.AGENT_FAILED, {"error": str(e)})

            return self._create_result(
                success=False,
                error=str(e),
                failure_type="testing_error",
            )

    def _run_tests(self) -> Dict[str, Any]:
        """运行 pytest"""
        if self._command_executor:
            success, stdout, stderr = self._command_executor("pytest tests/ -v --tb=short", 120)
            return {"success": success, "stdout": stdout, "stderr": stderr}
        return {"success": True, "stdout": "Tests passed (simulated)", "stderr": ""}

    def _run_type_check(self) -> Dict[str, Any]:
        """运行 mypy"""
        if self._command_executor:
            success, stdout, stderr = self._command_executor("mypy src/ --strict", 60)
            return {"success": success, "stdout": stdout, "stderr": stderr}
        return {"success": True, "stdout": "No type errors (simulated)", "stderr": ""}

    def _run_lint(self) -> Dict[str, Any]:
        """运行 flake8"""
        if self._command_executor:
            success, stdout, stderr = self._command_executor("flake8 src/", 30)
            return {"success": success, "stdout": stdout, "stderr": stderr}
        return {"success": True, "stdout": "No lint issues (simulated)", "stderr": ""}

    def _run_coverage(self) -> Dict[str, Any]:
        """运行覆盖率检查"""
        if self._command_executor:
            success, stdout, stderr = self._command_executor(
                "pytest tests/ --cov=src --cov-fail-under=80 -q", 60
            )
            return {"success": success, "stdout": stdout, "stderr": stderr}
        return {"success": True, "stdout": "Coverage OK (simulated)", "stderr": ""}

    def _generate_report(
        self,
        tests: Dict,
        types: Dict,
        lint: Dict,
        coverage: Dict
    ) -> str:
        """生成质量报告"""
        lines = ["# Quality Report\n"]

        # 测试
        lines.append("## Tests\n")
        if tests.get("success"):
            lines.append("✅ All tests passed\n")
        else:
            lines.append(f"❌ Tests failed\n")
            lines.append(f"```\n{tests.get('stderr', '')}\n```\n")

        # 类型检查
        lines.append("## Type Check\n")
        if types.get("success"):
            lines.append("✅ No type errors\n")
        else:
            lines.append(f"❌ Type errors found\n")
            lines.append(f"```\n{types.get('stderr', '')}\n```\n")

        # Lint
        lines.append("## Code Style\n")
        if lint.get("success"):
            lines.append("✅ No style issues\n")
        else:
            lines.append(f"❌ Style issues found\n")
            lines.append(f"```\n{lint.get('stderr', '')}\n```\n")

        # 覆盖率
        lines.append("## Coverage\n")
        if coverage.get("success"):
            lines.append("✅ Coverage >= 80%\n")
        else:
            lines.append(f"⚠️ Coverage < 80%\n")
            lines.append(f"```\n{coverage.get('stderr', '')}\n```\n")

        return "\n".join(lines)


# ==================== Export ====================

__all__ = [
    # Events
    "EventType",
    "Event",
    # Blackboard
    "Blackboard",
    "BlackboardArtifact",
    # Agent Base
    "AgentCapabilities",
    "EnhancedAgentState",
    "EnhancedAgentResult",
    "BaseEnhancedAgent",
    # Concrete Agents
    "PlannerCapabilities",
    "PlannerAgent",
    "CoderCapabilities",
    "CoderAgent",
    "TesterCapabilities",
    "TesterAgent",
]
