## 1. Project Setup and Dependencies

- [x] 1.1 Create `src/mini_coder/tui/` directory structure
- [x] 1.2 Add Textual dependency to requirements.txt (textual>=0.50.0)
- [x] 1.3 Add PyInstaller to requirements.txt (pyinstaller>=6.0.0)
- [x] 1.4 Add PyYAML to requirements.txt (pyyaml>=6.0.0)
- [x] 1.5 Add pytest-asyncio to requirements.txt (pytest-asyncio>=0.23.0)
- [x] 1.6 Create `src/mini_coder/tui/__init__.py` with package initialization
- [x] 1.7 Create `tests/tui/` directory structure for tests

## 2. Configuration Management

- [x] 2.1 Create configuration dataclass in `src/mini_coder/tui/models/config.py`
- [x] 2.2 Implement YAML config loading with default values
- [x] 2.3 Implement config validation with Pydantic (animation settings, thinking settings, working directory settings)
- [x] 2.4 Implement config persistence to ~/.mini-coder/tui.yaml
- [x] 2.5 Write unit tests for config loading, validation, and persistence
- [x] 2.6 Ensure >=80% test coverage for config module

## 3. Core TUI Application Structure

- [x] 3.1 Create entry point in `src/mini_coder/tui/__main__.py` with CLI argument parsing
- [x] 3.2 Implement CLI arguments: --directory, --animation-speed, --animation-delay, --version, --help
- [x] 3.3 Create main application class in `src/mini_coder/tui/app.py` inheriting from textual.App
- [x] 3.4 Implement basic TUI layout with header, main content area, and footer
- [x] 3.5 Implement application state management (idle, running, paused, completed)
- [x] 3.6 Add logging configuration (console and optional file logging)
- [x] 3.7 Write integration tests for application initialization
- [x] 3.8 Ensure >=80% test coverage for app module

## 4. Working Directory Selection

- [x] 4.1 Create directory browser widget in `src/mini_coder/tui/widgets/directory_browser.py`
- [x] 4.2 Implement directory listing with subdirectory display
- [x] 4.3 Implement navigation to parent and child directories
- [x] 4.4 Implement directory selection confirmation
- [x] 4.5 Implement directory validation (existence check, read permission check)
- [x] 4.6 Add CLI argument handling for --directory with path validation
- [x] 4.7 Implement working directory persistence in config (last used directory)
- [x] 4.8 Implement relative path resolution (., .., ./subdirectory)
- [x] 4.9 Create error messages for invalid directories
- [x] 4.10 Write unit tests for directory validation and path resolution
- [x] 4.11 Write integration tests for directory browser widget
- [x] 4.12 Ensure >=80% test coverage for directory selection

## 5. Typewriter Renderer

- [x] 5.1 Create typewriter renderer in `src/mini_coder/tui/rendering.py`
- [x] 5.2 Implement async generator for character-by-character rendering
- [x] 5.3 Implement animation state machine (idle, running, paused, canceled, completed)
- [x] 5.4 Implement configurable animation speed presets (slow, normal, fast)
- [x] 5.5 Implement custom animation delay support via config
- [x] 5.6 Implement pause/resume functionality (Space key toggle)
- [x] 5.7 Implement skip/interrupt functionality (Enter key)
- [x] 5.8 Implement cancellation for new output interruption
- [x] 5.9 Add selective rendering (error/warning messages render instantly)
- [x] 5.10 Implement batch character rendering (3-5 chars per frame) for performance
- [x] 5.11 Add visual cursor tracking during animation
- [x] 5.12 Write unit tests for animation state machine
- [x] 5.13 Write integration tests for typewriter rendering
- [x] 5.14 Ensure >=80% test coverage for typewriter renderer

## 6. AI Thinking Visualizer

- [x] 6.1 Create thinking message dataclass in `src/mini_coder/tui/models/thinking.py`
- [x] 6.2 Define ThinkingType enum (PLAN, ANALYSIS, REFLECTION)
- [x] 6.3 Implement thinking message structure with step, timestamp, type, content, metadata
- [x] 6.4 Create thinking display widget in `src/mini_coder/tui/widgets/thinking_panel.py`
- [x] 6.5 Implement async message queue for real-time thinking updates
- [x] 6.6 Implement type-based formatting (prefixes: [PLAN], [ANALYSIS], [REFLECTION])
- [x] 6.7 Implement type-based color coding (blue/green for plan, purple/magenta for analysis, yellow/orange for reflection)
- [x] 6.8 Implement collapsible thinking sections with toggle functionality
- [x] 6.9 Implement thinking history with scrollable panel
- [x] 6.10 Implement history navigation (scroll through previous cycles)
- [x] 6.11 Implement thinking history search with highlighting
- [x] 6.12 Implement density control modes (verbose, normal, concise)
- [x] 6.13 Implement visual state indicators (progress spinner, checkmark, warning icon)
- [x] 6.14 Implement export functionality to markdown format
- [x] 6.15 Implement export functionality to JSON format
- [x] 6.16 Implement synchronization with main response output
- [x] 6.17 Write unit tests for thinking message structure
- [x] 6.18 Write unit tests for message queue processing
- [x] 6.19 Write integration tests for thinking display widget
- [x] 6.20 Write E2E tests for full thinking workflow
- [x] 6.21 Ensure >=80% test coverage for thinking visualizer

## 7. Build Infrastructure

- [x] 7.1 Create PyInstaller spec file for Linux build (`tui_linux.spec`)
- [x] 7.2 Create PyInstaller spec file for macOS build (`tui_macos.spec`)
- [x] 7.3 Create PyInstaller spec file for Windows build (`tui_windows.spec`)
- [x] 7.4 Implement platform-specific build flags (upx compression, exclude modules)
- [x] 7.5 Create build script `scripts/build-tui.sh` with multi-stage pipeline
- [x] 7.6 Implement clean stage (remove previous artifacts)
- [x] 7.7 Implement bundle stage (collect dependencies)
- [x] 7.8 Implement compile stage (run PyInstaller)
- [x] 7.9 Implement compress stage (UPX compression if available)
- [x] 7.10 Implement package stage (create tar.gz for Linux/macOS, zip for Windows)
- [x] 7.11 Implement verify stage (test generated binary)
- [x] 7.12 Create Makefile with build targets (build-all, build-linux, build-macos, build-windows, clean, verify)
- [x] 7.13 Add binary size validation (<50MB target)
- [x] 7.14 Add version information embedding to binary
- [x] 7.15 Create cross-platform CI workflow (GitHub Actions or GitLab CI)
- [x] 7.16 Test build on Linux platform
- [x] 7.17 Test build on macOS platform (or verify CI configuration)
- [x] 7.18 Test build on Windows platform (or verify CI configuration)

## 8. Testing Infrastructure

- [x] 8.1 Create pytest fixtures for TUI testing (`tests/tui/conftest.py`)
- [x] 8.2 Create fixture for temporary test directories
- [x] 8.3 Create fixture for mock async event loop
- [x] 8.4 Create fixture for config with test values
- [x] 8.5 Create fixture for thinking message queue
- [x] 8.6 Set up pytest-asyncio configuration
- [x] 8.7 Configure mypy for strict type checking in TUI module
- [x] 8.8 Configure pytest-cov for coverage reporting
- [x] 8.9 Create E2E test framework for TUI workflow simulation
- [x] 8.10 Implement subprocess-based binary testing for generated executables

## 9. Integration and Assembly

- [x] 9.1 Integrate directory selector into main TUI workflow
- [x] 9.2 Integrate typewriter renderer with output widgets
- [x] 9.3 Integrate thinking display panel into main layout
- [x] 9.4 Implement message routing from AI to thinking display
- [x] 9.5 Implement coordination between typewriter and thinking display
- [x] 9.6 Add TUI help menu with keyboard shortcuts
- [x] 9.7 Add TUI about menu with version information
- [x] 9.8 Implement graceful error handling and user-friendly error messages
- [x] 9.9 Write E2E tests for complete TUI workflow (directory selection → AI thinking → output)
- [x] 9.10 Verify >=80% overall test coverage for TUI module
- [x] 9.11 Run mypy strict type checking on TUI module
- [x] 9.12 Run black formatting check on TUI module
- [x] 9.13 Run isort import sorting check on TUI module

## 10. Documentation

- [x] 10.1 Create README for TUI component in `docs/tui/README.md`
- [x] 10.2 Document installation instructions for source and binary
- [x] 10.3 Document CLI arguments and usage examples
- [x] 10.4 Document configuration options and YAML format
- [x] 10.5 Document keyboard shortcuts and TUI navigation
- [x] 10.6 Document build process for generating binaries
- [x] 10.7 Document subagent usage for TUI development
- [x] 10.8 Document known limitations (deferred terminal-tool-bridge)
- [x] 10.9 Document troubleshooting guide for common issues
- [x] 10.10 Add API documentation for public TUI components (Google-style docstrings)

## 11. Subagent Integration Validation

- [x] 11.1 Validate Orchestrator skill coordination for TUI development workflow
- [x] 11.2 Validate Architectural Consultant guidance matches implemented TUI architecture
- [x] 11.3 Verify Planner implementation plans align with completed tasks
- [x] 11.4 Verify Implementer outputs follow PEP 8 and type hints requirements
- [x] 11.5 Verify Tester validation confirms >=80% test coverage
- [x] 11.6 Document subagent workflow used during TUI development
- [x] 11.7 Create subagent integration test case (optional)

## 12. Release Preparation

- [x] 12.1 Create release notes for TUI component
- [x] 12.2 Tag release version in git
- [x] 12.3 Build final binaries for all platforms
- [x] 12.4 Test final binaries on each platform
- [x] 12.5 Create distribution package with binaries and documentation
- [x] 12.6 Update main project README with TUI section
- [x] 12.7 Archive create-tui change via openspec
