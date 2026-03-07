# 主代理与子代理流转与上下文分析

本文档基于代码追踪，说明 TUI 下「主代理」与子代理的触发逻辑、LLM 参与方式、以及上下文共享机制；并指出当前存在的问题。

---

## 一、入口与两条路径

当前存在两条完全独立的入口：

| 入口 | 调用方 | 方法 | 用途 |
|------|--------|------|------|
| **TUI** | `console_app.py` 主循环 | `orchestrator.dispatch(user_input)` | 每轮用户输入**直接**派发到**一个**子代理，无多步工作流 |
| **CLI** | `agents/cli.py` | `orchestrator.execute_workflow(requirement)` | 完整流水线：ANALYZING → PLANNING → IMPLEMENTING → TESTING → VERIFYING，**多子代理顺序执行**且**共享上下文** |

TUI 下**没有**调用 `execute_workflow()`，只调用 `dispatch()`，因此「主代理」与「子代理」的流转仅指 **dispatch 路径**。

---

## 二、TUI 下触发逻辑（谁决定交给哪个子代理）

### 2.1 没有「主代理 LLM 再派发」的步骤

- 用户输入 **不会** 先经过某个「主代理」LLM 再根据回复派发。
- 流程是：**用户输入 → Orchestrator._analyze_intent(intent) → 得到 SubAgentType → 创建该子代理 → agent.execute(intent, context)**。

即：**派发决策 = 意图分析（关键词或一次 LLM），不依赖主代理的 LLM 响应内容。**

### 2.2 意图分析：何时交给子代理、交给谁

**实现位置**：`orchestrator._analyze_intent(intent)`（约 549–608 行）。

1. **关键词匹配（优先）**  
   对 `intent` 做小写后按固定关键词匹配，**命中即返回对应 SubAgentType**，不再问 LLM：

   - Mini-Coder Guide：`mini-coder`, `如何使用`, `配置`, `tui`, `agent 角色`, `工作流`, `prompt`, `subagent` 等 → `MINI_CODER_GUIDE`
   - General Purpose：`快速查找`, `code search`, `文件发现` 等 → `GENERAL_PURPOSE`
   - Explorer：`看看`, `找找`, `探索`, `explore`, `search`, `find`, `查看` 等 → `EXPLORER`
   - Planner：`规划`, `计划`, `拆解`, `plan`, `design`, `架构` 等 → `PLANNER`
   - Coder：`实现`, `添加`, `修改`, `implement`, `create`, `write`, `add`, `feature`, `功能` 等 → `CODER`
   - Reviewer：`评审`, `检查`, `review`, `quality`, `代码质量`, `架构对齐` 等 → `REVIEWER`
   - Bash：`测试`, `运行`, `execute`, `test`, `bash`, `验证`, `verify` 等 → `BASH`

2. **兜底：LLM 决策**  
   若**无一**关键词命中，则调用 `_llm_analyze_intent(intent)`：
   - 用 `llm_service.chat(prompt)` 发一段固定 prompt，要求根据用户请求**只回答一个词**：`EXPLORER` / `PLANNER` / `CODER` / `REVIEWER` / `BASH` / `GENERAL_PURPOSE` / `MINI_CODER_GUIDE`。
   - 对返回字符串做 `strip().upper()` 后按包含关系映射到 `SubAgentType`（例如包含 "PLANNER" 则返回 `SubAgentType.PLANNER`）。

**结论**：

- **主代理收到 LLM 什么样的响应才会把任务交给子代理**：  
  - 若走关键词：**不依赖任何 LLM 响应**，直接按关键词交给对应子代理。  
  - 若走兜底：**仅依赖这一次意图分析的 LLM 响应**，响应里包含哪个子代理名就交给哪个子代理；**没有**「主代理先和用户对话、再根据对话内容派发」的步骤。

### 2.3 TUI 路由与 Bash 行为模式（bash_mode）

**说明**：TUI 使用**独立的路由 LLM**（`console_app._route_user_input`），返回 `route`、`agent`，且当 `agent=BASH` 时要求返回 **`bash_mode`**。**质量流水线仅由用户/Planner/Orchestrator 显式触发，Bash 不自行决定**；详见 docs/quality-pipeline-spec.md。

| bash_mode        | 含义                     | BashAgent 行为 |
|------------------|--------------------------|----------------|
| `quality_report` | 调用方显式要求跑测试/质量报告 | 跑完整质量流水线（pytest、mypy、flake8、coverage）并输出【质量报告】 |
| `confirm_save`   | 用户要「把代码写入本地」等 | 仅执行 `ls -la .` 列工作目录，不跑测试 |
| `single_command` | 用户给了一条具体命令     | 将 task 当作单条命令执行（仅首词在白名单内时执行） |
| 未设置           | 未显式请求跑测试         | 不跑流水线，返回提示要求调用方明确指定 |

- **触发质量流水线的逻辑**：仅当 `context["bash_mode"] == "quality_report"` 时，`BashAgent.execute()` 才执行流水线；未设置或为其它值时**不跑**，并返回说明（见 **docs/quality-pipeline-spec.md**）。
- **谁传入 bash_mode**：TUI 仅在路由明确返回 `bash_mode` 时传入（不默认 quality_report）；未传时由 Orchestrator 在 `dispatch_with_agent` 中根据 intent 推断（`_infer_bash_mode`）。
- **代码位置**：`agents/base.py` 中 `BashAgent.execute()` 按 `ctx.get("bash_mode")` 分支；Orchestrator 在派发 BASH 且 context 无 `bash_mode` 时调用 `_infer_bash_mode(intent)`。

---

## 三、上下文在两条路径下的共享方式

### 3.1 execute_workflow 路径（CLI，有共享上下文）

- 调用 `execute_workflow(requirement)` 时会在内部创建 **WorkflowContext**（含 `task_id`, `requirement`, `config`），并创建/绑定一个 **Blackboard**。
- 同一轮工作流内，ANALYZING → PLANNING → IMPLEMENTING → TESTING → VERIFYING 各阶段**共用**该 `WorkflowContext` 和 **Blackboard**。
- Planner 把计划写入 `blackboard.add_artifact("implementation_plan.md", ...)`；Coder 从 blackboard 读计划、写代码；Tester/Reviewer 同样通过 blackboard 读计划/代码。  
→ **子代理之间通过 Blackboard 共享上下文。**

### 3.2 dispatch 路径（TUI，当前几乎无跨轮共享）

- TUI 只调用 `dispatch(intent, context=None)`，且**不会**先调用 `execute_workflow()`，因此 **orchestrator._context 始终为 None**（在 TUI 场景下）。
- `_create_subagent` 中（约 665 行）：
  ```python
  blackboard = self._context.blackboard if self._context else Blackboard("dispatch")
  ```
  因为 `self._context` 为 None，所以**每次 dispatch 都会新建**一个 `Blackboard("dispatch")`。
- 子代理执行时拿到的只是**当前这一轮**的 blackboard；下一轮用户输入再次 `dispatch` 时又会新建一个 blackboard，**上一轮子代理写上去的计划/代码等不会被下一轮看到**。
- 此外，TUI 调用为 `dispatch(user_input)`，未传第二参数，故 **context 始终为 None**；子代理收到的 `context` 也是 None（对支持 `context` 的 base 系子代理而言同样没有跨轮信息）。

**结论**：

- **主代理和子代理之间的上下文共享**：  
  - 在 **execute_workflow** 中：通过 **WorkflowContext + Blackboard** 在多个子代理之间共享。  
  - 在 **dispatch（TUI）** 中：**没有**跨轮共享；每轮一个新的 Blackboard，且无 WorkflowContext；**子代理之间、主代理与子代理之间在 TUI 下都没有持久化共享上下文**（除非后续改成分轮复用同一 context/blackboard 或显式传入上轮结果）。

---

## 四、流程简图（TUI + dispatch）

```
用户输入
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  Orchestrator.dispatch(intent, context=None)                 │
│  （注意：无「主代理」LLM 先回复再派发）                        │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
_analyze_intent(intent)
    │
    ├─ 关键词命中 → 直接返回 SubAgentType（无 LLM）
    │
    └─ 未命中 → _llm_analyze_intent(intent)
                    │
                    ▼
                llm_service.chat(prompt)  // 一次调用，要求只回答一个词
                    │
                    ▼
                解析返回词 → SubAgentType
    │
    ▼
_notify_agent_started(agent_type)
    │
    ▼
_create_subagent(agent_type)
    │
    │  blackboard = self._context.blackboard if self._context else Blackboard("dispatch")
    │  → TUI 下 _context 为 None → 每轮新建 Blackboard("dispatch")
    │
    ▼
agent.execute(intent, context=None)
    │
    │  - Base 系（Explorer/Reviewer/Bash）：execute(task, context=None)，可接收 context 但当前为 None
    │  - Enhanced 系（Planner/Coder/Tester）：execute(task) 仅接受 task，上下文只来自 blackboard
    │
    ▼
_notify_agent_completed(agent_type, result)
    │
    ▼
返回 result；本轮结束，下一轮用户输入再次 dispatch 时重新 _analyze_intent、新建 blackboard
```

---

## 五、已发现的问题与不一致

### 5.1 dispatch 与 execute 签名不一致（潜在运行时错误）

- `orchestrator.dispatch()` 中调用：`result = agent.execute(intent, context=context)`（约 749 行），即对所有子代理都传了 `context=`。
- **Base 系**（Explorer, Reviewer, Bash）：`execute(self, task, context=None)`，可接受 `context`，无问题。
- **Enhanced 系**（Planner, Coder, Tester）：`execute(self, task: str)` **没有** `context` 参数，在 Python 中会触发 `TypeError: execute() got an unexpected keyword argument 'context'`。

**已验证**：对 `PlannerAgent.execute("plan task", context=None)` 会抛出 `TypeError: execute() got an unexpected keyword argument 'context'`。因此只要 TUI 将请求路由到 Planner/Coder/Tester，就会报错。

**修复建议**（二选一）：  
- 方案 A：Orchestrator.dispatch() 中，对 Enhanced 系只调 `agent.execute(intent)`，对 Base 系调 `agent.execute(intent, context=context)`。  
- 方案 B：Enhanced 系 `execute(self, task: str, context: Optional[Dict] = None)` 增加 `context` 参数（可忽略），与 Base 系签名统一，dispatch 继续统一写 `agent.execute(intent, context=context)`。

### 5.2 TUI 下无跨轮上下文

- 每轮 dispatch 新建 Blackboard，且不传入上一轮结果，因此：
  - 用户先说「规划登录功能」再 say「按刚才的计划实现」，第二句派发到的 Coder **拿不到**「刚才的计划」；
  - 无法在 TUI 下实现「先规划 → 再实现 → 再评审」的连贯多轮，除非在应用层维护会话级 context 并传入 dispatch，或改为在 TUI 中调用 `execute_workflow`（或等价的带 WorkflowContext 的流程）。

### 5.3 「主代理」在代码中的含义

- 若「主代理」指**先和用户对话、再根据对话内容决定派发**的 LLM 角色：**当前实现里没有**；派发完全由 `_analyze_intent`（关键词 + 单次 LLM 意图分析）决定。
- 若「主代理」指 **Orchestrator**：则「主代理与子代理的流转」= 用户输入 → Orchestrator 意图分析 → 单次子代理执行，且 TUI 下无持久化共享上下文。

---

## 六、建议（可后续落地）

1. **统一 execute 签名与 dispatch 调用**  
   - 要么：Enhanced 的 `execute(self, task, context=None)` 并忽略 `context`；  
   - 要么：dispatch 中根据 agent 类型决定 `agent.execute(intent)` 或 `agent.execute(intent, context=context)`，避免传 `context` 给只接受 `task` 的 Enhanced 子代理。

2. **TUI 下若需多轮连贯（规划→实现→评审）**  
   - 方案 A：在 TUI 会话中维护「会话级 context」（如上一轮结果、当前 plan/code 摘要），在 `dispatch(intent, context=session_context)` 时传入，且子代理（含 Enhanced）从 context 或 blackboard 中读取；  
   - 方案 B：对「完整任务」走 `execute_workflow(requirement)`，在 TUI 中提供入口（如特定命令或按钮）触发工作流，从而复用现有 WorkflowContext + Blackboard 共享。

3. **文档与设计**  
   - 在设计文档中明确：TUI 当前是「单轮单子代理」+「无跨轮共享上下文」；若产品期望「主代理先对话再派发」或「多轮共享上下文」，需在架构上单独设计并实现。

以上为对主代理与子代理触发逻辑、LLM 响应作用、以及上下文共享的检测结论与建议。
