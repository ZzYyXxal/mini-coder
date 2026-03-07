"""Tests for embedding service functionality."""

import pytest
import numpy as np

from mini_coder.memory.embeddings import (
    LocalEmbeddingService,
    EmbeddingConfig,
    EMBEDDINGS_AVAILABLE,
    FASTEMBED_DEFAULT_MODEL,
)


class TestEmbeddingConfig:
    """Tests for EmbeddingConfig model."""

    def test_default_config(self) -> None:
        """Test default configuration values（默认 fastembed）。"""
        config = EmbeddingConfig()

        assert config.model_name == FASTEMBED_DEFAULT_MODEL
        assert config.backend == "fastembed"
        assert config.batch_size == 32
        assert config.cache_size == 1000
        assert config.normalize is True

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = EmbeddingConfig(
            model_name="custom-model",
            backend="fastembed",
            cache_size=500,
            normalize=False,
            batch_size=16,
        )

        assert config.model_name == "custom-model"
        assert config.cache_size == 500
        assert config.normalize is False
        assert config.batch_size == 16


class TestLocalEmbeddingService:
    """Tests for LocalEmbeddingService（默认 fastembed，无 sentence-transformers）。"""

    @pytest.fixture
    def service(self) -> LocalEmbeddingService:
        """Create an embedding service（使用 fastembed 后端）。"""
        return LocalEmbeddingService(config=EmbeddingConfig(backend="fastembed"))

    def test_service_creation(self, service: LocalEmbeddingService) -> None:
        """Test service can be created."""
        assert service is not None
        if service.is_available:
            assert service.dimension > 0

    def test_embed_single_text(self, service: LocalEmbeddingService) -> None:
        """Test embedding a single text."""
        if not service.is_available:
            pytest.skip("No embedding backend available (install fastembed or set API)")

        text = "Hello world"
        embedding = service.embed(text)

        assert embedding is not None
        assert len(embedding) == service.dimension
        assert isinstance(embedding, np.ndarray)

    def test_embed_batch(self, service: LocalEmbeddingService) -> None:
        """Test embedding multiple texts（含 batch_size 分批）."""
        if not service.is_available:
            pytest.skip("No embedding backend available (install fastembed or set API)")

        texts = ["Hello world", "Goodbye world", "Test embedding"]
        embeddings = service.embed_batch(texts)

        assert embeddings is not None
        assert embeddings.shape[0] == len(texts)
        assert embeddings.shape[1] == service.dimension

    def test_cosine_similarity_identical(self, service: LocalEmbeddingService) -> None:
        """Test cosine similarity of identical texts."""
        if not service.is_available:
            pytest.skip("No embedding backend available (install fastembed or set API)")

        text = "The quick brown fox"
        emb1 = service.embed(text)
        emb2 = service.embed(text)

        similarity = service.cosine_similarity(emb1, emb2)

        # Identical texts should have similarity close to 1.0
        assert similarity > 0.99

    def test_cosine_similarity_different(self, service: LocalEmbeddingService) -> None:
        """Test cosine similarity of different texts."""
        if not service.is_available:
            pytest.skip("No embedding backend available (install fastembed or set API)")

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
        if not service.is_available:
            pytest.skip("No embedding backend available (install fastembed or set API)")

        query = service.embed("database query")
        documents = [
            "database system",
            "web development",
            "data storage"
        ]
        doc_embeddings = service.embed_batch(documents)

        similarities = service.cosine_similarity_batch(query, doc_embeddings)

        assert len(similarities) == len(documents)
        assert all(-1.0 <= s <= 1.0 for s in similarities)

    def test_embedding_caching(self, service: LocalEmbeddingService) -> None:
        """Test that embeddings are cached (same input -> same output)."""
        if not service.is_available:
            pytest.skip("No embedding backend available (install fastembed or set API)")

        text = "Test caching"

        # First call should compute
        emb1 = service.embed(text)
        # Second call should return same vector
        emb2 = service.embed(text)

        np.testing.assert_array_almost_equal(emb1, emb2)

    def test_empty_text_handling(self, service: LocalEmbeddingService) -> None:
        """Test handling of empty text."""
        if not service.is_available:
            pytest.skip("No embedding backend available (install fastembed or set API)")

        embedding = service.embed("")

        # Should return zero vector or handle gracefully
        assert embedding is not None
        assert len(embedding) == service.dimension

    def test_get_similarity_fallback(self) -> None:
        """Test fallback similarity when embeddings unavailable."""
        # 使用类构造一个未初始化的实例并标记为不可用，以测试词重叠回退
        service = LocalEmbeddingService.__new__(LocalEmbeddingService)
        service._available = False
        service.config = EmbeddingConfig()

        similarity = service.get_similarity("hello world", "world hello")

        # Should use word overlap fallback
        assert similarity > 0.9  # Same words, different order


class TestEmbeddingAvailability:
    """Tests for embedding availability checking."""

    def test_availability_flag(self) -> None:
        """Test that availability flag is set correctly."""
        assert isinstance(EMBEDDINGS_AVAILABLE, bool)

    def test_fallback_mode(self) -> None:
        """Test service behavior when no backend available (word overlap)."""
        # 无 fastembed 且无 API 时走词重叠
        service = LocalEmbeddingService(config=EmbeddingConfig(backend="fastembed"))
        if service.is_available:
            pytest.skip("Embedding backend available, cannot test fallback")
        similarity = service.get_similarity("hello", "hello")
        assert similarity == 1.0  # Same word should match exactly
