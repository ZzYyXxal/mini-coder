"""Token counting utilities for context management.

This module provides token counting functionality for estimating
the token usage of messages and context.
"""

from abc import ABC, abstractmethod
from typing import Protocol


class Tokenizer(Protocol):
    """Protocol for tokenizer implementations.

    Any tokenizer that implements this protocol can be used
    with the TokenCounter.
    """

    def count(self, text: str) -> int:
        """Count the number of tokens in the text.

        Args:
            text: The text to count tokens for.

        Returns:
            The number of tokens.
        """
        ...


class BaseTokenizer(ABC):
    """Base class for tokenizer implementations."""

    @abstractmethod
    def count(self, text: str) -> int:
        """Count the number of tokens in the text.

        Args:
            text: The text to count tokens for.

        Returns:
            The number of tokens.
        """
        pass


class ApproximateTokenizer(BaseTokenizer):
    """Simple tokenizer that approximates token count.

    Uses a rough heuristic of ~4 characters per token for English text.
    This is less accurate but has no external dependencies.

    For Chinese/mixed content, uses ~2 characters per token as a rough estimate.
    """

    # Average characters per token for different content types
    CHARS_PER_TOKEN_ENGLISH = 4.0
    CHARS_PER_TOKEN_CJK = 2.0

    def count(self, text: str) -> int:
        """Approximate token count based on character count.

        Uses different ratios for ASCII vs CJK characters.

        Args:
            text: The text to count tokens for.

        Returns:
            Approximate number of tokens.
        """
        if not text:
            return 0

        # Count CJK characters (Unicode ranges for Chinese, Japanese, Korean)
        cjk_count = sum(1 for c in text if self._is_cjk(c))
        other_count = len(text) - cjk_count

        # Calculate tokens using different ratios
        cjk_tokens = cjk_count / self.CHARS_PER_TOKEN_CJK
        other_tokens = other_count / self.CHARS_PER_TOKEN_ENGLISH

        return int(cjk_tokens + other_tokens) + 1  # +1 for rounding

    @staticmethod
    def _is_cjk(char: str) -> bool:
        """Check if a character is CJK.

        Args:
            char: A single character.

        Returns:
            True if the character is CJK, False otherwise.
        """
        code = ord(char)
        return (
            0x4E00 <= code <= 0x9FFF   # CJK Unified Ideographs
            or 0x3400 <= code <= 0x4DBF  # CJK Unified Ideographs Extension A
            or 0x20000 <= code <= 0x2A6DF  # CJK Unified Ideographs Extension B
            or 0x2A700 <= code <= 0x2B73F  # CJK Unified Ideographs Extension C
            or 0x2B740 <= code <= 0x2B81F  # CJK Unified Ideographs Extension D
            or 0x2B820 <= code <= 0x2CEAF  # CJK Unified Ideographs Extension E
            or 0x3000 <= code <= 0x303F   # CJK Symbols and Punctuation
            or 0xFF00 <= code <= 0xFFEF   # Halfwidth and Fullwidth Forms
        )


class TiktokenTokenizer(BaseTokenizer):
    """Tokenizer using tiktoken library.

    This provides accurate token counts for OpenAI models.
    Falls back to ApproximateTokenizer if tiktoken is not available.
    """

    def __init__(self, encoding_name: str = "cl100k_base"):
        """Initialize the tiktoken tokenizer.

        Args:
            encoding_name: The name of the encoding to use.
                          Common options: cl100k_base (GPT-4), p50k_base (GPT-3)
        """
        self._encoding_name = encoding_name
        self._encoding = None
        self._fallback = ApproximateTokenizer()

        try:
            import tiktoken
            self._encoding = tiktoken.get_encoding(encoding_name)
        except ImportError:
            pass  # Will use fallback

    def count(self, text: str) -> int:
        """Count tokens using tiktoken if available, otherwise approximate.

        Args:
            text: The text to count tokens for.

        Returns:
            The number of tokens.
        """
        if not text:
            return 0

        if self._encoding is not None:
            return len(self._encoding.encode(text))

        return self._fallback.count(text)


class TokenCounter:
    """Token counter for context management.

    Provides token counting functionality with support for different
    tokenizers and buffer calculations.
    """

    def __init__(
        self,
        tokenizer: Tokenizer | None = None,
        max_tokens: int = 128000,
        buffer_ratio: float = 0.10
    ):
        """Initialize the token counter.

        Args:
            tokenizer: The tokenizer to use. Defaults to ApproximateTokenizer.
            max_tokens: Maximum token limit for the context.
            buffer_ratio: Buffer ratio for token counting errors.
        """
        self._tokenizer = tokenizer or ApproximateTokenizer()
        self._max_tokens = max_tokens
        self._buffer_ratio = buffer_ratio
        self._current_tokens = 0

    def count(self, text: str) -> int:
        """Count tokens in the given text.

        Args:
            text: The text to count tokens for.

        Returns:
            The number of tokens.
        """
        return self._tokenizer.count(text)

    def count_messages(self, messages: list[dict]) -> int:
        """Count total tokens in a list of messages.

        Args:
            messages: List of message dictionaries with 'role' and 'content'.

        Returns:
            Total token count for all messages.
        """
        total = 0
        for msg in messages:
            # Count role tokens (approximately 4 tokens per role)
            total += 4
            # Count content tokens
            content = msg.get("content", "")
            if isinstance(content, str):
                total += self.count(content)
            elif isinstance(content, list):
                # Handle multi-part content
                for part in content:
                    if isinstance(part, dict) and "text" in part:
                        total += self.count(part["text"])
        return total

    def set_current_tokens(self, count: int) -> None:
        """Set the current token count.

        Args:
            count: The current token count.
        """
        self._current_tokens = count

    def add_tokens(self, count: int) -> None:
        """Add tokens to the current count.

        Args:
            count: Number of tokens to add.
        """
        self._current_tokens += count

    def ratio(self) -> float:
        """Get the current token usage ratio.

        Returns:
            The ratio of current tokens to max tokens (0.0 to 1.0+).
        """
        if self._max_tokens == 0:
            return 0.0
        return self._current_tokens / self._max_tokens

    def remaining(self) -> int:
        """Get the remaining token budget.

        Returns:
            Number of tokens remaining before reaching the limit.
        """
        return max(0, self._max_tokens - self._current_tokens)

    def effective_limit(self) -> int:
        """Get the effective token limit after buffer.

        The buffer provides headroom for token counting inaccuracies.

        Returns:
            Effective maximum tokens after applying buffer.
        """
        return int(self._max_tokens * (1 - self._buffer_ratio))

    def can_fit(self, text: str) -> bool:
        """Check if text can fit within the remaining budget.

        Args:
            text: The text to check.

        Returns:
            True if the text can fit, False otherwise.
        """
        tokens = self.count(text)
        return self._current_tokens + tokens <= self.effective_limit()

    def should_compress(self, threshold: float = 0.92) -> bool:
        """Check if compression should be triggered.

        Args:
            threshold: The ratio threshold for triggering compression.

        Returns:
            True if compression should be triggered, False otherwise.
        """
        return self.ratio() >= threshold

    def reset(self) -> None:
        """Reset the current token count to zero."""
        self._current_tokens = 0
