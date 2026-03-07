# mini-coder

A custom multi-agent coding assistant with TUI support.

## Overview

mini-coder is a Python-based multi-agent coding assistant that provides:
- **Multi-Agent System**: Orchestrator coordinates specialized agents (Explorer, Planner, Coder, Reviewer, Tester, Bash)
- **Interactive TUI**: Rich-based terminal interface with real-time agent/tool display
- **Debug Mode**: View LLM context, token usage, and tool calls
- **Working Directory Isolation**: Security-focused file access control
- **Configurable LLM Providers**: Support for Zhipu, Anthropic, OpenAI, DashScope and more
- **Memory System**: Context management with session persistence and note extraction

## Features

### Multi-Agent System

The orchestrator coordinates specialized agents for different tasks:

| Agent | Purpose | Tool Access |
|-------|---------|-------------|
| **Explorer** | Codebase search and exploration | Read-only |
| **Planner** | Requirements analysis and TDD planning | Read-only + Web |
| **Coder** | Code implementation following TDD | Full access (safe) |
| **Reviewer** | Code quality and architecture review | Read-only |
| **Tester** | Run tests, type check, lint, coverage | Bash (restricted) |
| **Bash** | Terminal execution and verification | Bash (whitelist) |

### TUI Features

- **Agent Display**: Current agent shown in prompt (e.g., `Planner ▶`, `Coder ▶`)
- **Tool Call Display**: Real-time display of tool usage
- **Debug Mode**: Toggle with `/debug` to show LLM context and thinking
- **Context Info**: View token usage with `/context` command
- **Agent History**: Review agent flow with `/agents` command
- **Tool Logs**: View recent tool calls with `/tools` command

### Debug Commands

| Command | Description |
|---------|-------------|
| `/debug` | Toggle debug mode (shows LLM context and response stats) |
| `/context` | Display current LLM context info (provider, tokens, messages) |
| `/agents` | Show agent execution history |
| `/tools` | Show recent tool call logs |
| `/memory` | Display memory/session status |
| `/sessions` | List saved sessions |
| `/save` | Save current session |
| `/restore` | Restore latest session |
| `/clear` | Clear chat history |
| `/help` | Show available commands |

### Security Features

- **Working Directory Isolation**: Agents can only access files within the configured work directory
- **Path Pattern Filtering**: Configurable allow/deny patterns for file access
- **Protected Patterns**: Default protection for `.env`, credentials, `.ssh`, system directories
- **Bash Command Restrictions**: Whitelist/blacklist for shell commands

## Installation

### From Source

```bash
# Install dependencies
pip install -r requirements.txt

# Install as package
pip install -e .

# Run TUI (console mode)
python -m mini_coder.tui

# Run TUI (textual mode)
python -m mini_coder.tui.app
```

### From Binary (Built)

The binary has been successfully built and is available in the `dist/` directory as `mini-coder-tui`.

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

### LLM Configuration

The LLM service uses YAML configuration stored in `config/llm.yaml`.

**Supported Providers:**
- **Zhipu (GLM)**: `glm-5`, `glm-4` (default)
- **Anthropic Claude**: `claude-3-5-sonnet-20241022`
- **OpenAI GPT**: `gpt-4o-mini`
- **阿里云百炼 (DashScope)**: `qwen-turbo`, `qwen-plus`, `qwen-max`

**Example Configuration:**
```yaml
# LLM Service Configuration
default_provider: "dashscope"

providers:
  zhipu:
    api_key: "ZHIPU_API_KEY"  # Via environment variable
    base_url: "https://open.bigmodel.cn/api/paas/v4/"
    model: "glm-5"

  dashscope:
    api_key: "DASHSCOPE_API_KEY"  # Via environment variable
    base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model: "qwen-plus"
```

### Working Directory Configuration

Security-focused work directory isolation is configured in `config/workdir.yaml`:

```yaml
working_directory:
  default_path: "target/"    # Default work directory
  remember_last: true        # Remember last used directory
  always_ask: false          # Whether to always ask on startup

# Access control patterns (relative to work directory)
access_control:
  allowed_patterns:
    - "**/*"

  denied_patterns:
    - "../**"           # Parent directory
    - "**/.env"         # Environment files
    - "**/credentials*" # Credential files
    - "**/*.key"        # Key files
    - "**/.ssh/**"      # SSH directory
    - "/etc/**"         # System directories
```

### TUI Configuration

The TUI uses a YAML configuration file stored in `~/.mini-coder/tui.yaml`.

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

### TUI (Console Mode)

```bash
python -m mini_coder.tui [OPTIONS]

Options:
  --directory, -d PATH          Working directory for session
  --animation-speed, -a SPEED   Typewriter animation speed (slow/normal/fast)
  --animation-delay INT         Custom animation delay in milliseconds
  --thinking-density MODE       Thinking display density (verbose/normal/concise)
  --version, -v                 Show version and exit
  --help, -h                    Show help message and exit
```

### Special Commands (Runtime)

While running the TUI, use these slash commands:

```bash
/debug              Toggle debug mode (show LLM context and thinking)
/context            Show current LLM context info (tokens, messages)
/agents             Show agent execution history
/tools              Show recent tool call logs
/memory             Display memory status
/sessions           List saved sessions
/save               Save current session
/restore            Restore latest session
/clear              Clear chat history
/help               Show available commands
```

## Keyboard Shortcuts

- `q` - Quit TUI
- `Esc` - Return to welcome screen from thinking view
- `Space` - Pause/resume typewriter animation (when implemented)
- `Ctrl+C` - Interrupt current operation
- `Ctrl+D` - Exit application

## Agent Workflow

The orchestrator follows a structured workflow:

```
1. Explorer (Optional) → Explore codebase structure
2. Planner            → Analyze requirements, create TDD plan
3. Coder              → Write tests first (Red), implement (Green), refactor
4. Reviewer           → Architecture alignment + code quality review
5. Tester/Bash        → Run pytest, mypy, flake8, generate reports
```

**Loop Detection & Recovery:**
- If tests fail due to implementation details → Retry implementation
- If tests fail due to architecture issues → Re-plan
- Maximum retry count with user intervention option

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

### Build Script

A comprehensive build script is available at `scripts/build-tui.sh`:

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

## Project Structure

```
mini-coder/
├── src/mini_coder/
│   ├── agents/          # Multi-agent system
│   │   ├── enhanced.py      # Enhanced agent base classes
│   │   ├── orchestrator.py  # Workflow orchestrator
│   │   ├── base.py          # Base agent classes
│   │   └── prompt_loader.py # Dynamic prompt loading
│   ├── llm/             # LLM service layer
│   │   ├── service.py       # LLM service with context management
│   │   └── providers/       # Provider implementations
│   ├── memory/          # Context memory system
│   │   ├── manager.py       # Context manager
│   │   ├── context_builder.py
│   │   └── note_extractor.py
│   ├── tools/           # Tool implementations
│   │   ├── filter.py        # Tool access control
│   │   ├── command.py       # Command execution
│   │   └── security.py      # Security utilities
│   └── tui/             # Terminal UI
│       ├── console_app.py   # Rich-based console TUI
│       ├── app.py           # Textual-based TUI
│       └── models/          # TUI models
├── config/            # Configuration files
│   ├── llm.yaml           # LLM provider config
│   ├── workdir.yaml       # Working directory isolation
│   └── workflow.yaml      # Workflow settings
├── prompts/           # System prompts
└── tests/             # Test suites
```

## Development

### Running Tests

```bash
# Run all tests
make test

# Run tests with coverage
pytest tests/ --cov=src/mini_coder --cov-report=html

# Run specific test modules
pytest tests/agents/test_orchestrator.py
pytest tests/tui/test_console_app.py
pytest tests/tools/test_filter.py

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
- **flake8** for linting

### TDD Workflow

This project follows Test-Driven Development:
1. Write tests first (Red)
2. Run tests and confirm they fail
3. Write minimal code to make tests pass (Green)
4. Refactor under test protection

### Multi-Agent Architecture

The system uses a hybrid approach:

**Code Framework + Dynamic Prompt Injection:**
- Prompts stored in `prompts/system/*.md`
- `PromptLoader` loads prompts with placeholder interpolation (`{{identifier}}` syntax)
- Fallback to built-in prompts when files are missing

**Tool Security:**
- `ToolFilter` controls agent tool access
- `WorkDirFilter` enforces working directory isolation
- `BashRestrictedFilter` provides command whitelist/blacklist

## Memory System

The memory system provides context management across sessions:

**Features:**
- **Session Persistence**: Save and restore conversation sessions
- **Context Building**: Efficient token management with priority-based pruning
- **Note Extraction**: Automatic extraction of project notes from conversations
- **Token Counting**: Real-time token estimation for context windows

**API:**
```python
from mini_coder.memory import ContextManager, ContextBuilder

# Create context manager
manager = ContextManager(project_path="/path/to/project")

# Build context with user message
context = builder.build_with_user_message("implement feature X")
```

## License

[Specify your license here]

## Contributing

Contributions are welcome! Please read the development guidelines above.

## Known Limitations

- File system access layer (terminal-tool-bridge) is deferred to future implementation
- Advanced widget features (collapsible sections, density controls) are simplified in initial version
- Full E2E workflow tests are deferred for follow-up
- Some agents (Explorer, Reviewer, Bash, GeneralPurpose) do not yet support event callbacks for TUI display

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
- Try `--thinking-density concise` for simpler output

### Build errors
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check Python version: `python --version` (requires 3.10+)

### LLM Connection Issues
- Verify API keys are set in environment variables
- Check `config/llm.yaml` for correct base URLs
- For DashScope, ensure using `compatible-mode/v1` endpoint

### Working Directory Isolation
- If agents cannot access files, check `config/workdir.yaml` patterns
- Ensure files are within the configured work directory
- Check for denied pattern matches (e.g., `**/.env`)

### Debug Mode
- Use `/debug` command to toggle verbose output
- Use `/context` to view token usage and message count
- Check logs at `~/.mini-coder/logs/` or `logs/` (文件名格式: `tui_YYYYMMDD_HHMMSS.log`，带创建时间戳)
