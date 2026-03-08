"""LangGraph state definitions for mini-coder.

This module defines the state types used in the LangGraph workflow,
replacing the previous Blackboard and Mailbox system.

Key design decisions:
1. AgentMessage preserved for directed messaging (to_agent/from_agent)
2. CodingAgentState is the main state type for the workflow
3. Stage and agent constants defined here for consistency
"""

from typing import TypedDict, List, Dict, Any, Optional, Annotated
from langgraph.graph import add_messages


# ==================== Agent Type Constants ====================

AGENT_MAIN = "main"
AGENT_EXPLORER = "explorer"
AGENT_PLANNER = "planner"
AGENT_CODER = "coder"
AGENT_REVIEWER = "reviewer"
AGENT_BASH = "bash"

# ==================== Stage Constants ====================

STAGE_PENDING = "pending"
STAGE_ROUTING = "routing"
STAGE_EXPLORING = "exploring"
STAGE_PLANNING = "planning"
STAGE_CODING = "coding"
STAGE_REVIEWING = "reviewing"
STAGE_TESTING = "testing"
STAGE_COMPLETED = "completed"


# ==================== Agent Message (Preserved from Mailbox) ====================

class AgentMessage(TypedDict):
    """Simplified agent-to-agent message with directed delivery.

    This type is preserved from the original Mailbox system because
    LangGraph State is globally shared and lacks the concept of
    "who sent this to whom". This is useful for:

    1. Debugging - quickly identify which agent produced what
    2. Auditing - trace message origins
    3. Isolation - agents can see directed messages

    Attributes:
        message_id: Unique identifier for this message
        to_agent: Target agent (e.g., "coder", "reviewer")
        from_agent: Source agent (e.g., "planner", "explorer")
        content: Message content
        created_at: Unix timestamp
    """
    message_id: str
    to_agent: str
    from_agent: str
    content: str
    created_at: float


# ==================== Main Workflow State ====================

class CodingAgentState(TypedDict):
    """Main state type for the coding agent workflow.

    This state is passed between all nodes in the LangGraph workflow.
    It replaces the previous Blackboard + Mailbox combination.

    Key fields:
        messages: Conversation history (auto-merged by add_messages)
        user_request: The original user request
        current_stage: Current workflow stage (see STAGE_* constants)
        session_id: Unique session identifier
        agent_messages: List of directed agent messages (preserved)

        exploration_result: Output from Explorer agent
        implementation_plan: Output from Planner agent
        code_changes: List of code changes made by Coder
        review_result: Review result from Reviewer
        test_result: Test result from Bash

        tool_results: Tool call results (supports DAG scheduling)
        errors: List of errors encountered
        retry_count: Current retry count
        max_retries: Maximum allowed retries

        project_path: Path to the project being worked on
        metadata: Additional metadata
    """
    # Message history (auto-merged with add_messages reducer)
    messages: Annotated[List[Any], add_messages]

    # Core fields
    user_request: str
    current_stage: str
    session_id: str

    # Agent messages (preserved for directed delivery)
    agent_messages: List[AgentMessage]

    # Stage results
    exploration_result: Optional[str]
    implementation_plan: Optional[str]
    code_changes: List[Dict[str, str]]
    review_result: Optional[Dict[str, Any]]
    test_result: Optional[Dict[str, Any]]

    # Tool results (supports DAG scheduling via ToolScheduler)
    tool_results: List[Dict[str, Any]]

    # Error handling
    errors: List[str]
    retry_count: int
    max_retries: int

    # Metadata
    project_path: str
    metadata: Dict[str, Any]


# ==================== Helper Functions ====================

def create_initial_state(
    user_request: str,
    session_id: str,
    project_path: str = "",
    max_retries: int = 3,
) -> CodingAgentState:
    """Create an initial state for a new workflow.

    Args:
        user_request: The user's request
        session_id: Unique session identifier
        project_path: Path to the project (optional)
        max_retries: Maximum retry attempts (default 3)

    Returns:
        Initial CodingAgentState
    """
    import time
    import uuid

    return CodingAgentState(
        messages=[],
        user_request=user_request,
        current_stage=STAGE_PENDING,
        session_id=session_id,
        agent_messages=[],
        exploration_result=None,
        implementation_plan=None,
        code_changes=[],
        review_result=None,
        test_result=None,
        tool_results=[],
        errors=[],
        retry_count=0,
        max_retries=max_retries,
        project_path=project_path,
        metadata={},
    )


def create_agent_message(
    to_agent: str,
    from_agent: str,
    content: str,
    message_id: Optional[str] = None,
) -> AgentMessage:
    """Create a new agent message.

    Args:
        to_agent: Target agent
        from_agent: Source agent
        content: Message content
        message_id: Optional message ID (auto-generated if not provided)

    Returns:
        AgentMessage instance
    """
    import time
    import uuid

    return AgentMessage(
        message_id=message_id or str(uuid.uuid4()),
        to_agent=to_agent,
        from_agent=from_agent,
        content=content,
        created_at=time.time(),
    )