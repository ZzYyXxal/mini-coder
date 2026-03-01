"""Zhipu (智谱) provider for LLM service.

Provider implementation for GLM API (open.bigmodel.cn).
Uses OpenAI-compatible chat completions endpoint.
API key can be set in config (llm.yaml) or via environment variable ZHIPU_API_KEY.
"""

import asyncio
import json
import os
import urllib.error
import urllib.request
from typing import AsyncIterator, Dict, List

from .base import LLMProvider


class ZHIPUProvider(LLMProvider):
    """Zhipu / 智谱 GLM LLM provider."""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://open.bigmodel.cn/api/paas/v4/",
        model: str = "",
    ):
        """Initialize Zhipu provider.

        Args:
            api_key: API key (Bearer). If empty or placeholder "ZHIPU_API_KEY",
                reads from environment variable ZHIPU_API_KEY.
            base_url: Base URL, e.g. https://open.bigmodel.cn/api/paas/v4/
            model: Model name, e.g. glm-5 or glm-4-flash.
        """
        if api_key and api_key != "ZHIPU_API_KEY":
            self._api_key = api_key
        else:
            self._api_key = os.environ.get("ZHIPU_API_KEY", "").strip()
        self._base_url = base_url.rstrip("/") + "/"
        self._model = model or "glm-4-flash"

    @property
    def name(self) -> str:
        """Provider name."""
        return "zhipu"

    @property
    def base_url(self) -> str:
        """API base URL."""
        return self._base_url

    def _chat_completions_sync(
        self, messages: List[Dict[str, str]], stream: bool = False
    ) -> str:
        """Call chat/completions (sync, for use in thread)."""
        if not self._api_key:
            return "[Zhipu] 请配置有效的 api_key（config/llm.yaml 或环境变量 ZHIPU_API_KEY）。"
        url = self._base_url + "chat/completions"
        body = {
            "model": self._model,
            "messages": messages,
            "stream": stream,
            "max_tokens": 2048,
            "temperature": 0.7,
        }
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8")
            out = json.loads(raw)
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8")
                err_json = json.loads(err_body)
                msg = err_json.get("error", {}).get("message", err_body)
            except Exception:
                msg = str(e)
            return f"[Zhipu 请求错误] {msg}"
        except (OSError, json.JSONDecodeError) as e:
            return f"[Zhipu 请求失败] {e!s}"
        choices = out.get("choices") or []
        if not choices:
            return "[Zhipu] 无返回内容。"
        content = (choices[0].get("message") or {}).get("content") or ""
        return content.strip()

    def _stream_request_to_queue(
        self,
        messages: List[Dict[str, str]],
        queue: asyncio.Queue[str | None],
    ) -> None:
        """Run streaming HTTP request (sync), push content chunks to queue.

        Puts each content delta into queue; puts None when done or on error.
        Designed to run in a thread (run_in_executor).
        """
        if not self._api_key:
            queue.put_nowait("[Zhipu] 请配置有效的 api_key（config/llm.yaml 或环境变量 ZHIPU_API_KEY）。")
            queue.put_nowait(None)
            return
        url = self._base_url + "chat/completions"
        body = {
            "model": self._model,
            "messages": messages,
            "stream": True,
            "max_tokens": 2048,
            "temperature": 0.7,
        }
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                buf = b""
                while True:
                    chunk = resp.read(512)
                    if not chunk:
                        break
                    buf += chunk
                    while b"\n" in buf:
                        line, _, buf = buf.partition(b"\n")
                        line = line.strip().strip(b"\r")
                        if not line or line == b"data: [DONE]":
                            continue
                        if line.startswith(b"data: "):
                            try:
                                payload = json.loads(line[6:].decode("utf-8"))
                                delta = (payload.get("choices") or [{}])[0].get("delta") or {}
                                content = delta.get("content") or ""
                                if content:
                                    queue.put_nowait(content)
                            except (json.JSONDecodeError, KeyError, IndexError):
                                pass
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8")
                err_json = json.loads(err_body)
                msg = err_json.get("error", {}).get("message", err_body)
            except Exception:
                msg = str(e)
            queue.put_nowait(f"[Zhipu 请求错误] {msg}")
        except (OSError, json.JSONDecodeError) as e:
            queue.put_nowait(f"[Zhipu 请求失败] {e!s}")
        finally:
            queue.put_nowait(None)

    async def send_message(
        self, messages: List[Dict[str, str]], **kwargs
    ) -> AsyncIterator[str]:
        """Send messages and get response (one chunk for now).

        Args:
            messages: List of message dicts with 'role' and 'content'.
            **kwargs: Ignored.

        Yields:
            Response text chunk(s).
        """
        loop = asyncio.get_running_loop()
        content = await loop.run_in_executor(
            None, lambda: self._chat_completions_sync(messages, stream=False)
        )
        if content:
            yield content

    async def send_message_stream(
        self, messages: List[Dict[str, str]], **kwargs
    ) -> AsyncIterator[Dict[str, str]]:
        """Send messages and yield delta events (streaming).

        Args:
            messages: List of message dicts with 'role' and 'content'.
            **kwargs: Ignored.

        Yields:
            Delta dicts: {"type": "delta", "content": "..."} and {"type": "done", "content": ""}.
        """
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        future = loop.run_in_executor(
            None,
            lambda: self._stream_request_to_queue(messages, queue),
        )
        try:
            while True:
                chunk = await queue.get()
                if chunk is None:
                    break
                yield {"type": "delta", "content": chunk}
        finally:
            await future
        yield {"type": "done", "content": ""}
