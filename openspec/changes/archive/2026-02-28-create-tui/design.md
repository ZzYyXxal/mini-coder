## Context

mini-coder is a multi-agent coding assistant system with 5 subagents (Orchestrator, Architectural Consultant, Planner, Implementer, Tester). The project currently has no standalone terminal user interface, limiting users to interactive sessions within development environments.

**Current State:**
- No compiled binary distribution
- No TUI for standalone operation
- File system access capability exists but not exposed via TUI
- Subagent system defined via external skills (not internal Python code)

**Constraints:**
- Python 3.10+ required with strict type hints (PEP 484)
- TDD workflow with >=80% test coverage requirement
- PEP 8 compliance enforced
- Token optimization policy (targeted edits over full rewrites)
- Binary size target: <50MB for typical TUI application
- Must integrate with existing subagent system (external skills, not internal implementation)

**Stakeholders:**
- End users needing portable coding assistance
- Development team maintaining the mini-coder project
- Subagent system operators using the 5 external skill files

## Goals / Non-Goals

**Goals:**
- Create a standalone TUI application compiled to binary format
- Enable runtime working directory selection with both interactive and CLI modes
- Implement typewriter text animation with configurable speed and state management
- Display AI reasoning steps in real-time with structured formatting
- Maintain cross-platform compatibility (Linux, macOS, Windows)
- Ensure binary is self-contained without Python runtime dependency
- Integrate TUI development with the existing subagent system for planning and implementation

**Non-Goals:**
- File system access layer (terminal-tool-bridge) - deferred to future phase
- GUI-based interface (terminal-only focus)
- Remote execution capabilities
- Plugin system or extensibility
- Multi-user or collaborative features
- Advanced file system operations beyond basic directory selection

## Decisions

### Decision 1: TUI Framework Selection - Textual

**Choice:** Use [Textual](https://textual.textual.io/) as the TUI framework.

**Rationale:**
- Modern, actively maintained with comprehensive documentation
- Built-in support for animations and typewriter effects
- Asynchronous architecture enables non-blocking rendering
- Rich widget library for complex UIs (directory browser, collapsible panels)
- Excellent keyboard navigation and accessibility
- Strong community and ecosystem
- Python 3.10+ compatible with type hints support

**Alternatives Considered:**

| Alternative | Pros | Cons | Decision |
|-------------|------|------|----------|
| **Rich** | Simple, mature, good for terminal output | Not a full TUI framework, limited interactivity | Rejected - insufficient for interactive directory browser |
| **Urwid** | Established, cross-platform | Steep learning curve, less modern API, async support limited | Rejected - better alternatives available |
| **Curses** | Standard library, no dependencies | Low-level, complex animations, platform differences | Rejected - too low-level for requirements |
| **Custom ncurses wrapper** | Full control, minimal dependencies | High development cost, reinventing the wheel | Rejected - high maintenance burden |

### Decision 2: Binary Compilation Tool - PyInstaller

**Choice:** Use PyInstaller for binary compilation with UPX compression.

**Rationale:**
- Mature, widely-used tool with proven reliability
- Good documentation and community support
- Supports all target platforms (Linux, macOS, Windows)
- Single-file distribution possible via `--onefile` flag
- UPX compression integration for size optimization
- Easy integration with build pipelines

**Alternatives Considered:**

| Alternative | Pros | Cons | Decision |
|-------------|------|------|----------|
| **Nuitka** | Better performance, smaller binaries sometimes | Compilation is slower, less mature ecosystem | Rejected - PyInstaller sufficient for our needs |
| **Briefcase** | Cross-platform packaging, good distribution | Primarily for GUI apps, adds complexity | Rejected - overkill for TUI |
| **PyOxidizer** | Excellent security, fast startup | Complex configuration, steeper learning curve | Rejected - security requirements not critical |

### Decision 3: Configuration Management - YAML-based

**Choice:** Use YAML files for TUI configuration stored in user's home directory.

**Rationale:**
- Human-readable and editable by users
- Python standard library support via PyYAML
- Aligns with existing project YAML configuration patterns (subagents.yaml, workflow.yaml)
- Easy to version control and validate

**Configuration Structure:**
```yaml
# ~/.mini-coder/tui.yaml
animation:
  speed: normal  # slow, normal, fast
  custom_delay_ms: 10
  pause_on_space: true
thinking:
  display_mode: normal  # verbose, normal, concise
  history_max_entries: 100
  collapse_by_default: false
working_directory:
  remember_last: true
  default_path: "."
```

### Decision 4: Architecture Pattern - MVC with Async Components

**Choice:** Use Model-View-Controller pattern with async components for non-blocking rendering.

**Rationale:**
- Separates concerns cleanly (state, display, logic)
- Async rendering prevents UI blocking during long animations
- Maps well to Textual's widget-based architecture
- Testable components can be isolated

**Architecture Layers:**

```
┌─────────────────────────────────────────────────────┐
│                   Controller Layer                    │
│  (Entry Point, CLI Argument Parsing, State Machine)  │
└──────────────────────┬────────────────────────────────┘
                       │
         ┌─────────────┴─────────────┐
         │                           │
         ▼                           ▼
┌─────────────────┐         ┌─────────────────┐
│  Model Layer    │         │  View Layer      │
│  - State        │◄────────┤  - Textual UI    │
│  - Config       │         │  - Widgets       │
│  - History      │         │  - Animations    │
└─────────────────┘         └─────────────────┘
```

**Component Breakdown:**

| Component | File | Responsibility |
|-----------|------|----------------|
| Entry Point | `src/mini_coder/tui/__main__.py` | CLI parsing, TUI initialization |
| Controller | `src/mini_coder/tui/app.py` | State management, event handling |
| Models | `src/mini_coder/tui/models/` | State, config, history data structures |
| Views | `src/mini_coder/tui/widgets/` | Textual widgets (directory browser, thinking panel) |
| Rendering | `src/mini_coder/tui/rendering.py` | Typewriter animation logic |
| Thinking Display | `src/mini_coder/tui/thinking_display.py` | AI thinking visualization |

### Decision 5: Typewriter Animation Implementation - Async Generator-based

**Choice:** Implement typewriter animation using async generators with configurable delay.

**Rationale:**
- Non-blocking by design (async/await)
- Fine-grained control over timing
- Cancellable via async generators
- Clean separation of animation logic from rendering

**Implementation Pattern:**
```python
async def typewriter_render(text: str, delay: float) -> AsyncIterator[str]:
    """Yield text character by character with delay."""
    for char in text:
        yield char
        await asyncio.sleep(delay)
```

**Animation State Machine:**
```
IDLE → RUNNING → (PAUSED) → RUNNING
        ↓
    CANCELED → COMPLETED
```

### Decision 6: Working Directory Selection - Hybrid Interactive/CLI Mode

**Choice:** Support both interactive directory browser and CLI argument specification.

**Rationale:**
- Interactive mode for casual users (discoverability)
- CLI mode for automation and power users (efficiency)
- Graceful fallback (try CLI first, prompt if missing)

**Implementation:**
```python
async def select_working_directory(cli_path: str | None) -> Path:
    if cli_path:
        resolved = Path(cli_path).resolve()
        if resolved.exists() and resolved.is_dir():
            return resolved
        # Fall through to interactive on invalid CLI path
    # Launch interactive directory browser
    return await interactive_directory_selector()
```

### Decision 7: AI Thinking Display - Panel-based with Message Queue

**Choice:** Use Textual Panel widgets with async message queue for real-time updates.

**Rationale:**
- Panel widgets support scrolling and collapsing
- Async queue prevents blocking on AI output
- Structured formatting (prefixes, colors) via rich text

**Thinking Message Structure:**
```python
@dataclass
class ThinkingMessage:
    step: int
    timestamp: datetime
    message_type: ThinkingType  # PLAN, ANALYSIS, REFLECTION
    content: str
    metadata: dict[str, Any] | None = None
```

**Display Strategy:**
- Real-time streaming: Process messages as they arrive
- Type-based formatting: Different prefixes/colors for each type
- Collapsible sections: Group related thoughts under headers
- History navigation: Scrollable panel with search

### Decision 8: Build and Distribution - Multi-stage Build Pipeline

**Choice:** Implement build pipeline with separate stages for each platform and compression.

**Build Stages:**
1. **Clean**: Remove previous build artifacts
2. **Bundle**: Collect Python dependencies
3. **Compile**: Run PyInstaller with platform-specific flags
4. **Compress**: Apply UPX compression (if available)
5. **Package**: Create distribution archives (tar.gz, zip)
6. **Verify**: Test generated binary

**Build Script Structure:**
```bash
scripts/build-tui.sh
├── clean()
├── build_linux()
├── build_macos()
├── build_windows()
├── compress_binary()
└── verify_binary()
```

**Makefile Targets:**
```makefile
build: build-linux build-macos build-windows
build-linux: clean build-linux-only verify-linux
build-macos: clean build-macos-only verify-macos
build-windows: clean build-windows-only verify-windows
clean:
verify:
```

### Decision 9: Testing Strategy - Unit + Integration + E2E

**Choice:** Multi-layer testing approach with pytest and pytest-asyncio.

**Testing Pyramid:**

| Layer | Scope | Tools | Coverage Target |
|-------|-------|-------|-----------------|
| Unit | Individual functions, models | pytest, unittest.mock | 90%+ |
| Integration | Component interaction | pytest-asyncio, fixtures | 80%+ |
| E2E | Full workflow simulation | subprocess, temporary directories | Key paths only |

**Test Structure:**
```
tests/
├── unit/
│   ├── test_rendering.py       # Typewriter animation
│   ├── test_thinking_display.py # Thinking display logic
│   └── test_models.py           # State management
├── integration/
│   ├── test_directory_selector.py # Interactive selection
│   └── test_typewriter_state.py   # Animation state machine
└── e2e/
    └── test_tui_workflow.py      # End-to-end scenarios
```

### Decision 10: Subagent Integration - Skill-based Development Workflow

**Choice:** Use existing external subagent skills for TUI development coordination.

**Rationale:**
- Subagent system already defined and operational
- Skills provide specialized guidance (TDD, type hints, testing)
- Avoids duplicating logic in internal Python code
- Maintains separation between development tools and production code

**Development Workflow:**

1. **Orchestrator** (`/orchestrator`): Coordinate TUI development tasks
2. **Architectural Consultant** (`/architectural-consultant`): Guide TUI architecture decisions
3. **Planner** (`/planner`): Create implementation plans with TDD focus
4. **Implementer** (`/implementer`): Execute with type hints and PEP 8 compliance
5. **Tester** (`/tester`): Validate with >=80% coverage

**Subagent Usage Pattern:**
```bash
# Start TUI development cycle
/orchestrator "Develop TUI working directory selector component"

# Architectural guidance
/architectural-consultant "What TUI patterns for directory navigation?"

# Create TDD plan
/planner "Working directory selector with interactive browser"

# Implement with type hints
/implementer "Implement DirectoryBrowser widget with full type hints"

# Validate implementation
/tester "Run tests for directory selector component"
```

## Risks / Trade-offs

### Risk 1: Binary Size Exceeds 50MB Target

**Risk:** PyInstaller bundles may produce binaries >50MB, especially with Textual and dependencies.

**Mitigation:**
- Use UPX compression for 20-40% size reduction
- Exclude unnecessary modules via `--exclude-module` flags
- Consider `--onedir` mode for platform-specific distribution (smaller than `--onefile`)
- Optimize imports and remove unused dependencies
- Track size in CI/CD pipeline, fail if exceeds threshold

**Trade-off:** `--onedir` vs `--onefile`
- `--onefile`: Easier distribution, but larger (~15% overhead)
- `--onedir`: Smaller, but requires directory structure (tar.gz for distribution)
- **Decision:** Use `--onefile` for user convenience, monitor size closely

### Risk 2: Cross-platform Compatibility Issues

**Risk:** Terminal differences (colors, scrolling, key bindings) may cause inconsistent behavior.

**Mitigation:**
- Use Textual's platform abstraction layer
- Test on all three target platforms (Linux, macOS, Windows)
- Provide fallback rendering for unsupported features
- Document platform-specific limitations
- Use CI matrix for automated testing

**Trade-off:** Rich formatting vs. compatibility
- Rich formatting: Better user experience, but platform-dependent
- Plain text: Universal, but limited features
- **Decision:** Use rich formatting with graceful degradation

### Risk 3: Typewriter Animation Performance Impact

**Risk:** Character-by-character rendering may cause latency or UI lag, especially for long outputs.

**Mitigation:**
- Use async rendering to avoid blocking main thread
- Implement adaptive speed (faster for long text)
- Provide skip/interrupt mechanism
- Batch character rendering for performance (e.g., 5 chars per frame)
- Monitor performance metrics, optimize bottlenecks

**Trade-off:** Smooth animation vs. responsiveness
- Smooth animation: 1 char/frame, but higher CPU usage
- Batch rendering: Lower CPU, but less smooth
- **Decision:** Batch rendering (3-5 chars) with user-configurable speed

### Risk 4: AI Thinking Display Overwhelms UI

**Risk:** Large or frequent thinking output may clutter interface or impact performance.

**Mitigation:**
- Implement collapsible sections by default
- Limit history size (max 100 entries, configurable)
- Provide density control (verbose/normal/concise modes)
- Lazy rendering for long history (virtual scrolling)
- Rate limiting for very high-frequency updates

**Trade-off:** Complete visibility vs. usability
- Complete visibility: All thoughts shown, but UI crowded
- Summarized view: Cleaner UI, but less transparency
- **Decision:** Default to normal density, allow user to expand

### Risk 5: Subagent Coordination Complexity

**Risk:** Coordinating 5 external subagents for TUI development may introduce workflow overhead or conflicts.

**Mitigation:**
- Define clear phase boundaries (planning → architecture → implementation → testing)
- Use Orchestrator skill to manage transitions and detect deadlocks
- Document subagent interaction patterns
- Keep subagent prompts focused and scoped
- Validate outputs before proceeding to next phase

**Trade-off:** Full subagent usage vs. pragmatic development
- Full usage: Maximum benefit from subagent system, but higher coordination cost
- Hybrid approach: Use subagents selectively for complex tasks
- **Decision:** Full usage for core components, pragmatic for simple utilities

### Risk 6: File System Access Deferred May Limit TUI Utility

**Risk:** Deferring terminal-tool-bridge (file system access) means TUI initially cannot browse or edit files.

**Mitigation:**
- Document this limitation clearly in initial release
- Prioritize working directory selection as partial workaround
- Plan terminal-tool-bridge as Phase 2 with clear timeline
- Gather user feedback on file access priorities

**Trade-off:** Early release vs. complete feature set
- Early release: Get feedback sooner, but limited functionality
- Delayed release: More features, but slower time-to-market
- **Decision:** Release MVP with working directory selection, add file access in Phase 2

### Risk 7: Build Pipeline Complexity for Cross-platform Binaries

**Risk:** Building for multiple platforms requires CI infrastructure and may be error-prone.

**Mitigation:**
- Start with single platform (Linux) for initial development
- Add platform-specific build scripts gradually
- Use GitHub Actions or GitLab CI with matrix builds
- Platform-specific testing in isolated environments
- Document build requirements and dependencies

**Trade-off:** Cross-platform support vs. development velocity
- Cross-platform: Wider reach, but more complex builds
- Platform-specific: Simpler, but limits user base
- **Decision:** Support all three platforms from start, use CI automation

## Migration Plan

### Phase 1: Core Infrastructure (Week 1-2)
1. Set up Textual TUI framework with basic app structure
2. Implement configuration management (YAML-based)
3. Create build infrastructure (PyInstaller, build scripts)
4. Set up testing framework (pytest-asyncio, fixtures)
5. **Subagent Usage:**
   - `/architectural-consultant` - Framework selection and architecture review
   - `/planner` - Phase 1 implementation plan (TDD-based)
   - `/implementer` - Implement core infrastructure
   - `/tester` - Validate >=80% coverage

### Phase 2: Working Directory Selection (Week 3)
1. Implement directory browser widget with navigation
2. Add CLI argument parsing for directory specification
3. Implement directory validation and error handling
4. Add persistence for last used directory
5. **Subagent Usage:**
   - `/planner` - Directory selector implementation plan
   - `/implementer` - Implement with type hints
   - `/tester` - Validate directory selection workflows

### Phase 3: Typewriter Renderer (Week 4)
1. Implement async typewriter animation engine
2. Add configurable animation speed (presets + custom)
3. Implement state management (pause/resume/cancel)
4. Add skip/interrupt handling
5. **Subagent Usage:**
   - `/planner` - Animation implementation plan
   - `/implementer` - Implement with async patterns
   - `/tester` - Test animation state machine

### Phase 4: AI Thinking Visualizer (Week 5-6)
1. Implement thinking message structure and queue
2. Create panel widget with collapsible sections
3. Add type-based formatting (plan/analysis/reflection)
4. Implement history navigation and search
5. Add export functionality (markdown, JSON)
6. **Subagent Usage:**
   - `/planner` - Thinking display implementation plan
   - `/implementer` - Implement with message queue
   - `/tester` - Validate thinking display and export

### Phase 5: Build and Distribution (Week 7)
1. Complete cross-platform build scripts
2. Implement UPX compression
3. Create distribution archives
4. Add binary verification tests
5. Document installation and usage
6. **Subagent Usage:**
   - `/architectural-consultant` - Build pipeline review
   - `/tester` - Validate binary generation and testing

### Phase 6: Integration and Polish (Week 8)
1. Integrate all components end-to-end
2. Perform E2E testing
3. Optimize performance and binary size
4. Document user-facing features
5. Prepare initial release
6. **Subagent Usage:**
   - `/orchestrator` - Coordinate final integration phase
   - `/tester` - Complete test suite validation

### Rollback Strategy
1. **Git-based rollback:** Each phase in separate branch, merge to main when complete
2. **Build artifact rollback:** Keep previous binary versions available for download
3. **Configuration rollback:** Schema versioning in YAML config, automatic migration or rollback on version downgrade

## Open Questions

1. **Q1: Should we use `--onefile` or `--onedir` for PyInstaller builds?**
   - Current decision: `--onefile` for user convenience
   - Needs validation: Test actual binary sizes for both modes
   - Resolution required: Phase 5 (Build and Distribution)

2. **Q2: What is the optimal character batch size for typewriter animation?**
   - Current decision: 3-5 characters per frame
   - Needs user testing: Balance between smoothness and performance
   - Resolution required: Phase 4 (user testing and feedback)

3. **Q3: Should AI thinking history be persisted across sessions?**
   - Current design: History preserved in session only, cleared on exit
   - Alternative: Persist to disk with configurable retention
   - Resolution required: User feedback after initial release

4. **Q4: Should we add syntax highlighting to AI code output in thinking display?**
   - Current design: Plain text with type-based formatting only
   - Enhancement potential: Pygments integration for code blocks
   - Resolution required: Phase 4 (deferred if time constraints)

5. **Q5: What is the maximum supported thinking history size?**
   - Current design: 100 entries (configurable)
   - Trade-off: Larger history uses more memory, but provides more context
   - Resolution required: Performance testing in Phase 4

6. **Q6: Should the TUI support dark/light terminal themes or detect automatically?**
   - Current design: Use Textual default (auto-detect)
   - Enhancement potential: Explicit theme selection
   - Resolution required: User feedback after initial release
