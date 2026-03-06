# Tools Framework Architecture Design

> **Version**: 1.0
> **Created**: 2026-03-06
> **Status**: Design Complete
> **Design Goal**: Implement "Code Framework + Dynamic Prompt Injection" pattern for tools, reference Agent architecture

---

## 1. Architecture Overview

### 1.1 Design Decision: Memory is NOT a Tool

After careful analysis, we decided that **Memory should remain as independent infrastructure, not be implemented as a Tool**. The reasons are:

| Reason | Explanation |
|--------|-------------|
| **1. Infrastructure vs. Capability** | Memory is context management infrastructure, not an LLM-callable capability. Tools are for LLM to invoke; Memory is for session state management. |
| **2. Access Pattern Difference** | Tools follow "request-response" pattern (LLM initiates); Memory requires automatic triggering (compression at 92% threshold, transparent read/write). |
| **3. Security Boundary** | Tools have security filters (ReadOnly/FullAccess); Memory access control should be handled by session management layer, not ToolFilter. |
| **4. Implementation Complexity** | Implementing Memory as Tool requires internal calls (Main Agent → Memory Tool), increasing complexity. Direct method calls are more efficient. |

### 1.2 Memory vs. Command Tool Comparison

| Aspect | Memory (Infrastructure) | Command Tool |
|--------|------------------------|--------------|
| **Trigger Mechanism** | Auto-triggered (threshold-based) | LLM invoked |
| **Access Pattern** | Read/Write via method calls | Request-Response via tool call |
| **Security Model** | Session-based access control | Command whitelist/blacklist |
| **Implementation** | ContextMemoryManager class | CommandTool class |
| **State Management** | Persistent session state | Stateless execution |
| **Filter Support** | Not applicable | ToolFilter (ReadOnly/FullAccess) |

---

## 2. BaseTool 2.0 Framework Design

### 2.1 Design Goals

1. **Dynamic Prompt Loading**: Support loading tool-specific prompts from files (`prompts/tools/*.md`)
2. **Event Callback Support**: Enable TUI to display tool execution progress
3. **Configuration Driven**: Tool behavior configurable via `tools.yaml`
4. **Backward Compatible**: Preserve existing Tool interface

### 2.2 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BaseTool 2.0 Framework                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        BaseTool (Abstract)                           │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │  - name: str                                                         │   │
│  │  - description: str                                                  │   │
│  │  - prompt_loader: PromptLoader                                       │   │
│  │  - event_callback: Optional[Callable]                                │   │
│  │                                                                      │   │
│  │  + run(parameters) -> ToolResponse          [Abstract]              │   │
│  │  + get_parameters() -> list[ToolParameter]  [Abstract]              │   │
│  │  + get_system_prompt() -> str                                        │   │
│  │  + notify_event(event_type, data)                                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                     │
│                    ┌─────────────────┼─────────────────┐                  │
│                    │                 │                 │                  │
│                    ▼                 ▼                 ▼                  │
│          ┌────────────────┐ ┌────────────────┐ ┌────────────────┐        │
│          │   CommandTool  │ │   FutureTool1  │ │   FutureTool2  │        │
│          │   (Migrated)   │ │   (New)        │ │   (New)        │        │
│          └────────────────┘ └────────────────┘ └────────────────┘        │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      Supporting Components                           │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │  - PromptLoader: Load prompts from prompts/tools/*.md               │   │
│  │  - ToolFilter: Control tool access (ReadOnly/FullAccess/Custom)     │   │
│  │  - EventCallback: TUI display integration                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 BaseTool 2.0 Interface

```python
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional
from pathlib import Path


class BaseTool(ABC):
    """Base class for all tools with dynamic prompt support"""

    def __init__(
        self,
        name: str,
        description: str,
        prompt_path: Optional[str] = None,
        event_callback: Optional[Callable] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize BaseTool

        Args:
            name: Tool name
            description: Tool description
            prompt_path: Path to prompt template (relative to prompts/tools/)
            event_callback: Callback for tool events (for TUI display)
            config: Tool configuration from tools.yaml
        """
        self.name = name
        self.description = description
        self.config = config or {}
        self._event_callback = event_callback

        # Initialize prompt loader
        self._prompt_loader = PromptLoader()
        self._prompt_path = prompt_path

    @abstractmethod
    def run(self, parameters: Dict[str, Any]) -> "ToolResponse":
        """Execute the tool

        Args:
            parameters: Tool parameters

        Returns:
            ToolResponse: Tool execution result
        """
        pass

    @abstractmethod
    def get_parameters(self) -> List["ToolParameter"]:
        """Get tool parameter definitions

        Returns:
            List of parameter definitions
        """
        pass

    def get_system_prompt(self, context: Dict[str, Any] = None) -> str:
        """Get tool-specific system prompt

        Args:
            context: Context for prompt interpolation

        Returns:
            System prompt string
        """
        if self._prompt_path:
            return self._prompt_loader.load(self._prompt_path, context)
        return self._get_default_prompt()

    def _get_default_prompt(self) -> str:
        """Get default system prompt (override in subclass)"""
        return f"You are the {self.name} tool. {self.description}"

    def notify_event(self, event_type: str, data: Dict[str, Any] = None) -> None:
        """Notify tool event to callback (for TUI display)

        Args:
            event_type: Event type (e.g., "start", "progress", "complete", "error")
            data: Event data
        """
        if self._event_callback:
            self._event_callback(
                tool_name=self.name,
                event_type=event_type,
                data=data or {},
            )
```

---

## 3. CommandTool Migration to 2.0

### 3.1 Current Architecture (1.0)

```
CommandTool (v1.0)
├─ SecurityLayer (SecurityLevel)
│  ├─ BANNED_COMMANDS
│  ├─ SAFE_READ_ONLY
│  └─ REQUIRES_CONFIRMATION
├─ PermissionService
└─ SafeExecutor
```

### 3.2 Migrated Architecture (2.0)

```
CommandTool (v2.0) extends BaseTool
├─ BaseTool
│  ├─ name: str = "Command"
│  ├─ description: str
│  ├─ prompt_loader: PromptLoader
│  └─ event_callback: Callable
├─ SecurityLayer (unchanged)
├─ PermissionService (unchanged)
└─ SafeExecutor (unchanged)
```

### 3.3 Migration Changes

| Aspect | v1.0 | v2.0 |
|--------|------|------|
| **Base Class** | `Tool` | `BaseTool` |
| **Prompt Source** | Hardcoded | `prompts/tools/command.md` |
| **Event Support** | None | `event_callback` parameter |
| **Configuration** | Constructor args | `config` dict from tools.yaml |
| **Security** | Unchanged | Unchanged |

---

## 4. Prompt System Design

### 4.1 Directory Structure

```
prompts/
├── system/                    # Agent system prompts (existing)
│   ├── main-agent.md
│   ├── subagent-coder.md
│   └── ...
├── tools/                     # Tool-specific prompts (new)
│   ├── command.md            # CommandTool prompt template
│   ├── memory.md             # Future Memory Tool (if needed)
│   └── ...                   # Future tools
└── templates/                 # Shared templates (existing)
    ├── coding-standards.md
    └── project-context.md
```

### 4.2 Command Tool Prompt Template

Location: `prompts/tools/command.md`

```markdown
# Command Tool

You are the **Command** tool - a safe system command executor.

## Security Model

You execute commands with the following security checks:

1. **Blacklist Check**: Dangerous commands are directly rejected
   - Examples: `rm -rf`, `curl`, `wget`, `sudo`, `chmod`, `dd`

2. **Whitelist (Safe Commands)**: These execute without confirmation
   - File viewing: `ls`, `pwd`, `cat`, `head`, `tail`, `wc`
   - Git read-only: `git status`, `git log`, `git diff`, `git branch`
   - Development: `python --version`, `pytest --collect-only`

3. **Requires Confirmation**: Other commands need user approval
   - File operations: `mkdir`, `cp`, `mv`, `rm`
   - Git write: `git add`, `git commit`, `git push`
   - Package managers: `pip install`, `npm install`

## Security Modes

- **strict**: Only whitelisted commands allowed
- **normal**: Blacklist + Whitelist + Confirmation (default)
- **trust**: Only blacklist check

Current mode: `{{security_mode}}`

## Output Handling

- Command output is truncated if exceeds {{max_output_length}} characters
- Execution timeout: {{timeout}} seconds (max: {{max_timeout}})
- Working directory restricted to: {{allowed_paths}}

## Usage

Execute commands by specifying:
- `command`: The shell command to run
- `timeout`: Optional timeout override (seconds)

## Event Callbacks

Tool execution triggers events:
- `start`: Command execution started
- `security_check`: Security check result
- `permission_request`: User confirmation requested (if needed)
- `complete`: Execution completed
- `error`: Execution failed
```

### 4.3 PromptLoader Implementation

```python
from pathlib import Path
from typing import Dict, Any, Optional


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
        """Load and interpolate prompt template

        Args:
            prompt_path: Path relative to base_dir (e.g., "tools/command.md")
            context: Context dictionary for interpolation
            use_cache: Whether to use cached prompt

        Returns:
            Interpolated prompt string
        """
        # Check cache
        if use_cache and prompt_path in self._cache:
            prompt = self._cache[prompt_path]
        else:
            # Load from file
            full_path = self.base_dir / prompt_path
            if not full_path.exists():
                prompt = self._get_fallback_prompt(prompt_path)
            else:
                prompt = full_path.read_text(encoding="utf-8")

            if use_cache:
                self._cache[prompt_path] = prompt

        # Interpolate context
        if context:
            for key, value in context.items():
                prompt = prompt.replace(f"{{{{{key}}}}}", str(value))

        return prompt

    def _get_fallback_prompt(self, prompt_path: str) -> str:
        """Get fallback prompt when file is missing"""
        return f"[Prompt file not found: {prompt_path}]"
```

---

## 5. Configuration Design

### 5.1 tools.yaml Structure

```yaml
# Tools Configuration
# 工具配置文件

# Command Tool Settings
command:
  # Prompt template path (relative to prompts/)
  prompt_path: "tools/command.md"

  # Security mode: strict, normal, trust
  security_mode: normal

  # Timeout settings (seconds)
  timeout:
    default: 120    # Default 2 minutes
    max: 600        # Max 10 minutes

  # Output limits
  max_output_length: 30000  # 30KB

  # Permission cache
  permission:
    cache_enabled: true
    cache_ttl: 3600  # 1 hour

  # Allowed working directories
  allowed_paths:
    - ${PROJECT_ROOT}
    - /tmp

  # Custom blacklist (appended to default)
  banned_commands:
    - my_dangerous_command

  # Custom whitelist (appended to default)
  safe_commands:
    - my_safe_command

  # Event callback configuration
  events:
    enabled: true
    on_start: true
    on_progress: false
    on_complete: true
    on_error: true

# Tool Filter Settings
tool_filter:
  # Default filter for subagents
  default_for_subagent: readonly

  # Filter configuration by agent type
  agent_filters:
    explore: readonly
    plan: planner     # ReadOnly + WebSearch
    code: full_access
    review: readonly
    bash: bash_restricted
```

### 5.2 Configuration Loading

```python
import os
from pathlib import Path
import yaml


class ToolConfigLoader:
    """Load tool configuration from tools.yaml"""

    def __init__(self, config_path: str = "config/tools.yaml"):
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Load configuration from YAML file"""
        if self.config_path.exists():
            content = self.config_path.read_text(encoding="utf-8")
            self._config = yaml.safe_load(content) or {}
            self._interpolate_env_vars()

    def _interpolate_env_vars(self) -> None:
        """Interpolate environment variables in config values"""
        self._config = self._interpolate_recursive(self._config)

    def _interpolate_recursive(self, obj: Any) -> Any:
        """Recursively interpolate ${VAR} patterns"""
        if isinstance(obj, str):
            if obj.startswith("${") and obj.endswith("}"):
                var_name = obj[2:-1]
                return os.environ.get(var_name, obj)
            return obj
        elif isinstance(obj, dict):
            return {k: self._interpolate_recursive(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._interpolate_recursive(v) for v in obj]
        return obj

    def get_tool_config(self, tool_name: str) -> Dict[str, Any]:
        """Get configuration for a specific tool"""
        return self._config.get(tool_name, {})

    def get_filter_config(self, agent_type: str) -> str:
        """Get filter type for an agent"""
        filters = self._config.get("tool_filter", {})
        agent_filters = filters.get("agent_filters", {})
        return agent_filters.get(
            agent_type,
            filters.get("default_for_subagent", "readonly"),
        )
```

---

## 6. ToolFilter Architecture

### 6.1 Filter Types

| Filter | Purpose | Allowed Tools | Use Case |
|--------|---------|---------------|----------|
| **ReadOnlyFilter** | Read-only access | Read, Glob, Grep, LS, Command (safe) | Explorer, Reviewer |
| **PlannerFilter** | ReadOnly + Web | ReadOnly + WebSearch, WebFetch | Planner |
| **FullAccessFilter** | Full access (minus dangerous) | All except dangerous commands | Coder |
| **BashRestrictedFilter** | Bash command filtering | Whitelist-based | Bash Agent |
| **WorkDirFilter** | Working directory access | Path-based filtering | All file tools |
| **CustomFilter** | User-defined | Configurable | Custom agents |

### 6.2 Filter Hierarchy

```
ToolFilter (Abstract Base)
├── ReadOnlyFilter
│   └── PlannerFilter (extends with WebSearch/WebFetch)
├── FullAccessFilter
├── BashRestrictedFilter
├── WorkDirFilter
└── CustomFilter
```

---

## 7. Event Callback System

### 7.1 Event Types

| Event Type | Trigger | Data |
|------------|---------|------|
| `tool_start` | Tool execution starts | `{tool_name, parameters}` |
| `tool_progress` | Progress update (optional) | `{tool_name, progress_percent, message}` |
| `security_check` | Security check performed | `{tool_name, command, category}` |
| `permission_request` | User confirmation requested | `{tool_name, command, reason}` |
| `tool_complete` | Tool execution completed | `{tool_name, result_summary, duration_ms}` |
| `tool_error` | Tool execution failed | `{tool_name, error_code, error_message}` |

### 7.2 Callback Integration with TUI

```python
class TuiToolEventHandler:
    """Handle tool events for TUI display"""

    def __init__(self, tui_app):
        self.tui_app = tui_app

    def handle_event(
        self,
        tool_name: str,
        event_type: str,
        data: Dict[str, Any],
    ) -> None:
        """Handle tool event and update TUI"""
        if event_type == "tool_start":
            self.tui_app.show_tool_status(tool_name, "Running...")
        elif event_type == "tool_complete":
            self.tui_app.show_tool_status(tool_name, "Completed")
        elif event_type == "tool_error":
            self.tui_app.show_tool_status(tool_name, f"Error: {data.get('error_message')}")
        elif event_type == "permission_request":
            self.tui_app.show_permission_dialog(
                tool_name=tool_name,
                command=data.get("command"),
                reason=data.get("reason"),
            )
```

---

## 8. Implementation Roadmap

### Phase 1: Documentation & Planning
- [x] Write architecture design document (`docs/tools-architecture-design.md`)
- [ ] Create OpenSpec change request (`change: optimize-tools-framework`)
- [ ] Generate proposal.md, design.md, specs.md, tasks.md

### Phase 2: BaseTool 2.0 Framework
- [ ] Create `src/mini_coder/tools/base_v2.py` with BaseTool 2.0
- [ ] Implement PromptLoader class
- [ ] Implement ToolConfigLoader class
- [ ] Create prompts directory structure (`prompts/tools/`)

### Phase 3: CommandTool Migration
- [ ] Migrate CommandTool to extend BaseTool 2.0
- [ ] Create `prompts/tools/command.md` prompt template
- [ ] Add event_callback support to CommandTool
- [ ] Update tools.yaml with CommandTool configuration

### Phase 4: Integration & Testing
- [ ] Integrate event callbacks with TUI
- [ ] Write unit tests for BaseTool 2.0
- [ ] Write integration tests for migrated CommandTool
- [ ] Update documentation

### Phase 5: Future Enhancements (Optional)
- [ ] Create additional tool prompt templates
- [ ] Implement more sophisticated prompt interpolation
- [ ] Add support for tool chaining
- [ ] Implement tool response caching

---

## 9. Trade-offs and Decisions

### 9.1 Why Dynamic Prompts for Tools?

| Benefit | Explanation |
|---------|-------------|
| **Consistency** | Same pattern as Agent prompts (`prompts/system/*.md`) |
| **Maintainability** | Prompts are editable without code changes |
| **Localization** | Easy to add multi-language support |
| **Customization** | Users can override prompts via configuration |

### 9.2 Why Not Implement Memory as Tool?

| Concern | Explanation |
|---------|-------------|
| **Access Pattern** | Memory is auto-triggered, not LLM-initiated |
| **Complexity** | Would require Main Agent → Memory Tool internal calls |
| **Performance** | Direct method calls more efficient than tool invocation |
| **Semantic Clarity** | Memory is infrastructure, not a capability |

### 9.3 Why Keep Existing Tool Interface?

| Reason | Explanation |
|--------|-------------|
| **Backward Compatibility** | Existing code uses current interface |
| **Simplicity** | run() and get_parameters() are sufficient |
| **Extensibility** | BaseTool 2.0 adds features via inheritance |

---

## 10. Reference Architecture

### 10.1 Inspired By

| Project | Concept | Adaptation |
|---------|---------|------------|
| **HelloAgents** | ToolFilter mechanism | Extended with WorkDirFilter |
| **OpenCode** | Multi-layer security | Adopted blacklist/whitelist/confirm |
| **Aider** | Direct command execution | Improved with timeout/output limits |

### 10.2 Related Documentation

- `docs/multi-agent-architecture-design.md` - Agent architecture
- `docs/command-execution-security-design.md` - Command security
- `docs/context-memory-design.md` - Memory system design
- `CLAUDE.md` - Project overview and workflow

---

## Appendix A: Complete BaseTool 2.0 Code Example

See the full implementation in the design document content above.

## Appendix B: Migration Checklist

### CommandTool v1.0 → v2.0 Migration

- [ ] **Code Changes**
  - [ ] Change base class from `Tool` to `BaseTool`
  - [ ] Add `prompt_path` parameter to `__init__`
  - [ ] Add `event_callback` parameter to `__init__`
  - [ ] Call `notify_event()` at key execution points

- [ ] **Prompt Template**
  - [ ] Create `prompts/tools/command.md`
  - [ ] Include security mode documentation
  - [ ] Include usage examples
  - [ ] Use `{{placeholders}}` for dynamic values

- [ ] **Configuration**
  - [ ] Update `tools.yaml` with new settings
  - [ ] Add prompt_path configuration
  - [ ] Add event callback configuration

- [ ] **Testing**
  - [ ] Update existing unit tests
  - [ ] Add tests for prompt loading
  - [ ] Add tests for event callbacks

- [ ] **Documentation**
  - [ ] Update tool documentation
  - [ ] Add migration guide
  - [ ] Update API reference