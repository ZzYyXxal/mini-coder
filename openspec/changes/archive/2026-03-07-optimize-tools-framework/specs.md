# Specification: Tools Framework Optimization

## Functional Requirements

### FR-1: BaseTool 2.0 Framework

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-1.1 | BaseTool 2.0 must support dynamic prompt loading from files | High | Pending |
| FR-1.2 | BaseTool 2.0 must support event callback for TUI integration | High | Pending |
| FR-1.3 | BaseTool 2.0 must support configuration via config dict | Medium | Pending |
| FR-1.4 | BaseTool 2.0 must maintain backward compatibility with existing Tool interface | High | Pending |

### FR-2: PromptLoader

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-2.1 | PromptLoader must load prompts from markdown files | High | Pending |
| FR-2.2 | PromptLoader must support placeholder interpolation ({{key}} syntax) | High | Pending |
| FR-2.3 | PromptLoader must implement caching for performance | Medium | Pending |
| FR-2.4 | PromptLoader must provide fallback prompts when file is missing | Medium | Pending |

### FR-3: CommandTool Migration

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-3.1 | CommandTool must extend BaseTool 2.0 | High | Pending |
| FR-3.2 | CommandTool must load prompt from prompts/tools/command.md | High | Pending |
| FR-3.3 | CommandTool must emit events (start, security_check, complete, error) | High | Pending |
| FR-3.4 | CommandTool must support configuration from tools.yaml | Medium | Pending |

### FR-4: Configuration

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-4.1 | tools.yaml must support prompt_path configuration | Medium | Pending |
| FR-4.2 | tools.yaml must support event callback configuration | Medium | Pending |
| FR-4.3 | tools.yaml must support environment variable interpolation (${VAR}) | Low | Pending |

## Non-Functional Requirements

### NFR-1: Performance

| ID | Requirement | Target | Status |
|----|-------------|--------|--------|
| NFR-1.1 | Prompt loading latency | < 10ms (cached) | Pending |
| NFR-1.2 | Event callback overhead | < 1ms per event | Pending |
| NFR-1.3 | Memory footprint | < 1MB additional | Pending |

### NFR-2: Reliability

| ID | Requirement | Target | Status |
|----|-------------|--------|--------|
| NFR-2.1 | Fallback prompt availability | 100% | Pending |
| NFR-2.2 | Event callback error handling | Graceful degradation | Pending |

### NFR-3: Maintainability

| ID | Requirement | Target | Status |
|----|-------------|--------|--------|
| NFR-3.1 | Code documentation coverage | > 80% | Pending |
| NFR-3.2 | Unit test coverage | > 80% | Pending |

## Technical Specifications

### 1. BaseTool 2.0 Interface

```python
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional


class ToolParameter:
    """Tool parameter definition"""
    name: str
    type: str  # string, integer, number, boolean, array, object
    description: str
    required: bool
    default: Any


class ToolResponse:
    """Tool execution response"""
    text: str
    data: Optional[Dict[str, Any]]
    error_code: Optional[str]


class BaseTool(ABC):
    """Base class for all tools with dynamic prompt support"""

    TOOL_TYPE: str = "base"
    DEFAULT_PROMPT_PATH: Optional[str] = None

    def __init__(
        self,
        name: str,
        description: str,
        prompt_path: Optional[str] = None,
        event_callback: Optional[Callable] = None,
        config: Optional[Dict[str, Any]] = None,
    ): ...

    @abstractmethod
    def run(self, parameters: Dict[str, Any]) -> ToolResponse: ...

    @abstractmethod
    def get_parameters(self) -> List[ToolParameter]: ...

    def get_system_prompt(self, context: Dict[str, Any] = None) -> str: ...

    def notify_event(self, event_type: str, data: Dict[str, Any] = None) -> None: ...
```

### 2. PromptLoader Interface

```python
class PromptLoader:
    """Dynamic prompt loader with template interpolation"""

    def __init__(self, base_dir: str = "prompts"): ...

    def load(
        self,
        prompt_path: str,
        context: Dict[str, Any] = None,
        use_cache: bool = True,
    ) -> str: ...
```

### 3. CommandTool Interface

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
    ): ...

    def run(self, parameters: Dict[str, Any]) -> ToolResponse: ...

    def get_parameters(self) -> List[ToolParameter]: ...
```

## File Specifications

### prompts/tools/command.md

```markdown
# Command Tool

You are the **Command** tool - a safe system command executor.

## Security Model

Current mode: `{{security_mode}}`

## Security Checks

1. **Blacklist Check**: Dangerous commands are directly rejected
2. **Whitelist (Safe Commands)**: Execute without confirmation
3. **Requires Confirmation**: Other commands need user approval

## Configuration

- Timeout: `{{timeout}}` seconds
- Max Output: `{{max_output_length}}` characters
- Allowed Paths: `{{allowed_paths}}`

## Events

- `start`: Command execution started
- `security_check`: Security check result
- `permission_request`: User confirmation requested
- `complete`: Execution completed
- `error`: Execution failed
```

### config/tools.yaml

```yaml
# Tools Configuration

command:
  prompt_path: "tools/command.md"
  security_mode: normal
  timeout:
    default: 120
    max: 600
  max_output_length: 30000
  permission:
    cache_enabled: true
    cache_ttl: 3600
  events:
    enabled: true
    on_start: true
    on_progress: false
    on_complete: true
    on_error: true

tool_filter:
  default_for_subagent: readonly
  agent_filters:
    explore: readonly
    plan: planner
    code: full_access
    bash: bash_restricted
```

## Acceptance Criteria

### AC-1: BaseTool 2.0 Framework

- [ ] BaseTool 2.0 class is created and functional
- [ ] Dynamic prompt loading works correctly
- [ ] Event callback is invoked for all event types
- [ ] Backward compatibility is maintained

### AC-2: PromptLoader

- [ ] Prompts are loaded from markdown files
- [ ] Placeholder interpolation works correctly
- [ ] Caching reduces load time
- [ ] Fallback prompts are provided when file is missing

### AC-3: CommandTool Migration

- [ ] CommandTool extends BaseTool 2.0
- [ ] Prompt is loaded from prompts/tools/command.md
- [ ] Events are emitted during execution
- [ ] Configuration is loaded from tools.yaml

### AC-4: Testing

- [ ] Unit tests pass (>80% coverage)
- [ ] Integration tests pass
- [ ] No regression in existing functionality

## Change Log

| Date | Version | Author | Description |
|------|---------|--------|-------------|
| 2026-03-06 | 1.0 | - | Initial specification |
