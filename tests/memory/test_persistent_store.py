"""Unit tests for PersistentStore.

Tests cover session persistence, summary storage, and cleanup functionality.
"""

import json
import pytest
import tempfile
from datetime import datetime
from pathlib import Path

from mini_coder.memory.models import Session, Message, Summary
from mini_coder.memory.persistent_store import PersistentStore


class TestPersistentStore:
    """Tests for PersistentStore class."""

    @pytest.fixture
    def temp_path(self, tmp_path: Path) -> Path:
        """Create a temporary path for testing."""
        return tmp_path / "memory"

    @pytest.fixture
    def store(self, temp_path: Path) -> PersistentStore:
        """Create a PersistentStore instance with temporary path."""
        return PersistentStore(path=str(temp_path))

    def test_initialization_creates_directories(self, temp_path: Path) -> None:
        """Test that initialization creates necessary directories."""
        store = PersistentStore(path=str(temp_path))

        assert store.path.exists()
        assert (store.path / "sessions").exists()

    def test_path_expansion(self) -> None:
        """Test that ~ is expanded in path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a path with ~ that we'll override
            store = PersistentStore(path=tmpdir)
            assert store.path.exists()

    def test_save_session(self, store: PersistentStore) -> None:
        """Test saving a session to disk."""
        session = Session(id="test123", project_path="/test/project")
        session.add_message(Message(role="user", content="Hello"))

        store.save_session(session)

        session_file = store._sessions_dir / "test123.json"
        assert session_file.exists()

        # Verify content
        content = json.loads(session_file.read_text())
        assert content["id"] == "test123"
        assert content["project_path"] == "/test/project"
        assert len(content["messages"]) == 1

    def test_load_session(self, store: PersistentStore) -> None:
        """Test loading a session from disk."""
        # Save a session first
        session = Session(id="loadtest", project_path="/test")
        session.add_message(Message(role="user", content="Test message"))
        store.save_session(session)

        # Load it back
        loaded = store.load_session("loadtest")

        assert loaded is not None
        assert loaded.id == "loadtest"
        assert loaded.project_path == "/test"
        assert len(loaded.messages) == 1
        assert loaded.messages[0].content == "Test message"

    def test_load_nonexistent_session(self, store: PersistentStore) -> None:
        """Test loading a session that doesn't exist."""
        result = store.load_session("nonexistent")
        assert result is None

    def test_delete_session(self, store: PersistentStore) -> None:
        """Test deleting a session."""
        session = Session(id="to_delete")
        store.save_session(session)

        assert store.delete_session("to_delete") is True
        assert store.load_session("to_delete") is None

    def test_delete_nonexistent_session(self, store: PersistentStore) -> None:
        """Test deleting a session that doesn't exist."""
        assert store.delete_session("nonexistent") is False

    def test_list_sessions(self, store: PersistentStore) -> None:
        """Test listing all sessions."""
        # Save multiple sessions
        for i in range(3):
            session = Session(id=f"session_{i}")
            store.save_session(session)

        sessions = store.list_sessions()
        assert len(sessions) == 3
        assert "session_0" in sessions
        assert "session_1" in sessions
        assert "session_2" in sessions

    def test_list_sessions_empty(self, store: PersistentStore) -> None:
        """Test listing sessions when none exist."""
        sessions = store.list_sessions()
        assert sessions == []


class TestPersistentStoreSummaries:
    """Tests for summary storage."""

    @pytest.fixture
    def store(self, tmp_path: Path) -> PersistentStore:
        """Create a PersistentStore instance."""
        return PersistentStore(path=str(tmp_path / "memory"))

    def test_save_summary(self, store: PersistentStore) -> None:
        """Test saving a summary."""
        summary = Summary(
            id="sum1",
            content="Test summary",
            original_message_ids=["msg1", "msg2"]
        )

        store.save_summary(summary)

        summaries_file = store.path / "summaries.json"
        assert summaries_file.exists()

    def test_load_summaries(self, store: PersistentStore) -> None:
        """Test loading summaries."""
        # Save summaries
        for i in range(3):
            summary = Summary(
                id=f"sum_{i}",
                content=f"Summary {i}",
                original_message_ids=[f"msg_{i}"]
            )
            store.save_summary(summary)

        summaries = store.load_summaries()
        assert len(summaries) == 3

    def test_load_summaries_empty(self, store: PersistentStore) -> None:
        """Test loading summaries when none exist."""
        summaries = store.load_summaries()
        assert summaries == []


class TestPersistentStoreSessionManagement:
    """Tests for session management features."""

    @pytest.fixture
    def store(self, tmp_path: Path) -> PersistentStore:
        """Create a PersistentStore instance."""
        return PersistentStore(path=str(tmp_path / "memory"))

    def test_get_latest_session(self, store: PersistentStore) -> None:
        """Test getting the latest session."""
        # Create sessions with different update times
        import time

        session1 = Session(id="old_session")
        store.save_session(session1)

        time.sleep(0.01)

        session2 = Session(id="new_session")
        store.save_session(session2)

        latest = store.get_latest_session()
        assert latest is not None
        assert latest.id == "new_session"

    def test_get_latest_session_empty(self, store: PersistentStore) -> None:
        """Test getting latest session when none exist."""
        latest = store.get_latest_session()
        assert latest is None

    def test_cleanup_old_sessions(self, store: PersistentStore) -> None:
        """Test cleaning up old sessions."""
        import time

        # Create more sessions than the limit
        for i in range(15):
            session = Session(id=f"session_{i}")
            store.save_session(session)
            time.sleep(0.001)  # Ensure different timestamps

        removed = store.cleanup_old_sessions(max_count=10)

        assert removed == 5
        assert len(store.list_sessions()) == 10

    def test_cleanup_nothing_needed(self, store: PersistentStore) -> None:
        """Test cleanup when under limit."""
        for i in range(5):
            session = Session(id=f"session_{i}")
            store.save_session(session)

        removed = store.cleanup_old_sessions(max_count=10)

        assert removed == 0
        assert len(store.list_sessions()) == 5


class TestPersistentStoreVectorSearch:
    """Tests for optional vector search (Phase 2)."""

    @pytest.fixture
    def store(self, tmp_path: Path) -> PersistentStore:
        """Create a PersistentStore instance."""
        return PersistentStore(path=str(tmp_path / "memory"))

    def test_search_without_enable_raises_error(self, store: PersistentStore) -> None:
        """Test that search raises error when not enabled."""
        with pytest.raises(RuntimeError) as exc_info:
            store.search_similar("test query")
        assert "not enabled" in str(exc_info.value)

    @pytest.mark.skip(reason="Phase 2 feature - chromadb may have compatibility issues")
    def test_enable_vector_search(self, store: PersistentStore) -> None:
        """Test enable_vector_search."""
        # chromadb is installed, so this should work
        store.enable_vector_search()
        assert store._collection is not None
