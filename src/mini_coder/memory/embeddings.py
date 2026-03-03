"""Embedding service for semantic search.

This module provides local embedding generation using sentence-transformers
with graceful fallback when the library is not installed.

Example:
    >>> from mini_coder.memory import LocalEmbeddingService
    >>> service = LocalEmbeddingService()
    >>> embedding = service.embed("Hello world")
    >>> similar = service.cosine_similarity(embedding1, embedding2)
"""

import logging
from typing import Optional

import numpy as np

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Check if sentence-transformers is available
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    SentenceTransformer = None  # type: ignore


class EmbeddingConfig(BaseModel):
    """Configuration for embedding service.

    Attributes:
        model_name: Name of the sentence-transformers model.
        cache_size: Maximum number of embeddings to cache.
        normalize: Whether to normalize embeddings.
    """

    model_name: str = "all-MiniLM-L6-v2"
    cache_size: int = 1000
    normalize: bool = True


class LocalEmbeddingService:
    """Local embedding service using sentence-transformers.

    Provides efficient embedding generation for semantic similarity
    calculations. Falls back gracefully when sentence-transformers
    is not installed.

    Example:
        >>> service = LocalEmbeddingService()
        >>> embedding = service.embed("Hello world")
        >>> print(len(embedding))
        384
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        config: Optional[EmbeddingConfig] = None
    ):
        """Initialize the embedding service.

        Args:
            model_name: Name of the sentence-transformers model to use.
            config: Optional configuration object.
        """
        self.config = config or EmbeddingConfig(model_name=model_name)
        self.model_name = self.config.model_name
        self._model: Optional[SentenceTransformer] = None
        self._dimension: Optional[int] = None
        self._available = EMBEDDINGS_AVAILABLE

        if not self._available:
            logger.warning(
                "sentence-transformers not installed. "
                "Semantic search will be disabled. "
                "Install with: pip install sentence-transformers"
            )

    @property
    def is_available(self) -> bool:
        """Check if embedding service is available."""
        return self._available

    @property
    def dimension(self) -> int:
        """Get embedding dimension."""
        if self._dimension is None:
            if self._available:
                self._load_model()
                self._dimension = self._model.get_sentence_embedding_dimension()  # type: ignore
            else:
                # Default dimension for all-MiniLM-L6-v2
                self._dimension = 384
        return self._dimension

    def _load_model(self) -> None:
        """Lazy load the model."""
        if self._model is None and self._available:
            logger.info(f"Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
            dim = self._model.get_sentence_embedding_dimension()
            logger.info(f"Model loaded. Dimension: {dim}")

    def embed(self, text: str) -> np.ndarray:
        """Generate embedding for a single text.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector as numpy array.

        Raises:
            RuntimeError: If sentence-transformers is not installed.
        """
        if not self._available:
            raise RuntimeError(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )

        self._load_model()

        embedding = self._model.encode(  # type: ignore
            text,
            normalize_embeddings=self.config.normalize,
            convert_to_numpy=True
        )

        return embedding

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed.

        Returns:
            Array of embeddings (shape: len(texts) x dimension).

        Raises:
            RuntimeError: If sentence-transformers is not installed.
        """
        if not self._available:
            raise RuntimeError(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )

        if not texts:
            return np.array([])

        self._load_model()

        embeddings = self._model.encode(  # type: ignore
            texts,
            normalize_embeddings=self.config.normalize,
            convert_to_numpy=True,
            show_progress_bar=len(texts) > 100
        )

        return embeddings

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors.

        Args:
            a: First vector.
            b: Second vector.

        Returns:
            Cosine similarity score (-1 to 1).
        """
        # Handle zero vectors
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(np.dot(a, b) / (norm_a * norm_b))

    @staticmethod
    def cosine_similarity_batch(
        query: np.ndarray,
        embeddings: np.ndarray
    ) -> np.ndarray:
        """Calculate cosine similarity between query and multiple embeddings.

        Args:
            query: Query vector (1D).
            embeddings: Matrix of embeddings (2D, shape: n x dimension).

        Returns:
            Array of similarity scores.
        """
        if len(embeddings) == 0:
            return np.array([])

        # Normalize query
        query_norm = query / (np.linalg.norm(query) + 1e-10)

        # Normalize embeddings
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-10
        normalized = embeddings / norms

        # Calculate similarities
        similarities = np.dot(normalized, query_norm)

        return similarities

    def get_similarity(
        self,
        text1: str,
        text2: str
    ) -> float:
        """Calculate semantic similarity between two texts.

        Args:
            text1: First text.
            text2: Second text.

        Returns:
            Similarity score (0 to 1).
        """
        if not self._available:
            # Fallback to simple word overlap
            words1 = set(text1.lower().split())
            words2 = set(text2.lower().split())
            if not words1 or not words2:
                return 0.0
            return len(words1 & words2) / len(words1 | words2)

        emb1 = self.embed(text1)
        emb2 = self.embed(text2)

        # Convert to 0-1 range (cosine similarity is -1 to 1)
        return (self.cosine_similarity(emb1, emb2) + 1) / 2
