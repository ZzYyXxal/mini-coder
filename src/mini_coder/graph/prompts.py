"""Prompt management for LangGraph workflow.

This module provides prompt loading and formatting for agents
in the LangGraph workflow. It integrates with the existing
PromptLoader and adds workflow-specific functionality.

Phase 4.2 of LangGraph refactor.
"""

import logging
from typing import Any, Dict, List, Optional

from mini_coder.graph.roles import AgentRole
from mini_coder.graph.state import AgentMessage, CodingAgentState

logger = logging.getLogger(__name__)


# ==================== Prompt Cache ====================

_prompt_cache: Dict[str, str] = {}


def clear_prompt_cache() -> None:
    """Clear the prompt cache."""
    _prompt_cache.clear()


# ==================== Prompt Loading ====================

def get_system_prompt_for_role(
    role: AgentRole,
    context: Optional[Dict[str, Any]] = None,
    use_cache: bool = True,
) -> str:
    """Get the system prompt for an agent role.

    Args:
        role: AgentRole to get prompt for
        context: Optional context for placeholder interpolation
        use_cache: Whether to use cached prompts (default: True)

    Returns:
        System prompt string
    """
    from mini_coder.agents.prompt_loader import PromptLoader

    # Check cache first
    cache_key = role["name"]
    if use_cache and cache_key in _prompt_cache and not context:
        return _prompt_cache[cache_key]

    # Get prompt path from role
    prompt_path = role.get("prompt_path")

    # Initialize prompt loader
    loader = PromptLoader()

    try:
        if prompt_path:
            # Load from file
            prompt = loader.load(prompt_path, context=context, use_cache=use_cache)
        else:
            # Try loading by agent name
            prompt = loader.load(role["name"], context=context, use_cache=use_cache)
    except Exception as e:
        logger.warning(f"Failed to load prompt for role {role['name']}: {e}")
        # Return built-in fallback prompt
        prompt = _get_builtin_prompt(role["name"])

    # Cache if no context (context-dependent prompts shouldn't be cached)
    if use_cache and not context:
        _prompt_cache[cache_key] = prompt

    return prompt


def _get_builtin_prompt(role_name: str) -> str:
    """Get built-in fallback prompt for a role.

    Args:
        role_name: Name of the role

    Returns:
        Built-in prompt string
    """
    # Import built-in prompts from prompt_loader
    from mini_coder.agents.prompt_loader import _BUILTIN_PROMPTS

    if role_name in _BUILTIN_PROMPTS:
        return _BUILTIN_PROMPTS[role_name]

    # Generic fallback
    return f"You are the {role_name} agent. Complete the task to the best of your ability."


# ==================== User Prompt Building ====================

def build_user_prompt(
    state: CodingAgentState,
    agent_name: str,
    additional_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Build a user prompt for an agent from the workflow state.

    Args:
        state: Current workflow state
        agent_name: Name of the agent receiving the prompt
        additional_context: Optional additional context

    Returns:
        User prompt string
    """
    parts: List[str] = []

    # Add user request
    user_request = state.get("user_request", "")
    if user_request:
        parts.append(f"## User Request\n\n{user_request}")

    # Add relevant context based on agent
    context = _get_relevant_context(state, agent_name)
    if context:
        parts.append(f"## Context\n\n{context}")

    # Add stage-specific information
    stage_info = _get_stage_info(state, agent_name)
    if stage_info:
        parts.append(f"## Current Stage\n\n{stage_info}")

    # Add any additional context
    if additional_context:
        extra = "\n".join(f"- {k}: {v}" for k, v in additional_context.items())
        parts.append(f"## Additional Information\n\n{extra}")

    # Add instructions for the agent
    instructions = _get_agent_instructions(agent_name)
    if instructions:
        parts.append(f"## Instructions\n\n{instructions}")

    return "\n\n".join(parts)


def _get_relevant_context(state: CodingAgentState, agent_name: str) -> str:
    """Get context relevant to a specific agent.

    Args:
        state: Current workflow state
        agent_name: Name of the agent

    Returns:
        Context string
    """
    context_parts: List[str] = []

    # Explorer provides context for other agents
    if agent_name in ("planner", "coder", "reviewer"):
        exploration = state.get("exploration_result")
        if exploration:
            context_parts.append(f"### Exploration Results\n{exploration}")

    # Planner provides context for coder and reviewer
    if agent_name in ("coder", "reviewer"):
        plan = state.get("implementation_plan")
        if plan:
            context_parts.append(f"### Implementation Plan\n{plan}")

    # Coder provides context for reviewer
    if agent_name == "reviewer":
        code_changes = state.get("code_changes", [])
        if code_changes:
            changes_str = "\n".join(
                f"- {c.get('file', 'unknown')}: {c.get('description', '')}"
                for c in code_changes
            )
            context_parts.append(f"### Code Changes\n{changes_str}")

    return "\n\n".join(context_parts)


def _get_stage_info(state: CodingAgentState, agent_name: str) -> str:
    """Get information about the current stage.

    Args:
        state: Current workflow state
        agent_name: Name of the agent

    Returns:
        Stage information string
    """
    stage = state.get("current_stage", "unknown")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)

    info = f"You are in the **{stage}** stage."

    if retry_count > 0:
        info += f"\n\nThis is attempt {retry_count + 1} of {max_retries + 1}."

    return info


def _get_agent_instructions(agent_name: str) -> str:
    """Get specific instructions for an agent.

    Args:
        agent_name: Name of the agent

    Returns:
        Instructions string
    """
    instructions: Dict[str, str] = {
        "explorer": "Explore the codebase to find relevant files and understand the structure. Report your findings clearly.",
        "planner": "Analyze the requirements and create a TDD-compliant implementation plan. Break down into atomic steps.",
        "coder": "Implement the code following the plan. Write tests first (TDD), then implement. Prefer editing over creating new files.",
        "reviewer": "Review the code for quality and architecture alignment. Output [Pass] or [Reject] with specific feedback.",
        "bash": "Execute tests and quality checks. Generate a quality report with test results, type check, and coverage.",
    }

    return instructions.get(agent_name, "Complete your task to the best of your ability.")


# ==================== Message Formatting ====================

def format_messages_for_llm(messages: List[AgentMessage]) -> str:
    """Format agent messages for LLM consumption.

    Args:
        messages: List of agent messages

    Returns:
        Formatted string
    """
    if not messages:
        return ""

    parts: List[str] = []

    for msg in messages:
        from_agent = msg.get("from_agent", "unknown")
        to_agent = msg.get("to_agent", "unknown")
        content = msg.get("content", "")

        parts.append(f"[{from_agent} -> {to_agent}]\n{content}")

    return "\n\n".join(parts)


# ==================== Exports ====================

__all__ = [
    # Cache
    "_prompt_cache",
    "clear_prompt_cache",
    # Prompt loading
    "get_system_prompt_for_role",
    # User prompt building
    "build_user_prompt",
    # Message formatting
    "format_messages_for_llm",
]