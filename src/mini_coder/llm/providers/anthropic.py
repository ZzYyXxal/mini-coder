"""Anthropic provider for LLM service.

Provider implementation for Claude/Anthropic API.
"""

from typing import AsyncIterator, Dict, List

from .base import LLMProvider


class AnthropicProvider(LLMProvider):
    """Anthropic LLM provider."""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.anthropic.com",
        model: str = "claude-3-5-sonnet-20241022",
    ):
        """Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key.
            base_url: API base URL.
            model: Model name to use.
        """
        self._api_key = api_key
        self._base_url = base_url
        self._model = model

    @property
    def name(self) -> str:
        """Provider name."""
        return "anthropic"

    @property
    def base_url(self) -> str:
        """API base URL."""
        return self._base_url

    async def send_message(
        self, messages: List[Dict[str, str]], **kwargs
    ) -> AsyncIterator[str]:
        """Send messages and get response.

        Args:
            messages: List of message dictionaries with 'role' and 'content'.
            **kwargs: Additional keyword arguments.

        Returns:
            AsyncIterator yielding response chunks.
        """
        # TODO: Implement actual Anthropic API call
        # For now, return a simulated response
        last_message = messages[-1].get('content', '') if messages else ''
        response = f"[Anthropic 模拟响应] 收到消息: {last_message[:50]}..."
        yield response

    async def send_message_stream(
        self, messages: List[Dict[str, str]], **kwargs
    ) -> AsyncIterator[Dict[str, str]]:
        """Send messages and get stream response in delta format.

        Args:
            messages: List of message dictionaries with 'role' and 'content'.
            **kwargs: Additional keyword arguments.

        Returns:
            AsyncIterator yielding delta events.
        """
        # TODO: Implement actual Anthropic streaming API call
        # For now, return simulated delta events
        last_message = messages[-1].get('content', '') if messages else ''

        # Simulate streaming response
        response_text = f"收到您的消息: {last_message[:30]}... 正在处理中..."

        # Yield delta events
        for char in response_text:
            yield {"type": "delta", "content": char}

        # Yield completion event
        yield {"type": "done", "content": ""}
