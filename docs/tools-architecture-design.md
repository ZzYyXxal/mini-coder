# 工具框架架构设计

> **版本**: 2.0
> **更新日期**: 2026-03-06
> **状态**: 已实现
> **设计目标**: 实现工具的"代码框架 + 动态提示词注入"模式

---

## 1. 架构概述

### 1.1 设计决策：Memory 不是 Tool

经过仔细分析，我们决定 **Memory 应该保持为独立基础设施，而不是实现为 Tool**。原因如下：

| 原因 | 说明 |
|------|------|
| **1. 基础设施 vs 能力** | Memory 是上下文管理基础设施，不是 LLM 可调用的能力。Tool 是供 LLM 调用的；Memory 是用于会话状态管理。 |
| **2. 访问模式差异** | Tool 遵循"请求-响应"模式（LLM 发起）；Memory 需要自动触发（92% 阈值压缩，透明读写）。 |
| **3. 安全边界** | Tool 有安全过滤器（ReadOnly/FullAccess）；Memory 访问控制应由会话管理层处理，而非 ToolFilter。 |
| **4. 实现复杂性** | 将 Memory 实现为 Tool 需要内部调用（Main Agent → Memory Tool），增加复杂性。直接方法调用更高效。 |

### 1.2 当前实现状态

| 组件 | 状态 | 描述 |
|------|------|------|
| **BaseTool 2.0** | ✅ 已实现 | 支持动态提示词加载的抽象基类 |
| **PromptLoader** | ✅ 已实现 | 从 `prompts/tools/*.md` 加载提示词，支持插值 |
| **CommandTool v2.0** | ✅ 已实现 | 已迁移到 BaseTool 2.0，支持事件回调 |
| **ToolEventAdapter** | ✅ 已实现 | 桥接工具事件到 TUI 回调 |
| **ToolFilter** | ✅ 已存在 | ReadOnly, FullAccess, BashRestricted 过滤器 |

---

## 2. 工具模块架构

### 2.1 模块结构

```
src/mini_coder/tools/
├── __init__.py              # 模块导出
├── base.py                  # BaseTool 2.0 + Tool v1.0 (向后兼容)
├── command.py               # CommandTool v2.0
├── executor.py              # SafeExecutor - subprocess 封装
├── security.py              # SecurityLevel - 黑名单/白名单
├── permission.py            # PermissionService - 用户确认
├── filter.py                # ToolFilter 实现
├── prompt_loader.py         # 动态提示词加载
└── event_adapter.py         # ToolEventAdapter 用于 TUI 集成
```

### 2.2 类层次结构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           工具模块架构                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Tool (v1.0) - 旧版本                          │   │
│  │                        BaseTool (v2.0) - 新版本                      │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │  共同接口:                                                           │   │
│  │  - run(parameters) -> ToolResponse                                  │   │
│  │  - get_parameters() -> list[ToolParameter]                          │   │
│  │                                                                      │   │
│  │  BaseTool 2.0 新增:                                                  │   │
│  │  - get_system_prompt(context) -> str                                │   │
│  │  - notify_event(event_type, data)                                   │   │
│  │  - get_config(key, default) -> Any                                  │   │
│  │  - to_dict() -> Dict                                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                     │
│                                      ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        CommandTool (v2.0)                            │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │  组件:                                                               │   │
│  │  ├── SecurityLevel (黑名单/白名单/确认)                             │   │
│  │  ├── PermissionService (用户审批)                                   │   │
│  │  └── SafeExecutor (带超时/输出限制的 subprocess)                    │   │
│  │                                                                      │   │
│  │  事件: start → security_check → [permission_request] → complete     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                          支撑组件                                    │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │  ├── PromptLoader: 从 prompts/tools/*.md 加载提示词                 │   │
│  │  ├── ToolEventAdapter: 桥接事件到 TUI 回调                           │   │
│  │  └── ToolFilter: 控制工具访问 (ReadOnly/FullAccess 等)              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. BaseTool 2.0 框架

### 3.1 核心特性

1. **动态提示词加载**: 从 `prompts/tools/*.md` 加载工具提示词
2. **事件回调**: 通知 TUI 工具执行进度
3. **配置支持**: 通过 `config/tools.yaml` 配置工具行为
4. **向后兼容**: 保留 v1.0 Tool 接口

### 3.2 BaseTool 接口

```python
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional

class BaseTool(ABC):
    """所有工具的基类，支持动态提示词 (v2.0)"""

    def __init__(
        self,
        name: str,
        description: str,
        prompt_path: Optional[str] = None,
        event_callback: Optional[Callable[[str, str, Dict[str, Any]], None]] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """初始化 BaseTool

        Args:
            name: 工具名称
            description: 工具描述
            prompt_path: 提示词模板路径（相对于 prompts/）
            event_callback: 工具事件回调（用于 TUI 显示）
                           签名: callback(tool_name, event_type, data)
            config: 工具配置字典
        """
        ...

    @abstractmethod
    def run(self, parameters: Dict[str, Any]) -> "ToolResponse":
        """执行工具"""
        pass

    @abstractmethod
    def get_parameters(self) -> list["ToolParameter"]:
        """获取工具参数定义"""
        pass

    def get_system_prompt(self, context: Dict[str, Any] = None) -> str:
        """获取工具特定的系统提示词（带上下文插值）"""
        ...

    def notify_event(self, event_type: str, data: Dict[str, Any] = None) -> None:
        """通知工具事件到回调（用于 TUI 显示）"""
        ...

    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        ...

    def to_dict(self) -> Dict[str, Any]:
        """将工具信息转换为字典"""
        ...
```

---

## 4. CommandTool v2.0 架构

### 4.1 安全层

```
┌─────────────────────────────────────────────────────────────────┐
│                     CommandTool 安全流程                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  输入: 命令字符串                                                │
│         ↓                                                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 第一层: 黑名单检查                                         │  │
│  │ - rm -rf, curl, wget, sudo, chmod, dd 等                  │  │
│  │ → 匹配则拒绝                                               │  │
│  └──────────────────────────────────────────────────────────┘  │
│         ↓                                                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 第二层: 白名单检查 (安全命令)                               │  │
│  │ - ls, pwd, cat, git status, git log 等                    │  │
│  │ → 直接执行（无需确认）                                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│         ↓                                                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 第三层: 安全模式检查                                        │  │
│  │                                                           │  │
│  │ ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │  │
│  │ │   STRICT    │  │   NORMAL    │  │   TRUST     │        │  │
│  │ │ 仅白名单    │  │ 用户确认    │  │ 直接执行    │        │  │
│  │ └─────────────┘  └─────────────┘  └─────────────┘        │  │
│  └──────────────────────────────────────────────────────────┘  │
│         ↓                                                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ SafeExecutor                                              │  │
│  │ - 超时控制 (默认 120s, 最大 600s)                          │  │
│  │ - 输出截断 (最大 30KB)                                     │  │
│  │ - 工作目录限制                                             │  │
│  └──────────────────────────────────────────────────────────┘  │
│         ↓                                                       │
│  输出: CommandResult (success, stdout, stderr, exit_code)       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 事件流

```
┌─────────────────────────────────────────────────────────────────┐
│                    CommandTool 事件流                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  run() 被调用                                                    │
│      │                                                          │
│      ▼                                                          │
│  ┌─────────────┐                                                │
│  │    start    │ ──→ {"command": "..."}                        │
│  └─────────────┘                                                │
│      │                                                          │
│      ▼                                                          │
│  ┌──────────────────┐                                           │
│  │  security_check  │ ──→ {"command": "...", "category": "..."}│
│  └──────────────────┘                                           │
│      │                                                          │
│      ▼ (如果非安全命令)                                          │
│  ┌──────────────────────┐                                       │
│  │ permission_request   │ ──→ {"command": "...", "reason": ".."}│
│  └──────────────────────┘                                       │
│      │                                                          │
│      ▼                                                          │
│  ┌───────────────┐       ┌───────────────┐                     │
│  │   complete    │  或   │     error     │                     │
│  └───────────────┘       └───────────────┘                     │
│      │                        │                                  │
│      ▼                        ▼                                  │
│  {"exit_code": 0,        {"error_code": "...",                 │
│   "duration_ms": ...}     "error_message": "..."}              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. ToolEventAdapter - TUI 集成

### 5.1 目的

将 BaseTool 2.0 事件桥接到 TUI 回调，实现工具执行的实时显示。

### 5.2 使用方法

```python
from mini_coder.tools import CommandTool, ToolEventAdapter, ToolEventCollector

# 方式 1: 使用 TUI 回调
adapter = ToolEventAdapter(tui_callback=console_app.on_tool_called)
tool = CommandTool(event_callback=adapter.create_callback())

# 方式 2: 使用收集器进行测试
collector = ToolEventCollector()
tool = CommandTool(event_callback=collector.create_callback())

# 执行后检查事件
events = collector.get_events()
print(f"事件: {[e.event_type for e in events]}")
```

### 5.3 事件映射

| 工具事件 | TUI 状态 | 显示 |
|----------|----------|------|
| `start` | `starting` | `[Tool] Command: echo hello` |
| `complete` | `completed` | `[Tool] Command (1.23s)` |
| `error` | `failed` | `[Tool] Command (FAILED)` |
| `security_check` | (内部) | 不显示 |
| `permission_request` | `permission_request` | 权限对话框 |

---

## 6. 提示词系统

### 6.1 目录结构

```
prompts/
├── system/                    # Agent 系统提示词
│   ├── main-agent.md
│   └── subagent-*.md
├── tools/                     # 工具特定提示词
│   └── command.md            # CommandTool 提示词模板
└── templates/                 # 共享模板
    └── coding-standards.md
```

### 6.2 提示词模板示例

`prompts/tools/command.md`:

```markdown
# Command Tool

You are the **Command** tool - a safe system command executor.

## Security Model

1. **Blacklist Check**: Dangerous commands are rejected
2. **Whitelist**: Safe commands execute without confirmation
3. **Requires Confirmation**: Other commands need approval

Current security mode: `{{security_mode}}`
Timeout: {{timeout}} seconds (max: {{max_timeout}})
```

### 6.3 PromptLoader

```python
class PromptLoader:
    """动态提示词加载器，支持模板插值"""

    def load(
        self,
        prompt_path: str,
        context: Dict[str, Any] = None,
        use_cache: bool = True,
    ) -> str:
        """加载并插值提示词模板"""
        ...
```

---

## 7. 配置

### 7.1 tools.yaml 结构

```yaml
command:
  prompt_path: "tools/command.md"
  security_mode: normal
  timeout:
    default: 120
    max: 600
  max_output_length: 30000
  allowed_paths:
    - ${PROJECT_ROOT}
    - /tmp
  events:
    enabled: true
    on_start: true
    on_complete: true
    on_error: true

tool_filter:
  default_for_subagent: readonly
  agent_filters:
    explore: readonly
    plan: readonly
    code: full_access
```

---

## 8. ToolFilter 架构

### 8.1 过滤器类型

| 过滤器 | 用途 | 使用场景 |
|--------|------|----------|
| **ReadOnlyFilter** | 只读访问 | Explorer, Reviewer |
| **FullAccessFilter** | 完全访问（排除危险命令） | Coder |
| **BashRestrictedFilter** | Bash 命令过滤 | Bash Agent |
| **WorkDirFilter** | 工作目录过滤 | 所有文件工具 |
| **CustomFilter** | 用户自定义 | 自定义 agent |

### 8.2 过滤器层次

```
ToolFilter (抽象基类)
├── ReadOnlyFilter
├── FullAccessFilter
├── BashRestrictedFilter
├── WorkDirFilter
└── CustomFilter
```

---

## 9. 工具执行流程

### 9.1 完整流程图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          工具执行流程                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. 用户/Agent 请求                                                          │
│     │                                                                       │
│     ▼                                                                       │
│  2. ToolFilter.check_access(tool_name, parameters)                         │
│     │                                                                       │
│     ├─ DENIED → 返回 ToolResponse.error("访问被拒绝")                       │
│     │                                                                       │
│     ▼                                                                       │
│  3. BaseTool.run(parameters)                                               │
│     │                                                                       │
│     ├─ notify_event("start", {...})                                        │
│     │                                                                       │
│     ▼                                                                       │
│  4. 工具特定逻辑（如 CommandTool 安全检查）                                   │
│     │                                                                       │
│     ├─ notify_event("security_check", {...})                               │
│     │                                                                       │
│     ▼                                                                       │
│  5. 执行工具动作                                                              │
│     │                                                                       │
│     ├─ 成功 → notify_event("complete", {...})                              │
│     │         返回 ToolResponse.success(...)                                │
│     │                                                                       │
│     └─ 失败 → notify_event("error", {...})                                 │
│               返回 ToolResponse.error(...)                                  │
│                                                                             │
│  6. ToolEventAdapter 将事件转换为 TUI 格式                                   │
│     │                                                                       │
│     ▼                                                                       │
│  7. TUI 显示工具状态                                                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 9.2 代码示例

```python
from mini_coder.tools import (
    CommandTool,
    ToolEventAdapter,
    SecurityMode,
)

# 1. 创建事件适配器用于 TUI
def on_tool_event(tool_name, args, status, duration, result):
    print(f"[{tool_name}] {status}: {args} ({duration:.2f}s)")

adapter = ToolEventAdapter(tui_callback=on_tool_event)

# 2. 创建带事件回调的工具
tool = CommandTool(
    security_mode=SecurityMode.NORMAL,
    event_callback=adapter.create_callback(),
    config={
        "timeout": 120,
        "max_output_length": 30000,
    }
)

# 3. 执行命令
result = tool.run({"command": "git status"})

# 4. 检查结果
if result.error_code is None:
    print(f"成功: {result.text}")
else:
    print(f"错误: {result.error_code} - {result.text}")
```

---

## 10. 实现清单

### 已完成

- [x] **Phase 1: 文档与规划**
  - [x] 架构设计文档
  - [x] 设计决策文档

- [x] **Phase 2: BaseTool 2.0 框架**
  - [x] `src/mini_coder/tools/base.py` - BaseTool 2.0
  - [x] `src/mini_coder/tools/prompt_loader.py` - PromptLoader
  - [x] `prompts/tools/command.md` - Command 提示词模板

- [x] **Phase 3: CommandTool 迁移**
  - [x] 迁移 CommandTool 到 BaseTool 2.0
  - [x] 添加 event_callback 支持
  - [x] 更新 tools.yaml 配置

- [x] **Phase 4: 集成与测试**
  - [x] `src/mini_coder/tools/event_adapter.py` - ToolEventAdapter
  - [x] BaseTool 2.0 单元测试
  - [x] ToolEventAdapter 单元测试
  - [x] 集成测试

### 未来增强

- [ ] 更多工具提示词模板
- [ ] 工具响应缓存
- [ ] 工具链支持
- [ ] 更复杂的提示词插值

---

## 11. 相关文档

- `docs/multi-agent-architecture-design.md` - Agent 架构
- `docs/command-execution-security-design.md` - 命令安全
- `CLAUDE.md` - 项目概述和工作流
- `prompts/tools/command.md` - Command 工具提示词模板