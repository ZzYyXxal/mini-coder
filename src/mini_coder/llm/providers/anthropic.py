"""Anthropic provider for LLM service.

Simulated provider for demonstration and testing purposes.
"""

import asyncio
from typing import AsyncIterator, Dict, List

from ..base import LLMProvider


class AnthropicProvider(LLMProvider):
    """Anthropic LLM provider (simulated)."""

    @property
    def name(self) -> str:
        """Provider name."""
        return "anthropic"

    @property
    def base_url(self) -> str:
        """API base URL."""
        return self.api_key

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        model: str = "claude-3-5-sonnet-20241022",
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def send_message(
        self, messages: List[Dict[str, str]], **kwargs
    ) -> AsyncIterator[str]:
        """Send messages and get simulated response.

        For now, return a simple simulated response.
        TODO: Integrate actual Anthropic API when available.
        """
        # Simulate a simple response
        response = f"[模拟响应] You asked: {messages[-1].get('content', 'user') if messages else ''}"

        # Yield as stream
        yield {"type": "message", "content": response}

    async def send_message_stream(
        self, messages: List[Dict[str, str]], **kwargs
    ) -> AsyncIterator[Dict[str, str]]:
        """Send messages and get simulated stream response in delta format.

        For now, return a simple simulated delta stream.
        """
        # Simulate delta format
        yield {"type": "delta", "content": "Simulated response stream..."}

    def _create_mock_client(self) -> None:
        """Create mock Anthropic client (for demonstration).

        Returns a mock object that simulates API responses.
        """
        return self
