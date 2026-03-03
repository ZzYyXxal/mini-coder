"""Tests for Project Notes system (NoteTool-like functionality)."""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from mini_coder.memory import (
    ProjectNote,
    ProjectNotesManager,
    NoteCategory,
    NoteStatus,
)


class TestProjectNote:
    """Tests for ProjectNote model."""

    def test_create_note(self) -> None:
        """Test creating a basic note."""
        note = ProjectNote(
            category=NoteCategory.DECISION,
            title="Use PostgreSQL",
            content="Decided to use PostgreSQL for primary database"
        )

        assert note.category == "decision"
        assert note.title == "Use PostgreSQL"
        assert note.status == NoteStatus.ACTIVE
        assert note.is_active() is True

    def test_note_with_tags(self) -> None:
        """Test note with tags."""
        note = ProjectNote(
            category=NoteCategory.TODO,
            title="Add tests",
            content="Need to add unit tests",
            tags=["testing", "priority"]
        )

        assert "testing" in note.tags
        assert "priority" in note.tags

    def test_format_for_context(self) -> None:
        """Test formatting note for context."""
        note = ProjectNote(
            category=NoteCategory.DECISION,
            title="Architecture Decision",
            content="We chose FastAPI over Flask"
        )

        formatted = note.format_for_context()

        assert "Architecture Decision" in formatted
        assert "FastAPI" in formatted

    def test_touch_updates_timestamp(self) -> None:
        """Test that touch() updates timestamp."""
        note = ProjectNote(
            category=NoteCategory.INFO,
            title="Test",
            content="Content"
        )
        original_time = note.updated_at

        note.touch()

        assert note.updated_at >= original_time


class TestProjectNotesManager:
    """Tests for ProjectNotesManager."""

    @pytest.fixture
    def temp_storage(self, tmp_path: Path) -> Path:
        """Create a temporary storage directory."""
        storage = tmp_path / "notes"
        storage.mkdir()
        return storage

    @pytest.fixture
    def manager(self, temp_storage: Path) -> ProjectNotesManager:
        """Create a manager with temporary storage."""
        return ProjectNotesManager(storage_path=str(temp_storage))

    def test_add_note(self, manager: ProjectNotesManager) -> None:
        """Test adding a note."""
        manager.set_project("/test/project")

        note = manager.add_note(
            category=NoteCategory.DECISION,
            title="Use Redis",
            content="For caching layer"
        )

        assert note.id is not None
        assert note.title == "Use Redis"

    def test_get_notes(self, manager: ProjectNotesManager) -> None:
        """Test retrieving notes."""
        manager.set_project("/test/project")

        manager.add_note(NoteCategory.TODO, "Task 1", "Do something")
        manager.add_note(NoteCategory.TODO, "Task 2", "Do another thing")
        manager.add_note(NoteCategory.DECISION, "Decision 1", "Decided")

        todos = manager.get_notes(category=NoteCategory.TODO)
        assert len(todos) == 2

        all_active = manager.get_notes()
        assert len(all_active) == 3

    def test_update_note(self, manager: ProjectNotesManager) -> None:
        """Test updating a note."""
        manager.set_project("/test/project")

        note = manager.add_note(NoteCategory.TODO, "Original", "Original content")

        updated = manager.update_note(note.id, title="Updated", content="Updated content")

        assert updated is not None
        assert updated.title == "Updated"
        assert updated.content == "Updated content"

    def test_complete_note(self, manager: ProjectNotesManager) -> None:
        """Test completing a todo note."""
        manager.set_project("/test/project")

        note = manager.add_note(NoteCategory.TODO, "Task", "Complete me")

        result = manager.complete_note(note.id)

        assert result is not None
        assert result.status == NoteStatus.COMPLETED

        # Should not appear in active notes
        active = manager.get_notes(active_only=True)
        assert len(active) == 0

    def test_delete_note(self, manager: ProjectNotesManager) -> None:
        """Test deleting a note."""
        manager.set_project("/test/project")

        note = manager.add_note(NoteCategory.INFO, "Info", "Some info")

        result = manager.delete_note(note.id)
        assert result is True

        # Should not be retrievable
        deleted = manager.get_note(note.id)
        assert deleted is None

    def test_search_notes(self, manager: ProjectNotesManager) -> None:
        """Test searching notes."""
        manager.set_project("/test/project")

        manager.add_note(NoteCategory.DECISION, "Use FastAPI", "For web API")
        manager.add_note(NoteCategory.PATTERN, "Repository Pattern", "Use repo pattern")
        manager.add_note(NoteCategory.TODO, "Add FastAPI tests", "Test the API")

        results = manager.search_notes("FastAPI")

        assert len(results) == 2

    def test_format_notes_for_context(self, manager: ProjectNotesManager) -> None:
        """Test formatting notes for context."""
        manager.set_project("/test/project")

        manager.add_note(NoteCategory.DECISION, "Architecture", "Use microservices")
        manager.add_note(NoteCategory.TODO, "Add tests", "Write unit tests")

        formatted = manager.format_notes_for_context()

        assert "Architecture" in formatted
        assert "Add tests" in formatted
        assert "Project Notes" in formatted

    def test_persistence(self, temp_storage: Path) -> None:
        """Test that notes persist across manager instances."""
        project_path = "/test/persistence"

        # First manager: add notes
        manager1 = ProjectNotesManager(storage_path=str(temp_storage))
        manager1.set_project(project_path)
        note = manager1.add_note(NoteCategory.DECISION, "Persist me", "This should persist")

        # Second manager: load notes
        manager2 = ProjectNotesManager(storage_path=str(temp_storage))
        manager2.set_project(project_path)

        notes = manager2.get_notes()
        assert len(notes) == 1
        assert notes[0].title == "Persist me"

    def test_different_projects(self, manager: ProjectNotesManager) -> None:
        """Test that notes are isolated by project."""
        # Add notes for project A
        manager.set_project("/project/a")
        manager.add_note(NoteCategory.TODO, "Project A task", "Do A stuff")

        # Add notes for project B
        manager.set_project("/project/b")
        manager.add_note(NoteCategory.TODO, "Project B task", "Do B stuff")

        # Check project B only has its own notes
        notes_b = manager.get_notes()
        assert len(notes_b) == 1
        assert notes_b[0].title == "Project B task"

        # Switch back to project A
        manager.set_project("/project/a")
        notes_a = manager.get_notes()
        assert len(notes_a) == 1
        assert notes_a[0].title == "Project A task"

    def test_get_stats(self, manager: ProjectNotesManager) -> None:
        """Test getting note statistics."""
        manager.set_project("/test/project")

        manager.add_note(NoteCategory.TODO, "Task 1", "Do 1")
        manager.add_note(NoteCategory.TODO, "Task 2", "Do 2")
        manager.add_note(NoteCategory.DECISION, "Decision", "Decided")

        note = manager.add_note(NoteCategory.TODO, "Task 3", "Do 3")
        manager.complete_note(note.id)

        stats = manager.get_stats()

        assert stats["total"] == 4
        assert stats["active"] == 3  # 3 active, 1 completed
        assert stats["by_category"]["todo"] == 3
        assert stats["by_category"]["decision"] == 1

    def test_max_notes_limit(self, manager: ProjectNotesManager) -> None:
        """Test max_notes parameter in format_notes_for_context."""
        manager.set_project("/test/project")

        # Add more notes than the limit
        for i in range(20):
            manager.add_note(NoteCategory.TODO, f"Task {i}", f"Content {i}")

        formatted = manager.format_notes_for_context(max_notes=5)

        # Should only include 5 notes
        # (This is a rough check - the actual format may vary)
        assert "Task 19" in formatted  # Most recent
        assert formatted.count("Task") <= 6  # Header + 5 notes


class TestProjectNotesIntegration:
    """Integration tests for ProjectNotes with LLMService."""

    @pytest.fixture
    def temp_config_dir(self, tmp_path: Path) -> Path:
        """Create a temporary config directory."""
        import uuid
        unique_id = uuid.uuid4().hex[:8]

        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Create LLM config
        llm_config = config_dir / "llm.yaml"
        llm_config.write_text("""
default_provider: zhipu
providers:
  zhipu:
    api_key: test-key
    base_url: https://test.api/
    model: test-model
""")

        # Create memory config with unique storage path
        memory_config = config_dir / "memory.yaml"
        memory_config.write_text(f"""
enabled: true
max_messages: 10
compression_threshold: 0.92
storage_path: ~/.mini-coder/test-memory-{unique_id}
""")

        return config_dir

    def test_service_has_notes_manager(self, temp_config_dir: Path) -> None:
        """Test that LLMService initializes with notes manager."""
        from mini_coder.llm.service import LLMService

        config_path = str(temp_config_dir / "llm.yaml")
        service = LLMService(config_path, enable_memory=True, enable_notes=True)

        assert service.notes_enabled is True

    def test_service_add_note(self, temp_config_dir: Path) -> None:
        """Test adding notes through LLMService."""
        import uuid
        from mini_coder.llm.service import LLMService

        config_path = str(temp_config_dir / "llm.yaml")
        service = LLMService(config_path, enable_memory=True, enable_notes=True)

        # Use unique project path to avoid collision
        unique_project = f"/test/project/{uuid.uuid4().hex[:8]}"
        service.start_session(unique_project)

        note_id = service.add_decision(
            title="Use FastAPI",
            content="Chose FastAPI for async support"
        )

        assert note_id is not None

        notes = service.list_notes()
        assert len(notes) == 1
        assert notes[0]["title"] == "Use FastAPI"

    def test_service_todo_workflow(self, temp_config_dir: Path) -> None:
        """Test todo workflow through LLMService."""
        import uuid
        from mini_coder.llm.service import LLMService

        config_path = str(temp_config_dir / "llm.yaml")
        service = LLMService(config_path, enable_memory=True, enable_notes=True)

        # Use unique project path to avoid collision
        unique_project = f"/test/project/{uuid.uuid4().hex[:8]}"
        service.start_session(unique_project)

        # Add todos
        todo_id = service.add_todo("Write tests", "Add unit tests for memory module")

        # List active todos
        todos = service.list_notes(category="todo")
        assert len(todos) == 1

        # Complete todo
        result = service.complete_todo(todo_id)
        assert result is True

        # Should not appear in active todos
        active_todos = service.list_notes(category="todo", active_only=True)
        assert len(active_todos) == 0

    def test_service_search_notes(self, temp_config_dir: Path) -> None:
        """Test searching notes through LLMService."""
        import uuid
        from mini_coder.llm.service import LLMService

        config_path = str(temp_config_dir / "llm.yaml")
        service = LLMService(config_path, enable_memory=True, enable_notes=True)

        # Use unique project path to avoid collision
        unique_project = f"/test/project/{uuid.uuid4().hex[:8]}"
        service.start_session(unique_project)

        service.add_decision("Database choice", "Use PostgreSQL")
        service.add_pattern("Repository pattern", "Use repository pattern for data access")

        results = service.search_notes("pattern")
        assert len(results) == 1
        assert "Repository" in results[0]["title"]
