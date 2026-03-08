# Spec: Parallel Agent Dispatch

## ADDED Requirements

### Requirement: Agent Parallel Execution

系统支持并行派发多个子代理任务，由 ParallelScheduler 统一管理并发。

#### Scenario: Parallel dispatch with semaphore control

- **GIVEN** Orchestrator 配置 `max_agent_concurrency=3`
- **WHEN** 派发 5 个独立的 Agent 任务
- **THEN** 最多 3 个 Agent 同时执行
- **AND** 剩余任务等待信号量释放后执行

#### Scenario: Partial success handling

- **GIVEN** 派发 3 个 Agent 任务
- **WHEN** 其中 1 个任务失败，其余成功
- **AND** `fail_strategy=continue`
- **THEN** 返回 `ParallelResultGroup` 包含 `success_count=2, failure_count=1`
- **AND** `partial_success=True`

#### Scenario: Fail fast strategy

- **GIVEN** 派发 3 个 Agent 任务
- **WHEN** 其中 1 个任务失败
- **AND** `fail_strategy=fail_fast`
- **THEN** 立即取消其他正在执行的任务
- **AND** 返回部分结果

### Requirement: Agent Task Timeout

每个 Agent 任务支持独立的超时控制。

#### Scenario: Single task timeout

- **GIVEN** 设置 `timeout=30.0` 秒
- **WHEN** Agent 执行超过 30 秒
- **THEN** 任务被取消
- **AND** 返回 `SubagentResult` 包含 `success=False, error="Timeout"`

#### Scenario: Batch task timeout

- **GIVEN** `ParallelTaskGroup.timeout_per_task=30.0`
- **AND** `ParallelTaskGroup.timeout_total=120.0`
- **WHEN** 批量执行任务
- **THEN** 单任务超时触发单任务取消
- **AND** 总超时触发所有未完成任务取消

### Requirement: Agent Type Inference

系统根据任务意图自动推断 Agent 类型。

#### Scenario: Infer explorer agent

- **GIVEN** 任务意图包含 "探索" 或 "explore" 关键词
- **WHEN** 派发任务
- **THEN** 自动选择 ExplorerAgent

#### Scenario: Infer coder agent

- **GIVEN** 任务意图包含 "实现" 或 "implement" 关键词
- **WHEN** 派发任务
- **THEN** 自动选择 CoderAgent

### Requirement: Task Cancellation

支持取消正在运行的任务。

#### Scenario: Cancel single task

- **GIVEN** Agent 任务正在执行
- **WHEN** 调用 `scheduler.cancel_task(task_id)`
- **THEN** 该任务被取消
- **AND** 返回 `True`

#### Scenario: Cancel all tasks

- **GIVEN** 3 个 Agent 任务正在执行
- **WHEN** 调用 `scheduler.cancel_all()`
- **THEN** 所有任务被取消
- **AND** 返回取消数量 `3`