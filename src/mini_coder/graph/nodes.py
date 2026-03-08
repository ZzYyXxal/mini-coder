"""LangGraph node functions.

This module implements the individual node functions that form
the workflow graph. Each node is an async function that:
1. Receives the current state
2. Performs its specific task
3. Returns state updates

Node Types:
- router_node: Analyzes intent and routes to appropriate next node
- explorer_node: Read-only codebase exploration
- planner_node: Task planning and analysis
- coder_node: Code implementation
- reviewer_node: Code quality review
- bash_node: Test execution and command running
- complete_node: Finalize workflow
"""
import time
import uuid
from typing import Any, Dict

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from .state import (
    CodingAgentState,
    AgentMessage,
    AGENT_EXPLORER,
    AGENT_PLANNER,
    AGENT_CODER,
    AGENT_REVIEWER,
    AGENT_BASH,
    AGENT_MAIN,
    STAGE_ROUTING,
    STAGE_EXPLORING,
    STAGE_PLANNING,
    STAGE_CODING,
    STAGE_REVIEWING,
    STAGE_TESTING,
    STAGE_COMPLETED,
)


# ==================== Intent Analysis ====================

def _analyze_intent(user_request: str) -> str:
    """Analyze user request to determine intent.

    Args:
        user_request: The user's request

    Returns:
        Intent string: "explore", "plan", "code", or "simple"
    """
    request_lower = user_request.lower()

    # Exploration keywords
    explore_keywords = ["探索", "查找", "搜索", "找", "看看", "explore", "search", "find"]
    for kw in explore_keywords:
        if kw in request_lower:
            return "explore"

    # Planning keywords
    plan_keywords = ["规划", "设计", "计划", "plan", "design", "架构"]
    for kw in plan_keywords:
        if kw in request_lower:
            return "plan"

    # Simple task detection
    if len(user_request) < 50:
        return "simple"

    # Default to code implementation
    return "code"


# ==================== Node Functions ====================

async def router_node(state: CodingAgentState) -> Dict[str, Any]:
    """Router node - Analyzes intent and prepares for routing.

    This node analyzes the user's request to determine which agent
    should handle it next.

    Args:
        state: Current workflow state

    Returns:
        State updates with intent metadata
    """
    # Analyze intent from user request
    intent = _analyze_intent(state["user_request"])

    return {
        "current_stage": STAGE_ROUTING,
        "metadata": {"intent": intent},
    }


async def explorer_node(state: CodingAgentState) -> Dict[str, Any]:
    """Explorer node - Read-only codebase exploration.

    Uses read-only tools (Read, Glob, Grep) to explore the codebase
    and find relevant files and code.

    Args:
        state: Current workflow state

    Returns:
        State updates with exploration results
    """
    # Get read-only tools (placeholder for now)
    tools = _get_readonly_tools()

    # Create agent with Haiku model for speed
    agent = create_react_agent(
        model=_get_model("haiku"),
        tools=tools,
        state_modifier=_get_explorer_prompt(),
    )

    # Execute exploration
    result = await agent.ainvoke({
        "messages": state["messages"] + [
            HumanMessage(content=f"探索任务: {state['user_request']}")
        ]
    })

    # Extract result
    last_message = result["messages"][-1]
    content = last_message.content if hasattr(last_message, "content") else str(last_message)

    # Create agent message (preserved directed delivery)
    agent_message = AgentMessage(
        message_id=str(uuid.uuid4()),
        to_agent=AGENT_PLANNER,
        from_agent=AGENT_EXPLORER,
        content=content,
        created_at=time.time(),
    )

    return {
        "exploration_result": content,
        "agent_messages": [agent_message],
        "current_stage": STAGE_EXPLORING,
    }


async def planner_node(state: CodingAgentState) -> Dict[str, Any]:
    """Planner node - Task planning and analysis.

    Analyzes requirements and creates implementation plans.

    Args:
        state: Current workflow state

    Returns:
        State updates with implementation plan
    """
    # Placeholder implementation
    plan = f"Implementation plan for: {state['user_request']}"

    agent_message = AgentMessage(
        message_id=str(uuid.uuid4()),
        to_agent=AGENT_CODER,
        from_agent=AGENT_PLANNER,
        content=plan,
        created_at=time.time(),
    )

    return {
        "implementation_plan": plan,
        "agent_messages": [agent_message],
        "current_stage": STAGE_PLANNING,
    }


async def coder_node(state: CodingAgentState) -> Dict[str, Any]:
    """Coder node - Code implementation.

    Implements code based on the plan and requirements.

    Args:
        state: Current workflow state

    Returns:
        State updates with code changes
    """
    # Placeholder implementation
    code_changes = [
        {
            "file": "main.py",
            "content": "# Implementation placeholder",
            "action": "create",
        }
    ]

    agent_message = AgentMessage(
        message_id=str(uuid.uuid4()),
        to_agent=AGENT_REVIEWER,
        from_agent=AGENT_CODER,
        content="Code implementation complete",
        created_at=time.time(),
    )

    return {
        "code_changes": code_changes,
        "agent_messages": [agent_message],
        "current_stage": STAGE_CODING,
    }


async def reviewer_node(state: CodingAgentState) -> Dict[str, Any]:
    """Reviewer node - Code quality review.

    Reviews code for quality, architecture alignment, and best practices.

    Args:
        state: Current workflow state

    Returns:
        State updates with review result
    """
    # Placeholder implementation
    review_result = {
        "passed": True,
        "comments": [],
    }

    agent_message = AgentMessage(
        message_id=str(uuid.uuid4()),
        to_agent=AGENT_BASH,
        from_agent=AGENT_REVIEWER,
        content="Review passed",
        created_at=time.time(),
    )

    return {
        "review_result": review_result,
        "agent_messages": [agent_message],
        "current_stage": STAGE_REVIEWING,
    }


async def bash_node(state: CodingAgentState) -> Dict[str, Any]:
    """Bash node - Test execution and command running.

    Runs tests and quality checks.

    Args:
        state: Current workflow state

    Returns:
        State updates with test results
    """
    # Placeholder implementation
    test_result = {
        "all_passed": True,
        "tests_run": 0,
        "failures": [],
    }

    agent_message = AgentMessage(
        message_id=str(uuid.uuid4()),
        to_agent=AGENT_MAIN,
        from_agent=AGENT_BASH,
        content="All tests passed",
        created_at=time.time(),
    )

    return {
        "test_result": test_result,
        "agent_messages": [agent_message],
        "current_stage": STAGE_TESTING,
    }


async def complete_node(state: CodingAgentState) -> Dict[str, Any]:
    """Complete node - Finalize workflow.

    Marks the workflow as completed and prepares final summary.

    Args:
        state: Current workflow state

    Returns:
        State updates marking completion
    """
    return {
        "current_stage": STAGE_COMPLETED,
    }


# ==================== Helper Functions ====================

def _get_readonly_tools() -> list[Any]:
    """Get read-only tools for Explorer."""
    # Placeholder - will be replaced with actual tools
    return []


def _get_model(model_name: str) -> Any:
    """Get LLM model by name.

    Args:
        model_name: Model identifier (e.g., "haiku", "sonnet")

    Returns:
        LangChain ChatModel instance
    """
    # Placeholder - will be replaced with actual model
    # Using Any to avoid complex type issues with placeholder
    return None


def _get_explorer_prompt() -> str:
    """Get Explorer system prompt."""
    return """You are the Explorer Agent - a read-only codebase search specialist.

Constraints: Read-Only Mode
- You MUST NOT create, modify, or delete files
- You can only use read-only tools

Output:
Report findings: files/code locations discovered, key conclusions."""