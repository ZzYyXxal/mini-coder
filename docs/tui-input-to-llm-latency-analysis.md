# TUI 输入到发起 LLM 调用耗时分析

本文分析从用户按下回车到「首字/首 token 返回」之间各阶段耗时，以及可优化点。

## 1. 调用链总览

```
用户输入 Enter
  → _handle_special_commands()          # 很快
  → _display_thinking("Processing...")  # 很快
  → _route_user_input(user_input)       # ★ 可能一次完整 LLM 调用
       → _ensure_llm_service()          # 首次：创建 LLMService、restore/start_session
       → chat_one_shot(ROUTER_SYSTEM, user_input)  # 非寒暄时：完整请求/响应
  → 若 route == "main"
       → _call_llm_stream_and_display(user_input)
            → _ensure_llm_service()      # 已存在则几乎无开销
            → chat_stream(user_input)   # 见下
                 → _validate_input()              # 很快
                 → run_compression_if_needed()  # 仅触发压缩并拿 stats，不 build
                 → add_message("user", ...)
                 → build_with_user_message()     # ★ 第二次完整 GSSC 构建
                 → _get_main_agent_system_prompt()  # 首次读文件，之后走缓存
                 → provider.send_with_context()  # HTTP 请求发出，首 token 在此之后返回
```

## 2. 主要耗时来源

### 2.1 路由阶段多一次完整 LLM 调用（影响最大）

- **位置**：`console_app._route_user_input()` → `chat_one_shot(ROUTER_SYSTEM, user_input)`。
- **触发条件**：当用户输入**不是**极简寒暄（如 "hi"/"你好"）时，会用一次**非流式、完整请求/响应**的 LLM 调用做路由。
- **影响**：多出约 **1～5+ 秒**（取决于接口 RTT 与模型首 token 延迟），且这段时间内主对话流式请求尚未发出。
- **现状**：仅对少数短句做了启发式 bypass（`s in {"hi", "hello", "你好", ...}`），其余都会走路由 LLM。

### 2.2 chat_stream 内重复做两次上下文构建

- **位置**：`llm/service.py` 的 `chat_stream()`。
- **流程**：
  （已优化为一次构建）先 `run_compression_if_needed()` 仅做压缩并拿 stats，再 `build_with_user_message()` 只 build 一次，用于 `send_with_context()`。

### 2.3 首次 _ensure_llm_service 的初始化

- **位置**：`console_app._ensure_llm_service()`，在 `_route_user_input` 和 `_call_llm_stream_and_display` 中都会调用。
- **首次调用时**：创建 `LLMService(config_path)`（读 YAML、建 provider、可能初始化 memory/notes/command tool），若 `memory_enabled` 还会 `restore_latest_session()` 或 `start_session()`（可能涉及磁盘 I/O）。
- **影响**：仅首轮明显，后续调用几乎无额外开销。

### 2.4 主 agent system prompt 加载

- **位置**：`_get_main_agent_system_prompt()`，在 `chat_stream` 构建完 context 后、`send_with_context` 前调用。
- **影响**：首次会读 `prompts/system/main-agent.md` 并缓存，之后走 `_main_agent_prompt_cache`，对首字延迟影响很小（仅首次略增）。

## 3. 优化建议（按优先级）

1. **减少或避免「为路由单独打一次完整 LLM」**
   - 扩展启发式：仅对**几乎不会误判**的输入（寒暄、致谢/告别、极短确认）直接返回 `route="main"`，不调 `chat_one_shot`；不含歧义短句，避免「该路由时不路由」。
   - 或改为「先发主代理流式请求，再根据首句/首段结果或用户后续行为决定是否派发子代理」（需改交互与产品逻辑）。
   - 或路由模型改用更小/更快模型或本地规则，降低单次路由延迟。

2. **chat_stream 中只做一次上下文构建**（已实现）
   - 原状：`build_with_compression()` 会触发 prune/compress 并返回 (context, stats)，但 context 未使用，仅用 stats 做「已清理/已压缩」提示；真正发请求的 context 来自 `build_with_user_message()`，导致 GSSC 全流程跑两遍。
   - 实现：新增 `ContextBuilder.run_compression_if_needed()`，仅执行 Plan B 压缩（prune + 必要时 compress）、返回相同结构的 stats，**不**调用 `build()`。`chat_stream` 先调用它并照常根据 stats yield 提示，再只调用一次 `build_with_user_message(..., auto_compress=False)` 构建发请求的 context。
   - 副作用：无。压缩仍会发生，统计与用户可见的「已清理 X tokens」「已压缩 X 条消息」保持不变；仅少了一次冗余的 `build()`。

3. **首轮 LLM 与会话初始化**
   - 若 TUI 启动时就能确定会用到 LLM，可在启动阶段提前调用一次 `_ensure_llm_service(init_session=True)`，把「首轮冷启动」从「用户第一次输入后」移到「进入 REPL 前」，首轮输入到首字的体感会更好。

4. **可观测性**
   - 在 `_route_user_input`、`chat_stream` 内各阶段（validate、run_compression_if_needed、build_with_user_message、get_main_prompt、send_with_context 首 chunk）打耗时日志（例如 DEBUG 或独立开关），便于在真实环境中量化各段占比，再针对性优化。

## 4. 小结

| 阶段                     | 大致耗时来源           | 优化方向                     |
|--------------------------|------------------------|------------------------------|
| 路由                     | 一次完整 LLM 调用      | 启发式扩展 / 先流式后路由等  |
| chat_stream 上下文构建   | 两次完整 GSSC build    | 合并为一次构建               |
| 首次 _ensure_llm_service | 建 Service + 会话 I/O  | 启动时预热                   |
| 主 agent prompt          | 首次读文件             | 已缓存，保持即可             |

当前对「输入到首字」体感影响最大的是：**路由用的那一次完整 LLM 调用**，以及 **chat_stream 内重复的两次上下文构建**。优先优化这两处，再配合耗时打点做验证即可。
