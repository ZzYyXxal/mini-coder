# Spec: Note Relations

Capability for typed relationships between notes with automatic detection and graph traversal support.

## ADDED Requirements

### Requirement: Relation types

The system SHALL support the following relation types between notes:
- `related_to`: General association
- `depends_on`: Dependency relationship
- `blocks`: Blocking relationship
- `implements`: Implementation relationship
- `derived_from`: Derivation relationship

#### Scenario: Add related_to relation
- **WHEN** user adds a "related_to" relation from note A to note B
- **THEN** note A's relations list SHALL contain note B's ID
- **AND** note A's relation_types SHALL map note B's ID to "related_to"

#### Scenario: Add bidirectional relation
- **WHEN** user adds a relation with bidirectional=true
- **THEN** both notes SHALL have each other in their relations list

### Requirement: Relation management API

The system SHALL provide CRUD operations for managing note relations.

#### Scenario: Remove relation
- **WHEN** user removes a relation from note A to note B
- **THEN** note B's ID SHALL be removed from note A's relations list
- **AND** note B's ID SHALL be removed from note A's relation_types

#### Scenario: Get related notes
- **WHEN** user queries related notes for note A
- **THEN** system SHALL return all notes that note A has relations to

### Requirement: Automatic relation detection

The system SHALL detect potential relations between notes based on similarity and category affinity.

#### Scenario: Detect similar notes
- **WHEN** a new note is created
- **AND** existing notes have similarity >= threshold (default 0.75)
- **THEN** system SHALL suggest relations to those notes

#### Scenario: Category affinity rules
- **WHEN** note A is category "decision" and note B is category "todo"
- **THEN** suggested relation type SHALL be "related_to"

#### Scenario: Auto-link disabled by default
- **WHEN** config `notes.relations.auto_detect` is true but `auto_link` is false
- **THEN** system SHALL suggest relations but NOT create them automatically

### Requirement: Relation graph traversal

The system SHALL support traversing the note relation graph to find connected notes.

#### Scenario: Traverse depth 1
- **WHEN** user requests related notes with depth=1
- **THEN** system SHALL return only directly connected notes

#### Scenario: Traverse depth 2
- **WHEN** user requests related notes with depth=2
- **THEN** system SHALL return notes connected within 2 hops
- **AND** results SHALL be grouped by depth level
