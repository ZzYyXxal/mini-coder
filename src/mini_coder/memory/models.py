"""Pydantic models for context memory system.

This module defines the core data models used throughout the memory system
for type-safe message, session, and summary handling.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from .priority import Priority


class Message(BaseModel):
    """A single message in the conversation context.

    Attributes:
        id: Unique identifier for the message.
        role: The role of the message sender (user, assistant, system).
        content: The text content of the message.
        priority: Priority level for context management.
        timestamp: When the message was created.
        metadata: Additional metadata for the message.
    """

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., min_length=1)
    priority: int = Field(default=Priority.NORMAL, ge=0, le=9)
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("content")
    @classmethod
    def content_must_not_be_whitespace(cls, v: str) -> str:
        """Validate that content is not just whitespace."""
        if not v or not v.strip():
            raise ValueError("content cannot be empty or whitespace only")
        return v

    model_config = {
        "use_enum_values": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": "a1b2c3d4",
                    "role": "user",
                    "content": "Hello, how can I implement a binary search?",
                    "priority": 1,
                    "timestamp": "2024-01-15T10:30:00",
                    "metadata": {"source": "tui"},
                }
            ]
        },
    }


class Session(BaseModel):
    """A conversation session with persistent state.

    Attributes:
        id: Unique identifier for the session.
        project_path: Optional path to the project being worked on.
        messages: List of messages in the session.
        created_at: When the session was created.
        updated_at: When the session was last updated.
    """

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    project_path: Optional[str] = None
    messages: list[Message] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def touch(self) -> None:
        """Update the updated_at timestamp to current time."""
        self.updated_at = datetime.now()

    def add_message(self, message: Message) -> None:
        """Add a message to the session and update timestamp."""
        self.messages.append(message)
        self.touch()

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "session123",
                    "project_path": "/home/user/my-project",
                    "messages": [],
                    "created_at": "2024-01-15T10:00:00",
                    "updated_at": "2024-01-15T10:30:00",
                }
            ]
        },
    }


class Summary(BaseModel):
    """A compressed summary of multiple messages.

    Summaries are created when context is compressed to reduce token usage
    while preserving key information.

    Attributes:
        id: Unique identifier for the summary.
        original_message_ids: IDs of messages that were summarized.
        content: The summary content.
        created_at: When the summary was created.
        metadata: Additional metadata about the compression.
    """

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    original_message_ids: list[str] = Field(default_factory=list)
    content: str = Field(..., min_length=1)
    created_at: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("content")
    @classmethod
    def content_must_not_be_empty(cls, v: str) -> str:
        """Validate that content is not empty."""
        if not v or not v.strip():
            raise ValueError("content cannot be empty")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "sum12345",
                    "original_message_ids": ["msg1", "msg2", "msg3"],
                    "content": "User discussed implementing binary search algorithm",
                    "created_at": "2024-01-15T11:00:00",
                    "metadata": {"compression_ratio": 0.3},
                }
            ]
        },
    }


class MessageSummary(BaseModel):
    """Summary metadata for a conversation turn.

    Captures key information about what happened in a single turn,
    including file operations and tool usage.

    Attributes:
        files_read: List of files that were read.
        files_modified: List of files that were modified.
        additions: Number of lines added.
        deletions: Number of lines deleted.
        tools_used: List of tools invoked.
        key_points: Key information extracted from the turn.
    """

    files_read: list[str] = Field(default_factory=list)
    files_modified: list[str] = Field(default_factory=list)
    additions: int = Field(default=0, ge=0)
    deletions: int = Field(default=0, ge=0)
    tools_used: list[str] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "files_read": ["/src/main.py", "/src/utils.py"],
                    "files_modified": ["/src/main.py"],
                    "additions": 25,
                    "deletions": 10,
                    "tools_used": ["read", "edit"],
                    "key_points": ["Added error handling", "Fixed typo in function name"],
                }
            ]
        },
    }


class MemoryConfig(BaseModel):
    """Configuration for the context memory system.

    Plan B: Hybrid Compression Strategy with:
    - Token-based triggering
    - Tool output pruning
    - Priority-based compression
    - Message-level summaries

    Attributes:
        enabled: Whether the memory system is enabled.
        max_messages: Maximum number of messages in working memory.
        compression_threshold: Token usage ratio that triggers compression (fallback).
        token_buffer: Buffer ratio for token counting inaccuracies.
        storage_path: Path to the persistent storage directory.
        max_history: Maximum number of summaries to keep.

        # Token management (Plan B)
        max_context_tokens: Maximum tokens for context.
        reserved_tokens: Tokens reserved for LLM output.

        # Pruning settings (from OpenCode)
        prune_threshold: Tokens to accumulate before pruning.
        prune_minimum: Minimum tokens to prune.
        prune_protected_tools: Tool patterns that are never pruned.
        preserve_recent_turns: Number of recent turns to preserve.
    """

    # Basic settings
    enabled: bool = Field(default=True)
    max_messages: int = Field(default=20, ge=5, le=100)
    compression_threshold: float = Field(default=0.92, ge=0.5, le=1.0)
    token_buffer: float = Field(default=0.10, ge=0.0, le=0.3)
    storage_path: str = Field(default="~/.mini-coder/memory")
    max_history: int = Field(default=1000, ge=100, le=10000)

    # Token management (Plan B)
    max_context_tokens: int = Field(default=128000, ge=10000)
    reserved_tokens: int = Field(default=20000, ge=5000)

    # Pruning settings (from OpenCode strategy)
    prune_threshold: int = Field(default=40000, ge=10000)
    prune_minimum: int = Field(default=20000, ge=5000)
    prune_protected_tools: list[str] = Field(
        default_factory=lambda: ["skill", "file", "search", "read", "write"]
    )
    preserve_recent_turns: int = Field(default=2, ge=1, le=10)

    # Message summaries
    enable_message_summaries: bool = Field(default=True)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "enabled": True,
                    "max_messages": 20,
                    "compression_threshold": 0.92,
                    "token_buffer": 0.10,
                    "storage_path": "~/.mini-coder/memory",
                    "max_history": 1000,
                    "max_context_tokens": 128000,
                    "reserved_tokens": 20000,
                    "prune_threshold": 40000,
                    "prune_minimum": 20000,
                    "prune_protected_tools": ["skill", "file", "search"],
                    "preserve_recent_turns": 2,
                    "enable_message_summaries": True,
                }
            ]
        },
    }
