## Context

The mini-coder project is being developed using external Claude Code skills that coordinate a multi-agent approach. These skills are invoked by developers using the Claude Code CLI to build mini-coder itself. The subagents are NOT implemented as Python code within mini-coder, but are defined as skill files, configuration, and documentation.

**Current State**: Mini-coder repository has incorrect Python implementations of subagents in `src/mini_coder/agents/`, `src/mini_coder/orchestrator/`, `src/mini_coder/knowledge/` that must be removed and replaced with external skill definitions.

**Constraints**:
- Subagents are external Claude Code skills invoked via CLI (`/skill:name`)
- Knowledge base is file-based markdown documentation, not a vector database
- Python 3.10+ with strict type hints and PEP 8 compliance for mini-coder code
- TDD workflow (Red-Green-Refactor) is mandatory for mini-coder development
- Token optimization required (prefer targeted edits over full rewrites)

**Stakeholders**: Developers using Claude Code to build mini-coder, maintainers of the skill definitions.

## Goals / Non-Goals

**Goals:**
- Define skill files and prompt templates for 5 external subagents
- Create file-based knowledge base with markdown documentation for architectural patterns
- Document TDD workflow that developers must follow when using skills
- Provide guidance for test execution and quality validation
- Document workflow coordination and dead-loop detection guidance

**Non-Goals:**
- Implement subagents as Python code within mini-coder
- Vector database integration (using file-based documentation instead)
- Persistent task storage (documentation-based state tracking)
- Automatic execution (developers manually invoke skills)

## Decisions

### 1. Subagent Execution Mechanism
**Decision**: Use Claude Code CLI skill invocation pattern

**Rationale**: Claude Code provides built-in skill system that can be invoked from command line. Skills are defined as markdown files with specific structure (SKILL.md). This aligns with external agent requirement without adding mini-coder dependencies.

**Alternatives considered**:
- Custom Python CLI: Would add complexity and maintenance burden
- External service: Adds latency and deployment complexity

### 2. Knowledge Base Storage
**Decision**: Use markdown files with YAML frontmatter for knowledge documentation

**Rationale**: File-based documentation is version-controlled, searchable via standard tools, and requires no external dependencies. YAML frontmatter allows metadata filtering (language, pattern_type) without vector database.

**Alternatives considered**:
- ChromaDB: Requires external dependency, SQLite version constraints
- Vector database: Overkill for documentation, adds complexity

### 3. Skill File Structure
**Decision**: Use standard Claude Code SKILL.md format in `.claude/skills/` directory

**Rationale**: Claude Code's built-in skill system uses SKILL.md files with specific structure. This allows easy distribution, versioning, and CLI invocation without custom implementation.

**Structure**:
```
.claude/skills/
├── orchestrator/SKILL.md          # Workflow coordination
├── architectural-consultant/SKILL.md  # Knowledge retrieval
├── planner/SKILL.md              # Task planning
├── implementer/SKILL.md          # Code implementation
└── tester/SKILL.md               # Quality validation
```

### 4. Configuration Management
**Decision**: Use YAML configuration files in `config/` directory

**Rationale**: YAML is human-readable, supports comments, and can define complex nested structures for agent behavior settings.

**Configuration files**:
```
config/
├── subagents.yaml        # Agent behavior settings
├── knowledge-base.yaml   # Knowledge sources
└── workflow.yaml         # Workflow rules
```

### 5. Workflow Coordination Approach
**Decision**: Manual skill invocation with documentation-based workflow guidance

**Rationale**: Rather than automatic orchestration, developers invoke skills sequentially based on workflow documentation. This provides flexibility and transparency while maintaining structure.

**Alternatives considered**:
- Automatic orchestration: Would require implementing coordinator as tool, not external
- Complex state machine: Overkill for manual skill invocation

### 6. Knowledge Retrieval Strategy
**Decision**: Grep/find-based search with metadata filtering

**Rationale**: Standard Unix tools work well with markdown files. YAML frontmatter enables filtering without vector database. Simple, reliable, no external dependencies.

**Alternatives considered**:
- Vector search: Requires embedding generation and database
- Full-text search libraries: Adds dependency burden

### 7. Dead-Loop Detection
**Decision**: Documentation-based guidance for human intervention

**Rationale**: Without automatic orchestration, dead-loop detection is a human-in-the-loop process documented in orchestrator skill.

**Alternatives considered**:
- Automatic state tracking: Requires implementing state persistence
- Error signature hashing: Requires running code to track

## External Agent Architecture

### Skill File Format

Each subagent is defined as a Claude Code skill with standard structure:

```markdown
# Skill Name

## Description
Brief description of what this skill does.

## Usage
How to invoke this skill from Claude Code CLI.

## Instructions
Detailed prompt template for the AI model.

## Tools
Tools and files this skill can access.

## Examples
Example usage scenarios.
```

### Knowledge Base Structure

```
docs/knowledge-base/
├── index.md                    # Knowledge base navigation
├── opencode-patterns/
│   ├── sandbox-isolation.md
│   ├── async-patterns.md
│   └── ...
├── hello-agent-patterns/
│   ├── self-reflection.md
│   └── ...
└── python-best-practices/
    ├── pydantic-usage.md
    ├── dependency-injection.md
    └── ...
```

### Knowledge File Format

Each knowledge file uses YAML frontmatter for metadata:

```markdown
---
title: Pydantic Data Models
language: python
pattern_type: best_practice
tags: [data, validation, typing]
last_updated: 2024-01-15
---

# Pydantic Data Models

## Usage Example
```python
from pydantic import BaseModel

class UserData(BaseModel):
    name: str
    age: int
```

## Best Practices
- Use type hints for all fields
- Provide default values where appropriate
- Use validators for complex validation
```

## Risks / Trade-offs

### Risk: Skill maintenance overhead
**Mitigation**: Keep skill files focused and well-documented. Use configuration for variable behavior.

### Trade-off: Manual vs. Automatic
**Decision**: Manual skill invocation for transparency and flexibility, accepting potential workflow drift.

### Risk: Knowledge base becoming stale
**Mitigation**: Include last_updated metadata, document refresh process.

### Trade-off: Simplicity vs. Features
**Decision**: Favor simple file-based approach over complex systems for maintainability.

## Migration Plan

**Phase 1**: Remove incorrect internal implementations
```bash
# Delete Python subagent implementations
rm -rf src/mini_coder/agents/
rm -rf src/mini_coder/orchestrator/
rm -rf src/mini_coder/knowledge/
rm tests/test_*.py
```

**Phase 2**: Create skill directory structure
```bash
mkdir -p .claude/skills/{orchestrator,architectural-consultant,planner,implementer,tester}
```

**Phase 3**: Create knowledge base structure
```bash
mkdir -p docs/knowledge-base/{opencode-patterns,hello-agent-patterns,python-best-practices}
```

**Phase 4**: Create configuration files
```bash
mkdir -p config
touch config/{subagents.yaml,knowledge-base.yaml,workflow.yaml}
```

**Phase 5**: Write skill files and knowledge documentation
```bash
# Write SKILL.md files for each agent
# Create knowledge base markdown files
```

**Rollback Strategy**: Git commit after each phase. Rollback by reverting commits if issues arise.

## Open Questions

1. **Skill distribution**: How will skills be distributed to other developers?
   - Action: Document in README, consider packaging as separate repository

2. **Knowledge base curation**: Who maintains the knowledge base documentation?
   - Action: Define ownership process, contribution guidelines

3. **Workflow enforcement**: How to ensure developers follow the documented workflow?
   - Action: Include checklist in orchestrator skill, document best practices

4. **Configuration management**: Should configuration be versioned or local-only?
   - Action: Version templates, allow local overrides via .gitignore patterns
