"""Agent 任务与结果的数据结构（供 Scheduler、Orchestrator 使用）。

本模块提供 TaskBrief、SubagentResult、ParallelTaskGroup 等**纯数据结构**，用于：
- Scheduler 的 schedule_agent_single / schedule_agent_batch：任务描述与返回结果形态。
- Orchestrator 的 dispatch_async / dispatch_parallel_async：构造任务并接收 SubagentResult。

不再使用 Mailbox 机制：Blackboard 已移除 post_message/collect_messages/get_latest_task_brief/post_result；
Agent 间应传递的数据由 Orchestrator 在调用 agent.execute(task, context=...) 时通过 context 显式传入，
与 LangGraph 的显式状态传递一致。
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# 允许的 agent 标识（与 SubAgentType 对齐，小写）
AGENT_MAIN = "main"
AGENT_EXPLORER = "explorer"
AGENT_PLANNER = "planner"
AGENT_CODER = "coder"
AGENT_REVIEWER = "reviewer"
AGENT_BASH = "bash"

# 消息类型常量
MESSAGE_TYPE_TASK = "task"
MESSAGE_TYPE_RESULT = "result"
MESSAGE_TYPE_REQUEST = "request"
MESSAGE_TYPE_BATCH_TASK = "batch_task"
MESSAGE_TYPE_BATCH_RESULT = "batch_result"

# 失败策略
FAIL_STRATEGY_CONTINUE = "continue"
FAIL_STRATEGY_FAIL_FAST = "fail_fast"

# 默认并发和超时配置
DEFAULT_MAX_CONCURRENCY = 3
DEFAULT_AGENT_TIMEOUT = 300.0  # 5 分钟
DEFAULT_TOOL_TIMEOUT = 60.0   # 1 分钟
DEFAULT_BATCH_TIMEOUT = 600.0 # 10 分钟


@dataclass
class TaskBrief:
    """主代理下发给子代理的任务摘要（type=task 的 payload）。"""

    task_id: str
    intent: str
    context_refs: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SubagentResult:
    """子代理回传给主代理的结构化结果（type=result 的 payload）。"""

    task_id: str
    from_agent: str
    success: bool
    summary: str
    artifact_refs: List[str] = field(default_factory=list)
    error: Optional[str] = None
    next_suggested_agent: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None


# ==================== 并行执行 Schema ====================


@dataclass
class ParallelTaskGroup:
    """批量并行任务派发（type=batch_task 的 payload）。

    支持多个子代理并行执行，由调度器统一管理并发和超时。
    """

    group_id: str
    tasks: List[TaskBrief]
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY
    timeout_per_task: float = DEFAULT_AGENT_TIMEOUT
    timeout_total: float = DEFAULT_BATCH_TIMEOUT
    fail_strategy: str = FAIL_STRATEGY_CONTINUE

    def __post_init__(self):
        if self.max_concurrency < 1 or self.max_concurrency > 3:
            raise ValueError(f"max_concurrency must be 1-3, got {self.max_concurrency}")
        if self.fail_strategy not in (FAIL_STRATEGY_CONTINUE, FAIL_STRATEGY_FAIL_FAST):
            raise ValueError(f"Invalid fail_strategy: {self.fail_strategy}")


@dataclass
class ParallelResultGroup:
    """批量并行任务结果汇总（type=batch_result 的 payload）。"""

    group_id: str
    results: List[SubagentResult]
    success_count: int
    failure_count: int
    elapsed_time: float
    cancelled_count: int = 0
    partial_success: bool = False


# ==================== Tool 并行调用 Schema ====================


@dataclass
class ToolCall:
    """单次 Tool 调用请求。"""

    call_id: str
    tool_name: str
    arguments: Dict[str, Any]
    depends_on: List[str] = field(default_factory=list)


@dataclass
class ToolCallResult:
    """单次 Tool 调用结果。"""

    call_id: str
    tool_name: str
    success: bool
    duration: float
    output: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class ToolBatchRequest:
    """Tool 批量并行调用请求。

    支持声明依赖关系（DAG），由 ToolScheduler 按拓扑序分批执行。
    """

    batch_id: str
    tool_calls: List[ToolCall]
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY
    timeout_per_call: float = DEFAULT_TOOL_TIMEOUT

    def __post_init__(self):
        if self.max_concurrency < 1 or self.max_concurrency > 3:
            raise ValueError(f"max_concurrency must be 1-3, got {self.max_concurrency}")


@dataclass
class ToolBatchResult:
    """Tool 批量并行调用结果。"""

    batch_id: str
    results: List[ToolCallResult]
    success_count: int
    failure_count: int
    elapsed_time: float


@dataclass
class MailboxMessage:
    """Mailbox 消息信封：定向投递，带类型与结构化 payload。"""

    message_id: str
    to_agent: str
    from_agent: str
    type: str  # "task" | "result" | "request" | "batch_task" | "batch_result"
    payload: Dict[str, Any]
    created_at: float = field(default_factory=time.time)

    @classmethod
    def create_task(
        cls,
        to_agent: str,
        task_id: str,
        intent: str,
        context_refs: Optional[List[str]] = None,
        extra: Optional[Dict[str, Any]] = None,
        message_id: Optional[str] = None,
    ) -> "MailboxMessage":
        """构造一条下发给子代理的 task 消息。"""
        brief = TaskBrief(
            task_id=task_id,
            intent=intent,
            context_refs=context_refs or [],
            extra=extra or {},
        )
        payload = {
            "task_id": brief.task_id,
            "intent": brief.intent,
            "context_refs": brief.context_refs,
            "extra": brief.extra,
        }
        return cls(
            message_id=message_id or str(uuid.uuid4()),
            to_agent=to_agent,
            from_agent=AGENT_MAIN,
            type=MESSAGE_TYPE_TASK,
            payload=payload,
        )

    @classmethod
    def create_result(
        cls,
        result: SubagentResult,
        message_id: Optional[str] = None,
    ) -> "MailboxMessage":
        """构造一条子代理回传给 main 的 result 消息。"""
        payload = {
            "task_id": result.task_id,
            "from_agent": result.from_agent,
            "success": result.success,
            "summary": result.summary,
            "artifact_refs": result.artifact_refs,
            "error": result.error,
            "next_suggested_agent": result.next_suggested_agent,
            "metrics": result.metrics,
        }
        return cls(
            message_id=message_id or str(uuid.uuid4()),
            to_agent=AGENT_MAIN,
            from_agent=result.from_agent,
            type=MESSAGE_TYPE_RESULT,
            payload=payload,
        )

    @classmethod
    def create_batch_task(
        cls,
        group: ParallelTaskGroup,
        message_id: Optional[str] = None,
    ) -> "MailboxMessage":
        """构造一条批量并行任务派发消息（batch_task）。"""
        payload = {
            "group_id": group.group_id,
            "tasks": [
                {
                    "task_id": t.task_id,
                    "intent": t.intent,
                    "context_refs": t.context_refs,
                    "extra": t.extra,
                }
                for t in group.tasks
            ],
            "max_concurrency": group.max_concurrency,
            "timeout_per_task": group.timeout_per_task,
            "timeout_total": group.timeout_total,
            "fail_strategy": group.fail_strategy,
        }
        return cls(
            message_id=message_id or str(uuid.uuid4()),
            to_agent=AGENT_MAIN,  # 广播给所有目标 agent
            from_agent=AGENT_MAIN,
            type=MESSAGE_TYPE_BATCH_TASK,
            payload=payload,
        )

    @classmethod
    def create_batch_result(
        cls,
        result_group: ParallelResultGroup,
        message_id: Optional[str] = None,
    ) -> "MailboxMessage":
        """构造一条批量并行结果收集消息（batch_result）。"""
        payload = {
            "group_id": result_group.group_id,
            "results": [
                {
                    "task_id": r.task_id,
                    "from_agent": r.from_agent,
                    "success": r.success,
                    "summary": r.summary,
                    "artifact_refs": r.artifact_refs,
                    "error": r.error,
                    "next_suggested_agent": r.next_suggested_agent,
                    "metrics": r.metrics,
                }
                for r in result_group.results
            ],
            "success_count": result_group.success_count,
            "failure_count": result_group.failure_count,
            "cancelled_count": result_group.cancelled_count,
            "elapsed_time": result_group.elapsed_time,
            "partial_success": result_group.partial_success,
        }
        return cls(
            message_id=message_id or str(uuid.uuid4()),
            to_agent=AGENT_MAIN,
            from_agent=AGENT_MAIN,
            type=MESSAGE_TYPE_BATCH_RESULT,
            payload=payload,
        )

    def get_task_brief(self) -> Optional[TaskBrief]:
        """若 type=task，解析 payload 为 TaskBrief。"""
        if self.type != MESSAGE_TYPE_TASK:
            return None
        p = self.payload
        return TaskBrief(
            task_id=p["task_id"],
            intent=p["intent"],
            context_refs=p.get("context_refs") or [],
            extra=p.get("extra") or {},
        )

    def get_subagent_result(self) -> Optional[SubagentResult]:
        """若 type=result，解析 payload 为 SubagentResult。"""
        if self.type != MESSAGE_TYPE_RESULT:
            return None
        p = self.payload
        return SubagentResult(
            task_id=p["task_id"],
            from_agent=p["from_agent"],
            success=p["success"],
            summary=p["summary"],
            artifact_refs=p.get("artifact_refs") or [],
            error=p.get("error"),
            next_suggested_agent=p.get("next_suggested_agent"),
            metrics=p.get("metrics"),
        )

    def get_parallel_task_group(self) -> Optional[ParallelTaskGroup]:
        """若 type=batch_task，解析 payload 为 ParallelTaskGroup。"""
        if self.type != MESSAGE_TYPE_BATCH_TASK:
            return None
        p = self.payload
        tasks = [
            TaskBrief(
                task_id=t["task_id"],
                intent=t["intent"],
                context_refs=t.get("context_refs") or [],
                extra=t.get("extra") or {},
            )
            for t in p["tasks"]
        ]
        return ParallelTaskGroup(
            group_id=p["group_id"],
            tasks=tasks,
            max_concurrency=p.get("max_concurrency", DEFAULT_MAX_CONCURRENCY),
            timeout_per_task=p.get("timeout_per_task", DEFAULT_AGENT_TIMEOUT),
            timeout_total=p.get("timeout_total", DEFAULT_BATCH_TIMEOUT),
            fail_strategy=p.get("fail_strategy", FAIL_STRATEGY_CONTINUE),
        )

    def get_parallel_result_group(self) -> Optional[ParallelResultGroup]:
        """若 type=batch_result，解析 payload 为 ParallelResultGroup。"""
        if self.type != MESSAGE_TYPE_BATCH_RESULT:
            return None
        p = self.payload
        results = [
            SubagentResult(
                task_id=r["task_id"],
                from_agent=r["from_agent"],
                success=r["success"],
                summary=r["summary"],
                artifact_refs=r.get("artifact_refs") or [],
                error=r.get("error"),
                next_suggested_agent=r.get("next_suggested_agent"),
                metrics=r.get("metrics"),
            )
            for r in p["results"]
        ]
        return ParallelResultGroup(
            group_id=p["group_id"],
            results=results,
            success_count=p["success_count"],
            failure_count=p["failure_count"],
            cancelled_count=p.get("cancelled_count", 0),
            elapsed_time=p["elapsed_time"],
            partial_success=p.get("partial_success", False),
        )
