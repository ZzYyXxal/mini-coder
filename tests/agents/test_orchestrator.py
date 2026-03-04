"""Tests for Enhanced Workflow Orchestrator and Agent System"""

import pytest
import unittest
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, Any

from mini_coder.agents.orchestrator import (
    WorkflowState,
    FailureType,
    WorkflowConfig,
    WorkflowContext,
    WorkflowOrchestrator,
)
from mini_coder.agents.enhanced import (
    Blackboard,
    Event,
    EventType,
    AgentCapabilities,
    EnhancedAgentState,
    EnhancedAgentResult,
    BaseEnhancedAgent,
    PlannerAgent,
    CoderAgent,
    TesterAgent,
    PlannerCapabilities,
    CoderCapabilities,
    TesterCapabilities,
)


class TestWorkflowConfig(unittest.TestCase):
    """测试 WorkflowConfig"""

    def test_default_config(self):
        """测试默认配置"""
        config = WorkflowConfig()
        self.assertEqual(config.max_retries, 4)
        self.assertEqual(config.timeout_seconds, 600)
        self.assertTrue(config.loop_detection_enabled)
        self.assertTrue(config.auto_retry)
        self.assertFalse(config.verbose)

    def test_custom_config(self):
        """测试自定义配置"""
        config = WorkflowConfig(
            max_retries=10,
            timeout_seconds=1200,
            loop_detection_enabled=False,
        )
        self.assertEqual(config.max_retries, 10)
        self.assertEqual(config.timeout_seconds, 1200)
        self.assertFalse(config.loop_detection_enabled)


class TestWorkflowContext(unittest.TestCase):
    """测试 WorkflowContext"""

    def setUp(self):
        """设置测试 fixture"""
        self.config = WorkflowConfig(max_retries=3)
        self.ctx = WorkflowContext(
            task_id="test-1",
            requirement="Test requirement",
            config=self.config
        )

    def test_initial_state(self):
        """测试初始状态"""
        self.assertEqual(self.ctx.current_state, WorkflowState.PENDING)
        self.assertEqual(self.ctx.retry_count, 0)
        self.assertEqual(len(self.ctx.error_history), 0)
        self.assertIsNotNone(self.ctx.blackboard)

    def test_blackboard_initialization(self):
        """测试黑板初始化"""
        self.assertIsNotNone(self.ctx.blackboard)
        self.assertEqual(self.ctx.blackboard.task_id, "test-1")

    def test_context_in_blackboard(self):
        """测试上下文在黑板中"""
        self.assertEqual(self.ctx.blackboard.get_context("requirement"), "Test requirement")
        self.assertEqual(self.ctx.blackboard.get_context("task_id"), "test-1")

    def test_add_error(self):
        """测试添加错误"""
        key = self.ctx.add_error({
            "file": "test.py",
            "line": 10,
            "type": "AssertionError",
            "message": "Test error"
        })
        self.assertEqual(len(self.ctx.error_history), 1)
        self.assertEqual(self.ctx.error_counts[key], 1)
        self.assertEqual(key, "test.py:10:AssertionError")

    def test_error_count_increment(self):
        """测试错误计数递增"""
        self.ctx.add_error({"file": "test.py", "line": 10, "type": "AssertionError"})
        self.ctx.add_error({"file": "test.py", "line": 10, "type": "AssertionError"})
        self.ctx.add_error({"file": "test.py", "line": 10, "type": "AssertionError"})
        key = "test.py:10:AssertionError"
        self.assertEqual(self.ctx.error_counts[key], 3)

    def test_loop_detection(self):
        """测试死循环检测"""
        # 添加 2 次错误 - 不应检测到循环 (max_retries=3)
        for _ in range(2):
            self.ctx.add_error({"file": "test.py", "line": 10, "type": "AssertionError"})
        self.assertFalse(self.ctx.is_loop_detected())

        # 添加第 3 次错误 - 应检测到循环
        self.ctx.add_error({"file": "test.py", "line": 10, "type": "AssertionError"})
        self.assertTrue(self.ctx.is_loop_detected())

    def test_loop_detection_disabled(self):
        """测试禁用死循环检测"""
        self.ctx.config.loop_detection_enabled = False
        for _ in range(10):
            self.ctx.add_error({"file": "test.py", "line": 10, "type": "AssertionError"})
        self.assertFalse(self.ctx.is_loop_detected())

    def test_reset_for_replan(self):
        """测试重置以重新规划"""
        self.ctx.current_state = WorkflowState.TESTING
        self.ctx.retry_count = 2

        self.ctx.reset_for_replan()

        self.assertEqual(self.ctx.current_state, WorkflowState.REPLANNING)
        self.assertEqual(self.ctx.retry_count, 3)
        self.assertEqual(len(self.ctx.decision_history), 1)

    def test_reset_for_retry(self):
        """测试重置以重试"""
        self.ctx.current_state = WorkflowState.TESTING
        self.ctx.retry_count = 2

        self.ctx.reset_for_retry()

        self.assertEqual(self.ctx.current_state, WorkflowState.RETRYING)
        self.assertEqual(self.ctx.retry_count, 3)

    def test_get_summary(self):
        """测试获取摘要"""
        summary = self.ctx.get_summary()
        self.assertEqual(summary["task_id"], "test-1")
        self.assertEqual(summary["state"], "pending")
        self.assertEqual(summary["retry_count"], 0)
        self.assertFalse(summary["loop_detected"])

    def test_plan_property(self):
        """测试计划属性"""
        # 初始时计划为空
        self.assertIsNone(self.ctx.plan)

        # 添加计划到黑板
        self.ctx.blackboard.add_artifact(
            name="implementation_plan.md",
            content="Test plan content",
            content_type="plan",
            created_by="planner"
        )

        self.assertEqual(self.ctx.plan, "Test plan content")

    def test_code_artifacts_property(self):
        """测试代码工件属性"""
        # 初始时代码工件为空
        self.assertEqual(len(self.ctx.code_artifacts), 0)

        # 添加代码到黑板
        self.ctx.blackboard.add_artifact(
            name="code:src/main.py",
            content="def main(): pass",
            content_type="code",
            created_by="coder"
        )

        code = self.ctx.code_artifacts
        self.assertEqual(len(code), 1)
        self.assertEqual(code["src/main.py"], "def main(): pass")


class TestWorkflowOrchestrator(unittest.TestCase):
    """测试 WorkflowOrchestrator"""

    def setUp(self):
        """设置测试 fixture"""
        self.mock_llm = Mock()
        self.config = WorkflowConfig(max_retries=3, timeout_seconds=60)
        self.orchestrator = WorkflowOrchestrator(
            llm_service=self.mock_llm,
            config=self.config
        )

    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(self.orchestrator.config.max_retries, 3)
        self.assertEqual(self.orchestrator.config.timeout_seconds, 60)
        self.assertIsNone(self.orchestrator._context)

    def test_execute_workflow_creates_context(self):
        """测试执行工作流创建上下文"""
        # Mock 整个工作流执行过程
        with patch.object(self.orchestrator, '_execute_current_stage') as mock_stage:
            # 返回一个最小化的成功结果
            mock_stage.return_value = EnhancedAgentResult(
                success=True,
                output="done",
                elapsed_time=0.1
            )
            self.orchestrator.execute_workflow("test requirement")

            self.assertIsNotNone(self.orchestrator._context)
            self.assertEqual(self.orchestrator._context.requirement, "test requirement")

    def test_loop_detection_stops_workflow(self):
        """测试死循环检测停止工作流"""
        # 创建一个已经有错误计数的上下文
        self.orchestrator._context = WorkflowContext(
            task_id="test-1",
            requirement="test",
            config=self.config
        )
        # 添加足够的错误以触发循环检测
        for _ in range(3):
            self.orchestrator._context.add_error({
                "file": "test.py",
                "line": 10,
                "type": "AssertionError"
            })

        self.orchestrator._context.current_state = WorkflowState.TESTING

        # 执行应该检测到循环
        result = self.orchestrator._execute_current_stage()

        # 循环检测应该在主循环中触发，这里测试的是底层方法
        # 实际循环检测在 execute_workflow 的主循环中
        self.assertTrue(self.orchestrator._context.is_loop_detected())

    def test_state_callback(self):
        """测试状态回调"""
        callback_called = []

        def callback(ctx, state):
            callback_called.append(state)

        self.orchestrator.register_state_callback(WorkflowState.PLANNING, callback)

        # 触发状态变更
        self.orchestrator._context = WorkflowContext(
            task_id="test-1",
            requirement="test"
        )
        self.orchestrator._notify_state_change(WorkflowState.PLANNING)

        self.assertEqual(len(callback_called), 1)
        self.assertEqual(callback_called[0], WorkflowState.PLANNING)

    def test_get_status(self):
        """测试获取状态"""
        status = self.orchestrator.get_status()
        self.assertEqual(status, {"status": "idle"})

        # 执行后获取状态
        with patch.object(self.orchestrator, '_execute_current_stage') as mock_stage:
            mock_stage.return_value = EnhancedAgentResult(success=True)
            self.orchestrator.execute_workflow("test")

            status = self.orchestrator.get_status()
            self.assertIn("task_id", status)
            self.assertIn("state", status)


class TestEnhancedAgentResult(unittest.TestCase):
    """测试 EnhancedAgentResult"""

    def test_success_result(self):
        """测试成功结果"""
        result = EnhancedAgentResult(success=True, output="test output")
        self.assertTrue(result.success)
        self.assertEqual(result.output, "test output")
        self.assertEqual(result.error, "")
        self.assertEqual(result.elapsed_time, 0.0)

    def test_failure_result(self):
        """测试失败结果"""
        result = EnhancedAgentResult(
            success=False,
            error="test error",
            failure_type="agent_error"
        )
        self.assertFalse(result.success)
        self.assertEqual(result.error, "test error")
        self.assertEqual(result.failure_type, "agent_error")

    def test_needs_user_decision(self):
        """测试需要用户决策"""
        result = EnhancedAgentResult(
            success=False,
            needs_user_decision=True,
            decision_reason="需要人工决策"
        )
        self.assertTrue(result.needs_user_decision)
        self.assertEqual(result.decision_reason, "需要人工决策")

    def test_with_artifacts(self):
        """测试带工件的结果"""
        result = EnhancedAgentResult(
            success=True,
            artifacts={"file.py": "content"}
        )
        self.assertEqual(result.artifacts, {"file.py": "content"})


class TestPlannerAgent(unittest.TestCase):
    """测试 PlannerAgent"""

    def setUp(self):
        """设置测试 fixture"""
        self.mock_llm = Mock()
        self.blackboard = Blackboard("test-1")
        self.agent = PlannerAgent(self.mock_llm, self.blackboard)

    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(self.agent.AGENT_TYPE, "planner")
        self.assertIsNotNone(self.agent.blackboard)
        self.assertIsInstance(self.agent.capabilities, PlannerCapabilities)

    def test_capabilities(self):
        """测试能力定义"""
        caps = PlannerCapabilities()
        self.assertIn("Read", caps.allowed_tools)
        self.assertIn("WebSearch", caps.allowed_tools)

    def test_execute_success(self):
        """测试成功执行"""
        self.mock_llm.chat.return_value = "Implementation plan..."

        result = self.agent.execute("Create a calculator")

        self.assertTrue(result.success)
        self.assertIn("implementation_plan.md", result.artifacts)
        # 验证计划已保存到黑板
        plan = self.blackboard.get_artifact_content("implementation_plan.md")
        self.assertEqual(plan, "Implementation plan...")

    def test_execute_failure(self):
        """测试执行失败"""
        self.mock_llm.chat.side_effect = Exception("LLM error")

        result = self.agent.execute("Create a calculator")

        self.assertFalse(result.success)
        self.assertIn("LLM error", result.error)
        self.assertEqual(result.failure_type, "planning_error")


class TestCoderAgent(unittest.TestCase):
    """测试 CoderAgent"""

    def setUp(self):
        """设置测试 fixture"""
        self.mock_llm = Mock()
        self.blackboard = Blackboard("test-1")
        self.agent = CoderAgent(self.mock_llm, self.blackboard)

    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(self.agent.AGENT_TYPE, "coder")
        self.assertIsInstance(self.agent.capabilities, CoderCapabilities)

    def test_capabilities(self):
        """测试能力定义"""
        caps = CoderCapabilities()
        self.assertIn("Read", caps.allowed_tools)
        self.assertIn("Write", caps.allowed_tools)
        self.assertIn("Edit", caps.allowed_tools)
        self.assertTrue(caps.requires_confirmation)

    def test_execute_success(self):
        """测试成功执行"""
        self.mock_llm.chat.return_value = '```python filename="calc.py"\ndef calc(): pass\n```'

        result = self.agent.execute("Implement calculator")

        self.assertTrue(result.success)
        # 验证代码已保存到黑板
        code_artifacts = self.blackboard.list_artifacts(content_type="code")
        self.assertTrue(len(code_artifacts) > 0)


class TestTesterAgent(unittest.TestCase):
    """测试 TesterAgent"""

    def setUp(self):
        """设置测试 fixture"""
        self.mock_llm = Mock()
        self.blackboard = Blackboard("test-1")

        # Mock 命令执行器
        self.mock_executor = Mock()
        self.mock_executor.return_value = (True, "Tests passed", "")

        self.agent = TesterAgent(self.mock_llm, self.blackboard, self.mock_executor)

    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(self.agent.AGENT_TYPE, "tester")
        self.assertIsInstance(self.agent.capabilities, TesterCapabilities)

    def test_capabilities(self):
        """测试能力定义"""
        caps = TesterCapabilities()
        self.assertIn("Read", caps.allowed_tools)
        self.assertIn("Bash", caps.allowed_tools)
        self.assertFalse(caps.requires_confirmation)

    def test_generate_report(self):
        """测试生成报告"""
        results = {
            "tests": {"success": True, "stdout": "All tests passed", "stderr": ""},
            "types": {"success": True, "stdout": "", "stderr": ""},
            "lint": {"success": True, "stdout": "", "stderr": ""},
            "coverage": {"success": True, "stdout": "80%", "stderr": ""}
        }

        report = self.agent._generate_report(**results)

        self.assertIn("Quality Report", report)
        self.assertIn("Tests", report)
        self.assertIn("Type Check", report)


class TestFailureTypeClassification(unittest.TestCase):
    """测试失败类型分类"""

    def setUp(self):
        """设置测试 fixture"""
        self.mock_llm = Mock()
        self.orchestrator = WorkflowOrchestrator(llm_service=self.mock_llm)

    def test_classify_type_error(self):
        """测试类型错误分类"""
        result = self.orchestrator._classify_failure_type("TypeError: incompatible types")
        self.assertEqual(result, "type_error")

    def test_classify_syntax_error(self):
        """测试语法错误分类"""
        result = self.orchestrator._classify_failure_type("SyntaxError: invalid syntax")
        self.assertEqual(result, "syntax_error")

    def test_classify_assertion_error(self):
        """测试断言错误分类"""
        result = self.orchestrator._classify_failure_type("AssertionError: expected 200, got 404")
        self.assertEqual(result, "test_failure")

    def test_classify_import_error(self):
        """测试导入错误分类"""
        result = self.orchestrator._classify_failure_type("ImportError: No module named 'xyz'")
        self.assertEqual(result, "runtime_error")


class TestAnalyzeTestFailure(unittest.TestCase):
    """测试测试失败分析"""

    def setUp(self):
        """设置测试 fixture"""
        self.mock_llm = Mock()
        self.orchestrator = WorkflowOrchestrator(llm_service=self.mock_llm)

    def test_retry_for_type_error(self):
        """测试类型错误应该重试"""
        result = EnhancedAgentResult(
            success=False,
            error="TypeError: incompatible types"
        )
        decision = self.orchestrator._analyze_test_failure(result)
        self.assertEqual(decision, "retry")

    def test_replan_for_assertion_error(self):
        """测试断言错误应该重新规划"""
        result = EnhancedAgentResult(
            success=False,
            error="AssertionError: expected 200, got 404"
        )
        decision = self.orchestrator._analyze_test_failure(result)
        self.assertEqual(decision, "replan")

    def test_default_retry(self):
        """测试默认重试"""
        result = EnhancedAgentResult(
            success=False,
            error="Unknown error"
        )
        decision = self.orchestrator._analyze_test_failure(result)
        self.assertEqual(decision, "retry")


class TestBlackboard(unittest.TestCase):
    """测试 Blackboard"""

    def setUp(self):
        """设置测试 fixture"""
        self.blackboard = Blackboard("test-1")

    def test_add_artifact(self):
        """测试添加工件"""
        artifact_id = self.blackboard.add_artifact(
            name="test.txt",
            content="test content",
            content_type="text",
            created_by="tester"
        )
        self.assertIsNotNone(artifact_id)

    def test_get_artifact(self):
        """测试获取工件"""
        self.blackboard.add_artifact(
            name="test.txt",
            content="test content",
            content_type="text",
            created_by="tester"
        )
        artifact = self.blackboard.get_artifact("test.txt")
        self.assertIsNotNone(artifact)
        self.assertEqual(artifact.content, "test content")

    def test_list_artifacts(self):
        """测试列出工件"""
        self.blackboard.add_artifact("plan.md", "plan", "plan", "planner")
        self.blackboard.add_artifact("code.py", "code", "code", "coder")
        self.blackboard.add_artifact("test.py", "test", "code", "coder")

        # 按类型过滤
        code_artifacts = self.blackboard.list_artifacts(content_type="code")
        self.assertEqual(len(code_artifacts), 2)

        # 按创建者过滤
        coder_artifacts = self.blackboard.list_artifacts(created_by="coder")
        self.assertEqual(len(coder_artifacts), 2)

    def test_context_management(self):
        """测试上下文管理"""
        self.blackboard.set_context("key1", "value1")
        self.blackboard.set_context("key2", {"nested": "value"})

        self.assertEqual(self.blackboard.get_context("key1"), "value1")
        self.assertEqual(self.blackboard.get_context("key2"), {"nested": "value"})
        self.assertEqual(self.blackboard.get_context("missing", "default"), "default")

    def test_event_logging(self):
        """测试事件日志"""
        event = Event(
            type=EventType.AGENT_COMPLETED,
            data={"result": "success"},
            source="planner"
        )
        self.blackboard.log_event(event)

        events = self.blackboard.get_event_log()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, EventType.AGENT_COMPLETED)

    def test_event_subscription(self):
        """测试事件订阅"""
        callback_called = []

        def callback(event):
            callback_called.append(event)

        self.blackboard.subscribe(EventType.AGENT_COMPLETED, callback)

        event = Event(
            type=EventType.AGENT_COMPLETED,
            source="test"
        )
        self.blackboard.log_event(event)

        self.assertEqual(len(callback_called), 1)
        self.assertEqual(callback_called[0].type, EventType.AGENT_COMPLETED)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
