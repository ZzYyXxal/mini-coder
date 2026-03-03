"""Unit tests for ContextMemoryManager.

Tests cover session management, message handling, compression,
and integration with working memory and persistent store.
"""

import pytest
import tempfile
from pathlib import Path

from mini_coder.memory.manager import ContextMemoryManager
from mini_coder.memory.models import MemoryConfig, Message
from mini_coder.memory.priority import Priority


class TestContextMemoryManager:
    """Tests for ContextMemoryManager class."""

    @pytest.fixture
    def temp_path(self, tmp_path: Path) -> str:
        """Create a temporary path for testing."""
        return str(tmp_path / "memory")

    @pytest.fixture
    def config(self, temp_path: str) -> MemoryConfig:
        """Create a test configuration."""
        return MemoryConfig(
            enabled=True,
            max_messages=10,
            compression_threshold=0.92,
            storage_path=temp_path
        )

    @pytest.fixture
    def manager(self, config: MemoryConfig) -> ContextMemoryManager:
        """Create a ContextMemoryManager instance."""
        return ContextMemoryManager(config=config)

    def test_initialization_with_defaults(self) -> None:
        """Test initialization with default configuration."""
        manager = ContextMemoryManager()
        assert manager.is_enabled is True
        assert manager.message_count == 0

    def test_initialization_with_config(self, config: MemoryConfig) -> None:
        """Test initialization with custom configuration."""
        manager = ContextMemoryManager(config=config)
        assert manager.is_enabled is True
        assert manager._config.max_messages == 10

    def test_disabled_memory(self, temp_path: str) -> None:
        """Test that disabled memory doesn't store messages."""
        config = MemoryConfig(enabled=False, storage_path=temp_path)
        manager = ContextMemoryManager(config=config)

        manager.add_message("user", "Hello")

        assert manager.message_count == 0

    def test_start_session(self, manager: ContextMemoryManager) -> None:
        """Test starting a new session."""
        session_id = manager.start_session("/test/project")

        assert session_id is not None
        assert len(session_id) == 8
        assert manager.current_session_id == session_id
        assert manager.message_count == 0

    def test_add_message(self, manager: ContextMemoryManager) -> None:
        """Test adding a message."""
        manager.start_session()
        manager.add_message("user", "Hello")

        assert manager.message_count == 1

    def test_add_message_with_priority(self, manager: ContextMemoryManager) -> None:
        """Test adding a message with custom priority."""
        manager.start_session()
        manager.add_message("user", "Important", priority=Priority.HIGH)

        assert manager.message_count == 1

    def test_add_empty_message_is_skipped(self, manager: ContextMemoryManager) -> None:
        """Test that empty messages are skipped."""
        manager.start_session()
        manager.add_message("user", "   ")

        assert manager.message_count == 0

    def test_role_based_priority(self, manager: ContextMemoryManager) -> None:
        """Test that role-based priority is assigned correctly."""
        manager.start_session()

        manager.add_message("user", "User message")
        manager.add_message("assistant", "Assistant message")
        manager.add_message("system", "System message")

        # Check that messages were added
        assert manager.message_count == 3

    def test_get_context(self, manager: ContextMemoryManager) -> None:
        """Test getting context for LLM call."""
        manager.start_session()
        manager.add_message("user", "Hello")
        manager.add_message("assistant", "Hi there!")

        context = manager.get_context(max_tokens=10000)

        assert len(context) == 2
        assert context[0]["role"] == "user"
        assert context[1]["role"] == "assistant"

    def test_get_context_when_disabled(self, temp_path: str) -> None:
        """Test getting context when memory is disabled."""
        config = MemoryConfig(enabled=False, storage_path=temp_path)
        manager = ContextMemoryManager(config=config)

        context = manager.get_context(max_tokens=1000)

        assert context == []


class TestContextMemoryManagerSession:
    """Tests for session management."""

    @pytest.fixture
    def manager(self, tmp_path: Path) -> ContextMemoryManager:
        """Create a manager with temporary storage."""
        config = MemoryConfig(storage_path=str(tmp_path / "memory"))
        return ContextMemoryManager(config=config)

    def test_save_session(self, manager: ContextMemoryManager) -> None:
        """Test saving a session."""
        session_id = manager.start_session()
        manager.add_message("user", "Test message")
        manager.save_session()

        # Verify session was saved
        sessions = manager.list_sessions()
        assert session_id in sessions

    def test_load_session(self, manager: ContextMemoryManager) -> None:
        """Test loading a session."""
        # Create and save a session
        session_id = manager.start_session()
        manager.add_message("user", "Test message")
        manager.save_session()

        # Start new session (clears memory)
        manager.start_session()
        assert manager.message_count == 0

        # Load previous session
        result = manager.load_session(session_id)

        assert result is True
        assert manager.message_count == 1

    def test_load_nonexistent_session(self, manager: ContextMemoryManager) -> None:
        """Test loading a session that doesn't exist."""
        result = manager.load_session("nonexistent")
        assert result is False

    def test_list_sessions(self, manager: ContextMemoryManager) -> None:
        """Test listing sessions."""
        # Create multiple sessions
        for i in range(3):
            manager.start_session()
            manager.add_message("user", f"Message {i}")
            manager.save_session()

        sessions = manager.list_sessions()
        assert len(sessions) == 3

    def test_restore_latest_session(self, manager: ContextMemoryManager) -> None:
        """Test restoring the latest session."""
        # Create and save a session
        manager.start_session()
        manager.add_message("user", "Test")
        manager.save_session()

        # Clear and restore
        manager.start_session()
        manager.clear()

        result = manager.restore_latest_session()

        assert result is True
        assert manager.message_count == 1

    def test_restore_latest_session_when_none(self, manager: ContextMemoryManager) -> None:
        """Test restoring when no sessions exist."""
        result = manager.restore_latest_session()
        assert result is False


class TestContextMemoryManagerCompression:
    """Tests for compression functionality."""

    @pytest.fixture
    def manager(self, tmp_path: Path) -> ContextMemoryManager:
        """Create a manager with low compression threshold."""
        config = MemoryConfig(
            max_messages=5,
            compression_threshold=0.5,
            storage_path=str(tmp_path / "memory")
        )
        return ContextMemoryManager(config=config, max_tokens=100)

    def test_compress_removes_low_priority(self, manager: ContextMemoryManager) -> None:
        """Test that compression removes low priority messages from working memory.

        Note: The messages are included in a summary, so they may appear
        in the context as part of the summary text.
        """
        manager.start_session()

        # Add high and low priority messages
        manager.add_message("user", "Important", priority=Priority.HIGH)
        manager.add_message("user", "Less important", priority=Priority.LOW)
        manager.add_message("user", "Archive me", priority=Priority.ARCHIVE)

        summary = manager.compress()

        assert summary is not None
        # Check that low priority messages are removed from working memory
        assert manager.message_count == 1  # Only the high priority message remains
        # Check that summary was created and cached
        assert manager.summary_count == 1

    def test_compress_saves_summary(self, manager: ContextMemoryManager) -> None:
        """Test that compression saves summary to persistent store."""
        manager.start_session()

        manager.add_message("user", "Message 1", priority=Priority.LOW)
        manager.add_message("user", "Message 2", priority=Priority.LOW)

        summary = manager.compress()

        assert summary is not None
        assert len(summary.original_message_ids) == 2

    def test_compress_when_no_compressible_messages(self, manager: ContextMemoryManager) -> None:
        """Test compression when no messages are compressible."""
        manager.start_session()

        # Only add high priority messages
        manager.add_message("user", "Important", priority=Priority.HIGH)

        summary = manager.compress()

        assert summary is None

    def test_auto_compression_on_add(self, tmp_path: Path) -> None:
        """Test that compression is triggered automatically when threshold is reached."""
        config = MemoryConfig(
            max_messages=5,
            compression_threshold=0.5,  # Minimum allowed
            storage_path=str(tmp_path / "memory")
        )
        manager = ContextMemoryManager(config=config, max_tokens=100)

        manager.start_session()

        # Add messages with LOW priority to trigger compression
        for i in range(20):
            manager.add_message("user", f"Message {i} " * 10, priority=Priority.LOW)

        # Due to eviction and compression, should have fewer messages than added
        # Note: eviction happens at max_messages limit, compression at token threshold
        assert manager.message_count <= 5  # max_messages limit


class TestContextMemoryManagerIntegration:
    """Integration tests for full workflow."""

    @pytest.fixture
    def manager(self, tmp_path: Path) -> ContextMemoryManager:
        """Create a manager for integration testing."""
        config = MemoryConfig(storage_path=str(tmp_path / "memory"))
        return ContextMemoryManager(config=config)

    def test_full_conversation_workflow(self, manager: ContextMemoryManager) -> None:
        """Test a full conversation workflow."""
        # Start session
        session_id = manager.start_session("/project")

        # Add conversation
        manager.add_message("user", "Hello, I need help with Python.")
        manager.add_message("assistant", "Sure, I can help with Python!")
        manager.add_message("user", "How do I read a file?")

        # Get context for LLM
        context = manager.get_context(max_tokens=4000)
        assert len(context) == 3

        # Save session
        manager.save_session()

        # Simulate restart - load session
        manager.start_session()  # New empty session
        manager.load_session(session_id)

        assert manager.message_count == 3

    def test_clear_resets_memory(self, manager: ContextMemoryManager) -> None:
        """Test that clear resets working memory."""
        manager.start_session()
        manager.add_message("user", "Test")
        manager.clear()

        assert manager.message_count == 0
        assert manager.token_ratio == 0.0
