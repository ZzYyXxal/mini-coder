# Design: Enhance TUI Agent Display

## Architecture Overview

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

## Component Design

### 1. Event System Extension

**文件**: `src/mini_coder/agents/enhanced.py`

添加新的事件类型：

```python
class EventType(Enum):
    # ... 现有事件类型 ...

    # TUI 新增事件类型
    AGENT_STARTED = "agent_started"      # Agent 开始执行
    AGENT_COMPLETED = "agent_completed"  # Agent 执行完成
    TOOL_STARTING = "tool_starting"      # 工具开始执行
    TOOL_COMPLETED = "tool_completed"    # 工具执行完成
```

### 2. Orchestrator State Callback

**文件**: `src/mini_coder/agents/orchestrator.py`

扩展状态回调机制：

```python
class WorkflowOrchestrator:
    def register_state_callback(self, state: WorkflowState, callback: Callable) -> None:
        """注册状态回调"""
        self._state_callbacks[state].append(callback)

    def register_agent_callback(self, callback: Callable) -> None:
        """注册 Agent 事件回调"""
        self._agent_callbacks.append(callback)

    def dispatch(self, intent: str, context: Optional[Dict] = None) -> EnhancedAgentResult:
        """派发子代理"""
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

**文件**: `src/mini_coder/tui/console_app.py`

修改 WorkingMode 为 Agent 显示：

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
    def __init__(self, config: Config, directory: str | None = None) -> None:
        self._current_agent: Optional[AgentDisplay] = None
        self._tool_logs: List[str] = []

    def on_agent_started(self, agent_type: str):
        """Agent 开始执行回调"""
        self._current_agent = AgentDisplay[agent_type.upper()]
        self._console.print(f"[bold cyan][{self._current_agent.value}] 开始执行...[/bold cyan]")

    def on_tool_called(self, tool_name: str, args: str):
        """工具调用回调"""
        self._console.print(f"  ↳ [dim][Tool] {tool_name}: {args}[/dim]")
```

### 4. Working Directory Configuration

**文件**: `config/workdir.yaml`

```yaml
# 工作目录配置

working_directory:
  # 默认工作目录（可选，为空则在启动时选择）
  default_path: ""

  # 是否记住上次使用的目录
  remember_last: true

  # 启动时是否总是询问
  always_ask: false

# 访问控制（相对于工作目录）
access_control:
  # 允许读取的模式
  allowed_patterns:
    - "**/*"

  # 禁止读取的模式
  denied_patterns:
    - "../**"           # 禁止访问父目录
    - "/etc/**"         # 禁止访问系统目录
    - "**/.env"         # 禁止访问.env 文件
    - "**/credentials*" # 禁止访问凭证文件
```

### 5. Access Control Filter

**文件**: `src/mini_coder/tools/filter.py`

添加工具访问控制：

```python
class WorkDirFilter(ToolFilter):
    """工作目录访问控制过滤器"""

    def __init__(self, workdir: Path, config: dict):
        self.workdir = workdir.resolve()
        self.allowed_patterns = config.get('allowed_patterns', ['**/*'])
        self.denied_patterns = config.get('denied_patterns', [])

    def filter(self, tools: List[str]) -> List[str]:
        """过滤工具列表"""
        # 检查工作目录是否设置
        if not self.workdir:
            return []  # 没有工作目录，禁止所有工具

        return tools

    def is_path_allowed(self, path: Path) -> bool:
        """检查路径是否允许访问"""
        path = path.resolve()

        # 检查是否在工作目录内
        try:
            path.relative_to(self.workdir)
        except ValueError:
            return False  # 不在工作目录内

        # 检查 denied patterns
        for pattern in self.denied_patterns:
            if path.match(pattern):
                return False

        return True
```

## Data Flow

### Agent Execution Flow

```
User Request
    │
    ▼
┌─────────────────┐
│ TUI Input       │
│ - 用户输入请求  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Orchestrator    │
│ dispatch()      │───────→ on_agent_started(agent_type)
└────────┬────────┘         [Explorer] 开始执行...
         │
         ▼
┌─────────────────┐
│ SubAgent        │
│ execute()       │
└────────┬────────┘
         │
         ├──────────────────┐
         │                  │
         ▼                  ▼
┌─────────────────┐  ┌─────────────────┐
│ Tool Called     │  │ LLM Invocation  │
│ on_tool_called()│  │ (no callback)   │
│ [Tool] Read: x  │  │                 │
└─────────────────┘  └─────────────────┘
         │
         ▼
┌─────────────────┐
│ Agent Complete  │
│ on_agent_       │
│ completed()     │
│ [Explorer] ✓    │
└─────────────────┘
```

## Implementation Details

### Event Notification Implementation

```python
# In orchestrator.py
def _notify_agent_started(self, agent_type: SubAgentType):
    """通知 Agent 开始事件"""
    for callback in self._agent_callbacks:
        try:
            callback({
                "event": "agent_started",
                "agent_type": agent_type.value,
                "timestamp": time.time()
            })
        except Exception as e:
            logger.exception(f"Agent callback error: {e}")

def _notify_agent_completed(self, agent_type: SubAgentType, result):
    """通知 Agent 完成事件"""
    for callback in self._agent_callbacks:
        try:
            callback({
                "event": "agent_completed",
                "agent_type": agent_type.value,
                "success": result.success,
                "timestamp": time.time()
            })
        except Exception as e:
            logger.exception(f"Agent callback error: {e}")
```

### TUI Callback Registration

```python
# In console_app.py
def setup_agent_callbacks(self, orchestrator: WorkflowOrchestrator):
    """设置 Agent 回调"""
    def on_agent_event(event: dict):
        agent = event['agent_type'].upper()
        if event['event'] == 'agent_started':
            self._current_agent = agent
            self._console.print(f"\n[bold cyan][{agent}] 开始执行...[/bold cyan]")
        elif event['event'] == 'agent_completed':
            status = "✓ 完成" if event['success'] else "✗ 失败"
            self._console.print(f"[bold cyan][{agent}] {status}[/bold cyan]")

    orchestrator.register_agent_callback(on_agent_event)
```

## Testing Strategy

### Unit Tests

1. **Test WorkDirFilter** - 测试工作目录访问控制
2. **Test Agent Event Notification** - 测试事件通知
3. **Test TUI Callback** - 测试 TUI 回调

### Integration Tests

1. **Test Full Workflow** - 测试完整工作流（Explorer → Bash）
2. **Test Tool Logging** - 测试工具日志显示
3. **Test WorkDir Isolation** - 测试工作目录隔离

## Migration Plan

### Backward Compatibility

- 现有的 WorkingMode 枚举保留，作为 fallback
- 回调是可选的，不影响现有代码
- 工作目录配置是可选的，默认为当前目录

### Rollout Plan

1. 先实现核心事件系统
2. 添加 TUI 显示
3. 实现工作目录隔离
4. 测试和文档
