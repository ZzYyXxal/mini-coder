# Spec: Subagent Coder

Code implementation agent with full access to file editing tools.

## ADDED Requirements

### Requirement: Coder Agent Generates Code

The system SHALL provide a Coder agent that generates code according to implementation plans.

#### Scenario: Implement new feature
- **WHEN** Coder receives a task with implementation plan
- **THEN** Coder generates complete code files with proper structure
- **AND** code follows the implementation plan

#### Scenario: Follow TDD workflow
- **WHEN** implementation plan specifies test-first approach
- **THEN** Coder writes tests before implementation code
- **AND** implementation code is written to make tests pass

### Requirement: Coder Agent Prefers Editing Over Creating

The system SHALL require Coder agent to prefer editing existing files over creating new files.

#### Scenario: Edit existing file
- **WHEN** functionality can be added by editing an existing file
- **THEN** Coder uses Edit tool to modify the existing file
- **AND** does not create a new file

#### Scenario: Create new file when necessary
- **WHEN** functionality requires a new module or test file
- **THEN** Coder creates a new file with appropriate name and location
- **AND** follows project conventions for file naming

### Requirement: Coder Agent Follows Project Coding Standards

The system SHALL require Coder agent to follow project-specific coding standards.

#### Scenario: Apply coding standards
- **WHEN** Coder generates code
- **THEN** code follows project coding standards (injected via {{coding_standards}})
- **AND** standards include: naming conventions, indentation, line length, type hints, docstrings

#### Scenario: Type hints compliance
- **WHEN** Coder writes Python functions
- **THEN** all functions have complete type hints using Python 3.10+ syntax
- **AND** type hints cover parameters, return types, and complex types

#### Scenario: Google-style docstrings
- **WHEN** Coder documents public APIs
- **THEN** docstrings follow Google style format
- **AND** include Args, Returns, Raises sections as appropriate

### Requirement: Coder Agent Uses Full Access Tools

The system SHALL provide Coder agent with full access to Read, Write, Edit, Glob, Grep, and restricted Bash tools.

#### Scenario: Write new files
- **WHEN** Coder needs to create new files
- **THEN** Coder uses Write tool to create files
- **AND** file paths use absolute paths

#### Scenario: Edit existing files
- **WHEN** Coder needs to modify existing files
- **THEN** Coder uses Edit tool with appropriate search/replace patterns
- **AND** edits are minimal and targeted

#### Scenario: Run code quality checks
- **WHEN** Coder completes code generation
- **THEN** Coder can use Bash tool to run quality checks (mypy, flake8, pytest)
- **AND** dangerous bash commands are blocked by FullAccessFilter

### Requirement: Coder Agent Provides Memory Summary

The system SHALL require Coder agent to output a "memory summary" section for the main agent to persist.

#### Scenario: Generate memory summary
- **WHEN** Coder completes implementation
- **THEN** Coder outputs a structured "memory summary" section
- **AND** summary includes: key files modified, implementation highlights, important notes

#### Scenario: Memory summary format
- **WHEN** memory summary is generated
- **THEN** it follows a fixed format for parsing by main agent
- **AND** summary is concise and actionable
