"""Tests for Note Relations functionality."""

import pytest
from pathlib import Path

from mini_coder.memory import (
    ProjectNotesManager,
    NoteCategory,
    NoteStatus,
)
from mini_coder.memory.note_relations import (
    RelationType,
    NoteRelation,
    NoteRelationManager,
    AutoRelationDetector,
    CATEGORY_AFFINITY,
    REVERSE_RELATIONS,
)


class TestRelationType:
    """Tests for RelationType enum."""

    def test_all_relation_types_exist(self) -> None:
        """Test that all expected relation types exist."""
        expected = {"related_to", "depends_on", "blocks", "implements", "supersedes", "derived_from"}
        actual = {rt.value for rt in RelationType}
        assert expected == actual

    def test_relation_type_values(self) -> None:
        """Test relation type string values."""
        assert RelationType.RELATED_TO.value == "related_to"
        assert RelationType.DEPENDS_ON.value == "depends_on"
        assert RelationType.BLOCKS.value == "blocks"


class TestNoteRelation:
    """Tests for NoteRelation model."""

    def test_create_relation(self) -> None:
        """Test creating a note relation."""
        relation = NoteRelation(
            source_id="note1",
            target_id="note2",
            relation_type=RelationType.DEPENDS_ON.value
        )

        assert relation.source_id == "note1"
        assert relation.target_id == "note2"
        assert relation.relation_type == "depends_on"
        assert relation.id is not None

    def test_relation_with_metadata(self) -> None:
        """Test relation with metadata."""
        relation = NoteRelation(
            source_id="n1",
            target_id="n2",
            relation_type=RelationType.RELATED_TO.value,
            metadata={"auto_detected": True, "confidence": 0.85}
        )

        assert relation.metadata["auto_detected"] is True
        assert relation.metadata["confidence"] == 0.85


class TestNoteRelationManager:
    """Tests for NoteRelationManager."""

    @pytest.fixture
    def temp_storage(self, tmp_path: Path) -> Path:
        """Create a temporary storage directory."""
        storage = tmp_path / "notes"
        storage.mkdir()
        return storage

    @pytest.fixture
    def notes_manager(self, temp_storage: Path) -> ProjectNotesManager:
        """Create a notes manager."""
        return ProjectNotesManager(storage_path=str(temp_storage))

    @pytest.fixture
    def manager(self, notes_manager: ProjectNotesManager) -> NoteRelationManager:
        """Create a relation manager."""
        return NoteRelationManager(notes_manager)

    def test_add_relation(self, manager: NoteRelationManager, notes_manager: ProjectNotesManager) -> None:
        """Test adding a relation between notes."""
        notes_manager.set_project("/test/project")

        n1 = notes_manager.add_note(NoteCategory.DECISION, "Use FastAPI", "Decided")
        n2 = notes_manager.add_note(NoteCategory.TODO, "Add tests", "Need tests")

        relation = manager.add_relation(n1.id, n2.id, RelationType.RELATED_TO)

        assert relation is not None
        assert relation.source_id == n1.id
        assert relation.target_id == n2.id

        # Check note was updated
        note1 = notes_manager.get_note(n1.id)
        assert n2.id in note1.relations

    def test_add_bidirectional_relation(self, manager: NoteRelationManager, notes_manager: ProjectNotesManager) -> None:
        """Test adding bidirectional relation."""
        notes_manager.set_project("/test/project")

        n1 = notes_manager.add_note(NoteCategory.TODO, "Task 1", "First")
        n2 = notes_manager.add_note(NoteCategory.TODO, "Task 2", "Second")

        manager.add_relation(n1.id, n2.id, RelationType.DEPENDS_ON, bidirectional=True)

        # Both notes should have relations
        note1 = notes_manager.get_note(n1.id)
        note2 = notes_manager.get_note(n2.id)

        assert n2.id in note1.relations
        assert n1.id in note2.relations

    def test_remove_relation(self, manager: NoteRelationManager, notes_manager: ProjectNotesManager) -> None:
        """Test removing a relation."""
        notes_manager.set_project("/test/project")

        n1 = notes_manager.add_note(NoteCategory.INFO, "Note 1", "Content")
        n2 = notes_manager.add_note(NoteCategory.INFO, "Note 2", "Content")

        manager.add_relation(n1.id, n2.id, RelationType.RELATED_TO)

        result = manager.remove_relation(n1.id, n2.id)

        assert result is True

        note1 = notes_manager.get_note(n1.id)
        assert n2.id not in note1.relations

    def test_get_relations(self, manager: NoteRelationManager, notes_manager: ProjectNotesManager) -> None:
        """Test getting relations for a note."""
        notes_manager.set_project("/test/project")

        n1 = notes_manager.add_note(NoteCategory.DECISION, "Main", "Main decision")
        n2 = notes_manager.add_note(NoteCategory.TODO, "Task 1", "Task")
        n3 = notes_manager.add_note(NoteCategory.TODO, "Task 2", "Task")

        manager.add_relation(n1.id, n2.id, RelationType.RELATED_TO)
        manager.add_relation(n1.id, n3.id, RelationType.DEPENDS_ON)

        relations = manager.get_relations(n1.id)

        assert len(relations) == 2

    def test_get_related_notes_depth_1(self, manager: NoteRelationManager, notes_manager: ProjectNotesManager) -> None:
        """Test getting related notes at depth 1."""
        notes_manager.set_project("/test/project")

        n1 = notes_manager.add_note(NoteCategory.DECISION, "Main", "Main")
        n2 = notes_manager.add_note(NoteCategory.TODO, "Task", "Task")
        n3 = notes_manager.add_note(NoteCategory.BLOCK, "Blocker", "Block")

        manager.add_relation(n1.id, n2.id, RelationType.RELATED_TO)
        manager.add_relation(n2.id, n3.id, RelationType.DEPENDS_ON)

        related = manager.get_related_notes(n1.id, depth=1)

        assert "1" in related
        assert n2.id in related["1"]
        assert n3.id not in related["1"]  # Not at depth 1

    def test_get_related_notes_depth_2(self, manager: NoteRelationManager, notes_manager: ProjectNotesManager) -> None:
        """Test getting related notes at depth 2."""
        notes_manager.set_project("/test/project")

        n1 = notes_manager.add_note(NoteCategory.DECISION, "Main", "Main")
        n2 = notes_manager.add_note(NoteCategory.TODO, "Task", "Task")
        n3 = notes_manager.add_note(NoteCategory.BLOCK, "Blocker", "Block")

        manager.add_relation(n1.id, n2.id, RelationType.RELATED_TO)
        manager.add_relation(n2.id, n3.id, RelationType.DEPENDS_ON)

        related = manager.get_related_notes(n1.id, depth=2)

        assert "1" in related
        assert "2" in related
        assert n2.id in related["1"]
        assert n3.id in related["2"]


class TestAutoRelationDetector:
    """Tests for AutoRelationDetector."""

    @pytest.fixture
    def temp_storage(self, tmp_path: Path) -> Path:
        """Create a temporary storage directory."""
        storage = tmp_path / "notes"
        storage.mkdir()
        return storage

    @pytest.fixture
    def notes_manager(self, temp_storage: Path) -> ProjectNotesManager:
        """Create a notes manager."""
        return ProjectNotesManager(storage_path=str(temp_storage))

    @pytest.fixture
    def relation_manager(self, notes_manager: ProjectNotesManager) -> NoteRelationManager:
        """Create a relation manager."""
        return NoteRelationManager(notes_manager)

    @pytest.fixture
    def detector(self, notes_manager: ProjectNotesManager, relation_manager: NoteRelationManager) -> AutoRelationDetector:
        """Create an auto relation detector with low threshold for testing."""
        return AutoRelationDetector(notes_manager, relation_manager, similarity_threshold=0.2)

    def test_detect_relations_by_tag(self, detector: AutoRelationDetector, notes_manager: ProjectNotesManager) -> None:
        """Test detecting relations by tag similarity."""
        notes_manager.set_project("/test/project")

        n1 = notes_manager.add_note(NoteCategory.DECISION, "Use FastAPI", "Decided on FastAPI", tags=["api", "backend"])
        n2 = notes_manager.add_note(NoteCategory.TODO, "Add API tests", "Test the API", tags=["api", "testing"])

        candidates = detector.detect_relations(n1)

        # Should detect relation due to shared "api" tag
        assert len(candidates) >= 1
        assert any(n2.id == c[0] for c in candidates)

    def test_detect_relations_by_content(self, detector: AutoRelationDetector, notes_manager: ProjectNotesManager) -> None:
        """Test detecting relations by content similarity."""
        notes_manager.set_project("/test/project")

        n1 = notes_manager.add_note(NoteCategory.DECISION, "Database choice", "Use PostgreSQL for database storage")
        n2 = notes_manager.add_note(NoteCategory.TODO, "Setup database", "Configure PostgreSQL database connection")

        candidates = detector.detect_relations(n1)

        # Should detect relation due to shared "PostgreSQL" and "database"
        assert len(candidates) >= 1

    def test_no_relation_to_self(self, detector: AutoRelationDetector, notes_manager: ProjectNotesManager) -> None:
        """Test that notes don't relate to themselves."""
        notes_manager.set_project("/test/project")

        note = notes_manager.add_note(NoteCategory.INFO, "Test", "Content", tags=["test"])

        candidates = detector.detect_relations(note)

        # Should not include self
        assert not any(note.id == c[0] for c in candidates)

    def test_auto_link_creates_relations(self, notes_manager: ProjectNotesManager, relation_manager: NoteRelationManager) -> None:
        """Test that auto_link=True creates relations."""
        detector = AutoRelationDetector(notes_manager, relation_manager, similarity_threshold=0.3)
        notes_manager.set_project("/test/project")

        n1 = notes_manager.add_note(NoteCategory.DECISION, "Use Redis", "For caching", tags=["cache"])
        n2 = notes_manager.add_note(NoteCategory.TODO, "Add caching", "Implement cache layer", tags=["cache"])

        candidates = detector.detect_relations(n1, auto_link=True)

        # Relation should be created
        note1 = notes_manager.get_note(n1.id)
        assert n2.id in note1.relations

    def test_category_affinity_inference(self, detector: AutoRelationDetector, notes_manager: ProjectNotesManager) -> None:
        """Test that relation type is inferred from category affinity."""
        notes_manager.set_project("/test/project")

        decision = notes_manager.add_note(NoteCategory.DECISION, "Architecture", "Use microservices")
        todo = notes_manager.add_note(NoteCategory.TODO, "Implement", "Build the services", tags=["microservices"])

        candidates = detector.detect_relations(decision)

        if candidates:
            # decision -> todo should suggest related_to
            rel_type = candidates[0][1]
            assert rel_type == RelationType.RELATED_TO


class TestCategoryAffinityRules:
    """Tests for category affinity rules."""

    def test_affinity_rules_exist(self) -> None:
        """Test that affinity rules are defined."""
        assert len(CATEGORY_AFFINITY) > 0

    def test_decision_todo_affinity(self) -> None:
        """Test decision -> todo affinity."""
        assert CATEGORY_AFFINITY.get(("decision", "todo")) == RelationType.RELATED_TO

    def test_todo_block_affinity(self) -> None:
        """Test todo -> block affinity."""
        assert CATEGORY_AFFINITY.get(("todo", "block")) == RelationType.DEPENDS_ON


class TestReverseRelations:
    """Tests for reverse relation mappings."""

    def test_reverse_relations_defined(self) -> None:
        """Test that reverse relations are defined for all types."""
        for rt in RelationType:
            assert rt in REVERSE_RELATIONS

    def test_supersedes_reverse_is_derived_from(self) -> None:
        """Test that supersedes reverses to derived_from."""
        assert REVERSE_RELATIONS[RelationType.SUPERSEDES] == RelationType.DERIVED_FROM
