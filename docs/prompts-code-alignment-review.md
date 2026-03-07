# 提示词与代码逻辑对齐核对

本文档核对优化后的 agents/tools 提示词中的**占位符**与**结构化输出**是否与代码中的注入/解析一致。

---

## 一、占位符与注入

### 1. 工具提示词 `prompts/tools/command.md`

| 占位符 | 提示词中用法 | 代码注入位置 | 结论 |
|--------|--------------|--------------|------|
| `{{security_mode}}` | 当前模式（strict \| normal \| trust） | `CommandTool._get_prompt_context()` → `mode.value` | ✅ 一致 |
| `{{timeout}}` | 超时（秒） | `_get_prompt_context()` → `self._executor.timeout` | ✅ 一致 |
| `{{max_output_length}}` | 最大输出字符数 | `_get_prompt_context()` → `self._executor.max_output_length` | ✅ 一致 |
| `{{allowed_paths}}` | 允许路径 | `_get_prompt_context()` → `self._executor.allowed_paths` 转字符串 | ✅ 一致 |

注入路径：调用 `CommandTool.get_system_prompt(context)` 时，内部合并 `_get_prompt_context()` 与传入的 `context`，再交给 `PromptLoader.load(path, context)` 做 `{{key}}` 替换。

### 2. 子代理提示词 `{{work_dir}}`

| 提示词文件 | 占位符 | 代码注入位置 | 结论 |
|------------|--------|--------------|------|
| `subagent-coder.md` | `{{work_dir}}` | `CoderAgent._build_coding_prompt()`：`work_dir = self.blackboard.get_context("work_dir")`，再 `_load_system_prompt(context={"work_dir": ...})` | ✅ 一致 |
| `subagent-planner.md` | `{{work_dir}}` | `PlannerAgent._build_planning_prompt()` 仅调用 `_load_system_prompt()`，**未传 context** | ❌ 未注入 |
| `subagent-explorer.md` | `{{work_dir}}` | `ExplorerAgent` 在 `_invoke_llm()` 中 `get_system_prompt(context=invoke_context)`，但 `invoke_context` 来自 `kwargs.pop("_prompt_context", None)`，而 `execute()` 未传 `_prompt_context`；且 orchestrator 调用 `execute(intent, context=None)`，未传含 work_dir 的 context | ❌ 未注入 |

**修复建议**（见下文代码修改）：

- **Planner**：在 `_build_planning_prompt()` 中从 blackboard 读取 `work_dir`，并传入 `_load_system_prompt(context={"work_dir": work_dir})`。
- **Explorer**：① orchestrator 在 `dispatch`/`dispatch_with_agent` 中从 blackboard 取 `work_dir`，构造 `context={"work_dir": ...}` 并传入 `agent.execute(intent, context=context)`；② `ExplorerAgent.execute()` 中调用 `_invoke_llm(user_prompt, _prompt_context=context or {})`，使加载系统提示时能替换 `{{work_dir}}`。

---

## 二、结构化输出与解析

### 1. 主代理 `main-agent.md`

| 输出块 | 解析器 | 代码位置 | 结论 |
|--------|--------|----------|------|
| 【简单回答】 | `MainAgentParser.SIMPLE_ANSWER_PATTERN` | `output_parser.py` | ✅ 一致 |
| 【复杂任务】 | `COMPLEX_TASK_PATTERN` + `SUBTASK_PATTERN`（问题类型、拆解子问题、交由：代理名） | 同上 | ✅ 一致 |
| 【无法处理】 | `CANNOT_HANDLE_PATTERN` | 同上 | ✅ 一致 |

子任务正则：`(\d+)[.、．]\s*(.+?)\s*(→|->)\s*交由[：:]\s*([A-Z_]+)`，与提示词中「1. <子问题> → 交由：<子代理名>」一致。

### 2. Reviewer `subagent-reviewer.md`

| 输出块 | 解析器 | 代码位置 | 结论 |
|--------|--------|----------|------|
| [Pass] | `ReviewerParser.PASS_PATTERN` | `output_parser.py` | ✅ 一致 |
| [Reject] | `REJECT_PATTERN` + `ISSUE_PATTERN`（序号、[架构|质量|风格]、路径:行号、描述、建议） | 同上 | ✅ 一致 |

Reviewer 的 `_parse_review_result()`（enhanced.py / base.py）通过 `"[Pass]" in r` / `"[Reject]" in r` 判断，与提示词约定一致。

### 3. Bash `subagent-bash.md`

| 输出块 | 解析器 | 代码位置 | 结论 |
|--------|--------|----------|------|
| 【质量报告】 | `QualityReportParser.REPORT_PATTERN` | `output_parser.py` | ✅ 一致 |
| ## 测试结果 / 类型检查 / 代码风格 / 覆盖率 / 其他 | `SECTION_PATTERN` 按小节名解析 | 同上 | ✅ 一致 |

小节名与提示词完全一致。

### 4. 其他子代理（Coder / Explorer / Planner / GeneralPurpose / Mini-Coder Guide）

【实现结果】、【探索结果】、implementation_plan.md、【分析结果】、【指南回答】目前**无专用解析器**，输出以展示或人工阅读为主；代码中仅引用 artifact（如 `implementation_plan.md`）或直接使用原始文本。与“仅约定格式、不强制解析”的设计一致，无需改代码。

### 5. Command 工具返回值

提示词约定语义：`stdout`、`stderr`、`exit_code`、`execution_time_ms`。  
代码中 `CommandTool.run()` 返回 `ToolResponse.success(text=stdout+stderr, data={"command", "exit_code", "execution_time_ms"})`，语义一致；实际字段名以 `ToolResponse.data` 为准，提示词描述为“由工具实现保证”的语义说明，✅ 一致。

---

## 三、已修复的代码改动

1. **Planner 注入 work_dir**：`PlannerAgent._build_planning_prompt()` 中从 `self.blackboard.get_context("work_dir")` 取值并传入 `_load_system_prompt(context={"work_dir": ...})`。
2. **Orchestrator 传递 context**：在 `dispatch()` 与 `dispatch_with_agent()` 中，若 blackboard 存在 `work_dir`，则构造 `context = {"work_dir": self._context.blackboard.get_context("work_dir")}`，并传给 `agent.execute(intent, context=context)`（对非 Enhanced 系 agent）。
3. **Explorer 使用 context 加载系统提示**：`ExplorerAgent.execute()` 中调用 `_invoke_llm(user_prompt, _prompt_context=context or {})`，使 `get_system_prompt(context=invoke_context)` 收到 work_dir，从而替换 `subagent-explorer.md` 中的 `{{work_dir}}`。

---

## 四、小结

| 类别 | 状态 |
|------|------|
| 工具占位符（command.md） | ✅ 与 `_get_prompt_context()` 一致 |
| Coder work_dir | ✅ 已注入 |
| Planner / Explorer work_dir | ❌→✅ 已通过上述修改注入 |
| 主代理 / Reviewer / Bash 结构化输出 | ✅ 与现有解析器一致 |
| 其他子代理结构化输出 | ✅ 仅展示用，无解析器，符合设计 |
| Command 返回值语义 | ✅ 与 ToolResponse 一致 |
