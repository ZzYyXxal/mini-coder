# Spec: Mailbox Batch Protocol

## ADDED Requirements

### Requirement: ParallelTaskGroup Schema

批量并行任务派发的结构化消息协议。

#### Scenario: Create parallel task group

- **GIVEN** 3 个任务:
  - TaskBrief(task_id="task_1", intent="探索代码")
  - TaskBrief(task_id="task_2", intent="规划方案")
  - TaskBrief(task_id="task_3", intent="实现功能")
- **WHEN** 创建 `ParallelTaskGroup(group_id="batch_001", tasks=[...])`
- **THEN** 生成有效的 `ParallelTaskGroup` 实例
- **AND** 默认 `max_concurrency=3, timeout_per_task=300.0`

#### Scenario: Invalid concurrency validation

- **GIVEN** 尝试创建 `ParallelTaskGroup(max_concurrency=5)`
- **WHEN** 初始化
- **THEN** 抛出 `ValueError`
- **AND** 错误信息包含 "max_concurrency must be 1-3"

#### Scenario: Invalid fail strategy validation

- **GIVEN** 尝试创建 `ParallelTaskGroup(fail_strategy="unknown")`
- **WHEN** 初始化
- **THEN** 抛出 `ValueError`
- **AND** 错误信息包含 "Invalid fail_strategy"

### Requirement: ParallelResultGroup Schema

批量并行任务结果的汇总结构。

#### Scenario: Create result group

- **GIVEN** 3 个任务结果:
  - 2 个成功，1 个失败
- **WHEN** 创建 `ParallelResultGroup`
- **THEN** `success_count=2, failure_count=1`
- **AND** `partial_success=True`

#### Scenario: All success result

- **GIVEN** 3 个任务全部成功
- **WHEN** 创建 `ParallelResultGroup`
- **THEN** `success_count=3, failure_count=0`
- **AND** `partial_success=False`

### Requirement: ToolBatchRequest Schema

Tool 批量调用请求的结构化消息。

#### Scenario: Create tool batch request

- **GIVEN** 3 个 Tool 调用
- **WHEN** 创建 `ToolBatchRequest(batch_id="batch_001", tool_calls=[...])`
- **THEN** 生成有效的 `ToolBatchRequest` 实例
- **AND** 默认 `max_concurrency=3, timeout_per_call=60.0`

#### Scenario: Tool batch with dependencies

- **GIVEN** Tool 调用带依赖关系:
  - ToolCall(call_id="1", depends_on=[])
  - ToolCall(call_id="2", depends_on=["1"])
- **WHEN** 创建 `ToolBatchRequest`
- **THEN** 依赖关系被正确保存

### Requirement: ToolBatchResult Schema

Tool 批量调用结果的结构化消息。

#### Scenario: Create tool batch result

- **GIVEN** 3 个 Tool 调用结果
- **WHEN** 创建 `ToolBatchResult`
- **THEN** 包含 `batch_id, results, success_count, failure_count, elapsed_time`

### Requirement: MailboxMessage Integration

Mailbox 消息支持批量协议类型。

#### Scenario: Create batch_task message

- **GIVEN** `ParallelTaskGroup` 实例
- **WHEN** 调用 `MailboxMessage.create_batch_task(group)`
- **THEN** 返回 `MailboxMessage(type="batch_task", payload={...})`

#### Scenario: Create batch_result message

- **GIVEN** `ParallelResultGroup` 实例
- **WHEN** 调用 `MailboxMessage.create_batch_result(result_group)`
- **THEN** 返回 `MailboxMessage(type="batch_result", payload={...})`

#### Scenario: Parse batch_task from message

- **GIVEN** `MailboxMessage(type="batch_task")`
- **WHEN** 调用 `message.get_parallel_task_group()`
- **THEN** 返回解析后的 `ParallelTaskGroup` 实例

#### Scenario: Parse batch_result from message

- **GIVEN** `MailboxMessage(type="batch_result")`
- **WHEN** 调用 `message.get_parallel_result_group()`
- **THEN** 返回解析后的 `ParallelResultGroup` 实例