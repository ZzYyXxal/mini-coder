"""OpenAI Compatible provider for LLM service.

使用 httpx 直接调用 LLM API，优化性能。
支持 ZHIPU AI、Anthropic、OpenAI 及其他兼容接口。
"""

import json
import logging
from typing import Dict, Generator, List

import httpx

from .base import LLMProvider

# Token estimation: ~4 chars per token for Chinese/English mixed content
CHARS_PER_TOKEN = 4
# Maximum tokens to send in context (leave room for response)
MAX_CONTEXT_TOKENS = 100000


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
        timeout: float = 120.0,
    ):
        """初始化 OpenAI 兼容提供商。

        Args:
            timeout: HTTP 读超时（秒）。Coder 等长上下文请求可能超过 60s，建议 120 及以上。
        """
        self._api_key = api_key
        self._base_url = base_url.rstrip('/')
        self._model = model
        self._system_prompt = system_prompt
        self._timeout = max(30.0, float(timeout))
        self._client: httpx.Client | None = None
        self._conversation: List[Dict[str, str]] = []

    def _auth_header(self) -> str:
        """返回 Authorization 头取值。多数 OpenAI 兼容接口（含百炼 DashScope）要求 Bearer 前缀。"""
        key = (self._api_key or "").strip()
        if not key:
            return ""
        if key.lower().startswith("bearer "):
            return key
        return f"Bearer {key}"

    @property
    def name(self) -> str:
        return "openai_compatible"

    @property
    def base_url(self) -> str:
        return self._base_url

    def _get_client(self) -> httpx.Client:
        """获取或创建 httpx 客户端（复用连接）。读超时由初始化时的 timeout 决定。"""
        if self._client is None:
            self._client = httpx.Client(
                timeout=httpx.Timeout(self._timeout, connect=5.0),
                follow_redirects=True,
            )
        return self._client

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Args:
            text: Text to estimate.

        Returns:
            Estimated token count.
        """
        # Simple estimation: ~4 chars per token for mixed content
        # More accurate would be to use tiktoken, but this is fast
        return max(1, len(text) // CHARS_PER_TOKEN)

    def _build_messages(self, user_message: str) -> List[Dict[str, str]]:
        """构建消息列表，带token限制。

        Ensures total context doesn't exceed MAX_CONTEXT_TOKENS.
        Recent messages are prioritized over older ones.
        """
        messages = [{"role": "system", "content": self._system_prompt}]
        system_tokens = self._estimate_tokens(self._system_prompt)
        user_tokens = self._estimate_tokens(user_message) + 10  # overhead

        # Calculate available tokens for history
        available_tokens = MAX_CONTEXT_TOKENS - system_tokens - user_tokens

        # Add history messages from newest to oldest until token limit
        history_messages = []
        current_tokens = 0

        # Iterate in reverse to prioritize recent messages
        for msg in reversed(self._conversation):
            msg_tokens = self._estimate_tokens(msg.get("content", "")) + 10
            if current_tokens + msg_tokens > available_tokens:
                # Skip older messages if they would exceed limit
                logging.debug(f"Skipping older message: {msg_tokens} tokens")
                break
            history_messages.insert(0, msg)  # Insert at beginning to maintain order
            current_tokens += msg_tokens

        if len(history_messages) < len(self._conversation):
            logging.info(
                f"Context trimmed: {len(history_messages)}/{len(self._conversation)} messages, "
                f"~{current_tokens} tokens"
            )

        messages.extend(history_messages)
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
            "Authorization": self._auth_header(),
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
            "Authorization": self._auth_header(),
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

    def send_with_context(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Generator[Dict, None, None]:
        """发送预构建的消息列表并获取流式响应。

        用于 GSSC 流水线集成，接受外部构建的消息列表。

        Args:
            messages: 预构建的消息列表，包含 role 和 content。
            **kwargs: 额外参数。

        Yields:
            Dict 包含 type 和 content 字段。
        """
        client = self._get_client()
        url = f"{self._base_url}/chat/completions"

        payload = {
            "model": self._model,
            "messages": messages,
            "stream": True,
            **kwargs
        }

        headers = {
            "Authorization": self._auth_header(),
            "Content-Type": "application/json",
        }

        full_content = ""

        with client.stream("POST", url, json=payload, headers=headers) as response:
            for line in response.iter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        if data.get("choices"):
                            delta = data["choices"][0].get("delta", {})
                            content = delta.get("content") or delta.get("reasoning_content") or ""
                            if content:
                                full_content += content
                                yield {"type": "delta", "content": content}
                    except json.JSONDecodeError:
                        continue

        # 更新内部历史以保持一致性
        if full_content:
            # 获取最后一条用户消息
            last_user_msg = None
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    last_user_msg = msg.get("content", "")
                    break

            if last_user_msg:
                self.add_to_history("user", last_user_msg)
            self.add_to_history("assistant", full_content)

        yield {"type": "done", "content": ""}

    def send_messages_one_shot(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """发送指定消息列表并返回完整响应，不写入对话历史。

        用于路由等一次性决策，避免污染主对话上下文。

        Args:
            messages: 消息列表，需包含 role 和 content。
            **kwargs: 额外请求参数。

        Returns:
            助手回复的完整文本。
        """
        client = self._get_client()
        url = f"{self._base_url}/chat/completions"

        payload = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            **kwargs
        }

        headers = {
            "Authorization": self._auth_header(),
            "Content-Type": "application/json",
        }

        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()

        data = response.json()
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        return content

    def send_messages_one_shot_stream(
        self, messages: List[Dict[str, str]], **kwargs
    ) -> Generator[Dict, None, None]:
        """发送指定消息列表并流式返回响应，不写入对话历史。

        用于子代理等一次性流式输出，避免污染主对话上下文。
        """
        client = self._get_client()
        url = f"{self._base_url}/chat/completions"

        payload = {
            "model": self._model,
            "messages": messages,
            "stream": True,
            **kwargs
        }

        headers = {
            "Authorization": self._auth_header(),
            "Content-Type": "application/json",
        }

        full_content = ""
        with client.stream("POST", url, json=payload, headers=headers) as response:
            for line in response.iter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        if data.get("choices"):
                            delta = data["choices"][0].get("delta", {})
                            content = delta.get("content") or delta.get("reasoning_content") or ""
                            if content:
                                full_content += content
                                yield {"type": "delta", "content": content}
                    except json.JSONDecodeError:
                        continue
        yield {"type": "done", "content": ""}
