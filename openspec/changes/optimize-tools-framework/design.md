# Technical Design: Optimize Tools Framework

## Architecture Overview

### System Context

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LLMService                                           │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    Memory Subsystem (基础设施)                       │   │
│   │   - ContextMemoryManager (独立，不是 Tool)                          │   │
│   │   - ContextBuilder (GSSC pipeline)                                  │   │
│   │   - ProjectNotesManager                                             │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                   Tools Registry (工具注册表)                        │   │
│   │   ┌─────────────────────────────────────────────────────────────┐   │   │
│   │   │              BaseTool 2.0 Framework                         │   │   │
│   │   │   - CommandTool (migrated)                                  │   │   │
│   │   │   - Future Tools...                                         │   │   │
│   │   └─────────────────────────────────────────────────────────────┘   │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Design

### 1. BaseTool 2.0 Class

```python
class BaseTool(ABC):
    """Base class for all tools with dynamic prompt support"""

    # Class variables
    TOOL_TYPE: str = "base"
    DEFAULT_PROMPT_PATH: Optional[str] = None

    def __init__(
        self,
        name: str,
        description: str,
        prompt_path: Optional[str] = None,
        event_callback: Optional[Callable] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.description = description
        self.config = config or {}
        self._event_callback = event_callback
        self._prompt_loader = PromptLoader()
        self._prompt_path = prompt_path

    @abstractmethod
    def run(self, parameters: Dict[str, Any]) -> ToolResponse:
        pass

    @abstractmethod
    def get_parameters(self) -> List[ToolParameter]:
        pass

    def get_system_prompt(self, context: Dict[str, Any] = None) -> str:
        if self._prompt_path:
            return self._prompt_loader.load(self._prompt_path, context)
        return self._get_default_prompt()

    def notify_event(self, event_type: str, data: Dict[str, Any] = None) -> None:
        if self._event_callback:
            self._event_callback(
                tool_name=self.name,
                event_type=event_type,
                data=data or {},
            )
```

### 2. PromptLoader Class

```python
class PromptLoader:
    """Dynamic prompt loader with template interpolation"""

    def __init__(self, base_dir: str = "prompts"):
        self.base_dir = Path(base_dir)
        self._cache: Dict[str, str] = {}

    def load(
        self,
        prompt_path: str,
        context: Dict[str, Any] = None,
        use_cache: bool = True,
    ) -> str:
        # Check cache
        if use_cache and prompt_path in self._cache:
            prompt = self._cache[prompt_path]
        else:
            full_path = self.base_dir / prompt_path
            if full_path.exists():
                prompt = full_path.read_text(encoding="utf-8")
            else:
                prompt = self._get_fallback_prompt(prompt_path)

            if use_cache:
                self._cache[prompt_path] = prompt

        # Interpolate context
        if context:
            for key, value in context.items():
                prompt = prompt.replace(f"{{{{{key}}}}}", str(value))

        return prompt
```

### 3. CommandTool Migration

```python
class CommandTool(BaseTool):
    """Safe system command executor (v2.0)"""

    TOOL_TYPE = "command"
    DEFAULT_PROMPT_PATH = "tools/command.md"

    def __init__(
        self,
        security_mode: str = "normal",
        event_callback: Optional[Callable] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            name="Command",
            description="Safe system command executor",
            prompt_path=self.DEFAULT_PROMPT_PATH,
            event_callback=event_callback,
            config=config,
        )

        self.security_mode = security_mode
        self._security = SecurityLevel()
        self._executor = SafeExecutor()

    def run(self, parameters: Dict[str, Any]) -> ToolResponse:
        command = parameters.get("command", "")

        # Emit start event
        self.notify_event("start", {"command": command})

        # Security check
        if self._security.is_banned(command):
            self.notify_event("error", {"code": "BANNED", "command": command})
            return ToolResponse.error("BANNED", "命令被禁止")

        # Execute
        result = self._executor.execute(command)

        # Emit complete event
        self.notify_event("complete", {
            "command": command,
            "exit_code": result.exit_code,
            "duration_ms": result.execution_time_ms,
        })

        if result.success:
            return ToolResponse.success(text=result.stdout)
        else:
            return ToolResponse.error("EXECUTION_FAILED", result.stderr)
```

## File Structure

```
mini-coder/
├── src/mini_coder/tools/
│   ├── base.py              # Existing - will add BaseTool 2.0
│   ├── command.py           # Migrate to BaseTool 2.0
│   ├── filter.py            # Existing - keep compatible
│   ├── security.py          # Existing - keep compatible
│   ├── executor.py          # Existing - keep compatible
│   ├── permission.py        # Existing - keep compatible
│   └── prompt_loader.py     # New - PromptLoader class
├── prompts/
│   ├── system/              # Existing - Agent prompts
│   └── tools/               # New - Tool prompts
│       └── command.md       # CommandTool prompt template
└── config/
    └── tools.yaml           # Update with new configuration
```

## Interface Changes

### Before (v1.0)

```python
from mini_coder.tools import CommandTool

tool = CommandTool(
    security_mode="normal",
    permission_service=permission_service,
    timeout=120,
)
result = tool.run({"command": "ls -la"})
```

### After (v2.0)

```python
from mini_coder.tools import CommandTool

tool = CommandTool(
    security_mode="normal",
    event_callback=on_tool_event,  # New: event callback
    config=tool_config,             # New: config from tools.yaml
)
result = tool.run({"command": "ls -la"})

# Get system prompt
prompt = tool.get_system_prompt(context={"security_mode": "normal"})
```

## Data Flow

### Tool Execution Flow

```
Agent/LLM
    │
    ▼
┌─────────────────────────────────┐
│  1. tool.get_system_prompt()    │  ← Load from prompts/tools/command.md
│     - Interpolate context       │
│     - Return system prompt      │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│  2. tool.run(parameters)        │  ← Execute tool
│     - Validate parameters       │
│     - Security check            │
│     - Execute command           │
│     - Return result             │
└─────────────────────────────────┘
    │
    ├──────────────────┐
    │                  │
    ▼                  ▼
┌──────────┐    ┌──────────┐
│ Success  │    │  Error   │
└──────────┘    └──────────┘
    │                  │
    └──────────────────┘
           │
           ▼
┌─────────────────────────────────┐
│  3. notify_event()              │  ← Emit events
│     - "start"                   │
│     - "security_check"          │
│     - "complete" or "error"     │
└─────────────────────────────────┘
```

## Testing Strategy

### Unit Tests

```python
class TestBaseTool2:
    def test_prompt_loading(self):
        """Test dynamic prompt loading"""
        pass

    def test_event_callback(self):
        """Test event callback invocation"""
        pass

    def test_parameter_validation(self):
        """Test parameter validation"""
        pass


class TestCommandToolMigration:
    def test_backward_compatible(self):
        """Test backward compatibility with v1.0"""
        pass

    def test_security_check(self):
        """Test security check functionality"""
        pass

    def test_event_emission(self):
        """Test event emission during execution"""
        pass
```

### Integration Tests

```python
class TestToolTUIIntegration:
    def test_tui_displays_tool_status(self):
        """Test TUI displays tool execution status"""
        pass

    def test_permission_dialog(self):
        """Test permission request dialog"""
        pass
```

## Migration Path

### Phase 1: Framework Creation
1. Create BaseTool 2.0 in `base.py`
2. Create PromptLoader class
3. Create `prompts/tools/` directory

### Phase 2: CommandTool Migration
1. Update CommandTool to extend BaseTool 2.0
2. Create `prompts/tools/command.md`
3. Add event_callback support

### Phase 3: Configuration Update
1. Update `tools.yaml` with new settings
2. Load config from YAML in CommandTool

### Phase 4: Testing & Documentation
1. Write unit tests
2. Write integration tests
3. Update documentation

## Rollback Plan

If issues are discovered:

1. **Keep v1.0 interface** - Old code continues to work
2. **Disable event callbacks** - Set to None or empty function
3. **Use fallback prompts** - Built-in prompts when file missing
4. **Revert configuration** - Old tools.yaml format still supported
