"""Structured Output Parser - 结构化输出解析器

解析各 Agent 的结构化输出格式：

Main Agent:
- 【简单回答】<content>
- 【复杂任务】...structured...
- 【无法处理】<reason>

Reviewer Agent:
- [Pass] ...
- [Reject] ...numbered issues...

Bash Agent:
- 【质量报告】...structured sections...
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
import re
import logging

logger = logging.getLogger(__name__)


class MainAgentOutputType(Enum):
    """主代理输出类型"""
    SIMPLE_ANSWER = "simple_answer"      # 【简单回答】
    COMPLEX_TASK = "complex_task"         # 【复杂任务】
    CANNOT_HANDLE = "cannot_handle"       # 【无法处理】
    UNKNOWN = "unknown"                   # 无法解析


class ReviewerResultType(Enum):
    """Reviewer 结果类型"""
    PASS = "pass"
    REJECT = "reject"
    UNKNOWN = "unknown"


@dataclass
class SubTask:
    """子任务"""
    description: str
    agent: str


@dataclass
class MainAgentOutput:
    """主代理结构化输出"""
    output_type: MainAgentOutputType
    content: Optional[str] = None          # 用于简单回答/无法处理
    problem_type: Optional[str] = None     # 用于复杂任务
    subtasks: List[SubTask] = field(default_factory=list)  # 子任务列表
    raw_text: str = ""


@dataclass
class ReviewerIssue:
    """Reviewer 问题项"""
    category: str       # 架构|质量|风格
    file_path: str
    line_number: Optional[int]
    description: str
    suggestion: str
    raw_line: str = ""


@dataclass
class ReviewerOutput:
    """Reviewer 结构化输出"""
    result_type: ReviewerResultType
    message: str = ""
    issues: List[ReviewerIssue] = field(default_factory=list)
    raw_text: str = ""


@dataclass
class QualityReport:
    """Bash Agent 质量报告"""
    test_result: str = "未执行"
    type_check: str = "未执行"
    code_style: str = "未执行"
    coverage: str = "未执行"
    other: str = ""
    raw_text: str = ""


class MainAgentParser:
    """主代理输出解析器

    解析格式：
    【简单回答】
    <内容>

    【复杂任务】
    问题类型：<类型>
    拆解子问题：
    1. <子问题> → 交由：<代理名>
    ...

    【无法处理】
    <原因>
    """

    # 正则模式
    SIMPLE_ANSWER_PATTERN = re.compile(r'^【简单回答】\s*\n?(.*)', re.DOTALL)
    COMPLEX_TASK_PATTERN = re.compile(
        r'^【复杂任务】\s*\n'
        r'问题类型[：:]\s*(.+?)\s*\n'
        r'拆解子问题[：:]?\s*\n'
        r'(.+)',
        re.DOTALL
    )
    CANNOT_HANDLE_PATTERN = re.compile(r'^【无法处理】\s*\n?(.*)', re.DOTALL)
    SUBTASK_PATTERN = re.compile(
        r'^\s*(\d+)[.、．]\s*(.+?)\s*(?:→|->)\s*交由[：:]\s*([A-Z_]+)',
        re.MULTILINE
    )

    def parse(self, text: str) -> MainAgentOutput:
        """解析主代理输出

        Args:
            text: 原始输出文本

        Returns:
            MainAgentOutput: 解析结果
        """
        text = text.strip()

        # 尝试匹配【简单回答】
        match = self.SIMPLE_ANSWER_PATTERN.match(text)
        if match:
            content = match.group(1).strip()
            logger.debug(f"Parsed SIMPLE_ANSWER: {content[:50]}...")
            return MainAgentOutput(
                output_type=MainAgentOutputType.SIMPLE_ANSWER,
                content=content,
                raw_text=text
            )

        # 尝试匹配【复杂任务】
        match = self.COMPLEX_TASK_PATTERN.match(text)
        if match:
            problem_type = match.group(1).strip()
            subtasks_text = match.group(2).strip()

            # 解析子任务
            subtasks = []
            for m in self.SUBTASK_PATTERN.finditer(subtasks_text):
                subtasks.append(SubTask(
                    description=m.group(2).strip(),
                    agent=m.group(3).strip()
                ))

            logger.debug(f"Parsed COMPLEX_TASK: type={problem_type}, subtasks={len(subtasks)}")
            return MainAgentOutput(
                output_type=MainAgentOutputType.COMPLEX_TASK,
                problem_type=problem_type,
                subtasks=subtasks,
                raw_text=text
            )

        # 尝试匹配【无法处理】
        match = self.CANNOT_HANDLE_PATTERN.match(text)
        if match:
            reason = match.group(1).strip()
            logger.debug(f"Parsed CANNOT_HANDLE: {reason[:50]}...")
            return MainAgentOutput(
                output_type=MainAgentOutputType.CANNOT_HANDLE,
                content=reason,
                raw_text=text
            )

        # 无法解析，返回 UNKNOWN
        logger.warning(f"Failed to parse main agent output: {text[:100]}...")
        return MainAgentOutput(
            output_type=MainAgentOutputType.UNKNOWN,
            raw_text=text
        )


class ReviewerParser:
    """Reviewer 输出解析器

    解析格式：
    [Pass]
    代码符合架构与质量要求，可进入 Bash 测试阶段。
    （可选）简要说明：<一句话>

    [Reject]
    1. [架构|质量|风格] <文件绝对路径>:<行号> - <问题描述>；建议：<修复建议>
    2. ...
    """

    PASS_PATTERN = re.compile(r'^\[Pass\]\s*\n?(.*)', re.DOTALL)
    REJECT_PATTERN = re.compile(r'^\[Reject\]\s*\n(.+)', re.DOTALL)
    ISSUE_PATTERN = re.compile(
        r'^\s*(\d+)[.、．]\s*\[(架构|质量|风格)\]\s*'
        r'(.+?):(\d+|-)\s*[-－]\s*(.+?)\s*[；;]\s*建议[：:]\s*(.+)$',
        re.MULTILINE
    )

    def parse(self, text: str) -> ReviewerOutput:
        """解析 Reviewer 输出

        Args:
            text: 原始输出文本

        Returns:
            ReviewerOutput: 解析结果
        """
        text = text.strip()

        # 尝试匹配 [Pass]
        match = self.PASS_PATTERN.match(text)
        if match:
            message = match.group(1).strip()
            logger.debug(f"Parsed PASS: {message[:50]}...")
            return ReviewerOutput(
                result_type=ReviewerResultType.PASS,
                message=message,
                raw_text=text
            )

        # 尝试匹配 [Reject]
        match = self.REJECT_PATTERN.match(text)
        if match:
            issues_text = match.group(1).strip()

            # 解析问题列表
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

            logger.debug(f"Parsed REJECT: {len(issues)} issues")
            return ReviewerOutput(
                result_type=ReviewerResultType.REJECT,
                issues=issues,
                raw_text=text
            )

        # 无法解析
        logger.warning(f"Failed to parse reviewer output: {text[:100]}...")
        return ReviewerOutput(
            result_type=ReviewerResultType.UNKNOWN,
            raw_text=text
        )


class QualityReportParser:
    """Bash Agent 质量报告解析器

    解析格式：
    【质量报告】
    ## 测试结果
    <内容>

    ## 类型检查
    <内容>

    ## 代码风格
    <内容>

    ## 覆盖率
    <内容>

    ## 其他
    <内容>
    """

    REPORT_PATTERN = re.compile(
        r'^【质量报告】\s*\n(.+)',
        re.DOTALL
    )

    SECTION_PATTERN = re.compile(
        r'##\s*(测试结果|类型检查|代码风格|覆盖率|其他)\s*\n([^\x00]+?)(?=##\s*|$)',
        re.DOTALL
    )

    def parse(self, text: str) -> QualityReport:
        """解析质量报告

        Args:
            text: 原始输出文本

        Returns:
            QualityReport: 解析结果
        """
        text = text.strip()

        # 尝试匹配【质量报告】
        match = self.REPORT_PATTERN.match(text)
        if match:
            report_text = match.group(1).strip()

            # 解析各部分
            report = QualityReport(raw_text=text)

            for m in self.SECTION_PATTERN.finditer(report_text):
                section_name = m.group(1)
                section_content = m.group(2).strip()

                if section_name == "测试结果":
                    report.test_result = section_content
                elif section_name == "类型检查":
                    report.type_check = section_content
                elif section_name == "代码风格":
                    report.code_style = section_content
                elif section_name == "覆盖率":
                    report.coverage = section_content
                elif section_name == "其他":
                    report.other = section_content

            logger.debug(f"Parsed QUALITY_REPORT: test={report.test_result[:30] if report.test_result else 'N/A'}...")
            return report

        # 无法解析，返回默认报告
        logger.warning(f"Failed to parse quality report: {text[:100]}...")
        return QualityReport(raw_text=text)


def parse_main_agent_output(text: str) -> MainAgentOutput:
    """便捷函数：解析主代理输出"""
    return MainAgentParser().parse(text)


def parse_reviewer_output(text: str) -> ReviewerOutput:
    """便捷函数：解析 Reviewer 输出"""
    return ReviewerParser().parse(text)


def parse_quality_report(text: str) -> QualityReport:
    """便捷函数：解析质量报告"""
    return QualityReportParser().parse(text)