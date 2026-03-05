# Spec: Subagent Explorer

Read-only codebase exploration agent with controlled tool access.

## ADDED Requirements

### Requirement: Explorer Agent Provides Read-Only Codebase Search

The system SHALL provide an Explorer agent that performs read-only codebase exploration using Glob, Grep, and Read tools.

#### Scenario: Find files by pattern
- **WHEN** user asks to find files matching a pattern (e.g., "find all test files")
- **THEN** Explorer uses Glob tool with appropriate pattern to locate files
- **AND** returns absolute paths of all matching files

#### Scenario: Search code content
- **WHEN** user asks to search for code patterns (e.g., "where is authentication handled?")
- **THEN** Explorer uses Grep tool to search for relevant code patterns
- **AND** reports file paths and line numbers with context

#### Scenario: Read file contents
- **WHEN** Explorer needs to examine specific file contents
- **THEN** Explorer uses Read tool to retrieve file content
- **AND** includes relevant code snippets in the response

### Requirement: Explorer Agent Enforces Read-Only Constraints

The system SHALL prevent Explorer agent from modifying any files or executing state-changing commands.

#### Scenario: Block file modification
- **WHEN** Explorer attempts to use Write or Edit tool
- **THEN** the tool call is rejected by ReadOnlyFilter
- **AND** an error is logged

#### Scenario: Block destructive bash commands
- **WHEN** Explorer attempts to execute bash commands like `mkdir`, `git add`, `npm install`
- **THEN** only read-only bash commands are allowed (ls, git status, git log, git diff, find, cat, head, tail)
- **AND** state-changing commands are rejected

### Requirement: Explorer Agent Uses Absolute Paths

The system SHALL require Explorer agent to report all file paths using absolute paths.

#### Scenario: Report file locations
- **WHEN** Explorer reports discovered files
- **THEN** all file paths are reported as absolute paths
- **AND** relative paths are converted to absolute before reporting

### Requirement: Explorer Agent Supports Exploration Depth

The system SHALL support configurable exploration depth (quick, medium, thorough) for Explorer agent.

#### Scenario: Quick exploration
- **WHEN** thoroughness is set to "quick"
- **THEN** Explorer performs minimal searches (1-2 Glob/Grep calls)
- **AND** returns only most relevant results

#### Scenario: Medium exploration
- **WHEN** thoroughness is set to "medium"
- **THEN** Explorer performs moderate searches (3-5 Glob/Grep calls)
- **AND** returns comprehensive results

#### Scenario: Thorough exploration
- **WHEN** thoroughness is set to "thorough"
- **THEN** Explorer performs exhaustive searches (up to max_tool_calls)
- **AND** returns all relevant results with detailed analysis

### Requirement: Explorer Agent Provides Structured Output

The system SHALL require Explorer agent to provide structured output with findings and recommendations.

#### Scenario: Report findings
- **WHEN** Explorer completes exploration
- **THEN** Explorer reports what files/code were found with key conclusions
- **AND** maps findings back to the original request

#### Scenario: Recommend files for attention
- **WHEN** Explorer identifies files that Coder/Fixer should focus on
- **THEN** Explorer explicitly lists recommended files with reasons
- **AND** provides absolute paths for each recommendation
