## Why

The current development workflow lacks structured guidance for developing mini-coder itself. This change creates external Claude Code skills and documentation that will be used to develop mini-coder using a multi-agent approach. These skills are NOT part of mini-coder's source code, but are external tools invoked by developers using the Claude Code CLI.

## What Changes

- Create Claude Code skill definitions for 5 external subagents (orchestrator, architectural-consultant, planner, implementer, tester)
- Create file-based knowledge base with markdown documentation for architectural best practices
- Establish TDD-first development workflow documentation that developers must follow
- Define configuration schemas and prompt templates for each agent type
- Document dead-loop detection guidance and architectural advisory workflows
- Remove existing incorrect Python code that implements subagents as internal mini-coder modules

## Capabilities

### New Capabilities
- agent-orchestration: Claude Code skill for coordinating workflow and task lifecycle
- knowledge-rag: Markdown-based knowledge base for architectural best practices retrieval
- tdd-planning: External skill for task decomposition with test-first requirement generation
- python-implementation: External skill that produces type-hinted, documented Python code
- quality-gating: External skill for pytest, mypy, and coverage validation

### Modified Capabilities
- No existing mini-coder capabilities require changes

## Impact

- Project structure: Add `.claude/skills/` directory with skill definitions and `config/` for configuration
- Knowledge base: Create `docs/knowledge-base/` with markdown documentation (no vector database)
- Development workflow: Developers invoke skills via Claude Code CLI (`/skill:name`) to develop mini-coder
- Code quality: Skill prompt templates enforce type hints, docstrings, and test coverage requirements
- Testing: Developers follow skill instructions for test execution and quality validation
- Removed files: Delete `src/mini_coder/agents/`, `src/mini_coder/orchestrator/`, `src/mini_coder/knowledge/` directories (incorrect internal implementations)
