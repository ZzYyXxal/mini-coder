# TUI Agent Display Enhancement Design

## Overview

本文档总结了 mini-coder TUI 增强设计方案，目标是让用户能够看到当前正在执行的 Agent 和工具调用情况。

## Problem Statement

当前 TUI 存在以下问题：

1. **显示的是模式而非 Agent** - TUI 显示 PLAN/CODE/EXECUTE 模式，但用户无法知道实际是哪个 Agent 在处理请求
2. **缺少 Agent 流转可视化** - 用户看不到 Agent 之间的切换过程
3. **缺少工具使用显示** - 用户看不到正在使用的工具
4. **缺少上下文信息** - 没有 Token 使用、上下文组成等信息显示
5. **缺少工作目录隔离** - mini-coder 可能读取/修改自身代码，存在安全隐患

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    TUI Agent 追踪架构                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  事件源 (Event Sources) → 事件处理 → TUI 显示                     │
│                                                                 │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐ │
│  │ Orchestrator │      │  SubAgents   │      │ LLM Service  │ │
│  │              │      │              │      │              │ │
│  │ - 状态变化   │      │ - 工具调用   │      │ - Token 使用  │ │
│  │ - Agent 派发  │      │ - 执行完成   │      │ - 上下文组成  │ │
│  └───────┬──────┘      └───────┬──────┘      └───────┬──────┘ │
│          │                     │                     │         │
│          └─────────────────────┼─────────────────────┘         │
│                                │                                │
│                                ▼                                │
│                      ┌─────────────────┐                        │
│                      │  Event Callback │                        │
│                      │  (状态回调)     │                        │
│                      └────────┬────────┘                        │
│                               │                                 │
│                               ▼                                 │
│                      ┌─────────────────┐                        │
│                      │   TUI Display   │                        │
│                      │  - Agent 名称    │                        │
│                      │  - 工具日志      │                        │
│                      │  - 流转状态      │                        │
│                      └─────────────────┘                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Phased Implementation Plan

### Phase 1: MVP + 安全（当前 Change）

| 功能 | 描述 | 优先级 |
|------|------|--------|
| Agent 名称显示 | 显示当前 Agent（Explorer/Planner/Coder/Reviewer/Bash） | 高 |
| Agent 流转日志 | 显示 Agent 开始/完成状态 | 高 |
| 工具调用显示 | 实时显示正在使用的工具 | 高 |
| 工作目录隔离 | 限制 Agent 只能访问工作目录 | 高 |

**Display Example:**
```
[Explorer] 正在探索代码库...
  ↳ [Tool] Grep: "def authenticate" in **/*.py
  ↳ [Tool] Read: src/auth.py

[Planner] 正在创建实现计划...
  ↳ [Tool] Write: implementation_plan.md

[Coder] 正在实现功能...
  ↳ [Tool] Write: src/auth.py

[Reviewer] 正在评审代码质量...
  ↳ [Pass] 代码质量检查通过

[Bash] 正在运行测试...
  ↳ [Tool] pytest: 15 passed in 2.3s
```

### Phase 2: Debug 功能（后续）

| 功能 | 描述 | 优先级 |
|------|------|--------|
| /context 命令 | 显示 Token 使用情况和上下文组成 | 中 |
| Debug 模式 | /debug 命令切换详细日志 | 中 |
| 日志文件 | JSONL 格式记录执行轨迹 | 低 |

### Phase 3: 增强显示（可选）

| 功能 | 描述 | 优先级 |
|------|------|--------|
| Agent 流程图 | ASCII 进度条显示 Agent 流转 | 低 |
| Token 仪表板 | 实时 Token 使用统计 | 低 |
| 配置界面 | /settings 命令配置显示选项 | 低 |

## Component Design

### 1. Event System Extension

**File:** `src/mini_coder/agents/enhanced.py`

```python
class EventType(Enum):
    # TUI 新增事件类型
    AGENT_STARTED = "agent_started"      # Agent 开始执行
    AGENT_COMPLETED = "agent_completed"  # Agent 执行完成
    TOOL_STARTING = "tool_starting"      # 工具开始执行
    TOOL_COMPLETED = "tool_completed"    # 工具执行完成
```

### 2. Orchestrator State Callback

**File:** `src/mini_coder/agents/orchestrator.py`

```python
class WorkflowOrchestrator:
    def dispatch(self, intent: str, context: Optional[Dict] = None):
        # 1. 分析意图
        agent_type = self._analyze_intent(intent)

        # 2. 发送 Agent 开始事件
        self._notify_agent_started(agent_type)

        # 3. 创建子代理
        agent = self._create_subagent(agent_type)

        # 4. 执行任务
        result = agent.execute(intent, context=context)

        # 5. 发送 Agent 完成事件
        self._notify_agent_completed(agent_type, result)

        return result
```

### 3. TUI Agent Display

**File:** `src/mini_coder/tui/console_app.py`

```python
class AgentDisplay(Enum):
    """Agent 显示枚举"""
    EXPLORER = "Explorer"
    PLANNER = "Planner"
    CODER = "Coder"
    REVIEWER = "Reviewer"
    BASH = "Bash"
    UNKNOWN = "Unknown"


class MiniCoderConsole:
    def on_agent_started(self, agent_type: str):
        """Agent 开始执行回调"""
        self._current_agent = AgentDisplay[agent_type.upper()]
        self._console.print(f"[bold cyan][{self._current_agent.value}] 开始执行...[/bold cyan]")

    def on_tool_called(self, tool_name: str, args: str):
        """工具调用回调"""
        self._console.print(f"  ↳ [dim][Tool] {tool_name}: {args}[/dim]")
```

### 4. Working Directory Configuration

**File:** `config/workdir.yaml`

```yaml
working_directory:
  default_path: ""
  remember_last: true
  always_ask: false

access_control:
  allowed_patterns:
    - "**/*"
  denied_patterns:
    - "../**"
    - "/etc/**"
    - "**/.env"
    - "**/credentials*"
```

### 5. Access Control Filter

**File:** `src/mini_coder/tools/filter.py`

```python
class WorkDirFilter(ToolFilter):
    """工作目录访问控制过滤器"""

    def __init__(self, workdir: Path, config: dict):
        self.workdir = workdir.resolve()
        self.denied_patterns = config.get('denied_patterns', [])

    def is_path_allowed(self, path: Path) -> bool:
        """检查路径是否允许访问"""
        path = path.resolve()

        # 必须在工作目录内
        try:
            path.relative_to(self.workdir)
        except ValueError:
            return False

        # 不能匹配 denied patterns
        for pattern in self.denied_patterns:
            if path.match(pattern):
                return False

        return True
```

## Implementation Status

- [x] OpenSpec Change 创建
- [x] Proposal 文档完成
- [x] Design 文档完成
- [x] Specs 完成（3 个 capability）
- [x] Tasks 文档完成
- [ ] Phase 1 实现中
- [ ] Phase 2 待开始
- [ ] Phase 3 待评估

## Related Files

| File | Status |
|------|--------|
| `openspec/changes/enhance-tui-agent-display/proposal.md` | ✓ |
| `openspec/changes/enhance-tui-agent-display/design.md` | ✓ |
| `openspec/changes/enhance-tui-agent-display/tasks.md` | ✓ |
| `openspec/changes/enhance-tui-agent-display/specs/agent-event-notification/spec.md` | ✓ |
| `openspec/changes/enhance-tui-agent-display/specs/tui-agent-display/spec.md` | ✓ |
| `openspec/changes/enhance-tui-agent-display/specs/workdir-isolation/spec.md` | ✓ |

## Next Steps

1. 开始 Phase 1 实现
2. 按照 tasks.md 中的任务列表逐项完成
3. 完成一项测试一项
4. 所有 Phase 1 任务完成后进行集成测试
