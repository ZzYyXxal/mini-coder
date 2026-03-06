"""Tool 调度器 - Agent 内部 Tool 并行调用管理。

核心职责:
1. 解析 LLM 返回的 tool_calls
2. 构建依赖图 (DAG)
3. 按拓扑序分批执行
4. 同层任务并行执行
5. 结果收集与返回

与 ParallelScheduler 的区别:
- ParallelScheduler: Agent 级调度，管理多个 Agent 的并发
- ToolScheduler: Agent 内部调度，管理单个 Agent 内的 Tool 并发

使用示例:
```python
scheduler = ToolScheduler(max_concurrency=3)

# 解析并执行 tool_calls
tool_calls = parse_llm_response(response)
result = await scheduler.execute_batch(tool_calls, tool_registry)
```
"""

import asyncio
import logging
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, TYPE_CHECKING

from mini_coder.agents.mailbox import (
    ToolCall,
    ToolCallResult,
    ToolBatchRequest,
    ToolBatchResult,
    DEFAULT_MAX_CONCURRENCY,
    DEFAULT_TOOL_TIMEOUT,
)

if TYPE_CHECKING:
    from mini_coder.tools.base import BaseTool

logger = logging.getLogger(__name__)


@dataclass
class ToolExecutionBatch:
    """一批可并行执行的 Tool 调用。"""

    batch_index: int
    calls: List[ToolCall]


@dataclass
class DependencyGraph:
    """Tool 调用依赖图。"""

    nodes: Dict[str, ToolCall]
    edges: Dict[str, List[str]]  # call_id -> [依赖它的 call_ids]
    in_degree: Dict[str, int]
    execution_batches: List[ToolExecutionBatch]


class ToolScheduler:
    """Agent 内部的 Tool 并行调度器。

    特性:
    - 支持声明依赖关系 (depends_on)
    - 自动构建 DAG 并拓扑排序
    - 同层调用并行执行
    - 支持 placeholder 参数解析
    """

    def __init__(
        self,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
        default_timeout: float = DEFAULT_TOOL_TIMEOUT,
    ):
        """初始化调度器。

        Args:
            max_concurrency: 最大并发数 (1-3)
            default_timeout: 单次调用默认超时 (秒)
        """
        if not 1 <= max_concurrency <= 3:
            raise ValueError(f"max_concurrency must be 1-3, got {max_concurrency}")

        self._max_concurrency = max_concurrency
        self._default_timeout = default_timeout
        self._semaphore = asyncio.Semaphore(max_concurrency)

        # 执行历史
        self._execution_history: List[ToolBatchResult] = []

        logger.info(f"ToolScheduler initialized (max_concurrency={max_concurrency})")

    async def execute_batch(
        self,
        tool_calls: List[ToolCall],
        tool_registry: Dict[str, "BaseTool"],
        timeout: Optional[float] = None,
    ) -> ToolBatchResult:
        """执行一批 Tool 调用。

        Args:
            tool_calls: Tool 调用列表
            tool_registry: Tool 注册表 {name: tool_instance}
            timeout: 整体超时时间

        Returns:
            ToolBatchResult: 执行结果
        """
        timeout = timeout or self._default_timeout
        start_time = time.time()
        batch_id = f"batch_{int(start_time * 1000)}"

        # 构建依赖图
        dep_graph = self._build_dependency_graph(tool_calls)

        # 存储执行结果
        all_results: List[ToolCallResult] = []
        call_outputs: Dict[str, Any] = {}  # call_id -> output

        # 按批次执行
        for batch in dep_graph.execution_batches:
            batch_results = await self._execute_batch_parallel(
                batch.calls,
                tool_registry,
                call_outputs,
                timeout,
            )

            # 收集结果
            for result in batch_results:
                call_outputs[result.call_id] = result.output if result.success else None
                all_results.append(result)

        elapsed_time = time.time() - start_time
        success_count = sum(1 for r in all_results if r.success)

        result = ToolBatchResult(
            batch_id=batch_id,
            results=all_results,
            success_count=success_count,
            failure_count=len(all_results) - success_count,
            elapsed_time=elapsed_time,
        )

        self._execution_history.append(result)
        return result

    async def execute_single(
        self,
        tool_call: ToolCall,
        tool_registry: Dict[str, "BaseTool"],
        timeout: Optional[float] = None,
    ) -> ToolCallResult:
        """执行单个 Tool 调用。

        Args:
            tool_call: Tool 调用
            tool_registry: Tool 注册表
            timeout: 超时时间

        Returns:
            ToolCallResult: 执行结果
        """
        timeout = timeout or self._default_timeout
        start_time = time.time()

        async with self._semaphore:
            try:
                tool = tool_registry.get(tool_call.tool_name)
                if not tool:
                    return ToolCallResult(
                        call_id=tool_call.call_id,
                        tool_name=tool_call.tool_name,
                        success=False,
                        duration=time.time() - start_time,
                        error=f"Tool not found: {tool_call.tool_name}",
                    )

                # 执行
                output = await asyncio.wait_for(
                    self._invoke_tool(tool, tool_call.arguments),
                    timeout=timeout,
                )

                return ToolCallResult(
                    call_id=tool_call.call_id,
                    tool_name=tool_call.tool_name,
                    success=True,
                    duration=time.time() - start_time,
                    output=output,
                )

            except asyncio.TimeoutError:
                return ToolCallResult(
                    call_id=tool_call.call_id,
                    tool_name=tool_call.tool_name,
                    success=False,
                    duration=time.time() - start_time,
                    error=f"Timeout after {timeout}s",
                )
            except Exception as e:
                logger.exception(f"Tool execution error: {e}")
                return ToolCallResult(
                    call_id=tool_call.call_id,
                    tool_name=tool_call.tool_name,
                    success=False,
                    duration=time.time() - start_time,
                    error=str(e),
                )

    def _build_dependency_graph(self, tool_calls: List[ToolCall]) -> DependencyGraph:
        """构建依赖图并计算执行批次。"""
        nodes: Dict[str, ToolCall] = {}
        edges: Dict[str, List[str]] = defaultdict(list)
        in_degree: Dict[str, int] = {}

        # 初始化
        for tc in tool_calls:
            nodes[tc.call_id] = tc
            in_degree[tc.call_id] = 0

        # 构建边和入度
        for tc in tool_calls:
            for dep_id in tc.depends_on:
                if dep_id in nodes:
                    edges[dep_id].append(tc.call_id)
                    in_degree[tc.call_id] += 1
                else:
                    logger.warning(
                        f"Tool call {tc.call_id} depends on non-existent call {dep_id}"
                    )

        # 拓扑排序，构建执行批次
        execution_batches: List[ToolExecutionBatch] = []
        remaining = set(in_degree.keys())
        batch_index = 0

        while remaining:
            # 当前层：入度为 0 的节点
            current_layer = [
                nodes[call_id] for call_id in remaining
                if in_degree[call_id] == 0
            ]

            if not current_layer:
                # 循环依赖，强制执行剩余节点
                logger.warning("Circular dependency detected, forcing execution")
                current_layer = [nodes[call_id] for call_id in remaining]

            execution_batches.append(ToolExecutionBatch(
                batch_index=batch_index,
                calls=current_layer,
            ))
            batch_index += 1

            # 更新入度
            for tc in current_layer:
                for dependent_id in edges[tc.call_id]:
                    in_degree[dependent_id] -= 1
                remaining.discard(tc.call_id)

        return DependencyGraph(
            nodes=nodes,
            edges=dict(edges),
            in_degree=in_degree,
            execution_batches=execution_batches,
        )

    async def _execute_batch_parallel(
        self,
        calls: List[ToolCall],
        tool_registry: Dict[str, "BaseTool"],
        previous_outputs: Dict[str, Any],
        timeout: float,
    ) -> List[ToolCallResult]:
        """并行执行一批 Tool 调用。"""
        tasks = [
            asyncio.create_task(
                self._execute_single_with_semaphore(
                    tc, tool_registry, previous_outputs, timeout
                )
            )
            for tc in calls
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理异常
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(ToolCallResult(
                    call_id=calls[i].call_id,
                    tool_name=calls[i].tool_name,
                    success=False,
                    duration=0,
                    error=str(result),
                ))
            else:
                final_results.append(result)

        return final_results

    async def _execute_single_with_semaphore(
        self,
        tool_call: ToolCall,
        tool_registry: Dict[str, "BaseTool"],
        previous_outputs: Dict[str, Any],
        timeout: float,
    ) -> ToolCallResult:
        """在 semaphore 控制下执行单个 Tool。"""
        start_time = time.time()

        async with self._semaphore:
            try:
                tool = tool_registry.get(tool_call.tool_name)
                if not tool:
                    return ToolCallResult(
                        call_id=tool_call.call_id,
                        tool_name=tool_call.tool_name,
                        success=False,
                        duration=time.time() - start_time,
                        error=f"Tool not found: {tool_call.tool_name}",
                    )

                # 解析参数中的 placeholder
                resolved_args = self._resolve_placeholders(
                    tool_call.arguments, previous_outputs
                )

                # 执行
                output = await asyncio.wait_for(
                    self._invoke_tool(tool, resolved_args),
                    timeout=timeout,
                )

                return ToolCallResult(
                    call_id=tool_call.call_id,
                    tool_name=tool_call.tool_name,
                    success=True,
                    duration=time.time() - start_time,
                    output=output,
                )

            except asyncio.TimeoutError:
                return ToolCallResult(
                    call_id=tool_call.call_id,
                    tool_name=tool_call.tool_name,
                    success=False,
                    duration=time.time() - start_time,
                    error=f"Timeout after {timeout}s",
                )
            except Exception as e:
                logger.exception(f"Tool execution error for {tool_call.tool_name}: {e}")
                return ToolCallResult(
                    call_id=tool_call.call_id,
                    tool_name=tool_call.tool_name,
                    success=False,
                    duration=time.time() - start_time,
                    error=str(e),
                )

    async def _invoke_tool(
        self,
        tool: "BaseTool",
        arguments: Dict[str, Any],
    ) -> Any:
        """调用 Tool 执行。

        支持同步和异步 Tool。
        """
        import inspect

        if hasattr(tool, "execute"):
            if inspect.iscoroutinefunction(tool.execute):
                return await tool.execute(**arguments)
            else:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None, lambda: tool.execute(**arguments)
                )
        elif hasattr(tool, "__call__"):
            if inspect.iscoroutinefunction(tool):
                return await tool(**arguments)
            else:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None, lambda: tool(**arguments)
                )
        else:
            raise ValueError(f"Tool {tool} has no execute method or is not callable")

    def _resolve_placeholders(
        self,
        args: Dict[str, Any],
        previous_outputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """解析参数中的 placeholder。

        支持格式:
        - {{call_id.output}} - 引用整个输出
        - {{call_id.output.field}} - 引用输出的某个字段
        - {{call_id.output.field.0}} - 引用输出的某个列表元素
        """
        resolved = {}

        for key, value in args.items():
            if isinstance(value, str):
                resolved[key] = self._resolve_string_placeholder(value, previous_outputs)
            elif isinstance(value, dict):
                resolved[key] = self._resolve_placeholders(value, previous_outputs)
            elif isinstance(value, list):
                resolved[key] = [
                    self._resolve_placeholders(v, previous_outputs) if isinstance(v, dict)
                    else self._resolve_string_placeholder(v, previous_outputs) if isinstance(v, str)
                    else v
                    for v in value
                ]
            else:
                resolved[key] = value

        return resolved

    def _resolve_string_placeholder(
        self,
        value: str,
        previous_outputs: Dict[str, Any],
    ) -> Any:
        """解析字符串中的 placeholder。"""
        if "{{" not in value:
            return value

        # 完全匹配一个 placeholder
        full_match = re.fullmatch(r'\{\{(\w+(?:\.\w+)*(?:\[\d+\])*)\}\}', value.strip())
        if full_match:
            return self._get_path_value(full_match.group(1), previous_outputs)

        # 部分匹配，替换 placeholder
        def replace_placeholder(match):
            path = match.group(1)
            result = self._get_path_value(path, previous_outputs)
            return str(result) if result is not None else match.group(0)

        return re.sub(r'\{\{(\w+(?:\.\w+)*(?:\[\d+\])*)\}\}', replace_placeholder, value)

    def _get_path_value(self, path: str, data: Dict[str, Any]) -> Any:
        """根据路径获取值。

        路径格式: call_id.output.field[0].subfield
        """
        # 解析路径
        parts = []
        for part in re.split(r'\.|\[|\]', path):
            if part:
                if part.isdigit():
                    parts.append(int(part))
                else:
                    parts.append(part)

        # 遍历路径
        result = data
        for part in parts:
            if result is None:
                return None
            if isinstance(part, int):
                if isinstance(result, (list, tuple)) and 0 <= part < len(result):
                    result = result[part]
                else:
                    return None
            elif isinstance(result, dict):
                result = result.get(part)
            else:
                return None

        return result

    # ==================== 工具方法 ====================

    @staticmethod
    def parse_tool_calls_from_llm(
        llm_response: Dict[str, Any],
    ) -> List[ToolCall]:
        """从 LLM 响应解析 tool_calls。

        Args:
            llm_response: LLM API 响应

        Returns:
            List[ToolCall]: 解析后的 Tool 调用列表
        """
        tool_calls = []

        # 标准 OpenAI/Anthropic 格式
        if "tool_calls" in llm_response:
            for i, tc in enumerate(llm_response["tool_calls"]):
                tool_calls.append(ToolCall(
                    call_id=tc.get("id", f"call_{i}"),
                    tool_name=tc.get("name") or tc.get("function", {}).get("name", "unknown"),
                    arguments=tc.get("arguments") or tc.get("function", {}).get("arguments", {}),
                    depends_on=[],  # 默认无依赖
                ))

        # 内容中的 tool_use 块 (Anthropic 格式)
        elif "content" in llm_response:
            content = llm_response["content"]
            if isinstance(content, list):
                for i, block in enumerate(content):
                    if block.get("type") == "tool_use":
                        tool_calls.append(ToolCall(
                            call_id=block.get("id", f"call_{i}"),
                            tool_name=block.get("name", "unknown"),
                            arguments=block.get("input", {}),
                            depends_on=[],
                        ))

        return tool_calls

    def get_execution_history(self) -> List[ToolBatchResult]:
        """获取执行历史。"""
        return self._execution_history.copy()

    def clear_history(self) -> None:
        """清空执行历史。"""
        self._execution_history.clear()