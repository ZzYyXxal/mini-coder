# Proposal: Enhance Project Notes System

## Why

The current ProjectNotes system requires manual note creation, leading to missed important decisions and increased cognitive load. Users must actively record decisions, todos, and blockers instead of focusing on development. Additionally, notes exist in isolation without relationships, and search is limited to keyword matching, missing semantically related content.

This change addresses three key gaps identified through comparison with Hello-Agents' NoteTool:
1. Manual note creation → Automatic extraction from LLM responses
2. Keyword-only search → Semantic similarity search
3. Isolated notes → Connected note relationships

## What Changes

### Auto Note Extraction
- Add `NoteExtractor` to automatically detect and extract notes from LLM responses
- Support pattern-based extraction for decisions, todos, blocks, and patterns
- Add confidence scoring for extracted notes
- Integrate extraction into `LLMService.chat_stream` pipeline

### Semantic Search
- Add embedding generation for notes using sentence-transformers
- Implement vector similarity search for semantic matching
- Support hybrid search (keyword + semantic)
- Add index building and persistence

### Note Relations
- Add typed relations between notes (related_to, depends_on, blocks, implements)
- Implement `NoteRelationManager` for relation CRUD
- Add automatic relation detection based on similarity and category affinity
- Support relation graph traversal

## Capabilities

### New Capabilities

- `note-extractor`: Automatic extraction of structured notes from LLM responses using pattern matching and optional LLM assistance

- `note-relations`: Typed relationships between notes with automatic detection and graph traversal support

- `semantic-search`: Vector-based semantic similarity search for notes using local embeddings

### Modified Capabilities

- `llm-service`: Add auto-extraction integration and semantic search API methods

- `context-memory`: Extend ProjectNote model with embedding and relation fields

## Impact

### Files Modified
- `src/mini_coder/memory/project_notes.py` - Add embedding and relation fields to ProjectNote
- `src/mini_coder/memory/context_builder.py` - Integrate semantic search
- `src/mini_coder/llm/service.py` - Add extraction and search methods

### Files Created
- `src/mini_coder/memory/note_extractor.py` - Auto-extraction logic
- `src/mini_coder/memory/note_relations.py` - Relation management
- `src/mini_coder/memory/embeddings.py` - Embedding service
- `src/mini_coder/memory/semantic_search.py` - Semantic search implementation

### Dependencies
- `sentence-transformers` - For local embeddings (optional, feature-gated)

### Configuration
- `config/memory.yaml` - Add notes enhancement options (auto_extract, semantic_search, relations)

### Tests
- `tests/memory/test_extractor.py`
- `tests/memory/test_relations.py`
- `tests/memory/test_semantic_search.py`
