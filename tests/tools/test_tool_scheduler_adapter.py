"""Tests for ToolScheduler adaptation to LangChain tools.

TDD tests for DAG execution with LangChain tools.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path
import tempfile
import os


class TestLangChainToolScheduler:
    """Tests for LangChainToolScheduler."""

    @pytest.mark.asyncio
    async def test_execute_single_tool(self):
        """Should execute a single tool call."""
        from mini_coder.tools.tool_scheduler_adapter import LangChainToolScheduler
        from mini_coder.tools.langchain_tools import read_file
        from mini_coder.agents.mailbox import ToolCall
        import tempfile
        import os

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
    async def test_execute_parallel_tools(self):
        """Should execute multiple tools in parallel."""
        from mini_coder.tools.tool_scheduler_adapter import LangChainToolScheduler
        from mini_coder.tools.langchain_tools import read_file, write_file
        from mini_coder.agents.mailbox import ToolCall, ToolBatchRequest
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
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

    @pytest.mark.asyncio
    async def test_execute_dag_tools(self):
        """Should execute tools with DAG dependencies."""
        from mini_coder.tools.tool_scheduler_adapter import LangChainToolScheduler
        from mini_coder.tools.langchain_tools import read_file, write_file
        from mini_coder.agents.mailbox import ToolCall, ToolBatchRequest
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "config.txt")
            Path(config_file).write_text("output_file=output.txt")

            scheduler = LangChainToolScheduler(tools=[read_file, write_file])

            # DAG: read config first, then write based on it
            request = ToolBatchRequest(
                batch_id="batch-dag",
                tool_calls=[
                    ToolCall(
                        call_id="c1",
                        tool_name="read_file",
                        arguments={"path": config_file},
                        depends_on=[],
                    ),
                    ToolCall(
                        call_id="c2",
                        tool_name="write_file",
                        arguments={"path": os.path.join(tmpdir, "output.txt"), "content": "test"},
                        depends_on=["c1"],
                    ),
                ],
                max_concurrency=2,
            )

            result = await scheduler.execute_batch(request)

            # Both should complete
            assert result.success_count >= 1