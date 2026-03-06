# Implementation Tasks: Optimize Tools Framework

## Phase 1: Documentation & Planning ✅

| ID | Task | Status |
|----|------|--------|
| 1.1 | Write architecture design document (`docs/tools-architecture-design.md`) | ✅ Done |
| 1.2 | Create OpenSpec change request (`optimize-tools-framework`) | ✅ Done |
| 1.3 | Generate proposal.md | ✅ Done |
| 1.4 | Generate design.md | ✅ Done |
| 1.5 | Generate specs.md | ✅ Done |

---

## Phase 2: BaseTool 2.0 Framework

### Task 2.1: Create PromptLoader Class

| Field | Value |
|-------|-------|
| **ID** | 2.1 |
| **Priority** | High |
| **Estimated Effort** | 2 hours |
| **Status** | Pending |
| **Acceptance Criteria** | PromptLoader loads prompts from files, supports interpolation, caching, and fallback |

**Implementation:**
```python
# Create: src/mini_coder/tools/prompt_loader.py
class PromptLoader:
    """Dynamic prompt loader with template interpolation"""

    def __init__(self, base_dir: str = "prompts"):
        self.base_dir = Path(base_dir)
        self._cache: Dict[str, str] = {}

    def load(self, prompt_path: str, context: Dict = None, use_cache: bool = True) -> str:
        # Load from file or cache
        # Interpolate context
        # Return prompt string
        pass
```

**Tests:**
- [ ] Test load existing prompt file
- [ ] Test load non-existent file (fallback)
- [ ] Test context interpolation
- [ ] Test caching behavior

---

### Task 2.2: Create BaseTool 2.0 Class

| Field | Value |
|-------|-------|
| **ID** | 2.2 |
| **Priority** | High |
| **Estimated Effort** | 3 hours |
| **Status** | Pending |
| **Acceptance Criteria** | BaseTool 2.0 supports dynamic prompts, event callbacks, and configuration |

**Implementation:**
```python
# Update: src/mini_coder/tools/base.py
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
    ):
        self.name = name
        self.description = description
        self.config = config or {}
        self._event_callback = event_callback
        self._prompt_loader = PromptLoader()
        self._prompt_path = prompt_path

    def get_system_prompt(self, context: Dict = None) -> str:
        if self._prompt_path:
            return self._prompt_loader.load(self._prompt_path, context)
        return self._get_default_prompt()

    def notify_event(self, event_type: str, data: Dict = None) -> None:
        if self._event_callback:
            self._event_callback(
                tool_name=self.name,
                event_type=event_type,
                data=data or {},
            )
```

**Tests:**
- [ ] Test get_system_prompt loads from file
- [ ] Test get_system_prompt returns fallback
- [ ] Test notify_event invokes callback
- [ ] Test backward compatibility

---

## Phase 3: CommandTool Migration

### Task 3.1: Create Command Tool Prompt Template

| Field | Value |
|-------|-------|
| **ID** | 3.1 |
| **Priority** | High |
| **Estimated Effort** | 1 hour |
| **Status** | Pending |
| **Acceptance Criteria** | prompts/tools/command.md contains complete prompt with placeholders |

**Implementation:**
```markdown
# Create: prompts/tools/command.md

# Command Tool

You are the **Command** tool - a safe system command executor.

## Security Model

Current mode: `{{security_mode}}`

## Security Checks
1. **Blacklist Check**: Dangerous commands rejected
2. **Whitelist**: Safe commands execute without confirmation
3. **Requires Confirmation**: Other commands need approval

## Configuration
- Timeout: `{{timeout}}` seconds
- Max Output: `{{max_output_length}}` characters

## Events
- `start`, `security_check`, `permission_request`, `complete`, `error`
```

---

### Task 3.2: Migrate CommandTool to BaseTool 2.0

| Field | Value |
|-------|-------|
| **ID** | 3.2 |
| **Priority** | High |
| **Estimated Effort** | 3 hours |
| **Status** | Pending |
| **Acceptance Criteria** | CommandTool extends BaseTool 2.0, loads prompt, emits events |

**Implementation:**
```python
# Update: src/mini_coder/tools/command.py
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
```

**Tests:**
- [ ] Test backward compatibility (old constructor args)
- [ ] Test prompt loading
- [ ] Test event emission (start, complete, error)
- [ ] Test security functionality unchanged

---

## Phase 4: Configuration Update

### Task 4.1: Update tools.yaml

| Field | Value |
|-------|-------|
| **ID** | 4.1 |
| **Priority** | Medium |
| **Estimated Effort** | 1 hour |
| **Status** | Pending |
| **Acceptance Criteria** | tools.yaml contains command tool configuration with prompt_path and events |

**Implementation:**
```yaml
# Update: config/tools.yaml
command:
  prompt_path: "tools/command.md"
  security_mode: normal
  timeout:
    default: 120
    max: 600
  max_output_length: 30000
  events:
    enabled: true
    on_start: true
    on_complete: true
    on_error: true
```

---

## Phase 5: Integration & Testing

### Task 5.1: Integrate Event Callbacks with TUI

| Field | Value |
|-------|-------|
| **ID** | 5.1 |
| **Priority** | Medium |
| **Estimated Effort** | 2 hours |
| **Status** | Pending |
| **Acceptance Criteria** | TUI displays tool execution status in real-time |

**Implementation:**
```python
# Update: src/mini_coder/tui/console_app.py
def on_tool_called(self, tool_name: str, event_type: str, data: Dict) -> None:
    """Handle tool events for TUI display"""
    if event_type == "tool_start":
        self._console.print(f"[dim]Running: {tool_name}...[/dim]")
    elif event_type == "tool_complete":
        self._console.print(f"[green]✓ Completed: {tool_name}[/green]")
    elif event_type == "tool_error":
        self._console.print(f"[red]✗ Error: {tool_name}[/red]")
```

---

### Task 5.2: Write Unit Tests

| Field | Value |
|-------|-------|
| **ID** | 5.2 |
| **Priority** | High |
| **Estimated Effort** | 4 hours |
| **Status** | Pending |
| **Acceptance Criteria** | All tests pass, coverage > 80% |

**Test Files:**
- [ ] `tests/tools/test_base_v2.py` - BaseTool 2.0 tests
- [ ] `tests/tools/test_prompt_loader.py` - PromptLoader tests
- [ ] `tests/tools/test_command_v2.py` - CommandTool v2.0 tests

---

### Task 5.3: Write Integration Tests

| Field | Value |
|-------|-------|
| **ID** | 5.3 |
| **Priority** | Medium |
| **Estimated Effort** | 2 hours |
| **Status** | Pending |
| **Acceptance Criteria** | Integration tests verify end-to-end functionality |

**Test Scenarios:**
- [ ] Agent calls CommandTool with event callback
- [ ] TUI displays tool status during execution
- [ ] Configuration loaded from tools.yaml

---

## Phase 6: Documentation

### Task 6.1: Update README.md

| Field | Value |
|-------|-------|
| **ID** | 6.1 |
| **Priority** | Medium |
| **Estimated Effort** | 1 hour |
| **Status** | Pending |
| **Acceptance Criteria** | README.md documents new tools framework features |

---

### Task 6.2: Create Migration Guide

| Field | Value |
|-------|-------|
| **ID** | 6.2 |
| **Priority** | Low |
| **Estimated Effort** | 1 hour |
| **Status** | Pending |
| **Acceptance Criteria** | Migration guide helps users upgrade from v1.0 to v2.0 |

**Content:**
- Differences between v1.0 and v2.0
- Step-by-step migration instructions
- Troubleshooting common issues

---

## Summary

| Phase | Tasks | Completed | Pending |
|-------|-------|-----------|---------|
| Phase 1: Documentation | 5 | 5 ✅ | 0 |
| Phase 2: BaseTool 2.0 | 2 | 0 | 2 |
| Phase 3: CommandTool | 2 | 0 | 2 |
| Phase 4: Configuration | 1 | 0 | 1 |
| Phase 5: Testing | 3 | 0 | 3 |
| Phase 6: Documentation | 2 | 0 | 2 |
| **Total** | **15** | **5** | **10** |
