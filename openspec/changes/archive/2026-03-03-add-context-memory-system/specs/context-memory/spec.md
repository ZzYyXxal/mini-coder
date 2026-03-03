# Spec: Context Memory

Core memory management with working/persistent storage, priority queue, compression, and session persistence.

## ADDED Requirements

### Requirement: Working Memory Management

The system SHALL maintain a working memory in RAM that stores recent conversation messages with priority-based management.

#### Scenario: Add message to working memory
- **WHEN** a new message is added with a priority level
- **THEN** the message is stored in working memory with timestamp and metadata

#### Scenario: Evict low priority messages
- **WHEN** working memory exceeds max_messages limit
- **THEN** the system evicts the lowest priority message(s) to make room

#### Scenario: Skip empty messages
- **WHEN** a message with empty or whitespace-only content is added
- **THEN** the message is silently ignored and not stored

### Requirement: Priority-Based Context Retrieval

The system SHALL retrieve context ordered by priority, respecting token limits.

#### Scenario: Get context within token limit
- **WHEN** context is requested with a max_tokens limit
- **THEN** messages are returned in priority order (HIGH first) within the token limit

#### Scenario: Token buffer for counting errors
- **WHEN** calculating token usage
- **THEN** a 10% buffer is applied to account for counting inaccuracies

#### Scenario: High priority preservation
- **WHEN** context is compressed or evicted
- **THEN** HIGH priority messages (level 1-3) are preserved over LOW priority messages

### Requirement: Persistent Session Storage

The system SHALL persist session state to disk for cross-session continuity.

#### Scenario: Save session to disk
- **WHEN** save_session is called
- **THEN** the current session is written to JSON file in the memory directory

#### Scenario: Load session from disk
- **WHEN** load_session is called with a valid session_id
- **THEN** the session state is restored including all messages

#### Scenario: List available sessions
- **WHEN** list_sessions is called
- **THEN** all saved session IDs are returned as a list

#### Scenario: Handle missing session
- **WHEN** load_session is called with non-existent session_id
- **THEN** returns False without raising an exception

### Requirement: Automatic Compression

The system SHALL automatically compress context when approaching token limits.

#### Scenario: Trigger compression at threshold
- **WHEN** token usage reaches 92% of max_tokens
- **THEN** compression is automatically triggered

#### Scenario: Compress low priority messages
- **WHEN** compression is triggered
- **THEN** LOW and ARCHIVE priority messages are summarized and removed from working memory

#### Scenario: Preserve compression history
- **WHEN** messages are compressed
- **THEN** the summary is saved to persistent store with references to original messages

### Requirement: Message Data Model

The system SHALL use Pydantic models for type-safe message handling.

#### Scenario: Validate message role
- **WHEN** a message is created with invalid role
- **THEN** Pydantic validation raises an error

#### Scenario: Validate message content
- **WHEN** a message is created with empty content
- **THEN** Pydantic validation raises an error

#### Scenario: Auto-generate timestamp
- **WHEN** a message is created without timestamp
- **THEN** the current datetime is automatically assigned

### Requirement: Configuration

The system SHALL support configurable memory parameters.

#### Scenario: Configure max messages
- **WHEN** max_messages is set in configuration
- **THEN** working memory respects this limit

#### Scenario: Configure compression threshold
- **WHEN** compression_threshold is set in configuration
- **THEN** compression triggers at this ratio

#### Scenario: Configure storage path
- **WHEN** storage_path is set in configuration
- **THEN** persistent store uses this path for all file operations
