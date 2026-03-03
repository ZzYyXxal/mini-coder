"""Note relations management.

This module provides typed relationships between notes with automatic
detection and graph traversal support.

Example:
    >>> from mini_coder.memory import NoteRelationManager, RelationType
    >>> manager = NoteRelationManager(notes_manager)
    >>> manager.add_relation("note1", "note2", RelationType.DEPENDS_ON)
"""

from enum import Enum
from typing import Optional
from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class RelationType(str, Enum):
    """Types of relationships between notes."""

    RELATED_TO = "related_to"      # General association
    DEPENDS_ON = "depends_on"      # Dependency relationship
    BLOCKS = "blocks"              # Blocking relationship
    IMPLEMENTS = "implements"      # Implementation relationship
    SUPERSEDES = "supersedes"      # Replacement relationship
    DERIVED_FROM = "derived_from"  # Source relationship


# Reverse relation mappings for bidirectional relations
REVERSE_RELATIONS: dict[RelationType, RelationType] = {
    RelationType.DEPENDS_ON: RelationType.RELATED_TO,
    RelationType.BLOCKS: RelationType.RELATED_TO,
    RelationType.IMPLEMENTS: RelationType.RELATED_TO,
    RelationType.SUPERSEDES: RelationType.DERIVED_FROM,
    RelationType.DERIVED_FROM: RelationType.SUPERSEDES,
    RelationType.RELATED_TO: RelationType.RELATED_TO,
}

# Category affinity rules for automatic relation type inference
# Maps (source_category, target_category) -> suggested_relation_type
CATEGORY_AFFINITY: dict[tuple[str, str], RelationType] = {
    ("decision", "todo"): RelationType.RELATED_TO,
    ("decision", "pattern"): RelationType.IMPLEMENTS,
    ("todo", "block"): RelationType.DEPENDS_ON,
    ("block", "todo"): RelationType.BLOCKS,
    ("pattern", "info"): RelationType.RELATED_TO,
    ("todo", "todo"): RelationType.DEPENDS_ON,
    ("decision", "decision"): RelationType.RELATED_TO,
}


class NoteRelation(BaseModel):
    """A typed relationship between two notes.

    Attributes:
        id: Unique identifier for the relation.
        source_id: ID of the source note.
        target_id: ID of the target note.
        relation_type: Type of relationship.
        created_at: When the relation was created.
        metadata: Additional metadata.
    """

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    source_id: str
    target_id: str
    relation_type: str = RelationType.RELATED_TO
    created_at: datetime = Field(default_factory=datetime.now)
    metadata: dict = Field(default_factory=dict)


class NoteRelationManager:
    """Manager for note relationships.

    Provides CRUD operations and graph traversal for note relations.

    Example:
        >>> manager = NoteRelationManager(notes_manager)
        >>> manager.add_relation("n1", "n2", RelationType.DEPENDS_ON)
        >>> related = manager.get_related_notes("n1", depth=2)
    """

    def __init__(self, notes_manager):
        """Initialize the relation manager.

        Args:
            notes_manager: ProjectNotesManager instance.
        """
        self.notes = notes_manager
        # Cache of relations by source note ID
        self._relations: dict[str, list[NoteRelation]] = {}

    def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: RelationType | str = RelationType.RELATED_TO,
        bidirectional: bool = False
    ) -> Optional[NoteRelation]:
        """Add a relation between two notes.

        Args:
            source_id: ID of the source note.
            target_id: ID of the target note.
            relation_type: Type of relationship.
            bidirectional: If True, creates reverse relation on target.

        Returns:
            The created relation, or None if notes don't exist.
        """
        # Validate notes exist
        source = self.notes.get_note(source_id)
        target = self.notes.get_note(target_id)

        if not source or not target:
            return None

        # Normalize relation type
        if isinstance(relation_type, str):
            relation_type = RelationType(relation_type)

        # Create relation
        relation = NoteRelation(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type.value
        )

        # Update source note's relations
        source.add_relation(target_id, relation_type.value)

        # Create bidirectional relation if requested
        if bidirectional:
            reverse_type = REVERSE_RELATIONS.get(relation_type, RelationType.RELATED_TO)
            target.add_relation(source_id, reverse_type.value)

        # Cache the relation
        if source_id not in self._relations:
            self._relations[source_id] = []
        self._relations[source_id].append(relation)

        # Save changes
        self.notes._save_project_notes()

        return relation

    def remove_relation(
        self,
        source_id: str,
        target_id: str,
        remove_reverse: bool = False
    ) -> bool:
        """Remove a relation between two notes.

        Args:
            source_id: ID of the source note.
            target_id: ID of the target note.
            remove_reverse: If True, also removes reverse relation.

        Returns:
            True if relation was removed, False otherwise.
        """
        source = self.notes.get_note(source_id)
        target = self.notes.get_note(target_id)

        if not source:
            return False

        # Remove from source note
        source.remove_relation(target_id)

        # Remove reverse relation if requested
        if remove_reverse and target:
            target.remove_relation(source_id)

        # Remove from cache
        if source_id in self._relations:
            self._relations[source_id] = [
                r for r in self._relations[source_id]
                if r.target_id != target_id
            ]

        self.notes._save_project_notes()
        return True

    def get_relations(
        self,
        note_id: str,
        relation_type: Optional[RelationType | str] = None
    ) -> list[NoteRelation]:
        """Get all relations for a note.

        Args:
            note_id: ID of the note.
            relation_type: Optional filter by relation type.

        Returns:
            List of relations.
        """
        relations = self._relations.get(note_id, [])

        if relation_type:
            if isinstance(relation_type, str):
                relation_type = RelationType(relation_type)
            relations = [r for r in relations if r.relation_type == relation_type.value]

        return relations

    def get_related_notes(
        self,
        note_id: str,
        depth: int = 1,
        relation_type: Optional[RelationType | str] = None
    ) -> dict[str, list[str]]:
        """Get notes related to a note, traversing the relation graph.

        Args:
            note_id: Starting note ID.
            depth: Maximum traversal depth.
            relation_type: Optional filter by relation type.

        Returns:
            Dict mapping depth level to list of note IDs at that depth.
        """
        result: dict[str, list[str]] = {}
        visited = {note_id}
        current_level = [note_id]

        for level in range(1, depth + 1):
            next_level: list[str] = []
            result[str(level)] = []

            for nid in current_level:
                note = self.notes.get_note(nid)
                if not note:
                    continue

                # Get related note IDs
                related = note.get_related_notes(relation_type)

                for related_id in related:
                    if related_id not in visited:
                        visited.add(related_id)
                        next_level.append(related_id)
                        result[str(level)].append(related_id)

            current_level = next_level
            if not current_level:
                break

        return result


class AutoRelationDetector:
    """Automatic detection of potential note relations.

    Analyzes note similarity and category affinity to suggest relations.

    Example:
        >>> detector = AutoRelationDetector(notes_manager)
        >>> candidates = detector.detect_relations(new_note)
        >>> for note_id, rel_type, conf in candidates:
        ...     print(f"Related to {note_id} via {rel_type} (conf: {conf})")
    """

    def __init__(
        self,
        notes_manager,
        relation_manager: NoteRelationManager,
        similarity_threshold: float = 0.75
    ):
        """Initialize the detector.

        Args:
            notes_manager: ProjectNotesManager instance.
            relation_manager: NoteRelationManager instance.
            similarity_threshold: Minimum similarity to suggest relation.
        """
        self.notes = notes_manager
        self.relations = relation_manager
        self.threshold = similarity_threshold

    def detect_relations(
        self,
        note,
        auto_link: bool = False,
        max_relations: int = 3
    ) -> list[tuple[str, RelationType, float]]:
        """Detect potential relations for a note.

        Args:
            note: The note to analyze.
            auto_link: If True, automatically create detected relations.
            max_relations: Maximum number of relations to create/suggest.

        Returns:
            List of (note_id, suggested_relation_type, confidence) tuples.
        """
        candidates: list[tuple[str, RelationType, float]] = []
        all_notes = self.notes.get_notes(active_only=True)

        for other in all_notes:
            if other.id == note.id:
                continue

            # Skip if already related
            if other.id in note.relations:
                continue

            # Calculate similarity
            similarity = self._calculate_similarity(note, other)

            if similarity >= self.threshold:
                # Infer relation type
                relation_type = self._infer_relation_type(note, other)
                candidates.append((other.id, relation_type, similarity))

        # Sort by similarity
        candidates.sort(key=lambda x: x[2], reverse=True)

        # Auto-link if requested
        if auto_link:
            for other_id, rel_type, conf in candidates[:max_relations]:
                self.relations.add_relation(note.id, other_id, rel_type)

        return candidates[:max_relations]

    def _calculate_similarity(self, note1, note2) -> float:
        """Calculate similarity between two notes.

        Args:
            note1: First note.
            note2: Second note.

        Returns:
            Similarity score (0.0 to 1.0).
        """
        # Method 1: Tag overlap (Jaccard similarity)
        tags1 = set(note1.tags)
        tags2 = set(note2.tags)

        if tags1 or tags2:
            tag_overlap = len(tags1 & tags2) / max(len(tags1 | tags2), 1)
        else:
            tag_overlap = 0.0

        # Method 2: Content word overlap
        words1 = set(note1.content.lower().split())
        words2 = set(note2.content.lower().split())

        # Filter common words
        stopwords = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                     "being", "have", "has", "had", "do", "does", "did", "will",
                     "would", "could", "should", "may", "might", "must", "shall",
                     "can", "need", "to", "of", "in", "for", "on", "with", "at",
                     "by", "from", "as", "into", "through", "during", "before",
                     "after", "above", "below", "between", "under", "again",
                     "的", "是", "在", "有", "和", "与", "或", "了", "我", "我们"}

        words1 = words1 - stopwords
        words2 = words2 - stopwords

        if words1 or words2:
            word_overlap = len(words1 & words2) / max(len(words1 | words2), 1)
        else:
            word_overlap = 0.0

        # Method 3: Category affinity
        category_bonus = self._get_category_affinity(note1.category, note2.category)

        # Weighted combination - give more weight to tags and category
        return 0.4 * tag_overlap + 0.3 * word_overlap + 0.3 * category_bonus

    def _get_category_affinity(self, cat1: str, cat2: str) -> float:
        """Get affinity score between note categories.

        Args:
            cat1: First note category.
            cat2: Second note category.

        Returns:
            Affinity score (0.0 to 1.0).
        """
        # Same category has high affinity
        if cat1 == cat2:
            return 0.9

        # Check affinity rules
        key = (cat1, cat2)
        reverse_key = (cat2, cat1)

        if key in CATEGORY_AFFINITY or reverse_key in CATEGORY_AFFINITY:
            return 0.7

        # Default low affinity
        return 0.3

    def _infer_relation_type(self, note1, note2) -> RelationType:
        """Infer relation type based on note categories.

        Args:
            note1: Source note.
            note2: Target note.

        Returns:
            Inferred relation type.
        """
        key = (note1.category, note2.category)

        if key in CATEGORY_AFFINITY:
            return CATEGORY_AFFINITY[key]

        # Default relation type
        return RelationType.RELATED_TO
