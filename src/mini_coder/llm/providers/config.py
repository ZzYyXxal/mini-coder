"""LLM Providers config module.

Extends configuration model to support LLM provider fields.
"""

from typing import Dict, Optional


class Config:
    """Configuration model for LLM providers."""

    def __init__(
        self,
        default_provider: str = "anthropic",
        providers: Dict[str, Dict] = None,
    ):
        self.default_provider = default_provider
        self.providers = providers if providers else {}

        # Initialize default provider config
        self.providers['anthropic'] = {
            'api_key': '',
            'base_url': 'https://api.anthropic.com',
            'model': 'claude-3-5-sonnet-20241022',
            'max_tokens': 4096,
            'temperature': 0.7,
        }

    def get(self, provider_name: str, key: str, default: Optional[str] = None) -> Optional[Dict]:
        """Get configuration value for a specific provider and key.

        Args:
            provider_name: Name of the provider.
            key: Configuration key to retrieve.
            default: Default value if key not found.

        Returns:
            Configuration dictionary for the provider, or None if not found.
        """
        if provider_name not in self.providers:
            raise ValueError(f"Unknown provider: {provider_name}")

        provider_config = self.providers.get(provider_name, {})

        if key is None:
            return provider_config.get(key, None)

        return provider_config.get(key)

    def set(self, provider_name: str, config: Dict[str, str]) -> None:
        """Set configuration for a provider.

        Args:
            provider_name: Name of the provider.
            config: Configuration dictionary with keys and values.

        Raises:
            ValueError: If provider name is unknown.
        """
        if provider_name not in self.providers:
            raise ValueError(f"Unknown provider: {provider_name}")

        if provider_name not in self.providers:
            self.providers[provider_name] = {}
            for key, value in config.items():
                self.providers[provider_name][key] = value
