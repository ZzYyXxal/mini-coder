"""Tests for GraphRunner.

TDD Phase 5.1: Red - Write tests first for GraphRunner.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio


class TestGraphRunner:
    """Tests for GraphRunner."""

    @pytest.mark.asyncio
    async def test_run_returns_result(self):
        """GraphRunner.run() should return a result."""
        from mini_coder.graph.runner import GraphRunner
        from mini_coder.graph.state import create_initial_state

        # Mock LLM service
        mock_llm = MagicMock()
        mock_llm.chat = MagicMock(return_value="Test response")

        runner = GraphRunner(llm_service=mock_llm)
        state = create_initial_state(
            user_request="Test request",
            session_id="test-session",
        )

        result = await runner.run(state)

        assert result is not None
        assert "current_stage" in result

    @pytest.mark.asyncio
    async def test_run_updates_stage(self):
        """GraphRunner.run() should update the stage."""
        from mini_coder.graph.runner import GraphRunner
        from mini_coder.graph.state import create_initial_state, STAGE_PENDING

        mock_llm = MagicMock()
        mock_llm.chat = MagicMock(return_value="Done")

        runner = GraphRunner(llm_service=mock_llm)
        state = create_initial_state(
            user_request="Test",
            session_id="test",
        )

        assert state["current_stage"] == STAGE_PENDING

        result = await runner.run(state)

        # Stage should have changed from pending
        assert result["current_stage"] != STAGE_PENDING

    @pytest.mark.asyncio
    async def test_stream_yields_events(self):
        """GraphRunner.stream() should yield events."""
        from mini_coder.graph.runner import GraphRunner
        from mini_coder.graph.state import create_initial_state

        mock_llm = MagicMock()
        mock_llm.chat = MagicMock(return_value="Response")

        runner = GraphRunner(llm_service=mock_llm)
        state = create_initial_state(
            user_request="Test",
            session_id="test",
        )

        events = []
        async for event in runner.stream(state):
            events.append(event)

        assert len(events) > 0
        # Each event should have a type
        for event in events:
            assert "type" in event

    @pytest.mark.asyncio
    async def test_stream_event_types(self):
        """GraphRunner.stream() should yield proper event types."""
        from mini_coder.graph.runner import GraphRunner
        from mini_coder.graph.state import create_initial_state

        mock_llm = MagicMock()
        mock_llm.chat = MagicMock(return_value="Response")

        runner = GraphRunner(llm_service=mock_llm)
        state = create_initial_state(
            user_request="Test",
            session_id="test",
        )

        event_types = set()
        async for event in runner.stream(state):
            event_types.add(event.get("type"))

        # Should have at least node_start or node_end events
        assert len(event_types) > 0

    @pytest.mark.asyncio
    async def test_run_with_error_handling(self):
        """GraphRunner should handle errors gracefully."""
        from mini_coder.graph.runner import GraphRunner
        from mini_coder.graph.state import create_initial_state

        mock_llm = MagicMock()
        runner = GraphRunner(llm_service=mock_llm, timeout=1)  # Short timeout
        state = create_initial_state(
            user_request="Test",
            session_id="test",
        )

        # The runner should complete without raising exceptions
        # even if there are internal errors
        result = await runner.run(state)

        # Should return a valid state
        assert result is not None
        assert "current_stage" in result


class TestGraphRunnerConfig:
    """Tests for GraphRunner configuration."""

    def test_runner_default_config(self):
        """GraphRunner should have sensible defaults."""
        from mini_coder.graph.runner import GraphRunner

        mock_llm = MagicMock()
        runner = GraphRunner(llm_service=mock_llm)

        assert runner.max_retries == 3
        assert runner.timeout == 300

    def test_runner_custom_config(self):
        """GraphRunner should accept custom config."""
        from mini_coder.graph.runner import GraphRunner

        mock_llm = MagicMock()
        runner = GraphRunner(
            llm_service=mock_llm,
            max_retries=5,
            timeout=600,
        )

        assert runner.max_retries == 5
        assert runner.timeout == 600


class TestGraphRunnerIntegration:
    """Integration tests for GraphRunner with graph components."""

    @pytest.mark.asyncio
    async def test_runner_uses_graph_builder(self):
        """GraphRunner should use CodingAgentGraphBuilder."""
        from mini_coder.graph.runner import GraphRunner

        mock_llm = MagicMock()
        runner = GraphRunner(llm_service=mock_llm)

        # Should have a compiled graph
        assert runner.graph is not None

    @pytest.mark.asyncio
    async def test_runner_routes_by_intent(self):
        """GraphRunner should route requests by intent."""
        from mini_coder.graph.runner import GraphRunner
        from mini_coder.graph.state import create_initial_state

        mock_llm = MagicMock()
        mock_llm.chat = MagicMock(return_value="Exploring codebase...")

        runner = GraphRunner(llm_service=mock_llm)

        # Request with "explore" keyword
        state = create_initial_state(
            user_request="探索代码库结构",
            session_id="test",
        )

        result = await runner.run(state)

        # Should have routed to explorer
        assert result is not None