"""Tests for structured output parsing.

TDD tests for JSON structured output from agents.
"""
import pytest
import json


class TestCoderOutput:
    """Tests for Coder structured output."""

    def test_coder_output_to_dict(self):
        """CoderOutput should convert to dict correctly."""
        from mini_coder.graph.structured_output import CodeChunk, CoderOutput

        chunk = CodeChunk(
            path="main.py",
            action="create",
            content="print('hello')",
            description="Hello world script"
        )

        output = CoderOutput(
            code_chunks=[chunk],
            summary="Created hello world script",
        )

        d = output.to_dict()
        assert d["summary"] == "Created hello world script"
        assert len(d["code_chunks"]) == 1
        assert d["code_chunks"][0]["path"] == "main.py"

    def test_coder_output_to_json(self):
        """CoderOutput should serialize to JSON."""
        from mini_coder.graph.structured_output import CodeChunk, CoderOutput

        chunk = CodeChunk(
            path="app.py",
            action="modify",
            content="def main(): pass",
            description="Added main function"
        )

        output = CoderOutput(
            code_chunks=[chunk],
            summary="Modified app",
            incomplete_items=["Add tests"],
        )

        json_str = output.to_json()
        parsed = json.loads(json_str)

        assert parsed["summary"] == "Modified app"
        assert "code_chunks" in parsed
        assert parsed["incomplete_items"] == ["Add tests"]

    def test_coder_output_from_dict(self):
        """CoderOutput should deserialize from dict."""
        from mini_coder.graph.structured_output import CoderOutput

        data = {
            "code_chunks": [
                {
                    "path": "test.py",
                    "action": "create",
                    "content": "def test_x(): pass",
                    "description": "Test file"
                }
            ],
            "summary": "Created test",
            "incomplete_items": [],
        }

        output = CoderOutput.from_dict(data)

        assert output.summary == "Created test"
        assert len(output.code_chunks) == 1
        assert output.code_chunks[0].path == "test.py"

    def test_coder_multiple_chunks(self):
        """CoderOutput should handle multiple code chunks."""
        from mini_coder.graph.structured_output import CodeChunk, CoderOutput

        chunks = [
            CodeChunk(path="model.py", action="create", content="class User:", description="User model"),
            CodeChunk(path="view.py", action="create", content="def show():", description="View function"),
        ]

        output = CoderOutput(code_chunks=chunks, summary="Created MVC")

        assert len(output.code_chunks) == 2


class TestPlannerOutput:
    """Tests for Planner structured output."""

    def test_planner_output_to_dict(self):
        """PlannerOutput should convert to dict correctly."""
        from mini_coder.graph.structured_output import TodoTask, TaskPriority, PlannerOutput

        task = TodoTask(
            id="1.1",
            title="Create model",
            description="Define User model",
            is_test=False,
            priority=TaskPriority.HIGH,
        )

        output = PlannerOutput(
            title="User System",
            overview="Implement user management",
            phases={"Phase 1": [task]},
        )

        d = output.to_dict()
        assert d["title"] == "User System"
        assert "Phase 1" in d["phases"]

    def test_planner_output_get_all_tasks(self):
        """PlannerOutput should flatten all tasks."""
        from mini_coder.graph.structured_output import TodoTask, PlannerOutput

        task1 = TodoTask(id="1.1", title="Task 1", description="")
        task2 = TodoTask(id="2.1", title="Task 2", description="")

        output = PlannerOutput(
            title="Plan",
            overview="Overview",
            phases={
                "Phase 1": [task1],
                "Phase 2": [task2],
            },
        )

        all_tasks = output.get_all_tasks()
        assert len(all_tasks) == 2

    def test_todo_task_dependencies(self):
        """TodoTask should track dependencies."""
        from mini_coder.graph.structured_output import TodoTask

        task = TodoTask(
            id="2.1",
            title="Implementation",
            description="Implement feature",
            dependencies=["1.1", "1.2"],
        )

        assert task.dependencies == ["1.1", "1.2"]

    def test_tdd_ordering(self):
        """PlannerOutput should support TDD task ordering."""
        from mini_coder.graph.structured_output import TodoTask, PlannerOutput

        test_task = TodoTask(
            id="1.1",
            title="Test login",
            description="Write test for login",
            is_test=True,
        )
        impl_task = TodoTask(
            id="1.2",
            title="Implement login",
            description="Implement login function",
            is_test=False,
            dependencies=["1.1"],
        )

        output = PlannerOutput(
            title="Login Feature",
            overview="TDD login implementation",
            phases={"Phase 1": [test_task, impl_task]},
        )

        tasks = output.phases["Phase 1"]
        assert tasks[0].is_test is True
        assert tasks[1].is_test is False


class TestReviewerOutput:
    """Tests for Reviewer structured output."""

    def test_reviewer_pass_output(self):
        """ReviewerOutput should represent pass decision."""
        from mini_coder.graph.structured_output import ReviewDecision, ReviewerOutput

        output = ReviewerOutput(
            decision=ReviewDecision.PASS,
            summary="Code looks good",
        )

        d = output.to_dict()
        assert d["decision"] == "pass"
        assert d["issues"] == []

    def test_reviewer_reject_with_issues(self):
        """ReviewerOutput should represent reject with issues."""
        from mini_coder.graph.structured_output import (
            ReviewDecision,
            ReviewIssue,
            ReviewerOutput,
        )

        issue = ReviewIssue(
            file="main.py",
            line=42,
            category="quality",
            message="Missing type hints",
            suggestion="Add type annotations",
        )

        output = ReviewerOutput(
            decision=ReviewDecision.REJECT,
            issues=[issue],
            summary="Found quality issues",
        )

        d = output.to_dict()
        assert d["decision"] == "reject"
        assert len(d["issues"]) == 1
        assert d["issues"][0]["file"] == "main.py"


class TestExplorerOutput:
    """Tests for Explorer structured output."""

    def test_explorer_output_findings(self):
        """ExplorerOutput should represent file findings."""
        from mini_coder.graph.structured_output import FileFinding, ExplorerOutput

        finding = FileFinding(
            path="src/auth.py",
            relevance="Main authentication module",
            key_functions=["login", "logout"],
        )

        output = ExplorerOutput(
            findings=[finding],
            summary="Found auth module",
            suggested_next_steps=["Review password handling"],
        )

        d = output.to_dict()
        assert len(d["findings"]) == 1
        assert d["findings"][0]["key_functions"] == ["login", "logout"]


class TestBashOutput:
    """Tests for Bash structured output."""

    def test_bash_output_test_results(self):
        """BashOutput should represent test results."""
        from mini_coder.graph.structured_output import TestResult, BashOutput

        tests = TestResult(
            passed=10,
            failed=2,
            skipped=1,
            coverage_percent=85.0,
        )

        output = BashOutput(
            tests=tests,
            type_check_passed=True,
            lint_passed=True,
            commands_run=["pytest tests/"],
        )

        d = output.to_dict()
        assert d["tests"]["passed"] == 10
        assert d["tests"]["failed"] == 2
        assert d["type_check_passed"] is True

    def test_bash_output_errors(self):
        """BashOutput should track errors."""
        from mini_coder.graph.structured_output import BashOutput

        output = BashOutput(
            commands_run=["pytest tests/"],
            errors=["test_login failed: AssertionError"],
        )

        d = output.to_dict()
        assert len(d["errors"]) == 1


class TestRouterOutput:
    """Tests for Router structured output."""

    def test_router_output_to_dict(self):
        """RouterOutput should convert to dict correctly."""
        from mini_coder.graph.structured_output import (
            RouterDestination,
            RouterOutput,
        )

        output = RouterOutput(
            destination=RouterDestination.CODER,
            reasoning="User wants to implement new code",
            confidence=0.95,
        )

        d = output.to_dict()
        assert d["destination"] == "coder"
        assert d["reasoning"] == "User wants to implement new code"
        assert d["confidence"] == 0.95

    def test_router_output_with_bash_mode(self):
        """RouterOutput should include bash_mode for bash destination."""
        from mini_coder.graph.structured_output import (
            RouterDestination,
            RouterOutput,
        )

        output = RouterOutput(
            destination=RouterDestination.BASH,
            reasoning="User wants to run tests",
            bash_mode="quality_report",
            confidence=0.99,
        )

        d = output.to_dict()
        assert d["destination"] == "bash"
        assert d["bash_mode"] == "quality_report"
        assert "command" not in d  # command is None, not included

    def test_router_output_with_command(self):
        """RouterOutput should include command for single_command mode."""
        from mini_coder.graph.structured_output import (
            RouterDestination,
            RouterOutput,
        )

        output = RouterOutput(
            destination=RouterDestination.BASH,
            reasoning="User wants to list files",
            bash_mode="single_command",
            command="ls -la",
            confidence=0.90,
        )

        d = output.to_dict()
        assert d["bash_mode"] == "single_command"
        assert d["command"] == "ls -la"

    def test_router_low_confidence(self):
        """RouterOutput should handle low confidence for ambiguous requests."""
        from mini_coder.graph.structured_output import (
            RouterDestination,
            RouterOutput,
        )

        output = RouterOutput(
            destination=RouterDestination.CODER,
            reasoning="Ambiguous request, best guess is code modification",
            confidence=0.60,
        )

        assert output.confidence < 0.75


class TestFallbackParsing:
    """Tests for enum fallback parsing."""

    def test_priority_fallback_unknown(self):
        """Should fallback to MEDIUM for unknown priority values."""
        from mini_coder.graph.output_parser import _safe_parse_priority
        from mini_coder.graph.structured_output import TaskPriority

        assert _safe_parse_priority("critical") == TaskPriority.HIGH
        assert _safe_parse_priority("urgent") == TaskPriority.HIGH
        assert _safe_parse_priority("normal") == TaskPriority.MEDIUM
        assert _safe_parse_priority("unknown_value") == TaskPriority.MEDIUM

    def test_review_decision_fallback(self):
        """Should fallback to REJECT for unknown decision values."""
        from mini_coder.graph.output_parser import _safe_parse_review_decision
        from mini_coder.graph.structured_output import ReviewDecision

        assert _safe_parse_review_decision("approved") == ReviewDecision.PASS
        assert _safe_parse_review_decision("failed") == ReviewDecision.REJECT
        assert _safe_parse_review_decision("unknown") == ReviewDecision.REJECT

    def test_router_destination_fallback(self):
        """Should fallback to GENERAL_PURPOSE for unknown destinations."""
        from mini_coder.graph.output_parser import _safe_parse_router_destination
        from mini_coder.graph.structured_output import RouterDestination

        assert _safe_parse_router_destination("general") == RouterDestination.GENERAL_PURPOSE
        assert _safe_parse_router_destination("unknown_agent") == RouterDestination.GENERAL_PURPOSE

    def test_router_destination_mini_coder_guide(self):
        """Should correctly parse mini_coder_guide destination."""
        from mini_coder.graph.output_parser import _safe_parse_router_destination
        from mini_coder.graph.structured_output import RouterDestination

        assert _safe_parse_router_destination("mini_coder_guide") == RouterDestination.MINI_CODER_GUIDE
        assert _safe_parse_router_destination("guide") == RouterDestination.MINI_CODER_GUIDE
        assert _safe_parse_router_destination("help") == RouterDestination.MINI_CODER_GUIDE

    def test_bash_output_with_mode(self):
        """BashOutput should include bash_mode_used."""
        from mini_coder.graph.structured_output import BashOutput

        output = BashOutput(
            commands_run=["ls -la"],
            bash_mode_used="single_command",
        )

        d = output.to_dict()
        assert d["bash_mode_used"] == "single_command"


class TestJSONParsing:
    """Tests for parsing JSON from LLM output."""

    def test_parse_coder_json(self):
        """Should parse Coder JSON from LLM output."""
        from mini_coder.graph.structured_output import CoderOutput

        json_str = '''
        {
            "code_chunks": [
                {
                    "path": "hello.py",
                    "action": "create",
                    "content": "print('hello')",
                    "description": "Hello script"
                }
            ],
            "summary": "Created hello.py",
            "incomplete_items": [],
            "memory_notes": null
        }
        '''

        data = json.loads(json_str)
        output = CoderOutput.from_dict(data)

        assert output.summary == "Created hello.py"
        assert len(output.code_chunks) == 1

    def test_parse_planner_json(self):
        """Should parse Planner JSON from LLM output."""
        from mini_coder.graph.structured_output import PlannerOutput, TodoTask, TaskPriority

        json_str = '''
        {
            "title": "Calculator",
            "overview": "Build a calculator",
            "phases": {
                "Phase 1": [
                    {
                        "id": "1.1",
                        "title": "Test add",
                        "description": "Test addition",
                        "is_test": true,
                        "priority": "high",
                        "dependencies": [],
                        "estimated_complexity": "low"
                    }
                ]
            },
            "tech_decisions": ["Use class-based design"],
            "risks": []
        }
        '''

        data = json.loads(json_str)
        output = PlannerOutput(
            title=data["title"],
            overview=data["overview"],
            phases={
                phase: [
                    TodoTask(
                        id=t["id"],
                        title=t["title"],
                        description=t["description"],
                        is_test=t.get("is_test", False),
                        priority=TaskPriority(t.get("priority", "medium")),
                        dependencies=t.get("dependencies", []),
                        estimated_complexity=t.get("estimated_complexity", "medium"),
                    )
                    for t in tasks
                ]
                for phase, tasks in data["phases"].items()
            },
            tech_decisions=data.get("tech_decisions", []),
            risks=data.get("risks", []),
        )

        assert output.title == "Calculator"
        assert len(output.get_all_tasks()) == 1
        assert output.get_all_tasks()[0].is_test is True