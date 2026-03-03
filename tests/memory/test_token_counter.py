"""Unit tests for token counting utilities.

Tests cover ApproximateTokenizer, TokenCounter, and related functionality.
"""

import pytest
from unittest.mock import MagicMock

from mini_coder.memory.token_counter import (
    ApproximateTokenizer,
    TokenCounter,
    TiktokenTokenizer,
)


class TestApproximateTokenizer:
    """Tests for ApproximateTokenizer."""

    def test_count_empty_text(self) -> None:
        """Test counting empty text returns 0."""
        tokenizer = ApproximateTokenizer()
        assert tokenizer.count("") == 0

    def test_count_english_text(self) -> None:
        """Test counting English text."""
        tokenizer = ApproximateTokenizer()
        # "Hello world" = 11 chars / 4 = ~3 tokens + 1 = 4
        count = tokenizer.count("Hello world")
        assert count > 0
        assert count < 20  # Reasonable upper bound

    def test_count_chinese_text(self) -> None:
        """Test counting Chinese text."""
        tokenizer = ApproximateTokenizer()
        # Chinese characters should use different ratio
        count = tokenizer.count("你好世界")
        assert count > 0

    def test_count_mixed_text(self) -> None:
        """Test counting mixed English and Chinese text."""
        tokenizer = ApproximateTokenizer()
        count = tokenizer.count("Hello 你好 World 世界")
        assert count > 0

    def test_count_long_text(self) -> None:
        """Test counting long text."""
        tokenizer = ApproximateTokenizer()
        long_text = "a" * 1000
        count = tokenizer.count(long_text)
        assert count > 200  # Should be roughly 1000/4 = 250

    def test_is_cjk_detection(self) -> None:
        """Test CJK character detection."""
        assert ApproximateTokenizer._is_cjk("中") is True
        assert ApproximateTokenizer._is_cjk("a") is False
        assert ApproximateTokenizer._is_cjk("。") is True  # CJK punctuation


class TestTiktokenTokenizer:
    """Tests for TiktokenTokenizer."""

    def test_count_empty_text(self) -> None:
        """Test counting empty text returns 0."""
        tokenizer = TiktokenTokenizer()
        assert tokenizer.count("") == 0

    def test_fallback_when_tiktoken_unavailable(self) -> None:
        """Test that fallback is used when tiktoken is not available."""
        # This test verifies the fallback mechanism
        tokenizer = TiktokenTokenizer()
        # If tiktoken is not installed, should use approximate tokenizer
        count = tokenizer.count("Hello world")
        assert count > 0


class TestTokenCounter:
    """Tests for TokenCounter."""

    def test_initialization_with_defaults(self) -> None:
        """Test counter initialization with default values."""
        counter = TokenCounter()
        assert counter._max_tokens == 128000
        assert counter._buffer_ratio == 0.10
        assert counter._current_tokens == 0

    def test_initialization_with_custom_values(self) -> None:
        """Test counter initialization with custom values."""
        tokenizer = ApproximateTokenizer()
        counter = TokenCounter(
            tokenizer=tokenizer,
            max_tokens=1000,
            buffer_ratio=0.2
        )
        assert counter._max_tokens == 1000
        assert counter._buffer_ratio == 0.2

    def test_count_text(self) -> None:
        """Test counting text."""
        counter = TokenCounter(max_tokens=1000)
        count = counter.count("Hello world")
        assert count > 0

    def test_count_messages(self) -> None:
        """Test counting messages."""
        counter = TokenCounter(max_tokens=1000)
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        total = counter.count_messages(messages)
        assert total > 0
        # Each message should have at least 4 tokens for role
        assert total >= 8

    def test_count_messages_with_empty_content(self) -> None:
        """Test counting messages with empty content."""
        counter = TokenCounter(max_tokens=1000)
        messages = [{"role": "user", "content": ""}]
        total = counter.count_messages(messages)
        assert total >= 4  # At least role tokens

    def test_set_current_tokens(self) -> None:
        """Test setting current token count."""
        counter = TokenCounter(max_tokens=1000)
        counter.set_current_tokens(500)
        assert counter._current_tokens == 500

    def test_add_tokens(self) -> None:
        """Test adding tokens to current count."""
        counter = TokenCounter(max_tokens=1000)
        counter.add_tokens(100)
        assert counter._current_tokens == 100
        counter.add_tokens(50)
        assert counter._current_tokens == 150

    def test_ratio_calculation(self) -> None:
        """Test token usage ratio calculation."""
        counter = TokenCounter(max_tokens=1000)
        assert counter.ratio() == 0.0

        counter.set_current_tokens(500)
        assert counter.ratio() == 0.5

        counter.set_current_tokens(920)
        assert counter.ratio() == pytest.approx(0.92, rel=0.01)

    def test_ratio_with_zero_max_tokens(self) -> None:
        """Test ratio calculation with zero max tokens."""
        counter = TokenCounter(max_tokens=0)
        assert counter.ratio() == 0.0

    def test_remaining_tokens(self) -> None:
        """Test remaining token calculation."""
        counter = TokenCounter(max_tokens=1000)
        assert counter.remaining() == 1000

        counter.set_current_tokens(300)
        assert counter.remaining() == 700

        counter.set_current_tokens(1200)  # Over limit
        assert counter.remaining() == 0

    def test_effective_limit_with_buffer(self) -> None:
        """Test effective limit calculation with buffer."""
        counter = TokenCounter(max_tokens=1000, buffer_ratio=0.10)
        # 1000 * (1 - 0.10) = 900
        assert counter.effective_limit() == 900

    def test_can_fit_within_budget(self) -> None:
        """Test checking if text can fit within budget."""
        counter = TokenCounter(max_tokens=1000, buffer_ratio=0.10)
        counter.set_current_tokens(800)

        # Should fit (effective limit is 900)
        short_text = "a" * 100  # ~25 tokens
        assert counter.can_fit(short_text) is True

    def test_can_fit_exceeds_budget(self) -> None:
        """Test checking if text exceeds budget."""
        counter = TokenCounter(max_tokens=1000, buffer_ratio=0.10)
        counter.set_current_tokens(890)

        # Should not fit (effective limit is 900)
        long_text = "a" * 1000  # ~250 tokens
        assert counter.can_fit(long_text) is False

    def test_should_compress_below_threshold(self) -> None:
        """Test compression check below threshold."""
        counter = TokenCounter(max_tokens=1000)
        counter.set_current_tokens(500)  # 50%
        assert counter.should_compress(threshold=0.92) is False

    def test_should_compress_at_threshold(self) -> None:
        """Test compression check at threshold."""
        counter = TokenCounter(max_tokens=1000)
        counter.set_current_tokens(920)  # 92%
        assert counter.should_compress(threshold=0.92) is True

    def test_should_compress_above_threshold(self) -> None:
        """Test compression check above threshold."""
        counter = TokenCounter(max_tokens=1000)
        counter.set_current_tokens(950)  # 95%
        assert counter.should_compress(threshold=0.92) is True

    def test_reset(self) -> None:
        """Test resetting token counter."""
        counter = TokenCounter(max_tokens=1000)
        counter.set_current_tokens(500)
        counter.reset()
        assert counter._current_tokens == 0
        assert counter.ratio() == 0.0


class TestTokenCounterIntegration:
    """Integration tests for TokenCounter with messages."""

    def test_full_workflow(self) -> None:
        """Test full workflow of counting and managing tokens."""
        counter = TokenCounter(max_tokens=1000, buffer_ratio=0.10)

        # Add some messages
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there! How can I help you?"},
        ]

        total = counter.count_messages(messages)
        counter.set_current_tokens(total)

        # Check status
        assert counter.ratio() < 0.92
        assert counter.should_compress() is False
        assert counter.remaining() > 0

        # Reset and verify
        counter.reset()
        assert counter._current_tokens == 0
