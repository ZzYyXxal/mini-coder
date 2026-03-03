# Tasks: Context Memory System

## 1. Setup and Data Models

- [x] 1.1 Create `src/mini_coder/memory/` module directory structure
- [x] 1.2 Implement `models.py` with Pydantic models (Message, Session, Summary)
- [x] 1.3 Implement `priority.py` with Priority enum
- [x] 1.4 Add unit tests for Pydantic models validation
- [x] 1.5 Create `config/memory.yaml` configuration file

## 2. Token Counter

- [x] 2.1 Implement `token_counter.py` with basic token estimation
- [x] 2.2 Add tokenizer interface for future extensibility
- [x] 2.3 Implement token ratio calculation
- [x] 2.4 Add unit tests for token counting

## 3. Working Memory

- [x] 3.1 Implement `working_memory.py` with WorkingMemory class
- [x] 3.2 Add message storage with priority queue
- [x] 3.3 Implement eviction of low priority messages
- [x] 3.4 Implement get_context with token limit respect
- [x] 3.5 Add 10% buffer for token counting errors
- [x] 3.6 Add unit tests for WorkingMemory

## 4. Persistent Store

- [x] 4.1 Implement `persistent_store.py` with PersistentStore class
- [x] 4.2 Implement session save/load with JSON files
- [x] 4.3 Implement summary storage
- [x] 4.4 Implement list_sessions functionality
- [x] 4.5 Add unit tests for PersistentStore

## 5. Context Manager

- [x] 5.1 Implement `manager.py` with ContextMemoryManager class
- [x] 5.2 Integrate WorkingMemory and PersistentStore
- [x] 5.3 Implement session lifecycle (start, save, load)
- [x] 5.4 Implement add_message with auto-compression check
- [x] 5.5 Implement compress method
- [x] 5.6 Add unit tests for ContextMemoryManager

## 6. Context Builder

- [x] 6.1 Implement `context_builder.py` with GSSC pipeline
- [x] 6.2 Implement Gather phase (collect from sources)
- [x] 6.3 Implement Select phase (filter by priority/tokens)
- [x] 6.4 Implement Structure phase (format for LLM)
- [x] 6.5 Implement Compress phase (optimize tokens)
- [x] 6.6 Add unit tests for ContextBuilder

## 7. LLM Service Integration

- [x] 7.1 Update `src/mini_coder/llm/service.py` to integrate ContextMemoryManager
- [x] 7.2 Update chat method to use context
- [x] 7.3 Update chat_stream method to use context
- [x] 7.4 Add session management methods to LLM service
- [x] 7.5 Add integration tests for LLM service with context

## 8. TUI Integration

- [x] 8.1 Update `src/mini_coder/tui/console_app.py` for session management
- [x] 8.2 Add session save on exit
- [x] 8.3 Add session restore on startup (optional)
- [x] 8.4 Add commands for session management (/memory, /sessions)
- [x] 8.5 Add integration tests for TUI with context

## 9. Documentation and Polish

- [x] 9.1 Update CLAUDE.md with context memory documentation
- [x] 9.2 Add docstrings to all public APIs
- [x] 9.3 Ensure >= 80% test coverage
- [x] 9.4 Run mypy type checking and fix issues
- [x] 9.5 Run linting and fix issues

## 10. Phase 2 Preparation (Optional)

- [x] 10.1 Add Chroma dependency to requirements.txt (optional)
- [ ] 10.2 Implement vector search in PersistentStore (optional)
- [ ] 10.3 Add embedding model configuration (optional)

## 11. Project Notes System (NoteTool-like)

- [x] 11.1 Create `project_notes.py` with ProjectNote and ProjectNotesManager models
- [x] 11.2 Implement note categories (decision, todo, pattern, info, block)
- [x] 11.3 Implement note status management (active, completed, archived, resolved)
- [x] 11.4 Implement per-project storage and persistence
- [x] 11.5 Add note management methods to LLMService
- [x] 11.6 Integrate ProjectNotesManager with ContextBuilder
- [x] 11.7 Add unit tests for ProjectNotes functionality
- [x] 11.8 Update design.md with NoteTool integration documentation
