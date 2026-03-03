# Spec: Context Memory (Delta)

Changes to ProjectNote model for embedding and relation fields.

## ADDED Requirements

### Requirement: Embedding fields

ProjectNote model SHALL include optional fields for storing embeddings.

#### Scenario: Store embedding
- **WHEN** an embedding is generated for a note
- **THEN** embedding vector SHALL be stored in the embedding field as list[float]
- **AND** model name SHALL be stored in embedding_model field

#### Scenario: Check embedding freshness
- **WHEN** note has embedding from different model
- **THEN** needs_embedding(new_model) SHALL return true

### Requirement: Relation fields

ProjectNote model SHALL include fields for storing note relations.

#### Scenario: Add relation to note
- **WHEN** add_relation(note_id, type) is called
- **THEN** note_id SHALL be added to relations list
- **AND** type SHALL be stored in relation_types dict

#### Scenario: Remove relation from note
- **WHEN** remove_relation(note_id) is called
- **THEN** note_id SHALL be removed from relations list
- **AND** note_id SHALL be removed from relation_types dict

#### Scenario: Get related notes by type
- **WHEN** get_related_notes(relation_type="depends_on") is called
- **THEN** only notes with that relation type SHALL be returned

### Requirement: Backward compatibility

ProjectNote model SHALL maintain backward compatibility with existing note files.

#### Scenario: Load note without new fields
- **WHEN** loading a note JSON without embedding or relations fields
- **THEN** fields SHALL default to None (embedding) or empty list/dict (relations)

#### Scenario: Save note with new fields
- **WHEN** saving a note with embedding and relations
- **THEN** all fields SHALL be serialized to JSON
