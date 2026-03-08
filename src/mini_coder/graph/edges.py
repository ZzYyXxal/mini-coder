"""LangGraph edge functions (routing logic).

This module defines the conditional edge functions used to route
between nodes in the workflow graph.
"""
from typing import Literal

from .state import CodingAgentState


def route_by_intent(
    state: CodingAgentState,
) -> Literal["explore", "plan", "code", "simple"]:
    """Route to the appropriate node based on intent.

    Args:
        state: Current workflow state

    Returns:
        Name of the next node to execute
    """
    intent = state.get("metadata", {}).get("intent", "")

    # Route based on intent
    if intent == "explore" or "explore" in str(intent) or "搜索" in str(intent) or "查找" in str(intent):
        return "explore"
    elif intent == "plan" or "plan" in str(intent) or "设计" in str(intent) or "规划" in str(intent):
        return "plan"
    elif intent == "simple":
        return "simple"
    else:
        # Default to code for implementation tasks
        return "code"


def check_review_result(
    state: CodingAgentState,
) -> Literal["pass", "reject", "max_retry"]:
    """Check the review result and decide next step.

    Args:
        state: Current workflow state

    Returns:
        - "pass": Review passed, proceed to testing
        - "reject": Review failed, return to coding
        - "max_retry": Max retries reached, give up
    """
    # Check if max retries reached
    if state["retry_count"] >= state["max_retries"]:
        return "max_retry"

    # Check review result
    review = state.get("review_result") or {}
    if review.get("passed", False):
        return "pass"

    return "reject"


def check_test_result(
    state: CodingAgentState,
) -> Literal["pass", "fail"]:
    """Check the test result and decide next step.

    Args:
        state: Current workflow state

    Returns:
        - "pass": All tests passed, complete workflow
        - "fail": Tests failed, return to coding
    """
    test = state.get("test_result") or {}
    if test.get("all_passed", False):
        return "pass"

    return "fail"