# TUI Agent Display Enhancement Design

## Overview

本文档总结了 mini-coder TUI 增强设计方案，目标是让用户能够看到当前正在执行的 Agent 和工具调用情况。

## 概念区分：Agent（子代理）与 Tool（工具）

为避免混淆，先明确两类概念：

| 概念 | 含义 | 在项目中的体现 | TUI 展示方式 |
|------|------|----------------|--------------|
| **Agent / 子代理 (Subagent)** | 由 Orchestrator 派发的**执行主体**，负责某一类任务（探索、规划、编码、评审、测试等）。 | `agents/` 中实现：ExplorerAgent、PlannerAgent、CoderAgent、ReviewerAgent、BashAgent 等（Tester 功能已由 Bash 子代理融合取代）。 | 显示**当前是哪个 Agent 在工作**：`[Explorer]`、`[Planner]`、`[Coder]`、`[Reviewer]`、`[Bash]` 等。 |
| **Tool / 工具** | Agent **在执行过程中调用的能力**，如读文件、写文件、搜索、执行命令等。一个 Agent 可能多次调用多种工具。 | `tools/` 中实现：Read、Write、Grep、Glob、Bash（终端命令）等。 | 显示**当前 Agent 正在使用哪些工具**：`↳ [Tool] Read: src/auth.py`、`↳ [Tool] Grep: "def foo"`、`↳ [Tool] pytest: ...` 等。 |

- **Agent**：谁在做（Explorer / Planner / Coder / Reviewer / Bash；Tester 已由 Bash 取代）。
- **Tool**：该 Agent 正在用什么能力（Read / Write / Grep / Glob / Bash 等）。

设计中的「Agent 名称显示」「Agent 流转」针对**子代理**；「工具调用显示」针对**工具**，且展示在「当前 Agent」的上下文中（例如在 `[Coder]` 下方显示 Coder 调用的 Read/Write）。

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
| Agent（子代理）名称显示 | 显示当前是哪个子代理在工作（Explorer/Planner/Coder/Reviewer/Bash；Tester 已由 Bash 取代） | 高 |
| Agent 流转日志 | 显示子代理开始/完成状态（谁开始、谁结束） | 高 |
| 工具调用显示 | 实时显示当前子代理正在调用的**工具**（Read/Write/Grep/Glob/Bash 等） | 高 |
| 工作目录隔离 | 限制工具只能访问工作目录内路径 | 高 |

**Display Example（子代理 + 该子代理调用的工具）：**
```
[Explorer] 正在探索代码库...          ← 子代理 Explorer 开始
  ↳ [Tool] Grep: "def authenticate"  ← 该 Agent 调用的工具
  ↳ [Tool] Read: src/auth.py

[Planner] 正在创建实现计划...        ← 子代理 Planner 开始
  ↳ [Tool] Write: implementation_plan.md

[Coder] 正在实现功能...              ← 子代理 Coder 开始
  ↳ [Tool] Write: src/auth.py

[Reviewer] 正在评审代码质量...
  ↳ [Pass] 代码质量检查通过           ← 评审结论，非工具

[Bash] 正在运行测试...               ← 子代理 Bash 开始
  ↳ [Tool] pytest: 15 passed in 2.3s  ← Bash 调用的命令/工具
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

- `on_agent_*`：针对**子代理**（Explorer/Planner/Coder/Reviewer/Bash）的开始/完成。
- `on_tool_called`：针对**工具**（Read/Write/Grep/Glob/Bash 等）的调用，展示在「当前子代理」之下。

```python
class AgentDisplay(Enum):
    """子代理显示枚举（Agent = 子代理，非工具）"""
    EXPLORER = "Explorer"
    PLANNER = "Planner"
    CODER = "Coder"
    REVIEWER = "Reviewer"
    BASH = "Bash"
    UNKNOWN = "Unknown"


class MiniCoderConsole:
    def on_agent_started(self, agent_type: str):
        """子代理开始执行回调（显示当前是哪个 Agent 在工作）"""
        self._current_agent = AgentDisplay[agent_type.upper()]
        self._console.print(f"[bold cyan][{self._current_agent.value}] 开始执行...[/bold cyan]")

    def on_tool_called(self, tool_name: str, args: str):
        """工具调用回调（显示当前子代理正在使用的工具：Read/Grep/Bash 等）"""
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

---

## 后续开发方案（Development Roadmap）

本节基于当前代码库盘点，给出可执行的开发顺序与文件级改动建议。

### 一、当前实现状态盘点

| 能力 | 设计文档 | 当前实现 | 缺口说明 |
|------|----------|----------|----------|
| **子代理** 开始/完成回调 | orchestrator 在 dispatch 中 notify | ✅ 已实现 | `_notify_agent_started` / `_notify_agent_completed` 已在 dispatch 中调用 |
| TUI **子代理** 显示 | on_agent_event 打印 `[Explorer]` 等开始/完成 | ✅ 已实现 | `AgentDisplay`、`on_agent_event`、输入提示符旁子代理状态已有 |
| **工具** 调用回调注册 | orchestrator 注册 tool_callback | ✅ 已实现 | `register_tool_callback`、`_create_agent_event_callback` 将 TOOL_* 转给 TUI |
| 子代理在执行时上报**工具**调用 | 各 Agent 在调用 Read/Write/Grep 等时 _emit_event(TOOL_*) | ✅ 部分实现 | 仅 **Planner / Coder / Tester**（Enhanced 系）传入 `event_callback` 并上报工具事件；Explorer、Reviewer、Bash 未接入，故其**工具**调用不显示 |
| 工作目录配置 | config/workdir.yaml | ❌ 未实现 | 需新增配置与 TUI header 展示 |
| 工作目录访问控制 | WorkDirFilter、路径校验 | ❌ 未实现 | 需在**工具**的 filter 层限制读写路径 |

**结论**：Phase 1 中「子代理名称 + 流转」已基本就绪；「工具调用显示」需在更多子代理中接入 event_callback，使其在**调用工具**（Read/Write/Grep 等）时上报；「工作目录隔离」从零实现。

---

### 二、Phase 1 剩余工作（建议执行顺序）

#### 步骤 1：补全工具事件覆盖（高优先级）

**目标**：Explorer、Reviewer、Bash 与 Planner/Coder/Tester 一致，在 TUI 中能看到**该子代理所调用的工具**（Read/Write/Grep/Glob/Bash 等），而不是把子代理本身当工具。

| 任务 | 文件 | 改动要点 |
|------|------|----------|
| 1.1 Explorer 支持 event_callback | `orchestrator.py` / `agents/base.py` | Explorer 作为**子代理**，若其执行过程中会调用 Read/Grep/Glob 等**工具**，需在调用工具时上报 TOOL_*；若当前实现为单次 LLM 调用无工具环，则仅传 event_callback 占位，待后续接入工具环时再上报。 |
| 1.2 Reviewer 支持 event_callback | 同上 | Reviewer 作为**子代理**，若会调用工具则上报；否则仅接口一致。 |
| 1.3 Bash 支持 event_callback | 同上 | Bash 作为**子代理**，其执行的 pytest/mypy/flake8 等可视为对「Bash/命令」**工具**的调用，可在此处上报 TOOL_* 以便 TUI 显示 `↳ [Tool] pytest: ...`。 |

**验收**：TUI 走一遍各子代理，在任一代执行期间，其调用的**工具**（Read/Grep/Bash 等）均有 `↳ [Tool] ...` 输出；子代理名称仍显示为 `[Explorer]`、`[Coder]` 等，不混淆为工具。

---

#### 步骤 2：工作目录配置与展示（高优先级）

| 任务 | 文件 | 改动要点 |
|------|------|----------|
| 2.1 工作目录配置 | `config/workdir.yaml`（新建） | 定义 `working_directory.default_path`、`remember_last`、`access_control.denied_patterns` 等，与设计文档一致。 |
| 2.2 读取并应用配置 | `src/mini_coder/tui/console_app.py` 或独立 config 模块 | 启动时读取 workdir 配置；若存在 `directory` 参数则优先使用，否则用 default_path 或上次记录；可选「启动时询问」。 |
| 2.3 TUI header 显示工作目录 | `src/mini_coder/tui/console_app.py` | 在现有 header（如 `Work Dir: ...`）中显示当前工作目录，确保与运行时的 workdir 一致。 |

**验收**：配置存在时 TUI 标题栏展示正确工作目录；修改配置后重启生效。

---

#### 步骤 3：工作目录访问控制（高优先级）

| 任务 | 文件 | 改动要点 |
|------|------|----------|
| 3.1 WorkDirFilter 实现 | `src/mini_coder/tools/filter.py` | 新增 `WorkDirFilter`，持有 `workdir: Path` 与 `denied_patterns`；实现 `is_path_allowed(path)`：先判 `path` 是否在 workdir 下，再判是否匹配 denied_patterns。 |
| 3.2 集成到 Read/Write/Glob 等工具 | 各工具调用处或 ToolFilter 链 | 在现有工具执行前对路径参数做 WorkDirFilter 校验；拒绝时返回明确错误（如「路径不在工作目录内」），避免泄露内部路径。 |
| 3.3 与 TUI 工作目录一致 | `console_app.py` / orchestrator | 创建子 Agent 或工具执行时传入的 workdir 与 TUI 当前工作目录同源（同一配置或同一变量）。 |

**验收**：工作目录外的路径无法被 Read/Write/Glob 访问；TUI 显示的工作目录与过滤使用目录一致。

---

#### 步骤 4：Phase 1 集成与测试

| 任务 | 说明 |
|------|------|
| 4.1 回归 Agent 流转 | 再次验证 Agent 开始/完成、提示符旁 Agent 名称无退化。 |
| 4.2 工具日志端到端 | 全链路（含 Explorer/Reviewer/Bash）工具调用均在 TUI 有 `↳ [Tool]` 输出。 |
| 4.3 工作目录与安全 | 配置 workdir 后，仅该目录下可访问；尝试访问外部路径有明确拒绝提示。 |
| 4.4 更新 tasks.md | 将上述步骤 1–3 对应到 `openspec/changes/enhance-tui-agent-display/tasks.md` 中具体 checkbox，完成一项勾一项。 |

---

### 三、Phase 2：Debug 功能（建议顺序）

1. **/context 命令**：在 LLMService 或 ContextBuilder 中提供「当前上下文统计」（如 message 数、token 估算），TUI 解析 `/context` 后调用并格式化输出。
2. **/debug 切换**：已有 `_ui_state.debug_mode` 时，增加 `/debug` 命令切换，并保持现有 Debug 模式下 LLM 上下文/响应信息展示。
3. **JSONL 日志**：在 TUI 或 orchestrator 层将 Agent 事件、工具调用写入 JSONL 文件，路径可配置；可选 `/logs` 命令查看最近 N 条。

---

### 四、Phase 3：增强显示（可选）

- Agent 流程图、Token 仪表板、/settings 等按需求再排期；实现前可再细化设计（如 ASCII 流程图的数据来源与刷新策略）。

---

### 五、文档与 DoD

- **CLAUDE.md**：在「Project Status」或「TUI」相关小节注明「Agent 显示与工具日志已接入；工作目录隔离见 config/workdir.yaml 与 WorkDirFilter」。
- **Definition of Done**：Phase 1 以「步骤 1–3 完成 + 步骤 4 集成测试通过 + 无严重 bug」为达标；Phase 2 以「/context、/debug、JSONL 日志可用」为达标。
