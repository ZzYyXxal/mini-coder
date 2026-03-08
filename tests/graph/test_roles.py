"""Tests for AgentRole type and roles module.

TDD Phase 4.1: Red - Write tests first for AgentRole type.
"""
import pytest
from typing import Set


class TestAgentRole:
    """Tests for AgentRole TypedDict."""

    def test_agent_role_has_required_fields(self):
        """AgentRole should have all required fields."""
        from mini_coder.graph.roles import AgentRole

        role: AgentRole = {
            "name": "explorer",
            "description": "Read-only codebase explorer",
            "tools": ["Read", "Glob", "Grep"],
            "stage": "exploring",
            "model": "haiku",
        }

        assert role["name"] == "explorer"
        assert role["description"] == "Read-only codebase explorer"
        assert "Read" in role["tools"]
        assert role["stage"] == "exploring"
        assert role["model"] == "haiku"

    def test_agent_role_defaults(self):
        """AgentRole should have sensible defaults."""
        from mini_coder.graph.roles import AgentRole, create_agent_role

        role = create_agent_role(
            name="coder",
            description="Code implementation agent",
            tools=["Read", "Write", "Edit"],
            stage="coding",
        )

        # Default model should be sonnet
        assert role["model"] == "sonnet"
        # Default temperature
        assert role.get("temperature", 0.7) == 0.7
        # Default max_iterations
        assert role.get("max_iterations", 10) == 10

    def test_agent_role_tool_filter_compatibility(self):
        """AgentRole should be compatible with ToolFilter system."""
        from mini_coder.graph.roles import AgentRole, get_tool_filter_for_role

        role: AgentRole = {
            "name": "explorer",
            "description": "Read-only",
            "tools": ["Read", "Glob", "Grep"],
            "stage": "exploring",
            "model": "haiku",
        }

        filter_instance = get_tool_filter_for_role(role)
        assert filter_instance is not None
        assert filter_instance.is_allowed("Read")
        assert not filter_instance.is_allowed("Write")

    def test_agent_role_prompt_path(self):
        """AgentRole should have prompt path for PromptLoader."""
        from mini_coder.graph.roles import AgentRole, create_agent_role

        role = create_agent_role(
            name="explorer",
            description="Read-only",
            tools=["Read", "Glob", "Grep"],
            stage="exploring",
            prompt_path="subagent-explorer",
        )

        assert role.get("prompt_path") == "subagent-explorer"


class TestPredefinedRoles:
    """Tests for predefined agent roles."""

    def test_get_explorer_role(self):
        """Should get predefined Explorer role."""
        from mini_coder.graph.roles import get_role, AGENT_EXPLORER

        role = get_role(AGENT_EXPLORER)

        assert role["name"] == "explorer"
        assert "Read" in role["tools"]
        assert "Write" not in role["tools"]
        assert role["stage"] == "exploring"
        assert role["model"] == "haiku"  # Fast model for exploration

    def test_get_planner_role(self):
        """Should get predefined Planner role."""
        from mini_coder.graph.roles import get_role, AGENT_PLANNER

        role = get_role(AGENT_PLANNER)

        assert role["name"] == "planner"
        assert "Read" in role["tools"]
        assert "Glob" in role["tools"]
        assert "WebSearch" in role["tools"]  # Planner can search web
        assert role["stage"] == "planning"

    def test_get_coder_role(self):
        """Should get predefined Coder role."""
        from mini_coder.graph.roles import get_role, AGENT_CODER

        role = get_role(AGENT_CODER)

        assert role["name"] == "coder"
        assert "Read" in role["tools"]
        assert "Write" in role["tools"]
        assert "Edit" in role["tools"]
        assert "Execute" in role["tools"]
        assert role["stage"] == "coding"

    def test_get_reviewer_role(self):
        """Should get predefined Reviewer role."""
        from mini_coder.graph.roles import get_role, AGENT_REVIEWER

        role = get_role(AGENT_REVIEWER)

        assert role["name"] == "reviewer"
        assert "Read" in role["tools"]
        assert "Write" not in role["tools"]  # Read-only
        assert role["stage"] == "reviewing"

    def test_get_bash_role(self):
        """Should get predefined Bash role."""
        from mini_coder.graph.roles import get_role, AGENT_BASH

        role = get_role(AGENT_BASH)

        assert role["name"] == "bash"
        assert "Read" in role["tools"]
        assert "Execute" in role["tools"]  # Can run commands
        assert role["stage"] == "testing"

    def test_get_all_roles(self):
        """Should get all predefined roles."""
        from mini_coder.graph.roles import get_all_roles

        roles = get_all_roles()

        assert "explorer" in roles
        assert "planner" in roles
        assert "coder" in roles
        assert "reviewer" in roles
        assert "bash" in roles

        # All roles should have required fields
        for name, role in roles.items():
            assert "name" in role
            assert "tools" in role
            assert "stage" in role
            assert "model" in role


class TestRoleValidation:
    """Tests for role validation."""

    def test_validate_role_valid(self):
        """Should pass validation for valid role."""
        from mini_coder.graph.roles import AgentRole, validate_role

        role: AgentRole = {
            "name": "test",
            "description": "Test agent",
            "tools": ["Read"],
            "stage": "testing",
            "model": "haiku",
        }

        # Should not raise
        validate_role(role)

    def test_validate_role_missing_name(self):
        """Should fail validation when name is missing."""
        from mini_coder.graph.roles import AgentRole, validate_role

        role = {
            "description": "Test agent",
            "tools": ["Read"],
            "stage": "testing",
            "model": "haiku",
        }

        with pytest.raises(ValueError, match="name"):
            validate_role(role)  # type: ignore

    def test_validate_role_empty_tools(self):
        """Should fail validation when tools is empty."""
        from mini_coder.graph.roles import AgentRole, validate_role

        role: AgentRole = {
            "name": "test",
            "description": "Test agent",
            "tools": [],
            "stage": "testing",
            "model": "haiku",
        }

        with pytest.raises(ValueError, match="tool"):
            validate_role(role)