# Spec: Parallel Tool Execution

## ADDED Requirements

### Requirement: Tool DAG Execution

Tool 调用支持声明依赖关系，按 DAG 拓扑序执行。

#### Scenario: DAG dependency resolution

- **GIVEN** 三个 Tool 调用:
  - ToolCall A: 无依赖
  - ToolCall B: 依赖 A
  - ToolCall C: 依赖 A
- **WHEN** 执行批量调用
- **THEN** A 首先执行
- **AND** B 和 C 并行执行（在 A 完成后）

#### Scenario: Circular dependency detection

- **GIVEN** Tool 调用存在循环依赖:
  - ToolCall A 依赖 B
  - ToolCall B 依赖 A
- **WHEN** 执行批量调用
- **THEN** 系统检测到循环依赖
- **AND** 强制按原顺序执行（降级处理）
- **AND** 记录警告日志

#### Scenario: Multi-level DAG

- **GIVEN** 四层依赖关系:
  - Layer 0: [A]
  - Layer 1: [B, C] (依赖 A)
  - Layer 2: [D] (依赖 B, C)
- **WHEN** 执行批量调用
- **THEN** 按层级顺序执行
- **AND** 同层调用并行执行

### Requirement: Tool Placeholder Resolution

支持在参数中引用其他 Tool 调用的输出。

#### Scenario: Simple placeholder

- **GIVEN** ToolCall 1 返回 `{"main": "app.py"}`
- **AND** ToolCall 2 参数为 `{"path": "{{1.output.main}}"}`
- **WHEN** 执行 ToolCall 2
- **THEN** 参数解析为 `{"path": "app.py"}`

#### Scenario: Nested path placeholder

- **GIVEN** ToolCall 1 返回 `{"config": {"paths": {"src": "/src"}}}`
- **AND** ToolCall 2 参数为 `{"path": "{{1.output.config.paths.src}}"}`
- **WHEN** 执行 ToolCall 2
- **THEN** 参数解析为 `{"path": "/src"}`

#### Scenario: List index placeholder

- **GIVEN** ToolCall 1 返回 `["file1.py", "file2.py", "file3.py"]`
- **AND** ToolCall 2 参数为 `{"path": "{{1.output[0]}}"}`
- **WHEN** 执行 ToolCall 2
- **THEN** 参数解析为 `{"path": "file1.py"}`

### Requirement: Tool Concurrency Control

Tool 调用并发数受 Semaphore 控制。

#### Scenario: Semaphore limiting

- **GIVEN** `ToolScheduler(max_concurrency=2)`
- **AND** 5 个无依赖的 Tool 调用
- **WHEN** 执行批量调用
- **THEN** 最多 2 个 Tool 同时执行

#### Scenario: Concurrency validation

- **GIVEN** 尝试创建 `ToolScheduler(max_concurrency=5)`
- **WHEN** 初始化
- **THEN** 抛出 `ValueError`
- **AND** 错误信息包含 "max_concurrency must be 1-3"

### Requirement: Tool Timeout

每个 Tool 调用支持超时控制。

#### Scenario: Single tool timeout

- **GIVEN** `ToolScheduler(default_timeout=1.0)`
- **AND** Tool 执行耗时 5 秒
- **WHEN** 调用 `execute_single`
- **THEN** 1 秒后超时
- **AND** 返回 `ToolCallResult(success=False, error="Timeout after 1.0s")`

### Requirement: LLM Response Parsing

支持从 LLM 响应解析 Tool 调用。

#### Scenario: OpenAI format parsing

- **GIVEN** LLM 响应:
  ```json
  {
    "tool_calls": [
      {"id": "call_1", "function": {"name": "Read", "arguments": {"path": "file.py"}}}
    ]
  }
  ```
- **WHEN** 调用 `ToolScheduler.parse_tool_calls_from_llm(response)`
- **THEN** 返回 `[ToolCall(call_id="call_1", tool_name="Read", arguments={"path": "file.py"})]`

#### Scenario: Anthropic format parsing

- **GIVEN** LLM 响应:
  ```json
  {
    "content": [
      {"type": "tool_use", "id": "call_1", "name": "Read", "input": {"path": "file.py"}}
    ]
  }
  ```
- **WHEN** 调用 `ToolScheduler.parse_tool_calls_from_llm(response)`
- **THEN** 返回 `[ToolCall(call_id="call_1", tool_name="Read", arguments={"path": "file.py"})]`