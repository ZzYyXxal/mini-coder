"""ParallelScheduler 单元测试。

测试场景:
1. 单任务执行
2. 并行执行（全部成功）
3. 并行执行（部分失败）
4. 超时测试
5. fail_fast 策略测试
6. 并发限制测试
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import time

from mini_coder.agents.scheduler import ParallelScheduler, SchedulerStatus
from mini_coder.agents.mailbox import (
    TaskBrief,
    SubagentResult,
    ParallelTaskGroup,
    ParallelResultGroup,
    ToolBatchRequest,
    ToolBatchResult,
    ToolCall,
    ToolCallResult,
    FAIL_STRATEGY_CONTINUE,
    FAIL_STRATEGY_FAIL_FAST,
    DEFAULT_MAX_CONCURRENCY,
    DEFAULT_AGENT_TIMEOUT,
    DEFAULT_TOOL_TIMEOUT,
    MESSAGE_TYPE_BATCH_TASK,
    MESSAGE_TYPE_BATCH_RESULT,
)


class TestParallelScheduler:
    """ParallelScheduler 测试类。"""

    def test_init_default_params(self):
        """测试默认参数初始化。"""
        scheduler = ParallelScheduler()
        assert scheduler._max_agent_concurrency == DEFAULT_MAX_CONCURRENCY

    def test_init_custom_params(self):
        """测试自定义参数初始化。"""
        scheduler = ParallelScheduler(
            max_agent_concurrency=2,
            default_agent_timeout=120.0,
        )
        assert scheduler._max_agent_concurrency == 2

    def test_init_invalid_concurrency(self):
        """测试无效并发参数。"""
        with pytest.raises(ValueError):
            ParallelScheduler(max_agent_concurrency=0)
        with pytest.raises(ValueError):
            ParallelScheduler(max_agent_concurrency=4)

    def test_get_status(self):
        """测试状态获取。"""
        scheduler = ParallelScheduler()
        status = scheduler.get_status()
        assert isinstance(status, SchedulerStatus)
        assert status.running_agents == 0
        assert status.max_agent_concurrency == DEFAULT_MAX_CONCURRENCY

    @pytest.mark.asyncio
    async def test_schedule_agent_single_success(self):
        """测试单任务执行成功。"""
        scheduler = ParallelScheduler()

        task_brief = TaskBrief(
            task_id="test_001",
            intent="探索代码库",
        )

        # Mock Agent
        mock_agent = MagicMock()
        mock_agent.name = "ExplorerAgent"
        mock_agent.execute.return_value = {"success": True, "output": "Found 5 files"}

        def agent_factory(agent_type: str):
            return mock_agent

        result = await scheduler.schedule_agent_single(task_brief, agent_factory, timeout=10.0)

        assert isinstance(result, SubagentResult)
        assert result.task_id == "test_001"
        assert result.success is True

    @pytest.mark.asyncio
    async def test_schedule_agent_single_failure(self):
        """测试单任务执行失败。"""
        scheduler = ParallelScheduler()

        task_brief = TaskBrief(
            task_id="test_002",
            intent="实现功能",
        )

        # Mock Agent that throws exception
        def agent_factory(agent_type: str):
            mock_agent = MagicMock()
            mock_agent.name = "CoderAgent"
            mock_agent.execute.side_effect = Exception("Implementation failed")
            return mock_agent

        result = await scheduler.schedule_agent_single(task_brief, agent_factory, timeout=10.0)

        assert result.success is False
        assert "Implementation failed" in result.error

    @pytest.mark.asyncio
    async def test_schedule_agent_batch_all_success(self):
        """测试批量并行执行（全部成功）。"""
        scheduler = ParallelScheduler(max_agent_concurrency=3)

        tasks = [
            TaskBrief(task_id="task_1", intent="探索代码库"),
            TaskBrief(task_id="task_2", intent="规划任务"),
            TaskBrief(task_id="task_3", intent="实现功能"),
        ]

        group = ParallelTaskGroup(
            group_id="batch_001",
            tasks=tasks,
            max_concurrency=3,
            timeout_per_task=10.0,
        )

        # Mock Agent
        def agent_factory(agent_type: str):
            mock_agent = MagicMock()
            mock_agent.name = f"{agent_type.capitalize()}Agent"
            mock_agent.execute.return_value = {"success": True, "output": "Done"}
            return mock_agent

        result = await scheduler.schedule_agent_batch(group, agent_factory)

        assert isinstance(result, ParallelResultGroup)
        assert result.success_count == 3
        assert result.failure_count == 0
        assert result.partial_success is False

    @pytest.mark.asyncio
    async def test_schedule_agent_batch_partial_failure(self):
        """测试批量并行执行（部分失败）。"""
        scheduler = ParallelScheduler(max_agent_concurrency=3)

        tasks = [
            TaskBrief(task_id="task_1", intent="探索代码库"),
            TaskBrief(task_id="task_2", intent="规划任务"),
            TaskBrief(task_id="task_3", intent="实现功能"),
        ]

        group = ParallelTaskGroup(
            group_id="batch_002",
            tasks=tasks,
            max_concurrency=3,
            timeout_per_task=10.0,
            fail_strategy=FAIL_STRATEGY_CONTINUE,
        )

        call_count = [0]

        # Mock Agent: 第2个任务失败
        def agent_factory(agent_type: str):
            call_count[0] += 1
            mock_agent = MagicMock()
            mock_agent.name = f"{agent_type.capitalize()}Agent"
            if call_count[0] == 2:
                mock_agent.execute.side_effect = Exception("Task 2 failed")
            else:
                mock_agent.execute.return_value = {"success": True, "output": "Done"}
            return mock_agent

        result = await scheduler.schedule_agent_batch(group, agent_factory)

        assert result.success_count == 2
        assert result.failure_count == 1
        assert result.partial_success is True

    @pytest.mark.asyncio
    async def test_schedule_agent_batch_fail_fast(self):
        """测试 fail_fast 策略。"""
        scheduler = ParallelScheduler(max_agent_concurrency=1)  # 串行执行

        tasks = [
            TaskBrief(task_id="task_1", intent="任务1"),
            TaskBrief(task_id="task_2", intent="任务2"),
            TaskBrief(task_id="task_3", intent="任务3"),
        ]

        group = ParallelTaskGroup(
            group_id="batch_003",
            tasks=tasks,
            max_concurrency=1,
            timeout_per_task=10.0,
            fail_strategy=FAIL_STRATEGY_FAIL_FAST,
        )

        call_count = [0]

        # Mock Agent: 第1个任务就失败
        def agent_factory(agent_type: str):
            call_count[0] += 1
            mock_agent = MagicMock()
            mock_agent.name = "TestAgent"
            if call_count[0] == 1:
                mock_agent.execute.side_effect = Exception("First task fails")
            else:
                mock_agent.execute.return_value = {"success": True, "output": "Done"}
            return mock_agent

        result = await scheduler.schedule_agent_batch(group, agent_factory)

        # fail_fast 策略下，失败后取消其他任务
        assert result.failure_count >= 1

    @pytest.mark.asyncio
    async def test_schedule_agent_batch_timeout(self):
        """测试超时。"""
        scheduler = ParallelScheduler()

        tasks = [
            TaskBrief(task_id="slow_task", intent="慢任务"),
        ]

        group = ParallelTaskGroup(
            group_id="batch_timeout",
            tasks=tasks,
            max_concurrency=1,
            timeout_per_task=0.05,  # 50ms 超时
        )

        # Mock Agent: 模拟慢执行（睡眠）
        def slow_execute(intent):
            import time
            time.sleep(0.2)  # 睡眠 200ms，超过 50ms 超时
            return {"success": True, "output": "Done"}

        def agent_factory(agent_type: str):
            mock_agent = MagicMock()
            mock_agent.name = "SlowAgent"
            mock_agent.execute = slow_execute
            return mock_agent

        result = await scheduler.schedule_agent_batch(group, agent_factory)

        # 超时后应该返回失败结果
        assert result.failure_count == 1
        # 验证任务失败（可能是超时或其他错误）
        assert result.results[0].success is False

    @pytest.mark.asyncio
    async def test_concurrency_limit(self):
        """测试并发限制。"""
        scheduler = ParallelScheduler(max_agent_concurrency=2)

        tasks = [
            TaskBrief(task_id=f"task_{i}", intent=f"任务{i}")
            for i in range(4)
        ]

        group = ParallelTaskGroup(
            group_id="concurrency_test",
            tasks=tasks,
            max_concurrency=2,  # 最多 2 个并行
            timeout_per_task=30.0,
        )

        concurrent_count = [0]
        max_concurrent = [0]

        def agent_factory(agent_type: str):
            mock_agent = MagicMock()
            mock_agent.name = "TestAgent"
            mock_agent.execute.return_value = {"success": True, "output": "Done"}
            return mock_agent

        result = await scheduler.schedule_agent_batch(group, agent_factory)

        # 验证所有任务都完成了
        assert result.success_count == 4


class TestToolScheduler:
    """ToolScheduler 测试类。"""

    @pytest.mark.asyncio
    async def test_execute_single_tool(self):
        """测试单个 Tool 执行。"""
        from mini_coder.agents.tool_scheduler import ToolScheduler

        scheduler = ToolScheduler()

        tool_call = ToolCall(
            call_id="call_1",
            tool_name="Read",
            arguments={"path": "/test/file.py"},
        )

        tool_registry = {
            "Read": MagicMock(execute=MagicMock(return_value="file content")),
        }

        result = await scheduler.execute_single(tool_call, tool_registry, timeout=10.0)

        assert isinstance(result, ToolCallResult)
        assert result.call_id == "call_1"
        assert result.tool_name == "Read"
        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_batch_tools(self):
        """测试批量 Tool 执行。"""
        from mini_coder.agents.tool_scheduler import ToolScheduler

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
    async def test_tool_dependency_dag(self):
        """测试 Tool 依赖 DAG 执行。"""
        from mini_coder.agents.tool_scheduler import ToolScheduler

        scheduler = ToolScheduler()

        # call_2 和 call_3 依赖 call_1
        tool_calls = [
            ToolCall(call_id="1", tool_name="Read", arguments={"path": "config.yaml"}),
            ToolCall(call_id="2", tool_name="Read", arguments={"path": "{{1.output.main}}"}, depends_on=["1"]),
            ToolCall(call_id="3", tool_name="Read", arguments={"path": "{{1.output.test}}"}, depends_on=["1"]),
        ]

        call_order = []

        def mock_execute(**kwargs):
            path = kwargs.get("path", "")
            call_order.append(path)
            if path == "config.yaml":
                return {"main": "main.py", "test": "test_main.py"}
            return f"content of {path}"

        tool_registry = {
            "Read": MagicMock(execute=mock_execute),
        }

        result = await scheduler.execute_batch(tool_calls, tool_registry)

        # 验证执行顺序: config.yaml 应该先执行
        assert "config.yaml" in call_order[0]

    @pytest.mark.asyncio
    async def test_tool_failure_partial_success(self):
        """测试 Tool 部分失败。"""
        from mini_coder.agents.tool_scheduler import ToolScheduler

        scheduler = ToolScheduler()

        tool_calls = [
            ToolCall(call_id="1", tool_name="Read", arguments={"path": "exists.py"}),
            ToolCall(call_id="2", tool_name="Read", arguments={"path": "missing.py"}),
            ToolCall(call_id="3", tool_name="Read", arguments={"path": "another.py"}),
        ]

        call_count = [0]

        def mock_execute(**kwargs):
            call_count[0] += 1
            path = kwargs.get("path", "")
            if path == "missing.py":
                raise FileNotFoundError("File not found")
            return f"content of {path}"

        tool_registry = {
            "Read": MagicMock(execute=mock_execute),
        }

        result = await scheduler.execute_batch(tool_calls, tool_registry)

        assert result.success_count == 2
        assert result.failure_count == 1


class TestMailboxSchema:
    """Mailbox Schema 测试类。"""

    def test_parallel_task_group_validation(self):
        """测试 ParallelTaskGroup 验证。"""
        # 有效参数
        group = ParallelTaskGroup(
            group_id="test",
            tasks=[TaskBrief(task_id="1", intent="test")],
            max_concurrency=3,
        )
        assert group.max_concurrency == 3

        # 无效并发数
        with pytest.raises(ValueError):
            ParallelTaskGroup(
                group_id="test",
                tasks=[],
                max_concurrency=5,
            )

        # 无效失败策略
        with pytest.raises(ValueError):
            ParallelTaskGroup(
                group_id="test",
                tasks=[],
                fail_strategy="invalid",
            )

    def test_parallel_result_group(self):
        """测试 ParallelResultGroup。"""
        results = [
            SubagentResult(task_id="1", from_agent="explorer", success=True, summary="Done"),
            SubagentResult(task_id="2", from_agent="planner", success=False, summary="Failed", error="Error"),
        ]

        group = ParallelResultGroup(
            group_id="test",
            results=results,
            success_count=1,
            failure_count=1,
            elapsed_time=1.5,
            partial_success=True,
        )

        assert group.partial_success is True
        assert len(group.results) == 2

    def test_mailbox_message_batch_task(self):
        """测试 MailboxMessage.create_batch_task。"""
        from mini_coder.agents.mailbox import MailboxMessage

        group = ParallelTaskGroup(
            group_id="batch_001",
            tasks=[
                TaskBrief(task_id="1", intent="task1"),
                TaskBrief(task_id="2", intent="task2"),
            ],
        )

        msg = MailboxMessage.create_batch_task(group)

        assert msg.type == MESSAGE_TYPE_BATCH_TASK
        assert msg.to_agent == "main"

        # 解析回 ParallelTaskGroup
        parsed = msg.get_parallel_task_group()
        assert parsed is not None
        assert parsed.group_id == "batch_001"
        assert len(parsed.tasks) == 2

    def test_mailbox_message_batch_result(self):
        """测试 MailboxMessage.create_batch_result。"""
        from mini_coder.agents.mailbox import MailboxMessage

        result_group = ParallelResultGroup(
            group_id="batch_002",
            results=[
                SubagentResult(task_id="1", from_agent="explorer", success=True, summary="Done"),
            ],
            success_count=1,
            failure_count=0,
            elapsed_time=0.5,
        )

        msg = MailboxMessage.create_batch_result(result_group)

        assert msg.type == MESSAGE_TYPE_BATCH_RESULT

        # 解析回 ParallelResultGroup
        parsed = msg.get_parallel_result_group()
        assert parsed is not None
        assert parsed.group_id == "batch_002"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])