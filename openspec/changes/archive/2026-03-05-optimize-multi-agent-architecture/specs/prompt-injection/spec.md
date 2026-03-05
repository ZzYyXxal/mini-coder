# Spec: Prompt Injection

Dynamic prompt loading and interpolation system for agent system prompts.

## ADDED Requirements

### Requirement: PromptLoader Class Provides Dynamic Loading

The system SHALL provide a PromptLoader class that loads agent system prompts from markdown files.

#### Scenario: Load prompt from file
- **WHEN** PromptLoader.load(agent_type, context) is called
- **THEN** PromptLoader reads the corresponding markdown file from knowledge-base/mini-coder-agent-prompts/
- **AND** returns the file content as a string

#### Scenario: Cache prompts
- **WHEN** the same prompt is requested multiple times
- **THEN** PromptLoader returns cached content without re-reading the file
- **AND** cache key is the agent_type

#### Scenario: Handle missing prompt file
- **WHEN** requested prompt file does not exist
- **THEN** PromptLoader falls back to built-in default prompt (code constant)
- **AND** logs a warning about missing file

### Requirement: PromptLoader Supports Placeholder Interpolation

The system SHALL support placeholder replacement in loaded prompts using {{identifier}} syntax.

#### Scenario: Replace placeholders
- **WHEN** context dictionary is provided to load()
- **THEN** placeholders in format {{key}} are replaced with context[key] values
- **AND** replacement is case-sensitive

#### Scenario: Handle missing placeholder
- **WHEN** a placeholder key is not in context dictionary
- **THEN** the placeholder remains unreplaced in output
- **AND** no error is raised

#### Scenario: Escape special characters
- **WHEN** context values contain special characters (newlines, quotes)
- **THEN** values are properly escaped for inclusion in prompt
- **AND** prompt structure is preserved

### Requirement: Predefined Placeholders

The system SHALL support a set of predefined placeholders for common use cases.

#### Scenario: Tool name placeholders
- **WHEN** prompt contains {{GLOB_TOOL_NAME}}, {{GREP_TOOL_NAME}}, {{READ_TOOL_NAME}}
- **THEN** placeholders are replaced with actual tool names from tool registry
- **AND** default values are "Glob", "Grep", "Read"

#### Scenario: Exploration depth placeholder
- **WHEN** prompt contains {{thoroughness}}
- **THEN** placeholder is replaced with exploration depth value (quick/medium/thorough)
- **AND** default value is "medium"

#### Scenario: Coding standards placeholder
- **WHEN** prompt contains {{coding_standards}}
- **THEN** placeholder is replaced with project coding standards from config/coding-standards.md
- **AND** if file missing, uses default standards string

#### Scenario: Project name placeholder
- **WHEN** prompt contains {{project_name}}
- **THEN** placeholder is replaced with project name from CLAUDE.md or config
- **AND** default value is extracted from project root directory name

### Requirement: PromptLoader Supports Project Standards Injection

The system SHALL support loading and injecting project-specific coding standards.

#### Scenario: Load coding standards
- **WHEN** project standards injection is requested
- **THEN** PromptLoader reads config/coding-standards.md or CLAUDE.md
- **AND** returns the standards content for injection

#### Scenario: Inject standards into prompt
- **WHEN** Coder agent prompt is loaded
- **THEN** coding standards are injected via {{coding_standards}} placeholder
- **AND** standards are formatted as markdown bullet points

### Requirement: PromptLoader API

The system SHALL provide a clean API for prompt loading and interpolation.

#### Scenario: Initialize with custom directory
- **WHEN** PromptLoader is initialized with prompt_dir parameter
- **THEN** custom directory is used instead of default knowledge-base/mini-coder-agent-prompts/
- **AND** directory path is validated for existence

#### Scenario: Load with context
- **WHEN** load(agent_type, context) is called with context dictionary
- **THEN** prompt is loaded and interpolated with context values
- **AND** result is returned as a single string

#### Scenario: Clear cache
- **WHEN** clear_cache() is called
- **THEN** all cached prompts are cleared
- **AND** subsequent loads will re-read from files
