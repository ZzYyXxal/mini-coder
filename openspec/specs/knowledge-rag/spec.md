# Knowledge RAG (Retrieval Augmented Generation)

## Purpose

The system shall provide a file-based knowledge base for storing and retrieving architectural patterns, best practices, and guidance for the mini-coder subagent system. The knowledge base serves as a source of truth for the Architectural Consultant skill to reference when providing guidance.

## Requirements

### Requirement: Architectural Consultant skill provides knowledge base search
The architectural consultant skill SHALL provide instructions for searching file-based knowledge base for relevant architectural patterns.

#### Scenario: Retrieve pydantic usage patterns
- **WHEN** planner skill requests best practices for data modeling
- **THEN** architectural consultant skill searches knowledge base for "pydantic data models"
- **AND** skill returns relevant markdown documents with file paths and excerpts

#### Scenario: Retrieve dependency injection patterns
- **WHEN** planner asks for modularity design patterns
- **THEN** architectural consultant skill searches knowledge base for "dependency injection python"
- **AND** skill returns OpenCode sandbox isolation strategy documents

### Requirement: Knowledge base contains OpenCode patterns
The system SHALL store OpenCode patterns as markdown files with YAML frontmatter for categorization.

#### Scenario: Knowledge base structure
- **WHEN** knowledge base is created
- **THEN** system includes `docs/knowledge-base/opencode-patterns/` directory
- **AND** each pattern is stored as markdown file with frontmatter

#### Scenario: Retrieve sandbox isolation strategies
- **WHEN** implementer needs environment isolation guidance
- **THEN** architectural consultant skill filters files by pattern_type="sandbox_isolation"
- **AND** skill returns relevant isolation strategy documents

### Requirement: Knowledge base contains Hello-Agent self-reflection mechanisms
The system SHALL store Hello-Agent self-reflection mechanisms as markdown files in knowledge base.

#### Scenario: Store reflection patterns
- **WHEN** knowledge ingestion adds Hello-Agent patterns
- **THEN** system creates markdown files with self-reflection steps and error recovery strategies
- **AND** files are tagged with metadata: mechanism="self_reflection", approach="recursive_repair"

#### Scenario: Retrieve recursive repair strategies
- **WHEN** architectural consultant provides alternative for stuck implementation
- **THEN** system retrieves self-reflection mechanism documents
- **AND** skill returns step-by-step repair strategies

### Requirement: Architectural Consultant skill provides Python best practices
The architectural consultant skill SHALL retrieve Python best practices from knowledge base documentation.

#### Scenario: Recommend pydantic for data validation
- **WHEN** planner skill designs data models for new module
- **THEN** architectural consultant skill retrieves pydantic usage pattern documents
- **AND** skill provides example code with type hints and validation rules

#### Scenario: Recommend dependency_injector for decoupling
- **WHEN** planner skill designs module dependencies
- **THEN** architectural consultant skill retrieves dependency injection pattern documents
- **AND** skill provides example showing container configuration

### Requirement: Architectural Consultant skill warns of edge cases
The architectural consultant skill SHALL warn planner skill of potential edge cases based on stored patterns.

#### Scenario: Warn about async edge cases
- **WHEN** planner skill designs async operation flow
- **THEN** architectural consultant skill retrieves async edge case pattern documents
- **AND** skill warns about race conditions, cancellation, and exception handling

#### Scenario: Warn about type validation edge cases
- **WHEN** planner skill designs complex type system
- **THEN** architectural consultant skill retrieves pydantic validation edge case documents
- **AND** skill warns about forward references, recursive models, and coercion issues

### Requirement: Architectural Consultant skill provides alternative refactorings
The architectural consultant skill SHALL provide alternative refactoring solutions when code fixes are stuck.

#### Scenario: Alternative refactoring for circular dependency
- **WHEN** implementer reports circular import deadlock
- **THEN** architectural consultant skill retrieves circular dependency resolution pattern documents
- **AND** skill provides 2-3 alternative refactoring strategies
- **AND** skill ranks options by maintainability and complexity

#### Scenario: Alternative architecture for performance bottleneck
- **WHEN** tester identifies performance issue after 3 failed fix attempts
- **THEN** architectural consultant skill retrieves performance optimization pattern documents
- **AND** skill suggests architectural alternatives (caching, async, batching)

### Requirement: Knowledge base uses YAML frontmatter for metadata
The system SHALL support YAML frontmatter in markdown files for metadata filtering.

#### Scenario: File with frontmatter
- **WHEN** creating knowledge file
- **THEN** system uses YAML frontmatter with fields: title, language, pattern_type, tags, last_updated
- **AND** metadata is searchable via standard tools

#### Scenario: Filter by programming language
- **WHEN** architectural consultant skill retrieves patterns with language="python" constraint
- **THEN** system filters knowledge files by language metadata
- **AND** returns only Python-related pattern documents

### Requirement: Knowledge base tracks document freshness
The system SHALL track timestamp and version for each stored pattern via frontmatter.

#### Scenario: Document with last_updated metadata
- **WHEN** architectural consultant skill retrieves patterns
- **THEN** system displays last_updated timestamp from frontmatter
- **AND** skill includes freshness consideration in relevance ranking

#### Scenario: Manual knowledge refresh guidance
- **WHEN** developer needs to update knowledge base
- **THEN** skill provides guidance for updating pattern documents
- **AND** skill includes instruction to update last_updated timestamp

### Requirement: Knowledge base ingestion handles code and documentation
The system SHALL store both code patterns and documentation as markdown files.

#### Scenario: Extract patterns from code
- **WHEN** knowledge ingestion processes code examples
- **THEN** system creates markdown files with code blocks for pattern demonstrations
- **AND** system preserves code structure and formatting

#### Scenario: Extract patterns from documentation
- **WHEN** knowledge ingestion processes external documentation
- **THEN** system creates markdown files with architectural explanations and best practices
- **AND** system preserves formatting and links related patterns

### Requirement: Knowledge base provides search guidance
The architectural consultant skill SHALL provide guidance for searching knowledge base using standard tools.

#### Scenario: Grep-based search
- **WHEN** skill needs to find relevant patterns
- **THEN** skill provides grep/find command examples for searching markdown files
- **AND** skill includes examples for filtering by metadata patterns

#### Scenario: Browse-based navigation
- **WHEN** skill provides knowledge access
- **THEN** skill includes index.md with categorized links to pattern files
- **AND** skill describes how to navigate knowledge base structure

### Requirement: Knowledge base supports manual organization
The system SHALL support manual organization and curation of knowledge files.

#### Scenario: File naming conventions
- **WHEN** adding knowledge files
- **THEN** system follows naming convention: `[topic]-[pattern].md`
- **AND** system uses descriptive names for easy discovery

#### Scenario: Categorization structure
- **WHEN** organizing knowledge files
- **THEN** system uses directory structure: `docs/knowledge-base/{category}/`
- **AND** categories include: opencode-patterns, hello-agent-patterns, python-best-practices
