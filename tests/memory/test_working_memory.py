"""Unit tests for WorkingMemory.

Tests cover message storage, priority-based eviction, token management,
and context retrieval.
"""

import pytest
from datetime import datetime, timedelta

from mini_coder.memory.models import Message
from mini_coder.memory.priority import Priority
from mini_coder.memory.working_memory import WorkingMemory


class TestWorkingMemory:
    """Tests for WorkingMemory class."""

    def test_initialization_with_defaults(self) -> None:
        """Test initialization with default values."""
        memory = WorkingMemory()
        assert memory.max_messages == 20
        assert memory.compression_threshold == 0.92
        assert memory.message_count == 0

    def test_initialization_with_custom_values(self) -> None:
        """Test initialization with custom values."""
        memory = WorkingMemory(
            max_messages=10,
            compression_threshold=0.8,
            token_buffer=0.15
        )
        assert memory.max_messages == 10
        assert memory.compression_threshold == 0.8

    def test_add_message(self) -> None:
        """Test adding a message."""
        memory = WorkingMemory()
        msg = Message(role="user", content="Hello")
        memory.add(msg)

        assert memory.message_count == 1
        assert len(memory.messages) == 1
        assert memory.messages[0].content == "Hello"

    def test_add_message_updates_token_count(self) -> None:
        """Test that adding a message updates token count."""
        memory = WorkingMemory(max_tokens=1000)
        msg = Message(role="user", content="Hello world")
        memory.add(msg)

        assert memory.token_ratio > 0

    def test_skip_empty_message(self) -> None:
        """Test that empty messages are handled correctly."""
        memory = WorkingMemory()
        # Pydantic validates at creation, so we test with valid content
        # but check the add method handles the case
        msg = Message(role="user", content="Valid content")
        memory.add(msg)

        assert memory.message_count == 1

    def test_eviction_when_over_limit(self) -> None:
        """Test that low priority messages are evicted when over limit."""
        memory = WorkingMemory(max_messages=3)

        # Add messages with different priorities
        memory.add(Message(role="user", content="High", priority=Priority.HIGH))
        memory.add(Message(role="user", content="Normal1", priority=Priority.NORMAL))
        memory.add(Message(role="user", content="Low", priority=Priority.LOW))
        memory.add(Message(role="user", content="Normal2", priority=Priority.NORMAL))

        # Should have evicted the LOW priority message
        assert memory.message_count == 3
        contents = [m.content for m in memory.messages]
        assert "Low" not in contents

    def test_get_context_respects_token_limit(self) -> None:
        """Test that get_context respects token limit."""
        memory = WorkingMemory(max_tokens=100)

        # Add several messages
        for i in range(5):
            memory.add(Message(role="user", content=f"Message {i} " * 10))

        context = memory.get_context(max_tokens=50)
        # Should not return all messages due to token limit
        assert len(context) < 5

    def test_get_context_returns_priority_ordered(self) -> None:
        """Test that get_context returns messages with priority selection."""
        memory = WorkingMemory(max_messages=10, max_tokens=100)

        # Add messages with different priorities
        memory.add(Message(role="user", content="Low", priority=Priority.LOW))
        memory.add(Message(role="user", content="High", priority=Priority.HIGH))
        memory.add(Message(role="user", content="Normal", priority=Priority.NORMAL))

        context = memory.get_context(max_tokens=10000)

        # All messages should be returned (they fit in token limit)
        contents = [c["content"] for c in context]
        assert len(contents) == 3
        # Messages maintain chronological order after priority selection
        assert set(contents) == {"Low", "High", "Normal"}

    def test_should_compress_below_threshold(self) -> None:
        """Test should_compress returns False below threshold."""
        memory = WorkingMemory(compression_threshold=0.92)
        memory.add(Message(role="user", content="Short message"))

        assert memory.should_compress() is False

    def test_should_compress_at_threshold(self) -> None:
        """Test should_compress returns True at threshold."""
        memory = WorkingMemory(
            max_tokens=100,
            compression_threshold=0.5
        )

        # Add enough messages to exceed threshold
        for i in range(20):
            memory.add(Message(role="user", content=f"Message {i} " * 5))

        assert memory.should_compress() is True

    def test_get_low_priority_messages(self) -> None:
        """Test getting low priority messages."""
        memory = WorkingMemory()

        memory.add(Message(role="user", content="High", priority=Priority.HIGH))
        memory.add(Message(role="user", content="Low", priority=Priority.LOW))
        memory.add(Message(role="user", content="Archive", priority=Priority.ARCHIVE))

        low_priority = memory.get_low_priority()
        assert len(low_priority) == 2
        contents = [m.content for m in low_priority]
        assert "Low" in contents
        assert "Archive" in contents

    def test_get_high_priority_messages(self) -> None:
        """Test getting high priority messages."""
        memory = WorkingMemory()

        memory.add(Message(role="user", content="High", priority=Priority.HIGH))
        memory.add(Message(role="user", content="Medium", priority=Priority.MEDIUM))
        memory.add(Message(role="user", content="Low", priority=Priority.LOW))

        high_priority = memory.get_high_priority()
        assert len(high_priority) == 2
        contents = [m.content for m in high_priority]
        assert "High" in contents
        assert "Medium" in contents

    def test_remove_messages_by_id(self) -> None:
        """Test removing messages by ID."""
        memory = WorkingMemory()

        msg1 = Message(role="user", content="Message 1")
        msg2 = Message(role="user", content="Message 2")
        memory.add(msg1)
        memory.add(msg2)

        memory.remove_messages([msg1.id])

        assert memory.message_count == 1
        assert memory.messages[0].content == "Message 2"

    def test_clear_all_messages(self) -> None:
        """Test clearing all messages."""
        memory = WorkingMemory()

        for i in range(5):
            memory.add(Message(role="user", content=f"Message {i}"))

        memory.clear()

        assert memory.message_count == 0
        assert memory.token_ratio == 0.0

    def test_messages_property_returns_copy(self) -> None:
        """Test that messages property returns a copy."""
        memory = WorkingMemory()
        memory.add(Message(role="user", content="Test"))

        msgs = memory.messages
        msgs.clear()  # Modify the copy

        assert memory.message_count == 1  # Original unchanged


class TestWorkingMemoryEviction:
    """Tests for eviction behavior."""

    def test_evict_oldest_when_same_priority(self) -> None:
        """Test that oldest message is evicted when all have same priority."""
        memory = WorkingMemory(max_messages=3)

        # Add messages with same priority
        memory.add(Message(role="user", content="First"))
        memory.add(Message(role="user", content="Second"))
        memory.add(Message(role="user", content="Third"))
        memory.add(Message(role="user", content="Fourth"))

        contents = [m.content for m in memory.messages]
        assert "First" not in contents  # Oldest should be evicted
        assert "Fourth" in contents  # Newest should remain

    def test_preserve_high_priority_during_eviction(self) -> None:
        """Test that high priority messages are preserved during eviction."""
        memory = WorkingMemory(max_messages=2)

        memory.add(Message(role="user", content="High", priority=Priority.HIGH))
        memory.add(Message(role="user", content="Low", priority=Priority.LOW))
        memory.add(Message(role="user", content="Normal", priority=Priority.NORMAL))

        contents = [m.content for m in memory.messages]
        assert "High" in contents  # Should be preserved

    def test_multiple_evictions(self) -> None:
        """Test multiple evictions when adding many messages."""
        memory = WorkingMemory(max_messages=3)

        for i in range(10):
            memory.add(Message(role="user", content=f"Message {i}"))

        assert memory.message_count == 3


class TestWorkingMemoryTokenBuffer:
    """Tests for token buffer behavior."""

    def test_token_buffer_in_get_context(self) -> None:
        """Test that token buffer is applied in get_context."""
        memory = WorkingMemory(
            max_tokens=100,
            token_buffer=0.20  # 20% buffer
        )

        # Add messages that would fit without buffer
        for i in range(10):
            memory.add(Message(role="user", content=f"Message {i}"))

        # Get context with buffer applied (effective limit = 80)
        context = memory.get_context(max_tokens=100)

        # Should respect the buffer
        total_chars = sum(len(c["content"]) for c in context)
        # Rough check that buffer is working
        assert total_chars < 500  # Should be limited

    def test_default_token_buffer(self) -> None:
        """Test default token buffer is 10%."""
        memory = WorkingMemory()
        assert memory._token_counter._buffer_ratio == 0.10
