"""Unit tests for ContextBuilder.

Tests cover the GSSC pipeline (Gather, Select, Structure, Compress).
"""

import pytest
import tempfile
from pathlib import Path

from mini_coder.memory.context_builder import ContextBuilder
from mini_coder.memory.manager import ContextMemoryManager
from mini_coder.memory.models import MemoryConfig
from mini_coder.memory.priority import Priority


class TestContextBuilder:
    """Tests for ContextBuilder class."""

    @pytest.fixture
    def temp_path(self, tmp_path: Path) -> str:
        """Create a temporary path for testing."""
        return str(tmp_path / "memory")

    @pytest.fixture
    def config(self, temp_path: str) -> MemoryConfig:
        """Create a test configuration."""
        return MemoryConfig(storage_path=temp_path)

    @pytest.fixture
    def manager(self, config: MemoryConfig) -> ContextMemoryManager:
        """Create a ContextMemoryManager instance."""
        return ContextMemoryManager(config=config)

    @pytest.fixture
    def builder(self, manager: ContextMemoryManager) -> ContextBuilder:
        """Create a ContextBuilder instance."""
        return ContextBuilder(manager=manager, max_tokens=10000)

    def test_initialization(self, manager: ContextMemoryManager) -> None:
        """Test builder initialization."""
        builder = ContextBuilder(manager=manager, max_tokens=5000)
        assert builder._max_tokens == 5000

    def test_build_empty_context(self, builder: ContextBuilder) -> None:
        """Test building context with no messages."""
        context = builder.build()
        assert context == []

    def test_build_with_messages(
        self,
        builder: ContextBuilder,
        manager: ContextMemoryManager
    ) -> None:
        """Test building context with messages."""
        manager.start_session()
        manager.add_message("user", "Hello")
        manager.add_message("assistant", "Hi there!")

        context = builder.build()

        assert len(context) == 2
        assert context[0]["role"] == "user"
        assert context[1]["role"] == "assistant"

    def test_build_respects_token_limit(
        self,
        manager: ContextMemoryManager,
        temp_path: str
    ) -> None:
        """Test that build respects token limit."""
        config = MemoryConfig(storage_path=temp_path)
        manager = ContextMemoryManager(config=config)
        builder = ContextBuilder(manager=manager, max_tokens=50)

        manager.start_session()
        # Add several messages
        for i in range(10):
            manager.add_message("user", f"Message {i} " * 20)

        context = builder.build(max_tokens=100)

        # Should not include all messages due to token limit
        assert len(context) < 10

    def test_gather_phase(
        self,
        builder: ContextBuilder,
        manager: ContextMemoryManager
    ) -> None:
        """Test the Gather phase."""
        manager.start_session()
        manager.add_message("user", "Test message")

        gathered = builder._gather(include_project_memory=False, project_path=None)

        assert len(gathered) == 1
        assert gathered[0]["content"] == "Test message"

    def test_select_phase_prioritizes(self, builder: ContextBuilder) -> None:
        """Test that Select phase prioritizes messages."""
        messages = [
            {"role": "user", "content": "Low priority", "priority": Priority.LOW},
            {"role": "user", "content": "High priority", "priority": Priority.HIGH},
            {"role": "user", "content": "Normal priority", "priority": Priority.NORMAL},
        ]

        # With low token limit, should prioritize
        selected = builder._select(messages, max_tokens=50)

        # High priority should be included
        contents = [m["content"] for m in selected]
        assert "High priority" in contents

    def test_structure_phase_orders_by_timestamp(self, builder: ContextBuilder) -> None:
        """Test that Structure phase maintains order."""
        messages = [
            {"role": "user", "content": "Second", "timestamp": "2024-01-01T12:00:00"},
            {"role": "user", "content": "First", "timestamp": "2024-01-01T11:00:00"},
        ]

        structured = builder._structure(messages)

        assert structured[0]["content"] == "First"
        assert structured[1]["content"] == "Second"

    def test_structure_phase_ensures_required_fields(self, builder: ContextBuilder) -> None:
        """Test that Structure phase ensures required fields."""
        messages = [
            {"content": "No role"},  # Missing role
            {"role": "user"},  # Missing content
        ]

        structured = builder._structure(messages)

        assert structured[0]["role"] == "user"  # Default role
        assert structured[0]["content"] == "No role"
        assert structured[1]["content"] == ""  # Default content

    def test_compress_phase(self, builder: ContextBuilder) -> None:
        """Test the Compress phase."""
        messages = [
            {"role": "user", "content": "Short"},
            {"role": "user", "content": "A" * 1000},  # Long message
        ]

        compressed = builder._compress(messages, max_tokens=100)

        # Should only include short message due to token limit
        assert len(compressed) == 1
        assert compressed[0]["content"] == "Short"

    def test_build_with_user_message(
        self,
        builder: ContextBuilder,
        manager: ContextMemoryManager
    ) -> None:
        """Test building context with a new user message."""
        manager.start_session()
        manager.add_message("user", "Previous message")

        context = builder.build_with_user_message(
            user_message="New question"
        )

        assert len(context) == 2
        assert context[-1]["role"] == "user"
        assert context[-1]["content"] == "New question"

    def test_estimate_tokens(self, builder: ContextBuilder) -> None:
        """Test token estimation."""
        messages = [
            {"role": "user", "content": "Hello world"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        tokens = builder.estimate_tokens(messages)

        assert tokens > 0


class TestContextBuilderProjectMemory:
    """Tests for project memory integration."""

    @pytest.fixture
    def temp_project(self, tmp_path: Path) -> Path:
        """Create a temporary project with CLAUDE.md."""
        project = tmp_path / "project"
        project.mkdir()
        claude_md = project / "CLAUDE.md"
        claude_md.write_text("# Project Memory\n\nThis is a test project.")
        return project

    @pytest.fixture
    def manager(self, tmp_path: Path) -> ContextMemoryManager:
        """Create a manager."""
        config = MemoryConfig(storage_path=str(tmp_path / "memory"))
        return ContextMemoryManager(config=config)

    @pytest.fixture
    def builder(self, manager: ContextMemoryManager) -> ContextBuilder:
        """Create a builder."""
        return ContextBuilder(manager=manager, max_tokens=10000)

    def test_load_project_memory(self, builder: ContextBuilder, temp_project: Path) -> None:
        """Test loading project memory from CLAUDE.md."""
        content = builder._load_project_memory(str(temp_project))

        assert content is not None
        assert "Project Memory" in content

    def test_load_project_memory_not_found(self, builder: ContextBuilder, tmp_path: Path) -> None:
        """Test loading project memory when CLAUDE.md doesn't exist."""
        content = builder._load_project_memory(str(tmp_path))
        assert content is None

    def test_build_with_project_memory(
        self,
        builder: ContextBuilder,
        manager: ContextMemoryManager,
        temp_project: Path
    ) -> None:
        """Test building context with project memory included."""
        manager.start_session()
        manager.add_message("user", "Hello")

        context = builder.build(
            include_project_memory=True,
            project_path=str(temp_project)
        )

        # Should include project memory as system message
        system_messages = [m for m in context if m["role"] == "system"]
        assert len(system_messages) == 1
        assert "Project Memory" in system_messages[0]["content"]
