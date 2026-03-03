"""Working memory implementation for context management.

This module provides the WorkingMemory class for managing messages
in RAM with priority-based eviction and token-aware context retrieval.

Plan B enhancements:
- Token-based compression triggering
- Tool output pruning
- Protected message preservation
"""

import logging
from typing import Optional

from .models import Message, MemoryConfig
from .priority import is_compressible, is_high_priority
from .token_counter import TokenCounter


class WorkingMemory:
    """In-memory context with priority-based management.

    WorkingMemory stores recent conversation messages in RAM with
    priority-based eviction when the message limit is exceeded.

    Plan B enhancements:
    - Token-based compression triggering
    - Tool output pruning with protected tools
    - Recent turn preservation

    Attributes:
        max_messages: Maximum number of messages to store.
        compression_threshold: Token ratio that triggers compression.
        token_buffer: Buffer ratio for token counting errors.
        config: MemoryConfig for Plan B settings.
    """

    def __init__(
        self,
        max_messages: int = 20,
        compression_threshold: float = 0.92,
        token_buffer: float = 0.10,
        max_tokens: int = 128000,
        config: Optional[MemoryConfig] = None
    ):
        """Initialize working memory.

        Args:
            max_messages: Maximum number of messages to store.
            compression_threshold: Token ratio that triggers compression.
            token_buffer: Buffer ratio for token counting errors.
            max_tokens: Maximum token limit for context.
            config: MemoryConfig for Plan B settings (optional).
        """
        self._messages: list[Message] = []
        self.max_messages = max_messages
        self.compression_threshold = compression_threshold
        self._config = config or MemoryConfig()
        self._token_counter = TokenCounter(
            max_tokens=max_tokens,
            buffer_ratio=token_buffer
        )

    @property
    def messages(self) -> list[Message]:
        """Get a copy of the current messages."""
        return self._messages.copy()

    @property
    def message_count(self) -> int:
        """Get the number of messages in memory."""
        return len(self._messages)

    @property
    def token_ratio(self) -> float:
        """Get the current token usage ratio."""
        return self._token_counter.ratio()

    def add(self, message: Message) -> None:
        """Add a message to working memory.

        If the message limit is exceeded, low priority messages are evicted.

        Args:
            message: The message to add.
        """
        # Skip empty messages
        if not message.content or not message.content.strip():
            return

        # Add message
        self._messages.append(message)

        # Update token counter
        tokens = self._token_counter.count(message.content)
        self._token_counter.add_tokens(tokens + 4)  # +4 for role overhead

        # Evict if over limit
        while len(self._messages) > self.max_messages:
            self._evict_low_priority()

    def get_context(self, max_tokens: int) -> list[dict]:
        """Get context within token limit, sorted by priority.

        Messages are returned in priority order (HIGH first) but maintain
        chronological order within the same priority level.

        Args:
            max_tokens: Maximum tokens for the context.

        Returns:
            List of message dictionaries within the token limit.
        """
        # Sort by priority (lower = higher priority)
        sorted_messages = sorted(
            self._messages,
            key=lambda m: (m.priority, m.timestamp)
        )

        result: list[dict] = []
        current_tokens = 0
        effective_limit = int(max_tokens * (1 - self._token_counter._buffer_ratio))

        for msg in sorted_messages:
            msg_tokens = self._token_counter.count(msg.content) + 4
            if current_tokens + msg_tokens <= effective_limit:
                result.append(msg.model_dump())
                current_tokens += msg_tokens

        # Re-sort by timestamp to maintain conversation order
        result.sort(key=lambda m: m.get("timestamp", ""))

        return result

    def should_compress(self) -> bool:
        """Check if compression should be triggered.

        Plan B: Uses token-based triggering with reserved buffer.

        Returns:
            True if compression is needed.
        """
        # Plan B: Token-based check
        current_tokens = self._token_counter._current_tokens
        usable_tokens = self._config.max_context_tokens - self._config.reserved_tokens

        if current_tokens >= usable_tokens:
            return True

        # Fallback: Ratio-based check
        return self._token_counter.should_compress(self.compression_threshold)

    def prune_tool_outputs(self) -> int:
        """Remove old tool outputs to free tokens (Plan B).

        Scans messages from oldest to newest, skipping recent turns
        and protected tools. Removes tool output messages when
        accumulated tokens exceed threshold.

        Returns:
            Number of tokens freed by pruning.
        """
        messages = self._messages
        total_tokens = 0
        to_prune: list[Message] = []

        # Calculate protected range (recent turns)
        # Each turn = user message + assistant message
        protected_count = self._config.preserve_recent_turns * 2
        scan_messages = messages[:-protected_count] if len(messages) > protected_count else []

        # Scan from oldest to newest
        for msg in scan_messages:
            # Check if this is a tool output
            tool_name = msg.metadata.get("tool_name")
            is_tool_output = msg.metadata.get("is_tool_output", False)

            if not is_tool_output and not tool_name:
                continue

            # Check if tool is protected
            if tool_name:
                is_protected = any(
                    protected in tool_name.lower()
                    for protected in self._config.prune_protected_tools
                )
                if is_protected:
                    continue

            # Add to prune list
            msg_tokens = self._token_counter.count(msg.content) + 4
            total_tokens += msg_tokens
            to_prune.append(msg)

            # Stop when we've accumulated enough tokens
            if total_tokens >= self._config.prune_threshold:
                break

        # Only prune if we have enough to make it worthwhile
        if total_tokens >= self._config.prune_minimum:
            pruned_ids = [msg.id for msg in to_prune]
            self.remove_messages(pruned_ids)
            logging.info(
                f"Pruned {len(to_prune)} tool outputs, freed {total_tokens} tokens"
            )
            return total_tokens

        return 0

    def get_protected_ids(self) -> set[str]:
        """Get IDs of messages that should never be removed by pruning.

        Note: This is for pruning protection only. Compression uses
        a different protection mechanism (high priority + compressible check).

        Returns:
            Set of protected message IDs.
        """
        protected_ids: set[str] = set()

        # Protect recent turns
        protected_count = self._config.preserve_recent_turns * 2
        if len(self._messages) > protected_count:
            recent_messages = self._messages[-protected_count:]
            for msg in recent_messages:
                protected_ids.add(msg.id)

        # Protect messages with protected tools
        for msg in self._messages:
            tool_name = msg.metadata.get("tool_name", "")
            if tool_name:
                is_protected = any(
                    protected in tool_name.lower()
                    for protected in self._config.prune_protected_tools
                )
                if is_protected:
                    protected_ids.add(msg.id)

        return protected_ids

    def get_low_priority(self) -> list[Message]:
        """Get messages eligible for compression.

        Returns messages with LOW or ARCHIVE priority that can be compressed.

        Returns:
            List of compressible messages.
        """
        return [m for m in self._messages if is_compressible(m.priority)]

    def get_high_priority(self) -> list[Message]:
        """Get high priority messages that should be preserved.

        Returns:
            List of high priority messages.
        """
        return [m for m in self._messages if is_high_priority(m.priority)]

    def remove_messages(self, message_ids: list[str]) -> None:
        """Remove messages by ID.

        Args:
            message_ids: List of message IDs to remove.
        """
        ids_to_remove = set(message_ids)

        self._messages = [m for m in self._messages if m.id not in ids_to_remove]

        # Recalculate token count
        self._recalculate_tokens()

    def clear(self) -> None:
        """Clear all messages from working memory."""
        self._messages.clear()
        self._token_counter.reset()

    def _evict_low_priority(self) -> None:
        """Evict the lowest priority message.

        If all messages have the same priority, evicts the oldest.
        """
        if not self._messages:
            return

        # Find lowest priority (highest number) message
        lowest = max(self._messages, key=lambda m: m.priority)

        # If multiple have same priority, take oldest
        candidates = [m for m in self._messages if m.priority == lowest.priority]
        if len(candidates) > 1:
            lowest = min(candidates, key=lambda m: m.timestamp)

        # Remove and update token counter
        self._messages.remove(lowest)
        tokens = self._token_counter.count(lowest.content) + 4
        self._token_counter.add_tokens(-tokens)

    def _recalculate_tokens(self) -> None:
        """Recalculate the total token count from current messages."""
        self._token_counter.reset()
        for msg in self._messages:
            tokens = self._token_counter.count(msg.content) + 4
            self._token_counter.add_tokens(tokens)

    def __len__(self) -> int:
        """Get the number of messages."""
        return len(self._messages)

    def __repr__(self) -> str:
        """Get string representation."""
        return (
            f"WorkingMemory(messages={len(self._messages)}, "
            f"max={self.max_messages}, ratio={self.token_ratio:.2%})"
        )
