"""并行调度器 - 统一管理 Agent 级和 Tool 级并发。

核心职责:
1. Agent 级并行 - 多个 Agent 同时执行任务
2. Tool 级并行 - Agent 内并行调用多个 Tool
3. 资源管理 - Semaphore 控制并发数量
4. 超时控制 - 单任务和批量任务超时保护
5. 错误处理 - 部分成功继续、失败策略

使用示例:
```python
scheduler = ParallelScheduler(max_agent_concurrency=3, max_tool_concurrency=3)

# 单任务执行
result = await scheduler.schedule_agent_single(task_brief, agent_factory)

# 并行任务执行
result_group = await scheduler.schedule_agent_batch(parallel_task_group, agent_factory)

# Tool 批量调用
tool_result = await scheduler.schedule_tool_batch(tool_batch_request, tool_executor)
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
    running_tools: int
    waiting_agents: int
    waiting_tools: int
    max_agent_concurrency: int
    max_tool_concurrency: int


class ParallelScheduler:
    """统一并行调度器，管理 Agent 级和 Tool 级并发。

    特性:
    - 使用 asyncio.Semaphore 控制并发数量
    - 支持单任务和批量任务执行
    - 支持部分成功继续策略
    - 支持超时控制和错误处理
    """

    def __init__(
        self,
        max_agent_concurrency: int = DEFAULT_MAX_CONCURRENCY,
        max_tool_concurrency: int = DEFAULT_MAX_CONCURRENCY,
        default_agent_timeout: float = DEFAULT_AGENT_TIMEOUT,
        default_tool_timeout: float = DEFAULT_TOOL_TIMEOUT,
    ):
        """初始化调度器。

        Args:
            max_agent_concurrency: Agent 级最大并发数 (1-3)
            max_tool_concurrency: Tool 级最大并发数 (1-3)
            default_agent_timeout: Agent 任务默认超时时间 (秒)
            default_tool_timeout: Tool 调用默认超时时间 (秒)
        """
        if not 1 <= max_agent_concurrency <= 3:
            raise ValueError(f"max_agent_concurrency must be 1-3, got {max_agent_concurrency}")
        if not 1 <= max_tool_concurrency <= 3:
            raise ValueError(f"max_tool_concurrency must be 1-3, got {max_tool_concurrency}")

        self._max_agent_concurrency = max_agent_concurrency
        self._max_tool_concurrency = max_tool_concurrency
        self._default_agent_timeout = default_agent_timeout
        self._default_tool_timeout = default_tool_timeout

        # 并发控制信号量
        self._agent_semaphore = asyncio.Semaphore(max_agent_concurrency)
        self._tool_semaphore = asyncio.Semaphore(max_tool_concurrency)

        # 运行中的任务跟踪
        self._running_agents: Dict[str, asyncio.Task] = {}
        self._running_tools: Dict[str, asyncio.Task] = {}

        # 任务超时配置
        self._agent_timeouts: Dict[str, float] = {}
        self._tool_timeouts: Dict[str, float] = {}

        logger.info(
            f"ParallelScheduler initialized "
            f"(max_agents={max_agent_concurrency}, max_tools={max_tool_concurrency})"
        )

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
        task_map: List[tuple] = []  # [(task_id, asyncio.Task), ...]

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
                done, pending = await asyncio.wait(
                    [t for _, t in task_map],
                    return_when=asyncio.FIRST_EXCEPTION,
                    timeout=group.timeout_total,
                )
                # 取消未完成的任务
                for task in pending:
                    task.cancel()
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

        except Exception as e:
            logger.exception(f"Batch execution error: {e}")

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
        - 如果是同步方法，在 executor 中运行
        """
        import inspect

        # 检查是否是增强型 Agent
        from mini_coder.agents.enhanced import BaseEnhancedAgent, EnhancedAgentResult

        if isinstance(agent, BaseEnhancedAgent):
            # Enhanced Agent 使用同步 execute
            result = agent.execute(task_brief.intent)
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

    # ==================== Tool 级调度 ====================

    async def schedule_tool_batch(
        self,
        batch: ToolBatchRequest,
        tool_executor: Callable[[str, Dict[str, Any]], Any],
    ) -> ToolBatchResult:
        """并行执行多个 Tool 调用。

        支持依赖关系（DAG），按拓扑序分批执行。

        Args:
            batch: Tool 批量调用请求
            tool_executor: Tool 执行函数，接收 (tool_name, arguments) 返回结果

        Returns:
            ToolBatchResult: 批量调用结果
        """
        start_time = time.time()
        results: List[ToolCallResult] = []

        # 构建依赖图并获取执行批次
        batches = self._build_execution_batches(batch.tool_calls)

        # 存储每个调用的结果，用于依赖解析
        call_results: Dict[str, Any] = {}

        for batch_calls in batches:
            # 同一批次内的调用并行执行
            batch_results = await self._execute_tool_batch(
                batch_calls, tool_executor, batch.timeout_per_call, call_results
            )

            # 更新结果映射
            for result in batch_results:
                call_results[result.call_id] = result.output if result.success else None
                results.append(result)

        elapsed_time = time.time() - start_time
        success_count = sum(1 for r in results if r.success)

        return ToolBatchResult(
            batch_id=batch.batch_id,
            results=results,
            success_count=success_count,
            failure_count=len(results) - success_count,
            elapsed_time=elapsed_time,
        )

    def _build_execution_batches(self, tool_calls: List[ToolCall]) -> List[List[ToolCall]]:
        """构建执行批次（拓扑排序）。

        无依赖的调用放在第一批，
        依赖前面批次的调用放在后续批次。
        """
        # 构建依赖图
        call_map = {tc.call_id: tc for tc in tool_calls}
        in_degree = {tc.call_id: 0 for tc in tool_calls}
        dependents: Dict[str, List[str]] = {tc.call_id: [] for tc in tool_calls}

        for tc in tool_calls:
            for dep_id in tc.depends_on:
                if dep_id in call_map:
                    dependents[dep_id].append(tc.call_id)
                    in_degree[tc.call_id] += 1

        # 拓扑排序，分层构建批次
        batches: List[List[ToolCall]] = []
        remaining = set(in_degree.keys())

        while remaining:
            # 找出当前层（入度为 0）
            current_layer = [
                call_map[call_id]
                for call_id in remaining
                if in_degree[call_id] == 0
            ]

            if not current_layer:
                # 存在循环依赖，按原顺序执行剩余调用
                logger.warning("Circular dependency detected in tool calls")
                current_layer = [call_map[call_id] for call_id in remaining]

            batches.append(current_layer)

            # 更新入度
            for tc in current_layer:
                for dep_call_id in dependents[tc.call_id]:
                    in_degree[dep_call_id] -= 1
                remaining.discard(tc.call_id)

        return batches

    async def _execute_tool_batch(
        self,
        tool_calls: List[ToolCall],
        tool_executor: Callable[[str, Dict[str, Any]], Any],
        timeout: float,
        previous_results: Dict[str, Any],
    ) -> List[ToolCallResult]:
        """执行一批 Tool 调用（并行）。"""
        results: List[ToolCallResult] = []

        async def run_single(tc: ToolCall) -> ToolCallResult:
            async with self._tool_semaphore:
                start = time.time()
                try:
                    # 解析参数中的占位符
                    resolved_args = self._resolve_args(tc.arguments, previous_results)

                    # 执行 Tool
                    output = await asyncio.wait_for(
                        self._run_tool(tool_executor, tc.tool_name, resolved_args),
                        timeout=timeout,
                    )

                    return ToolCallResult(
                        call_id=tc.call_id,
                        tool_name=tc.tool_name,
                        success=True,
                        duration=time.time() - start,
                        output=output,
                    )
                except asyncio.TimeoutError:
                    return ToolCallResult(
                        call_id=tc.call_id,
                        tool_name=tc.tool_name,
                        success=False,
                        duration=time.time() - start,
                        error=f"Timeout after {timeout}s",
                    )
                except Exception as e:
                    return ToolCallResult(
                        call_id=tc.call_id,
                        tool_name=tc.tool_name,
                        success=False,
                        duration=time.time() - start,
                        error=str(e),
                    )

        # 并行执行
        tasks = [asyncio.create_task(run_single(tc)) for tc in tool_calls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理异常结果
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(ToolCallResult(
                    call_id=tool_calls[i].call_id,
                    tool_name=tool_calls[i].tool_name,
                    success=False,
                    duration=0,
                    error=str(result),
                ))
            else:
                final_results.append(result)

        return final_results

    async def _run_tool(
        self,
        tool_executor: Callable[[str, Dict[str, Any]], Any],
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Any:
        """执行单个 Tool。"""
        import inspect

        if inspect.iscoroutinefunction(tool_executor):
            return await tool_executor(tool_name, arguments)
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, lambda: tool_executor(tool_name, arguments)
            )

    def _resolve_args(
        self,
        args: Dict[str, Any],
        previous_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """解析参数中的占位符引用。

        支持格式: {{call_id.output.field}}
        """
        import re

        resolved = {}
        for key, value in args.items():
            if isinstance(value, str) and "{{" in value:
                # 替换占位符
                def replace_placeholder(match):
                    path = match.group(1).split(".")
                    result = previous_results.get(path[0])
                    if result is None:
                        return match.group(0)  # 保持原样
                    for field in path[1:]:
                        if isinstance(result, dict):
                            result = result.get(field)
                        else:
                            return match.group(0)
                    return str(result) if result is not None else match.group(0)

                resolved[key] = re.sub(r'\{\{(\w+(?:\.\w+)*)\}\}', replace_placeholder, value)
            elif isinstance(value, dict):
                resolved[key] = self._resolve_args(value, previous_results)
            elif isinstance(value, list):
                resolved[key] = [
                    self._resolve_args(v, previous_results) if isinstance(v, dict) else v
                    for v in value
                ]
            else:
                resolved[key] = value

        return resolved

    # ==================== 任务管理 ====================

    def cancel_task(self, task_id: str) -> bool:
        """取消正在运行的任务。

        Args:
            task_id: 任务 ID

        Returns:
            bool: 是否成功取消
        """
        task = self._running_agents.get(task_id) or self._running_tools.get(task_id)
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
        for task_id, task in list(self._running_tools.items()):
            if not task.done():
                task.cancel()
                count += 1
        return count

    def get_status(self) -> SchedulerStatus:
        """获取调度器状态。"""
        running_agents = sum(1 for t in self._running_agents.values() if not t.done())
        running_tools = sum(1 for t in self._running_tools.values() if not t.done())

        # 估算等待数量（semaphore 的等待者）
        waiting_agents = max(0, len(self._running_agents) - running_agents)
        waiting_tools = max(0, len(self._running_tools) - running_tools)

        return SchedulerStatus(
            running_agents=running_agents,
            running_tools=running_tools,
            waiting_agents=waiting_agents,
            waiting_tools=waiting_tools,
            max_agent_concurrency=self._max_agent_concurrency,
            max_tool_concurrency=self._max_tool_concurrency,
        )