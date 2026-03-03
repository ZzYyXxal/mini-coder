# Spec: LLM Service (Delta)

Changes to LLMService for auto-extraction integration and semantic search API methods.

## ADDED Requirements

### Requirement: Auto-extraction integration

LLMService SHALL integrate NoteExtractor into the chat stream pipeline to automatically extract notes from LLM responses.

#### Scenario: Extract after response
- **WHEN** LLMService completes a chat_stream response
- **AND** auto_extract is enabled
- **THEN** system SHALL call NoteExtractor.extract() on the response

#### Scenario: Save extracted notes
- **WHEN** NoteExtractor returns extracted notes
- **AND** confidence >= threshold
- **THEN** system SHALL save notes via ProjectNotesManager

### Requirement: Semantic search API

LLMService SHALL provide API methods for semantic note search.

#### Scenario: Search notes semantically
- **WHEN** user calls search_notes(query, semantic=True)
- **THEN** system SHALL use SemanticNoteSearch for matching

#### Scenario: Search with category filter
- **WHEN** user calls search_notes(query, category="todo", semantic=True)
- **THEN** system SHALL return only todo notes matching the query

### Requirement: Relation management API

LLMService SHALL provide convenience methods for note relation management.

#### Scenario: Add relation between notes
- **WHEN** user calls add_relation(source_id, target_id, relation_type)
- **THEN** system SHALL create the relation via NoteRelationManager

#### Scenario: Get related notes
- **WHEN** user calls get_related_notes(note_id, depth=2)
- **THEN** system SHALL return notes related within specified depth
