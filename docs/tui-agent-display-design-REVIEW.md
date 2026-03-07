# TUI Agent Display 设计方案审阅

基于 `docs/tui-agent-display-design.md` 与 OpenSpec change `enhance-tui-agent-display` 的 artifact 进行审阅。

---

## 一、设计要点总结

### 1. 概念区分（文档已明确）

| 概念 | 含义 | TUI 展示 |
|------|------|----------|
| **Agent / 子代理** | Orchestrator 派发的执行主体（Explorer/Planner/Coder/Reviewer/Bash/Tester） | `[Explorer]`、`[Coder]` 等，表示「谁在工作」 |
| **Tool / 工具** | 子代理执行时调用的能力（Read/Write/Grep/Glob/Bash） | `↳ [Tool] Read: path`，表示「当前子代理在用哪些工具」 |

- 子代理 = 谁在做；工具 = 该子代理正在用什么能力。
- 避免把子代理名称与工具名称混淆（如不要把 Planner 当成一种「工具」）。

### 2. 架构

- 事件源：Orchestrator（子代理派发）、SubAgents（工具调用）、LLM Service（Token/上下文）。
- 统一通过 Event Callback 驱动 TUI 显示：子代理名称、工具日志、流转状态。

### 3. Phase 1 范围（MVP + 安全）

- 子代理名称显示与流转（开始/完成）。
- 工具调用实时显示（在当前子代理上下文中）。
- 工作目录配置（config/workdir.yaml）与 TUI header 展示。
- 工作目录访问控制（WorkDirFilter，限制工具只能访问工作目录内）。

### 4. 实现状态（与代码库一致）

- 子代理开始/完成回调和 TUI 显示：已实现。
- 工具回调注册与 Enhanced 系（Planner/Coder/Tester）工具事件：已实现。
- Explorer/Reviewer/Bash 的工具事件：部分未接入（base 系为单次 LLM 调用，无工具环时可先占位）。
- 工作目录配置与 WorkDirFilter：未实现。

---

## 二、疑问点与建议

### 1. OpenSpec design.md 与当前实现已统一

- **已处理**：design.md 已修改为与代码一致，回调签名为 `(agent_type, event_type, result)`，不再使用 event dict；TUI 注册方式与 `on_agent_event(agent_type, event_type, result)` 一致。artifact 与实现单一一致，无二选一。

### 2. Tester 由 Bash 融合取代

- **已处理**：Tester 功能已由 Bash 子代理融合取代，不再作为独立子代理列出。proposal、design、specs 中 agent 列表统一为 Explorer/Planner/Coder/Reviewer/Bash；设计文档中已注明「Tester 已由 Bash 取代」。

### 3. 工具环必要性已评估并列入后续扩展

- **已处理**：在 design.md 中增加「工具环与后续扩展」：Explorer/Reviewer 当前无工具环；若需其也输出工具调用日志，需在后续扩展中实现。Phase 1 不强制，工具环实现列入后续扩展。

### 4. WorkDirFilter 调用时机已明确

- **已处理**：在 workdir-isolation spec 中明确：WorkDirFilter 在 **Read/Write/Glob 等工具执行前** 对路径参数调用 `is_path_allowed(path)`，拒绝则**不执行该工具调用**并返回**明确错误**；并增加「调用时机」小节。

### 5. 子代理结论与 [Tool] 区分已写入 spec

- **已处理**：在 tui-agent-display spec 中新增 FR2.1「子代理结论与工具区分」：工具行用 `[Tool]`，结论行（如 Pass/Reject）可单独标注为「结论」或不同样式，不与 `[Tool]` 混用。

---

## 三、结论与下一步

- **设计方案**：目标清晰，子代理与工具区分明确，Phase 1 范围与优先级合理，与当前实现状态的差异已在文档中说明。
- **疑问点**：以上 5 点均为澄清/一致性改进，无阻塞性矛盾；按建议更新 OpenSpec 与设计文档即可。

**Change 状态**：OpenSpec 中已存在 change **`enhance-tui-agent-display`**（in-progress），无需新建 change。

**建议操作**：

1. **不新建 change**，在现有 **`enhance-tui-agent-display`** 下继续实现。
2. **同步设计到 OpenSpec**（可选）：
   - 在 **proposal.md** 或 **design.md** 中增加「Agent（子代理）与 Tool（工具）概念区分」简短小节；
   - 在 **specs/agent-event-notification/spec.md** 中注明 agent_type 包含 `tester`；
   - 在 **tasks.md** 中明确 Explorer/Reviewer 的 event_callback 为占位、以及 WorkDirFilter 的集成方式。
3. 按 **docs/tui-agent-display-design.md** 的「后续开发方案」步骤 1～4 在现有 change 下逐项实现与验收。

如需，我可以根据上述建议直接修改 OpenSpec 下各 artifact 的文案（不写业务代码）。
