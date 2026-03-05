# Spec: TUI Agent Display

## Requirement

TUI 需要实时显示当前正在执行的 Agent 名称和工具调用情况，替换现有的 PLAN/CODE/EXECUTE 模式显示。

## Functional Requirements

### FR1: Current Agent Display

在用户输入提示符中显示当前 Agent 名称。

**Display Format:**
```
[Explorer] ▶ 用户输入...
[Planner] ▶ 用户输入...
[Coder] ▶ 用户输入...
```

**Behavior:**
- 默认显示 `Unknown` 或 `Ready`
- Agent 开始时更新为对应名称
- Agent 完成后保持显示，直到下一个 Agent 开始

### FR2: Agent Flow Log

在 TUI 中显示 Agent 流转日志。

**Display Format:**
```
[10:23:45] [Explorer] 开始执行
[10:23:46]   ↳ [Tool] Grep: "def authenticate"
[10:23:47]   ↳ [Tool] Read: src/auth.py
[10:23:50] [Explorer] ✓ 完成

[10:23:50] [Planner] 开始执行
[10:23:55] [Planner] ✓ 完成
```

**Behavior:**
- 每条日志带时间戳
- 工具调用缩进显示
- 完成状态用 ✓/✗ 标记

### FR3: Header Information

在 TUI header 中显示工作目录信息。

**Display Format:**
```
╭────── mini-coder ──────╮
│ Work Dir: ~/projects/x │
╰────────────────────────╯
```

**Behavior:**
- 启动时显示工作目录
- 工作目录改变时更新

### FR4: Debug Mode Toggle

支持 `/context` 命令显示上下文信息。

**Display Format:**
```
Context:
- Tokens: 22.5k / 128k (18% used)
- Messages: 12
- System: 2k | History: 8k | Code: 12.5k
```

## Non-Functional Requirements

### NFR1: Readability

显示应该清晰易读，不应该过于拥挤。

### NFR2: Responsiveness

显示更新应该及时，不应该有明显延迟。

### NFR3: Configurable

用户应该能够选择是否显示详细信息。

## Implementation Constraints

1. **Rich Console** - 使用现有的 Rich 框架
2. **Backward Compatible** - 保留现有的 WorkingMode 作为 fallback
3. **Cross-platform** - 支持 Linux/macOS/Windows 终端

## Acceptance Criteria

- [ ] TUI 中显示当前 Agent 名称
- [ ] Agent 流转日志正确显示
- [ ] 工具调用实时显示
- [ ] Header 显示工作目录
- [ ] /context 命令显示上下文信息

## Dependencies

- 依赖 agent-event-notification spec 的事件
- 依赖 Rich 框架

## Open Questions

1. 是否需要颜色区分不同的 Agent？
2. 是否需要可配置的日志级别（简洁/详细）？
