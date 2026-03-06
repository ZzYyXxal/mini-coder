"""并行工作流集成测试。

测试场景:
1. Orchestrator 并行 Agent 派发
2. Tool 并行调用
3. DAG 依赖执行
4. 完整工作流测试
"""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import time

from mini_coder.agents.orchestrator import (
    WorkflowOrchestrator,
    WorkflowConfig,
    SubAgentType,
)
from mini_coder.agents.mailbox import (
    TaskBrief,
    SubagentResult,
    ParallelTaskGroup,
    ParallelResultGroup,
    ToolCall,
    ToolCallResult,
    FAIL_STRATEGY_CONTINUE,
    FAIL_STRATEGY_FAIL_FAST,
)
from mini_coder.agents.scheduler import ParallelScheduler
from mini_coder.agents.tool_scheduler import ToolScheduler


class TestOrchestratorParallelDispatch:
    """Orchestrator 并行派发测试。"""

    @pytest.mark.asyncio
    async def test_dispatch_async_single(self):
        """测试异步单任务派发。"""
        config = WorkflowConfig(
            max_agent_concurrency=3,
            max_tool_concurrency=3,
            timeout_seconds=30.0,
        )
        orchestrator = WorkflowOrchestrator(
            llm_service=None,
            config=config,
        )

        # Mock _create_subagent 返回模拟 Agent
        mock_agent = MagicMock()
        mock_agent.name = "ExplorerAgent"
        mock_agent.execute.return_value = {"success": True, "output": "Found files"}

        with patch.object(orchestrator, '_create_subagent', return_value=mock_agent):
            result = await orchestrator.dispatch_async("探索代码库")

        assert result is not None
        assert result.success is True

    @pytest.mark.asyncio
    async def test_dispatch_parallel_async(self):
        """测试异步并行任务派发。"""
        config = WorkflowConfig(
            max_agent_concurrency=3,
            max_tool_concurrency=3,
            timeout_seconds=30.0,
        )
        orchestrator = WorkflowOrchestrator(
            llm_service=None,
            config=config,
        )

        # Mock _create_subagent 返回模拟 Agent
        mock_agent = MagicMock()
        mock_agent.name = "TestAgent"
        mock_agent.execute.return_value = {"success": True, "output": "Done"}

        intents = [
            "探索代码库",
            "规划任务",
            "实现功能",
        ]

        with patch.object(orchestrator, '_create_subagent', return_value=mock_agent):
            result = await orchestrator.dispatch_parallel_async(intents)

        assert isinstance(result, ParallelResultGroup)
        assert result.success_count == 3
        assert result.failure_count == 0

    @pytest.mark.asyncio
    async def test_dispatch_parallel_partial_failure(self):
        """测试并行派发部分失败。"""
        config = WorkflowConfig(
            max_agent_concurrency=3,
            timeout_seconds=30.0,
        )
        orchestrator = WorkflowOrchestrator(
            llm_service=None,
            config=config,
        )

        call_count = [0]

        def create_mock_agent(agent_type):
            call_count[0] += 1
            mock_agent = MagicMock()
            mock_agent.name = "TestAgent"
            if call_count[0] == 2:
                mock_agent.execute.side_effect = Exception("Task 2 failed")
            else:
                mock_agent.execute.return_value = {"success": True, "output": "Done"}
            return mock_agent

        intents = ["任务1", "任务2", "任务3"]

        with patch.object(orchestrator, '_create_subagent', side_effect=create_mock_agent):
            result = await orchestrator.dispatch_parallel_async(
                intents,
                fail_strategy=FAIL_STRATEGY_CONTINUE,
            )

        assert result.partial_success is True
        assert result.success_count == 2
        assert result.failure_count == 1

    def test_get_scheduler_status(self):
        """测试获取调度器状态。"""
        config = WorkflowConfig(
            max_agent_concurrency=2,
            max_tool_concurrency=2,
        )
        orchestrator = WorkflowOrchestrator(
            llm_service=None,
            config=config,
        )

        status = orchestrator.get_scheduler_status()

        assert status["max_agent_concurrency"] == 2
        assert status["max_tool_concurrency"] == 2
        assert status["running_agents"] == 0
        assert status["running_tools"] == 0


class TestToolParallelExecution:
    """Tool 并行执行测试。"""

    @pytest.mark.asyncio
    async def test_tool_batch_execution(self):
        """测试 Tool 批量执行。"""
        scheduler = ToolScheduler(max_concurrency=3)

        tool_calls = [
            ToolCall(call_id="1", tool_name="Read", arguments={"path": "file1.py"}),
            ToolCall(call_id="2", tool_name="Read", arguments={"path": "file2.py"}),
            ToolCall(call_id="3", tool_name="Read", arguments={"path": "file3.py"}),
        ]

        tool_registry = {
            "Read": MagicMock(execute=MagicMock(return_value="content")),
        }

        result = await scheduler.execute_batch(tool_calls, tool_registry)

        assert result.success_count == 3
        assert result.failure_count == 0

    @pytest.mark.asyncio
    async def test_tool_dag_execution(self):
        """测试 Tool DAG 依赖执行。"""
        scheduler = ToolScheduler(max_concurrency=2)

        # DAG: task1 -> [task2, task3]
        tool_calls = [
            ToolCall(call_id="1", tool_name="Read", arguments={"path": "config.yaml"}),
            ToolCall(
                call_id="2",
                tool_name="Read",
                arguments={"path": "{{1.output.main}}"},
                depends_on=["1"],
            ),
            ToolCall(
                call_id="3",
                tool_name="Read",
                arguments={"path": "{{1.output.test}}"},
                depends_on=["1"],
            ),
        ]

        execution_order = []

        def mock_execute(**kwargs):
            path = kwargs.get("path", "")
            execution_order.append(path)
            if path == "config.yaml":
                return {"main": "main.py", "test": "test_main.py"}
            return f"content of {path}"

        tool_registry = {
            "Read": MagicMock(execute=mock_execute),
        }

        result = await scheduler.execute_batch(tool_calls, tool_registry)

        assert result.success_count == 3
        # 验证 config.yaml 先执行
        assert "config.yaml" in execution_order[0]

    @pytest.mark.asyncio
    async def test_tool_timeout(self):
        """测试 Tool 超时。"""
        scheduler = ToolScheduler(max_concurrency=1)

        tool_call = ToolCall(
            call_id="slow",
            tool_name="SlowTool",
            arguments={"delay": 1.0},
        )

        def slow_execute(**kwargs):
            import time
            time.sleep(0.5)  # 睡眠 500ms
            return "done"

        tool_registry = {
            "SlowTool": MagicMock(execute=slow_execute),
        }

        result = await scheduler.execute_single(
            tool_call,
            tool_registry,
            timeout=0.1,  # 100ms 超时
        )

        assert result.success is False
        assert "Timeout" in result.error or "timeout" in result.error.lower()


class TestParallelSchedulerIntegration:
    """ParallelScheduler 集成测试。"""

    @pytest.mark.asyncio
    async def test_agent_batch_with_semaphore(self):
        """测试 Semaphore 并发限制。"""
        scheduler = ParallelScheduler(max_agent_concurrency=2)

        tasks = [
            TaskBrief(task_id=f"task_{i}", intent=f"任务{i}")
            for i in range(4)
        ]

        group = ParallelTaskGroup(
            group_id="semaphore_test",
            tasks=tasks,
            max_concurrency=2,  # 最多 2 个并行
            timeout_per_task=30.0,
        )

        def agent_factory(agent_type: str):
            mock_agent = MagicMock()
            mock_agent.name = "TestAgent"
            mock_agent.execute.return_value = {"success": True, "output": "Done"}
            return mock_agent

        result = await scheduler.schedule_agent_batch(group, agent_factory)

        assert result.success_count == 4

    @pytest.mark.asyncio
    async def test_cancel_running_tasks(self):
        """测试取消运行中的任务。"""
        scheduler = ParallelScheduler(max_agent_concurrency=1)

        task_brief = TaskBrief(task_id="long_task", intent="长任务")

        def slow_agent_factory(agent_type: str):
            mock_agent = MagicMock()
            mock_agent.name = "SlowAgent"

            def slow_execute(intent):
                import time
                time.sleep(10)  # 睡眠 10 秒
                return {"success": True}

            mock_agent.execute = slow_execute
            return mock_agent

        # 在后台启动任务
        task = asyncio.create_task(
            scheduler.schedule_agent_single(task_brief, slow_agent_factory, timeout=30.0)
        )

        # 等待任务开始
        await asyncio.sleep(0.1)

        # 取消所有任务
        cancelled = scheduler.cancel_all()

        # 验证任务被取消
        assert cancelled >= 0


class TestFullWorkflow:
    """完整工作流测试。"""

    @pytest.mark.asyncio
    async def test_parallel_workflow_integration(self):
        """测试完整并行工作流。"""
        # 创建 Orchestrator
        config = WorkflowConfig(
            max_agent_concurrency=3,
            max_tool_concurrency=3,
            timeout_seconds=60.0,
        )
        orchestrator = WorkflowOrchestrator(
            llm_service=None,
            config=config,
        )

        # 模拟多个 Agent 任务
        intents = [
            "探索 src 目录结构",
            "规划模块划分",
            "实现核心功能",
        ]

        # Mock Agent 工厂
        def create_mock_agent(agent_type):
            # agent_type 可能是 SubAgentType 枚举或字符串
            if isinstance(agent_type, SubAgentType):
                agent_name = agent_type.value
            else:
                agent_name = str(agent_type)

            mock_agent = MagicMock()
            mock_agent.name = f"{agent_name.capitalize()}Agent"
            mock_agent.execute.return_value = {
                "success": True,
                "output": f"Task completed by {agent_name}",
            }
            return mock_agent

        with patch.object(orchestrator, '_create_subagent', side_effect=create_mock_agent):
            # 并行执行
            result = await orchestrator.dispatch_parallel_async(intents)

        # 验证结果
        assert result.success_count == 3
        assert result.failure_count == 0
        assert result.elapsed_time > 0

        # 获取调度器状态
        status = orchestrator.get_scheduler_status()
        assert status["running_agents"] == 0  # 所有任务完成


if __name__ == "__main__":
    pytest.main([__file__, "-v"])