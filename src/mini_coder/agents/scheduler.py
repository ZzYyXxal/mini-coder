"""并行调度器 - 统一管理 Agent 级并发。

核心职责:
1. Agent 级并行 - 多个 Agent 同时执行任务
2. 资源管理 - Semaphore 控制并发数量
3. 超时控制 - 单任务和批量任务超时保护
4. 错误处理 - 部分成功继续、失败策略

注意: Tool 级并行调度已移至 ToolScheduler 类。

使用示例:
```python
scheduler = ParallelScheduler(max_agent_concurrency=3)

# 单任务执行
result = await scheduler.schedule_agent_single(task_brief, agent_factory)

# 并行任务执行
result_group = await scheduler.schedule_agent_batch(parallel_task_group, agent_factory)

# Tool 批量调用 - 使用 ToolScheduler
from mini_coder.agents.tool_scheduler import ToolScheduler
tool_scheduler = ToolScheduler(max_concurrency=3)
tool_result = await tool_scheduler.execute_batch(tool_calls, tool_registry)
```
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

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
)

if TYPE_CHECKING:
    from mini_coder.agents.base import BaseAgent
    from mini_coder.agents.enhanced import BaseEnhancedAgent

logger = logging.getLogger(__name__)


@dataclass
class SchedulerStatus:
    """调度器状态快照。"""

    running_agents: int
    waiting_agents: int
    max_agent_concurrency: int


class ParallelScheduler:
    """Agent 级并行调度器。

    特性:
    - 使用 asyncio.Semaphore 控制并发数量
    - 支持单任务和批量任务执行
    - 支持部分成功继续策略
    - 支持超时控制和错误处理

    注意: Tool 级调度请使用 ToolScheduler 类。
    """

    def __init__(
        self,
        max_agent_concurrency: int = DEFAULT_MAX_CONCURRENCY,
        default_agent_timeout: float = DEFAULT_AGENT_TIMEOUT,
    ):
        """初始化调度器。

        Args:
            max_agent_concurrency: Agent 级最大并发数 (1-3)
            default_agent_timeout: Agent 任务默认超时时间 (秒)
        """
        if not 1 <= max_agent_concurrency <= 3:
            raise ValueError(f"max_agent_concurrency must be 1-3, got {max_agent_concurrency}")

        self._max_agent_concurrency = max_agent_concurrency
        self._default_agent_timeout = default_agent_timeout

        # 并发控制信号量
        self._agent_semaphore = asyncio.Semaphore(max_agent_concurrency)

        # 运行中的任务跟踪
        self._running_agents: Dict[str, asyncio.Task[SubagentResult]] = {}

        # 任务超时配置
        self._agent_timeouts: Dict[str, float] = {}

        logger.info(f"ParallelScheduler initialized (max_agents={max_agent_concurrency})")

    # ==================== Agent 级调度 ====================

    async def schedule_agent_single(
        self,
        task_brief: TaskBrief,
        agent_factory: Callable[[str], "BaseAgent"],
        timeout: Optional[float] = None,
    ) -> SubagentResult:
        """执行单个 Agent 任务。

        Args:
            task_brief: 任务描述
            agent_factory: Agent 工厂函数，接收 agent_type 返回 Agent 实例
            timeout: 超时时间（秒），默认使用 default_agent_timeout

        Returns:
            SubagentResult: 执行结果
        """
        timeout = timeout or self._default_agent_timeout
        start_time = time.time()

        async def run_with_semaphore() -> SubagentResult:
            async with self._agent_semaphore:
                return await self._execute_agent_task(task_brief, agent_factory, timeout)

        # 创建任务
        task = asyncio.create_task(run_with_semaphore())
        self._running_agents[task_brief.task_id] = task
        self._agent_timeouts[task_brief.task_id] = timeout

        try:
            result = await task
            return result
        except asyncio.TimeoutError:
            logger.warning(f"Agent task {task_brief.task_id} timed out after {timeout}s")
            return SubagentResult(
                task_id=task_brief.task_id,
                from_agent="unknown",
                success=False,
                summary="Task timed out",
                error=f"Timeout after {timeout} seconds",
            )
        except Exception as e:
            logger.exception(f"Agent task {task_brief.task_id} failed: {e}")
            return SubagentResult(
                task_id=task_brief.task_id,
                from_agent="unknown",
                success=False,
                summary="Task failed",
                error=str(e),
            )
        finally:
            self._running_agents.pop(task_brief.task_id, None)
            self._agent_timeouts.pop(task_brief.task_id, None)

    async def schedule_agent_batch(
        self,
        group: ParallelTaskGroup,
        agent_factory: Callable[[str], "BaseAgent"],
    ) -> ParallelResultGroup:
        """并行执行多个 Agent 任务。

        Args:
            group: 并行任务组
            agent_factory: Agent 工厂函数

        Returns:
            ParallelResultGroup: 批量执行结果
        """
        start_time = time.time()
        results: List[SubagentResult] = []
        task_map: List[tuple[str, asyncio.Task[SubagentResult]]] = []  # [(task_id, asyncio.Task), ...]

        async def run_with_semaphore(task_brief: TaskBrief) -> SubagentResult:
            async with self._agent_semaphore:
                return await self._execute_agent_task(
                    task_brief, agent_factory, group.timeout_per_task
                )

        # 创建所有任务
        for task_brief in group.tasks:
            task = asyncio.create_task(run_with_semaphore(task_brief))
            task_map.append((task_brief.task_id, task))
            self._running_agents[task_brief.task_id] = task

        try:
            if group.fail_strategy == FAIL_STRATEGY_FAIL_FAST:
                # 任一失败立即停止
                # 使用 FIRST_COMPLETED 而不是 FIRST_EXCEPTION，因为取消的任务也需要处理
                done, pending = await asyncio.wait(
                    [t for _, t in task_map],
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=group.timeout_total,
                )

                # 检查第一个完成的任务是否失败
                first_failed = False
                for task in done:
                    try:
                        if task.cancelled():
                            first_failed = True
                            break
                        # 尝试获取结果，如果抛出异常则标记失败
                        task.result()
                    except Exception:
                        first_failed = True
                        break

                # 如果第一个任务失败，取消所有未完成的任务
                if first_failed:
                    for task in pending:
                        task.cancel()
                    # 等待取消完成
                    if pending:
                        await asyncio.gather(*pending, return_exceptions=True)
            else:
                # 继续执行，等待所有完成
                done, pending = await asyncio.wait(
                    [t for _, t in task_map],
                    return_when=asyncio.ALL_COMPLETED,
                    timeout=group.timeout_total,
                )
                # 超时后取消未完成的任务
                for task in pending:
                    task.cancel()
                # 等待取消完成
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)

        except Exception as e:
            logger.exception(f"Batch execution error: {e}")
            # 确保所有任务都被取消
            for _, task in task_map:
                if not task.done():
                    task.cancel()

        # 收集结果
        cancelled_count = 0
        for task_id, task in task_map:
            try:
                if task.cancelled():
                    cancelled_count += 1
                    results.append(SubagentResult(
                        task_id=task_id,
                        from_agent="unknown",
                        success=False,
                        summary="Task cancelled",
                        error="Task was cancelled",
                    ))
                else:
                    result = task.result()
                    results.append(result)
            except asyncio.CancelledError:
                cancelled_count += 1
                results.append(SubagentResult(
                    task_id=task_id,
                    from_agent="unknown",
                    success=False,
                    summary="Task cancelled",
                    error="Task was cancelled",
                ))
            except Exception as e:
                results.append(SubagentResult(
                    task_id=task_id,
                    from_agent="unknown",
                    success=False,
                    summary="Task failed",
                    error=str(e),
                ))

        # 清理
        for task_id, _ in task_map:
            self._running_agents.pop(task_id, None)

        elapsed_time = time.time() - start_time
        success_count = sum(1 for r in results if r.success)
        failure_count = len(results) - success_count

        return ParallelResultGroup(
            group_id=group.group_id,
            results=results,
            success_count=success_count,
            failure_count=failure_count,
            cancelled_count=cancelled_count,
            elapsed_time=elapsed_time,
            partial_success=success_count > 0 and failure_count > 0,
        )

    async def _execute_agent_task(
        self,
        task_brief: TaskBrief,
        agent_factory: Callable[[str], "BaseAgent"],
        timeout: float,
    ) -> SubagentResult:
        """执行单个 Agent 任务（内部方法，已获取 semaphore）。"""
        start_time = time.time()

        try:
            # 从 intent 中推断 agent_type
            agent_type = self._infer_agent_type(task_brief.intent)
            agent = agent_factory(agent_type)

            # 执行任务（带超时）
            result = await asyncio.wait_for(
                self._run_agent(agent, task_brief),
                timeout=timeout,
            )

            elapsed = time.time() - start_time
            if result.metrics is None:
                result.metrics = {}
            result.metrics["elapsed_time"] = elapsed

            return result

        except asyncio.TimeoutError:
            raise
        except Exception as e:
            logger.exception(f"Agent execution error: {e}")
            return SubagentResult(
                task_id=task_brief.task_id,
                from_agent="unknown",
                success=False,
                summary="Agent execution failed",
                error=str(e),
            )

    async def _run_agent(
        self,
        agent: "BaseAgent",
        task_brief: TaskBrief,
    ) -> SubagentResult:
        """运行 Agent 并返回结构化结果。

        支持同步和异步 Agent：
        - 如果 Agent.execute 是异步方法，直接 await
        - 如果是同步方法，在 executor 中运行（避免阻塞事件循环）
        """
        import inspect

        # 检查是否是增强型 Agent
        from mini_coder.agents.enhanced import BaseEnhancedAgent, EnhancedAgentResult

        if isinstance(agent, BaseEnhancedAgent):
            # Enhanced Agent 使用同步 execute，必须在 executor 中运行以避免阻塞事件循环
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: agent.execute(task_brief.intent)
            )
            return self._convert_enhanced_result(result, task_brief.task_id, agent.name)
        else:
            # 普通 Agent
            if inspect.iscoroutinefunction(agent.execute):
                result = await agent.execute(task_brief.intent)
            else:
                # 在线程池中运行同步方法
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, lambda: agent.execute(task_brief.intent)
                )

            # 转换结果
            return self._convert_agent_result(result, task_brief.task_id, agent.name)

    def _convert_enhanced_result(
        self,
        result: "EnhancedAgentResult",
        task_id: str,
        agent_name: str,
    ) -> SubagentResult:
        """转换 EnhancedAgentResult 为 SubagentResult。"""
        return SubagentResult(
            task_id=task_id,
            from_agent=agent_name.lower(),
            success=result.success,
            summary=result.output[:200] if result.output else "Completed",
            error=result.error,
            metrics={
                "elapsed_time": result.elapsed_time,
                "failure_type": result.failure_type,
            },
        )

    def _convert_agent_result(
        self,
        result: Any,
        task_id: str,
        agent_name: str,
    ) -> SubagentResult:
        """转换普通 Agent 结果为 SubagentResult。"""
        if isinstance(result, SubagentResult):
            return result
        elif isinstance(result, dict):
            return SubagentResult(
                task_id=task_id,
                from_agent=agent_name.lower(),
                success=result.get("success", True),
                summary=result.get("summary", result.get("output", "Completed")[:200]),
                error=result.get("error"),
                metrics=result.get("metrics"),
            )
        else:
            return SubagentResult(
                task_id=task_id,
                from_agent=agent_name.lower(),
                success=True,
                summary=str(result)[:200] if result else "Completed",
            )

    def _infer_agent_type(self, intent: str) -> str:
        """从意图推断 Agent 类型。"""
        intent_lower = intent.lower()

        # 简单关键词匹配
        if any(kw in intent_lower for kw in ["探索", "查找", "explore", "search", "find"]):
            return "explorer"
        elif any(kw in intent_lower for kw in ["规划", "计划", "plan", "design"]):
            return "planner"
        elif any(kw in intent_lower for kw in ["实现", "编写", "implement", "write", "code"]):
            return "coder"
        elif any(kw in intent_lower for kw in ["评审", "检查", "review", "check"]):
            return "reviewer"
        elif any(kw in intent_lower for kw in ["测试", "运行", "test", "run", "bash"]):
            return "bash"
        else:
            return "coder"  # 默认

    # ==================== 任务管理 ====================

    def cancel_task(self, task_id: str) -> bool:
        """取消正在运行的任务。

        Args:
            task_id: 任务 ID

        Returns:
            bool: 是否成功取消
        """
        task = self._running_agents.get(task_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    def cancel_all(self) -> int:
        """取消所有正在运行的任务。

        Returns:
            int: 取消的任务数量
        """
        count = 0
        for task_id, task in list(self._running_agents.items()):
            if not task.done():
                task.cancel()
                count += 1
        return count

    def get_status(self) -> SchedulerStatus:
        """获取调度器状态。"""
        running_agents = sum(1 for t in self._running_agents.values() if not t.done())

        # 估算等待数量（semaphore 的等待者）
        waiting_agents = max(0, len(self._running_agents) - running_agents)

        return SchedulerStatus(
            running_agents=running_agents,
            waiting_agents=waiting_agents,
            max_agent_concurrency=self._max_agent_concurrency,
        )