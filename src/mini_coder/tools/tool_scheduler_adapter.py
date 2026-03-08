"""ToolScheduler adapter for LangChain tools.

This module adapts the existing ToolScheduler to work with LangChain tools,
enabling DAG-based parallel execution within LangGraph nodes.
"""
import asyncio
import time
from typing import Any, Dict, List, Optional

from langchain_core.tools import BaseTool

from mini_coder.agents.mailbox import (
    ToolCall,
    ToolCallResult,
    ToolBatchRequest,
    ToolBatchResult,
)


class LangChainToolScheduler:
    """Scheduler for executing LangChain tools with DAG support.

    This adapter allows the existing ToolScheduler logic to work with
    LangChain Tool objects, enabling:
    - Parallel execution of independent tools
    - DAG-based execution with depends_on
    - Timeout and concurrency control

    Example:
        >>> scheduler = LangChainToolScheduler(tools=[read_file, write_file])
        >>> result = await scheduler.execute_batch(request)
    """

    def __init__(
        self,
        tools: List[BaseTool],
        max_concurrency: int = 3,
        default_timeout: float = 60.0,
    ) -> None:
        """Initialize the scheduler.

        Args:
            tools: List of LangChain Tool instances
            max_concurrency: Maximum concurrent tool executions
            default_timeout: Default timeout per tool call
        """
        self._tools = {tool.name: tool for tool in tools}
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._default_timeout = default_timeout

    async def execute_single(self, tool_call: ToolCall) -> ToolCallResult:
        """Execute a single tool call.

        Args:
            tool_call: Tool call specification

        Returns:
            ToolCallResult with output or error
        """
        tool = self._tools.get(tool_call.tool_name)
        if tool is None:
            return ToolCallResult(
                call_id=tool_call.call_id,
                tool_name=tool_call.tool_name,
                success=False,
                duration=0.0,
                output=None,
                error=f"Unknown tool: {tool_call.tool_name}",
            )

        start_time = time.time()
        try:
            async with self._semaphore:
                # LangChain tools have sync invoke, wrap in executor
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: tool.invoke(tool_call.arguments),
                    ),
                    timeout=self._default_timeout,
                )

            duration = time.time() - start_time
            return ToolCallResult(
                call_id=tool_call.call_id,
                tool_name=tool_call.tool_name,
                success=True,
                duration=duration,
                output=result,
                error=None,
            )
        except asyncio.TimeoutError:
            duration = time.time() - start_time
            return ToolCallResult(
                call_id=tool_call.call_id,
                tool_name=tool_call.tool_name,
                success=False,
                duration=duration,
                output=None,
                error=f"Timeout after {self._default_timeout}s",
            )
        except Exception as e:
            duration = time.time() - start_time
            return ToolCallResult(
                call_id=tool_call.call_id,
                tool_name=tool_call.tool_name,
                success=False,
                duration=duration,
                output=None,
                error=str(e),
            )

    async def execute_batch(self, request: ToolBatchRequest) -> ToolBatchResult:
        """Execute a batch of tool calls with DAG support.

        Args:
            request: Batch request with tool calls and dependencies

        Returns:
            ToolBatchResult with all results
        """
        start_time = time.time()
        results: List[ToolCallResult] = []

        # Build dependency graph
        call_map = {tc.call_id: tc for tc in request.tool_calls}
        completed: Dict[str, ToolCallResult] = {}

        # Execute in topological order
        while len(completed) < len(request.tool_calls):
            # Find calls with all dependencies satisfied
            ready = [
                tc for tc in request.tool_calls
                if tc.call_id not in completed
                and all(dep in completed for dep in tc.depends_on)
            ]

            if not ready:
                # Circular dependency or other issue
                for tc in request.tool_calls:
                    if tc.call_id not in completed:
                        results.append(ToolCallResult(
                            call_id=tc.call_id,
                            tool_name=tc.tool_name,
                            success=False,
                            duration=0.0,
                            output=None,
                            error="Dependency not satisfied",
                        ))
                break

            # Execute ready calls in parallel
            tasks = [self.execute_single(tc) for tc in ready]
            batch_results = await asyncio.gather(*tasks)

            for tc, result in zip(ready, batch_results):
                completed[tc.call_id] = result
                results.append(result)

        duration = time.time() - start_time
        return ToolBatchResult(
            batch_id=request.batch_id,
            results=results,
            success_count=sum(1 for r in results if r.success),
            failure_count=sum(1 for r in results if not r.success),
            elapsed_time=duration,
        )