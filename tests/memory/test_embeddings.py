"""Tests for embedding service functionality."""

import pytest
import numpy as np

from mini_coder.memory.embeddings import (
    LocalEmbeddingService,
    EmbeddingConfig,
    EMBEDDINGS_AVAILABLE,
)


class TestEmbeddingConfig:
    """Tests for EmbeddingConfig model."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = EmbeddingConfig()

        assert config.model_name == "all-MiniLM-L6-v2"
        assert config.cache_size == 1000
        assert config.normalize is True

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = EmbeddingConfig(
            model_name="custom-model",
            cache_size=500,
            normalize=False
        )

        assert config.model_name == "custom-model"
        assert config.cache_size == 500
        assert config.normalize is False


class TestLocalEmbeddingService:
    """Tests for LocalEmbeddingService."""

    @pytest.fixture
    def service(self) -> LocalEmbeddingService:
        """Create an embedding service."""
        return LocalEmbeddingService()

    def test_service_creation(self, service: LocalEmbeddingService) -> None:
        """Test service can be created."""
        assert service is not None
        assert service.dimension > 0

    def test_embed_single_text(self, service: LocalEmbeddingService) -> None:
        """Test embedding a single text."""
        if not EMBEDDINGS_AVAILABLE:
            pytest.skip("sentence-transformers not installed")

        text = "Hello world"
        embedding = service.embed(text)

        assert embedding is not None
        assert len(embedding) == service.dimension
        assert isinstance(embedding, np.ndarray)

    def test_embed_batch(self, service: LocalEmbeddingService) -> None:
        """Test embedding multiple texts."""
        if not EMBEDDINGS_AVAILABLE:
            pytest.skip("sentence-transformers not installed")

        texts = ["Hello world", "Goodbye world", "Test embedding"]
        embeddings = service.embed_batch(texts)

        assert embeddings is not None
        assert embeddings.shape[0] == len(texts)
        assert embeddings.shape[1] == service.dimension

    def test_cosine_similarity_identical(self, service: LocalEmbeddingService) -> None:
        """Test cosine similarity of identical texts."""
        if not EMBEDDINGS_AVAILABLE:
            pytest.skip("sentence-transformers not installed")

        text = "The quick brown fox"
        emb1 = service.embed(text)
        emb2 = service.embed(text)

        similarity = service.cosine_similarity(emb1, emb2)

        # Identical texts should have similarity close to 1.0
        assert similarity > 0.99

    def test_cosine_similarity_different(self, service: LocalEmbeddingService) -> None:
        """Test cosine similarity of different texts."""
        if not EMBEDDINGS_AVAILABLE:
            pytest.skip("sentence-transformers not installed")

        text1 = "The quick brown fox jumps over the lazy dog"
        text2 = "Python programming is fun"

        emb1 = service.embed(text1)
        emb2 = service.embed(text2)

        similarity = service.cosine_similarity(emb1, emb2)

        # Different texts should have lower similarity
        # (but not necessarily 0, semantic similarity can vary)
        assert 0.0 <= similarity <= 1.0

    def test_cosine_similarity_batch(self, service: LocalEmbeddingService) -> None:
        """Test batch cosine similarity calculation."""
        if not EMBEDDINGS_AVAILABLE:
            pytest.skip("sentence-transformers not installed")

        query = service.embed("database query")
        documents = [
            "database system",
            "web development",
            "data storage"
        ]
        doc_embeddings = service.embed_batch(documents)

        similarities = service.cosine_similarity_batch(query, doc_embeddings)

        assert len(similarities) == len(documents)
        assert all(0.0 <= s <= 1.0 for s in similarities)

    def test_embedding_caching(self, service: LocalEmbeddingService) -> None:
        """Test that embeddings are cached."""
        if not EMBEDDINGS_AVAILABLE:
            pytest.skip("sentence-transformers not installed")

        text = "Test caching"

        # First call should compute
        emb1 = service.embed(text)
        # Second call should use cache
        emb2 = service.embed(text)

        # Should return same embedding
        np.testing.assert_array_almost_equal(emb1, emb2)

    def test_empty_text_handling(self, service: LocalEmbeddingService) -> None:
        """Test handling of empty text."""
        if not EMBEDDINGS_AVAILABLE:
            pytest.skip("sentence-transformers not installed")

        embedding = service.embed("")

        # Should return zero vector or handle gracefully
        assert embedding is not None
        assert len(embedding) == service.dimension

    def test_get_similarity_fallback(self) -> None:
        """Test fallback similarity when embeddings unavailable."""
        # Create service with fallback mode
        service = LocalEmbeddingService.__new__(object)  # Bypass __init__
        service._available = False

        similarity = service.get_similarity("hello world", "world hello")

        # Should use word overlap fallback
        assert similarity > 0.9  # Same words, different order


class TestEmbeddingAvailability:
    """Tests for embedding availability checking."""

    def test_availability_flag(self) -> None:
        """Test that availability flag is set correctly."""
        # EMBEDDINGS_AVAILABLE should be a boolean
        assert isinstance(EMBEDDINGS_AVAILABLE, bool)

    def test_fallback_mode(self) -> None:
        """Test service behavior in fallback mode."""
        if EMBEDDINGS_AVAILABLE:
            pytest.skip("Testing fallback mode, but embeddings available")

        service = LocalEmbeddingService()
        similarity = service.get_similarity("hello", "hello")
        assert similarity == 1.0  # Same word should match exactly
