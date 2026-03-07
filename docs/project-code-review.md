# Mini-Coder 项目代码审查报告

> **审查日期**: 2026-03-07
> **审查范围**: 全项目源代码和设计文档
> **严重程度**: 🔴 严重 | 🟡 中等 | 🟢 轻微

---

## 一、设计不合理之处

### 1.1 🔴 双重 Agent 基类架构

**位置**: `src/mini_coder/agents/base.py` + `src/mini_coder/agents/enhanced.py`

**问题**: 存在两套 Agent 基类架构，职责边界模糊：

```
base.py:
├── BaseAgent         # 基础 Agent 类
├── AgentConfig       # Agent 配置
└── AgentTeam         # Agent 团队

enhanced.py:
├── BaseEnhancedAgent # "增强" Agent 类
├── EnhancedAgentState
└── EnhancedAgentResult
```

**影响**:
- 命名混乱：`BaseAgent` vs `BaseEnhancedAgent`，开发者不知道该继承哪个
- `BaseEnhancedAgent` 实际上才是主要使用的基类
- 两套配置类：`AgentConfig` vs `EnhancedAgentState`

**建议**: 统一为一套 Agent 架构，废弃 `base.py` 中的旧实现或合并到 `enhanced.py`。

---

### 1.2 🟡 LLMService 职责过重

**位置**: `src/mini_coder/llm/service.py`

**问题**: `LLMService` 类违反单一职责原则，承担了过多职责：

```
LLMService (1047 行)
├── Provider 管理 (配置加载、切换)
├── 上下文记忆管理
├── 项目笔记管理 (add_note, complete_todo, ...)
├── 命令执行工具 (execute_command, is_command_safe)
├── 工具注册表 (_tools_registry)
├── 语义搜索 (search_notes_semantic)
└── 关系管理 (add_relation, get_related_notes)
```

**影响**:
- 类过于庞大（1047 行），难以维护
- 测试困难，mock 依赖复杂
- 违反 SOLID 原则中的单一职责原则

**建议**: 拆分为多个服务类：
```
LLMService          → 核心 LLM 调用
ContextService      → 上下文记忆管理
NotesService        → 项目笔记管理
CommandService      → 命令执行
```

---

### 1.3 🟡 调度器职责重叠

**位置**: `src/mini_coder/agents/scheduler.py` + `src/mini_coder/agents/tool_scheduler.py`

**问题**: `ParallelScheduler` 和 `ToolScheduler` 存在功能重叠：

```python
# ParallelScheduler 中也有 Tool 调度逻辑
class ParallelScheduler:
    async def schedule_tool_batch(self, batch, tool_executor): ...
    def _build_execution_batches(self, tool_calls): ...  # DAG 构建
    def _resolve_args(self, args, previous_results): ...  # Placeholder 解析

# ToolScheduler 做同样的事情
class ToolScheduler:
    async def execute_batch(self, tool_calls, tool_registry): ...
    def _build_dependency_graph(self, tool_calls): ...    # DAG 构建
    def _resolve_placeholders(self, args, previous_outputs): ...  # Placeholder 解析
```

**影响**:
- 代码重复：DAG 构建、Placeholder 解析逻辑在两个类中都有实现
- 维护成本高：修改逻辑需要同时修改两处
- 调用者困惑：不知道应该用哪个调度器

**建议**:
1. `ParallelScheduler` 只负责 Agent 级调度
2. Tool 级调度统一委托给 `ToolScheduler`
3. 移除 `ParallelScheduler` 中的 `_build_execution_batches` 和 `_resolve_args`

---

### 1.4 🟢 Blackboard 概念模糊

**位置**: 设计文档 `docs/agent-mailbox-schema.md`

**问题**: Blackboard 和 Mailbox 的职责边界在设计文档中模糊：

```
文档描述:
- "Blackboard 当 Mailbox"
- "Mailbox 仅存消息队列"
- "Artifacts 仍由 Blackboard 管理"
```

但代码中没有独立的 `Blackboard` 模块，`MailboxMessage` 直接存储在列表中。

**建议**: 明确架构并实现独立的 Blackboard 类，或更新文档反映实际实现。

---

## 二、冗余设计

### 2.1 🟡 双重 Tool 基类

**位置**: `src/mini_coder/tools/base.py`

```python
class Tool(ABC):        # v1.0 - 保留向后兼容
    def run(self, parameters) -> ToolResponse: ...
    def get_parameters(self) -> list[ToolParameter]: ...

class BaseTool(ABC):    # v2.0 - 新版本
    def run(self, parameters) -> ToolResponse: ...
    def get_parameters(self) -> List[ToolParameter]: ...
    def get_system_prompt(self, context) -> str: ...  # 新增
    def notify_event(self, event_type, data): ...     # 新增
```

**问题**: 同时存在两套接口，增加理解和维护成本。

**建议**: 设置迁移计划，逐步废弃 v1.0 `Tool` 类。

---

### 2.2 🟡 双重 PromptLoader

**位置**:
- `src/mini_coder/tools/prompt_loader.py`
- `src/mini_coder/agents/prompt_loader.py`

**问题**: 存在两个 PromptLoader 实现，功能相似：

```python
# tools/prompt_loader.py
class PromptLoader:
    def load(self, prompt_path, context=None, use_cache=True) -> str: ...

# agents/prompt_loader.py
class PromptLoader:
    def load(self, prompt_path: str, context: Dict[str, Any] = None) -> str: ...
```

**建议**: 合并为一个通用 PromptLoader，放在公共模块。

---

### 2.3 🟢 废弃的 WorkingMode 枚举

**位置**: `src/mini_coder/tui/console_app.py:43-52`

```python
class WorkingMode(Enum):
    """Working mode enumeration (deprecated - kept for backwards compatibility)."""
    PLAN = "plan"
    CODE = "code"
    EXECUTE = "execute"
```

**问题**: 标记为 deprecated 但仍保留，增加了代码理解成本。

**建议**: 如果确实不需要，应删除相关代码（包括 `_toggle_working_mode` 方法）。

---

### 2.4 🟢 AgentDisplay vs SubAgentType 映射

**位置**: `src/mini_coder/tui/console_app.py:55-89`

```python
class AgentDisplay(Enum):
    MAIN = "Main"
    EXPLORER = "Explorer"
    # ...

    @classmethod
    def from_agent_type(cls, agent_type: Any) -> "AgentDisplay":
        mapping = {
            "explorer": cls.EXPLORER,
            "planner": cls.PLANNER,
            # ...
        }
```

**问题**: 与 `SubAgentType` 枚举功能重叠，需要手动维护映射关系。

**建议**: 使用单一枚举，或让 `AgentDisplay` 直接使用 `SubAgentType` 的值。

---

## 三、逻辑错误和潜在 Bug

### 3.1 🔴 硬编码的调试日志路径

**位置**: `src/mini_coder/llm/service.py:625-647`

```python
# region agent log
try:
    import json
    import time
    from pathlib import Path

    log_path = Path("/root/LLM/mini-coder/.cursor/debug-61572a.log")  # 硬编码路径！
    log_entry = {
        "sessionId": "61572a",
        "runId": "pre-fix",
        # ...
    }
```

**问题**:
- 硬编码的绝对路径，在其他环境无法工作
- 看起来是调试代码遗留，不应该出现在生产代码中
- 文件路径包含特定 sessionId，疑似调试遗留

**建议**: 移除此调试代码，或改为使用可配置的日志系统。

---

### 3.2 🟡 fail_fast 策略的异常处理不完整

**位置**: `src/mini_coder/agents/scheduler.py:204-223`

```python
if group.fail_strategy == FAIL_STRATEGY_FAIL_FAST:
    done, pending = await asyncio.wait(
        [t for _, t in task_map],
        return_when=asyncio.FIRST_EXCEPTION,
        timeout=group.timeout_total,
    )
    # 取消未完成的任务
    for task in pending:
        task.cancel()
else:
    # ...
```

**问题**: `return_when=asyncio.FIRST_EXCEPTION` 只会在任务抛出异常时返回，但不会处理取消的任务。如果任务被取消而不是异常，可能不会正确触发 fail_fast。

**建议**: 添加对 `asyncio.CancelledError` 的显式处理。

---

### 3.3 🟡 同步/异步 Agent 混合处理

**位置**: `src/mini_coder/agents/scheduler.py:319-351`

```python
async def _run_agent(self, agent, task_brief) -> SubagentResult:
    from mini_coder.agents.enhanced import BaseEnhancedAgent, EnhancedAgentResult

    if isinstance(agent, BaseEnhancedAgent):
        # Enhanced Agent 使用同步 execute
        result = agent.execute(task_brief.intent)  # 同步调用！
        return self._convert_enhanced_result(result, ...)
    else:
        if inspect.iscoroutinefunction(agent.execute):
            result = await agent.execute(task_brief.intent)
        else:
            # 在线程池中运行同步方法
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(...)
```

**问题**:
- `BaseEnhancedAgent.execute` 是同步方法，在异步上下文中直接调用会阻塞事件循环
- 只有非 Enhanced Agent 才会使用 `run_in_executor`

**建议**: 让 `BaseEnhancedAgent` 也支持异步执行，或统一使用 `run_in_executor`。

---

### 3.4 🟡 Agent 类型推断过于简单

**位置**: `src/mini_coder/agents/scheduler.py:398-414`

```python
def _infer_agent_type(self, intent: str) -> str:
    intent_lower = intent.lower()

    if any(kw in intent_lower for kw in ["探索", "查找", "explore", "search", "find"]):
        return "explorer"
    elif any(kw in intent_lower for kw in ["规划", "计划", "plan", "design"]):
        return "planner"
    # ...
```

**问题**:
- 基于简单关键词匹配，容易误判
- 例如："实现探索功能" 会被错误识别为 explorer
- 没有优先级处理

**建议**:
1. 使用更智能的意图分类（如 LLM 辅助）
2. 或允许调用者显式指定 agent_type

---

### 3.5 🟢 循环依赖风险

**位置**: `src/mini_coder/agents/scheduler.py:333`

```python
async def _run_agent(self, agent, task_brief) -> SubagentResult:
    # 检查是否是增强型 Agent
    from mini_coder.agents.enhanced import BaseEnhancedAgent, EnhancedAgentResult
```

**问题**: 在方法内部 import 可能导致循环依赖，且影响性能。

**建议**: 将 import 移到文件顶部，使用 `TYPE_CHECKING` 进行类型检查。

---

## 四、代码质量问题

### 4.1 🟡 过长的方法

| 文件 | 方法 | 行数 | 建议 |
|------|------|------|------|
| `console_app.py` | `_get_user_input` | ~80 行 | 拆分为多个辅助方法 |
| `service.py` | `__init__` | ~50 行 | 使用依赖注入 |
| `scheduler.py` | `schedule_agent_batch` | ~90 行 | 提取结果收集逻辑 |

---

### 4.2 🟡 类型注解不一致

```python
# 有些地方使用旧语法
def get_parameters(self) -> list[ToolParameter]:  # Python 3.9+ 风格

# 有些地方使用旧语法
from typing import List
def get_parameters(self) -> List[ToolParameter]:  # 兼容风格
```

**建议**: 统一使用 Python 3.9+ 的 `list[...]` 语法或全部使用 `typing.List`。

---

### 4.3 🟢 命名不一致

```python
# 常量命名不一致
AGENT_MAIN = "main"           # 大写下划线 ✓
MESSAGE_TYPE_TASK = "task"    # 大写下划线 ✓
fail_strategy = "continue"    # 小写，应该是常量？

# 方法命名不一致
def schedule_agent_batch      # snake_case ✓
def dispatch_parallel_async   # snake_case ✓
def getSystemPrompt           # camelCase ✗ (不存在，但设计文档中有)
```

---

## 五、架构建议

### 5.1 建议的模块结构重构

```
src/mini_coder/
├── agents/
│   ├── __init__.py
│   ├── base.py              # 统一的 BaseAgent（合并 base.py 和 enhanced.py）
│   ├── types.py             # AgentType 枚举、AgentState 等
│   ├── registry.py          # Agent 注册和工厂
│   ├── orchestrator.py      # Orchestrator
│   ├── mailbox.py           # Mailbox 消息定义
│   └── implementations/     # 具体 Agent 实现
│       ├── explorer.py
│       ├── planner.py
│       ├── coder.py
│       └── ...
├── scheduler/
│   ├── __init__.py
│   ├── parallel.py          # ParallelScheduler（只负责 Agent 级）
│   └── tool.py              # ToolScheduler
├── llm/
│   ├── service.py           # 核心 LLM 调用（精简）
│   └── providers/
├── tools/
│   ├── base.py              # 只保留 BaseTool
│   ├── command.py
│   └── ...
├── memory/                  # 保持现状
├── tui/                     # 保持现状
└── common/
    ├── prompt_loader.py     # 统一的 PromptLoader
    ├── config.py            # 配置管理
    └── events.py            # 事件定义
```

### 5.2 建议的接口简化

```python
# 简化后的 Orchestrator 接口
class Orchestrator:
    async def dispatch(self, intent: str, agent_type: AgentType) -> Result: ...
    async def dispatch_parallel(self, tasks: List[Task]) -> List[Result]: ...
    def get_status(self) -> Status: ...

# 简化后的 LLMService 接口
class LLMService:
    async def chat(self, message: str) -> str: ...
    async def chat_stream(self, message: str) -> AsyncIterator[str]: ...
    def set_provider(self, provider: str) -> None: ...

# 分离的服务
class NotesService:
    def add_note(...) -> str: ...
    def search_notes(...) -> List[Note]: ...

class CommandService:
    def execute(self, command: str) -> CommandResult: ...
    def is_safe(self, command: str) -> bool: ...
```

---

## 六、总结

### 严重问题 (需要立即处理)
1. 硬编码调试日志路径 - 安全风险
2. 双重 Agent 基类 - 架构混乱
3. 同步/异步混合处理 - 潜在阻塞

### 中等问题 (建议近期处理)
1. LLMService 职责过重
2. 调度器功能重叠
3. fail_fast 异常处理不完整
4. Agent 类型推断过于简单

### 轻微问题 (可延后处理)
1. 废弃代码清理
2. 类型注解统一
3. 命名规范化
4. 方法拆分

---

## 七、优先修复建议

| 优先级 | 问题 | 预估工时 | 风险 |
|--------|------|----------|------|
| P0 | 移除硬编码调试日志 | 0.5h | 低 |
| P1 | 统一 Agent 基类 | 4h | 中 |
| P1 | 修复同步 Agent 阻塞问题 | 2h | 中 |
| P2 | 拆分 LLMService | 8h | 高 |
| P2 | 合并调度器重复逻辑 | 4h | 中 |
| P3 | 清理废弃代码 | 2h | 低 |

---

*报告完成于 2026-03-07*