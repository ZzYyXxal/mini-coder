"""AgentRole definitions for LangGraph workflow.

This module defines the AgentRole type and predefined roles for each
agent in the mini-coder system. Each role specifies:
- Tools available to the agent
- Model to use (haiku/sonnet)
- Stage it operates in
- Prompt path for dynamic loading

Phase 4.1 of LangGraph refactor.
"""

from typing import Dict, List, Optional, TypedDict, Set

from mini_coder.tools.filter import ToolFilter, CustomFilter


class AgentRole(TypedDict, total=False):
    """Definition of an agent role in the LangGraph workflow.

    Attributes:
        name: Unique identifier for the role (e.g., "explorer", "coder")
        description: Human-readable description of the role
        tools: List of tool names available to this agent
        stage: The workflow stage this agent operates in
        model: The LLM model to use ("haiku" for fast, "sonnet" for capable)
        temperature: Sampling temperature (default 0.7)
        max_iterations: Maximum iterations allowed (default 10)
        prompt_path: Path to the system prompt file (for PromptLoader)
    """
    name: str
    description: str
    tools: List[str]
    stage: str
    model: str
    temperature: float
    max_iterations: int
    prompt_path: str


# ==================== Default Values ====================

DEFAULT_MODEL = "sonnet"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_ITERATIONS = 10


# ==================== Role Creation ====================

def create_agent_role(
    name: str,
    description: str,
    tools: List[str],
    stage: str,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    prompt_path: Optional[str] = None,
) -> AgentRole:
    """Create an AgentRole with defaults.

    Args:
        name: Unique identifier for the role
        description: Human-readable description
        tools: List of available tool names
        stage: Workflow stage this agent operates in
        model: LLM model to use (default: sonnet)
        temperature: Sampling temperature (default: 0.7)
        max_iterations: Maximum iterations (default: 10)
        prompt_path: Path to system prompt file

    Returns:
        AgentRole instance
    """
    role: AgentRole = {
        "name": name,
        "description": description,
        "tools": tools,
        "stage": stage,
        "model": model,
        "temperature": temperature,
        "max_iterations": max_iterations,
    }

    if prompt_path is not None:
        role["prompt_path"] = prompt_path

    return role


# ==================== Tool Filter Integration ====================

def get_tool_filter_for_role(role: AgentRole) -> ToolFilter:
    """Get a ToolFilter instance for the given role.

    Uses CustomFilter in whitelist mode to allow only the tools
    specified in the role definition.

    Args:
        role: AgentRole to get filter for

    Returns:
        ToolFilter instance that allows only the tools specified in the role
    """
    tools_set: Set[str] = set(role["tools"])

    # Use CustomFilter in whitelist mode for precise control
    return CustomFilter(allowed=tools_set, mode="whitelist")


# ==================== Predefined Roles ====================

# Agent name constants (re-exported from state.py for convenience)
AGENT_EXPLORER = "explorer"
AGENT_PLANNER = "planner"
AGENT_CODER = "coder"
AGENT_REVIEWER = "reviewer"
AGENT_BASH = "bash"


# Stage constants
STAGE_EXPLORING = "exploring"
STAGE_PLANNING = "planning"
STAGE_CODING = "coding"
STAGE_REVIEWING = "reviewing"
STAGE_TESTING = "testing"


# Predefined role definitions
_ROLES: Dict[str, AgentRole] = {
    AGENT_EXPLORER: create_agent_role(
        name=AGENT_EXPLORER,
        description="Read-only codebase explorer - fast search and analysis",
        tools=["Read", "Glob", "Grep"],
        stage=STAGE_EXPLORING,
        model="haiku",  # Fast model for exploration
        prompt_path="subagent-explorer",
    ),

    AGENT_PLANNER: create_agent_role(
        name=AGENT_PLANNER,
        description="Requirements analyst and TDD planner",
        tools=["Read", "Glob", "Grep", "WebSearch", "WebFetch"],
        stage=STAGE_PLANNING,
        model="sonnet",  # Capable model for planning
        prompt_path="subagent-planner",
    ),

    AGENT_CODER: create_agent_role(
        name=AGENT_CODER,
        description="Code implementation specialist following TDD",
        tools=["Read", "Write", "Edit", "Glob", "Grep", "Execute"],
        stage=STAGE_CODING,
        model="sonnet",  # Capable model for coding
        prompt_path="subagent-coder",
    ),

    AGENT_REVIEWER: create_agent_role(
        name=AGENT_REVIEWER,
        description="Code quality and architecture reviewer",
        tools=["Read", "Glob", "Grep"],
        stage=STAGE_REVIEWING,
        model="sonnet",  # Capable model for review
        prompt_path="subagent-reviewer",
    ),

    AGENT_BASH: create_agent_role(
        name=AGENT_BASH,
        description="Terminal executor and test validator",
        tools=["Read", "Glob", "Execute"],
        stage=STAGE_TESTING,
        model="haiku",  # Fast model for tests
        max_iterations=5,  # Fewer iterations for bash
        prompt_path="subagent-bash",
    ),
}


def get_role(name: str) -> AgentRole:
    """Get a predefined role by name.

    Args:
        name: Role name (e.g., "explorer", "coder")

    Returns:
        AgentRole instance

    Raises:
        KeyError: If role not found
    """
    if name not in _ROLES:
        raise KeyError(f"Unknown role: {name}. Available: {list(_ROLES.keys())}")
    return _ROLES[name]


def get_all_roles() -> Dict[str, AgentRole]:
    """Get all predefined roles.

    Returns:
        Dictionary mapping role names to AgentRole instances
    """
    return _ROLES.copy()


# ==================== Validation ====================

def validate_role(role: AgentRole) -> None:
    """Validate an AgentRole has all required fields.

    Args:
        role: AgentRole to validate

    Raises:
        ValueError: If validation fails
    """
    if "name" not in role or not role["name"]:
        raise ValueError("AgentRole must have a non-empty 'name' field")

    if "tools" not in role or not role["tools"]:
        raise ValueError(f"AgentRole '{role['name']}' must have at least one tool")

    if "stage" not in role or not role["stage"]:
        raise ValueError(f"AgentRole '{role['name']}' must have a 'stage' field")

    if "model" not in role or not role["model"]:
        raise ValueError(f"AgentRole '{role['name']}' must have a 'model' field")


# ==================== Exports ====================

__all__ = [
    # Type
    "AgentRole",
    # Creation
    "create_agent_role",
    # Tool filter
    "get_tool_filter_for_role",
    # Predefined roles
    "AGENT_EXPLORER",
    "AGENT_PLANNER",
    "AGENT_CODER",
    "AGENT_REVIEWER",
    "AGENT_BASH",
    "get_role",
    "get_all_roles",
    # Validation
    "validate_role",
]