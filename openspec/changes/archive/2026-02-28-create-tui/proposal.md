## Why

mini-coder currently lacks a standalone terminal user interface (TUI) for interactive coding assistance. Users need a portable, self-contained binary that can be run from any directory with typewriter-style output effects and real-time visualization of AI reasoning processes to enhance the development experience.

## What Changes

- **NEW**: Standalone TUI application compiled from Python source to binary format
- **NEW**: Runtime working directory selection mechanism
- **NEW**: Typewriter text rendering effect for command output
- **NEW**: Real-time AI thinking/reasoning process visualization
- **NEW**: Binary packaging and distribution infrastructure
- **NOTE**: File system access layer (terminal-tool-bridge) deferred to future implementation phase

## Capabilities

### New Capabilities
- `tui-binary`: Standalone TUI application packaged as compiled binary
- `working-directory-selector`: Runtime selection of working directory for context
- `typewriter-renderer`: Text output with typewriter animation effects
- `ai-thinking-visualizer`: Real-time display of AI reasoning steps and thought process

### Modified Capabilities
- (None - this is a completely new standalone component)

## Impact

**Code Affected**:
- New `src/mini_coder/tui/` directory for TUI application
- New `src/mini_coder/tui/rendering.py` for typewriter effects
- New `src/mini_coder/tui/thinking_display.py` for AI visualization

**Dependencies Added**:
- Binary packaging tools (PyInstaller or Nuitka)
- Terminal UI library (rich, textual, or similar)

**API Changes**:
- New CLI entry point for TUI binary
- No breaking changes to existing mini-coder architecture

**Systems Affected**:
- Build/packaging pipeline for binary generation
- Distribution mechanism for pre-compiled binaries

**Implementation Approach**:
All capabilities will be developed using the mini-coder subagent system:
- **Orchestrator**: Coordinate TUI development workflow across subagents
- **Architectural Consultant**: Provide guidance on TUI architecture and binary compilation strategies
- **Planner**: Create detailed implementation plans following TDD principles
- **Implementer**: Execute implementation with full type hints and PEP 8 compliance
- **Tester**: Validate TUI functionality and ensure >=80% test coverage
