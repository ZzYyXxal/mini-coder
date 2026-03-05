"""Agents Package - 多 Agent 系统

提供自动化的 需求→代码→测试→(重分析) 循环能力。

核心组件:
- Orchestrator: 工作流协调器
- Enhanced Agents: 增强的 Agent 类 (Planner, Coder, Tester)
- Blackboard: 共享上下文管理
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
]
