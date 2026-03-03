# Design: Context Memory System

## Context

### Background

mini-coder is a TUI-based coding assistant that uses LLM services for intelligent code generation and debugging. Currently, each conversation session starts fresh with no memory of previous interactions, leading to:

- Repetitive explanations of project context
- Loss of important decisions and preferences
- Inefficient token usage in long conversations
- No cross-session continuity

### Current State

```
┌─────────────────────────────────────────┐
│           Current Architecture          │
├─────────────────────────────────────────┤
│                                         │
│  TUI ──→ LLM Service ──→ LLM Provider  │
│            │                            │
│            ▼                            │
│     Simple list                        │
│     (lost on exit)                     │
│                                         │
└─────────────────────────────────────────┘
```

### Constraints

- Must work with existing LLM service abstraction
- Must not significantly impact response latency
- Must be transparent to TUI layer
- Must support multiple LLM backends (ZHIPU, Anthropic, OpenAI)

### Stakeholders

- End users: Expect seamless conversation continuity
- Developers: Need clear APIs and extensibility
- System: Requires efficient resource usage

## Goals / Non-Goals

### Goals

1. **Persistent Memory**: Save and restore conversation context across sessions
2. **Smart Compression**: Automatically compress context when approaching token limits
3. **Priority Management**: Preserve important messages over less relevant ones
4. **Natural Integration**: Context injection should be transparent to users
5. **Backend Agnostic**: Work with any LLM provider

### Non-Goals

1. **Vector Search (Phase 1)**: Chroma integration deferred to Phase 2
2. **Multi-project Memory**: Each project has isolated memory (no cross-project)
3. **Cloud Sync**: Local-only storage, no cloud backup
4. **Real-time Collaboration**: Single-user sessions only
5. **Backend-specific Optimization**: ZHIPU/Anthropic specific features deferred

## Decisions

### Decision 1: Two-Layer Architecture

**Chosen**: Working Memory (RAM) + Persistent Store (Disk)

**Alternatives Considered**:

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Three-Layer (Short/Mid/Long) | Clear separation | Complex, over-engineered | Rejected |
| Two-Layer (Working/Persistent) | Simple, sufficient | Blurred mid/long boundary | **Chosen** |
| Single-Layer (File only) | Simplest | Poor performance | Rejected |

**Rationale**: Two-layer provides the right balance of simplicity and functionality. Chroma supports both vector search and metadata filtering, eliminating the need for a separate SQLite layer.

### Decision 2: Priority-Based Context Management

**Chosen**: 5-level priority system (HIGH=1 to ARCHIVE=9)

**Alternatives Considered**:

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| FIFO Queue | Simple | Loses important messages | Rejected |
| LRU Cache | Common pattern | No semantic understanding | Rejected |
| Priority Queue | Preserves important content | Requires priority assignment | **Chosen** |
| ML-based Importance | Intelligent | Complex, unreliable | Rejected |

**Rationale**: Priority-based approach gives explicit control over what to preserve. Based on Claude Code's best practices.

### Decision 3: GSSC Pipeline for Context Building

**Chosen**: Gather → Select → Structure → Compress pipeline

**Alternatives Considered**:

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Direct Injection | Simple | No optimization | Rejected |
| GSSC Pipeline | Structured, optimized | More code | **Chosen** |
| Template-based | Predictable | Inflexible | Rejected |

**Rationale**: GSSC pipeline is used by OpenCode and HelloAgents, proven effective for context management.

### Decision 4: Integration Point - LLM Service Layer

**Chosen**: Integrate at LLM service layer, transparent to TUI

**Alternatives Considered**:

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| TUI Layer | User visible | Tight coupling | Rejected |
| LLM Service Layer | Transparent, clean API | Hidden from user | **Chosen** |
| Provider Layer | Provider-specific optimization | Code duplication | Rejected |

**Rationale**: LLM service layer is the natural integration point - all conversations pass through it.

### Decision 5: Storage Format

**Chosen**: JSON files for sessions, optional Chroma for vectors

**Alternatives Considered**:

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| SQLite | Structured queries | Overkill for simple data | Rejected |
| JSON Files | Simple, human-readable | No indexing | **Chosen** (Phase 1) |
| Chroma Only | Unified storage | Requires embedding model | Rejected (Phase 1) |

**Rationale**: JSON is sufficient for Phase 1. Chroma can be added later for semantic search.

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    mini-coder System                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐     ┌─────────────────────────────────┐   │
│  │     TUI     │────→│          LLM Service            │   │
│  └─────────────┘     │                                 │   │
│                      │  ┌───────────────────────────┐  │   │
│                      │  │    ContextMemoryManager   │  │   │
│                      │  │                           │  │   │
│                      │  │  ┌─────────────────────┐  │  │   │
│                      │  │  │   ContextBuilder    │  │  │   │
│                      │  │  │   (GSSC Pipeline)   │  │  │   │
│                      │  │  └──────────┬──────────┘  │  │   │
│                      │  │             │             │  │   │
│                      │  │  ┌──────────┴──────────┐  │  │   │
│                      │  │  │                     │  │  │   │
│                      │  │  ▼                     ▼  │  │   │
│                      │  │ ┌─────────┐     ┌─────────┐│  │   │
│                      │  │ │ Working │     │Persistent││  │   │
│                      │  │ │ Memory  │     │  Store  ││  │   │
│                      │  │ │  (RAM)  │     │ (Disk)  ││  │   │
│                      │  │ └─────────┘     └─────────┘│  │   │
│                      │  └───────────────────────────┘  │   │
│                      └─────────────────────────────────┘   │
│                                    │                        │
│                                    ▼                        │
│                           ┌─────────────┐                  │
│                           │ LLM Provider│                  │
│                           │ (OpenAI API)│                  │
│                           └─────────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
1. User Input Flow:
   User → TUI → LLMService.chat()
                    │
                    ▼
              ContextManager.add_message()
                    │
                    ▼
              WorkingMemory.add(priority=NORMAL)
                    │
                    ▼ (if should_compress)
              ContextManager.compress()
                    │
                    ▼
              PersistentStore.save_summary()

2. LLM Call Flow:
   LLMService.chat()
        │
        ▼
   ContextBuilder.build(max_tokens)
        │
        ├── Gather: working_memory + persistent_store
        ├── Select: filter by priority and tokens
        ├── Structure: format for LLM
        └── Compress: optimize token usage
        │
        ▼
   LLM Provider call with context
```

### Module Structure

```
src/mini_coder/memory/
├── __init__.py              # Public API exports
├── models.py                # Pydantic models (Message, Session, Summary)
├── priority.py              # Priority enum and helpers
├── working_memory.py        # WorkingMemory class
├── persistent_store.py      # PersistentStore class
├── manager.py               # ContextMemoryManager class
├── context_builder.py       # GSSC pipeline implementation
├── compressor.py            # Compression strategies
└── token_counter.py         # Token counting utilities
```

### API Design

```python
# Main interface
class ContextMemoryManager:
    def __init__(self, config: MemoryConfig): ...
    def start_session(self, project_path: str = None) -> str: ...
    def add_message(self, role: str, content: str, priority: int = 5) -> None: ...
    def get_context(self, max_tokens: int) -> list[dict]: ...
    def compress(self) -> Summary | None: ...
    def save_session(self) -> None: ...
    def load_session(self, session_id: str) -> bool: ...
    def list_sessions(self) -> list[str]: ...

# Integration with LLM service
class LLMService:
    def __init__(self, config_path: str):
        # ... existing init ...
        self._context_manager = ContextMemoryManager(config)

    def chat(self, message: str) -> str:
        # Add user message to context
        self._context_manager.add_message("user", message, priority=Priority.HIGH)

        # Build context for LLM
        context = self._context_manager.get_context(max_tokens=self._max_tokens)

        # Call LLM with context
        response = self.provider.send_message(context)

        # Add assistant response to context
        self._context_manager.add_message("assistant", response, priority=Priority.MEDIUM)

        return response
```

## Risks / Trade-offs

### Risk 1: Token Counting Accuracy

**Risk**: Estimated token count differs from actual LLM token usage.

**Mitigation**:
- Use 10% buffer in token calculations
- Support multiple tokenizers (tiktoken, HuggingFace)
- Log warnings when estimates are off by >20%

### Risk 2: Compression Quality

**Risk**: LLM-based summarization may lose important details.

**Mitigation**:
- Always preserve HIGH priority messages
- Store original messages in persistent store before compression
- Allow users to view compression history

### Risk 3: Performance Impact

**Risk**: Context management adds latency to each LLM call.

**Mitigation**:
- Working memory operations are O(1) or O(n) where n is small
- Persistent store operations are async where possible
- Cache frequently accessed data

### Risk 4: Disk Space Growth

**Risk**: Persistent storage grows unbounded over time.

**Mitigation**:
- Implement max_history limit (default: 1000 summaries)
- Add cleanup job for old sessions
- Provide user command to clear memory

### Risk 5: Concurrent Access

**Risk**: Multiple mini-coder instances accessing same storage.

**Mitigation**:
- Use file locks for session files
- Each instance has unique session ID
- Document single-instance limitation

## Migration Plan

### Phase 1: Core Implementation

1. Create `memory/` module with core classes
2. Add `MemoryConfig` to `config/memory.yaml`
3. Integrate `ContextMemoryManager` into `LLMService`
4. Add session save/restore hooks to TUI

### Phase 2: Enhanced Features (Optional)

1. Add Chroma integration for vector search
2. Implement LLM-based compression
3. Add CLAUDE.md project memory integration

### Rollback Strategy

- Feature is additive, no breaking changes
- Can disable via config: `memory.enabled: false`
- Existing LLM service works without memory

## Open Questions

1. **Compression Trigger**: Should compression be time-based or token-based?
   - Current decision: Token-based (92% threshold)
   - Alternative: Time-based (every N minutes)

2. **Session Identification**: How to identify sessions across restarts?
   - Current decision: UUID stored in memory dir
   - Alternative: Project path hash

3. **Priority Assignment**: Should priorities be user-adjustable?
   - Current decision: System-assigned based on role
   - Alternative: Allow user override via command

4. **Embedding Model**: Which embedding model for Phase 2?
   - Current decision: Defer to Phase 2
   - Options: ZHIPU embedding, OpenAI embedding, local model

---

## Enhancement: Hybrid Compression Strategy (Plan B)

### Overview

Based on analysis of OpenCode's memory management and our existing priority-based system, we propose a **Hybrid Compression Strategy** that combines the best of both approaches:

- **OpenCode**: Token-based triggering, tool output pruning, message-level summaries
- **mini-coder (Plan A)**: Priority system, time-based degradation, simple summaries

### Core Components

```
┌────────────────────────────────────────────────────────────────┐
│                   Hybrid Compression Strategy                   │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  1. Token Management                     │   │
│  │  - max_context_tokens: 128000                            │   │
│  │  - reserved_tokens: 20000 (for LLM output)               │   │
│  │  - Trigger: current_tokens >= (max - reserved)           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  2. Tool Output Pruning                  │   │
│  │  - prune_threshold: 40000 tokens                         │   │
│  │  - prune_minimum: 20000 tokens (must delete this much)   │   │
│  │  - Protected tools: ["skill*", "file*", "search*"]       │   │
│  │  - Preserve: recent 2 turns                              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  3. Priority-Based Compression           │   │
│  │  Priority Levels (lower = higher priority):              │   │
│  │  - CRITICAL (0): System prompts, never compressed        │   │
│  │  - HIGH (1): Recent user input (last 2 turns)            │   │
│  │  - MEDIUM (2): Recent assistant responses                │   │
│  │  - NORMAL (4): Older conversation (3-6 turns)            │   │
│  │  - LOW (6): Old history (7+ turns)                       │   │
│  │  - ARCHIVE (8): Very old content                         │   │
│  │                                                          │   │
│  │  Compressible range: priority >= NORMAL (4)              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  4. Message-Level Summaries              │   │
│  │  - files_read: List of files accessed                    │   │
│  │  - files_modified: List of files changed                 │   │
│  │  - additions/deletions: Line change counts               │   │
│  │  - tools_used: Tools invoked in this turn                │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

### Configuration

```python
class MemoryConfig(BaseModel):
    """Enhanced memory configuration for Plan B."""

    # Basic settings
    enabled: bool = True
    storage_path: str = "~/.mini-coder/memory"
    max_history: int = 1000

    # Token management (from OpenCode)
    max_context_tokens: int = 128000
    reserved_tokens: int = 20000      # Reserved for LLM output

    # Pruning settings (from OpenCode)
    prune_threshold: int = 40000      # Start pruning at this many tokens
    prune_minimum: int = 20000        # Minimum tokens to prune
    prune_protected_tools: list[str] = ["skill", "file", "search"]

    # Compression settings (hybrid)
    compression_threshold: float = 0.92  # Fallback: percentage-based trigger
    preserve_recent_turns: int = 2       # Preserve last N user turns

    # Message summaries
    enable_message_summaries: bool = True
```

### Compression Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Compression Flow                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  should_compress()?                                              │
│       │                                                          │
│       ├── No ──▶ Return (no action needed)                       │
│       │                                                          │
│       └── Yes ──▶                                                │
│              │                                                   │
│              ▼                                                   │
│       ┌─────────────────┐                                        │
│       │ 1. Prune Tool   │  Low cost, high impact                 │
│       │    Outputs      │  - Delete old tool call results        │
│       └────────┬────────┘  - Protect recent turns                │
│                │           - Protect specific tool types         │
│                ▼                                                 │
│       should_compress()?                                         │
│              │                                                   │
│              ├── No ──▶ Return (pruning was sufficient)          │
│              │                                                   │
│              └── Yes ──▶                                         │
│                     │                                            │
│                     ▼                                            │
│              ┌─────────────────┐                                 │
│              │ 2. Priority     │  Medium cost, intelligent       │
│              │    Compression  │  - Get compressible messages    │
│              └────────┬────────┘  - Create structured summary    │
│                       │           - Remove from working memory   │
│                       ▼                                          │
│              ┌─────────────────┐                                 │
│              │ 3. Summary      │  Cache for context inclusion    │
│              │    Caching      │  - Store in _summaries list     │
│              └────────┬────────┘  - Include in future context    │
│                       │                                          │
│                       ▼                                          │
│                    Return Summary                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Token Calculation

```python
def should_compress(self) -> bool:
    """Check if compression is needed based on token usage."""
    current_tokens = self._token_counter.total()
    usable_tokens = self._config.max_context_tokens - self._config.reserved_tokens
    return current_tokens >= usable_tokens

def get_context(self, max_tokens: int) -> list[dict]:
    """Build context respecting token limits."""
    effective_limit = int(max_tokens * 0.9)  # 10% buffer
    current_tokens = 0
    result = []

    # 1. Add summaries first (high value, low token cost)
    if self._summaries:
        summary_text = self._format_summaries()
        summary_tokens = self._token_counter.count(summary_text)
        if current_tokens + summary_tokens <= effective_limit:
            result.append({"role": "system", "content": summary_text})
            current_tokens += summary_tokens

    # 2. Add high-priority messages
    for msg in self._get_high_priority_messages():
        msg_tokens = self._token_counter.count(msg.content)
        if current_tokens + msg_tokens <= effective_limit:
            result.append(msg.model_dump())
            current_tokens += msg_tokens

    # 3. Add remaining messages by priority
    for msg in self._get_remaining_messages():
        msg_tokens = self._token_counter.count(msg.content)
        if current_tokens + msg_tokens <= effective_limit:
            result.append(msg.model_dump())
            current_tokens += msg_tokens

    return sorted(result, key=lambda m: m.get("timestamp", ""))
```

### Tool Output Pruning

```python
PROTECTED_TOOLS = {"skill", "file_read", "file_write", "search"}

def prune_tool_outputs(self) -> int:
    """Remove old tool outputs to free tokens.

    Returns:
        Number of tokens freed.
    """
    messages = self._working.messages
    total_tokens = 0
    to_prune = []

    # Scan from oldest to newest, but skip recent turns
    protected_count = self._config.preserve_recent_turns * 2  # user + assistant
    scan_range = messages[:-protected_count] if len(messages) > protected_count else []

    for msg in scan_range:
        tool_name = msg.metadata.get("tool_name")

        # Skip protected tools
        if tool_name and any(p in tool_name for p in self._config.prune_protected_tools):
            continue

        # Check if this is a tool output
        if msg.metadata.get("is_tool_output"):
            msg_tokens = self._token_counter.count(msg.content)
            total_tokens += msg_tokens
            to_prune.append(msg)

            if total_tokens >= self._config.prune_threshold:
                break

    # Only prune if we have enough to make it worthwhile
    if total_tokens >= self._config.prune_minimum:
        for msg in to_prune:
            self._working.remove(msg.id)
        return total_tokens

    return 0
```

### Message-Level Summary

```python
class MessageSummary(BaseModel):
    """Summary metadata for a conversation turn."""

    files_read: list[str] = []
    files_modified: list[str] = []
    additions: int = 0
    deletions: int = 0
    tools_used: list[str] = []
    key_points: list[str] = []  # Optional: extracted key information

def summarize_turn(self, user_msg: Message, assistant_msg: Message) -> MessageSummary:
    """Create a summary for a conversation turn."""
    summary = MessageSummary()

    # Extract file operations from content
    content = user_msg.content + assistant_msg.content

    # Find file references
    import re
    file_pattern = r'[\w/\-\.]+\.\w+'
    summary.files_read = list(set(re.findall(file_pattern, content)))

    # Find tool usage from metadata
    summary.tools_used = assistant_msg.metadata.get("tools_used", [])

    # Count code changes (if patch data available)
    patch_data = assistant_msg.metadata.get("patch")
    if patch_data:
        summary.files_modified = [p["file"] for p in patch_data]
        summary.additions = sum(p.get("additions", 0) for p in patch_data)
        summary.deletions = sum(p.get("deletions", 0) for p in patch_data)

    return summary
```

### Priority Degradation

Messages degrade in priority as they age:

```python
def calculate_priority_by_age(
    base_priority: int,
    turns_ago: int,
    preserve_recent_turns: int = 4
) -> int:
    """Calculate adjusted priority based on message age.

    System messages (CRITICAL) never degrade.
    Recent messages (within preserve_recent_turns) keep their priority.
    Older messages degrade progressively.
    """
    if base_priority == Priority.CRITICAL:
        return Priority.CRITICAL

    if turns_ago < preserve_recent_turns:
        return base_priority

    if turns_ago < preserve_recent_turns + 4:
        return Priority.NORMAL  # 4-8 turns ago

    if turns_ago < preserve_recent_turns + 8:
        return Priority.LOW  # 8-12 turns ago

    return Priority.ARCHIVE  # 12+ turns ago
```

### GSSC Integration (Minimal Change)

The compression is integrated into the GSSC pipeline with minimal changes:

```python
# LLMService.chat_stream() - Enhanced with pre-check

async def chat_stream(self, message: str, **kwargs):
    """GSSC pipeline with memory management."""

    # 1. Validate
    is_valid, processed = self._validate_input(message)
    if not is_valid:
        yield {"type": "error", "content": processed}
        return

    # 2. Pre-check: Compress if needed (NEW)
    if self._context_manager and self._context_manager.should_compress():
        # Try pruning first (low cost)
        pruned = self._context_manager.prune_tool_outputs()

        # If still over limit, do full compression
        if self._context_manager.should_compress():
            summary = self._context_manager.compress()
            if summary:
                yield {"type": "system", "content": f"[压缩了 {len(summary.original_message_ids)} 条消息]"}

    # 3. Add user message
    if self._context_manager:
        self._context_manager.add_message("user", processed)

    # 4. Stream response
    full_response = ""
    async for chunk in self.provider.send_message_stream(processed, **kwargs):
        if chunk.get("type") == "delta":
            full_response += chunk.get("content", "")
        yield chunk

    # 5. Add assistant response
    if self._context_manager and full_response:
        self._context_manager.add_message("assistant", full_response)
```

### Comparison: Plan A vs Plan B

| Feature | Plan A (Original) | Plan B (Hybrid) |
|---------|------------------|-----------------|
| **Trigger** | Fixed ratio (92%) | Token-based with buffer |
| **Compression** | Priority only | Pruning + Priority |
| **Summary Quality** | Simple truncation | Structured with metadata |
| **Protection** | Priority levels | Priority + Turn count + Tool type |
| **LLM Dependency** | None | None (optional for key extraction) |
| **Complexity** | Low | Medium |
| **Effectiveness** | Basic | High |

### Implementation Checklist

- [x] Priority system with degradation (CRITICAL=0 to ARCHIVE=8)
- [x] Token-based compression trigger
- [x] Tool output pruning
- [x] Message-level summaries with metadata
- [x] Summary caching and context inclusion
- [x] GSSC pre-check integration
- [x] ContextBuilder integrated with Plan B compression
- [x] LLMService uses ContextBuilder for GSSC pipeline
- [x] Provider.send_with_context() for external message lists
- [x] Project Notes system (NoteTool-like functionality)
- [ ] Enhanced token counting (tiktoken integration)
- [ ] File diff tracking in summaries
- [ ] Compression statistics and logging

---

## NoteTool Integration: Project Notes System

### Overview

The Project Notes system provides NoteTool-like functionality for managing structured project information that persists across sessions. Unlike conversation messages which get compressed and eventually discarded, project notes are long-lived and explicitly managed.

### Key Distinction

```
┌─────────────────────────────────────────────────────────────────┐
│               Memory vs Notes Architecture                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Conversation Memory (Ephemeral)                                │
│  ├── Working Memory (RAM)                                       │
│  │   └── Recent messages (compressed over time)                 │
│  ├── Summaries (Compressed)                                     │
│  │   └── Condensed history                                      │
│  └── Session-based (per conversation)                           │
│                                                                  │
│  Project Notes (Persistent)                                     │
│  ├── Decisions (Architecture choices)                           │
│  ├── Todos (Active tasks)                                       │
│  ├── Patterns (Code conventions)                                │
│  ├── Info (Important knowledge)                                 │
│  ├── Blocks (Issues/blockers)                                   │
│  └── Project-based (per project)                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Note Categories

| Category | Emoji | Description | Example |
|----------|-------|-------------|---------|
| `decision` | 🎯 | Architecture/design decisions | "Use PostgreSQL for primary DB" |
| `todo` | 📝 | Active tasks and pending work | "Add unit tests for auth module" |
| `pattern` | 🔄 | Code patterns and conventions | "Use repository pattern for data access" |
| `info` | ℹ️ | Important project information | "API rate limit is 100 req/min" |
| `block` | 🚫 | Blockers and issues | "CORS issue with production API" |

### Data Model

```python
class ProjectNote(BaseModel):
    id: str
    category: str           # decision, todo, pattern, info, block
    title: str              # Short title
    content: str            # Full content (Markdown supported)
    status: int             # ACTIVE=0, COMPLETED=1, ARCHIVED=2, RESOLVED=3
    tags: list[str]         # Organization tags
    project_path: str       # Associated project
    created_at: datetime
    updated_at: datetime
    metadata: dict          # Additional data
```

### API Usage

```python
from mini_coder.memory import ProjectNotesManager, NoteCategory

# Initialize manager
manager = ProjectNotesManager()
manager.set_project("/home/user/my-project")

# Add notes
decision = manager.add_note(
    category=NoteCategory.DECISION,
    title="Use FastAPI",
    content="Chose FastAPI over Flask for async support",
    tags=["architecture", "backend"]
)

todo = manager.add_note(
    category=NoteCategory.TODO,
    title="Add authentication",
    content="Implement JWT-based authentication"
)

# Query notes
todos = manager.get_notes(category=NoteCategory.TODO)
results = manager.search_notes("FastAPI")

# Update notes
manager.complete_note(todo.id)  # Mark todo as completed

# Format for context (injected into LLM calls)
context = manager.format_notes_for_context(max_notes=10, max_tokens=1500)
```

### LLMService Integration

```python
from mini_coder.llm.service import LLMService

service = LLMService(config_path, enable_memory=True, enable_notes=True)
service.start_session("/home/user/my-project")

# Convenience methods
service.add_decision("Database choice", "Use PostgreSQL for reliability")
service.add_todo("Write tests", "Add unit tests for core module")
service.add_pattern("Error handling", "Use custom exceptions")

# List and search
todos = service.list_notes(category="todo")
results = service.search_notes("PostgreSQL")

# Complete/resolve
service.complete_todo(todo_id)
service.resolve_block(blocker_id)

# Stats
stats = service.get_notes_stats()
# {"total": 5, "active": 4, "by_category": {"todo": 2, "decision": 2, "info": 1}}
```

### Context Integration

Notes are automatically included in LLM context via ContextBuilder:

```python
class ContextBuilder:
    def _gather(self, ...):
        # 1. Project notes (highest priority, NoteTool integration)
        if self._notes_manager:
            notes_content = self._format_project_notes()
            messages.append({
                "role": "system",
                "content": notes_content,
                "priority": Priority.CRITICAL  # Never compressed
            })

        # 2. Cached summaries
        # 3. Working memory
        # 4. Project memory (CLAUDE.md)
```

### Storage

Notes are stored per-project in JSON format:

```
~/.mini-coder/notes/
├── _home_user_project-a.json
├── _home_user_project-b.json
└── global.json              # Notes without project context
```

### Design Decisions

1. **Separate from Conversation Memory**
   - Notes are explicit user actions, not automatic
   - Notes never get compressed or discarded
   - Clear distinction between ephemeral dialogue and persistent knowledge

2. **Project-Scoped**
   - Each project has isolated notes
   - Switching projects loads different notes
   - Prevents cross-contamination

3. **Structured Categories**
   - Predefined categories for consistency
   - Status tracking (active/completed/archived)
   - Tagging for flexible organization

4. **Context Priority**
   - Notes injected at CRITICAL priority
   - Always included in context (within token limits)
   - Formatted for easy LLM consumption

### Comparison with HelloAgents NoteTool

| Feature | HelloAgents NoteTool | mini-coder Project Notes |
|---------|---------------------|-------------------------|
| Format | Markdown + YAML | Markdown in content field |
| Persistence | File-based | JSON storage |
| Categories | Flexible | Predefined (5 types) |
| Status Tracking | Manual | Built-in (4 states) |
| Context Integration | Manual injection | Automatic via ContextBuilder |
| Project Scoping | Manual | Automatic by project path |

