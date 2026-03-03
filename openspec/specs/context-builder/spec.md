# Spec: Context Builder

GSSC pipeline (Gather-Select-Structure-Compress) for building context from multiple sources before LLM calls.

## ADDED Requirements

### Requirement: GSSC Pipeline

The system SHALL implement a Gather-Select-Structure-Compress pipeline for context building.

#### Scenario: Gather from multiple sources
- **WHEN** context is built
- **THEN** messages are gathered from working memory and persistent store

#### Scenario: Select by priority and tokens
- **WHEN** selecting messages for context
- **THEN** messages are filtered by priority and total token count

#### Scenario: Structure for LLM consumption
- **WHEN** structuring context
- **THEN** messages are formatted as a list of dicts with role and content

#### Scenario: Compress to fit token limit
- **WHEN** total tokens exceed max_tokens
- **THEN** low priority content is compressed or removed

### Requirement: Token Counting

The system SHALL provide accurate token counting for context management.

#### Scenario: Count message tokens
- **WHEN** a message is added or retrieved
- **THEN** token count is calculated for the content

#### Scenario: Calculate token ratio
- **WHEN** checking compression threshold
- **THEN** current token usage as ratio of max_tokens is returned

#### Scenario: Support multiple tokenizers
- **WHEN** a specific tokenizer is configured
- **THEN** that tokenizer is used for counting (default: approximation)

### Requirement: Context Assembly

The system SHALL assemble context in the correct order for LLM calls.

#### Scenario: System prompt first
- **WHEN** context is assembled
- **THEN** system prompt (if any) appears first

#### Scenario: Conversation history in order
- **WHEN** context is assembled
- **THEN** conversation messages appear in chronological order within each priority level

#### Scenario: Respect max tokens
- **WHEN** context is assembled
- **THEN** total tokens do not exceed max_tokens minus buffer

### Requirement: Integration with LLM Service

The context builder SHALL integrate transparently with the LLM service layer.

#### Scenario: Auto-inject context on chat
- **WHEN** LLM service chat method is called
- **THEN** context is automatically built and included in the LLM call

#### Scenario: Update context after response
- **WHEN** LLM response is received
- **THEN** response is added to context with appropriate priority

#### Scenario: Handle context build failure
- **WHEN** context building fails
- **THEN** LLM call proceeds with empty context (graceful degradation)

### Requirement: Project Memory Integration

The context builder SHALL optionally include project-level memory.

#### Scenario: Include CLAUDE.md content
- **WHEN** project has a CLAUDE.md file
- **THEN** its content is included as system context (if enabled)

#### Scenario: Project memory priority
- **WHEN** project memory is included
- **THEN** it is assigned MEDIUM priority by default

#### Scenario: Skip missing project memory
- **WHEN** project has no CLAUDE.md file
- **THEN** context building proceeds without it
