"""Semantic search for project notes.

This module provides vector-based semantic similarity search for notes
using local embeddings.

Example:
    >>> from mini_coder.memory import SemanticNoteSearch, LocalEmbeddingService
    >>> embedding_service = LocalEmbeddingService()
    >>> search = SemanticNoteSearch(notes_manager, embedding_service)
    >>> results = search.search("database configuration")
"""

import logging
from typing import Optional

import numpy as np

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class SemanticSearchConfig(BaseModel):
    """Configuration for semantic search.

    Attributes:
        similarity_threshold: Minimum similarity score for results.
        top_k: Maximum number of results to return.
        index_cache_size: Maximum embeddings to cache in memory.
    """

    similarity_threshold: float = 0.7
    top_k: int = 5
    index_cache_size: int = 1000


class SemanticNoteSearch:
    """Semantic search for project notes using embeddings.

    Provides similarity-based search for notes using vector embeddings.
    Falls back gracefully when embeddings are unavailable.

    Example:
        >>> search = SemanticNoteSearch(notes_manager, embedding_service)
        >>> results = search.search("database setup", top_k=3)
        >>> for note, score in results:
        ...     print(f"{note.title}: {score:.2f}")
    """

    def __init__(
        self,
        notes_manager,
        embedding_service,
        config: Optional[SemanticSearchConfig] = None
    ):
        """Initialize semantic search.

        Args:
            notes_manager: ProjectNotesManager instance.
            embedding_service: LocalEmbeddingService instance.
            config: Optional search configuration.
        """
        self.notes = notes_manager
        self.embeddings = embedding_service
        self.config = config or SemanticSearchConfig()

        # Index cache: project_key -> {note_ids, embeddings}
        self._index_cache: dict[str, dict] = {}

    @property
    def is_available(self) -> bool:
        """Check if semantic search is available."""
        return self.embeddings.is_available

    def build_index(self, force: bool = False) -> int:
        """Build search index for current project's notes.

        Args:
            force: Force rebuild even if notes have embeddings.

        Returns:
            Number of notes indexed.
        """
        if not self.is_available:
            logger.warning("Semantic search unavailable - embeddings not available")
            return 0

        key = self.notes._get_project_key()
        notes = self.notes.get_notes(active_only=True)

        if not notes:
            self._index_cache[key] = {"note_ids": [], "embeddings": np.array([])}
            return 0

        # Collect notes that need embeddings
        notes_to_embed = []
        note_ids = []

        for note in notes:
            if force or note.needs_embedding(self.embeddings.model_name):
                notes_to_embed.append(f"{note.title}\n{note.content}")
                note_ids.append(note.id)
            elif note.embedding:
                note_ids.append(note.id)

        # Generate embeddings for notes that need them
        if notes_to_embed:
            logger.info(f"Generating embeddings for {len(notes_to_embed)} notes")
            try:
                new_embeddings = self.embeddings.embed_batch(notes_to_embed)

                # Update notes with new embeddings
                for i, note_id in enumerate(note_ids):
                    note = self.notes.get_note(note_id)
                    if note and i < len(new_embeddings):
                        note.embedding = new_embeddings[i].tolist()
                        note.embedding_model = self.embeddings.model_name

                self.notes._save_project_notes()
            except Exception as e:
                logger.error(f"Failed to generate embeddings: {e}")
                return 0

        # Build index from all notes with embeddings
        all_embeddings = []
        all_note_ids = []

        for note in notes:
            if note.embedding:
                all_embeddings.append(note.embedding)
                all_note_ids.append(note.id)

        if all_embeddings:
            self._index_cache[key] = {
                "note_ids": all_note_ids,
                "embeddings": np.array(all_embeddings)
            }
        else:
            self._index_cache[key] = {"note_ids": [], "embeddings": np.array([])}

        logger.info(f"Built index with {len(all_note_ids)} notes")
        return len(all_note_ids)

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        threshold: Optional[float] = None,
        category: Optional[str] = None
    ) -> list[tuple]:
        """Search notes by semantic similarity.

        Args:
            query: Search query text.
            top_k: Maximum results to return (default from config).
            threshold: Minimum similarity score (default from config).
            category: Optional category filter.

        Returns:
            List of (note, similarity_score) tuples.
        """
        if not self.is_available:
            logger.warning("Semantic search unavailable")
            return []

        top_k = top_k or self.config.top_k
        threshold = threshold or self.config.similarity_threshold

        # Ensure index exists
        key = self.notes._get_project_key()
        if key not in self._index_cache:
            self.build_index()

        index = self._index_cache.get(key)
        if not index or len(index["note_ids"]) == 0:
            return []

        # Generate query embedding
        try:
            query_embedding = self.embeddings.embed(query)
        except Exception as e:
            logger.error(f"Failed to embed query: {e}")
            return []

        # Calculate similarities
        similarities = self.embeddings.cosine_similarity_batch(
            query_embedding,
            index["embeddings"]
        )

        # Build results
        results: list[tuple] = []
        for note_id, score in zip(index["note_ids"], similarities):
            if score >= threshold:
                note = self.notes.get_note(note_id)
                if note:
                    # Apply category filter
                    if category and note.category != category:
                        continue
                    results.append((note, float(score)))

        # Sort by score and limit
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def find_similar(
        self,
        note_id: str,
        top_k: Optional[int] = None,
        threshold: Optional[float] = None
    ) -> list[tuple]:
        """Find notes similar to a specific note.

        Args:
            note_id: ID of the note to find similar notes for.
            top_k: Maximum results to return.
            threshold: Minimum similarity score.

        Returns:
            List of (note, similarity_score) tuples.
        """
        note = self.notes.get_note(note_id)
        if not note or not note.embedding:
            return []

        top_k = top_k or self.config.top_k
        threshold = threshold or self.config.similarity_threshold

        # Get cached index
        key = self.notes._get_project_key()
        index = self._index_cache.get(key)

        if not index:
            self.build_index()
            index = self._index_cache.get(key)

        if not index:
            return []

        # Calculate similarities with note's embedding
        note_embedding = np.array(note.embedding)
        similarities = self.embeddings.cosine_similarity_batch(
            note_embedding,
            index["embeddings"]
        )

        # Build results (excluding the note itself)
        results: list[tuple] = []
        for other_id, score in zip(index["note_ids"], similarities):
            if other_id != note_id and score >= threshold:
                other = self.notes.get_note(other_id)
                if other:
                    results.append((other, float(score)))

        # Sort by score and limit
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def clear_cache(self) -> None:
        """Clear the index cache."""
        self._index_cache.clear()

    def get_stats(self) -> dict:
        """Get statistics about the search index.

        Returns:
            Dictionary with index statistics.
        """
        key = self.notes._get_project_key()
        index = self._index_cache.get(key)

        if not index:
            return {
                "indexed": 0,
                "available": self.is_available
            }

        embedding_dim = index["embeddings"].shape[1] if len(index["embeddings"]) > 0 else 0
        return {
            "indexed": len(index["note_ids"]),
            "available": self.is_available,
            "embedding_dimension": embedding_dim
        }
