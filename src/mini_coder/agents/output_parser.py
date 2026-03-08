"""Structured output parser.

Parses structured output from agents:

Main Agent:
- [Simple Answer] <content>
- [Complex Task] ... structured ...
- [Cannot Handle] <reason>

Reviewer Agent:
- [Pass] ...
- [Reject] ... numbered issues ...

Bash Agent:
- [Quality Report] or # Quality Report ... ## Tests, ## Type Check, etc.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
import re
import logging

logger = logging.getLogger(__name__)


class MainAgentOutputType(Enum):
    """Main agent output type."""
    SIMPLE_ANSWER = "simple_answer"
    COMPLEX_TASK = "complex_task"
    CANNOT_HANDLE = "cannot_handle"
    UNKNOWN = "unknown"


class ReviewerResultType(Enum):
    """Reviewer result type."""
    PASS = "pass"
    REJECT = "reject"
    UNKNOWN = "unknown"


@dataclass
class SubTask:
    """Sub-task with assigned agent."""
    description: str
    agent: str


@dataclass
class MainAgentOutput:
    """Parsed main agent structured output."""
    output_type: MainAgentOutputType
    content: Optional[str] = None
    problem_type: Optional[str] = None
    subtasks: List[SubTask] = field(default_factory=list)
    raw_text: str = ""


@dataclass
class ReviewerIssue:
    """Single Reviewer issue (architecture|quality|style)."""
    category: str
    file_path: str
    line_number: Optional[int]
    description: str
    suggestion: str
    raw_line: str = ""


@dataclass
class ReviewerOutput:
    """Parsed Reviewer structured output."""
    result_type: ReviewerResultType
    message: str = ""
    issues: List[ReviewerIssue] = field(default_factory=list)
    raw_text: str = ""


@dataclass
class QualityReport:
    """Bash agent quality report (parsed sections)."""
    test_result: str = "Not run"
    type_check: str = "Not run"
    code_style: str = "Not run"
    coverage: str = "Not run"
    other: str = ""
    raw_text: str = ""


class MainAgentParser:
    """Parser for main agent output.

    Expected format:
    [Simple Answer]
    <content>

    [Complex Task]
    Problem type: <type>
    Sub-questions:
    1. <sub-question> → Assign to: <AGENT_NAME>
    ...

    [Cannot Handle]
    <reason>
    """

    SIMPLE_ANSWER_PATTERN = re.compile(r'^\[Simple Answer\]\s*\n?(.*)', re.DOTALL)
    COMPLEX_TASK_PATTERN = re.compile(
        r'^\[Complex Task\]\s*\n'
        r'Problem type[：:]\s*(.+?)\s*\n'
        r'Sub-questions[：:]?\s*\n'
        r'(.+)',
        re.DOTALL
    )
    CANNOT_HANDLE_PATTERN = re.compile(r'^\[Cannot Handle\]\s*\n?(.*)', re.DOTALL)
    SUBTASK_PATTERN = re.compile(
        r'^\s*(\d+)[.、．]\s*(.+?)\s*(?:→|->)\s*Assign to[：:]\s*([A-Z_]+)',
        re.MULTILINE
    )

    def parse(self, text: str) -> MainAgentOutput:
        """Parse main agent output."""
        text = text.strip()

        match = self.SIMPLE_ANSWER_PATTERN.match(text)
        if match:
            content = match.group(1).strip()
            logger.debug("Parsed SIMPLE_ANSWER: %s...", content[:50])
            return MainAgentOutput(
                output_type=MainAgentOutputType.SIMPLE_ANSWER,
                content=content,
                raw_text=text
            )

        match = self.COMPLEX_TASK_PATTERN.match(text)
        if match:
            problem_type = match.group(1).strip()
            subtasks_text = match.group(2).strip()
            subtasks = []
            for m in self.SUBTASK_PATTERN.finditer(subtasks_text):
                subtasks.append(SubTask(
                    description=m.group(2).strip(),
                    agent=m.group(3).strip()
                ))
            logger.debug("Parsed COMPLEX_TASK: type=%s, subtasks=%d", problem_type, len(subtasks))
            return MainAgentOutput(
                output_type=MainAgentOutputType.COMPLEX_TASK,
                problem_type=problem_type,
                subtasks=subtasks,
                raw_text=text
            )

        match = self.CANNOT_HANDLE_PATTERN.match(text)
        if match:
            reason = match.group(1).strip()
            logger.debug("Parsed CANNOT_HANDLE: %s...", reason[:50])
            return MainAgentOutput(
                output_type=MainAgentOutputType.CANNOT_HANDLE,
                content=reason,
                raw_text=text
            )

        logger.warning("Failed to parse main agent output: %s...", text[:100])
        return MainAgentOutput(
            output_type=MainAgentOutputType.UNKNOWN,
            raw_text=text
        )


class ReviewerParser:
    """Parser for Reviewer output.

    [Pass]
    <optional message>

    [Reject]
    1. [architecture|quality|style] <file>:<line> - <description>; Suggestion: <suggestion>
    2. ...
    """

    PASS_PATTERN = re.compile(r'^\[Pass\]\s*\n?(.*)', re.DOTALL)
    REJECT_PATTERN = re.compile(r'^\[Reject\]\s*\n(.+)', re.DOTALL)
    ISSUE_PATTERN = re.compile(
        r'^\s*(\d+)[.、．]\s*\[(architecture|quality|style)\]\s*'
        r'(.+?):(\d+|-)\s*[-－]\s*(.+?)\s*[；;]\s*Suggestion[：:]\s*(.+)$',
        re.MULTILINE
    )

    def parse(self, text: str) -> ReviewerOutput:
        """Parse Reviewer output."""
        text = text.strip()

        match = self.PASS_PATTERN.match(text)
        if match:
            message = match.group(1).strip()
            logger.debug("Parsed PASS: %s...", message[:50])
            return ReviewerOutput(
                result_type=ReviewerResultType.PASS,
                message=message,
                raw_text=text
            )

        match = self.REJECT_PATTERN.match(text)
        if match:
            issues_text = match.group(1).strip()
            issues = []
            for m in self.ISSUE_PATTERN.finditer(issues_text):
                line_num_str = m.group(4)
                line_num = int(line_num_str) if line_num_str != '-' else None
                issues.append(ReviewerIssue(
                    category=m.group(2),
                    file_path=m.group(3),
                    line_number=line_num,
                    description=m.group(5).strip(),
                    suggestion=m.group(6).strip(),
                    raw_line=m.group(0)
                ))
            logger.debug("Parsed REJECT: %d issues", len(issues))
            return ReviewerOutput(
                result_type=ReviewerResultType.REJECT,
                issues=issues,
                raw_text=text
            )

        logger.warning("Failed to parse reviewer output: %s...", text[:100])
        return ReviewerOutput(
            result_type=ReviewerResultType.UNKNOWN,
            raw_text=text
        )


class QualityReportParser:
    """Parser for Bash agent quality report.

    Accepts either:
    [Quality Report]
    or
    # Quality Report

    Sections: ## Tests, ## Type Check, ## Code Style, ## Coverage, ## Other
    """

    REPORT_PATTERN = re.compile(
        r'^(?:\[Quality Report\]|# Quality Report)\s*\n(.+)',
        re.DOTALL
    )
    SECTION_PATTERN = re.compile(
        r'##\s*(Tests|Type Check|Code Style|Coverage|Other)\s*\n([^\x00]+?)(?=##\s*|$)',
        re.DOTALL
    )

    def parse(self, text: str) -> QualityReport:
        """Parse quality report text."""
        text = text.strip()

        match = self.REPORT_PATTERN.match(text)
        if match:
            report_text = match.group(1).strip()
            report = QualityReport(raw_text=text)
            for m in self.SECTION_PATTERN.finditer(report_text):
                section_name = m.group(1)
                section_content = m.group(2).strip()
                if section_name == "Tests":
                    report.test_result = section_content
                elif section_name == "Type Check":
                    report.type_check = section_content
                elif section_name == "Code Style":
                    report.code_style = section_content
                elif section_name == "Coverage":
                    report.coverage = section_content
                elif section_name == "Other":
                    report.other = section_content
            logger.debug(
                "Parsed QUALITY_REPORT: test=%s...",
                report.test_result[:30] if report.test_result else "N/A"
            )
            return report

        logger.warning("Failed to parse quality report: %s...", text[:100])
        return QualityReport(raw_text=text)


def parse_main_agent_output(text: str) -> MainAgentOutput:
    """Parse main agent output."""
    return MainAgentParser().parse(text)


def parse_reviewer_output(text: str) -> ReviewerOutput:
    """Parse Reviewer output."""
    return ReviewerParser().parse(text)


def parse_quality_report(text: str) -> QualityReport:
    """Parse quality report."""
    return QualityReportParser().parse(text)
