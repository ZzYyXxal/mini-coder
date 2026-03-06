# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**mini-coder** is a project to create a custom coding agent. The project uses a multi-agent system where Claude Code acts as the orchestrator, coordinating with specialized subagents for different aspects of the development workflow.

Important architecture design is documented in the `docs` directory; major architecture changes are also updated there.

## Development Environment Setup

### Running the Setup Script

The project uses a setup script `claude_code_env.sh` to configure the development environment:

```bash
bash claude_code_env.sh
```

This script will:
1. Install Node.js (v22) via nvm if not present
2. Install Claude Code CLI globally: `npm install -g @anthropic-ai/claude-code`
3. Configure Claude Code with ZHIPU AI credentials (prompted during setup)

### Configuration Files

After setup, Claude Code configuration is stored in:
- `~/.claude/settings.json` - Main settings including API credentials
- `~/.claude.json` - Onboarding status
- `~/.claude/cache/` - Cached data for improved performance

### API Configuration

The project uses ZHIPU AI API as the backend:
- **Base URL**: `https://open.bigmodel.cn/api/anthropic/v1`
- **API Timeout**: 3,000,000 ms
- **Model**: The project uses Claude's advanced models for code generation and analysis

---

## Core Coding Agent Workflow

### Overview

The mini-coder project utilizes a structured multi-agent system for code generation and management. The workflow is orchestrated by Claude Code and involves several specialized subagents, each with distinct responsibilities.

### Agent Roles

**5 Core Subagents** (with dynamic prompt loading):

| Agent | Purpose | Tool Filter |
|-------|---------|-------------|
| **Explorer** | Read-only codebase search | ReadOnlyFilter |
| **Planner** | Requirements analysis and TDD planning | PlannerFilter (ReadOnly + WebSearch) |
| **Coder** | Code implementation following TDD | FullAccessFilter |
| **Reviewer** | Code quality review (merged architecture alignment) | ReadOnlyFilter |
| **Bash** | Terminal execution and test validation | BashRestrictedFilter |

**Expert Agents** (optional):
- ArchitecturalConsultant: Removed (not needed)
- CodeReviewer: Merged into Reviewer

### Workflow Stages

```
1. Explorer (Optional)
   └─ Explore codebase structure, find relevant files

2. Planner
   ├─ Analyze requirements
   └─ Create TDD implementation plan

3. Coder
   ├─ Write tests first (Red)
   ├─ Implement to pass tests (Green)
   └─ Refactor if needed

4. Reviewer
   ├─ Architecture alignment check
   └─ Code quality review (type hints, docstrings, PEP 8)
   └─ Pass → Bash; Reject → back to Coder

5. Bash
   ├─ Run pytest tests
   ├─ Run mypy type check
   ├─ Run flake8 lint
   └─ Generate quality report
```

---

## Multi-Agent System Architecture

### Dynamic Prompt Loading

The system uses "Code Framework + Dynamic Prompt Injection" hybrid mode:

- **Prompt Storage**: `prompts/system/*.md` (separate from `knowledge-base/` which stores external references)
- **PromptLoader**: Loads prompts from files with placeholder interpolation (`{{identifier}}` syntax)
- **Fallback**: Built-in default prompts when files are missing

### Subagent Dispatch

The `WorkflowOrchestrator` provides:
- `_analyze_intent()`: Keyword-based intent analysis (Chinese and English)
- `_create_subagent()`: Factory method for agent instantiation
- `dispatch()`: Direct subagent invocation

### Tool Security

- **ToolFilter**: Controls agent tool access
- **BashRestrictedFilter**: Command whitelist/blacklist/confirm mechanism
- **Command Security**: Only whitelisted commands execute directly

---

## Using Orchestrator for Multi-Agent Coordination

The **Orchestrator** skill is used to coordinate multiple agents and manage complex workflows:

### When to Use Orchestrator

Use the `/orchestrator` skill when:
- A task requires coordination between multiple agents
- You need to implement a feature that involves code generation, debugging, or architecture decisions
- You want to get architectural guidance before writing code
- A task has dependencies across multiple components

### Example Commands

```bash
# Plan a new feature with architectural guidance
/orchestrator

# Implement the planned feature with quality enforcement
/orchestrator --enforce-quality

# Run tests to validate implementation
/orchestrator --test
```

### Workflow Integration

When a task requires coordination:
1. **Architectural Consultant** - Analyzes requirements, provides design patterns, ensures adherence to best practices
2. **Planner** - Creates detailed task breakdown, identifies dependencies, estimates complexity
3. **Implementer** - Generates code following the plan with TDD workflow
4. **Code Reviewer** - Reviews changes for architecture alignment and code quality (static/structure only); rejects or passes to Tester
5. **Environment Tester** - Validates that all quality gates are met (coverage, linting, type checking)

---

## Core Coding Agent Capabilities

### 1. Code Generation

The system provides intelligent code generation capabilities through the Claude Code agent:

#### Supported Capabilities

- **Feature Specification Analysis**: Understand and break down user requirements into implementable tasks
- **Architecture Design**: Create robust, maintainable code architecture following SOLID principles
- **Type-Safe Code Generation**: Generate code with full type hints and proper error handling
- **Unit Test Generation**: Create comprehensive tests following TDD principles
- **Code Refactoring**: Optimize existing code while maintaining functionality
- **Context Management**: Maintain understanding of codebase structure and relationships

#### Usage Patterns

```python
# Example: Generate code for a new feature
/orchestrator "Create a user authentication system"
```

### 2. Code Debugging

The system provides comprehensive debugging capabilities:

#### Supported Capabilities

- **Error Analysis**: Parse error messages, stack traces, and suggest fixes
- **Code Inspection**: Analyze code quality issues, provide refactoring suggestions
- **Performance Profiling**: Identify bottlenecks, suggest optimizations
- **Log Analysis**: Parse and analyze logs to understand runtime behavior
- **Interactive Debugging**: Support step-through debugging sessions

#### Usage Patterns

```python
# Example: Debug a failing test
/orchestrator "Debug failing test: tests/unit/test_auth.py"
```

### 3. Context Management

The system maintains awareness of the codebase structure and relationships:

#### Supported Capabilities

- **Codebase Indexing**: Understand the structure and organization of the project
- **Dependency Tracking**: Monitor relationships between modules and components
- **Change Detection**: Track modifications to files and understand impact
- **Code Navigation**: Provide efficient ways to locate and understand specific code sections

#### Usage Patterns

```python
# Example: Find all files related to a feature
/orchestrator "Search files related to: user authentication"
```

### 4. Sandbox Mechanism

The system provides a safe environment for code execution and testing:

#### Supported Capabilities

- **Isolated Execution**: Run code in controlled environment with limited system access
- **Resource Limiting**: Control CPU, memory, and network usage during execution
- **Time Limiting**: Enforce maximum execution time for operations
- **File System Isolation**: Use virtual or overlay filesystems to prevent accidental modifications
- **Input Validation**: Validate and sanitize all external inputs

---

## Common Agent Commands

### Orchestrator Commands

```bash
# Plan a task with architectural consultation
/orchestrator "Plan feature: Implement new file manager"

# Implement with quality enforcement
/orchestrator "Implement feature: Implement new file manager" --enforce-quality

# Test implementation
/orchestrator "Test feature: Implement new file manager"

# Get status of a workflow
/orchestrator "status: feature:file-manager"
```

### Subagent Communication

Orchestrator communicates with each subagent through standardized messages:
- **Architectural Consultant**: Design specifications, architecture reviews
- **Planner**: Task breakdowns, implementation plans
- **Implementer**: Code generation, refactoring suggestions
- **Code Reviewer**: Pass/reject with brief reasons and actionable suggestions
- **Environment Tester**: Test results, quality metrics

---

## Integration with mini-coder Project

### Current Status

The core coding agent workflow is **designed and documented** in CLAUDE.md but not yet fully integrated into the mini-coder project. The following steps are needed:

1. **Agent Configuration**: Set up Claude Code CLI with appropriate credentials
2. **Project Structure**: Create appropriate directory structure for agent workflows (agents/, workflows/, tests/)
3. **Workflow Integration**: Implement the agent workflow using Orchestrator
4. **Quality Gates**: Ensure all generated code passes quality gates (coverage >= 80%, PEP 8 compliance, type safety)

### Future Enhancements

Potential improvements to the coding agent workflow:

- **Persistent Context**: Maintain long-term knowledge about the codebase across sessions
- **Adaptive Agents**: Agents that learn from past interactions to improve performance
- **Code Templates**: Reusable code patterns for common tasks
- **Cross-Project Consistency**: Apply coding agent workflow consistently across all projects

---

## Best Practices

When using the multi-agent coding workflow:

1. **Clear Objectives**: Each task should have a well-defined purpose and expected outcome
2. **Start with Design**: Always consult Architectural Consultant before writing code
3. **Plan Thoroughly**: Use Planner to break down complex tasks into manageable steps
4. **Follow TDD**: Write tests first, implement to make tests pass
5. **Pass Code Review**: Ensure changes pass Code Reviewer (architecture + quality) before running tests
6. **Validate Quality**: Always run Environment Tester before considering work complete
7. **Document Changes**: Keep CLAUDE.md updated with workflow modifications
8. **Use Orchestrator**: For complex tasks requiring multiple agent coordination

---

## Project Status

This repository is currently implementing the mini-coder TUI component. The core coding agent workflow is documented and ready for integration once the TUI is complete.
