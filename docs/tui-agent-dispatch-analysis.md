# TUI 未体现 Agent 派发与流转记录的原因分析

## 1. 问题现象

- 对话中始终显示 **Main ▶**，没有出现 Explorer / Planner / Coder 等子 agent 的切换或派发提示。
- 用户说「切换成 code agent」时，模型仅用自然语言“扮演”切换，没有触发内部 agent 派发。
- 设计中要求的「记录 agent 流转」是否实现存疑。

## 2. 假设（待运行时验证）

| 假设 | 内容 |
|------|------|
| **H1** | TUI 主循环只调用了 `LLMService.chat_stream(user_input)`，从未创建或调用 `WorkflowOrchestrator`，因此不会发生 agent 派发。 |
| **H2** | `on_agent_event` 只有在注册到 orchestrator 后才会被调用；TUI 启动路径中从未创建或传入 orchestrator，因此该回调从未被触发。 |
| **H3** | `agent_history` 与 `/agents` 展示逻辑已实现，但因 orchestrator 未接入，`on_agent_event` 从未执行，故 agent 流转记录始终为空。 |
| **H4** | 「切换成 code agent」等请求被当作普通用户消息直接发给 LLM，没有经过意图分析或 dispatch，因此不会触发任何内部 agent 切换。 |
| **H5** | 「记录 agent 流转」在代码里已实现（`UIState.agent_history` + `on_agent_event` + `_display_agent_history`），但因 TUI 未与 orchestrator 集成，该功能在 TUI 下从未生效。 |

## 3. 代码路径结论（已确认）

### 3.1 TUI 请求路径

- **入口**: `python -m mini_coder.tui` → `tui/__main__.py` → `MiniCoderTUI(config).run()` → `MiniCoderConsole.run()`。
- **主循环** (`console_app.py` 约 927–980 行):  
  获取用户输入 → `_handle_special_commands()` → **仅调用** `_call_llm_stream_and_display(user_input)`。
- **`_call_llm_stream_and_display`** (约 438–497 行):  
  直接 `for event in self._llm_service.chat_stream(user_input)`，**没有任何** `WorkflowOrchestrator`、`dispatch()` 或 `execute_workflow()` 的调用。

因此：**TUI 下所有用户输入都只走了「单 LLM 流式对话」路径，没有经过多 agent 编排。**

### 3.2 Orchestrator 在哪里被使用

- **agents/cli.py**: `run_interactive_mode` / `run_batch_mode` 会创建 `WorkflowOrchestrator` 并调用 `execute_workflow(requirement)`，这是**命令行 agent 入口**，不是 TUI。
- **TUI**: 仅通过 `register_agent_callback(orchestrator)` 预留了「若有人传入 orchestrator 则注册回调」的能力，但 **TUI 启动与主循环中从未创建或传入 orchestrator**，因此：
  - `self._orchestrator` 始终为 `None`；
  - `on_agent_event` / `on_tool_called` 从未被调用；
  - `agent_history` 不会被写入，`/agents` 看到的始终为空。

### 3.3 Agent 流转记录功能是否存在

- **有实现**:
  - `UIState.agent_history`（约 103 行）、`UIState.tool_logs`（约 104 行）；
  - `on_agent_event()`（约 771–806 行）会向 `agent_history` 追加 `{agent, status, timestamp}`；
  - `on_tool_called()` 会向 `tool_logs` 追加工具调用记录；
  - `/agents` 命令调用 `_display_agent_history()`（约 876 行）展示最近 5 条 agent 历史。
- **未生效原因**: 上述逻辑依赖 orchestrator 在派发子 agent 时调用这些回调；TUI 未接入 orchestrator，故**从未触发**，流转记录在 TUI 下一直为空。

## 4. 小结

| 问题 | 结论 |
|------|------|
| 为什么对话中没有体现 agent 切换/派发？ | TUI 主流程只调用了 `LLMService.chat_stream()`，没有经过 `WorkflowOrchestrator.dispatch()` 或 `execute_workflow()`，因此不会出现子 agent 派发或切换。 |
| 设计中「记录 agent 流转」是否有？ | 有。`agent_history` + `on_agent_event` + `/agents` 展示已实现，但因 TUI 未与 orchestrator 集成，该功能在 TUI 下从未被触发，等价于未生效。 |

## 5. 建议改动方向（非本次实现）

- 在 TUI 中增加「多 agent 模式」：在合适入口（例如配置或启动参数）创建 `WorkflowOrchestrator`，并将用户消息先经意图分析/派发，再决定是走 `orchestrator.dispatch()` 还是直接 `chat_stream()`；同时在该路径下调用 `register_agent_callback(orchestrator)`，这样 `on_agent_event` 会被触发，`agent_history` 与 `/agents` 才会出现流转记录。
