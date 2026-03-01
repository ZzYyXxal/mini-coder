# mini-coder

A custom multi-agent coding assistant with TUI support.

## Overview

mini-coder is a Python-based coding assistant that provides:
- Interactive AI coding assistance with thinking visualization
- Terminal User Interface (TUI) with typewriter effects
- Working directory selection for context-aware assistance
- Configurable animation and display settings

## Installation

### From Source

```bash
# Install dependencies
pip install -r requirements.txt

# Run TUI
python -m mini_coder.tui
```

### From Binary (Built)

The binary has been successfully built and is available in the `dist/` directory as `mini-coder-tui` (49 MB).

#### Quick Start

```bash
# Linux (current build)
./dist/mini-coder-tui

# To verify build
make verify

# To rebuild from source
make build
```

#### Binary Details

- **Platform**: Linux (ELF 64-bit)
- **Architecture**: x86_64
- **Size**: 49 MB
- **Dependencies**: Self-contained (includes Python runtime, textual, pyyaml)
- **Location**: `dist/mini-coder-tui`

## Configuration

The TUI uses a YAML configuration file stored in `~/.mini-coder/tui.yaml`.

### Configuration Options

```yaml
# Animation settings
animation:
  speed: normal  # slow, normal, fast
  custom_delay_ms: 10
  pause_on_space: true
  batch_size: 3

# Thinking display settings
thinking:
  display_mode: normal  # verbose, normal, concise
  history_max_entries: 100
  collapse_by_default: false

# Working directory settings
working_directory:
  remember_last: true
  default_path: "."
```

## CLI Arguments

```bash
python -m mini_coder.tui [OPTIONS]

Options:
  --directory, -d PATH    Working directory for session (default: prompt or use last used)
  --animation-speed, -a {slow,normal,fast}
                               Typewriter animation speed
  --animation-delay INT     Custom animation delay in milliseconds (overrides speed preset)
  --thinking-density {verbose,normal,concise}
                               Thinking display density (default: normal)
  --version, -v           Show version and exit
  --help, -h             Show help message and exit
```

## Keyboard Shortcuts

- `q` - Quit TUI
- `Esc` - Return to welcome screen from thinking view
- `Space` - Pause/resume typewriter animation (when implemented)

## Building from Source

To build the TUI binary from source:

```bash
# Build for current platform (Linux)
make build

# Build for specific platforms
make build-linux
make build-macos
make build-windows

# Verify build
make verify
```

## Features

- **Working Directory Selection**: Browse and select project directory
- **Typewriter Animation**: Configurable character-by-character text rendering
- **AI Thinking Visualization**: Real-time display of AI reasoning steps
- **Configurable Settings**: Animation speed, thinking density, and more
- **Cross-Platform**: Works on Linux, macOS, and Windows

## Development

### Running Tests

```bash
# Run all tests
make test

# Run tests with coverage
pytest tests/ --cov=src/mini_coder --cov-report=html

# Run type checking
make lint
```

### Code Quality

The project follows strict Python development standards:
- **PEP 8** compliant code style
- **Type Hints** (PEP 484) on all functions
- **Test Coverage** >= 80% required
- **Black** for code formatting
- **isort** for import sorting
- **mypy** for type checking

### TDD Workflow

This project follows Test-Driven Development:
1. Write tests first (Red)
2. Run tests and confirm they fail
3. Write minimal code to make tests pass (Green)
4. Refactor under test protection

## Build Script

A comprehensive build script is available at `scripts/build-tui.sh` with the following stages:

```bash
# Multi-stage pipeline
./scripts/build-tui.sh {clean|bundle|compile|compress|package|verify|all}

# Individual stages
./scripts/build-tui.sh clean       # Remove build artifacts
./scripts/build-tui.sh bundle      # Collect dependencies
./scripts/build-tui.sh compile     # Compile binary
./scripts/build-tui.sh compress    # Apply UPX compression
./scripts/build-tui.sh package    # Create distribution package
./scripts/build-tui.sh verify     # Test generated binary
```

## License

[Specify your license here]

## Contributing

Contributions are welcome! Please read the development guidelines above.

## Known Limitations

- File system access layer (terminal-tool-bridge) is deferred to future implementation
- Advanced widget features (collapsible sections, density controls) are simplified in initial version
- Full E2E workflow tests are deferred for follow-up

## Troubleshooting

### Binary not found
- Ensure that binary has executable permissions (`chmod +x` on Linux/macOS)
- Check that Python 3.10+ is installed if building from source

### Configuration not saving
- Check that `~/.mini-coder/` directory exists and is writable
- Verify YAML syntax in `tui.yaml` configuration file

### TUI display issues
- Some terminals may not support all color codes
- Ensure terminal is at least 80x24 characters for best experience

### Build errors
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check Python version: `python --version` (requires 3.10+)
