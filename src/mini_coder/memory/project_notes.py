"""Project Notes system for persistent structured information.

This module provides NoteTool-like functionality for managing
structured project information that persists across sessions.

Unlike conversation messages which get compressed and discarded,
project notes are long-lived and explicitly managed.

Note Categories:
- decision: Architecture or design decisions made
- todo: Active tasks and pending work
- pattern: Code patterns and conventions discovered
- info: Important information about the project
- block: Blockers and issues encountered
"""

import json
from datetime import datetime
from enum import IntEnum
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class NoteCategory(str):
    """Categories for project notes."""
    DECISION = "decision"  # Architecture/design decisions
    TODO = "todo"         # Active tasks
    PATTERN = "pattern"   # Code patterns/conventions
    INFO = "info"         # Important information
    BLOCK = "block"       # Blockers/issues


class NoteStatus(IntEnum):
    """Status for project notes."""
    ACTIVE = 0      # Currently relevant
    COMPLETED = 1   # Task completed (for todos)
    ARCHIVED = 2    # No longer active but kept for reference
    RESOLVED = 3    # Blocker resolved


class ProjectNote(BaseModel):
    """A structured note about the project.

    Unlike conversation messages, notes are:
    - Explicitly created (not automatic)
    - Long-lived (never compressed)
    - Structured (category, status, tags)
    - Searchable (by category, tags, content)

    Attributes:
        id: Unique identifier.
        category: Type of note (decision, todo, pattern, info, block).
        title: Short title for the note.
        content: Full content (supports Markdown).
        status: Current status of the note.
        tags: List of tags for organization.
        project_path: Associated project path.
        created_at: When the note was created.
        updated_at: When the note was last updated.
        metadata: Additional metadata.
        relations: IDs of related notes.
        relation_types: Map of note_id -> relation_type.
        embedding: Vector embedding for semantic search.
        embedding_model: Model used to generate embedding.
    """

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    category: str = Field(default=NoteCategory.INFO)
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    status: int = Field(default=NoteStatus.ACTIVE)
    tags: list[str] = Field(default_factory=list)
    project_path: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Relation support
    relations: list[str] = Field(
        default_factory=list,
        description="IDs of related notes"
    )
    relation_types: dict[str, str] = Field(
        default_factory=dict,
        description="Map of note_id -> relation_type"
    )
    # Semantic search support
    embedding: Optional[list[float]] = Field(
        default=None,
        description="Vector embedding for semantic search"
    )
    embedding_model: Optional[str] = Field(
        default=None,
        description="Model used to generate embedding"
    )

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now()

    def is_active(self) -> bool:
        """Check if note is still active."""
        return self.status == NoteStatus.ACTIVE

    def add_relation(
        self,
        note_id: str,
        relation_type: str = "related_to"
    ) -> None:
        """Add a relation to another note.

        Args:
            note_id: ID of the related note.
            relation_type: Type of relation (related_to, depends_on, etc.).
        """
        if note_id not in self.relations:
            self.relations.append(note_id)
            self.relation_types[note_id] = relation_type
            self.touch()

    def remove_relation(self, note_id: str) -> None:
        """Remove a relation to another note.

        Args:
            note_id: ID of the note to remove relation to.
        """
        if note_id in self.relations:
            self.relations.remove(note_id)
            self.relation_types.pop(note_id, None)
            self.touch()

    def get_related_notes(
        self,
        relation_type: Optional[str] = None
    ) -> list[str]:
        """Get IDs of related notes.

        Args:
            relation_type: Optional filter by relation type.

        Returns:
            List of related note IDs.
        """
        if relation_type is None:
            return self.relations.copy()
        return [
            nid for nid in self.relations
            if self.relation_types.get(nid) == relation_type
        ]

    def needs_embedding(self, model_name: str) -> bool:
        """Check if note needs (re)embedding.

        Args:
            model_name: The embedding model name to check against.

        Returns:
            True if embedding is missing or from a different model.
        """
        return self.embedding is None or self.embedding_model != model_name

    def format_for_context(self) -> str:
        """Format note for inclusion in LLM context."""
        status_marker = {
            NoteStatus.ACTIVE: "📋",
            NoteStatus.COMPLETED: "✅",
            NoteStatus.ARCHIVED: "📁",
            NoteStatus.RESOLVED: "✔️",
        }.get(self.status, "")

        category_marker = {
            NoteCategory.DECISION: "🎯",
            NoteCategory.TODO: "📝",
            NoteCategory.PATTERN: "🔄",
            NoteCategory.INFO: "ℹ️",
            NoteCategory.BLOCK: "🚫",
        }.get(self.category, "📌")

        tags_str = f" [{', '.join(self.tags)}]" if self.tags else ""

        return f"{category_marker} **{self.title}**{tags_str}\n{self.content}"

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "note123",
                    "category": "decision",
                    "title": "Use PostgreSQL for primary database",
                    "content": "Decided to use PostgreSQL instead of MySQL because:\n- Better JSON support\n- More robust transaction handling\n- Team familiarity",
                    "status": 0,
                    "tags": ["architecture", "database"],
                    "project_path": "/home/user/my-project",
                    "created_at": "2024-01-15T10:00:00",
                    "updated_at": "2024-01-15T10:00:00",
                }
            ]
        }
    }


class ProjectNotesManager:
    """Manager for project notes with persistence.

    Provides CRUD operations and context formatting for project notes.
    Notes are stored per-project and persist across sessions.

    Example:
        >>> manager = ProjectNotesManager()
        >>> note = manager.add_note(
        ...     category="decision",
        ...     title="Use FastAPI",
        ...     content="Chose FastAPI for async support"
        ... )
        >>> context = manager.format_notes_for_context()
    """

    def __init__(
        self,
        storage_path: str = "~/.mini-coder/notes",
        enable_semantic_search: bool = False,
        enable_relations: bool = True,
        auto_detect_relations: bool = False,
        relation_threshold: float = 0.75
    ):
        """Initialize the notes manager.

        Args:
            storage_path: Base path for note storage.
            enable_semantic_search: Enable semantic search (requires embeddings).
            enable_relations: Enable note relations.
            auto_detect_relations: Automatically detect relations for new notes.
            relation_threshold: Similarity threshold for auto-detection.
        """
        self.path = Path(storage_path).expanduser()
        self.path.mkdir(parents=True, exist_ok=True)

        # Cache of notes by project
        self._notes: dict[str, list[ProjectNote]] = {}
        self._current_project: Optional[str] = None

        # Semantic search (optional)
        self._semantic_search = None
        self._enable_semantic_search = enable_semantic_search
        if enable_semantic_search:
            try:
                from .embeddings import LocalEmbeddingService
                from .semantic_search import SemanticNoteSearch
                embedding_service = LocalEmbeddingService()
                if embedding_service.is_available:
                    self._semantic_search = SemanticNoteSearch(self, embedding_service)
            except ImportError:
                pass

        # Note relations (optional)
        self._relation_manager = None
        self._auto_detect_relations = auto_detect_relations
        self._relation_threshold = relation_threshold
        if enable_relations:
            try:
                from .note_relations import NoteRelationManager, AutoRelationDetector
                self._relation_manager = NoteRelationManager(self)
                self._auto_detector = AutoRelationDetector(
                    self,
                    self._relation_manager,
                    similarity_threshold=relation_threshold
                )
            except ImportError:
                pass

    def set_project(self, project_path: Optional[str]) -> None:
        """Set the current project context.

        Args:
            project_path: Path to the current project.
        """
        self._current_project = project_path
        if project_path:
            self._load_project_notes(project_path)

    def _get_project_key(self, project_path: Optional[str] = None) -> str:
        """Get storage key for a project."""
        path = project_path or self._current_project or "global"
        # Create a safe filename from the path
        return path.replace("/", "_").replace("\\", "_")[:50]

    def _load_project_notes(self, project_path: str) -> None:
        """Load notes for a project from disk."""
        key = self._get_project_key(project_path)
        if key in self._notes:
            return

        notes_file = self.path / f"{key}.json"
        if not notes_file.exists():
            self._notes[key] = []
            return

        try:
            content = notes_file.read_text(encoding="utf-8")
            notes_data = json.loads(content)

            notes = []
            for item in notes_data:
                # Parse datetime strings
                for field in ["created_at", "updated_at"]:
                    if isinstance(item.get(field), str):
                        item[field] = datetime.fromisoformat(item[field])
                notes.append(ProjectNote(**item))

            self._notes[key] = notes
        except (json.JSONDecodeError, Exception):
            self._notes[key] = []

    def _save_project_notes(self, project_path: Optional[str] = None) -> None:
        """Save notes for a project to disk."""
        key = self._get_project_key(project_path)
        if key not in self._notes:
            return

        notes_file = self.path / f"{key}.json"

        # Serialize notes
        notes_data = []
        for note in self._notes[key]:
            note_dict = note.model_dump()
            note_dict["created_at"] = note_dict["created_at"].isoformat()
            note_dict["updated_at"] = note_dict["updated_at"].isoformat()
            notes_data.append(note_dict)

        notes_file.write_text(
            json.dumps(notes_data, indent=2),
            encoding="utf-8"
        )

    def add_note(
        self,
        category: str,
        title: str,
        content: str,
        tags: Optional[list[str]] = None,
        project_path: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> ProjectNote:
        """Add a new note.

        Args:
            category: Note category (decision, todo, pattern, info, block).
            title: Short title.
            content: Full content (Markdown supported).
            tags: Optional tags.
            project_path: Project path (uses current if not specified).
            metadata: Additional metadata.

        Returns:
            The created note.
        """
        key = self._get_project_key(project_path)

        if key not in self._notes:
            self._notes[key] = []

        note = ProjectNote(
            category=category,
            title=title,
            content=content,
            tags=tags or [],
            project_path=project_path or self._current_project,
            metadata=metadata or {},
        )

        self._notes[key].append(note)
        self._save_project_notes(project_path)

        # Auto-detect relations if enabled
        if self._auto_detect_relations and self._relation_manager:
            try:
                from .note_relations import AutoRelationDetector
                self._auto_detector.detect_relations(note, auto_link=True)
            except Exception:
                pass  # Don't fail note creation if relation detection fails

        return note

    def update_note(
        self,
        note_id: str,
        **updates
    ) -> Optional[ProjectNote]:
        """Update an existing note.

        Args:
            note_id: ID of the note to update.
            **updates: Fields to update.

        Returns:
            The updated note, or None if not found.
        """
        key = self._get_project_key()

        if key not in self._notes:
            return None

        for note in self._notes[key]:
            if note.id == note_id:
                for field, value in updates.items():
                    if hasattr(note, field):
                        setattr(note, field, value)
                note.touch()
                self._save_project_notes()
                return note

        return None

    def complete_note(self, note_id: str) -> Optional[ProjectNote]:
        """Mark a note as completed (for todos).

        Args:
            note_id: ID of the note.

        Returns:
            The updated note, or None if not found.
        """
        return self.update_note(note_id, status=NoteStatus.COMPLETED)

    def archive_note(self, note_id: str) -> Optional[ProjectNote]:
        """Archive a note.

        Args:
            note_id: ID of the note.

        Returns:
            The updated note, or None if not found.
        """
        return self.update_note(note_id, status=NoteStatus.ARCHIVED)

    def delete_note(self, note_id: str) -> bool:
        """Delete a note.

        Args:
            note_id: ID of the note to delete.

        Returns:
            True if deleted, False if not found.
        """
        key = self._get_project_key()

        if key not in self._notes:
            return False

        for i, note in enumerate(self._notes[key]):
            if note.id == note_id:
                self._notes[key].pop(i)
                self._save_project_notes()
                return True

        return False

    def get_note(self, note_id: str) -> Optional[ProjectNote]:
        """Get a specific note by ID.

        Args:
            note_id: ID of the note.

        Returns:
            The note, or None if not found.
        """
        key = self._get_project_key()

        if key not in self._notes:
            return None

        for note in self._notes[key]:
            if note.id == note_id:
                return note

        return None

    def get_notes(
        self,
        category: Optional[str] = None,
        status: Optional[int] = None,
        tag: Optional[str] = None,
        active_only: bool = True,
    ) -> list[ProjectNote]:
        """Get notes matching criteria.

        Args:
            category: Filter by category.
            status: Filter by status.
            tag: Filter by tag.
            active_only: Only return active notes.

        Returns:
            List of matching notes.
        """
        key = self._get_project_key()

        if key not in self._notes:
            return []

        notes = self._notes[key]

        # Apply filters
        if active_only:
            notes = [n for n in notes if n.is_active()]

        if category:
            notes = [n for n in notes if n.category == category]

        if status is not None:
            notes = [n for n in notes if n.status == status]

        if tag:
            notes = [n for n in notes if tag in n.tags]

        # Sort by created_at (newest first)
        notes.sort(key=lambda n: n.created_at, reverse=True)

        return notes

    def search_notes(
        self,
        query: str,
        semantic: bool = False,
        top_k: int = 10,
        threshold: float = 0.7
    ) -> list[ProjectNote]:
        """Search notes by content.

        Args:
            query: Search query.
            semantic: Use semantic search if available.
            top_k: Maximum results for semantic search.
            threshold: Similarity threshold for semantic search.

        Returns:
            List of matching notes.
        """
        key = self._get_project_key()

        if key not in self._notes:
            return []

        # Try semantic search first if requested and available
        if semantic and self._semantic_search:
            results = self._semantic_search.search(query, top_k=top_k, threshold=threshold)
            return [note for note, score in results]

        # Fallback to keyword search
        query_lower = query.lower()
        matches = []

        for note in self._notes[key]:
            if (query_lower in note.title.lower() or
                query_lower in note.content.lower() or
                any(query_lower in tag.lower() for tag in note.tags)):
                matches.append(note)

        # Sort by relevance (title match first, then content)
        def sort_key(n: ProjectNote) -> tuple:
            title_match = query_lower in n.title.lower()
            return (0 if title_match else 1, n.created_at)

        matches.sort(key=sort_key, reverse=True)
        return matches[:top_k]

    def format_notes_for_context(
        self,
        category: Optional[str] = None,
        max_notes: int = 10,
        max_tokens: int = 2000,
    ) -> str:
        """Format notes for inclusion in LLM context.

        Args:
            category: Optional category filter.
            max_notes: Maximum number of notes to include.
            max_tokens: Approximate token limit for output.

        Returns:
            Formatted notes string.
        """
        notes = self.get_notes(category=category, active_only=True)[:max_notes]

        if not notes:
            return ""

        parts = ["## Project Notes\n"]

        # Group by category
        by_category: dict[str, list[ProjectNote]] = {}
        for note in notes:
            if note.category not in by_category:
                by_category[note.category] = []
            by_category[note.category].append(note)

        category_labels = {
            NoteCategory.DECISION: "Decisions",
            NoteCategory.TODO: "Active Tasks",
            NoteCategory.PATTERN: "Patterns",
            NoteCategory.INFO: "Information",
            NoteCategory.BLOCK: "Blockers",
        }

        total_chars = 0
        char_limit = max_tokens * 4  # Rough chars per token

        for cat, cat_notes in by_category.items():
            label = category_labels.get(cat, cat.capitalize())
            section = f"\n### {label}\n"

            for note in cat_notes:
                note_str = note.format_for_context() + "\n\n"
                if total_chars + len(section) + len(note_str) > char_limit:
                    break
                section += note_str
                total_chars += len(note_str)

            parts.append(section)

        return "".join(parts)

    def get_stats(self) -> dict:
        """Get statistics about notes.

        Returns:
            Dictionary with note statistics.
        """
        key = self._get_project_key()
        notes = self._notes.get(key, [])

        by_category: dict[str, int] = {}
        by_status: dict[int, int] = {}

        for note in notes:
            by_category[note.category] = by_category.get(note.category, 0) + 1
            by_status[note.status] = by_status.get(note.status, 0) + 1

        return {
            "total": len(notes),
            "active": len([n for n in notes if n.is_active()]),
            "by_category": by_category,
            "by_status": {str(k): v for k, v in by_status.items()},
        }

    def __repr__(self) -> str:
        """Get string representation."""
        stats = self.get_stats()
        return f"ProjectNotesManager(notes={stats['total']}, active={stats['active']})"
