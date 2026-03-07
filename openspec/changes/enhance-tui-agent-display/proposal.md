# Proposal: Enhance TUI Agent Display

## Problem Statement

当前 TUI 显示存在以下问题：

1. **显示的是模式而非 Agent** - TUI 显示 PLAN/CODE/EXECUTE 模式，但用户无法知道实际是哪个 Agent 在处理请求
2. **缺少 Agent 流转可视化** - 用户看不到子代理之间的切换过程（Explorer → Planner → Coder → Reviewer → Bash；注：Tester 功能已由 Bash 子代理融合取代）
3. **缺少工具使用显示** - 用户看不到正在使用的工具（Read/Grep/Bash 等）
4. **缺少上下文信息** - 没有 Token 使用、上下文组成等信息显示
5. **缺少工作目录隔离** - mini-coder 可能读取/修改自身代码，存在安全隐患

## Goals

### Phase 1: MVP + 安全（本 change 范围）

- [ ] 显示当前子代理名称（Explorer/Planner/Coder/Reviewer/Bash；Tester 已由 Bash 取代）
- [ ] 显示子代理流转过程（开始/完成状态）
- [ ] 显示正在使用的工具（工具调用日志）
- [ ] 工作目录隔离和显示

### Phase 2: Debug 功能（后续 change）

- [ ] /context 命令显示 Token 使用情况
- [ ] Debug 模式切换（/debug 命令）
- [ ] 执行日志文件（JSONL 格式）

### Phase 3: 增强显示（可选）

- [ ] Agent 流程图可视化
- [ ] 实时 Token 仪表板
- [ ] TUI 配置界面

## Scope

### In Scope (Phase 1)

1. **Agent 状态事件** - 在 Agent 执行开始时发送事件
2. **状态回调机制** - Orchestrator 支持注册状态回调
3. **TUI Agent 显示** - 替换 WorkingMode 为 Agent 名称显示
4. **工具调用日志** - 实时显示工具调用
5. **工作目录配置** - config/workdir.yaml
6. **访问控制** - 限制 Agent 只能访问工作目录

### Out of Scope

- 复杂的 UI 组件（进度条、流程图）
- Token 使用统计显示
- 日志文件记录
- 配置界面

## Success Criteria

1. 用户在 TUI 中可以看到当前是哪个 Agent 在处理
2. 用户可以看到 Agent 流转过程（A 完成 → B 开始）
3. 用户可以看到正在使用的工具和参数
4. 工作目录隔离生效，工具无法访问工作目录外的路径（执行前校验，拒绝则返回明确错误）

## Stakeholders

- **Users** - 使用 mini-coder TUI 的开发者
- **Developers** - 需要维护和调试 TUI 显示

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| 事件系统复杂化 | 中 | 保持简单，仅添加必要事件 |
| TUI 显示过多信息 | 低 | 默认简洁模式，可选详细 |
| 工作目录隔离破坏现有功能 | 中 | 逐步测试，确保兼容性 |

## Timeline Estimate

- Proposal: 1 session
- Design: 1 session
- Implementation: 3-4 sessions
- Testing: 1 session
