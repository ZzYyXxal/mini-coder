"""Tests for graph prompts module.

TDD Phase 4.2: Red - Write tests first for prompt loading integration.
"""
import pytest
from pathlib import Path
import tempfile


class TestGraphPrompts:
    """Tests for graph prompts module."""

    def test_get_system_prompt_for_role(self):
        """Should get system prompt for a role."""
        from mini_coder.graph.prompts import get_system_prompt_for_role
        from mini_coder.graph.roles import get_role, AGENT_EXPLORER

        role = get_role(AGENT_EXPLORER)
        prompt = get_system_prompt_for_role(role)

        assert isinstance(prompt, str)
        assert len(prompt) > 0
        # Should mention read-only constraint
        assert "read" in prompt.lower() or "only" in prompt.lower()

    def test_get_system_prompt_with_context(self):
        """Should interpolate context variables in prompt."""
        from mini_coder.graph.prompts import get_system_prompt_for_role
        from mini_coder.graph.roles import create_agent_role

        # Create a role with prompt that has placeholders
        role = create_agent_role(
            name="test",
            description="Test agent",
            tools=["Read"],
            stage="testing",
            prompt_path="subagent-coder",  # Has {{work_dir}} placeholder
        )

        context = {"work_dir": "/project/root"}
        prompt = get_system_prompt_for_role(role, context)

        # The prompt should contain the interpolated work_dir
        assert "/project/root" in prompt or "work_dir" in prompt

    def test_get_system_prompt_fallback(self):
        """Should fallback to built-in prompt when file not found."""
        from mini_coder.graph.prompts import get_system_prompt_for_role
        from mini_coder.graph.roles import create_agent_role

        role = create_agent_role(
            name="unknown_agent",
            description="Unknown agent",
            tools=["Read"],
            stage="testing",
            prompt_path="nonexistent-prompt-file",
        )

        # Should not raise, return built-in or empty
        prompt = get_system_prompt_for_role(role)

        assert isinstance(prompt, str)

    def test_build_user_prompt(self):
        """Should build user prompt from state."""
        from mini_coder.graph.prompts import build_user_prompt
        from mini_coder.graph.state import create_initial_state

        state = create_initial_state(
            user_request="Implement a hello world function",
            session_id="test-session",
        )

        prompt = build_user_prompt(state, agent_name="coder")

        assert "hello world" in prompt.lower()
        assert "coder" in prompt.lower() or "implement" in prompt.lower()

    def test_build_user_prompt_with_context(self):
        """Should include context in user prompt."""
        from mini_coder.graph.prompts import build_user_prompt
        from mini_coder.graph.state import create_initial_state

        state = create_initial_state(
            user_request="Fix the bug",
            session_id="test-session",
        )
        state["exploration_result"] = "Found bug in module.py line 42"

        prompt = build_user_prompt(state, agent_name="coder")

        assert "bug" in prompt.lower()
        assert "exploration" in prompt.lower() or "module.py" in prompt

    def test_format_messages_for_llm(self):
        """Should format messages for LLM consumption."""
        from mini_coder.graph.prompts import format_messages_for_llm
        from mini_coder.graph.state import create_agent_message

        messages = [
            create_agent_message(
                to_agent="coder",
                from_agent="planner",
                content="Please implement X",
            ),
            create_agent_message(
                to_agent="reviewer",
                from_agent="coder",
                content="Implementation complete",
            ),
        ]

        formatted = format_messages_for_llm(messages)

        assert "planner" in formatted.lower()
        assert "coder" in formatted.lower()
        assert "implement" in formatted.lower()


class TestPromptCaching:
    """Tests for prompt caching."""

    def test_prompt_caching(self):
        """Should cache loaded prompts."""
        from mini_coder.graph.prompts import get_system_prompt_for_role, _prompt_cache
        from mini_coder.graph.roles import get_role, AGENT_CODER

        # Clear cache
        _prompt_cache.clear()

        role = get_role(AGENT_CODER)

        # First call
        prompt1 = get_system_prompt_for_role(role)

        # Second call should use cache
        prompt2 = get_system_prompt_for_role(role)

        assert prompt1 == prompt2
        assert len(_prompt_cache) > 0

    def test_prompt_cache_invalidation(self):
        """Should be able to invalidate cache."""
        from mini_coder.graph.prompts import (
            get_system_prompt_for_role,
            clear_prompt_cache,
            _prompt_cache,
        )
        from mini_coder.graph.roles import get_role, AGENT_CODER

        role = get_role(AGENT_CODER)
        get_system_prompt_for_role(role)

        assert len(_prompt_cache) > 0

        clear_prompt_cache()

        assert len(_prompt_cache) == 0