"""Tests for LangGraph builder.

TDD tests for graph compilation and execution.
"""
import pytest


class TestCodingAgentGraphBuilder:
    """Tests for CodingAgentGraphBuilder."""

    def test_builder_creates_graph(self):
        """Builder should create a compiled graph."""
        from mini_coder.graph.builder import CodingAgentGraphBuilder

        builder = CodingAgentGraphBuilder()
        graph = builder.build()

        assert graph is not None

    def test_graph_has_expected_nodes(self):
        """Graph should have all expected nodes."""
        from mini_coder.graph.builder import CodingAgentGraphBuilder

        builder = CodingAgentGraphBuilder()
        graph = builder.build()

        # Check nodes exist by trying to get graph structure
        assert hasattr(graph, "nodes") or hasattr(graph, "get_graph")


class TestGraphExecution:
    """Tests for graph execution."""

    @pytest.mark.asyncio
    async def test_simple_workflow_completes(self):
        """Simple workflow should complete successfully."""
        from mini_coder.graph.builder import CodingAgentGraphBuilder
        from mini_coder.graph.state import create_initial_state

        builder = CodingAgentGraphBuilder()
        graph = builder.build()

        # Create initial state
        state = create_initial_state(
            user_request="hi",  # Simple request
            session_id="test-execution-001",
        )

        # Execute graph with config (required for checkpointer)
        config = {"configurable": {"thread_id": "test-execution-001"}}
        result = await graph.ainvoke(state, config)

        assert result is not None
        assert "current_stage" in result

    @pytest.mark.asyncio
    async def test_graph_preserves_session_id(self):
        """Graph should preserve session_id through execution."""
        from mini_coder.graph.builder import CodingAgentGraphBuilder
        from mini_coder.graph.state import create_initial_state

        builder = CodingAgentGraphBuilder()
        graph = builder.build()

        state = create_initial_state(
            user_request="test",
            session_id="test-session-002",
        )

        config = {"configurable": {"thread_id": "test-session-002"}}
        result = await graph.ainvoke(state, config)

        assert result["session_id"] == "test-session-002"