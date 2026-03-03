"""Tests for NoteExtractor functionality."""

import pytest

from mini_coder.memory.note_extractor import (
    NoteExtractor,
    ExtractedNote,
    ExtractionSource,
    EXTRACTION_PATTERNS,
)


class TestExtractedNote:
    """Tests for ExtractedNote model."""

    def test_create_extracted_note(self) -> None:
        """Test creating an extracted note."""
        note = ExtractedNote(
            category="decision",
            title="Use FastAPI",
            content="Decided to use FastAPI for async support",
            confidence=0.9,
            source=ExtractionSource.RULE
        )

        assert note.category == "decision"
        assert note.title == "Use FastAPI"
        assert note.confidence == 0.9
        assert note.source == "rule"

    def test_extracted_note_with_original_text(self) -> None:
        """Test extracted note preserves original text."""
        note = ExtractedNote(
            category="todo",
            title="Add tests",
            content="Add unit tests",
            confidence=0.85,
            source=ExtractionSource.RULE,
            original_text="need to add unit tests"
        )

        assert note.original_text == "need to add unit tests"


class TestNoteExtractor:
    """Tests for NoteExtractor class."""

    @pytest.fixture
    def extractor(self) -> NoteExtractor:
        """Create a NoteExtractor instance."""
        return NoteExtractor()

    def test_extract_decision_english(self, extractor: NoteExtractor) -> None:
        """Test extracting decision from English text."""
        text = "We decided to use FastAPI for better async support"
        notes = extractor.extract(text)

        assert len(notes) >= 1
        decision = notes[0]
        assert decision.category == "decision"
        assert "FastAPI" in decision.content
        assert decision.confidence >= 0.7

    def test_extract_decision_chinese(self, extractor: NoteExtractor) -> None:
        """Test extracting decision from Chinese text."""
        text = "我们决定采用 PostgreSQL 作为主数据库"
        notes = extractor.extract(text)

        assert len(notes) >= 1
        decision = notes[0]
        assert decision.category == "decision"
        assert "PostgreSQL" in decision.content

    def test_extract_todo_english(self, extractor: NoteExtractor) -> None:
        """Test extracting todo from English text."""
        text = "TODO: Add unit tests for the extractor"
        notes = extractor.extract(text)

        assert len(notes) >= 1
        todo = notes[0]
        assert todo.category == "todo"
        assert "unit tests" in todo.content.lower()

    def test_extract_todo_chinese(self, extractor: NoteExtractor) -> None:
        """Test extracting todo from Chinese text."""
        text = "需要完成用户认证功能"
        notes = extractor.extract(text)

        assert len(notes) >= 1
        todo = notes[0]
        assert todo.category == "todo"

    def test_extract_block_english(self, extractor: NoteExtractor) -> None:
        """Test extracting block from English text."""
        text = "blocked by: missing API credentials"
        notes = extractor.extract(text)

        assert len(notes) >= 1
        block = notes[0]
        assert block.category == "block"

    def test_extract_block_chinese(self, extractor: NoteExtractor) -> None:
        """Test extracting block from Chinese text."""
        text = "阻塞问题: 依赖包未安装"
        notes = extractor.extract(text)

        assert len(notes) >= 1
        block = notes[0]
        assert block.category == "block"

    def test_extract_pattern(self, extractor: NoteExtractor) -> None:
        """Test extracting pattern."""
        text = "Use repository pattern for data access"
        notes = extractor.extract(text)

        assert len(notes) >= 1
        pattern = notes[0]
        assert pattern.category == "pattern"

    def test_extract_multiple_notes(self, extractor: NoteExtractor) -> None:
        """Test extracting multiple notes from text."""
        text = """
        We decided to use FastAPI for the backend.
        TODO: Add authentication middleware.
        blocked by: database connection issues.
        """
        notes = extractor.extract(text)

        categories = {n.category for n in notes}
        assert "decision" in categories
        assert "todo" in categories
        assert "block" in categories

    def test_no_extraction_from_plain_text(self, extractor: NoteExtractor) -> None:
        """Test that plain text without patterns extracts nothing."""
        text = "This is just a regular sentence about the weather."
        notes = extractor.extract(text)

        assert len(notes) == 0

    def test_empty_content_returns_empty(self, extractor: NoteExtractor) -> None:
        """Test that empty content returns empty list."""
        assert extractor.extract("") == []
        assert extractor.extract("   ") == []

    def test_confidence_threshold(self) -> None:
        """Test confidence threshold filtering."""
        extractor = NoteExtractor(confidence_threshold=0.9)
        text = "We decided to use FastAPI"

        notes = extractor.extract(text)

        # All returned notes should meet threshold
        for note in notes:
            assert note.confidence >= 0.9

    def test_max_notes_per_category(self) -> None:
        """Test limiting notes per category."""
        extractor = NoteExtractor(max_notes_per_category=2)
        text = """
        TODO: First task
        TODO: Second task
        TODO: Third task
        TODO: Fourth task
        """

        notes = extractor.extract(text)

        # Should have at most 2 todos
        todos = [n for n in notes if n.category == "todo"]
        assert len(todos) <= 2

    def test_notes_sorted_by_confidence(self, extractor: NoteExtractor) -> None:
        """Test that notes are sorted by confidence."""
        text = """
        We decided to use FastAPI.
        need to add tests
        """
        notes = extractor.extract(text)

        if len(notes) > 1:
            for i in range(len(notes) - 1):
                assert notes[i].confidence >= notes[i + 1].confidence

    def test_title_generation(self, extractor: NoteExtractor) -> None:
        """Test that titles are generated correctly."""
        text = "TODO: Implement user authentication"
        notes = extractor.extract(text)

        assert len(notes) >= 1
        assert notes[0].title  # Should have a title
        assert "TODO" in notes[0].title or "auth" in notes[0].title.lower()


class TestExtractionPatterns:
    """Tests for extraction patterns configuration."""

    def test_patterns_exist_for_all_categories(self) -> None:
        """Test that patterns exist for all note categories."""
        required_categories = {"decision", "todo", "block", "pattern", "info"}

        assert required_categories.issubset(set(EXTRACTION_PATTERNS.keys()))

    def test_patterns_are_tuples(self) -> None:
        """Test that patterns are (pattern, confidence) tuples."""
        for category, patterns in EXTRACTION_PATTERNS.items():
            for pattern, confidence in patterns:
                assert isinstance(pattern, str)
                assert isinstance(confidence, float)
                assert 0.0 <= confidence <= 1.0
