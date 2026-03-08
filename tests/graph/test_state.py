"""Tests for LangGraph state definitions.

TDD Phase 1: Red - Write tests first, they should fail.
"""
import pytest
from typing import get_type_hints


class TestAgentMessage:
    """Tests for AgentMessage type."""

    def test_agent_message_has_required_fields(self):
        """AgentMessage should have all required fields."""
        from mini_coder.graph.state import AgentMessage

        # Should be able to create with all fields
        msg = AgentMessage(
            message_id="msg-001",
            to_agent="coder",
            from_agent="planner",
            content="Please implement login",
            created_at=1234567890.0,
        )

        assert msg["message_id"] == "msg-001"
        assert msg["to_agent"] == "coder"
        assert msg["from_agent"] == "planner"
        assert msg["content"] == "Please implement login"
        assert msg["created_at"] == 1234567890.0

    def test_agent_message_is_typed_dict(self):
        """AgentMessage should be a TypedDict."""
        from mini_coder.graph.state import AgentMessage

        # TypedDict instances are dicts
        msg = AgentMessage(
            message_id="msg-002",
            to_agent="reviewer",
            from_agent="coder",
            content="Code ready for review",
            created_at=1234567891.0,
        )
        assert isinstance(msg, dict)


class TestCodingAgentState:
    """Tests for CodingAgentState type."""

    def test_state_has_user_request(self):
        """State should have user_request field."""
        from mini_coder.graph.state import CodingAgentState

        state: CodingAgentState = {
            "messages": [],
            "user_request": "实现登录功能",
            "current_stage": "pending",
            "session_id": "session-001",
            "agent_messages": [],
            "exploration_result": None,
            "implementation_plan": None,
            "code_changes": [],
            "review_result": None,
            "test_result": None,
            "tool_results": [],
            "errors": [],
            "retry_count": 0,
            "max_retries": 3,
            "project_path": "/tmp/project",
            "metadata": {},
        }

        assert state["user_request"] == "实现登录功能"

    def test_state_has_stage_result_fields(self):
        """State should have result fields for each stage."""
        from mini_coder.graph.state import CodingAgentState

        state: CodingAgentState = {
            "messages": [],
            "user_request": "test",
            "current_stage": "coding",
            "session_id": "session-001",
            "agent_messages": [],
            "exploration_result": "Found 3 relevant files",
            "implementation_plan": "1. Create login.py\n2. Add tests",
            "code_changes": [{"file": "login.py", "content": "def login(): pass", "action": "create"}],
            "review_result": {"passed": True, "comments": []},
            "test_result": None,
            "tool_results": [],
            "errors": [],
            "retry_count": 0,
            "max_retries": 3,
            "project_path": "/tmp/project",
            "metadata": {},
        }

        assert state["exploration_result"] == "Found 3 relevant files"
        assert state["implementation_plan"] == "1. Create login.py\n2. Add tests"
        assert len(state["code_changes"]) == 1
        assert state["review_result"]["passed"] is True

    def test_state_has_retry_fields(self):
        """State should have retry tracking fields."""
        from mini_coder.graph.state import CodingAgentState

        state: CodingAgentState = {
            "messages": [],
            "user_request": "test",
            "current_stage": "pending",
            "session_id": "session-001",
            "agent_messages": [],
            "exploration_result": None,
            "implementation_plan": None,
            "code_changes": [],
            "review_result": None,
            "test_result": None,
            "tool_results": [],
            "errors": ["Previous error"],
            "retry_count": 1,
            "max_retries": 3,
            "project_path": "/tmp/project",
            "metadata": {},
        }

        assert state["retry_count"] == 1
        assert state["max_retries"] == 3
        assert "Previous error" in state["errors"]


class TestStateAnnotatedFields:
    """Tests for annotated fields in state."""

    def test_messages_is_annotated_list(self):
        """messages field should use add_messages reducer."""
        from mini_coder.graph.state import CodingAgentState
        from typing import get_type_hints, get_origin, Annotated

        hints = get_type_hints(CodingAgentState, include_extras=True)

        # messages should be annotated with add_messages
        assert "messages" in hints


class TestAgentConstants:
    """Tests for agent type constants."""

    def test_agent_constants_exist(self):
        """Should have constants for agent types."""
        from mini_coder.graph.state import (
            AGENT_MAIN,
            AGENT_EXPLORER,
            AGENT_PLANNER,
            AGENT_CODER,
            AGENT_REVIEWER,
            AGENT_BASH,
        )

        assert AGENT_MAIN == "main"
        assert AGENT_EXPLORER == "explorer"
        assert AGENT_PLANNER == "planner"
        assert AGENT_CODER == "coder"
        assert AGENT_REVIEWER == "reviewer"
        assert AGENT_BASH == "bash"


class TestStageConstants:
    """Tests for stage constants."""

    def test_stage_constants_exist(self):
        """Should have constants for workflow stages."""
        from mini_coder.graph.state import (
            STAGE_PENDING,
            STAGE_ROUTING,
            STAGE_EXPLORING,
            STAGE_PLANNING,
            STAGE_CODING,
            STAGE_REVIEWING,
            STAGE_TESTING,
            STAGE_COMPLETED,
        )

        assert STAGE_PENDING == "pending"
        assert STAGE_ROUTING == "routing"
        assert STAGE_EXPLORING == "exploring"
        assert STAGE_PLANNING == "planning"
        assert STAGE_CODING == "coding"
        assert STAGE_REVIEWING == "reviewing"
        assert STAGE_TESTING == "testing"
        assert STAGE_COMPLETED == "completed"