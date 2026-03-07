# Design: Enhance Project Notes System

## Context

The mini-coder project has an existing `ProjectNotes` system (`src/mini_coder/memory/project_notes.py`) that provides NoteTool-like functionality:
- 5 note categories: decision, todo, pattern, info, block
- 4 statuses: ACTIVE, COMPLETED, ARCHIVED, RESOLVED
- Per-project JSON persistence
- Integration with ContextBuilder (GSSC pipeline, CRITICAL priority)

**Current Limitations**:
1. Notes must be manually created via API calls
2. Search is keyword-based only (string matching)
3. Notes exist in isolation without relationships

**Stakeholders**: LLMService, ContextBuilder, TUI (future)

## Goals / Non-Goals

**Goals:**
- Automatically extract notes from LLM responses using pattern matching
- Enable semantic search for better note discovery
- Create typed relationships between related notes
- Maintain backward compatibility with existing ProjectNotes API

**Non-Goals:**
- LLM-assisted extraction (Phase 2 - adds latency and cost)
- Vector database integration (ChromaDB) - local embeddings sufficient
- Note versioning/history tracking
- Real-time collaborative note editing

## Decisions

### D1: Pattern-Based Extraction (Rule Matching)

**Decision**: Use regex pattern matching for initial auto-extraction.

**Rationale**:
- Zero latency overhead
- No additional API calls
- Predictable behavior
- Sufficient for common patterns ("决定...", "TODO:", etc.)

**Alternatives Considered**:
| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| Rule matching | Fast, predictable, no cost | Limited patterns | ✅ Chosen (Phase 1) |
| LLM extraction | Smart, handles edge cases | Latency, cost, non-deterministic | 📋 Phase 2 optional |
| Hybrid | Best of both | Complexity | 📋 Future consideration |

### D2: Local Embeddings (fastembed default, optional API)

**Decision**: Use **fastembed** (ONNX, no PyTorch) as default for local embeddings; optionally use OpenAI-compatible embedding API when configured.

**Rationale**:
- fastembed: no PyTorch/torch dependency, lower memory and startup cost
- 384-dimensional vectors (e.g. BAAI/bge-small-en-v1.5), efficient storage
- Optional API (e.g. DashScope text-embedding-v4) for higher quality when configured
- Configurable `batch_size` to limit memory usage

**Alternatives Considered**:
| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| fastembed (local, ONNX) | No torch, low memory, fast | Model download | ✅ Chosen (default) |
| Embedding API (DashScope/OpenAI) | High quality | Cost, latency, API key | ✅ Optional via config |
| sentence-transformers (PyTorch) | Mature | Heavy torch dependency | ❌ Replaced by fastembed |
| ChromaDB with embeddings | Full vector DB | Overkill for note count | 📋 Future consideration |

### D3: Embedding Storage in ProjectNote Model

**Decision**: Store embeddings directly in ProjectNote JSON as `list[float]`.

**Rationale**:
- Simplicity - no separate index files
- Atomic updates - note and embedding always in sync
- Acceptable size - 384 floats × 4 bytes = ~1.5KB per note

**Alternatives Considered**:
| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| In-model storage | Simple, atomic | Slight file size increase | ✅ Chosen |
| Separate index file | Smaller notes | Sync complexity | ❌ Rejected |
| ChromaDB collection | Scalable, fast | External dependency | 📋 Future consideration |

### D4: Relation Storage in ProjectNote Model

**Decision**: Store relations as `relations: list[str]` and `relation_types: dict[str, str]` in ProjectNote.

**Rationale**:
- Simple implementation
- No separate relation store needed
- Easy to query and update

**Schema**:
```python
class ProjectNote(BaseModel):
    # Existing fields...
    relations: list[str] = Field(default_factory=list)
    relation_types: dict[str, str] = Field(default_factory=dict)
    # relation_types maps note_id -> "related_to" | "depends_on" | ...
```

### D5: Feature Flags for Optional Dependencies

**Decision**: Make embedding backend optional (fastembed or API); semantic search degrades gracefully when no backend is available.

**Rationale**:
- Reduces required dependencies for basic usage (install fastembed or configure API)
- Graceful degradation if neither is available
- Clear error messages when semantic search requires installation or configuration

**Configuration**:
```yaml
notes:
  auto_extract:
    enabled: true
  semantic_search:
    enabled: false  # Requires fastembed or embedding API
  relations:
    enabled: true
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        LLMService                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  chat_stream() ──▶ NoteExtractor.extract() ──▶ save_notes()    │
│                              │                                  │
│                              ▼                                  │
│                    ┌─────────────────┐                          │
│                    │ ExtractedNote   │                          │
│                    │ - category      │                          │
│                    │ - content       │                          │
│                    │ - confidence    │                          │
│                    └─────────────────┘                          │
│                                                                 │
│  search_notes(query, semantic=True) ──▶ SemanticNoteSearch     │
│                                                 │               │
│                                                 ▼               │
│                                        LocalEmbeddingService    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ProjectNotesManager                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ProjectNote                                                     │
│  ├── id: str                                                    │
│  ├── category: NoteCategory                                     │
│  ├── title: str                                                 │
│  ├── content: str                                               │
│  ├── status: NoteStatus                                         │
│  ├── tags: list[str]                                            │
│  ├── relations: list[str]          ← NEW                        │
│  ├── relation_types: dict[str, str] ← NEW                       │
│  ├── embedding: list[float] | None  ← NEW (optional)            │
│  └── embedding_model: str | None    ← NEW (optional)            │
│                                                                 │
│  NoteRelationManager (NEW)                                       │
│  ├── add_relation(source_id, target_id, type)                   │
│  ├── remove_relation(source_id, target_id)                      │
│  └── get_related_notes(note_id, depth)                          │
│                                                                 │
│  AutoRelationDetector (NEW)                                      │
│  ├── detect_relations(note) → list[candidate]                   │
│  └── auto_link: bool                                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ContextBuilder (GSSC)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  build_context()                                                 │
│  ├── Gather: notes, messages, files                             │
│  ├── Select: priority-based filtering                           │
│  ├── Structure: format for LLM                                  │
│  └── Compress: truncate if needed                               │
│                                                                 │
│  Notes Priority: CRITICAL (never compressed)                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## File Structure

```
src/mini_coder/memory/
├── __init__.py                    # Update exports
├── project_notes.py               # Extend ProjectNote model
├── context_builder.py             # Integrate semantic search (minor)
├── note_extractor.py              # NEW: Auto-extraction
├── note_relations.py              # NEW: Relations + AutoRelationDetector
├── embeddings.py                  # NEW: LocalEmbeddingService
└── semantic_search.py             # NEW: SemanticNoteSearch

tests/memory/
├── test_project_notes.py          # Existing (extend)
├── test_extractor.py              # NEW
├── test_relations.py              # NEW
└── test_semantic_search.py        # NEW
```

## Risks / Trade-offs

### Risk 1: Embedding Model Download Size
**Risk**: Default fastembed model (e.g. BAAI/bge-small-en-v1.5) has first-time download, may slow first use.
**Mitigation**:
- Document in README
- Lazy loading - only load when semantic search is used
- Configurable `batch_size` to limit memory

### Risk 2: Extraction False Positives
**Risk**: Pattern matching may extract incorrect notes.
**Mitigation**:
- Use confidence scoring
- Tag auto-extracted notes with `["auto-extracted"]`
- Low-confidence notes get `[待确认]` prefix
- User can delete incorrect notes

### Risk 3: Relation Detection Noise
**Risk**: Auto-detection may create spurious relations.
**Mitigation**:
- Configurable threshold (default 0.75)
- Limit auto-link to top 3 candidates
- `auto_link: false` by default (just suggest)

### Risk 4: Backward Compatibility
**Risk**: New fields may break existing note files.
**Mitigation**:
- All new fields have `default_factory` or `None` defaults
- Pydantic handles missing fields gracefully
- Migration not required

## Migration Plan

### Phase 1: Core Enhancements (No Migration)
1. Add new fields to `ProjectNote` with defaults
2. Existing notes load without issues
3. New features work on new notes only

### Phase 2: Semantic Search Enablement
1. User enables `semantic_search.enabled: true`
2. On first search, build embeddings for all notes
3. Cache embeddings in note files

### Rollback Strategy
- Disable features in config
- Existing functionality unaffected
- No data migration to reverse

## Open Questions

1. **Extraction timing**: Extract after every response or batch?
   - **Resolution**: After every response, but only if content matches patterns

2. **Embedding update**: Re-embed on note edit?
   - **Resolution**: Yes, but lazy - only when semantic search is used

3. **Max notes limit**: Should there be a cap?
   - **Resolution**: Current `format_notes_for_context(max_notes=N)` handles this

4. **Relation directionality**: Should relations be bidirectional?
   - **Resolution**: Configurable per relation type, `related_to` is bidirectional by default
