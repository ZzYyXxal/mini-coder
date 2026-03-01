"""LLM Service module.

使用 OpenAI SDK 兼容接口统一管理 LLM 服务。
支持对话、流式响应、多轮对话。
"""

from typing import Dict, List, Optional

from .providers.base import LLMProvider
from .providers.openai_compatible import OpenAICompatibleProvider


class LLMService:
    """LLM Service - 使用 OpenAI SDK 兼容接口。"""

    def __init__(self, config_path: str) -> None:
        """初始化 LLM 服务。

        Args:
            config_path: 配置文件路径（YAML）。
        """
        self.config_path = config_path
        self.provider: Optional[OpenAICompatibleProvider] = None
        self.provider_name: str = "zhipu"
        self._load_config()

    def _load_config(self) -> None:
        """从 YAML 文件加载配置。"""
        import yaml
        import os

        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
                self.provider_name = config.get('default_provider', 'zhipu')

                # 获取提供商配置
                providers = config.get('providers', {})
                provider_config = providers.get(self.provider_name, {})

                # 从环境变量获取 API Key（优先级高于配置文件）
                api_key = os.getenv(f"{self.provider_name.upper()}_API_KEY") or \
                          provider_config.get('api_key', '')

                # 创建统一的 OpenAI 兼容提供商
                self.provider = OpenAICompatibleProvider(
                    api_key=api_key,
                    base_url=provider_config.get('base_url', ''),
                    model=provider_config.get('model', ''),
                )

        except FileNotFoundError:
            # 配置文件不存在，使用默认值
            self.provider_name = 'zhipu'
            import os
            self.provider = OpenAICompatibleProvider(
                api_key=os.getenv("ZHIPU_API_KEY", ""),
                base_url="https://open.bigmodel.cn/api/paas/v4/",
                model="glm-5",
            )

    def chat(self, message: str, **kwargs) -> str:
        """发送消息并获取响应（非流式）。

        Args:
            message: 用户消息。
            **kwargs: 额外参数。

        Returns:
            AI 响应内容。
        """
        if self.provider is None:
            raise ValueError("No LLM provider configured.")
        return self.provider.send_message(message, **kwargs)

    def chat_stream(self, message: str, **kwargs):
        """发送消息并获取流式响应。

        Args:
            message: 用户消息。
            **kwargs: 额外参数。

        Yields:
            Dict 包含 type 和 content 字段。
        """
        if self.provider is None:
            raise ValueError("No LLM provider configured.")
        return self.provider.send_message_stream(message, **kwargs)

    async def async_chat(self, message: str, **kwargs) -> str:
        """异步发送消息并获取响应。

        Args:
            message: 用户消息。
            **kwargs: 额外参数。

        Returns:
            AI 响应内容。
        """
        if self.provider is None:
            raise ValueError("No LLM provider configured.")
        return await self.provider.async_send_message(message, **kwargs)

    async def async_chat_stream(self, message: str, **kwargs):
        """异步发送消息并获取流式响应。

        Args:
            message: 用户消息。
            **kwargs: 额外参数。

        Yields:
            Dict 包含 type 和 content 字段。
        """
        if self.provider is None:
            raise ValueError("No LLM provider configured.")
        async for chunk in self.provider.async_send_message_stream(message, **kwargs):
            yield chunk

    def clear_history(self) -> None:
        """清除对话历史。"""
        if self.provider:
            self.provider.clear_history()

    def set_provider(self, provider_name: str) -> None:
        """切换提供商。

        Args:
            provider_name: 提供商名称。
        """
        self.provider_name = provider_name
        self._load_config()
