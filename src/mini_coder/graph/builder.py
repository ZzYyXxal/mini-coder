"""LangGraph builder for mini-coder workflow.

This module provides the CodingAgentGraphBuilder class that constructs
the complete workflow graph for the multi-agent coding system.

Graph Structure:
```
                    ┌─────────────┐
                    │   router    │
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
    ┌───────────┐   ┌───────────┐   ┌───────────┐
    │ explorer  │   │  planner  │   │   coder   │
    └─────┬─────┘   └─────┬─────┘   └─────┬─────┘
          │               │               │
          └───────────────┴───────────────┘
                          │
                          ▼
                   ┌───────────┐
                   │ reviewer  │
                   └─────┬─────┘
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
        ┌───────────┐         ┌───────────┐
        │   bash    │         │ complete  │
        └─────┬─────┘         └───────────┘
              │
              ▼
        ┌───────────┐
        │ complete  │
        └───────────┘
```
"""
from typing import Any, Dict, Optional

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import CodingAgentState
from .nodes import (
    router_node,
    explorer_node,
    planner_node,
    coder_node,
    reviewer_node,
    bash_node,
    complete_node,
)
from .edges import route_by_intent, check_review_result, check_test_result


class CodingAgentGraphBuilder:
    """Builder for the coding agent workflow graph.

    This class constructs a LangGraph StateGraph that orchestrates
    the multi-agent coding workflow.

    Example:
        >>> builder = CodingAgentGraphBuilder()
        >>> graph = builder.build()
        >>> result = await graph.ainvoke(initial_state)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the graph builder.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self._checkpointer = MemorySaver()

    def build(self) -> Any:
        """Build and compile the workflow graph.

        Returns:
            Compiled LangGraph graph ready for execution
        """
        # Create state graph
        graph = StateGraph(CodingAgentState)

        # Add nodes
        graph.add_node("router", router_node)
        graph.add_node("explorer", explorer_node)
        graph.add_node("planner", planner_node)
        graph.add_node("coder", coder_node)
        graph.add_node("reviewer", reviewer_node)
        graph.add_node("bash", bash_node)
        graph.add_node("complete", complete_node)

        # Set entry point
        graph.set_entry_point("router")

        # Add conditional edges from router
        graph.add_conditional_edges(
            "router",
            route_by_intent,
            {
                "explore": "explorer",
                "plan": "planner",
                "code": "coder",
                "simple": "coder",
            },
        )

        # Standard flow edges
        graph.add_edge("explorer", "planner")
        graph.add_edge("planner", "coder")
        graph.add_edge("coder", "reviewer")

        # Review branch
        graph.add_conditional_edges(
            "reviewer",
            check_review_result,
            {
                "pass": "bash",
                "reject": "coder",
                "max_retry": "complete",
            },
        )

        # Test branch
        graph.add_conditional_edges(
            "bash",
            check_test_result,
            {
                "pass": "complete",
                "fail": "coder",
            },
        )

        # Complete ends the workflow
        graph.add_edge("complete", END)

        # Compile with checkpointer for state persistence
        return graph.compile(checkpointer=self._checkpointer)