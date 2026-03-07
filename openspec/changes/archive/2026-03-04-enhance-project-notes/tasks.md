# Tasks: Enhance Project Notes System

## 1. ProjectNote Model Extensions

- [x] 1.1 Add `relations: list[str]` field to ProjectNote model with default_factory=list
- [x] 1.2 Add `relation_types: dict[str, str]` field to ProjectNote model with default_factory=dict
- [x] 1.3 Add `embedding: list[float] | None` field to ProjectNote model with default=None
- [x] 1.4 Add `embedding_model: str | None` field to ProjectNote model with default=None
- [x] 1.5 Add `add_relation(note_id, relation_type)` method to ProjectNote
- [x] 1.6 Add `remove_relation(note_id)` method to ProjectNote
- [x] 1.7 Add `needs_embedding(model_name)` method to ProjectNote
- [x] 1.8 Write unit tests for new ProjectNote fields and methods

## 2. Note Extractor Implementation

- [x] 2.1 Create `src/mini_coder/memory/note_extractor.py` module
- [x] 2.2 Define `EXTRACTION_PATTERNS` dict with regex patterns for each category
- [x] 2.3 Create `ExtractedNote` model with category, content, confidence, source fields
- [x] 2.4 Implement `NoteExtractor` class with `extract(content)` method
- [x] 2.5 Add confidence scoring based on pattern match quality
- [x] 2.6 Write unit tests for NoteExtractor in `tests/memory/test_extractor.py`
- [x] 2.7 Add NoteExtractor to `memory/__init__.py` exports

## 3. Note Relations Implementation

- [x] 3.1 Create `src/mini_coder/memory/note_relations.py` module
- [x] 3.2 Define `RelationType` enum with all relation types
- [x] 3.3 Create `NoteRelation` model with source_id, target_id, relation_type fields
- [x] 3.4 Implement `NoteRelationManager` class with CRUD operations
- [x] 3.5 Implement `get_related_notes(note_id, depth)` for graph traversal
- [x] 3.6 Implement `AutoRelationDetector` class with similarity calculation
- [x] 3.7 Add category affinity rules for relation type inference
- [x] 3.8 Write unit tests in `tests/memory/test_relations.py`
- [x] 3.9 Add note_relations to `memory/__init__.py` exports

## 4. Embedding Service Implementation

- [x] 4.1 Create `src/mini_coder/memory/embeddings.py` module
- [x] 4.2 Implement `LocalEmbeddingService` class (fastembed default, optional API)
- [x] 4.3 Add `embed(text) -> np.ndarray` method
- [x] 4.4 Add `embed_batch(texts) -> np.ndarray` method
- [x] 4.5 Add `cosine_similarity(a, b)` static method
- [x] 4.6 Add graceful fallback when embedding backend unavailable
- [x] 4.7 Write unit tests in `tests/memory/test_embeddings.py`
- [x] 4.8 Add embeddings to `memory/__init__.py` exports

## 5. Semantic Search Implementation

- [x] 5.1 Create `src/mini_coder/memory/semantic_search.py` module
- [x] 5.2 Implement `SemanticNoteSearch` class
- [x] 5.3 Add `build_index(project_key)` method for creating search index
- [x] 5.4 Add `search(query, top_k, threshold)` method returning (note, score) tuples
- [x] 5.5 Integrate with ProjectNotesManager for note retrieval
- [x] 5.6 Add index persistence support
- [x] 5.7 Write unit tests in `tests/memory/test_semantic_search.py`
- [x] 5.8 Add semantic_search to `memory/__init__.py` exports

## 6. ProjectNotesManager Integration

- [x] 6.1 Add `enable_semantic_search` parameter to ProjectNotesManager.__init__
- [x] 6.2 Initialize SemanticNoteSearch when semantic search enabled
- [x] 6.3 Update `search_notes()` to support semantic parameter
- [x] 6.4 Add `NoteRelationManager` as optional component
- [x] 6.5 Update `add_note()` to trigger relation detection
- [x] 6.6 Update existing tests for new parameters
- [x] 6.7 Add integration tests for combined functionality

## 7. LLMService Integration

- [x] 7.1 Add `auto_extract_notes` parameter to LLMService.__init__
- [x] 7.2 Initialize NoteExtractor when auto-extract enabled
- [x] 7.3 Add `_extract_and_save_notes(response)` private method
- [x] 7.4 Integrate extraction into `async_chat_stream()` pipeline
- [x] 7.5 Add `search_notes_semantic(query)` convenience method
- [x] 7.6 Add `add_relation(source_id, target_id, type)` convenience method
- [x] 7.7 Add `get_related_notes(note_id, depth)` convenience method
- [x] 7.8 Update existing LLMService tests
- [x] 7.9 Add integration tests for auto-extraction

## 8. Configuration Updates

- [x] 8.1 Add `notes.auto_extract.enabled` config option (default: true)
- [x] 8.2 Add `notes.auto_extract.confidence_threshold` config option (default: 0.8)
- [x] 8.3 Add `notes.semantic_search.enabled` config option (default: false)
- [x] 8.4 Add `notes.semantic_search.model` / embeddings model config (default: fastembed model)
- [x] 8.5 Add `notes.semantic_search.similarity_threshold` config option (default: 0.7)
- [x] 8.6 Add `notes.relations.enabled` config option (default: true)
- [x] 8.7 Add `notes.relations.auto_detect` config option (default: true)
- [x] 8.8 Add `notes.relations.auto_detect_threshold` config option (default: 0.75)
- [x] 8.9 Update `config/memory.yaml` with new options
- [x] 8.10 Document configuration in README

## 9. Dependencies

- [x] 9.1 Add `fastembed` as optional dependency in pyproject.toml (semantic); optional `openai` for API backend
- [x] 9.2 Add `numpy` as dependency (required for embeddings)
- [x] 9.3 Update requirements.txt if needed

## 10. Documentation

- [x] 10.1 Update `docs/project-notes-enhancement.md` with implementation notes
- [x] 10.2 Add API documentation for new classes and methods
- [x] 10.3 Add usage examples to README or docs

## 11. Quality Gates

- [x] 11.1 Run pytest and ensure >= 80% coverage
- [x] 11.2 Run mypy and ensure zero type errors
- [x] 11.3 Run flake8 and ensure PEP 8 compliance
- [x] 11.4 Verify all tests pass
