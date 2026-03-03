"""Context Memory System for mini-coder.

This module provides a two-layer memory architecture for managing
conversation context across sessions.

Architecture:
    Working Memory (RAM) + Persistent Store (Disk) + Project Notes

Key Components:
    - ContextMemoryManager: Main interface for context management
    - WorkingMemory: In-memory message storage with priority-based eviction
    - PersistentStore: Disk-based session and summary storage
    - ContextBuilder: GSSC pipeline for building context
    - ProjectNotesManager: Structured project notes (NoteTool-like)

Example:
    >>> from mini_coder.memory import ContextMemoryManager, MemoryConfig
    >>> config = MemoryConfig(max_messages=20, compression_threshold=0.92)
    >>> manager = ContextMemoryManager(config)
    >>> session_id = manager.start_session("/path/to/project")
    >>> manager.add_message("user", "Hello!")
    >>> context = manager.get_context(max_tokens=4000)
    >>> manager.save_session()
"""

from .models import Message, MemoryConfig, Session, Summary, MessageSummary
from .priority import Priority, get_default_priority, is_high_priority, is_compressible
from .token_counter import TokenCounter, ApproximateTokenizer
from .working_memory import WorkingMemory
from .persistent_store import PersistentStore
from .manager import ContextMemoryManager
from .context_builder import ContextBuilder
from .project_notes import ProjectNote, ProjectNotesManager, NoteCategory, NoteStatus

__all__ = [
    # Main interface
    "ContextMemoryManager",
    # Context building
    "ContextBuilder",
    # Models
    "Message",
    "MemoryConfig",
    "Session",
    "Summary",
    "MessageSummary",
    # Priority
    "Priority",
    "get_default_priority",
    "is_high_priority",
    "is_compressible",
    # Token counting
    "TokenCounter",
    "ApproximateTokenizer",
    # Storage
    "WorkingMemory",
    "PersistentStore",
    # Project Notes (NoteTool-like)
    "ProjectNote",
    "ProjectNotesManager",
    "NoteCategory",
    "NoteStatus",
]
