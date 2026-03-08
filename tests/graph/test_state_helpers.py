"""Tests for state helper functions.

Additional tests for create_initial_state and create_agent_message.
"""
import pytest
import time


class TestCreateInitialState:
    """Tests for create_initial_state helper."""

    def test_creates_valid_state(self):
        """Should create a valid CodingAgentState."""
        from mini_coder.graph.state import create_initial_state, STAGE_PENDING

        state = create_initial_state(
            user_request="实现登录功能",
            session_id="session-001",
        )

        assert state["user_request"] == "实现登录功能"
        assert state["session_id"] == "session-001"
        assert state["current_stage"] == STAGE_PENDING
        assert state["messages"] == []
        assert state["agent_messages"] == []
        assert state["retry_count"] == 0
        assert state["max_retries"] == 3

    def test_custom_max_retries(self):
        """Should accept custom max_retries."""
        from mini_coder.graph.state import create_initial_state

        state = create_initial_state(
            user_request="test",
            session_id="session-002",
            max_retries=5,
        )

        assert state["max_retries"] == 5

    def test_all_optional_fields_are_none_or_empty(self):
        """All stage result fields should be None or empty."""
        from mini_coder.graph.state import create_initial_state

        state = create_initial_state(
            user_request="test",
            session_id="session-003",
        )

        assert state["exploration_result"] is None
        assert state["implementation_plan"] is None
        assert state["code_changes"] == []
        assert state["review_result"] is None
        assert state["test_result"] is None
        assert state["tool_results"] == []
        assert state["errors"] == []


class TestCreateAgentMessage:
    """Tests for create_agent_message helper."""

    def test_creates_valid_message(self):
        """Should create a valid AgentMessage."""
        from mini_coder.graph.state import create_agent_message

        msg = create_agent_message(
            to_agent="coder",
            from_agent="planner",
            content="Please implement login",
        )

        assert msg["to_agent"] == "coder"
        assert msg["from_agent"] == "planner"
        assert msg["content"] == "Please implement login"
        assert "message_id" in msg
        assert "created_at" in msg

    def test_auto_generates_message_id(self):
        """Should auto-generate message_id if not provided."""
        from mini_coder.graph.state import create_agent_message

        msg = create_agent_message(
            to_agent="reviewer",
            from_agent="coder",
            content="Code ready",
        )

        assert msg["message_id"] != ""
        assert len(msg["message_id"]) > 10  # UUID format

    def test_accepts_custom_message_id(self):
        """Should accept custom message_id."""
        from mini_coder.graph.state import create_agent_message

        msg = create_agent_message(
            to_agent="bash",
            from_agent="reviewer",
            content="Run tests",
            message_id="custom-msg-001",
        )

        assert msg["message_id"] == "custom-msg-001"

    def test_created_at_is_recent(self):
        """created_at should be a recent timestamp."""
        from mini_coder.graph.state import create_agent_message

        before = time.time()
        msg = create_agent_message(
            to_agent="main",
            from_agent="explorer",
            content="Found files",
        )
        after = time.time()

        assert before <= msg["created_at"] <= after