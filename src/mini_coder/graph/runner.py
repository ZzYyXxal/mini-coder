"""GraphRunner for executing LangGraph workflows.

This module provides the GraphRunner class that executes the
LangGraph workflow, supporting both synchronous and streaming
execution modes.

Phase 5.1 of LangGraph refactor.
"""

import asyncio
import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional, cast, cast

from langgraph.graph import StateGraph

from mini_coder.graph.state import (
    CodingAgentState,
    create_initial_state,
    STAGE_PENDING,
    STAGE_ROUTING,
    STAGE_COMPLETED,
)
from mini_coder.graph.builder import CodingAgentGraphBuilder

logger = logging.getLogger(__name__)


class GraphRunner:
    """Runner for executing LangGraph workflows.

    This class wraps the compiled LangGraph and provides:
    - Synchronous execution via run()
    - Streaming execution via stream()
    - Error handling and retry logic
    - Event emission for TUI integration

    Example:
        >>> runner = GraphRunner()
        >>> result = await runner.run(state)
        >>>
        >>> async for event in runner.stream(state):
        ...     print(event)
    """

    def __init__(
        self,
        llm_service: Any = None,
        max_retries: int = 3,
        timeout: int = 300,
        tools: Optional[List[Any]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize the GraphRunner.

        Args:
            llm_service: LLM service instance (optional, for compatibility)
            max_retries: Maximum retry attempts (default: 3)
            timeout: Timeout in seconds (default: 300)
            tools: Optional list of LangChain tools
            config: Optional configuration for the graph builder
        """
        self.llm_service = llm_service
        self.max_retries = max_retries
        self.timeout = timeout
        self.tools = tools or []
        self.config = config or {}

        # Build and compile the graph
        self._build_graph()

        logger.info(f"GraphRunner initialized with max_retries={max_retries}, timeout={timeout}")

    def _build_graph(self) -> None:
        """Build and compile the LangGraph workflow."""
        builder = CodingAgentGraphBuilder(config=self.config)
        self.graph = builder.build()

    async def run(self, state: CodingAgentState) -> CodingAgentState:
        """Run the workflow synchronously.

        Args:
            state: Initial state for the workflow

        Returns:
            Final state after workflow completion
        """
        logger.info(f"Starting workflow run for session {state.get('session_id')}")

        start_time = time.time()
        current_state = state.copy()

        try:
            # Set initial stage
            current_state["current_stage"] = STAGE_ROUTING

            # Config for checkpointer (requires thread_id)
            config = {
                "configurable": {
                    "thread_id": state.get("session_id", "default"),
                }
            }

            # Run the graph with timeout
            result = await asyncio.wait_for(
                self.graph.ainvoke(current_state, config=config),
                timeout=self.timeout,
            )

            # Update stage to completed
            result["current_stage"] = STAGE_COMPLETED

            duration = time.time() - start_time
            logger.info(f"Workflow completed in {duration:.2f}s")

            return cast(CodingAgentState, result)

        except asyncio.TimeoutError:
            logger.error(f"Workflow timed out after {self.timeout}s")
            current_state["errors"].append(f"Workflow timed out after {self.timeout}s")
            current_state["current_stage"] = STAGE_COMPLETED
            return current_state

        except Exception as e:
            logger.error(f"Workflow error: {e}")
            current_state["errors"].append(str(e))
            return current_state

    async def stream(self, state: CodingAgentState) -> AsyncIterator[Dict[str, Any]]:
        """Run the workflow with streaming events.

        Args:
            state: Initial state for the workflow

        Yields:
            Event dictionaries with type and data
        """
        logger.info(f"Starting streaming workflow for session {state.get('session_id')}")

        start_time = time.time()
        current_state = state.copy()
        current_state["current_stage"] = STAGE_ROUTING

        # Config for checkpointer (requires thread_id)
        config = {
            "configurable": {
                "thread_id": state.get("session_id", "default"),
            }
        }

        try:
            # Yield start event
            yield {
                "type": "workflow_start",
                "session_id": state.get("session_id"),
                "timestamp": start_time,
            }

            # Stream events from the graph
            async for event in self.graph.astream_events(
                current_state, config=config, version="v2"
            ):
                # Transform LangGraph events to our format
                transformed = self._transform_event(event)
                if transformed:
                    yield transformed

            # Yield completion event
            duration = time.time() - start_time
            yield {
                "type": "workflow_end",
                "session_id": state.get("session_id"),
                "duration": duration,
                "timestamp": time.time(),
            }

        except asyncio.TimeoutError:
            yield {
                "type": "error",
                "error": f"Workflow timed out after {self.timeout}s",
                "timestamp": time.time(),
            }

        except Exception as e:
            yield {
                "type": "error",
                "error": str(e),
                "timestamp": time.time(),
            }

    def _transform_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Transform LangGraph event to our event format.

        Args:
            event: Raw LangGraph event

        Returns:
            Transformed event or None if not relevant
        """
        event_type = event.get("event")

        if event_type == "on_chain_start":
            name = event.get("name", "unknown")
            if name in ("router_node", "explorer_node", "planner_node",
                       "coder_node", "reviewer_node", "bash_node"):
                return {
                    "type": "node_start",
                    "node": name,
                    "timestamp": time.time(),
                }

        elif event_type == "on_chain_end":
            name = event.get("name", "unknown")
            if name in ("router_node", "explorer_node", "planner_node",
                       "coder_node", "reviewer_node", "bash_node"):
                return {
                    "type": "node_end",
                    "node": name,
                    "output": event.get("data", {}).get("output"),
                    "timestamp": time.time(),
                }

        elif event_type == "on_llm_stream":
            # Token streaming
            chunk = event.get("data", {}).get("chunk")
            if chunk:
                content = getattr(chunk, "content", None) or getattr(chunk, "text", None)
                if content:
                    return {
                        "type": "token",
                        "content": content,
                        "timestamp": time.time(),
                    }

        elif event_type == "on_tool_start":
            return {
                "type": "tool_start",
                "tool": event.get("name", "unknown"),
                "input": event.get("data", {}).get("input"),
                "timestamp": time.time(),
            }

        elif event_type == "on_tool_end":
            return {
                "type": "tool_end",
                "tool": event.get("name", "unknown"),
                "output": event.get("data", {}).get("output"),
                "timestamp": time.time(),
            }

        return None

    def run_sync(self, state: CodingAgentState) -> CodingAgentState:
        """Synchronous wrapper for run().

        Args:
            state: Initial state for the workflow

        Returns:
            Final state after workflow completion
        """
        return asyncio.run(self.run(state))


# ==================== Exports ====================

__all__ = [
    "GraphRunner",
]