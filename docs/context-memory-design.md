# Context Memory System Design

> This document records the design decisions for the context memory management system in mini-coder.

## Overview

The context memory system enables mini-coder to:
1. Automatically store and compress context
2. Retain key information across multi-turn conversations
3. Persist memory across sessions

---

## Design Decision: Two-Layer Architecture

### Options Considered

#### Option A: Three-Layer Architecture

```
┌─────────────┐
│   Short-term │  ← RAM, sliding window
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Mid-term  │  ← Vector DB (semantic search)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Long-term │  ← SQLite (exact key-value)
└─────────────┘
```

#### Option B: Two-Layer Architecture (Chosen)

```
┌────────────────────┬─────────────────────────────┐
│   Working Memory   │      Persistent Store       │
│   (RAM)            │      (Disk)                 │
├────────────────────┼─────────────────────────────┤
│ • Priority queue   │ • Chroma (vector + metadata)│
│ • Sliding window   │ • Session index             │
│ • Token counter    │ • Key facts                 │
│ • 92% compression  │ • User preferences          │
└────────────────────┴─────────────────────────────┘
```

### Decision Rationale

| Factor | Three-Layer | Two-Layer | Winner |
|--------|-------------|-----------|--------|
| Complexity | 3 systems to maintain | 2 systems to maintain | Two-Layer |
| Mid/Long boundary | Clear separation | Blurred (merged) | Two-Layer |
| Query flexibility | Need to coordinate 3 layers | Single unified query | Two-Layer |
| Implementation effort | High | Medium | Two-Layer |
| Chroma capabilities | Only vector search | Vector + metadata filtering | Two-Layer |

### Why Two-Layer is Better

1. **Mid-term and Long-term boundary is blurred**
   - Users don't distinguish "I want semantic search" vs "I want exact query"
   - Merged layer can handle both with unified interface

2. **Chroma supports both vector search and metadata filtering**
   ```python
   # Single query handles both semantic and exact matching
   collection.query(
       query_texts=["API调用"],
       where={"type": "decision"}  # Exact metadata filter
   )
   ```
   No need for separate SQLite for key-value storage

3. **Aligns with Claude's best practices**
   - Claude Code official: Simple list + external files
   - Community best practice: Working Memory + Summary Store
   - Both follow two-layer approach

4. **Easier incremental implementation**
   ```
   Phase 1: RAM + Simple JSON persistence
   Phase 2: RAM + Chroma (vector + metadata)
   Phase 3: Add compression strategy
   ```

---

## Technical Selection (with Recommendation Index)

| 技术方案 | 优势 | 劣势 | 适用场景 | 推荐指数 |
|---------|------|---------|---------|---------|
| **Chroma (向量+元数据)** | 统一存储、语义检索、嵌入式 | 依赖 embedding 模型 | 需要语义搜索 | ⭐⭐⭐ |
| **SQLite + FTS** | 轻量、成熟、全文搜索 | 无语义理解 | 精确/关键词搜索 | ⭐⭐⭐ |
| **纯 JSON 文件** | 最简单、无依赖 | 无检索能力 | 极简场景 | ⭐ |
| **Chroma + SQLite 混合** | 功能最全 | 复杂度高 | 大规模应用 | ⭐⭐ |

**推荐**: Phase 1 使用 JSON，Phase 2 根据需求决定是否引入 Chroma

---

## Comparison with Reference Projects

| 维度 | 当前方案 (两层) | Claude Code (简单列表) | aider (文件式) | 建议 |
|------|----------------|----------------------|---------------|------|
| 复杂度 | 中 | 低 | 低 | ✅ 当前方案适中 |
| 向量检索 | Chroma (可选) | 无 | 无 | ⚠️ 按需引入 |
| 跨会话持久化 | 有 | 无 | 有 | ✅ 满足需求 |
| 压缩策略 | 92%触发 | 手动 | 简单剪枝 | ✅ 自动化好 |
| **推荐** | - | - | - | **当前方案可行** |

---

## Reference: Claude's Context Management Strategy

### Key Learnings from Claude Code

| Strategy | Description |
|----------|-------------|
| **Priority-based context** | User input > Recent 3 turns > Edited files > History |
| **Progressive compression** | 8-level compression + smart merging |
| **External persistence** | CLAUDE.md, project files as long-term memory |
| **Proactive triggering** | Compress at 92% capacity, not when full |

### Priority Levels

```python
class Priority:
    HIGH = 1      # User input, system prompt
    MEDIUM = 3    # Recent 3 turns, edited files
    NORMAL = 5    # General conversation, command results
    LOW = 7       # Early history, large file content
    ARCHIVE = 9   # Completed tasks, compressible content
```

### Compression Triggers

- **Threshold**: 92% of context window
- **Strategy**: Summarize low-priority content, preserve high-priority
- **Method**: LLM-based summarization (backend-agnostic)

---

## Architecture Details

### Data Models (Pydantic)

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import IntEnum


class Priority(IntEnum):
    """Message priority levels"""
    HIGH = 1      # User input, system prompt
    MEDIUM = 3    # Recent 3 turns, edited files
    NORMAL = 5    # General conversation, command results
    LOW = 7       # Early history, large file content
    ARCHIVE = 9   # Completed tasks, compressible content


class Message(BaseModel):
    """Message data model with validation"""
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., min_length=1)
    priority: int = Field(default=Priority.NORMAL, ge=1, le=9)
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict = Field(default_factory=dict)

    class Config:
        use_enum_values = True


class Session(BaseModel):
    """Session data model"""
    id: str = Field(..., min_length=1)
    project_path: Optional[str] = None
    messages: list[Message] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def touch(self):
        """Update the updated_at timestamp"""
        self.updated_at = datetime.now()


class Summary(BaseModel):
    """Compressed summary model"""
    id: str
    original_message_ids: list[str] = Field(default_factory=list)
    content: str
    created_at: datetime = Field(default_factory=datetime.now)
    metadata: dict = Field(default_factory=dict)
```

### Component: Working Memory (RAM)

```python
from typing import List, Optional
from pathlib import Path
import json


class WorkingMemory:
    """In-memory context with priority-based management"""

    def __init__(
        self,
        max_messages: int = 20,
        compression_threshold: float = 0.92,
        token_buffer: float = 0.10  # 10% buffer for token counting errors
    ):
        self.messages: List[Message] = []
        self.max_messages = max_messages
        self.compression_threshold = compression_threshold
        self.token_buffer = token_buffer
        self._token_counter = TokenCounter()

    def add(self, message: Message) -> None:
        """Add message with priority"""
        if not message.content or not message.content.strip():
            return  # Skip empty messages

        self.messages.append(message)

        # Enforce max messages limit
        if len(self.messages) > self.max_messages:
            self._evict_low_priority()

    def get_context(self, max_tokens: int) -> List[dict]:
        """Get context within token limit, sorted by priority"""
        # Sort by priority (lower = higher priority)
        sorted_messages = sorted(self.messages, key=lambda m: m.priority)

        result = []
        current_tokens = 0
        effective_limit = max_tokens * (1 - self.token_buffer)

        for msg in sorted_messages:
            msg_tokens = self._token_counter.count(msg.content)
            if current_tokens + msg_tokens <= effective_limit:
                result.append(msg.model_dump())
                current_tokens += msg_tokens

        return result

    def should_compress(self) -> bool:
        """Check if compression is needed"""
        return self._token_counter.ratio() >= self.compression_threshold

    def get_low_priority(self) -> List[Message]:
        """Get messages eligible for compression"""
        return [m for m in self.messages if m.priority >= Priority.LOW]

    def remove_messages(self, message_ids: List[str]) -> None:
        """Remove messages by ID after compression"""
        self.messages = [m for m in self.messages if m.metadata.get("id") not in message_ids]

    def _evict_low_priority(self) -> None:
        """Evict lowest priority messages when over limit"""
        if not self.messages:
            return

        # Find and remove lowest priority message
        lowest = max(self.messages, key=lambda m: m.priority)
        self.messages.remove(lowest)
```

### Component: Persistent Store (Disk)

```python
class PersistentStore:
    """Disk-based storage with optional vector search capability"""

    def __init__(self, path: str = "~/.mini-coder/memory"):
        self.path = Path(path).expanduser()
        self.path.mkdir(parents=True, exist_ok=True)

        # JSON-based storage (Phase 1)
        self.sessions_dir = self.path / "sessions"
        self.sessions_dir.mkdir(exist_ok=True)

        # Optional: Chroma for vector search (Phase 2)
        self._chroma_client = None
        self._collection = None

    def save_session(self, session: Session) -> None:
        """Save session to disk"""
        session_file = self.sessions_dir / f"{session.id}.json"
        session_file.write_text(session.model_dump_json(indent=2), encoding="utf-8")

    def load_session(self, session_id: str) -> Optional[Session]:
        """Load session from disk"""
        session_file = self.sessions_dir / f"{session_id}.json"
        if not session_file.exists():
            return None
        return Session.model_validate_json(session_file.read_text(encoding="utf-8"))

    def list_sessions(self) -> List[str]:
        """List all saved session IDs"""
        return [f.stem for f in self.sessions_dir.glob("*.json")]

    def save_summary(self, summary: Summary) -> None:
        """Save compressed summary"""
        summaries_file = self.path / "summaries.json"
        summaries = []
        if summaries_file.exists():
            summaries = json.loads(summaries_file.read_text(encoding="utf-8"))
        summaries.append(summary.model_dump())
        summaries_file.write_text(json.dumps(summaries, indent=2, default=str), encoding="utf-8")

    # Phase 2: Vector search (optional)
    def enable_vector_search(self) -> None:
        """Enable Chroma vector search (Phase 2)"""
        try:
            import chromadb
            self._chroma_client = chromadb.PersistentClient(path=str(self.path / "chroma"))
            self._collection = self._chroma_client.get_or_create_collection("conversations")
        except ImportError:
            raise RuntimeError("chromadb not installed. Run: pip install chromadb")

    def search_similar(self, query: str, n_results: int = 5) -> List[dict]:
        """Semantic search for similar content (requires Phase 2)"""
        if not self._collection:
            raise RuntimeError("Vector search not enabled. Call enable_vector_search() first.")
        results = self._collection.query(query_texts=[query], n_results=n_results)
        return results
```

### Component: Context Memory Manager

```python
import uuid
from typing import List, Optional


class ContextMemoryManager:
    """Main interface for context management"""

    def __init__(
        self,
        max_messages: int = 20,
        compression_threshold: float = 0.92,
        storage_path: str = "~/.mini-coder/memory"
    ):
        self.working = WorkingMemory(
            max_messages=max_messages,
            compression_threshold=compression_threshold
        )
        self.persistent = PersistentStore(path=storage_path)
        self.compressor = ContextCompressor()
        self._current_session: Optional[Session] = None

    def start_session(self, project_path: str = None) -> str:
        """Start a new session"""
        session_id = str(uuid.uuid4())[:8]
        self._current_session = Session(
            id=session_id,
            project_path=project_path
        )
        return session_id

    def add_message(
        self,
        role: str,
        content: str,
        priority: int = Priority.NORMAL
    ) -> None:
        """Add message to working memory"""
        if not content or not content.strip():
            return  # Skip empty messages

        message = Message(
            role=role,
            content=content,
            priority=priority,
            metadata={"id": str(uuid.uuid4())[:8]}
        )

        self.working.add(message)

        if self._current_session:
            self._current_session.messages.append(message)
            self._current_session.touch()

        # Auto-compress if needed
        if self.working.should_compress():
            self.compress()

    def get_context(self, max_tokens: int) -> List[dict]:
        """Get context for LLM call"""
        return self.working.get_context(max_tokens)

    def compress(self) -> Optional[Summary]:
        """Compress working memory, save to persistent store"""
        low_priority = self.working.get_low_priority()
        if not low_priority:
            return None

        summary_content = self.compressor.summarize(low_priority)
        summary = Summary(
            id=str(uuid.uuid4())[:8],
            original_message_ids=[m.metadata.get("id") for m in low_priority],
            content=summary_content
        )

        self.persistent.save_summary(summary)
        self.working.remove_messages(summary.original_message_ids)

        return summary

    def save_session(self) -> None:
        """Save current session to disk"""
        if self._current_session:
            self.persistent.save_session(self._current_session)

    def load_session(self, session_id: str) -> bool:
        """Load a previous session"""
        session = self.persistent.load_session(session_id)
        if session:
            self._current_session = session
            self.working.messages = session.messages.copy()
            return True
        return False

    def list_sessions(self) -> List[str]:
        """List all saved sessions"""
        return self.persistent.list_sessions()
```

---

## Boundary Conditions

| 边界条件 | 风险 | 处理策略 |
|---------|------|---------|
| **并发访问** | 多会话同时写入 | 文件锁或队列机制 |
| **空值消息** | content 为空 | Pydantic 验证 + 显式检查 |
| **Token 计数误差** | 估算值与实际偏差 | 10% 缓冲区 (token_buffer) |
| **磁盘空间增长** | Chroma/JSON 持续增长 | 定期清理 + 最大保留数 |
| **Embedding 模型** | 默认模型不适合中文 | Phase 2 按需选型 |

---

## Storage Structure

```
~/.mini-coder/
├── memory/
│   ├── sessions/
│   │   └── {session_id}.json      # Session records
│   ├── summaries.json              # Compressed summaries
│   ├── chroma/                     # Vector DB (Phase 2, optional)
│   │   └── ...
│   └── config.yaml                 # Memory configuration
└── config.yaml                     # Main configuration
```

---

## Implementation Roadmap (Simplified)

### Phase 1: Core Memory System

- [ ] Implement `Message`, `Session`, `Summary` Pydantic models
- [ ] Implement `WorkingMemory` with priority queue
- [ ] Implement `PersistentStore` with JSON storage
- [ ] Implement `ContextMemoryManager` main interface
- [ ] Add token counting with 10% buffer
- [ ] Add basic compression trigger (92% threshold)

### Phase 2: Enhanced Features (Optional)

- [ ] Integrate Chroma for vector search (if needed)
- [ ] Implement LLM-based summarization
- [ ] Add session restoration on startup
- [ ] Project-level memory (CLAUDE.md integration)

---

## Future Optimizations (Backend-Specific)

The following optimizations are deferred to keep the initial implementation generic:

### ZHIPU AI Specific (Future)

| Optimization | Purpose | Benefit |
|--------------|---------|---------|
| ZHIPU Embedding API | Use ZHIPU's embedding model | Better Chinese semantic understanding |
| GLM long-text optimization | Optimize for GLM model | More efficient token usage |
| reasoning_content | Extract reasoning process | Access to model's thinking |

### Other Backend Optimizations (Future)

| Backend | Optimization | Purpose |
|---------|--------------|---------|
| Anthropic | Claude 4.6 1M context | Larger context window |
| OpenAI | GPT-4 Turbo caching | Reduce costs |

---

## References

- [Claude Code Context Management](https://github.com/anthropics/claude-code)
- [Anthropic Context Best Practices](https://docs.anthropic.com/claude/docs/context-basics)
- [Chroma Documentation](https://docs.trychroma.com/)
- [LangChain Memory Patterns](https://python.langchain.com/docs/modules/memory/)
- [Pydantic V2 Documentation](https://docs.pydantic.dev/)

---

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2026-03-02 | Initial design document | Claude |
| 2026-03-02 | Added Architectural Consultant review | Claude |
| 2026-03-02 | Simplified implementation roadmap | Claude |
| 2026-03-02 | Added Pydantic models and boundary conditions | Claude |
