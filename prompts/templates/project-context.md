# Project Context Template
# Template for injecting into Agent prompts

## Project Info

- **Project Name**: mini-coder
- **Description**: A custom multi-agent coding assistant project
- **Tech Stack**: Python 3.10+, pytest, mypy, pydantic, chromadb, langgraph

## Core Principles

1. **TDD (Test-Driven Development)**: Red → Green → Refactor cycle
2. **Strict Type Hints**: PEP 484, complete function signatures
3. **PEP 8 Compliance**: Code style enforcement
4. **Token Optimization**: Prefer targeted edits over full file rewrites
5. **Google-style Docstrings**: For all public functions and classes

## Architecture Overview

### Subagent System

| Agent | Responsibility | Tool Scope |
|-------|---------------|------------|
| Explorer | Read-only codebase search | Read, Grep, Glob |
| Planner | Requirements analysis and task planning | Read, Grep, WebSearch |
| Coder | Code generation and editing | Read, Write, Edit, Bash(restricted) |
| Reviewer | Code quality review | Read, Grep, Glob |
| Bash | Terminal execution and test validation | Read, Bash(restricted) |

### Workflow

```
Requirement → Explorer(explore) → Planner(plan) → Coder(implement) → Reviewer(review) → Bash(test/validate)
```

## Important File Paths

- Main entry: `src/mini_coder/agents/orchestrator.py`
- Agent definitions: `src/mini_coder/agents/base.py`
- Tool filters: `src/mini_coder/tools/filter.py`
- Prompt templates: `prompts/system/*.md`

## Test Commands

```bash
# Run all tests
pytest tests/ -v

# Type check
mypy src/ --strict

# Code style
flake8 src/

# Coverage check
pytest tests/ --cov=src --cov-fail-under=80
```