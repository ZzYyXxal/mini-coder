"""LLM Service module.

Provides unified service interface for LLM integration.
Supports streaming responses and multiple provider management.
"""

import asyncio
from typing import Dict, List

from .providers.base import LLMProvider


class LLMService:
    """LLM Service for managing provider connections and message sending."""

    def __init__(self, config_path: str) -> None:
        """Initialize LLM service with configuration.

        Args:
            config_path: Path to configuration YAML file.
        """
        self.config_path = config_path
        self.provider: Optional[LLMProvider] = None
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        import yaml
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
                self.provider_name = config.get('default_provider', 'anthropic')

                # Get provider config
                provider_config = config.get(self.provider_name, {})

                # Create provider instance
                from .providers import anthropic, zhipu, openai, custom

                if self.provider_name == 'anthropic':
                    from .providers.anthropic import AnthropicProvider
                    self.provider = AnthropicProvider(
                        api_key=provider_config.get('api_key', ''),
                        base_url=provider_config.get('base_url', 'https://api.anthropic.com'),
                        model=provider_config.get('model', 'claude-3-5-sonnet-20241022'),
                        max_tokens=provider_config.get('max_tokens', 4096),
                        temperature=provider_config.get('temperature', 0.7)
                    )

                elif self.provider_name == 'zhipu':
                    from .providers.zhipu import ZHIPUProvider
                    self.provider = ZHIPUProvider(
                        api_key=provider_config.get('api_key', ''),
                        base_url=provider_config.get('base_url', 'https://open.bigmodel.cn/api/paas/v4/'),
                        model=provider_config.get('model', ''),
                        max_tokens=provider_config.get('max_tokens', 4096),
                        temperature=provider_config.get('temperature', 0.7)
                    )

                elif self.provider_name == 'openai':
                    from .providers.openai import OpenAIProvider
                    self.provider = OpenAIProvider(
                        api_key=provider_config.get('api_key', ''),
                        base_url=provider_config.get('base_url', 'https://api.openai.com/v1/'),
                        model=provider_config.get('model', 'gpt-4o-mini'),
                        max_tokens=provider_config.get('max_tokens', 4096),
                        temperature=provider_config.get('temperature', 0.7)
                    )

                elif self.provider_name == 'custom':
                    from .providers.custom import CustomProvider
                    self.provider = CustomProvider(
                        api_key=provider_config.get('api_key', ''),
                        base_url=provider_config.get('base_url', ''),
                        model=provider_config.get('model', ''),
                        max_tokens=provider_config.get('max_tokens', 4096),
                        temperature=provider_config.get('temperature', 0.7),
                        headers=provider_config.get('headers', {})
                    )

        except FileNotFoundError:
            # Config file not found, use defaults
            self.provider_name = 'anthropic'
            from .providers.anthropic import AnthropicProvider
            self.provider = AnthropicProvider(
                api_key='',
                base_url='https://api.anthropic.com',
                model='claude-3-5-sonnet-20241022',
                max_tokens=4096,
                temperature=0.7
            )

    async def send_message(
        self, messages: List[Dict[str, str]], **kwargs
    ) -> AsyncIterator[str]:
        """Send messages and get response stream.

        Args:
            messages: List of message dictionaries with 'role' and 'content'.
            **kwargs: Additional keyword arguments.

        Returns:
            AsyncIterator yielding response chunks.
        """
        if self.provider is None:
            raise ValueError("No LLM provider configured. Please set up a provider first.")

        return await self.provider.send_message(messages, **kwargs)

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
        """
        if self.provider is None:
            raise ValueError("No LLM provider configured. Please set up a provider first.")

        return await self.provider.send_message_stream(messages, **kwargs)

    def set_provider(self, provider_name: str) -> None:
        """Switch to a different LLM provider.

        Args:
            provider_name: Name of the provider to switch to.
        """
        self._load_config()
        self.provider_name = provider_name

        # Get provider config
        provider_config = self.config.get(provider_name, {})

        # Recreate provider
        if provider_name == 'anthropic':
            from .providers.anthropic import AnthropicProvider
            self.provider = AnthropicProvider(
                        api_key=provider_config.get('api_key', ''),
                        base_url=provider_config.get('base_url', 'https://api.anthropic.com'),
                        model=provider_config.get('model', 'claude-3-5-sonnet-20241022'),
                        max_tokens=provider_config.get('max_tokens', 4096),
                        temperature=provider_config.get('temperature', 0.7)
                    )

        elif provider_name == 'zhipu':
            from .providers.zhipu import ZHIPUProvider
            self.provider = ZHIPUProvider(
                        api_key=provider_config.get('api_key', ''),
                        base_url=provider_config.get('base_url', 'https://open.bigmodel.cn/api/paas/v4/'),
                        model=provider_config.get('model', ''),
                        max_tokens=provider_config.get('max_tokens', 4096),
                        temperature=provider_config.get('temperature', 0.7)
                    )

        elif provider_name == 'openai':
            from .providers.openai import OpenAIProvider
            self.provider = OpenAIProvider(
                        api_key=provider_config.get('api_key', ''),
                        base_url=provider_config.get('base_url', 'https://api.openai.com/v1/'),
                        model=provider_config.get('model', 'gpt-4o-mini'),
                        max_tokens=provider_config.get('max_tokens', 4096),
                        temperature=provider_config.get('temperature', 0.7)
                    )

        elif provider_name == 'custom':
            from .providers.custom import CustomProvider
            self.provider = CustomProvider(
                        api_key=provider_config.get('api_key', ''),
                        base_url=provider_config.get('base_url', ''),
                        model=provider_config.get('model', ''),
                        max_tokens=provider_config.get('max_tokens', 4096),
                        temperature=provider_config.get('temperature', 0.7),
                        headers=provider_config.get('headers', {})
                    )

        # Save updated config
        self._save_config()

    def _save_config(self) -> None:
        """Save current configuration to YAML file."""
        import yaml

        # Get current config
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
        except FileNotFoundError:
                # Create default config if file doesn't exist
                config = {
                    'default_provider': 'anthropic',
                    'anthropic': {
                        'api_key': '',
                        'base_url': 'https://api.anthropic.com',
                        'model': 'claude-3-5-sonnet-20241022',
                        'max_tokens': 4096,
                        'temperature': 0.7
                    }
                }

        # Update with current provider name
        provider_name = config.get('default_provider', 'anthropic')
        config[provider_name] = config.get(provider_name, {})

        # Merge with provider config
        for key in config[provider_name]:
            if key not in config[provider_name]:
                config[provider_name][key] = config.get(key, {})
            config[provider_name]['name'] = self.provider_name

        # Save
        with open(self.config_path, 'w') as f:
            yaml.safe_dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
