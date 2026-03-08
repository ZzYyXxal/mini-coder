# Design: Parallel Scheduler System

## Context

当前系统采用串行执行模式：
- Orchestrator 按顺序派发子代理任务
- Agent 内部的 Tool 调用也是串行执行
- 无并发控制机制，效率受限

## Goals / Non-Goals

**Goals:**
- 实现 Agent 级并行调度（多 Agent 同时执行）
- 实现 Tool 级并行调度（Agent 内 Tool 并发）
- 提供统一的并发控制和超时管理
- 支持 DAG 依赖关系的 Tool 调用

**Non-Goals:**
- 不支持跨 Orchestrator 的分布式调度
- 不实现持久化任务队列
- 不支持动态并发数调整（运行时修改）

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     WorkflowOrchestrator                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                   ParallelScheduler                        │  │
│  │  ┌─────────────────┐    ┌─────────────────────────────┐   │  │
│  │  │ Agent Semaphore │    │     Task Management         │   │  │
│  │  │   (max: 3)      │    │  - Running Tasks Tracking   │   │  │
│  │  └─────────────────┘    │  - Cancel/Timeout Support   │   │  │
│  │                          └─────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│              ┌───────────────┼───────────────┐                  │
│              ▼               ▼               ▼                  │
│         ┌────────┐      ┌────────┐      ┌────────┐             │
│         │ Agent1 │      │ Agent2 │      │ Agent3 │             │
│         └────────┘      └────────┘      └────────┘             │
│              │               │               │                  │
│         ┌────────────────────────────────────────┐             │
│         │            ToolScheduler               │             │
│         │  ┌─────────────────────────────────┐   │             │
│         │  │ Dependency Graph (DAG) Builder  │   │             │
│         │  └─────────────────────────────────┘   │             │
│         │  ┌─────────────────────────────────┐   │             │
│         │  │ Execution Batches (Topo Sort)   │   │             │
│         │  └─────────────────────────────────┘   │             │
│         └────────────────────────────────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

## Decisions

### Decision 1: 使用 asyncio.Semaphore 控制并发

**选择**: Python 原生 `asyncio.Semaphore`

**理由**:
- 原生支持，无额外依赖
- 与 asyncio 无缝集成
- 自动管理等待队列

**约束**:
- 并发数限制在 1-3（保守策略，避免资源竞争）

### Decision 2: Agent 级与 Tool 级分离调度

**选择**: 双层调度架构

```
ParallelScheduler (Agent 级)
    └── 管理多 Agent 并发
    └── 使用 agent_semaphore

ToolScheduler (Tool 级)
    └── 每个 Agent 独立实例
    └── 管理 Tool 调用并发
    └── 支持 DAG 依赖
```

**理由**:
- 关注点分离
- Agent 和 Tool 有不同的并发策略
- Tool 支持 DAG 依赖，Agent 不需要

### Decision 3: DAG 依赖使用拓扑排序

**选择**: 拓扑排序分层执行

```python
# 执行批次示例
Batch 0: [ToolCall A]           # 无依赖
Batch 1: [ToolCall B, ToolCall C]  # 依赖 A
Batch 2: [ToolCall D]           # 依赖 B, C
```

**实现**:
1. 构建依赖图（邻接表）
2. 计算入度
3. 拓扑排序，分层生成执行批次
4. 同层并行执行

### Decision 4: Placeholder 参数解析

**选择**: 使用 `{{call_id.output.field}}` 语法

```python
# 示例
ToolCall(
    call_id="1",
    tool_name="Read",
    arguments={"path": "config.yaml"}
)
ToolCall(
    call_id="2",
    tool_name="Read",
    arguments={"path": "{{1.output.main_file}}"},  # 引用 call_id=1 的输出
    depends_on=["1"]
)
```

**实现**:
- 正则匹配 `{{...}}` 模式
- 递归解析路径（支持嵌套 dict/list）
- 在执行前解析参数

### Decision 5: 失败策略

**选择**: 支持两种策略

| 策略 | 行为 |
|------|------|
| `continue` | 部分失败继续执行，收集所有结果 |
| `fail_fast` | 任一失败立即取消所有任务 |

**默认**: `continue`（更健壮）

## Data Structures

### Mailbox Schema 扩展

```python
# 并行任务组
@dataclass
class ParallelTaskGroup:
    group_id: str
    tasks: List[TaskBrief]
    max_concurrency: int = 3
    timeout_per_task: float = 300.0
    timeout_total: float = 600.0
    fail_strategy: str = "continue"

# 并行结果组
@dataclass
class ParallelResultGroup:
    group_id: str
    results: List[SubagentResult]
    success_count: int
    failure_count: int
    elapsed_time: float
    partial_success: bool = False

# Tool 调用
@dataclass
class ToolCall:
    call_id: str
    tool_name: str
    arguments: Dict[str, Any]
    depends_on: List[str] = field(default_factory=list)

# Tool 调用结果
@dataclass
class ToolCallResult:
    call_id: str
    tool_name: str
    success: bool
    duration: float
    output: Optional[Any] = None
    error: Optional[str] = None
```

## API Design

### ParallelScheduler

```python
class ParallelScheduler:
    def __init__(
        self,
        max_agent_concurrency: int = 3,
        max_tool_concurrency: int = 3,
    ): ...

    # Agent 级调度
    async def schedule_agent_single(
        self,
        task_brief: TaskBrief,
        agent_factory: Callable[[str], BaseAgent],
        timeout: Optional[float] = None,
    ) -> SubagentResult: ...

    async def schedule_agent_batch(
        self,
        group: ParallelTaskGroup,
        agent_factory: Callable[[str], BaseAgent],
    ) -> ParallelResultGroup: ...

    # Tool 级调度
    async def schedule_tool_batch(
        self,
        batch: ToolBatchRequest,
        tool_executor: Callable[[str, Dict], Any],
    ) -> ToolBatchResult: ...

    # 任务管理
    def cancel_task(self, task_id: str) -> bool: ...
    def cancel_all(self) -> int: ...
    def get_status(self) -> SchedulerStatus: ...
```

### ToolScheduler

```python
class ToolScheduler:
    def __init__(
        self,
        max_concurrency: int = 3,
        default_timeout: float = 60.0,
    ): ...

    async def execute_batch(
        self,
        tool_calls: List[ToolCall],
        tool_registry: Dict[str, BaseTool],
        timeout: Optional[float] = None,
    ) -> ToolBatchResult: ...

    async def execute_single(
        self,
        tool_call: ToolCall,
        tool_registry: Dict[str, BaseTool],
        timeout: Optional[float] = None,
    ) -> ToolCallResult: ...

    @staticmethod
    def parse_tool_calls_from_llm(
        llm_response: Dict[str, Any],
    ) -> List[ToolCall]: ...
```

## Error Handling

### 超时处理

```python
try:
    result = await asyncio.wait_for(
        self._run_agent(agent, task_brief),
        timeout=timeout,
    )
except asyncio.TimeoutError:
    return SubagentResult(
        task_id=task_brief.task_id,
        success=False,
        error=f"Timeout after {timeout}s",
    )
```

### 任务取消

```python
def cancel_all(self) -> int:
    count = 0
    for task_id, task in list(self._running_agents.items()):
        if not task.done():
            task.cancel()
            count += 1
    return count
```

### 部分成功处理

```python
# ParallelResultGroup 标记部分成功
partial_success = success_count > 0 and failure_count > 0
```

## Testing Strategy

### 单元测试
- `tests/agents/test_scheduler.py`: ParallelScheduler 单元测试
- `tests/tools/test_tool_scheduler.py`: ToolScheduler 单元测试

### 集成测试
- `tests/agents/test_parallel_workflow.py`: 端到端工作流测试
  - 并行 Agent 派发
  - Tool DAG 执行
  - 超时和取消
  - 部分成功场景

## Security Considerations

1. **并发数限制**: 强制 1-3 范围，防止资源耗尽
2. **超时保护**: 所有任务必须有超时
3. **任务隔离**: 使用 Semaphore 确保并发限制
4. **参数验证**: 解析 placeholder 时验证路径有效性