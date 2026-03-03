# Spec: LLM Service (Context Integration)

Integration of context memory into the LLM service layer for automatic context injection.

## ADDED Requirements

### Requirement: Context Manager Integration

The LLM service SHALL integrate with the context memory manager for automatic context handling.

#### Scenario: Initialize context manager
- **WHEN** LLM service is initialized
- **THEN** a ContextMemoryManager instance is created with configured settings

#### Scenario: Disable context memory
- **WHEN** memory.enabled is set to false in configuration
- **THEN** context manager is not initialized and LLM calls proceed without context

### Requirement: Automatic Context Injection

The LLM service SHALL automatically inject context into chat calls.

#### Scenario: Add user message to context
- **WHEN** chat method is called with user message
- **THEN** the message is added to context with HIGH priority

#### Scenario: Build context for LLM call
- **WHEN** preparing LLM call
- **THEN** context is built from memory and included in the messages list

#### Scenario: Add assistant response to context
- **WHEN** LLM response is received
- **THEN** the response is added to context with MEDIUM priority

### Requirement: Session Management

The LLM service SHALL support session-based context persistence.

#### Scenario: Start new session
- **WHEN** start_session is called
- **THEN** a new session ID is generated and returned

#### Scenario: Save session on exit
- **WHEN** save_session is called or TUI exits gracefully
- **THEN** current session is persisted to disk

#### Scenario: Restore previous session
- **WHEN** load_session is called with a session ID
- **THEN** previous session context is restored

### Requirement: Streaming with Context

The LLM service SHALL support streaming responses while maintaining context.

#### Scenario: Stream response with context
- **WHEN** chat_stream is called
- **THEN** context is built and included, response is streamed

#### Scenario: Update context after stream
- **WHEN** streaming response completes
- **THEN** full response is added to context

### Requirement: Configuration

The LLM service SHALL support memory configuration via config file.

#### Scenario: Load memory config
- **WHEN** LLM service initializes
- **THEN** memory settings are loaded from config/memory.yaml

#### Scenario: Default memory settings
- **WHEN** no memory config is provided
- **THEN** sensible defaults are used (max_messages=20, threshold=0.92)
