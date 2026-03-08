"""Memory Hook - 将记忆系统挂载为 agent 调用的 pre/post 钩子。

参考方案 4.4：记忆系统作为 hook 工具，在 agent 调用前加载并去重，调用后按需压缩与摘要。

- pre_step: 从存储加载 memory、去重，返回供 LLM 使用的消息列表。
- post_step: 若触发压缩/淘汰条件，则执行 prune + 摘要压缩，返回统计。
"""

import hashlib
import logging
from typing import Any, Dict, List, Optional

from .manager import ContextMemoryManager
from .context_builder import ContextBuilder

logger = logging.getLogger(__name__)


def _message_fingerprint(msg: Dict[str, Any], max_content_len: int = 500) -> str:
    """生成单条消息的指纹，用于去重。"""
    role = msg.get("role", "")
    content = (msg.get("content") or "")[:max_content_len]
    raw = f"{role}:{content}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _dedupe_messages(
    from_memory: List[Dict[str, Any]],
    current_messages: Optional[List[Dict[str, Any]]] = None,
    tail_window: int = 3,
) -> List[Dict[str, Any]]:
    """合并并去重：以 memory 为基，再合并 current；同指纹在 result 末尾 tail_window 条内则用 current 覆盖，否则去重追加。

    - from_memory: 从 get_context 得到的历史（含摘要等）。
    - current_messages: 当前轮待发送的消息（如 system + 本轮 user），避免与 memory 尾部重复。
    - tail_window: 末尾多少条内若指纹与 current 重复，用 current 覆盖（避免重复 user/assistant）。
    """
    seen: set = set()
    result: List[Dict[str, Any]] = []

    for m in from_memory:
        fp = _message_fingerprint(m)
        if fp not in seen:
            seen.add(fp)
            result.append(dict(m))

    if not current_messages:
        return result

    for m in current_messages:
        fp = _message_fingerprint(m)
        if fp in seen:
            # 已在 result 中：若在末尾 tail_window 内则用 current 覆盖
            for i in range(len(result) - 1, max(-1, len(result) - tail_window) - 1, -1):
                if i >= 0 and _message_fingerprint(result[i]) == fp:
                    result[i] = dict(m)
                    break
        else:
            seen.add(fp)
            result.append(dict(m))

    return result


class MemoryHook:
    """记忆钩子：在 agent 调用前（pre_step）加载并去重，调用后（post_step）按需压缩与摘要。

    可挂载到 LLMService 或任意「先取上下文再发请求、请求后再写回」的调用链。
    """

    def __init__(
        self,
        manager: ContextMemoryManager,
        context_builder: Optional[ContextBuilder] = None,
    ):
        """初始化钩子。

        Args:
            manager: 上下文记忆管理器（加载、写入、压缩均通过它）。
            context_builder: 可选；若提供则 pre_step 可用 build 得到带摘要/笔记的上下文；否则仅用 manager.get_context。
        """
        self._manager = manager
        self._context_builder = context_builder

    def pre_step(
        self,
        max_tokens: int = 128000,
        current_messages: Optional[List[Dict[str, Any]]] = None,
        dedupe: bool = True,
        include_project_memory: bool = False,
        project_path: Optional[str] = None,
        run_compression_first: bool = True,
    ) -> List[Dict[str, Any]]:
        """Agent 调用前：从 memory 存储加载上下文，可选与当前消息合并并去重。

        Args:
            max_tokens: 上下文 token 上限。
            current_messages: 当前轮已有的消息（如 system + 本轮 user），用于合并去重。
            dedupe: 是否对 memory 与 current_messages 做去重。
            include_project_memory: 是否包含项目记忆（如 CLAUDE.md）。
            project_path: 项目路径，用于加载项目记忆。
            run_compression_first: 是否在加载前先执行一次压缩（腾出空间再加载）。

        Returns:
            供 LLM 使用的消息列表（role/content 等）。
        """
        if not self._manager.is_enabled:
            return list(current_messages) if current_messages else []

        if run_compression_first and self._manager.should_compress():
            self._manager.prune_tool_outputs()
            if self._manager.should_compress():
                self._manager.compress()

        # 使用 ContextBuilder 时得到带摘要/笔记的完整上下文
        if self._context_builder:
            ctx = self._context_builder.build(
                max_tokens=max_tokens,
                include_project_memory=include_project_memory,
                project_path=project_path,
                auto_compress=False,
            )
        else:
            ctx = self._manager.get_context(max_tokens=max_tokens)

        if not dedupe:
            if current_messages:
                # 仅追加 current 中未在 ctx 中的（简单按顺序合并，不去重）
                return ctx + current_messages
            return ctx

        return _dedupe_messages(ctx, current_messages, tail_window=3)

    def post_step(self) -> Dict[str, Any]:
        """Agent 调用后：若触发压缩/淘汰条件，则执行 prune 与摘要压缩。

        调用方应在「已把本轮 user 与 assistant 消息写入 manager」之后调用本方法。

        Returns:
            统计字典：pruned_tokens, compressed_messages, tokens_saved, compression_triggered。
        """
        stats: Dict[str, Any] = {
            "pruned_tokens": 0,
            "compressed_messages": 0,
            "tokens_saved": 0,
            "compression_triggered": False,
        }
        if not self._manager.is_enabled:
            return stats

        if not self._manager.should_compress():
            return stats

        stats["compression_triggered"] = True
        pruned = self._manager.prune_tool_outputs()
        stats["pruned_tokens"] = pruned

        if self._manager.should_compress():
            summary = self._manager.compress()
            if summary:
                stats["compressed_messages"] = len(summary.original_message_ids)
                stats["tokens_saved"] = summary.metadata.get("tokens_saved", 0)
                logger.info(
                    "[MemoryHook] post_step compressed %s messages, tokens_saved=%s",
                    stats["compressed_messages"],
                    stats["tokens_saved"],
                )

        return stats
