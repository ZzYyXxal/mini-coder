# Reviewer 无法访问工作目录：工具调用方式分析与修改建议

## 1. 现象

用户输入「review 当前目录下的所有文件，给出意见」时，Reviewer 返回：

- 缺少 Implementation Plan，无法进行架构一致性校验
- Code to Review 部分为空，且作为 AI 助手无法直接访问您本地文件系统中的「当前目录」

## 2. 当前工具调用方式（TUI dispatch 路径）

### 2.1 实际执行路径

- TUI 使用 **Orchestrator.dispatch()**，按路由派发到 **base.ReviewerAgent**（`src/mini_coder/agents/base.py`）。
- **不经过** LangGraph 的 `graph/runner.py` 或 `graph/nodes.py`。

### 2.2 ReviewerAgent 实际行为

- `ReviewerAgent.execute(task, context=dispatch_context)` 只做：
  1. 用 `_build_reviewer_prompt(task, context)` 拼 prompt，**仅使用** `context.get("plan")` 和 `context.get("code")`；
  2. **一次** `_invoke_llm(user_prompt)`，无任何工具调用；
  3. 解析响应中的 `[Pass]` / `[Reject]` 并返回。

- 虽然定义了 `ReviewerCapabilities(allowed_tools={"Read", "Glob", "Grep"})`，但 **execute() 内没有任何「把工具暴露给 LLM + 执行 tool_calls」的逻辑**，因此模型无法主动发起 Read/Glob/Grep。

- **work_dir** 虽在 `dispatch_context` 中传入（来自 blackboard），但 **未被使用**：`_build_reviewer_prompt` 不读 `context.get("work_dir")`，也没有在 code 为空时根据 work_dir 去读文件。

### 2.3 上下文注入来源

- `_inject_reviewer_context(dispatch_context)` 只从 **blackboard** 取：
  - `implementation_plan.md` → `dispatch_context["plan"]`
  - 类型为 code 的 artifacts → `dispatch_context["code"]`
- 若用户未先跑 Coder/Planner，blackboard 无 code 工件 → **code 为空**；
- **没有任何**「当 code 为空时，根据 work_dir 读取当前目录文件并注入 code」的兜底逻辑。

## 3. 与 LangGraph 常规工具调用方式对比

| 维度           | LangGraph 常规方式                          | 当前 TUI 下 Reviewer（base.ReviewerAgent）     |
|----------------|---------------------------------------------|-----------------------------------------------|
| 工具暴露       | 模型通过 `bind_tools(tools)` 可输出 tool_calls | 无；仅一次 prompt + 一次 LLM，无工具绑定      |
| 工具执行       | 图中有 tool 节点或 prebuilt ReAct 执行工具   | 无工具执行循环                                |
| 工作目录       | 通过 state（如 `project_path`）传入节点/工具  | work_dir 在 context 中但未被使用              |
| 数据来源       | 模型可多次调用 Read/Glob，结果进 state/messages | 仅依赖 context["plan"] / context["code"] 预填 |

**结论**：当前 TUI 下 Reviewer 的「工具调用」方式与 LangGraph 常规的 **model + tools + 循环执行** **不一致**。Reviewer 实质是「单轮、无工具」的 LLM 调用，完全依赖预先注入的 plan/code，因此无法主动访问工作目录。

## 4. 修改建议

### 4.1 方案 A：编排层在 code 为空时按 work_dir 预读文件（推荐先做）

**思路**：不改变 Reviewer「单轮 LLM、无工具」的现状，在派发前把「当前目录下待评审内容」读好并注入，使模型能直接看到内容。

**实现要点**：

- 在 **Orchestrator._inject_reviewer_context** 中（或单独方法，在 dispatch 前调用）：
  - 若 `dispatch_context.get("code")` 为空且 blackboard 无 code 工件；
  - 且 `dispatch_context.get("work_dir")` 或 blackboard 的 `work_dir` 存在；
  - 则用 **Glob/Read**（或直接用 `Path(work_dir).rglob("*.py")` + 读文件）将工作目录下需要评审的文件（如 `**/*.py`，可配置）内容读出来；
  - 拼成「文件名 + 内容」的文本，写入 `dispatch_context["code"]`。
- 可选：对「当前目录」类意图（如「review 当前目录」「评审当前目录下所有文件」）在路由或注入时做简单识别，确保走上述分支。

**优点**：改动小、只动编排层；Reviewer 逻辑不变，立即可用。  
**缺点**：仍非「模型主动调工具」，与 LangGraph 的 tool-calling 模式不一致。

### 4.2 方案 B：让 Reviewer 具备「工具调用」能力（与 LangGraph 一致）

**思路**：让 Reviewer 像 LangGraph 中常见做法一样，可以发起 Read/Glob/Grep，并在 state 中传入 work_dir（或 project_path），工具内部基于该路径解析相对路径。

**两种实现方式**：

1. **TUI 的 REVIEWER 派发走 LangGraph**  
   - 对 REVIEWER 路由不再调 `base.ReviewerAgent`，改为进入 graph，执行带 `create_react_agent(model, tools)` 的 **reviewer_node**；
   - 在 **state** 中传入 `project_path` = 当前 work_dir；
   - reviewer_node 内提供 Read/Glob/Grep（实现时基于 `state["project_path"]` 解析路径），这样「review 当前目录」会由模型多次调工具完成。
2. **在 base.ReviewerAgent 内实现简单 tool loop**  
   - 在 ReviewerAgent 内：若 context 有 work_dir 且 code 为空，则先不直接评审，而是进入「循环：调用 LLM（带工具描述）→ 若返回 tool_calls 则执行 Read/Glob/Grep（传入 work_dir）→ 将结果拼回 messages/prompt → 再调 LLM」直到模型给出 [Pass]/[Reject]；
   - 需要为 base 系 Agent 增加「可选的工具执行循环」或复用现有 tool_scheduler 等逻辑，并传入配置好的工具实例（绑定 work_dir）。

**优点**：与 LangGraph 的「模型 + bind_tools + 工具循环」一致；可扩展为「按需读文件」。  
**缺点**：改动大，需统一 TUI 与 graph 的入口或为 base Agent 增加工具循环。

### 4.3 建议顺序

1. **先做方案 A**：在 `_inject_reviewer_context`（或 dispatch 前一步）中，当 code 为空且存在 work_dir 时，按 work_dir 预读目标文件并注入 `dispatch_context["code"]`，解决「无法访问工作目录」的问题。
2. **若希望架构与 LangGraph 一致**：再规划方案 B（TUI 部分请求走 graph 的 reviewer_node，或 base.ReviewerAgent 支持工具循环），并保证 state/context 中始终有 work_dir/project_path 供工具使用。

## 5. 小结

- **当前**：TUI 下 Reviewer 是「单轮 prompt + 单次 LLM」，无工具调用、未使用 work_dir，与 LangGraph 的「模型 + 工具 + 循环」**不一致**。
- **直接原因**：code 依赖 blackboard 注入，为空时没有任何基于 work_dir 的兜底读取。
- **推荐**：先用方案 A 在编排层按 work_dir 预读文件并注入 code；若需与 LangGraph 一致，再按方案 B 为 Reviewer 引入真正的工具调用与 work_dir/project_path 传递。
