"""Tests for LangGraph node functions.

TDD Phase 2: Red - Write tests first, they should fail.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestRouterNode:
    """Tests for router_node."""

    @pytest.mark.asyncio
    async def test_router_returns_intent_metadata(self):
        """Router should analyze intent and return metadata."""
        from mini_coder.graph.nodes import router_node
        from mini_coder.graph.state import CodingAgentState

        state = CodingAgentState(
            messages=[],
            user_request="探索代码库结构",
            current_stage="pending",
            session_id="test-001",
            agent_messages=[],
            exploration_result=None,
            implementation_plan=None,
            code_changes=[],
            review_result=None,
            test_result=None,
            tool_results=[],
            errors=[],
            retry_count=0,
            max_retries=3,
            project_path="/tmp",
            metadata={},
        )

        result = await router_node(state)

        assert "metadata" in result
        assert "intent" in result["metadata"]

    @pytest.mark.asyncio
    async def test_router_sets_routing_stage(self):
        """Router should set current_stage to 'routing'."""
        from mini_coder.graph.nodes import router_node
        from mini_coder.graph.state import CodingAgentState, STAGE_ROUTING

        state = CodingAgentState(
            messages=[],
            user_request="实现登录功能",
            current_stage="pending",
            session_id="test-002",
            agent_messages=[],
            exploration_result=None,
            implementation_plan=None,
            code_changes=[],
            review_result=None,
            test_result=None,
            tool_results=[],
            errors=[],
            retry_count=0,
            max_retries=3,
            project_path="/tmp",
            metadata={},
        )

        result = await router_node(state)

        assert result["current_stage"] == STAGE_ROUTING


class TestExplorerNode:
    """Tests for explorer_node."""

    @pytest.mark.asyncio
    async def test_explorer_returns_exploration_result(self):
        """Explorer should return exploration_result."""
        from mini_coder.graph.nodes import explorer_node
        from mini_coder.graph.state import CodingAgentState, STAGE_EXPLORING

        state = CodingAgentState(
            messages=[],
            user_request="查找登录相关代码",
            current_stage="routing",
            session_id="test-003",
            agent_messages=[],
            exploration_result=None,
            implementation_plan=None,
            code_changes=[],
            review_result=None,
            test_result=None,
            tool_results=[],
            errors=[],
            retry_count=0,
            max_retries=3,
            project_path="/tmp",
            metadata={},
        )

        # Mock the agent creation to avoid actual LLM calls
        with patch("mini_coder.graph.nodes.create_react_agent") as mock_create:
            mock_agent = AsyncMock()
            mock_agent.ainvoke = AsyncMock(return_value={
                "messages": [MagicMock(content="Found 3 files related to login")]
            })
            mock_create.return_value = mock_agent

            result = await explorer_node(state)

        assert "exploration_result" in result
        assert result["current_stage"] == STAGE_EXPLORING

    @pytest.mark.asyncio
    async def test_explorer_creates_agent_message(self):
        """Explorer should create an AgentMessage."""
        from mini_coder.graph.nodes import explorer_node
        from mini_coder.graph.state import CodingAgentState, AGENT_EXPLORER, AGENT_PLANNER

        state = CodingAgentState(
            messages=[],
            user_request="查找登录相关代码",
            current_stage="routing",
            session_id="test-004",
            agent_messages=[],
            exploration_result=None,
            implementation_plan=None,
            code_changes=[],
            review_result=None,
            test_result=None,
            tool_results=[],
            errors=[],
            retry_count=0,
            max_retries=3,
            project_path="/tmp",
            metadata={},
        )

        with patch("mini_coder.graph.nodes.create_react_agent") as mock_create:
            mock_agent = AsyncMock()
            mock_agent.ainvoke = AsyncMock(return_value={
                "messages": [MagicMock(content="Found files")]
            })
            mock_create.return_value = mock_agent

            result = await explorer_node(state)

        assert "agent_messages" in result
        assert len(result["agent_messages"]) == 1
        assert result["agent_messages"][0]["from_agent"] == AGENT_EXPLORER
        assert result["agent_messages"][0]["to_agent"] == AGENT_PLANNER


class TestCompleteNode:
    """Tests for complete_node."""

    @pytest.mark.asyncio
    async def test_complete_sets_completed_stage(self):
        """Complete node should set stage to 'completed'."""
        from mini_coder.graph.nodes import complete_node
        from mini_coder.graph.state import CodingAgentState, STAGE_COMPLETED

        state = CodingAgentState(
            messages=[],
            user_request="test",
            current_stage="testing",
            session_id="test-005",
            agent_messages=[],
            exploration_result="done",
            implementation_plan="done",
            code_changes=[{"file": "test.py", "content": "pass", "action": "create"}],
            review_result={"passed": True},
            test_result={"all_passed": True},
            tool_results=[],
            errors=[],
            retry_count=0,
            max_retries=3,
            project_path="/tmp",
            metadata={},
        )

        result = await complete_node(state)

        assert result["current_stage"] == STAGE_COMPLETED