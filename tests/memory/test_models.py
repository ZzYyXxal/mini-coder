"""Unit tests for context memory Pydantic models.

Tests cover validation, serialization, and edge cases for Message,
Session, Summary, and MemoryConfig models.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from mini_coder.memory.models import Message, Session, Summary, MemoryConfig
from mini_coder.memory.priority import Priority


class TestMessage:
    """Tests for Message model."""

    def test_create_message_with_defaults(self) -> None:
        """Test creating a message with default values."""
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.priority == Priority.NORMAL
        assert isinstance(msg.timestamp, datetime)
        assert isinstance(msg.id, str)
        assert len(msg.id) == 8

    def test_create_message_with_all_fields(self) -> None:
        """Test creating a message with all fields specified."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        msg = Message(
            id="test1234",
            role="assistant",
            content="Response",
            priority=Priority.HIGH,
            timestamp=timestamp,
            metadata={"source": "test"}
        )
        assert msg.id == "test1234"
        assert msg.role == "assistant"
        assert msg.content == "Response"
        assert msg.priority == Priority.HIGH
        assert msg.timestamp == timestamp
        assert msg.metadata == {"source": "test"}

    def test_invalid_role_raises_error(self) -> None:
        """Test that invalid role raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Message(role="invalid", content="test")
        assert "role" in str(exc_info.value).lower()

    def test_empty_content_raises_error(self) -> None:
        """Test that empty content raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Message(role="user", content="")
        assert "content" in str(exc_info.value).lower()

    def test_whitespace_only_content_raises_error(self) -> None:
        """Test that whitespace-only content raises ValidationError."""
        with pytest.raises(ValidationError):
            Message(role="user", content="   \n\t  ")

    def test_invalid_priority_raises_error(self) -> None:
        """Test that out-of-range priority raises ValidationError."""
        # Priority must be >= 0 and <= 9
        with pytest.raises(ValidationError):
            Message(role="user", content="test", priority=-1)

        with pytest.raises(ValidationError):
            Message(role="user", content="test", priority=10)

    def test_valid_priority_range(self) -> None:
        """Test that valid priority values are accepted."""
        # Priority range is now 0-9 (0 = CRITICAL, 9 = ARCHIVE)
        for priority in [0, 1, 2, 4, 6, 8]:
            msg = Message(role="user", content="test", priority=priority)
            assert msg.priority == priority

    def test_message_serialization(self) -> None:
        """Test message can be serialized to dict."""
        msg = Message(role="user", content="Hello", priority=Priority.HIGH)
        data = msg.model_dump()
        assert data["role"] == "user"
        assert data["content"] == "Hello"
        assert data["priority"] == 1  # Priority.HIGH value

    def test_message_json_serialization(self) -> None:
        """Test message can be serialized to JSON."""
        msg = Message(role="user", content="Hello")
        json_str = msg.model_dump_json()
        assert "user" in json_str
        assert "Hello" in json_str


class TestSession:
    """Tests for Session model."""

    def test_create_session_with_defaults(self) -> None:
        """Test creating a session with default values."""
        session = Session()
        assert isinstance(session.id, str)
        assert len(session.id) == 8
        assert session.project_path is None
        assert session.messages == []
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.updated_at, datetime)

    def test_create_session_with_project_path(self) -> None:
        """Test creating a session with project path."""
        session = Session(project_path="/home/user/project")
        assert session.project_path == "/home/user/project"

    def test_add_message_updates_timestamp(self) -> None:
        """Test that adding a message updates the timestamp."""
        session = Session()
        old_updated = session.updated_at

        # Add a small delay to ensure timestamp difference
        import time
        time.sleep(0.01)

        msg = Message(role="user", content="test")
        session.add_message(msg)

        assert len(session.messages) == 1
        assert session.updated_at > old_updated

    def test_touch_updates_timestamp(self) -> None:
        """Test that touch() updates the timestamp."""
        session = Session()
        old_updated = session.updated_at

        import time
        time.sleep(0.01)

        session.touch()
        assert session.updated_at > old_updated

    def test_session_serialization(self) -> None:
        """Test session can be serialized with messages."""
        session = Session(id="test1234", project_path="/test")
        session.add_message(Message(role="user", content="Hello"))

        data = session.model_dump()
        assert data["id"] == "test1234"
        assert data["project_path"] == "/test"
        assert len(data["messages"]) == 1


class TestSummary:
    """Tests for Summary model."""

    def test_create_summary_with_defaults(self) -> None:
        """Test creating a summary with default values."""
        summary = Summary(content="Summary text")
        assert isinstance(summary.id, str)
        assert summary.content == "Summary text"
        assert summary.original_message_ids == []
        assert isinstance(summary.created_at, datetime)

    def test_create_summary_with_message_ids(self) -> None:
        """Test creating a summary with original message IDs."""
        summary = Summary(
            content="Summary",
            original_message_ids=["msg1", "msg2", "msg3"],
            metadata={"ratio": 0.3}
        )
        assert summary.original_message_ids == ["msg1", "msg2", "msg3"]
        assert summary.metadata == {"ratio": 0.3}

    def test_empty_content_raises_error(self) -> None:
        """Test that empty content raises ValidationError."""
        with pytest.raises(ValidationError):
            Summary(content="")


class TestMemoryConfig:
    """Tests for MemoryConfig model."""

    def test_create_config_with_defaults(self) -> None:
        """Test creating config with default values."""
        config = MemoryConfig()
        assert config.enabled is True
        assert config.max_messages == 20
        assert config.compression_threshold == 0.92
        assert config.token_buffer == 0.10
        assert config.storage_path == "~/.mini-coder/memory"
        assert config.max_history == 1000

    def test_create_config_with_custom_values(self) -> None:
        """Test creating config with custom values."""
        config = MemoryConfig(
            enabled=False,
            max_messages=50,
            compression_threshold=0.8,
            storage_path="/custom/path"
        )
        assert config.enabled is False
        assert config.max_messages == 50
        assert config.compression_threshold == 0.8
        assert config.storage_path == "/custom/path"

    def test_invalid_max_messages_raises_error(self) -> None:
        """Test that out-of-range max_messages raises error."""
        with pytest.raises(ValidationError):
            MemoryConfig(max_messages=4)  # Below minimum

        with pytest.raises(ValidationError):
            MemoryConfig(max_messages=101)  # Above maximum

    def test_invalid_compression_threshold_raises_error(self) -> None:
        """Test that out-of-range compression_threshold raises error."""
        with pytest.raises(ValidationError):
            MemoryConfig(compression_threshold=0.4)  # Below minimum

        with pytest.raises(ValidationError):
            MemoryConfig(compression_threshold=1.1)  # Above maximum

    def test_invalid_token_buffer_raises_error(self) -> None:
        """Test that out-of-range token_buffer raises error."""
        with pytest.raises(ValidationError):
            MemoryConfig(token_buffer=-0.1)  # Below minimum

        with pytest.raises(ValidationError):
            MemoryConfig(token_buffer=0.4)  # Above maximum
