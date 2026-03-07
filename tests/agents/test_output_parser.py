"""Tests for output_parser.py"""

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
        text = """【简单回答】
这是一个简单的回答内容。"""
        result = parse_main_agent_output(text)

        assert result.output_type == MainAgentOutputType.SIMPLE_ANSWER
        assert result.content == "这是一个简单的回答内容。"
        assert result.problem_type is None
        assert len(result.subtasks) == 0

    def test_parse_complex_task(self) -> None:
        """Test parsing complex task"""
        text = """【复杂任务】
问题类型：代码实现
拆解子问题：
1. 探索现有代码结构 → 交由：EXPLORER
2. 规划实现方案 → 交由：PLANNER
3. 实现核心功能 → 交由：CODER"""
        result = parse_main_agent_output(text)

        assert result.output_type == MainAgentOutputType.COMPLEX_TASK
        assert result.problem_type == "代码实现"
        assert len(result.subtasks) == 3
        assert result.subtasks[0].description == "探索现有代码结构"
        assert result.subtasks[0].agent == "EXPLORER"
        assert result.subtasks[1].description == "规划实现方案"
        assert result.subtasks[1].agent == "PLANNER"
        assert result.subtasks[2].description == "实现核心功能"
        assert result.subtasks[2].agent == "CODER"

    def test_parse_complex_task_with_colon_variant(self) -> None:
        """Test parsing complex task with colon variant"""
        text = """【复杂任务】
问题类型: Bug修复
拆解子问题:
1. 定位问题代码 → 交由: EXPLORER
2. 修复 Bug → 交由: CODER"""
        result = parse_main_agent_output(text)

        assert result.output_type == MainAgentOutputType.COMPLEX_TASK
        assert result.problem_type == "Bug修复"
        assert len(result.subtasks) == 2

    def test_parse_cannot_handle(self) -> None:
        """Test parsing cannot handle"""
        text = """【无法处理】
该任务需要外部 API 访问权限，当前环境不支持。"""
        result = parse_main_agent_output(text)

        assert result.output_type == MainAgentOutputType.CANNOT_HANDLE
        assert result.content == "该任务需要外部 API 访问权限，当前环境不支持。"

    def test_parse_unknown(self) -> None:
        """Test parsing unknown format"""
        text = "这是一段普通的文本，不符合任何格式。"
        result = parse_main_agent_output(text)

        assert result.output_type == MainAgentOutputType.UNKNOWN
        assert result.raw_text == text

    def test_parse_with_thinking_tags(self) -> None:
        """Test that thinking tags are preserved in content"""
        text = """【简单回答】
<thinking>这是推理过程</thinking>
这是最终答案。"""
        result = parse_main_agent_output(text)

        assert result.output_type == MainAgentOutputType.SIMPLE_ANSWER
        assert "<thinking>" in result.content


class TestReviewerParser:
    """Test ReviewerParser"""

    def test_parse_pass(self) -> None:
        """Test parsing pass result"""
        text = """[Pass]
代码符合架构与质量要求，可进入 Bash 测试阶段。
（可选）简要说明：实现清晰，测试覆盖完整。"""
        result = parse_reviewer_output(text)

        assert result.result_type == ReviewerResultType.PASS
        assert "可进入 Bash 测试阶段" in result.message
        assert len(result.issues) == 0

    def test_parse_reject(self) -> None:
        """Test parsing reject result"""
        text = """[Reject]
1. [架构] /src/module.py:42 - 未遵循模块边界；建议：将逻辑移至独立模块
2. [质量] /src/utils.py:100 - 缺少类型注解；建议：添加参数和返回值类型注解
3. [风格] /src/main.py:15 - 行过长；建议：拆分为多行"""
        result = parse_reviewer_output(text)

        assert result.result_type == ReviewerResultType.REJECT
        assert len(result.issues) == 3

        # 检查第一个问题
        assert result.issues[0].category == "架构"
        assert result.issues[0].file_path == "/src/module.py"
        assert result.issues[0].line_number == 42
        assert "未遵循模块边界" in result.issues[0].description
        assert "将逻辑移至独立模块" in result.issues[0].suggestion

        # 检查第二个问题
        assert result.issues[1].category == "质量"
        assert result.issues[1].file_path == "/src/utils.py"
        assert result.issues[1].line_number == 100

    def test_parse_reject_with_dash_line(self) -> None:
        """Test parsing reject with dash line number"""
        text = """[Reject]
1. [风格] /src/config.py:- - 配置项未分类；建议：按功能分组"""
        result = parse_reviewer_output(text)

        assert result.result_type == ReviewerResultType.REJECT
        assert len(result.issues) == 1
        assert result.issues[0].line_number is None

    def test_parse_unknown(self) -> None:
        """Test parsing unknown format"""
        text = "这段代码看起来还行。"
        result = parse_reviewer_output(text)

        assert result.result_type == ReviewerResultType.UNKNOWN
        assert result.raw_text == text


class TestQualityReportParser:
    """Test QualityReportParser"""

    def test_parse_full_report(self) -> None:
        """Test parsing full quality report"""
        text = """【质量报告】
## 测试结果
全部通过

## 类型检查
无错误

## 代码风格
无问题

## 覆盖率
满足要求(>=80%)

## 其他
无"""
        result = parse_quality_report(text)

        assert result.test_result == "全部通过"
        assert result.type_check == "无错误"
        assert result.code_style == "无问题"
        assert result.coverage == "满足要求(>=80%)"
        assert result.other == "无"

    def test_parse_partial_report(self) -> None:
        """Test parsing partial report"""
        text = """【质量报告】
## 测试结果
失败：test_auth.py::test_login

## 类型检查
有错误：5 处类型不匹配

## 其他
超时 30 秒"""
        result = parse_quality_report(text)

        assert result.test_result == "失败：test_auth.py::test_login"
        assert result.type_check == "有错误：5 处类型不匹配"
        assert result.code_style == "未执行"
        assert result.coverage == "未执行"
        assert result.other == "超时 30 秒"

    def test_parse_unknown(self) -> None:
        """Test parsing unknown format"""
        text = "测试通过了。"
        result = parse_quality_report(text)

        assert result.test_result == "未执行"  # Default values
        assert result.type_check == "未执行"
        assert result.raw_text == text


class TestIntegration:
    """Integration tests for parser functions"""

    def test_main_agent_workflow(self) -> None:
        """Test main agent workflow simulation"""
        # 用户提问 -> 简单回答
        simple = parse_main_agent_output("【简单回答】\n你好！有什么可以帮助你的？")
        assert simple.output_type == MainAgentOutputType.SIMPLE_ANSWER

        # 复杂任务拆解
        complex_task = parse_main_agent_output("""【复杂任务】
问题类型：功能开发
拆解子问题：
1. 探索现有认证模块 → 交由：EXPLORER
2. 设计 OAuth 集成方案 → 交由：PLANNER
3. 实现 OAuth 认证 → 交由：CODER
4. 代码评审 → 交由：REVIEWER
5. 运行测试 → 交由：BASH""")
        assert complex_task.output_type == MainAgentOutputType.COMPLEX_TASK
        assert len(complex_task.subtasks) == 5

    def test_reviewer_workflow(self) -> None:
        """Test reviewer workflow simulation"""
        # 评审通过
        pass_result = parse_reviewer_output("[Pass]\n代码符合要求。")
        assert pass_result.result_type == ReviewerResultType.PASS

        # 评审拒绝
        reject_result = parse_reviewer_output("""[Reject]
1. [质量] /src/auth.py:50 - 密码未加密存储；建议：使用 bcrypt 加密""")
        assert reject_result.result_type == ReviewerResultType.REJECT
        assert len(reject_result.issues) == 1

    def test_bash_workflow(self) -> None:
        """Test bash agent workflow simulation"""
        report = parse_quality_report("""【质量报告】
## 测试结果
全部通过

## 类型检查
无错误

## 代码风格
无问题

## 覆盖率
满足要求(>=80%)""")
        assert report.test_result == "全部通过"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])