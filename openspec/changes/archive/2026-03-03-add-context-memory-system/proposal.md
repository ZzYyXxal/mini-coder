# Proposal: Context Memory System

## Why

mini-coder currently lacks persistent context management, causing loss of important information across sessions and inefficient token usage during long conversations. Users cannot resume previous work context or retrieve relevant past discussions, limiting productivity for complex multi-session development tasks.

## What Changes

### New Features
- **Two-layer memory architecture**: Working Memory (RAM) + Persistent Store (Disk)
- **Priority-based context management**: Messages ranked by importance (user input > recent turns > history)
- **Automatic compression**: Triggers at 92% context capacity, preserves high-priority content
- **Cross-session persistence**: Session state saved to disk, restorable on startup
- **Natural context injection**: Context automatically built and injected into LLM calls

### Architecture Integration
- Context memory integrated into LLM service layer
- Transparent to TUI - works automatically during conversations
- Optional vector search (Chroma) for semantic retrieval

## Capabilities

### New Capabilities

- `context-memory`: Core memory management with working/persistent storage, priority queue, compression, and session persistence
- `context-builder`: GSSC pipeline (Gather-Select-Structure-Compress) for building context from multiple sources before LLM calls

### Modified Capabilities

- `llm-service`: Integrate context memory into chat flow, auto-inject context into messages

## Impact

### Code Changes
- `src/mini_coder/memory/` - New module for context memory system
  - `models.py` - Pydantic data models (Message, Session, Summary)
  - `working_memory.py` - RAM-based priority queue
  - `persistent_store.py` - Disk storage with optional Chroma
  - `manager.py` - Main ContextMemoryManager interface
  - `context_builder.py` - GSSC pipeline implementation
- `src/mini_coder/llm/service.py` - Integrate context manager
- `src/mini_coder/tui/console_app.py` - Session save/restore hooks

### Dependencies
- `chromadb` (optional, for Phase 2 vector search)
- `pydantic` (already in use)

### Configuration
- `config/memory.yaml` - Memory system configuration
- `~/.mini-coder/memory/` - User-level persistent storage

### Reference Architecture

Based on analysis of Claude Code, OpenCode, aider, and HelloAgents:

```
┌─────────────────────────────────────────────────────────────┐
│                    Conversation Flow                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  User Input ──→ TUI ──→ ContextBuilder ──→ LLM Service     │
│                              │                              │
│                              ▼                              │
│                    ┌─────────────────┐                      │
│                    │ Context Manager │                      │
│                    └────────┬────────┘                      │
│              ┌──────────────┼──────────────┐               │
│              ▼              ▼              ▼               │
│       ┌───────────┐  ┌───────────┐  ┌───────────┐         │
│       │  Working  │  │ Persistent│  │  Project  │         │
│       │  Memory   │  │   Store   │  │  Memory   │         │
│       │   (RAM)   │  │  (Disk)   │  │ (CLAUDE.md)│         │
│       └───────────┘  └───────────┘  └───────────┘         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### GSSC Pipeline (Context Builder)

```
Gather ──→ Select ──→ Structure ──→ Compress
   │          │           │            │
   ▼          ▼           ▼            ▼
Sources    Filter      Format      Optimize
- History  by priority  for LLM    tokens
- Files    by tokens
- Tools
```
