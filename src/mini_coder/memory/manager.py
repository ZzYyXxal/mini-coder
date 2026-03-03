"""Context Memory Manager - main interface for context management.

This module provides the ContextMemoryManager class that coordinates
working memory, persistent storage, and compression.

Plan B: Hybrid Compression Strategy
- Token-based triggering with reserved buffer
- Tool output pruning (low cost, high impact)
- Priority-based compression (intelligent selection)
- Summary caching for context inclusion
"""

import logging
from typing import Optional
from uuid import uuid4

from .models import MemoryConfig, Message, Session, Summary
from .priority import (
    get_default_priority,
    is_compressible,
    is_high_priority,
    calculate_priority_by_age,
)
from .working_memory import WorkingMemory
from .persistent_store import PersistentStore


class ContextMemoryManager:
    """Main interface for context memory management.

    Coordinates working memory (RAM) and persistent storage (disk)
    with automatic compression and session management.

    Plan B: Hybrid Compression Strategy:
    1. Token-based triggering (precise)
    2. Tool output pruning (low cost)
    3. Priority-based compression (intelligent)
    4. Summary caching (preserve context)

    Example:
        >>> config = MemoryConfig(max_messages=20, compression_threshold=0.92)
        >>> manager = ContextMemoryManager(config)
        >>> session_id = manager.start_session("/path/to/project")
        >>> manager.add_message("user", "Hello!")
        >>> context = manager.get_context(max_tokens=4000)
    """

    def __init__(
        self,
        config: Optional[MemoryConfig] = None,
        max_tokens: int = 128000
    ):
        """Initialize the context memory manager.

        Args:
            config: Memory configuration. Uses defaults if not provided.
            max_tokens: Maximum token limit for context.
        """
        self._config = config or MemoryConfig()
        self._max_tokens = max_tokens

        # Initialize components with Plan B config
        self._working = WorkingMemory(
            max_messages=self._config.max_messages,
            compression_threshold=self._config.compression_threshold,
            token_buffer=self._config.token_buffer,
            max_tokens=max_tokens,
            config=self._config
        )

        self._persistent = PersistentStore(path=self._config.storage_path)

        # Current session state
        self._current_session: Optional[Session] = None

        # Cached summaries for context inclusion
        self._summaries: list[Summary] = []

        # Statistics
        self._stats = {
            "prune_operations": 0,
            "compress_operations": 0,
            "tokens_pruned": 0,
            "messages_compressed": 0,
        }

    @property
    def is_enabled(self) -> bool:
        """Check if memory system is enabled."""
        return self._config.enabled

    @property
    def current_session_id(self) -> Optional[str]:
        """Get the current session ID."""
        return self._current_session.id if self._current_session else None

    @property
    def message_count(self) -> int:
        """Get the number of messages in working memory."""
        return self._working.message_count

    @property
    def token_ratio(self) -> float:
        """Get the current token usage ratio."""
        return self._working.token_ratio

    @property
    def summary_count(self) -> int:
        """Get the number of cached summaries."""
        return len(self._summaries)

    @property
    def summaries(self) -> list[Summary]:
        """Get the cached summaries (read-only copy)."""
        return self._summaries.copy()

    def start_session(self, project_path: Optional[str] = None) -> str:
        """Start a new session.

        Args:
            project_path: Optional path to the project being worked on.

        Returns:
            The session ID.
        """
        session_id = uuid4().hex[:8]
        self._current_session = Session(
            id=session_id,
            project_path=project_path
        )

        # Clear working memory for new session
        self._working.clear()
        self._summaries = []

        return session_id

    def add_message(
        self,
        role: str,
        content: str,
        priority: Optional[int] = None
    ) -> None:
        """Add a message to the context.

        Args:
            role: The role of the message sender (user, assistant, system).
            content: The message content.
            priority: Optional priority override. Uses role-based default if not provided.
        """
        if not self._config.enabled:
            return

        if not content or not content.strip():
            return

        # Determine priority
        if priority is None:
            priority = get_default_priority(role)

        # Create message
        message = Message(
            role=role,
            content=content,
            priority=priority
        )

        # Add to working memory
        self._working.add(message)

        # Add to session
        if self._current_session:
            self._current_session.add_message(message)

        # Update priorities of older messages (degrade over time)
        self._degrade_old_priorities()

        # Check for compression
        if self._working.should_compress():
            self.compress()

    def _degrade_old_priorities(self) -> None:
        """Degrade priorities of older messages.

        This makes older messages more likely to be compressed.
        """
        messages = self._working.messages
        total_count = len(messages)

        if total_count <= 6:  # Keep recent messages as-is
            return

        # Update priorities based on position
        for i, msg in enumerate(messages):
            turns_ago = total_count - i - 1
            if turns_ago > 0:  # Don't change the newest message
                new_priority = calculate_priority_by_age(
                    msg.priority,
                    turns_ago // 2,  # Each turn = user + assistant
                    preserve_recent_turns=4
                )
                if new_priority != msg.priority:
                    msg.priority = new_priority

    def get_context(self, max_tokens: int) -> list[dict]:
        """Get context for LLM call.

        Returns messages formatted for LLM consumption, respecting
        the token limit. Includes summaries of compressed content.

        Args:
            max_tokens: Maximum tokens for the context.

        Returns:
            List of message dictionaries.
        """
        if not self._config.enabled:
            return []

        result: list[dict] = []
        current_tokens = 0
        effective_limit = int(max_tokens * 0.9)  # 10% buffer

        # 1. Add summaries first (if any) as a system-like context
        if self._summaries:
            summary_text = self._format_summaries_for_context()
            summary_tokens = self._working._token_counter.count(summary_text)
            if current_tokens + summary_tokens <= effective_limit:
                result.append({
                    "role": "system",
                    "content": f"[对话历史摘要]\n{summary_text}",
                    "priority": 0,
                })
                current_tokens += summary_tokens + 10

        # 2. Add high-priority messages
        high_priority = [m for m in self._working.messages if is_high_priority(m.priority)]
        for msg in sorted(high_priority, key=lambda m: m.timestamp):
            msg_tokens = self._working._token_counter.count(msg.content) + 10
            if current_tokens + msg_tokens <= effective_limit:
                result.append(msg.model_dump())
                current_tokens += msg_tokens

        # 3. Add remaining messages by priority
        other_messages = [m for m in self._working.messages if not is_high_priority(m.priority)]
        for msg in sorted(other_messages, key=lambda m: (m.priority, m.timestamp)):
            msg_tokens = self._working._token_counter.count(msg.content) + 10
            if current_tokens + msg_tokens <= effective_limit:
                result.append(msg.model_dump())
                current_tokens += msg_tokens

        # 4. Sort final result by timestamp to maintain conversation order
        def get_timestamp_key(m: dict) -> str:
            ts = m.get("timestamp", "")
            if hasattr(ts, 'isoformat'):
                return ts.isoformat()
            return str(ts) if ts else ""

        result.sort(key=get_timestamp_key)

        return result

    def _format_summaries_for_context(self) -> str:
        """Format summaries for inclusion in context.

        Returns:
            Formatted summary text.
        """
        if not self._summaries:
            return ""

        parts = []
        for i, summary in enumerate(self._summaries[-3:], 1):  # Last 3 summaries
            parts.append(f"历史片段 {i}:\n{summary.content}")

        return "\n\n".join(parts)

    def should_compress(self) -> bool:
        """Check if compression is needed (Plan B).

        Uses token-based triggering with reserved buffer.

        Returns:
            True if compression should be triggered.
        """
        if not self._config.enabled:
            return False
        return self._working.should_compress()

    def prune_tool_outputs(self) -> int:
        """Prune tool outputs to free tokens (Plan B).

        This is a low-cost operation that removes old tool outputs
        before doing full compression.

        Returns:
            Number of tokens freed.
        """
        if not self._config.enabled:
            return 0

        tokens_freed = self._working.prune_tool_outputs()
        if tokens_freed > 0:
            self._stats["prune_operations"] += 1
            self._stats["tokens_pruned"] += tokens_freed

        return tokens_freed

    def compress(self) -> Optional[Summary]:
        """Compress working memory using hybrid strategy (Plan B).

        This is a higher-cost operation that creates summaries.

        Flow:
        1. Get compressible messages (priority >= NORMAL)
        2. Exclude high priority messages
        3. Create structured summary
        4. Cache summary for context inclusion
        5. Remove compressed messages from working memory

        Returns:
            The created summary if compression occurred, None otherwise.
        """
        if not self._config.enabled:
            return None

        # Get compressible messages (now includes NORMAL priority and above)
        compressible = self._working.get_low_priority()
        if not compressible:
            logging.debug("No compressible messages found")
            return None

        # Always preserve high priority messages
        high_priority_ids = {m.id for m in self._working.messages if is_high_priority(m.priority)}

        # Filter to get messages to compress
        to_compress = [m for m in compressible if m.id not in high_priority_ids]

        if not to_compress:
            logging.debug("All compressible messages are high priority, skipping")
            return None

        # Create summary
        summary_content = self._create_summary(to_compress)
        summary = Summary(
            original_message_ids=[m.id for m in to_compress],
            content=summary_content,
            metadata={
                "compression_type": "hybrid",
                "original_count": len(to_compress),
                "preserved_count": len(high_priority_ids),
                "tokens_saved": sum(
                    self._working._token_counter.count(m.content)
                    for m in to_compress
                ),
            }
        )

        # Save summary to persistent store
        self._persistent.save_summary(summary)

        # Cache summary for context inclusion
        self._summaries.append(summary)

        # Remove compressed messages from working memory
        self._working.remove_messages(summary.original_message_ids)

        # Update statistics
        self._stats["compress_operations"] += 1
        self._stats["messages_compressed"] += len(to_compress)

        logging.info(
            f"Compressed {len(to_compress)} messages, "
            f"preserved {len(high_priority_ids)}, "
            f"tokens saved: {summary.metadata.get('tokens_saved', 0)}, "
            f"total summaries: {len(self._summaries)}"
        )

        return summary

    def smart_compress(self) -> tuple[Optional[Summary], int]:
        """Smart compression using Plan B hybrid strategy.

        First tries pruning (low cost), then compression if needed.

        Returns:
            Tuple of (summary, tokens_freed).
            summary: The created summary if compression occurred.
            tokens_freed: Total tokens freed by pruning + compression.
        """
        tokens_freed = 0
        summary = None

        # Step 1: Try pruning first (low cost)
        if self.should_compress():
            tokens_freed = self.prune_tool_outputs()

        # Step 2: If still over limit, do full compression
        if self.should_compress():
            summary = self.compress()
            if summary:
                tokens_freed += summary.metadata.get("tokens_saved", 0)

        return summary, tokens_freed

    def get_stats(self) -> dict:
        """Get compression statistics.

        Returns:
            Dictionary with statistics.
        """
        return {
            **self._stats,
            "current_messages": self.message_count,
            "current_summaries": self.summary_count,
            "token_ratio": self.token_ratio,
        }

    def save_session(self) -> None:
        """Save the current session to disk."""
        if self._current_session:
            self._persistent.save_session(self._current_session)

    def load_session(self, session_id: str) -> bool:
        """Load a previous session.

        Args:
            session_id: The ID of the session to load.

        Returns:
            True if session was loaded, False if not found.
        """
        session = self._persistent.load_session(session_id)
        if session:
            self._current_session = session

            # Restore messages to working memory
            self._working.clear()
            for message in session.messages:
                self._working.add(message)

            # Load summaries
            self._summaries = self._persistent.load_summaries()

            return True
        return False

    def list_sessions(self) -> list[str]:
        """List all saved sessions.

        Returns:
            List of session IDs.
        """
        return self._persistent.list_sessions()

    def get_latest_session(self) -> Optional[Session]:
        """Get the most recently updated session.

        Returns:
            The latest session if any, None otherwise.
        """
        return self._persistent.get_latest_session()

    def restore_latest_session(self) -> bool:
        """Restore the most recent session.

        Returns:
            True if a session was restored, False otherwise.
        """
        latest = self.get_latest_session()
        if latest:
            return self.load_session(latest.id)
        return False

    def clear(self) -> None:
        """Clear all messages from working memory."""
        self._working.clear()
        self._summaries = []

    def _create_summary(self, messages: list[Message]) -> str:
        """Create a summary of the given messages.

        Creates a structured summary with key information preserved.

        Args:
            messages: Messages to summarize.

        Returns:
            Summary text.
        """
        if not messages:
            return ""

        # Group messages by role
        user_messages = [m for m in messages if m.role == "user"]
        assistant_messages = [m for m in messages if m.role == "assistant"]

        parts = []

        # Summarize user queries
        if user_messages:
            parts.append("用户提问:")
            for i, msg in enumerate(user_messages[-5:], 1):  # Last 5
                preview = msg.content[:80]
                if len(msg.content) > 80:
                    preview += "..."
                parts.append(f"  {i}. {preview}")

        # Summarize assistant responses
        if assistant_messages:
            parts.append("\n助手回复:")
            for i, msg in enumerate(assistant_messages[-3:], 1):  # Last 3
                preview = msg.content[:100]
                if len(msg.content) > 100:
                    preview += "..."
                parts.append(f"  {i}. {preview}")

        # Add metadata
        parts.append(f"\n[共 {len(messages)} 条消息被压缩]")

        return "\n".join(parts)

    def __repr__(self) -> str:
        """Get string representation."""
        return (
            f"ContextMemoryManager(session={self.current_session_id}, "
            f"messages={self.message_count}, summaries={self.summary_count}, "
            f"ratio={self.token_ratio:.1%})"
        )
