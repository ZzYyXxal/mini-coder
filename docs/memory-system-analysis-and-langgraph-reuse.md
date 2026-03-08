# mini-coder 记忆系统分析与 LangGraph 记忆复用方案

> 仅设计方案与分析，不修改代码。

## 一、当前 mini-coder 记忆系统

### 1.1 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                     ContextMemoryManager                         │
│  (manager.py) 主入口：会话、压缩、上下文产出                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ WorkingMemory │   │ PersistentStore│   │ ContextBuilder│
│ (内存)        │   │ (磁盘)         │   │ (GSSC 管道)    │
│               │   │               │   │               │
│ - Message[]   │   │ sessions/     │   │ Gather →      │
│ - 优先级      │   │   {id}.json   │   │ Select →      │
│ - token 计数  │   │ summaries.json│   │ Structure →   │
│ - 压缩触发    │   │               │   │ Compress      │
└───────────────┘   └───────────────┘   └───────────────┘
```

### 1.2 核心组件

| 组件 | 文件 | 职责 |
|------|------|------|
| **ContextMemoryManager** | `memory/manager.py` | 会话生命周期（start_session/restore_latest_session）、add_message(user/assistant)、get_context(max_tokens)、compress/prune、与 PersistentStore 同步 |
| **WorkingMemory** | `memory/working_memory.py` | 内存中的 `Message` 列表；按优先级淘汰；token 计数与压缩阈值（compression_threshold）；工具输出裁剪（prune_tool_outputs） |
| **PersistentStore** | `memory/persistent_store.py` | 磁盘：Session 按 `session_id` 存为 `sessions/{id}.json`（含 messages）；Summary 追加写入 `summaries.json` |
| **ContextBuilder** | `memory/context_builder.py` | GSSC：Gather（摘要 + 笔记 + 记忆）→ Select（优先级 + token 限制）→ Structure（格式化）→ Compress（可选 Plan B 压缩） |
| **Message/Session** | `memory/models.py` | Message(role, content, priority, timestamp)；Session(id, project_path, messages, created_at, updated_at) |

### 1.3 数据流（TUI / 主对话）

1. **LLMService**（`llm/service.py`）持有 `_context_manager: ContextMemoryManager`。
2. **chat()**：`add_message("user", content)` → provider.send_message() → `add_message("assistant", response)`。
3. **get_context**：由 Provider 或调用方通过 `_context_manager.get_context(max_tokens)` 获取「带摘要 + 优先级排序」的消息列表，再拼成 LLM 的 messages。
4. **会话持久化**：start_session(project_path)、save_session()、restore_latest_session()、load_session(session_id)；Session 含完整 messages 列表并落盘。
5. **Plan B 压缩**：当 token 超阈值时，对低优先级消息做摘要，摘要写入 PersistentStore 并加入上下文；原消息从 WorkingMemory 移除。

### 1.4 特性小结

- **会话粒度**：以 session_id 为单位的 Session，对应「一次对话会话」。
- **消息粒度**：单条 Message，带 role / priority / timestamp。
- **上下文窗口**：get_context(max_tokens) 在 token 限制内按优先级和摘要组装，供 LLM 使用。
- **压缩**：摘要历史片段，减少 token 同时保留语义。
- **与执行解耦**：记忆系统只负责「对话历史」的存储与供给，不关心是否走 Orchestrator 还是 LangGraph。

---

## 二、LangGraph 的「记忆」机制

### 2.1 定位：图状态持久化（Checkpointer）

LangGraph 的持久化是 **图执行状态（checkpoint）** 的保存与恢复，而不是独立的「对话记忆服务」：

- **Checkpointer**（如 `MemorySaver` / `SqliteSaver`）：实现 `BaseCheckpointSaver`，按 **thread_id** 存一系列 **checkpoint**。
- **thread_id**：在 `config = {"configurable": {"thread_id": "xxx"}}` 中传入，是「线程/会话」的唯一标识。
- **Checkpoint**：每个 super-step 一次快照，包含：
  - **values**：当前图 State 各 channel 的值（如 `CodingAgentState` 的 messages、user_request、implementation_plan 等）；
  - **next**、**metadata**、**config** 等。
- **API**：`graph.invoke(..., config)` 会写入 checkpoint；`graph.get_state(config)` 取当前状态；`graph.get_state_history(config)` 取历史；`graph.update_state(config, values)` 可写回 state。

### 2.2 当前 mini-coder 中 LangGraph 的用法

- **graph/builder.py**：`CodingAgentGraphBuilder` 使用 `MemorySaver()` 作为 checkpointer，`graph.compile(checkpointer=self._checkpointer)`。
- **graph/runner.py**：执行时传入 `config["configurable"]["thread_id"] = state.get("session_id", "default")`，即用 **session_id 当 thread_id**。
- **graph/state.py**：`CodingAgentState` 含 `messages: Annotated[List, add_messages]`、session_id、各阶段结果等；整份 state 被 checkpoint 保存。

因此：**LangGraph 侧已有「按 session 持久化图状态」的能力**，但仅是 **state 快照**，没有「摘要、优先级、token 限制、Plan B 压缩」等逻辑。

### 2.3 LangGraph 与 mini-coder 记忆的差异

| 维度 | mini-coder 记忆系统 | LangGraph Checkpointer |
|------|---------------------|--------------------------|
| **抽象** | 对话消息 + 会话 + 摘要 | 图状态快照（含 messages 通道） |
| **粒度** | Message 级，带 priority | State 级，整图 values |
| **容量控制** | max_tokens / max_messages，优先级淘汰，压缩 | 无内置限制，通常整 state 存 |
| **压缩** | 有（Summary + 从 working memory 移除） | 无 |
| **会话标识** | session_id（Session） | thread_id（configurable） |
| **持久化** | Session JSON + summaries.json | 由 Checkpointer 实现（MemorySaver 仅内存；SqliteSaver 等可落盘） |
| **用途** | 给 LLM 组 context、多轮对话 | 图恢复、time-travel、human-in-the-loop |

---

## 三、能否复用 LangGraph 的记忆系统？

### 3.1 直接替代 mini-coder 记忆？

- **不能完全替代**。LangGraph 的 checkpointer 是 **图状态持久化**，不是「带优先级与压缩的对话记忆」：
  - 若只用 LangGraph state + checkpointer，则「上下文窗口」要自己在节点里实现（例如从 state.messages 里截断或摘要），否则 state 会无限增长。
  - mini-coder 的 **Plan B 压缩、优先级、token 限制、GSSC** 在 LangGraph 中都没有现成等价物，需要自己实现或继续用现有 memory 模块。

### 3.2 可以复用的部分

1. **thread_id ↔ session_id 统一**  
   当前 runner 已用 `session_id` 作 `thread_id`，可视为「一次 TUI 会话 = 一个 LangGraph thread」，便于同一会话内既用主对话记忆又用图状态恢复。

2. **State.messages 与 Message 列表互转**  
   - LangGraph 的 `messages` 多为 LangChain 的 `BaseMessage` 或兼容结构。  
   - 若在「图入口」从 ContextMemoryManager 的 get_context() 得到 `list[dict]`，可转成 state.messages 的格式注入；图结束后也可把新增的 user/assistant 消息写回 ContextMemoryManager。  
   - 这样 **对话历史** 仍由 mini-coder 记忆系统管理（压缩、持久化 Session），LangGraph 只在使用图执行时「读写」这段历史。

3. **用 Checkpointer 做「图执行」记忆**  
   - 图内多步、多 agent 的中间结果（implementation_plan、code_changes、review_result 等）已经存在 state 里并由 checkpointer 持久化。  
   - 这部分不需要、也不适合用 ContextMemoryManager 的 Message 列表来存；**图状态 = 图执行记忆**，与「主对话记忆」职责分离。

4. **持久化实现复用**  
   - 若希望 LangGraph 的 checkpoint 落盘，可使用 `SqliteSaver` 或自实现 `BaseCheckpointSaver`。  
   - 自实现时可以考虑：用 mini-coder 的 **PersistentStore 目录或格式** 存 checkpoint（例如按 thread_id 建子目录、存 state 序列化），这样存储路径与现有 sessions/summaries 统一，但 **语义上仍是「图状态快照」**，不是替换 Session/Summary。

---

## 四、推荐方案：双轨 + 桥接

### 4.1 职责划分

| 场景 | 负责方 | 说明 |
|------|--------|------|
| **TUI 主对话 / 多轮 chat** | mini-coder ContextMemoryManager | 继续负责消息存储、压缩、get_context、Session 持久化 |
| **LangGraph 工作流执行** | LangGraph Checkpointer + State | 负责图状态（含 messages 通道、阶段结果）的持久化与恢复 |
| **「图内」对话消息** | 可选桥接 | 图开始时从 ContextMemoryManager 注入 state.messages；图结束后把新消息同步回 ContextMemoryManager |

### 4.2 桥接方式（可选）

- **入口（TUI 发起一次图执行）**  
  - 用当前 `session_id` 作为 `thread_id`。  
  - 若希望图内节点「看到」主对话历史：在 `create_initial_state` 或首节点前，用 `ContextMemoryManager.get_context(max_tokens)` 得到消息列表，转成 LangChain 消息格式，写入 `state["messages"]`（或通过 `update_state` 写入）。  
  - 这样图内 LLM 节点使用的是「与主对话一致的历史视图」（但注意 token 限制在图侧也要遵守）。

- **出口（图执行结束）**  
  - 从 `state["messages"]` 中取出本轮新增的 user/assistant 消息，调用 `ContextMemoryManager.add_message(...)` 写回。  
  - 这样主对话的 Session 里既有「非图」的轮次，也有「图执行」产生的轮次，压缩与持久化逻辑不变。

### 4.3 不推荐的做法

- **用 LangGraph checkpointer 完全取代 ContextMemoryManager**：会失去 Plan B 压缩、优先级和 token 控制，需要重做一整套「对话记忆」逻辑。  
- **用 ContextMemoryManager 存图状态**：图状态结构复杂（多 channel、reducer），且需要 checkpoint 语义（版本、next、metadata），不适合用当前 Session/Message 模型表达。

### 4.4 记忆系统作为 Hook（已实现）与「全 LangGraph」化

**已实现**：记忆系统以 **MemoryHook** 形式挂载在 agent/LLM 调用前后（见 `memory/hook.py`）：

- **pre_step**：agent 调用前——从 memory 加载上下文（可选 `run_compression_first` 先执行压缩腾出空间）、与 `current_messages` 合并并去重，返回供 LLM 使用的消息列表。  
- **post_step**：agent 调用后——若触发压缩/淘汰条件，则执行 prune + 摘要压缩，返回统计（pruned_tokens、compressed_messages、tokens_saved）。

LLMService 已在 `chat()` 与 `chat_stream()` 中挂载：pre-step 在构建 context 前执行（可选压缩），post-step 在写入 assistant 消息后执行并产出压缩统计。

与 LangGraph 对接时，可在图节点中：**pre** 使用 `hook.pre_step(max_tokens, current_messages=state.messages, dedupe=True)` 得到合并去重后的上下文；**post** 在写入 state 后调用 `hook.post_step()` 做压缩与摘要。

若未来 TUI 主对话改为「单一大图」驱动，可进一步：

- **图 State 作为唯一对话载体**：state.messages 即主对话历史；checkpointer 负责持久化。  
- **在图中显式调用 MemoryHook**：pre 节点用 hook.pre_step 加载并去重；post 节点或边逻辑用 hook.post_step 做压缩与摘要。  
- **ContextMemoryManager 作为记忆服务**：仅负责压缩与摘要；图通过 MemoryHook 调用，state.messages 仍由 checkpointer 存，长程记忆由 memory 模块提供。

### 4.5 Per-agent 记忆与 NoteTool 范围（已实现）

- **每 agent 独立记忆**：`AgentMemoryRegistry` 按 agent 类型（explorer/planner/coder/reviewer/bash 等）维护独立的 `ContextMemoryManager`，存储路径为 `base_storage_path/{agent_type}`，互不混用。
- **派发时**：Orchestrator 在 dispatch 前用 `registry.get_hook(agent_type).pre_step(...)` 得到该 agent 的历史消息列表，注入 `dispatch_context["memory_context"]`；执行后把本轮 user/assistant 写入该 agent 的 manager 并调用 `hook.post_step()`。
- **NoteTool 仅部分 agent**：只有「关注项目进度」的 agent 使用项目笔记（NoteTool）：explorer、planner、coder 的 `ContextBuilder` 使用 `notes_manager`；reviewer、bash 等不使用笔记上下文（`notes_manager=None`）。常量见 `memory/agent_memory.py` 中 `AGENT_TYPES_WITH_NOTES`。

---

## 五、小结

| 问题 | 结论 |
|------|------|
| 当前 mini-coder 记忆系统怎么做的？ | 见第一节：ContextMemoryManager + WorkingMemory + PersistentStore + ContextBuilder；Session/Message 级；带优先级、token 限制与 Plan B 压缩；供 LLMService 的 chat/get_context 使用。 |
| LangGraph 的记忆是什么？ | 图状态 checkpointer：按 thread_id 存 state 快照，无内置压缩与 token 控制。 |
| 能否复用 LangGraph 的记忆系统？ | **不能直接替代** mini-coder 的对话记忆；**可以复用** thread_id≈session_id、state.messages 与 Message 互转、以及用 checkpointer 做图执行记忆。 |
| 推荐方案？ | **双轨**：主对话继续用 ContextMemoryManager；图执行用 LangGraph checkpointer。可选 **桥接**：图入口从 ContextMemoryManager 注入 messages，图出口把新消息同步回 ContextMemoryManager。 |

以上为仅设计分析，不涉及代码修改。
