"""Integration tests for mini-coder core functionality.

Tests cover:
1. Main agent and subagent core functionality
2. Routing functionality
3. Memory functionality
"""
import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch


class TestMainAgentFunctionality:
    """Test main agent core functionality."""

    @pytest.mark.asyncio
    async def test_main_agent_initialization(self):
        """Main agent should initialize correctly."""
        from mini_coder.agents.orchestrator import WorkflowOrchestrator

        # Create mock LLM service
        mock_llm = MagicMock()
        mock_llm.chat = MagicMock(return_value="Response")

        # Test orchestrator initialization
        orchestrator = WorkflowOrchestrator(llm_service=mock_llm)

        assert orchestrator is not None
        assert orchestrator.llm_service == mock_llm

    @pytest.mark.asyncio
    async def test_main_agent_dispatch_to_explorer(self):
        """Main agent should dispatch to Explorer for search requests."""
        from mini_coder.agents.orchestrator import WorkflowOrchestrator, SubAgentType

        mock_llm = MagicMock()
        orchestrator = WorkflowOrchestrator(llm_service=mock_llm)

        # Test intent analysis for exploration - uses specific keywords
        intent = orchestrator._analyze_intent("找找 main.py 在哪里")
        assert intent == SubAgentType.EXPLORER

    @pytest.mark.asyncio
    async def test_main_agent_dispatch_to_planner(self):
        """Main agent should dispatch to Planner for planning requests."""
        from mini_coder.agents.orchestrator import WorkflowOrchestrator, SubAgentType

        mock_llm = MagicMock()
        orchestrator = WorkflowOrchestrator(llm_service=mock_llm)

        # Test intent analysis for planning
        intent = orchestrator._analyze_intent("规划用户认证系统")
        assert intent == SubAgentType.PLANNER

        intent = orchestrator._analyze_intent("设计 API 架构")
        assert intent == SubAgentType.PLANNER

    @pytest.mark.asyncio
    async def test_main_agent_dispatch_to_coder(self):
        """Main agent should dispatch to Coder for implementation requests."""
        from mini_coder.agents.orchestrator import WorkflowOrchestrator, SubAgentType

        mock_llm = MagicMock()
        orchestrator = WorkflowOrchestrator(llm_service=mock_llm)

        # Test intent analysis for coding - uses specific keywords from the actual code
        intent = orchestrator._analyze_intent("实现用户登录功能")
        assert intent == SubAgentType.CODER


class TestSubagentFunctionality:
    """Test subagent core functionality."""

    @pytest.mark.asyncio
    async def test_explorer_agent_capabilities(self):
        """Explorer agent should have read-only capabilities."""
        from mini_coder.agents.base import ExplorerAgent
        from mini_coder.agents.enhanced import AgentCapabilities

        mock_llm = MagicMock()
        mock_llm.chat = MagicMock(return_value="Exploration result")

        agent = ExplorerAgent(llm_service=mock_llm)
        capabilities = agent._capabilities

        # Check capabilities structure
        assert isinstance(capabilities, AgentCapabilities)
        # Should have read tools in allowed_tools
        assert "Read" in capabilities.allowed_tools or "Glob" in capabilities.allowed_tools
        # Should NOT have write tools
        assert "Write" not in capabilities.allowed_tools
        assert "Edit" not in capabilities.allowed_tools

    @pytest.mark.asyncio
    async def test_coder_agent_full_access(self):
        """Coder agent should have full access to code tools."""
        from mini_coder.agents.enhanced import CoderAgent, Blackboard

        mock_llm = MagicMock()
        mock_llm.chat = MagicMock(return_value="Code implemented")

        blackboard = Blackboard("test-task")
        agent = CoderAgent(llm_service=mock_llm, blackboard=blackboard)

        assert agent is not None

    @pytest.mark.asyncio
    async def test_reviewer_agent_binary_output(self):
        """Reviewer agent should output binary pass/reject."""
        from mini_coder.agents.base import ReviewerAgent

        mock_llm = MagicMock()
        # Simulate pass response
        mock_llm.chat = MagicMock(return_value="[Pass] Code looks good")

        agent = ReviewerAgent(llm_service=mock_llm)

        result = agent.execute(
            "Review the code",
            context={"plan": "Plan", "code": "print('hello')"}
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_bash_agent_quality_pipeline(self):
        """Bash agent should run quality pipeline when requested."""
        from mini_coder.agents.base import BashAgent

        mock_llm = MagicMock()
        agent = BashAgent(llm_service=mock_llm)

        # Without explicit quality_report mode, should not run tests
        result = agent.execute("run tests")

        # Should indicate it needs explicit mode
        assert "未收到执行质量流水线的指令" in result.output or result.success is False


class TestRoutingFunctionality:
    """Test routing functionality."""

    @pytest.mark.asyncio
    async def test_route_by_intent_explore(self):
        """Router should route explore intent to explorer."""
        from mini_coder.graph.edges import route_by_intent
        from mini_coder.graph.state import create_initial_state

        state = create_initial_state(
            user_request="探索代码库",
            session_id="test",
        )
        state["metadata"] = {"intent": "explore"}

        result = route_by_intent(state)
        assert result == "explore"

    @pytest.mark.asyncio
    async def test_route_by_intent_plan(self):
        """Router should route plan intent to planner."""
        from mini_coder.graph.edges import route_by_intent
        from mini_coder.graph.state import create_initial_state

        state = create_initial_state(
            user_request="规划功能",
            session_id="test",
        )
        state["metadata"] = {"intent": "plan"}

        result = route_by_intent(state)
        assert result == "plan"

    @pytest.mark.asyncio
    async def test_route_by_intent_code(self):
        """Router should route code intent to coder."""
        from mini_coder.graph.edges import route_by_intent
        from mini_coder.graph.state import create_initial_state

        state = create_initial_state(
            user_request="实现功能",
            session_id="test",
        )
        state["metadata"] = {"intent": "code"}

        result = route_by_intent(state)
        assert result == "code"

    @pytest.mark.asyncio
    async def test_route_by_intent_simple(self):
        """Router should route simple tasks to coder."""
        from mini_coder.graph.edges import route_by_intent
        from mini_coder.graph.state import create_initial_state

        state = create_initial_state(
            user_request="fix typo",
            session_id="test",
        )
        state["metadata"] = {"intent": "simple"}

        result = route_by_intent(state)
        assert result == "simple"


class TestMemoryFunctionality:
    """Test memory functionality."""

    def test_working_memory_operations(self):
        """Working memory should support basic operations."""
        from mini_coder.memory.working_memory import WorkingMemory
        from mini_coder.memory.models import Message

        memory = WorkingMemory()

        # WorkingMemory stores messages
        message = Message(role="user", content="test message")
        memory.add(message)

        # Check internal state
        assert len(memory._messages) > 0

    def test_blackboard_operations(self):
        """Blackboard should support shared context."""
        from mini_coder.agents.enhanced import Blackboard

        blackboard = Blackboard("test-task")

        # Blackboard uses set_context/get_context
        blackboard.set_context("key1", "value1")
        assert blackboard.get_context("key1") == "value1"


class TestToolSchedulerFunctionality:
    """Test tool scheduler functionality."""

    @pytest.mark.asyncio
    async def test_single_tool_execution(self):
        """Tool scheduler should execute single tool."""
        from mini_coder.tools.tool_scheduler_adapter import LangChainToolScheduler
        from mini_coder.tools.langchain_tools import read_file
        from mini_coder.agents.mailbox import ToolCall

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("test content")
            f.flush()

            scheduler = LangChainToolScheduler(tools=[read_file])

            tool_call = ToolCall(
                call_id="call-1",
                tool_name="read_file",
                arguments={"path": f.name},
                depends_on=[],
            )

            result = await scheduler.execute_single(tool_call)

            os.unlink(f.name)
            assert result.success is True
            assert "test content" in result.output

    @pytest.mark.asyncio
    async def test_parallel_tool_execution(self):
        """Tool scheduler should execute tools in parallel."""
        from mini_coder.tools.tool_scheduler_adapter import LangChainToolScheduler
        from mini_coder.tools.langchain_tools import read_file, write_file
        from mini_coder.agents.mailbox import ToolCall, ToolBatchRequest

        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, "file1.txt")
            file2 = os.path.join(tmpdir, "file2.txt")
            Path(file1).write_text("content1")
            Path(file2).write_text("content2")

            scheduler = LangChainToolScheduler(tools=[read_file, write_file])

            request = ToolBatchRequest(
                batch_id="batch-1",
                tool_calls=[
                    ToolCall(call_id="c1", tool_name="read_file", arguments={"path": file1}),
                    ToolCall(call_id="c2", tool_name="read_file", arguments={"path": file2}),
                ],
                max_concurrency=2,
            )

            result = await scheduler.execute_batch(request)

            assert result.success_count == 2
            assert result.failure_count == 0


class TestGraphRunnerIntegration:
    """Test GraphRunner integration."""

    @pytest.mark.asyncio
    async def test_graph_runner_basic_flow(self):
        """GraphRunner should complete basic flow."""
        from mini_coder.graph.runner import GraphRunner
        from mini_coder.graph.state import create_initial_state

        mock_llm = MagicMock()
        runner = GraphRunner(llm_service=mock_llm)

        state = create_initial_state(
            user_request="simple test",
            session_id="test-session",
        )

        result = await runner.run(state)

        assert result is not None
        assert result["current_stage"] == "completed"

    @pytest.mark.asyncio
    async def test_graph_runner_streaming(self):
        """GraphRunner should support streaming."""
        from mini_coder.graph.runner import GraphRunner
        from mini_coder.graph.state import create_initial_state

        mock_llm = MagicMock()
        runner = GraphRunner(llm_service=mock_llm)

        state = create_initial_state(
            user_request="streaming test",
            session_id="test-session",
        )

        events = []
        async for event in runner.stream(state):
            events.append(event)

        # Should have start and end events
        event_types = [e.get("type") for e in events]
        assert "workflow_start" in event_types
        assert "workflow_end" in event_types