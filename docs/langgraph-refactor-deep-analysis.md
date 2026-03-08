# LangGraph 重构深度分析：Mailbox 与 ToolScheduler 替换

> **版本**: 1.0
> **日期**: 2026-03-07
> **目的**: 分析 mailbox.py 和 tool_scheduler.py 在 LangGraph 中的替换可行性

---

## 1. 核心问题总结

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ⚠️ 关键发现：不能完全删除                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  mailbox.py (12KB)                                                      │
│  ├─ TaskBrief / SubagentResult    → ✅ 可映射到 State 字段              │
│  ├─ MailboxMessage (to/from)      → ⚠️ LangGraph 无对应，需要保留       │
│  └─ ParallelTaskGroup             → ✅ LangGraph 图分支可替代           │
│                                                                         │
│  tool_scheduler.py (8KB)                                                │
│  ├─ DAG 依赖分析 (depends_on)     → ❌ LangGraph ToolNode 不支持        │
│  ├─ Placeholder 解析 ({{...}})    → ❌ LangGraph 无对应                 │
│  └─ 拓扑排序分批执行               → ❌ LangGraph 无对应                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Mailbox 详细分析

### 2.1 功能分解

| 功能 | 当前实现 | LangGraph 对应 | 替换方案 |
|------|----------|---------------|----------|
| **TaskBrief** | `task_id`, `intent`, `context_refs` | State 字段 | 直接映射 |
| **SubagentResult** | `success`, `summary`, `error` | State 字段 | 直接映射 |
| **to_agent/from_agent** | 消息信封字段 | 无对应 | 保留简化版 |
| **message_id/created_at** | 追踪字段 | checkpointer | 使用 checkpointer |
| **ParallelTaskGroup** | 批量任务派发 | 图分支 | 条件边替代 |

### 2.2 定向投递问题

**问题描述**：

LangGraph 的 State 是全局共享的，没有"发给谁"的概念。所有节点都能读取完整的 State。

```python
# 当前 Mailbox 方式
message = MailboxMessage(
    to_agent="coder",
    from_agent="planner",
    type="task",
    payload={"task_id": "t1", "intent": "实现登录功能"}
)

# LangGraph 方式 - 无 to_agent 概念
state = {
    "user_request": "实现登录功能",
    "current_stage": "coding",
    # 所有节点都能访问全部 state
}
```

**影响**：

1. **调试困难** - 无法快速定位"谁产出了什么"
2. **审计缺失** - 无法追踪消息来源
3. **隔离性差** - 子代理可以读取不相关的 State 字段

**解决方案**：保留简化的 `AgentMessage` 类型

```python
# 新设计：保留定向投递能力
class AgentMessage(TypedDict):
    """简化的 Agent 间消息"""
    message_id: str
    to_agent: str      # 保留：调试和审计需要
    from_agent: str    # 保留：追踪来源
    content: str
    created_at: float

class CodingAgentState(TypedDict):
    # 标准状态
    user_request: str
    current_stage: str

    # Agent 消息历史（保留定向投递）
    agent_messages: List[AgentMessage]

    # 其他字段...
```

### 2.3 推荐方案

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Mailbox 替换方案                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  删除：                                                                  │
│  - TaskBrief, SubagentResult (映射到 State 字段)                        │
│  - ParallelTaskGroup, ParallelResultGroup (用图分支替代)                │
│  - MailboxMessage 工厂方法 (简化为 AgentMessage)                        │
│                                                                         │
│  保留：                                                                  │
│  - AgentMessage 类型定义 (to_agent/from_agent)                          │
│  - AGENT_* 常量                                                         │
│                                                                         │
│  新增：                                                                  │
│  - state.py 中的消息字段定义                                             │
│  - 节点函数中的消息追加逻辑                                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. ToolScheduler 详细分析

### 3.1 核心功能对比

| 功能 | ToolScheduler | LangGraph ToolNode | 差异 |
|------|--------------|-------------------|------|
| **并行调用** | `asyncio.gather` | 支持 | ✅ 相同 |
| **DAG 依赖** | `depends_on` + 拓扑排序 | 不支持 | ❌ 缺失 |
| **Placeholder** | `{{call_id.output.field}}` | 不支持 | ❌ 缺失 |
| **超时控制** | `asyncio.wait_for` | 支持 | ✅ 相同 |
| **并发限制** | `Semaphore(3)` | 支持 | ✅ 相同 |

### 3.2 DAG 依赖问题（关键）

**问题描述**：

ToolScheduler 支持声明工具调用间的依赖关系，形成 DAG 执行顺序：

```python
# 当前 ToolScheduler 方式
tool_calls = [
    ToolCall(call_id="1", tool_name="Read", arguments={"path": "config.yaml"}),
    ToolCall(call_id="2", tool_name="Read", arguments={"path": "{{1.output.main_file}}"}, depends_on=["1"]),
    ToolCall(call_id="3", tool_name="Read", arguments={"path": "{{1.output.test_file}}"}, depends_on=["1"]),
]

# 执行顺序：
# Batch 1: [call_1]           (无依赖)
# Batch 2: [call_2, call_3]   (依赖 call_1，并行执行)
```

**LangGraph ToolNode** 不支持这种 DAG 模式：

```python
# LangGraph ToolNode 只能并行或顺序
# 无法表达 "call_2 和 call_3 依赖 call_1 的结果"
```

**影响**：

1. **效率下降** - 必须顺序执行所有工具
2. **功能缺失** - 无法实现"先读配置，再根据配置读文件"模式
3. **LLM 负担** - LLM 必须手动分多次调用

### 3.3 Placeholder 解析问题

**问题描述**：

ToolScheduler 支持 `{{call_id.output.field}}` 语法引用前序调用的结果：

```python
# 当前方式
ToolCall(
    call_id="2",
    tool_name="Write",
    arguments={"path": "{{1.output.suggested_path}}", "content": "..."},
    depends_on=["1"]
)

# LangGraph 方式 - 无法在单次 tool_calls 中引用前序结果
```

**影响**：

LLM 必须等待每轮工具调用完成，然后再发起下一轮调用，无法在单次响应中声明依赖链。

### 3.4 解决方案

**方案 A：保留 ToolScheduler，作为 LangGraph 扩展**

```python
# 在 LangGraph 节点内部使用 ToolScheduler
async def coder_node(state: CodingAgentState):
    # 解析 LLM 响应中的 tool_calls
    tool_calls = parse_tool_calls(state["llm_response"])

    # 使用 ToolScheduler 执行 DAG 调度
    scheduler = ToolScheduler()
    result = await scheduler.execute_batch(tool_calls, tool_registry)

    return {"tool_results": result.results}
```

**方案 B：让 LLM 分多次调用（不推荐）**

效率低，需要多轮 LLM 调用。

**方案 C：预定义工具组合**

为常见模式创建复合工具，但这降低了灵活性。

### 3.5 推荐方案

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     ToolScheduler 替换方案                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  保留：                                                                  │
│  - tool_scheduler.py 核心逻辑 (DAG 构建、拓扑排序、Placeholder 解析)     │
│  - ToolCall, ToolCallResult 类型                                        │
│                                                                         │
│  适配：                                                                  │
│  - ToolScheduler 接收 LangChain Tool 列表                               │
│  - 与 LangGraph ToolNode 协同工作                                        │
│                                                                         │
│  使用方式：                                                              │
│  - 简单并行：使用 LangGraph ToolNode                                    │
│  - DAG 依赖：在节点内调用 ToolScheduler                                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 最终代码保留决策

### 4.1 完全删除

| 文件 | 代码量 |
|------|--------|
| `agents/orchestrator.py` | 55KB |
| `agents/scheduler.py` | 15KB |
| `llm/providers/*.py` | 10KB |
| `llm/service.py` 部分 | 20KB |

**总计删除**: ~100KB

### 4.2 保留并适配

| 文件 | 原代码量 | 适配后 | 原因 |
|------|----------|--------|------|
| `agents/mailbox.py` | 12KB | ~4KB | 保留 AgentMessage 类型 |
| `agents/tool_scheduler.py` | 8KB | ~6KB | DAG 依赖无替代 |
| `agents/base.py` | 30KB | ~10KB | 保留配置类型 |
| `agents/enhanced.py` | 53KB | ~20KB | 保留 Agent 角色定义 |

**总计保留**: ~40KB (原 103KB)

### 4.3 新增代码

| 模块 | 代码量 |
|------|--------|
| `graph/state.py` | ~2KB |
| `graph/nodes.py` | ~8KB |
| `graph/edges.py` | ~3KB |
| `graph/builder.py` | ~5KB |
| `tools/mcp_adapter.py` | ~3KB |
| `tracing/client.py` | ~2KB |

**总计新增**: ~23KB

### 4.4 净变化

```
原代码: ~300KB
删除:   -100KB
保留:   ~40KB (适配后)
新增:   +23KB

最终:   ~263KB (-37KB, -12%)
```

---

## 5. 结论

### 5.1 不能删除的部分

| 模块 | 原因 | 解决方案 |
|------|------|----------|
| `mailbox.py` 中的 `AgentMessage` | LangGraph 无定向投递 | 保留简化版，映射到 State |
| `tool_scheduler.py` | LangGraph 无 DAG 依赖 | 保留核心逻辑，适配 LangChain Tool |

### 5.2 可以删除的部分

| 模块 | 原因 |
|------|------|
| `orchestrator.py` | StateGraph 替代 |
| `scheduler.py` | LangGraph 并行替代 |
| `mailbox.py` 中的 TaskBrief/SubagentResult | State 字段替代 |
| `mailbox.py` 中的 ParallelTaskGroup | 图分支替代 |

### 5.3 最终建议

1. **保留 ToolScheduler** - DAG 依赖是核心能力，LangGraph 不支持
2. **简化 Mailbox** - 保留 `AgentMessage` 类型，删除 `TaskBrief` 等
3. **适配而非重写** - ToolScheduler 接收 LangChain Tool，而非自定义 Tool