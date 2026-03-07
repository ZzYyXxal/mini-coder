# Spec: Semantic Search

Capability for vector-based semantic similarity search for notes using local embeddings.

## ADDED Requirements

### Requirement: Local embedding generation

The system SHALL generate embeddings for note content using the configured embedding backend (default: fastembed; optional: OpenAI-compatible API) when semantic search is enabled.

#### Scenario: Generate embedding for new note
- **WHEN** a new note is created and semantic search is enabled
- **THEN** system SHALL generate an embedding vector for the note content
- **AND** store the embedding in the note's embedding field

#### Scenario: Regenerate embedding on edit
- **WHEN** note content is edited and semantic search is enabled
- **THEN** system SHALL regenerate the embedding vector

#### Scenario: Lazy embedding generation
- **WHEN** semantic search is first enabled
- **AND** notes exist without embeddings
- **THEN** system SHALL generate embeddings on first search

### Requirement: Semantic similarity search

The system SHALL support searching notes by semantic similarity to a query string.

#### Scenario: Search with semantic matching
- **WHEN** user searches for "数据库存储方案"
- **THEN** system SHALL return notes semantically similar to the query
- **AND** include notes that don't contain the exact keywords

#### Scenario: Similarity threshold filtering
- **WHEN** user searches with threshold=0.7
- **THEN** system SHALL only return notes with similarity >= 0.7

#### Scenario: Return similarity scores
- **WHEN** semantic search is performed
- **THEN** results SHALL include similarity scores for each match

### Requirement: Hybrid search support

The system SHALL support combining keyword and semantic search.

#### Scenario: Keyword-only search
- **WHEN** user searches with semantic=false
- **THEN** system SHALL use traditional keyword matching

#### Scenario: Semantic-only search
- **WHEN** user searches with semantic=true
- **THEN** system SHALL use vector similarity matching

#### Scenario: Combined search (future)
- **WHEN** user searches with both enabled
- **THEN** system SHALL combine and rank results from both methods

### Requirement: Optional dependency handling

The system SHALL gracefully handle missing embedding backend (fastembed not installed, or API not configured).

#### Scenario: Semantic search disabled when unavailable
- **WHEN** no embedding backend is available (e.g. fastembed not installed and API not configured)
- **AND** semantic search is enabled in config
- **THEN** system SHALL log a warning
- **AND** fall back to keyword search

#### Scenario: Clear error message
- **WHEN** user explicitly requests semantic search without an available backend
- **THEN** system SHALL return clear error message with installation or configuration instructions
