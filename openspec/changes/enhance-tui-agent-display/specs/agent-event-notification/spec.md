# Spec: Agent Event Notification

## Requirement

系统需要在 Agent 执行的关键节点发送事件通知，以便 TUI 可以实时显示状态。

## Functional Requirements

### FR1: Agent Started Event

当 Agent 开始执行时，必须发送 `agent_started` 事件。

**Event Data:**  
（实现中回调签名为 `(agent_type, "started", None)`，agent_type 为 SubAgentType 枚举。）

- `agent_type`: explorer | planner | coder | reviewer | bash（Tester 功能已由 Bash 子代理融合取代，不单独列出）

**Trigger Points:**
- Orchestrator.dispatch() 创建子代理后
- SubAgent.execute() 方法开始时

### FR2: Agent Completed Event

当 Agent 执行完成时，必须发送 `agent_completed` 事件。

**Event Data:**  
（实现中回调签名为 `(agent_type, "completed", result)`，result 为 EnhancedAgentResult。）

- `agent_type`: explorer | planner | coder | reviewer | bash
- 成功/失败由 result.success 表达

**Trigger Points:**
- SubAgent.execute() 方法返回时
- 无论成功或失败都必须发送

### FR3: Tool Called Event

当工具被调用时，必须发送 `tool_called` 事件。

**Event Data:**
```json
{
  "event": "tool_called",
  "tool_name": "Read|Write|Grep|Glob|Bash|...",
  "args": {"param1": "value1", ...},
  "timestamp": 1234567890.789
}
```

**Trigger Points:**
- 工具执行前
- 仅记录工具名称和参数，不等待结果

### FR4: Tool Completed Event

当工具执行完成时，应该发送 `tool_completed` 事件（可选，因为可能过于频繁）。

**Event Data:**
```json
{
  "event": "tool_completed",
  "tool_name": "Read|Write|Grep|...",
  "success": true|false,
  "result_summary": "结果摘要",
  "timestamp": 1234567890.999
}
```

## Non-Functional Requirements

### NFR1: Performance

事件通知的开销应该小于 10ms，不应该显著影响 Agent 执行速度。

### NFR2: Reliability

事件回调失败不应该影响 Agent 的正常执行。回调异常必须被捕获和记录。

### NFR3: Extensibility

事件系统应该支持未来添加新的事件类型，而不需要修改现有代码。

## Implementation Constraints

1. **Minimal Changes** - 尽量不修改现有的 Agent 执行逻辑
2. **Backward Compatible** - 不影响不使用事件通知的代码
3. **Thread Safe** - 事件回调必须在正确的线程中执行

## Acceptance Criteria

- [ ] Agent 开始时发送 agent_started 事件
- [ ] Agent 完成时发送 agent_completed 事件
- [ ] 工具调用时发送 tool_called 事件
- [ ] 事件回调失败不影响 Agent 执行
- [ ] 单元测试覆盖所有事件类型

## Dependencies

- 依赖 enhanced.py 中的 EventType 和 Event 类
- 依赖 orchestrator 的回调机制

## Open Questions

1. 是否需要限制事件发送频率？（避免过于频繁的工具调用事件）
2. 是否需要在事件中携带完整结果还是仅摘要？
