"""OpenAI Compatible provider for LLM service.

使用 httpx 直接调用 LLM API，优化性能。
支持 ZHIPU AI、Anthropic、OpenAI 及其他兼容接口。
"""

import json
from typing import Dict, Generator, List

import httpx

from .base import LLMProvider


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI 兼容的 LLM 提供商。

    使用 httpx 直接调用 API，性能更优。
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        model: str = "",
        system_prompt: str = "你是一个有用的 AI 助手",
    ):
        """初始化 OpenAI 兼容提供商。"""
        self._api_key = api_key
        self._base_url = base_url.rstrip('/')
        self._model = model
        self._system_prompt = system_prompt
        self._client: httpx.Client | None = None
        self._conversation: List[Dict[str, str]] = []

    @property
    def name(self) -> str:
        return "openai_compatible"

    @property
    def base_url(self) -> str:
        return self._base_url

    def _get_client(self) -> httpx.Client:
        """获取或创建 httpx 客户端（复用连接）。"""
        if self._client is None:
            self._client = httpx.Client(
                timeout=httpx.Timeout(60.0, connect=5.0),
                follow_redirects=True,
            )
        return self._client

    def _build_messages(self, user_message: str) -> List[Dict[str, str]]:
        """构建消息列表。"""
        messages = [{"role": "system", "content": self._system_prompt}]
        messages.extend(self._conversation)
        messages.append({"role": "user", "content": user_message})
        return messages

    def add_to_history(self, role: str, content: str) -> None:
        """添加消息到对话历史。"""
        self._conversation.append({"role": role, "content": content})

    def clear_history(self) -> None:
        """清除对话历史。"""
        self._conversation = []

    def send_message(self, message: str, **kwargs) -> str:
        """发送消息并获取响应（非流式）。"""
        client = self._get_client()
        url = f"{self._base_url}/chat/completions"

        payload = {
            "model": self._model,
            "messages": self._build_messages(message),
            "stream": False,
            **kwargs
        }

        headers = {
            "Authorization": self._api_key,
            "Content-Type": "application/json",
        }

        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()

        data = response.json()
        content = data["choices"][0]["message"]["content"]

        self.add_to_history("user", message)
        self.add_to_history("assistant", content)
        return content

    def send_message_stream(self, message: str, **kwargs) -> Generator[Dict, None, None]:
        """发送消息并获取流式响应（高性能）。"""
        client = self._get_client()
        url = f"{self._base_url}/chat/completions"

        payload = {
            "model": self._model,
            "messages": self._build_messages(message),
            "stream": True,
            **kwargs
        }

        headers = {
            "Authorization": self._api_key,
            "Content-Type": "application/json",
        }

        self.add_to_history("user", message)
        full_content = ""

        with client.stream("POST", url, json=payload, headers=headers) as response:
            for line in response.iter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    data_str = line[6:]  # 去掉 "data: " 前缀
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        if data.get("choices"):
                            delta = data["choices"][0].get("delta", {})
                            # 支持 reasoning_content 和 content 两种格式
                            content = delta.get("content") or delta.get("reasoning_content") or ""
                            if content:
                                full_content += content
                                yield {"type": "delta", "content": content}
                    except json.JSONDecodeError:
                        continue

        self.add_to_history("assistant", full_content)
        yield {"type": "done", "content": ""}

    async def async_send_message(self, message: str, **kwargs) -> str:
        """异步发送消息（使用同步实现）。"""
        return self.send_message(message, **kwargs)

    async def async_send_message_stream(self, message: str, **kwargs):
        """异步流式发送（使用同步实现）。"""
        for chunk in self.send_message_stream(message, **kwargs):
            yield chunk
