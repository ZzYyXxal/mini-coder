"""LLM Provider base module.

Provides abstract base class for LLM service providers.
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, List, Optional


class LLMProvider(ABC):
    """Abstract base class for LLM service providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass

    @property
    @abstractmethod
    def base_url(self) -> str:
        """API base URL."""
        pass

    @abstractmethod
    async def send_message(
        self, messages: List[Dict[str, str]], **kwargs
    ) -> AsyncIterator[str]:
        """Send messages and get response stream.

        Args:
            messages: List of message dictionaries with 'role' and 'content'.
            **kwargs: Additional keyword arguments (e.g., temperature, max_tokens).

        Returns:
            AsyncIterator yielding response chunks.
        """
        pass

    @abstractmethod
    async def send_message_stream(
        self, messages: List[Dict[str, str]], **kwargs
    ) -> AsyncIterator[Dict[str, str]]:
        """Send messages and get stream response in delta format.

        Args:
            messages: List of message dictionaries with 'role' and 'content'.
            **kwargs: Additional keyword arguments.

        Returns:
            AsyncIterator yielding delta events with type field:
            - 'delta' for content updates
            - 'message' for complete messages
            - 'done' for completion
        """
        pass
