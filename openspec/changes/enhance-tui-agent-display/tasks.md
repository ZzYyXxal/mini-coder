# Tasks: Enhance TUI Agent Display

## Phase 1: MVP + 安全

### 1. Event System Extension

- [ ] 1.1 在 `enhanced.py` 中添加新的 EventType:
  - `AGENT_STARTED`
  - `AGENT_COMPLETED`
  - `TOOL_STARTING`
  - `TOOL_COMPLETED`
- [ ] 1.2 在 `BaseEnhancedAgent.execute()` 中发送事件
- [ ] 1.3 在工具调用时发送事件
- [ ] 1.4 编写 EventType 单元测试

### 2. Orchestrator State Callback

- [ ] 2.1 在 `orchestrator.py` 中添加 `_agent_callbacks` 列表
- [ ] 2.2 实现 `register_agent_callback()` 方法
- [ ] 2.3 在 `dispatch()` 中调用回调
- [ ] 2.4 实现 `_notify_agent_started()` 和 `_notify_agent_completed()`
- [ ] 2.5 编写回调单元测试

### 3. TUI Agent Display

- [ ] 3.1 修改 `console_app.py`:
  - 添加 `AgentDisplay` 枚举（替换 WorkingMode）
  - 添加 `_current_agent` 状态
  - 添加 `_tool_logs` 列表
- [ ] 3.2 实现 `on_agent_started()` 回调
- [ ] 3.3 实现 `on_tool_called()` 回调
- [ ] 3.4 更新输入提示符显示 Agent 名称
- [ ] 3.5 编写 TUI 显示测试

### 4. Tool Logging

- [ ] 4.1 在工具调用时打印日志
- [ ] 4.2 工具日志缩进显示
- [ ] 4.3 添加时间戳
- [ ] 4.4 支持简洁/详细模式切换

### 5. Working Directory Configuration

- [ ] 5.1 创建 `config/workdir.yaml` 配置文件
- [ ] 5.2 实现工作目录选择逻辑：
  - 读取默认路径
  - 读取上次记录
  - 启动时询问（如需要）
- [ ] 5.3 在 TUI header 显示工作目录
- [ ] 5.4 编写配置文件测试

### 6. Access Control Implementation

- [ ] 6.1 在 `filter.py` 中实现 `WorkDirFilter` 类
- [ ] 6.2 实现路径检查逻辑
- [ ] 6.3 实现 denied patterns 检查
- [ ] 6.4 集成到 Read/Write/Glob 工具
- [ ] 6.5 编写访问控制单元测试

### 7. Integration and Testing

- [ ] 7.1 集成测试：完整工作流（Explorer → Bash）
- [ ] 7.2 测试 Agent 流转显示
- [ ] 7.3 测试工具日志显示
- [ ] 7.4 测试工作目录隔离
- [ ] 7.5 测试访问控制（拒绝工作目录外访问）
- [ ] 7.6 修复发现的 bug

## Phase 2: Debug 功能（后续）

### 8. Context Display

- [ ] 8.1 在 `LLMService` 中实现 `get_context_stats()` 方法
- [ ] 8.2 在 TUI 中实现 `/context` 命令
- [ ] 8.3 显示 Token 使用情况
- [ ] 8.4 显示上下文组成

### 9. Debug Mode

- [ ] 9.1 实现 `/debug` 命令切换详细模式
- [ ] 9.2 Debug 模式下显示 LLM 调用详情
- [ ] 9.3 Debug 模式下显示完整上下文

### 10. Log File

- [ ] 10.1 创建 `tui/logger.py` 日志记录器
- [ ] 10.2 实现 JSONL 格式日志
- [ ] 10.3 实现 `/logs` 命令查看日志
- [ ] 10.4 编写日志测试

## Phase 3: 增强显示（可选）

### 11. Agent Flow Visualization

- [ ] 11.1 实现 ASCII 流程图
- [ ] 11.2 标记已完成/失败/进行中的 Agent
- [ ] 11.3 支持回退显示

### 12. Token Dashboard

- [ ] 12.1 实时 Token 使用统计
- [ ] 12.2 预警提示（超过 80%）
- [ ] 12.3 自动压缩建议

### 13. Settings UI

- [ ] 13.1 实现 `/settings` 命令
- [ ] 13.2 配置显示选项
- [ ] 13.3 保存用户偏好

## Documentation

- [ ] 14.1 更新 CLAUDE.md 添加新 Agent 显示说明
- [ ] 14.2 创建使用示例文档
- [ ] 14.3 更新 README.md 添加截图

## Definition of Done

- [ ] 所有 Phase 1 任务完成
- [ ] 单元测试通过率 >= 80%
- [ ] 集成测试通过
- [ ] 无严重 bug
- [ ] 文档完整
