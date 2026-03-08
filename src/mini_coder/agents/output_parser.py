"""Structured output parser.

Parses structured output from agents:

Main Agent:
- [Simple Answer] <content>
- [Complex Task] ... structured ...
- [Cannot Handle] <reason>

Unified Planner-Orchestrator (四类决策):
- [Simple Answer] / [Direct Dispatch] / [Complex Task] / [Cannot Handle]

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


# ----------------------------- Unified Planner-Orchestrator 四类输出 ------------------------------


class UnifiedOutputType(Enum):
    """统一 Planner-Orchestrator 输出类型。"""
    SIMPLE_ANSWER = "simple_answer"
    DIRECT_DISPATCH = "direct_dispatch"
    COMPLEX_TASK = "complex_task"
    CANNOT_HANDLE = "cannot_handle"
    UNKNOWN = "unknown"


@dataclass
class DirectDispatchOutput:
    """直接派发：单个 Agent + Task + 可选 Params。"""
    agent: str
    task: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StepWithParams:
    """复杂任务中的一步：Agent + Task + 可选 Params。"""
    agent: str
    task: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UnifiedOutput:
    """统一 Planner-Orchestrator 解析结果。"""
    output_type: UnifiedOutputType
    content: Optional[str] = None
    direct_dispatch: Optional[DirectDispatchOutput] = None
    problem_type: Optional[str] = None
    implementation_plan: Optional[str] = None
    steps: List[StepWithParams] = field(default_factory=list)
    raw_text: str = ""


class UnifiedParser:
    """解析统一 Agent 的四类输出。"""

    SIMPLE_ANSWER_PATTERN = re.compile(r'^\[Simple Answer\]\s*\n?(.*)', re.DOTALL)
    CANNOT_HANDLE_PATTERN = re.compile(r'^\[Cannot Handle\]\s*\n?(.*)', re.DOTALL)

    # [Direct Dispatch]\nAgent: X\nTask: ...\nParams:\nkey: value
    DIRECT_DISPATCH_HEAD = re.compile(r'^\[Direct Dispatch\]\s*\n', re.IGNORECASE)
    AGENT_LINE = re.compile(r'^Agent[：:]\s*(.+)$', re.MULTILINE)
    TASK_LINE = re.compile(r'^Task[：:]\s*(.+?)(?=\n(?:Params|Agent|$))', re.DOTALL | re.MULTILINE)
    PARAMS_BLOCK = re.compile(r'^Params[：:]\s*\n([\s\S]*?)(?=\n\n|\n\d+\.\s+Agent|\Z)', re.MULTILINE)

    # [Complex Task]\nProblem type: ...\nImplementation plan (optional): ...\nSteps:\n1. Agent: ...
    COMPLEX_HEAD = re.compile(r'^\[Complex Task\]\s*\n', re.IGNORECASE)
    PROBLEM_TYPE_LINE = re.compile(r'^Problem type[：:]\s*(.+)$', re.MULTILINE)
    STEP_ENTRY = re.compile(
        r'^\s*(\d+)[.、．]\s*Agent[：:]\s*([A-Z_]+)\s*\n\s*Task[：:]\s*(.+?)(?=\n\d+[.、．]\s*Agent|\n\s*Params:|\Z)',
        re.DOTALL | re.MULTILINE
    )
    STEP_PARAMS = re.compile(r'\s*Params[：:]\s*\n([\s\S]*?)(?=\n\d+[.、．]|\Z)', re.MULTILINE)

    def parse(self, text: str) -> UnifiedOutput:
        """解析统一 Agent 输出，返回四类之一。"""
        text = text.strip()
        # 去掉 <thinking>...</thinking> 再解析
        thinking_end = text.rfind("</thinking>")
        if thinking_end != -1:
            text = text[thinking_end + len("</thinking>"):].strip()

        # 1. [Simple Answer]
        m = self.SIMPLE_ANSWER_PATTERN.match(text)
        if m:
            return UnifiedOutput(
                output_type=UnifiedOutputType.SIMPLE_ANSWER,
                content=m.group(1).strip(),
                raw_text=text
            )

        # 2. [Cannot Handle]
        m = self.CANNOT_HANDLE_PATTERN.match(text)
        if m:
            return UnifiedOutput(
                output_type=UnifiedOutputType.CANNOT_HANDLE,
                content=m.group(1).strip(),
                raw_text=text
            )

        # 3. [Direct Dispatch]
        if self.DIRECT_DISPATCH_HEAD.match(text):
            body = text[text.find("]") + 1:].strip()
            agent = ""
            task = ""
            params: Dict[str, Any] = {}
            am = self.AGENT_LINE.search(body)
            if am:
                agent = am.group(1).strip().upper()
            task_m = re.search(r'Task[：:]\s*(.+?)(?=\nParams[：:]|\n\s*$|\Z)', body, re.DOTALL)
            if task_m:
                task = task_m.group(1).strip()
            params_m = self.PARAMS_BLOCK.search(body)
            if params_m:
                for line in params_m.group(1).strip().split("\n"):
                    if ":" in line or "：" in line:
                        k, _, v = line.partition(":")
                        if not v and "：" in line:
                            k, _, v = line.partition("：")
                        if k and v is not None:
                            params[k.strip()] = v.strip()
            if agent:
                return UnifiedOutput(
                    output_type=UnifiedOutputType.DIRECT_DISPATCH,
                    direct_dispatch=DirectDispatchOutput(agent=agent, task=task or body[:500], params=params),
                    raw_text=text
                )

        # 4. [Complex Task]
        if self.COMPLEX_HEAD.match(text):
            rest = text[text.find("]") + 1:].strip()
            problem_type = ""
            impl_plan = ""
            steps: List[StepWithParams] = []
            pt = self.PROBLEM_TYPE_LINE.search(rest)
            if pt:
                problem_type = pt.group(1).strip()
            # Steps: 后的 1. Agent: ... 2. Agent: ...
            steps_start = rest.find("Steps:")
            if steps_start == -1:
                steps_start = rest.find("Steps：")
            if steps_start != -1:
                steps_text = rest[steps_start + 6:].strip()
                for entry in self.STEP_ENTRY.finditer(steps_text):
                    step_agent = entry.group(2).strip().upper()
                    step_task = entry.group(3).strip()
                    step_params: Dict[str, Any] = {}
                    sp = self.STEP_PARAMS.search(steps_text[entry.end():])
                    if sp:
                        for line in sp.group(1).strip().split("\n"):
                            if ":" in line or "：" in line:
                                k, _, v = line.partition(":")
                                if not v and "：" in line:
                                    k, _, v = line.partition("：")
                                if k and v is not None:
                                    step_params[k.strip()] = v.strip()
                    steps.append(StepWithParams(agent=step_agent, task=step_task, params=step_params))
            if steps or problem_type:
                return UnifiedOutput(
                    output_type=UnifiedOutputType.COMPLEX_TASK,
                    problem_type=problem_type or None,
                    implementation_plan=impl_plan or None,
                    steps=steps,
                    raw_text=text
                )

        logger.warning("Failed to parse unified output: %s...", text[:150])
        return UnifiedOutput(output_type=UnifiedOutputType.UNKNOWN, raw_text=text)


def parse_unified_output(text: str) -> UnifiedOutput:
    """解析统一 Planner-Orchestrator 输出。"""
    return UnifiedParser().parse(text)


# ----------------------------- Main Agent (legacy) ------------------------------


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
