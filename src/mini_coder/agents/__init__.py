"""Agents Package - 多 Agent 系统

提供自动化的 需求→代码→测试→(重分析) 循环能力。

核心组件:
- Orchestrator: 工作流协调器
- Enhanced Agents: 增强的 Agent 类 (Planner, Coder, Tester)
- Blackboard: 共享上下文管理

Agent 基类架构:
- BaseEnhancedAgent: 工作流参与者，需要 Blackboard，支持事件驱动和 Mailbox 协议
  - 子类: PlannerAgent, CoderAgent, TesterAgent
- BaseAgent: 独立工具型 Agent，支持动态提示词加载，无 Blackboard 依赖
  - 子类: ExplorerAgent, ReviewerAgent, BashAgent, GeneralPurposeAgent

共享组件:
- AgentCapabilities: Agent 能力定义（工具权限、文件访问模式等）
- EventType/Event: 事件系统
- Blackboard: 共享上下文和工件管理
"""

from mini_coder.agents.orchestrator import (
    WorkflowState,
    FailureType,
    WorkflowConfig,
    WorkflowContext,
    WorkflowOrchestrator,
    SubAgentType,
)

from mini_coder.agents.enhanced import (
    # Events
    EventType,
    Event,
    # Blackboard
    Blackboard,
    BlackboardArtifact,
    # Agent Base
    AgentCapabilities,
    EnhancedAgentState,
    EnhancedAgentResult,
    BaseEnhancedAgent,
    # Concrete Agents
    PlannerAgent,
    CoderAgent,
    TesterAgent,
    PlannerCapabilities,
    CoderCapabilities,
    TesterCapabilities,
)

from mini_coder.agents.mailbox import (
    TaskBrief,
    SubagentResult,
    MailboxMessage,
    AGENT_MAIN,
    MESSAGE_TYPE_TASK,
    MESSAGE_TYPE_RESULT,
    MESSAGE_TYPE_BATCH_TASK,
    MESSAGE_TYPE_BATCH_RESULT,
    # Parallel Schemas
    ParallelTaskGroup,
    ParallelResultGroup,
    ToolCall,
    ToolCallResult,
    ToolBatchRequest,
    ToolBatchResult,
    # Constants
    FAIL_STRATEGY_CONTINUE,
    FAIL_STRATEGY_FAIL_FAST,
    DEFAULT_MAX_CONCURRENCY,
    DEFAULT_AGENT_TIMEOUT,
    DEFAULT_TOOL_TIMEOUT,
)

from mini_coder.agents.scheduler import (
    ParallelScheduler,
    SchedulerStatus,
)

from mini_coder.agents.tool_scheduler import (
    ToolScheduler,
    DependencyGraph,
    ToolExecutionBatch,
)

from mini_coder.agents.base import (
    AgentConfig,
    AgentState,
    AgentResult as BaseAgentResult,
    BaseAgent,
    AgentTeam,
    # New Subagents
    ExplorerCapabilities,
    ExplorerAgent,
    ReviewerCapabilities,
    ReviewerAgent,
    BashCapabilities,
    BashAgent,
    # General Purpose & Guide
    GeneralPurposeCapabilities,
    GeneralPurposeAgent,
    MiniCoderGuideCapabilities,
    MiniCoderGuideAgent,
)

from mini_coder.agents.output_parser import (
    # Enums
    MainAgentOutputType,
    ReviewerResultType,
    UnifiedOutputType,
    # Data Classes
    SubTask,
    MainAgentOutput,
    ReviewerIssue,
    ReviewerOutput,
    QualityReport,
    DirectDispatchOutput,
    StepWithParams,
    UnifiedOutput,
    # Parsers
    MainAgentParser,
    ReviewerParser,
    QualityReportParser,
    UnifiedParser,
    # Convenience Functions
    parse_main_agent_output,
    parse_reviewer_output,
    parse_quality_report,
    parse_unified_output,
)

__all__ = [
    # Orchestrator
    "WorkflowState",
    "FailureType",
    "WorkflowConfig",
    "WorkflowContext",
    "WorkflowOrchestrator",
    "SubAgentType",
    # Events
    "EventType",
    "Event",
    # Blackboard
    "Blackboard",
    "BlackboardArtifact",
    # Mailbox（主/子 Agent 定向消息与结构化回传）
    "TaskBrief",
    "SubagentResult",
    "MailboxMessage",
    "AGENT_MAIN",
    "MESSAGE_TYPE_TASK",
    "MESSAGE_TYPE_RESULT",
    "MESSAGE_TYPE_BATCH_TASK",
    "MESSAGE_TYPE_BATCH_RESULT",
    # Parallel Schemas
    "ParallelTaskGroup",
    "ParallelResultGroup",
    "ToolCall",
    "ToolCallResult",
    "ToolBatchRequest",
    "ToolBatchResult",
    # Constants
    "FAIL_STRATEGY_CONTINUE",
    "FAIL_STRATEGY_FAIL_FAST",
    "DEFAULT_MAX_CONCURRENCY",
    "DEFAULT_AGENT_TIMEOUT",
    "DEFAULT_TOOL_TIMEOUT",
    # Scheduler
    "ParallelScheduler",
    "SchedulerStatus",
    # Tool Scheduler
    "ToolScheduler",
    "DependencyGraph",
    "ToolExecutionBatch",
    # Agent Base (Enhanced)
    "AgentCapabilities",
    "EnhancedAgentState",
    "EnhancedAgentResult",
    "BaseEnhancedAgent",
    # Concrete Agents (Enhanced)
    "PlannerAgent",
    "CoderAgent",
    "TesterAgent",
    "PlannerCapabilities",
    "CoderCapabilities",
    "TesterCapabilities",
    # Base Agents (with Dynamic Prompt Loading)
    "AgentConfig",
    "AgentState",
    "BaseAgent",
    "AgentTeam",
    # New Subagents
    "ExplorerCapabilities",
    "ExplorerAgent",
    "ReviewerCapabilities",
    "ReviewerAgent",
    "BashCapabilities",
    "BashAgent",
    # General Purpose & Guide
    "GeneralPurposeCapabilities",
    "GeneralPurposeAgent",
    "MiniCoderGuideCapabilities",
    "MiniCoderGuideAgent",
    # Output Parsers
    "MainAgentOutputType",
    "ReviewerResultType",
    "UnifiedOutputType",
    "SubTask",
    "MainAgentOutput",
    "ReviewerIssue",
    "ReviewerOutput",
    "QualityReport",
    "DirectDispatchOutput",
    "StepWithParams",
    "UnifiedOutput",
    "MainAgentParser",
    "ReviewerParser",
    "QualityReportParser",
    "UnifiedParser",
    "parse_main_agent_output",
    "parse_reviewer_output",
    "parse_quality_report",
    "parse_unified_output",
]
