"""Tests for output_parser.py (English structured output markers)."""

import pytest
from mini_coder.agents.output_parser import (
    MainAgentParser,
    ReviewerParser,
    QualityReportParser,
    parse_main_agent_output,
    parse_reviewer_output,
    parse_quality_report,
    MainAgentOutputType,
    ReviewerResultType,
    MainAgentOutput,
    ReviewerOutput,
    QualityReport,
)


class TestMainAgentParser:
    """Test MainAgentParser"""

    def test_parse_simple_answer(self) -> None:
        """Test parsing simple answer"""
        text = """[Simple Answer]
This is the answer content."""
        result = parse_main_agent_output(text)

        assert result.output_type == MainAgentOutputType.SIMPLE_ANSWER
        assert result.content == "This is the answer content."
        assert result.problem_type is None
        assert len(result.subtasks) == 0

    def test_parse_complex_task(self) -> None:
        """Test parsing complex task"""
        text = """[Complex Task]
Problem type: Code implementation
Sub-questions:
1. Explore codebase structure → Assign to: EXPLORER
2. Plan implementation → Assign to: PLANNER
3. Implement core logic → Assign to: CODER"""
        result = parse_main_agent_output(text)

        assert result.output_type == MainAgentOutputType.COMPLEX_TASK
        assert result.problem_type == "Code implementation"
        assert len(result.subtasks) == 3
        assert result.subtasks[0].description == "Explore codebase structure"
        assert result.subtasks[0].agent == "EXPLORER"
        assert result.subtasks[1].description == "Plan implementation"
        assert result.subtasks[1].agent == "PLANNER"
        assert result.subtasks[2].description == "Implement core logic"
        assert result.subtasks[2].agent == "CODER"

    def test_parse_complex_task_with_colon_variant(self) -> None:
        """Test parsing complex task with colon variant"""
        text = """[Complex Task]
Problem type: Bug fix
Sub-questions:
1. Locate the bug → Assign to: EXPLORER
2. Fix the bug → Assign to: CODER"""
        result = parse_main_agent_output(text)

        assert result.output_type == MainAgentOutputType.COMPLEX_TASK
        assert result.problem_type == "Bug fix"
        assert len(result.subtasks) == 2

    def test_parse_cannot_handle(self) -> None:
        """Test parsing cannot handle"""
        text = """[Cannot Handle]
This task requires external API access which is not available in the current environment."""
        result = parse_main_agent_output(text)

        assert result.output_type == MainAgentOutputType.CANNOT_HANDLE
        assert "external API" in result.content

    def test_parse_unknown(self) -> None:
        """Test parsing unknown format"""
        text = "This is plain text that does not match any format."
        result = parse_main_agent_output(text)

        assert result.output_type == MainAgentOutputType.UNKNOWN
        assert result.raw_text == text

    def test_parse_with_thinking_tags(self) -> None:
        """Test that thinking tags are preserved in content"""
        text = """[Simple Answer]
<thinking>Reasoning here</thinking>
This is the final answer."""
        result = parse_main_agent_output(text)

        assert result.output_type == MainAgentOutputType.SIMPLE_ANSWER
        assert "<thinking>" in result.content


class TestReviewerParser:
    """Test ReviewerParser"""

    def test_parse_pass(self) -> None:
        """Test parsing pass result"""
        text = """[Pass]
Code meets architecture and quality requirements, ready for Bash testing.
(Optional) Note: Implementation is clear, tests are complete."""
        result = parse_reviewer_output(text)

        assert result.result_type == ReviewerResultType.PASS
        assert "Bash testing" in result.message
        assert len(result.issues) == 0

    def test_parse_reject(self) -> None:
        """Test parsing reject result"""
        text = """[Reject]
1. [architecture] /src/module.py:42 - Module boundary violated; Suggestion: Move logic to a separate module
2. [quality] /src/utils.py:100 - Missing type hints; Suggestion: Add parameter and return type hints
3. [style] /src/main.py:15 - Line too long; Suggestion: Split into multiple lines"""
        result = parse_reviewer_output(text)

        assert result.result_type == ReviewerResultType.REJECT
        assert len(result.issues) == 3

        assert result.issues[0].category == "architecture"
        assert result.issues[0].file_path == "/src/module.py"
        assert result.issues[0].line_number == 42
        assert "Module boundary" in result.issues[0].description
        assert "separate module" in result.issues[0].suggestion

        assert result.issues[1].category == "quality"
        assert result.issues[1].file_path == "/src/utils.py"
        assert result.issues[1].line_number == 100

    def test_parse_reject_with_dash_line(self) -> None:
        """Test parsing reject with dash line number"""
        text = """[Reject]
1. [style] /src/config.py:- - Config items not grouped; Suggestion: Group by function"""
        result = parse_reviewer_output(text)

        assert result.result_type == ReviewerResultType.REJECT
        assert len(result.issues) == 1
        assert result.issues[0].line_number is None

    def test_parse_unknown(self) -> None:
        """Test parsing unknown format"""
        text = "The code looks fine."
        result = parse_reviewer_output(text)

        assert result.result_type == ReviewerResultType.UNKNOWN
        assert result.raw_text == text


class TestQualityReportParser:
    """Test QualityReportParser"""

    def test_parse_full_report(self) -> None:
        """Test parsing full quality report"""
        text = """# Quality Report
## Tests
All passed

## Type Check
No errors

## Code Style
No issues

## Coverage
Met (>=80%)

## Other
None"""
        result = parse_quality_report(text)

        assert result.test_result == "All passed"
        assert result.type_check == "No errors"
        assert result.code_style == "No issues"
        assert result.coverage == "Met (>=80%)"
        assert result.other == "None"

    def test_parse_report_with_bracket_marker(self) -> None:
        """Test parsing report with [Quality Report] marker"""
        text = """[Quality Report]
## Tests
All passed

## Type Check
No errors

## Code Style
No issues

## Coverage
Met (>=80%)

## Other
None"""
        result = parse_quality_report(text)
        assert result.test_result == "All passed"
        assert result.type_check == "No errors"

    def test_parse_partial_report(self) -> None:
        """Test parsing partial report"""
        text = """# Quality Report
## Tests
Failed: test_auth.py::test_login

## Type Check
Errors: 5 type mismatches

## Other
Timeout 30s"""
        result = parse_quality_report(text)

        assert result.test_result == "Failed: test_auth.py::test_login"
        assert result.type_check == "Errors: 5 type mismatches"
        assert result.code_style == "Not run"
        assert result.coverage == "Not run"
        assert result.other == "Timeout 30s"

    def test_parse_unknown(self) -> None:
        """Test parsing unknown format"""
        text = "Tests passed."
        result = parse_quality_report(text)

        assert result.test_result == "Not run"
        assert result.type_check == "Not run"
        assert result.raw_text == text


class TestIntegration:
    """Integration tests for parser functions"""

    def test_main_agent_workflow(self) -> None:
        """Test main agent workflow simulation"""
        simple = parse_main_agent_output("[Simple Answer]\nHello! How can I help?")
        assert simple.output_type == MainAgentOutputType.SIMPLE_ANSWER

        complex_task = parse_main_agent_output("""[Complex Task]
Problem type: Feature development
Sub-questions:
1. Explore auth module → Assign to: EXPLORER
2. Design OAuth integration → Assign to: PLANNER
3. Implement OAuth → Assign to: CODER
4. Review code → Assign to: REVIEWER
5. Run tests → Assign to: BASH""")
        assert complex_task.output_type == MainAgentOutputType.COMPLEX_TASK
        assert len(complex_task.subtasks) == 5

    def test_reviewer_workflow(self) -> None:
        """Test reviewer workflow simulation"""
        pass_result = parse_reviewer_output("[Pass]\nCode meets requirements.")
        assert pass_result.result_type == ReviewerResultType.PASS

        reject_result = parse_reviewer_output("""[Reject]
1. [quality] /src/auth.py:50 - Password not encrypted; Suggestion: Use bcrypt""")
        assert reject_result.result_type == ReviewerResultType.REJECT
        assert len(reject_result.issues) == 1

    def test_bash_workflow(self) -> None:
        """Test bash agent workflow simulation"""
        report = parse_quality_report("""# Quality Report
## Tests
All passed

## Type Check
No errors

## Code Style
No issues

## Coverage
Met (>=80%)""")
        assert report.test_result == "All passed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
