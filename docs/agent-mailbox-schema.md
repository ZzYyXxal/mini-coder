# Agent 间上下文共享：Blackboard 作为 Mailbox + 结构化回传 Schema

## 一、设计目标

- **不共享全部信息**：子代理只能看到「发给自己的任务摘要」和「允许引用的工件」，不能随意读全量 context。
- **主 Agent 当管理员**：负责分解任务、投递任务到对应子代理、收集子代理的**结构化结果**，再决定下一步或汇总给用户（参考 AutoGen Magentic-One：Orchestrator + Task Ledger + Progress Ledger）。
- **Blackboard 当 Mailbox**：定向投递（指定 to/from），消息类型与 payload 有明确 schema，便于扩展和审计。
- **支持并行执行**：支持 Agent 级并行（多 Agent 同时执行）和 Tool 级并行（Agent 内并行调用多个 Tool），提升执行效率。

## 二、角色与流向

```
                    ┌─────────────────────────────────────────┐
                    │              MAIN (Orchestrator)        │
                    │  - 分解任务                              │
                    │  - 投递 TaskBrief → 指定子代理             │
                    │  - 收集 SubagentResult ← 子代理           │
                    │  - 更新进度、决定下一步                    │
                    └───────────────────┬─────────────────────┘
                                        │
          ┌─────────────────────────────┼─────────────────────────────┐
          │                             │                             │
          ▼                             ▼                             ▼
   ┌──────────────┐              ┌──────────────┐              ┌──────────────┐
   │  Explorer   │              │   Planner    │              │    Coder     │
   │ 收: TaskBrief│              │ 收: TaskBrief│              │ 收: TaskBrief│
   │ 发: Result   │              │ 发: Result   │              │ 发: Result   │
   └──────────────┘              └──────────────┘              └──────────────┘
```

- **MAIN**：唯一能「分解任务、投递任务、收集结果」的角色；不直接执行工具，只做调度与汇总。
- **子代理**：只接收**发给自己的** `TaskBrief`；执行结束后**必须**回写一条 `SubagentResult` 给 MAIN；不从 Blackboard 读「全量 context」，只读本任务允许的字段与工件引用。

## 三、Mailbox 消息约定

### 3.1 消息信封（所有消息共用）

| 字段 | 类型 | 说明 |
|------|------|------|
| `message_id` | str | 唯一 ID（如 UUID 或 task_id + 序列） |
| `to_agent` | str | 收件人：`main` \| `explorer` \| `planner` \| `coder` \| `reviewer` \| `bash` |
| `from_agent` | str | 发件人（同上枚举） |
| `type` | str | 见下表 |
| `payload` | object | 结构化负载，依 type 不同而不同 |
| `created_at` | float | 时间戳 |

### 3.2 消息类型与 Payload Schema

| type | 方向 | 说明 | payload 结构 |
|------|------|------|--------------|
| `task` | MAIN → 子代理 | 主代理下发的任务 | **TaskBrief**（见下） |
| `result` | 子代理 → MAIN | 子代理执行完毕的回传 | **SubagentResult**（见下） |
| `batch_task` | MAIN → 多个子代理 | 批量并行任务派发 | **ParallelTaskGroup**（见 3.5） |
| `batch_result` | 多个子代理 → MAIN | 批量并行结果收集 | **ParallelResultGroup**（见 3.6） |
| `request` | 子代理 → MAIN | 子代理请求更多信息或权限 | 可扩展，当前可不实现 |

### 3.3 TaskBrief（type = "task"）

主代理发给子代理的**唯一**输入；子代理不应再从 Blackboard 读 `get_all_context()`。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | str | ✓ | 本任务 ID，与结果回传时一致 |
| `intent` | str | ✓ | 用户意图或本步任务描述（一句话） |
| `context_refs` | List[str] | 否 | 允许子代理读取的**工件名称**列表（如 `["implementation_plan.md"]`）；空或不传表示不提供额外工件 |
| `extra` | Dict[str, Any] | 否 | 主代理认为需要带给该子代理的少量键值；建议少而精，避免大段文本 |

### 3.4 SubagentResult（type = "result"）

子代理**必须**在任务结束后回传一条给 MAIN；MAIN 据此更新进度、决定下一步或汇总给用户。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | str | ✓ | 与 TaskBrief.task_id 一致 |
| `from_agent` | str | ✓ | 与信封 from_agent 一致（冗余便于校验） |
| `success` | bool | ✓ | 是否成功完成 |
| `summary` | str | ✓ | 简短文字摘要（一两句话），供 MAIN 或用户快速浏览 |
| `artifact_refs` | List[str] | 否 | 本步产出的**工件名称**列表（如 `["implementation_plan.md"]`、`["code:src/foo.py"]`），MAIN 可据此从 Blackboard 取内容 |
| `error` | str | 否 | 若 success=false，错误信息 |
| `next_suggested_agent` | str | 否 | 建议下一步派发的子代理（如 `planner` → `coder`）；MAIN 可参考，不强制采纳 |
| `metrics` | Dict[str, Any] | 否 | 可选：耗时、token 数等，便于统计与审计 |

### 3.5 ParallelTaskGroup（type = "batch_task"）

用于批量并行派发多个子代理任务，支持统一调度和资源管理。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `group_id` | str | ✓ | 并行任务组唯一 ID |
| `tasks` | List[TaskBrief] | ✓ | 并行执行的任务列表 |
| `max_concurrency` | int | 否 | 最大并发数，默认 3，范围 1-3 |
| `timeout_per_task` | float | 否 | 单任务超时时间（秒），默认 300 |
| `timeout_total` | float | 否 | 整体超时时间（秒），默认 600 |
| `fail_strategy` | str | 否 | 失败策略：`"continue"`（继续执行）\| `"fail_fast"`（任一失败立即停止），默认 `"continue"` |

**设计说明：**
- `max_concurrency` 限制同时运行的子代理数量，防止资源耗尽
- `fail_strategy = "continue"` 时，部分失败不影响其他任务，最终返回所有结果
- `fail_strategy = "fail_fast"` 时，任一任务失败立即取消其他运行中的任务

### 3.6 ParallelResultGroup（type = "batch_result"）

批量并行任务的执行结果汇总。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `group_id` | str | ✓ | 与 ParallelTaskGroup.group_id 一致 |
| `results` | List[SubagentResult] | ✓ | 所有任务的执行结果（含成功和失败） |
| `success_count` | int | ✓ | 成功任务数量 |
| `failure_count` | int | ✓ | 失败任务数量 |
| `cancelled_count` | int | 否 | 被取消的任务数量（fail_fast 场景） |
| `elapsed_time` | float | ✓ | 整体执行耗时（秒） |
| `partial_success` | bool | ✓ | 是否部分成功（有成功也有失败） |

### 3.7 ToolBatchRequest（Agent 内部 Tool 并行调用）

用于 Agent 内部并行调用多个 Tool，由调度器统一管理。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `batch_id` | str | ✓ | 批量调用唯一 ID |
| `tool_calls` | List[ToolCall] | ✓ | 并行调用的 Tool 列表 |
| `max_concurrency` | int | 否 | 最大并发数，默认 3，范围 1-3 |
| `timeout_per_call` | float | 否 | 单次调用超时（秒），默认 60 |

**ToolCall 结构：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `call_id` | str | ✓ | 调用唯一 ID |
| `tool_name` | str | ✓ | Tool 名称 |
| `arguments` | Dict[str, Any] | ✓ | 调用参数 |
| `depends_on` | List[str] | 否 | 依赖的其他 call_id（支持 DAG） |

### 3.8 ToolBatchResult（Tool 批量调用结果）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `batch_id` | str | ✓ | 与 ToolBatchRequest.batch_id 一致 |
| `results` | List[ToolCallResult] | ✓ | 所有调用结果 |
| `success_count` | int | ✓ | 成功调用数量 |
| `failure_count` | int | ✓ | 失败调用数量 |
| `elapsed_time` | float | ✓ | 整体执行耗时（秒） |

**ToolCallResult 结构：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `call_id` | str | ✓ | 与 ToolCall.call_id 一致 |
| `tool_name` | str | ✓ | Tool 名称 |
| `success` | bool | ✓ | 是否成功 |
| `output` | Any | 否 | 成功时的输出 |
| `error` | str | 否 | 失败时的错误信息 |
| `duration` | float | ✓ | 单次调用耗时（秒） |

## 四、Blackboard 与 Mailbox 的职责划分

- **Mailbox**：仅存「消息队列」；按 `to_agent` 投递、按 `from_agent` / `type` 收集；**不**替代现有 artifact 存储。
- **Artifacts**：仍由 Blackboard 的 `add_artifact` / `get_artifact_content` 管理；TaskBrief 的 `context_refs` 与 SubagentResult 的 `artifact_refs` 引用这些**名称**，子代理或 MAIN 按名读取，实现「只共享关键信息」。
- **旧用法迁移**：逐步弃用「子代理直接 `get_all_context()`」；改为 MAIN 在 TaskBrief 中通过 `context_refs` 与 `extra` 显式传入允许的信息；子代理执行完后只写 artifact 并回传 SubagentResult，不写任意 context 键。

## 五、主代理（Orchestrator）流程（参考 Magentic-One）

### 5.1 单步派发

构造一条 `TaskBrief`，`to_agent` = 选中的子代理，`post(task)` 到 Mailbox；调用该子代理执行；子代理从 Mailbox `collect(to_agent=自己)` 取最新 task，执行，写 artifact（若有），再 `post_result(SubagentResult)`；MAIN `collect_results(for_agent=main)` 得到结果，展示或进入下一步。

### 5.2 多步工作流

循环：根据当前进度构造 TaskBrief → 投递 → 子代理执行 → 收集 SubagentResult → 更新进度；若 `next_suggested_agent` 或内部逻辑指定下一步，则继续；否则结束并汇总。

### 5.3 并行派发（batch_task）

当多个任务相互独立时，使用 `ParallelTaskGroup` 并行派发，由调度器统一管理并发：

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Parallel Dispatch Flow                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   MAIN                                                              │
│     │                                                               │
│     │ 1. Create ParallelTaskGroup                                   │
│     │    - tasks: [TaskBrief_1, TaskBrief_2, TaskBrief_3]          │
│     │    - max_concurrency: 3                                       │
│     │    - fail_strategy: "continue"                                │
│     ▼                                                               │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │                    ParallelScheduler                         │  │
│   │  ┌─────────────────────────────────────────────────────┐    │  │
│   │  │  Semaphore(max_concurrency=3)                       │    │  │
│   │  │  - 控制并发数量                                      │    │  │
│   │  │  - 任务队列管理                                      │    │  │
│   │  │  - 超时控制                                          │    │  │
│   │  └─────────────────────────────────────────────────────┘    │  │
│   └─────────────────────────────────────────────────────────────┘  │
│     │                                                               │
│     │ 2. asyncio.gather() with semaphore                           │
│     │                                                               │
│     ├────────────────┬────────────────┬────────────────┐          │
│     ▼                ▼                ▼                │          │
│   ┌──────┐        ┌──────┐        ┌──────┐            │          │
│   │Agent1│        │Agent2│        │Agent3│            │          │
│   │      │        │      │        │      │            │          │
│   │async │        │async │        │async │            │          │
│   └──┬───┘        └──┬───┘        └──┬───┘            │          │
│      │               │               │                 │          │
│      │ Success       │ Failure       │ Success         │          │
│      ▼               ▼               ▼                 │          │
│   Result_1       Result_2       Result_3              │          │
│     │               │               │                 │          │
│     └───────────────┴───────────────┴─────────────────┘          │
│                     │                                              │
│                     ▼                                              │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │ ParallelResultGroup                                          │  │
│   │  - success_count: 2                                          │  │
│   │  - failure_count: 1                                          │  │
│   │  - partial_success: true                                     │  │
│   │  - results: [Result_1, Result_2, Result_3]                   │  │
│   └─────────────────────────────────────────────────────────────┘  │
│     │                                                               │
│     ▼                                                               │
│   MAIN: 汇总结果，决定下一步                                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.4 进度/任务账本

可在 MAIN 侧维护轻量「任务账本」「进度账本」（如当前阶段、已完成步骤、最近一次 SubagentResult），用于决定下一步和防死循环；这些不必全部塞进 Mailbox，可放在 WorkflowContext 或 Orchestrator 状态中。

## 六、子代理行为约定

- **只读**：从 Mailbox 取「发给自己的」最新 `task`；从 Blackboard 只读 `context_refs` 中列出的 artifact（按名 `get_artifact_content(name)`）。
- **只写**：执行中产生的计划/代码等，仍用 `add_artifact` 写入 Blackboard；任务结束时**必须**调用 `post_result(SubagentResult)` 回传 MAIN。
- **不读**：不调用 `get_all_context()`；不读取未在 `context_refs` 或 `extra` 中给出的信息。

## 七、Tool 并行调用约定

### 7.1 调用模式

子代理内部支持 Tool 级并行调用，由 Agent 内部的 ToolScheduler 管理：

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Tool Parallel Invocation                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Sub-Agent (e.g., CoderAgent)                                      │
│     │                                                               │
│     │  LLM returns tool_calls: [call_1, call_2, call_3]            │
│     │                                                               │
│     ▼                                                               │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │                    ToolScheduler                             │  │
│   │  ┌─────────────────────────────────────────────────────┐    │  │
│   │  │  1. 分析依赖关系 (depends_on)                        │    │  │
│   │  │  2. 构建 DAG                                        │    │  │
│   │  │  3. 按拓扑序分批执行                                 │    │  │
│   │  │  4. 同层任务并行执行 (max_concurrency=3)            │    │  │
│   │  └─────────────────────────────────────────────────────┘    │  │
│   └─────────────────────────────────────────────────────────────┘  │
│     │                                                               │
│     │ 同层并行: [Read(file1), Read(file2), Read(file3)]           │
│     │                                                               │
│     ├────────────────┬────────────────┬────────────────┐          │
│     ▼                ▼                ▼                │          │
│   Tool_1          Tool_2          Tool_3               │          │
│   (Read)          (Read)          (Read)               │          │
│     │                │                │                 │          │
│     └────────────────┴────────────────┴─────────────────┘          │
│                      │                                              │
│                      ▼                                              │
│   ToolBatchResult: [result_1, result_2, result_3]                  │
│                      │                                              │
│                      ▼                                              │
│   返回给 LLM 进行下一轮决策                                         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.2 依赖分析

Tool 调用可以声明依赖关系，形成 DAG：

```python
# 示例：先读取配置，再根据配置读取多个文件
tool_calls = [
    ToolCall(call_id="1", tool_name="Read", arguments={"path": "config.yaml"}),
    ToolCall(call_id="2", tool_name="Read", arguments={"path": "{{1.output.main_file}}"}, depends_on=["1"]),
    ToolCall(call_id="3", tool_name="Read", arguments={"path": "{{1.output.test_file}}"}, depends_on=["1"]),
]

# DAG 执行顺序：
# Batch 1: [call_1]           (无依赖，先执行)
# Batch 2: [call_2, call_3]   (依赖 call_1，并行执行)
```

### 7.3 并行限制

- **max_concurrency = 3**：同一时刻最多 3 个 Tool 并行执行
- **timeout_per_call**：单个 Tool 调用超时保护
- **部分成功继续**：某个 Tool 失败不影响其他并行 Tool 执行

## 八、并行调度器设计

### 8.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Parallel Scheduler Architecture                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │                    Orchestrator (MAIN)                       │  │
│   │  - dispatch_single()    单任务派发                           │  │
│   │  - dispatch_parallel()  并行任务派发                         │  │
│   │  - dispatch_workflow()  工作流执行                           │  │
│   └─────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│                              ▼                                      │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │                  ParallelScheduler                           │  │
│   │  ┌───────────────────────────────────────────────────────┐  │  │
│   │  │  _agent_semaphore: asyncio.Semaphore(3)               │  │  │
│   │  │  _running_agents: Dict[str, asyncio.Task]             │  │  │
│   │  │  _agent_timeouts: Dict[str, float]                    │  │  │
│   │  └───────────────────────────────────────────────────────┘  │  │
│   │                                                              │  │
│   │  Methods:                                                    │  │
│   │  - schedule_agent_single(task: TaskBrief) -> SubagentResult│  │
│   │  - schedule_agent_batch(group: ParallelTaskGroup)          │  │
│   │      -> ParallelResultGroup                                  │  │
│   │  - cancel_task(task_id: str) -> bool                        │  │
│   │  - get_status() -> SchedulerStatus                          │  │
│   └─────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│          ┌───────────────────┼───────────────────┐                │
│          ▼                   ▼                   ▼                │
│   ┌────────────┐      ┌────────────┐      ┌────────────┐        │
│   │  Explorer  │      │  Planner   │      │   Coder    │        │
│   │   Agent    │      │   Agent    │      │   Agent    │        │
│   └────────────┘      └────────────┘      └────────────┘        │
│          │                   │                   │                │
│          ▼                   ▼                   ▼                │
│   ┌────────────┐      ┌────────────┐      ┌────────────┐        │
│   │ToolScheduler│     │ToolScheduler│     │ToolScheduler│        │
│   │(internal)  │      │(internal)  │      │(internal)  │        │
│   └────────────┘      └────────────┘      └────────────┘        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**职责分离**:
- `ParallelScheduler`: Agent 级调度，管理多个 Agent 的并发执行
- `ToolScheduler`: Tool 级调度，管理单个 Agent 内的 Tool 并发调用

### 8.2 ParallelScheduler 核心类设计

```python
class ParallelScheduler:
    """Agent 级并行调度器，管理多个 Agent 的并发执行"""

    def __init__(
        self,
        max_agent_concurrency: int = 3,
        default_agent_timeout: float = 300.0,
    ):
        self._agent_semaphore = asyncio.Semaphore(max_agent_concurrency)
        self._running_agents: Dict[str, asyncio.Task] = {}
        self._default_agent_timeout = default_agent_timeout

    async def schedule_agent_batch(
        self,
        group: ParallelTaskGroup,
        agent_factory: Callable[[str], BaseAgent],
    ) -> ParallelResultGroup:
        """并行执行多个 Agent 任务"""
        results = []
        tasks = []

        async def run_with_semaphore(task_brief: TaskBrief) -> SubagentResult:
            async with self._agent_semaphore:
                return await self._run_agent_task(
                    task_brief, agent_factory, group.timeout_per_task
                )

        # 创建所有任务
        for task_brief in group.tasks:
            task = asyncio.create_task(run_with_semaphore(task_brief))
            tasks.append((task_brief.task_id, task))
            self._running_agents[task_brief.task_id] = task

        # 等待所有任务完成（continue 策略）或任一失败（fail_fast 策略）
        if group.fail_strategy == "fail_fast":
            done, pending = await asyncio.wait(
                [t for _, t in tasks],
                return_when=asyncio.FIRST_EXCEPTION,
                timeout=group.timeout_total,
            )
            # 取消未完成的任务
            for task in pending:
                task.cancel()
        else:
            done, pending = await asyncio.wait(
                [t for _, t in tasks],
                return_when=asyncio.ALL_COMPLETED,
                timeout=group.timeout_total,
            )

        # 收集结果
        for task_id, task in tasks:
            try:
                result = task.result()
                results.append(result)
            except Exception as e:
                results.append(SubagentResult(
                    task_id=task_id,
                    from_agent="unknown",
                    success=False,
                    summary="Task failed",
                    error=str(e),
                ))

        # 清理
        for task_id, _ in tasks:
            self._running_agents.pop(task_id, None)

        return ParallelResultGroup(
            group_id=group.group_id,
            results=results,
            success_count=sum(1 for r in results if r.success),
            failure_count=sum(1 for r in results if not r.success),
            cancelled_count=len(pending) if group.fail_strategy == "fail_fast" else 0,
            elapsed_time=...,  # 计算实际耗时
            partial_success=any(r.success for r in results) and any(not r.success for r in results),
        )
```

### 8.3 资源管理

| 资源类型 | 限制 | 管理机制 | 调度器 |
|---------|------|---------|--------|
| Agent 并发 | max 3 | `asyncio.Semaphore(3)` | ParallelScheduler |
| Tool 并发 | max 3 | `asyncio.Semaphore(3)` | ToolScheduler |
| 单任务超时 | 默认 300s | `asyncio.wait_for()` | ParallelScheduler |
| Tool 调用超时 | 默认 60s | `asyncio.wait_for()` | ToolScheduler |
| 批量超时 | 默认 600s | `asyncio.wait(timeout=...)` | ParallelScheduler |
| 内存 | 无硬限制 | 依赖 Python GC | - |

### 8.4 ToolScheduler 核心类设计

```python
class ToolScheduler:
    """Agent 内部的 Tool 并行调度器"""

    def __init__(
        self,
        max_concurrency: int = 3,
        default_timeout: float = 60.0,
    ):
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._default_timeout = default_timeout
        self._execution_history: List[ToolBatchResult] = []

    async def execute_batch(
        self,
        tool_calls: List[ToolCall],
        tool_registry: Dict[str, BaseTool],
        timeout: Optional[float] = None,
    ) -> ToolBatchResult:
        """执行一批 Tool 调用，支持 DAG 依赖"""

    async def execute_single(
        self,
        tool_call: ToolCall,
        tool_registry: Dict[str, BaseTool],
        timeout: Optional[float] = None,
    ) -> ToolCallResult:
        """执行单个 Tool 调用"""

    def _build_dependency_graph(self, tool_calls: List[ToolCall]) -> DependencyGraph:
        """构建依赖图并计算执行批次"""

    def _resolve_placeholders(
        self,
        args: Dict[str, Any],
        previous_outputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """解析参数中的 placeholder"""
```

**关键特性**:
1. **DAG 依赖**: Tool 调用可以声明 `depends_on`，形成有向无环图
2. **拓扑排序**: 自动计算执行批次，同层并行执行
3. **Placeholder 解析**: 支持 `{{call_id.output.field}}` 语法引用前序调用结果
4. **LLM 响应解析**: `parse_tool_calls_from_llm()` 从 LLM 响应提取 tool_calls

## 九、错误处理与恢复策略

### 9.1 错误分类

| 错误类型 | 触发条件 | 处理策略 |
|---------|---------|---------|
| `TaskTimeout` | 单任务超时 | 标记失败，返回超时错误 |
| `BatchTimeout` | 整体超时 | 取消未完成任务，返回部分结果 |
| `AgentError` | Agent 执行异常 | 记录错误，返回失败结果 |
| `ToolError` | Tool 调用失败 | 标记失败，继续执行其他并行 Tool |
| `ResourceExhausted` | 并发上限 | 等待 semaphore，队列排队 |
| `Cancelled` | 用户取消/fail_fast | 返回取消状态 |

### 9.2 恢复策略

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Error Recovery Flow                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Task Failed                                                       │
│       │                                                             │
│       ▼                                                             │
│   ┌─────────────────┐                                              │
│   │ Classify Error  │                                              │
│   └────────┬────────┘                                              │
│            │                                                        │
│   ┌────────┼────────┬────────────────┬──────────────┐            │
│   ▼        ▼        ▼                ▼              ▼            │
│ Timeout  AgentErr  ToolErr        Cancelled      Unexpected       │
│   │        │        │                │              │            │
│   ▼        ▼        ▼                ▼              ▼            │
│ Return   Return   Return          Return        Log + Return    │
│ Error    Error    Error           Cancelled     Generic Error    │
│ Info     Info     Info            Info          Info             │
│   │        │        │                │              │            │
│   └────────┴────────┴────────────────┴──────────────┘            │
│                          │                                         │
│                          ▼                                         │
│              Continue with remaining tasks                         │
│              (if fail_strategy = "continue")                      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 9.3 部分成功处理

```python
# 示例：3 个并行任务，2 成功 1 失败
result_group = ParallelResultGroup(
    group_id="batch_001",
    results=[
        SubagentResult(task_id="t1", from_agent="explorer", success=True, summary="Found 5 files"),
        SubagentResult(task_id="t2", from_agent="planner", success=True, summary="Plan created"),
        SubagentResult(task_id="t3", from_agent="coder", success=False, summary="Failed", error="Syntax error"),
    ],
    success_count=2,
    failure_count=1,
    partial_success=True,
)

# MAIN 决策逻辑
if result_group.partial_success:
    # 使用成功的结果继续
    successful_results = [r for r in result_group.results if r.success]
    failed_results = [r for r in result_group.results if not r.success]

    # 报告失败但继续执行
    logger.warning(f"Partial success: {result_group.success_count}/{len(result_group.results)}")
    for r in failed_results:
        logger.error(f"Task {r.task_id} failed: {r.error}")
```

## 十、实现清单

### 10.1 基础 Schema（已完成）

- [x] 在 `agents/mailbox.py` 中定义 `TaskBrief`、`SubagentResult`、`MailboxMessage` 数据结构（dataclass）；`MailboxMessage.create_task` / `create_result` 工厂方法。
- [x] 在 `Blackboard` 上增加：`post_message(msg)`、`collect_messages(for_agent, type_filter=None)`、`post_result(result)`、`collect_results(for_agent="main")`、`get_latest_task_brief(for_agent)`；内部用 `_mailbox: List[MailboxMessage]` 存储。

### 10.2 并行 Schema（已完成）

- [x] 在 `agents/mailbox.py` 中添加 `ParallelTaskGroup`、`ParallelResultGroup` 数据结构
- [x] 在 `agents/mailbox.py` 中添加 `ToolBatchRequest`、`ToolBatchResult`、`ToolCall`、`ToolCallResult` 数据结构
- [x] 添加 `MailboxMessage.create_batch_task()` / `create_batch_result()` 工厂方法

### 10.3 并行调度器（已完成）

- [x] 创建 `agents/scheduler.py`，实现 `ParallelScheduler` 类（Agent 级调度）
  - [x] `schedule_agent_single()` - 单任务异步执行
  - [x] `schedule_agent_batch()` - 批量并行执行
  - [x] `_agent_semaphore` 并发控制
  - [x] 超时控制和错误处理
  - [x] fail_fast 策略（支持 FIRST_COMPLETED + 取消）
- [x] 创建 `agents/tool_scheduler.py`，实现独立的 `ToolScheduler` 类（Tool 级调度）
  - [x] `execute_batch()` - 批量 Tool 执行
  - [x] `execute_single()` - 单个 Tool 执行
  - [x] DAG 依赖分析 (`_build_dependency_graph`)
  - [x] 拓扑排序分批执行
  - [x] 同层任务并行执行
  - [x] Placeholder 参数解析 (`_resolve_placeholders`)
  - [x] LLM 响应解析 (`parse_tool_calls_from_llm`)

### 10.4 Orchestrator 集成（已完成）

- [x] 重构 `Orchestrator` 为 async/await 模式
- [x] 添加 `dispatch_async()` - 单任务派发（async）
- [x] 添加 `dispatch_parallel_async()` - 并行任务派发（async）
- [x] 集成 `ParallelScheduler` 管理并发资源
- [x] 保持 `dispatch()` 同步接口向后兼容

### 10.5 子代理改造（已完成）

- [x] 各子代理支持异步执行：`async execute_async(task: str) -> EnhancedAgentResult`
- [x] 支持 Mailbox 协议：`async execute_from_mailbox() -> SubagentResult`
- [x] 执行入口支持「从 `blackboard.get_latest_task_brief(自己)` 取任务」
- [x] 执行结束后构造 `SubagentResult` 并 `blackboard.post_result(result)`
- [x] ToolScheduler 可选集成（通过 ParallelScheduler）

### 10.6 测试与文档

- [x] 单元测试：`tests/agents/test_scheduler.py`
  - [x] 单任务执行测试
  - [x] 并行执行测试（全部成功）
  - [x] 并行执行测试（部分失败）
  - [x] 超时测试
  - [x] fail_fast 策略测试
- [x] 集成测试：`tests/agents/test_parallel_workflow.py`
  - [x] 并行 Agent 派发测试
  - [x] Tool 并行调用测试
  - [x] DAG 依赖执行测试
- [x] 更新 `CLAUDE.md` 文档

---

以上为「明确 schema、Blackboard 作 Mailbox、主 Agent 管理员、结构化回传、并行调度」的约定；实现时按此契约落地即可做到「只共享关键信息、定向传递、结果明确可解析、高效并行执行」。
