"""Tests for LangGraph edge functions (routing logic).

TDD Phase 2: Red - Write tests first.
"""
import pytest


class TestRouteByIntent:
    """Tests for route_by_intent function."""

    def test_explore_intent_returns_explore(self):
        """Explore intent should return 'explore'."""
        from mini_coder.graph.edges import route_by_intent
        from mini_coder.graph.state import CodingAgentState

        state = CodingAgentState(
            messages=[],
            user_request="探索代码库",
            current_stage="routing",
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
            metadata={"intent": "explore"},
        )

        result = route_by_intent(state)
        assert result == "explore"

    def test_plan_intent_returns_plan(self):
        """Plan intent should return 'plan'."""
        from mini_coder.graph.edges import route_by_intent
        from mini_coder.graph.state import CodingAgentState

        state = CodingAgentState(
            messages=[],
            user_request="设计登录系统",
            current_stage="routing",
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
            metadata={"intent": "plan"},
        )

        result = route_by_intent(state)
        assert result == "plan"

    def test_code_intent_returns_code(self):
        """Code intent should return 'code'."""
        from mini_coder.graph.edges import route_by_intent
        from mini_coder.graph.state import CodingAgentState

        state = CodingAgentState(
            messages=[],
            user_request="实现登录功能",
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
            metadata={"intent": "code"},
        )

        result = route_by_intent(state)
        assert result == "code"

    def test_simple_request_returns_simple(self):
        """Simple request should return 'simple'."""
        from mini_coder.graph.edges import route_by_intent
        from mini_coder.graph.state import CodingAgentState

        state = CodingAgentState(
            messages=[],
            user_request="hi",  # Very short request
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
            metadata={"intent": "simple"},
        )

        result = route_by_intent(state)
        assert result == "simple"


class TestCheckReviewResult:
    """Tests for check_review_result function."""

    def test_passed_review_returns_pass(self):
        """Passed review should return 'pass'."""
        from mini_coder.graph.edges import check_review_result
        from mini_coder.graph.state import CodingAgentState

        state = CodingAgentState(
            messages=[],
            user_request="test",
            current_stage="reviewing",
            session_id="test-005",
            agent_messages=[],
            exploration_result=None,
            implementation_plan=None,
            code_changes=[],
            review_result={"passed": True},
            test_result=None,
            tool_results=[],
            errors=[],
            retry_count=0,
            max_retries=3,
            project_path="/tmp",
            metadata={},
        )

        result = check_review_result(state)
        assert result == "pass"

    def test_failed_review_returns_reject(self):
        """Failed review should return 'reject'."""
        from mini_coder.graph.edges import check_review_result
        from mini_coder.graph.state import CodingAgentState

        state = CodingAgentState(
            messages=[],
            user_request="test",
            current_stage="reviewing",
            session_id="test-006",
            agent_messages=[],
            exploration_result=None,
            implementation_plan=None,
            code_changes=[],
            review_result={"passed": False},
            test_result=None,
            tool_results=[],
            errors=[],
            retry_count=0,
            max_retries=3,
            project_path="/tmp",
            metadata={},
        )

        result = check_review_result(state)
        assert result == "reject"

    def test_max_retry_returns_max_retry(self):
        """Max retry reached should return 'max_retry'."""
        from mini_coder.graph.edges import check_review_result
        from mini_coder.graph.state import CodingAgentState

        state = CodingAgentState(
            messages=[],
            user_request="test",
            current_stage="reviewing",
            session_id="test-007",
            agent_messages=[],
            exploration_result=None,
            implementation_plan=None,
            code_changes=[],
            review_result={"passed": False},
            test_result=None,
            tool_results=[],
            errors=[],
            retry_count=3,
            max_retries=3,
            project_path="/tmp",
            metadata={},
        )

        result = check_review_result(state)
        assert result == "max_retry"


class TestCheckTestResult:
    """Tests for check_test_result function."""

    def test_all_passed_returns_pass(self):
        """All tests passed should return 'pass'."""
        from mini_coder.graph.edges import check_test_result
        from mini_coder.graph.state import CodingAgentState

        state = CodingAgentState(
            messages=[],
            user_request="test",
            current_stage="testing",
            session_id="test-008",
            agent_messages=[],
            exploration_result=None,
            implementation_plan=None,
            code_changes=[],
            review_result=None,
            test_result={"all_passed": True},
            tool_results=[],
            errors=[],
            retry_count=0,
            max_retries=3,
            project_path="/tmp",
            metadata={},
        )

        result = check_test_result(state)
        assert result == "pass"

    def test_failed_tests_returns_fail(self):
        """Failed tests should return 'fail'."""
        from mini_coder.graph.edges import check_test_result
        from mini_coder.graph.state import CodingAgentState

        state = CodingAgentState(
            messages=[],
            user_request="test",
            current_stage="testing",
            session_id="test-009",
            agent_messages=[],
            exploration_result=None,
            implementation_plan=None,
            code_changes=[],
            review_result=None,
            test_result={"all_passed": False, "failures": ["test_login"]},
            tool_results=[],
            errors=[],
            retry_count=0,
            max_retries=3,
            project_path="/tmp",
            metadata={},
        )

        result = check_test_result(state)
        assert result == "fail"