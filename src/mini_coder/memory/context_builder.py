"""Context Builder with GSSC pipeline for LLM context preparation.

This module implements the Gather-Select-Structure-Compress pipeline
for building optimized context for LLM calls.

Plan B Integration:
- Gather includes cached summaries
- Compress uses Plan B pruning and compression

Project Notes Integration (NoteTool-like):
- Gather includes active project notes
- Notes are prioritized as CRITICAL (never compressed)
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from .manager import ContextMemoryManager
from .priority import Priority
from .token_counter import TokenCounter

if TYPE_CHECKING:
    from .project_notes import ProjectNotesManager


class ContextBuilder:
    """Builds context for LLM calls using GSSC pipeline.

    The GSSC pipeline:
    1. Gather: Collect context from multiple sources (summaries, notes, memory)
    2. Select: Filter by priority and token limits
    3. Structure: Format for LLM consumption
    4. Compress: Optimize token usage (with Plan B integration)

    Attributes:
        manager: The context memory manager.
        notes_manager: Optional project notes manager (NoteTool-like).
        max_tokens: Maximum tokens for context.
        token_counter: Token counting utility.
    """

    def __init__(
        self,
        manager: ContextMemoryManager,
        max_tokens: int = 128000,
        notes_manager: Optional["ProjectNotesManager"] = None
    ):
        """Initialize the context builder.

        Args:
            manager: The context memory manager to use.
            max_tokens: Maximum tokens for context.
            notes_manager: Optional project notes manager for structured notes.
        """
        self._manager = manager
        self._max_tokens = max_tokens
        self._token_counter = TokenCounter(max_tokens=max_tokens)
        self._notes_manager = notes_manager

    def build(
        self,
        max_tokens: Optional[int] = None,
        include_project_memory: bool = False,
        project_path: Optional[str] = None,
        auto_compress: bool = False
    ) -> list[dict]:
        """Build context using the GSSC pipeline.

        Args:
            max_tokens: Maximum tokens for context. Uses default if not provided.
            include_project_memory: Whether to include CLAUDE.md content.
            project_path: Path to project for CLAUDE.md lookup.
            auto_compress: Whether to trigger Plan B compression if needed.

        Returns:
            List of message dictionaries ready for LLM call.
        """
        token_limit = max_tokens or self._max_tokens

        # Phase 1: Gather
        gathered = self._gather(include_project_memory, project_path)

        # Phase 2: Select
        selected = self._select(gathered, token_limit)

        # Phase 3: Structure
        structured = self._structure(selected)

        # Phase 4: Compress (with optional Plan B integration)
        compressed = self._compress(structured, token_limit, auto_compress)

        return compressed

    def build_with_compression(
        self,
        max_tokens: Optional[int] = None,
        include_project_memory: bool = False,
        project_path: Optional[str] = None
    ) -> tuple[list[dict], dict]:
        """Build context with Plan B compression, returning statistics.

        This method triggers compression if needed and returns
        statistics about the compression operation.

        Args:
            max_tokens: Maximum tokens for context.
            include_project_memory: Whether to include CLAUDE.md content.
            project_path: Path to project for CLAUDE.md lookup.

        Returns:
            Tuple of (context, stats) where stats contains compression info.
        """
        token_limit = max_tokens or self._max_tokens
        stats = {
            "pruned_tokens": 0,
            "compressed_messages": 0,
            "tokens_saved": 0,
            "compression_triggered": False,
        }

        # Check if compression is needed
        if self._manager.should_compress():
            stats["compression_triggered"] = True

            # Try pruning first
            pruned = self._manager.prune_tool_outputs()
            stats["pruned_tokens"] = pruned

            # If still over limit, do full compression
            if self._manager.should_compress():
                summary = self._manager.compress()
                if summary:
                    stats["compressed_messages"] = len(summary.original_message_ids)
                    stats["tokens_saved"] = summary.metadata.get("tokens_saved", 0)

        # Build context with auto_compress=False (we already handled it)
        context = self.build(
            max_tokens=token_limit,
            include_project_memory=include_project_memory,
            project_path=project_path,
            auto_compress=False
        )

        return context, stats

    def run_compression_if_needed(self) -> dict:
        """仅执行 Plan B 压缩（prune + 必要时 compress），不构建 context；用于与 build_with_user_message 配合，避免重复 build。

        返回与 build_with_compression 相同的 stats 结构，便于调用方展示「已清理/已压缩」提示。
        """
        stats = {
            "pruned_tokens": 0,
            "compressed_messages": 0,
            "tokens_saved": 0,
            "compression_triggered": False,
        }
        if self._manager.should_compress():
            stats["compression_triggered"] = True
            pruned = self._manager.prune_tool_outputs()
            stats["pruned_tokens"] = pruned
            if self._manager.should_compress():
                summary = self._manager.compress()
                if summary:
                    stats["compressed_messages"] = len(summary.original_message_ids)
                    stats["tokens_saved"] = summary.metadata.get("tokens_saved", 0)
        return stats

    def _gather(
        self,
        include_project_memory: bool,
        project_path: Optional[str]
    ) -> list[dict]:
        """Gather context from multiple sources.

        Sources (Plan B enhanced + NoteTool integration):
        - Project notes (decisions, todos, patterns) - NoteTool-like
        - Cached summaries (high value, low token cost)
        - Working memory (conversation history)
        - Project memory (CLAUDE.md)

        Args:
            include_project_memory: Whether to include CLAUDE.md.
            project_path: Path to project.

        Returns:
            List of gathered messages.
        """
        messages = []

        # NoteTool integration: Add project notes first (highest priority)
        if self._notes_manager:
            notes_content = self._format_project_notes()
            if notes_content:
                messages.append({
                    "role": "system",
                    "content": notes_content,
                    "priority": Priority.CRITICAL,
                    "timestamp": datetime(1970, 1, 1).isoformat()
                })

        # Plan B: Add cached summaries (high value, low token cost)
        summaries = self._manager.summaries
        if summaries:
            summary_content = self._format_summaries(summaries)
            messages.append({
                "role": "system",
                "content": summary_content,
                "priority": Priority.CRITICAL,
                "timestamp": datetime(1970, 1, 1).isoformat()
            })

        # Get conversation history from working memory
        context = self._manager.get_context(self._max_tokens)
        messages.extend(context)

        # Optionally include project memory
        if include_project_memory and project_path:
            project_memory = self._load_project_memory(project_path)
            if project_memory:
                messages.insert(0, {
                    "role": "system",
                    "content": project_memory,
                    "priority": Priority.HIGH,
                    "timestamp": datetime(1970, 1, 1).isoformat()
                })

        return messages

    def _format_project_notes(self) -> str:
        """Format project notes for context inclusion.

        Returns:
            Formatted notes string, or empty string if no notes.
        """
        if not self._notes_manager:
            return ""

        return self._notes_manager.format_notes_for_context(
            max_notes=15,
            max_tokens=1500
        )

    def _format_summaries(self, summaries: list) -> str:
        """Format summaries into a system message.

        Args:
            summaries: List of Summary objects.

        Returns:
            Formatted summary text.
        """
        if not summaries:
            return ""

        lines = ["[对话历史摘要]"]
        for i, summary in enumerate(summaries[-5:], 1):  # Last 5 summaries
            count = len(summary.original_message_ids)
            lines.append(f"{i}. 压缩了 {count} 条消息")
            # Add truncated content preview
            content_preview = summary.content[:200]
            if len(summary.content) > 200:
                content_preview += "..."
            lines.append(f"   {content_preview}")

        return "\n".join(lines)

    def _select(
        self,
        messages: list[dict],
        max_tokens: int
    ) -> list[dict]:
        """Select messages based on priority and token limits.

        Args:
            messages: Messages to filter.
            max_tokens: Maximum tokens.

        Returns:
            Filtered messages.
        """
        if not messages:
            return []

        # Sort by priority (lower = higher priority)
        sorted_messages = sorted(
            messages,
            key=lambda m: m.get("priority", 5)
        )

        # Select messages within token limit
        counter = TokenCounter(max_tokens=max_tokens)
        selected = []

        for msg in sorted_messages:
            content = msg.get("content", "")
            msg_tokens = counter.count(content) + 4  # +4 for role

            if counter._current_tokens + msg_tokens <= counter.effective_limit():
                selected.append(msg)
                counter.add_tokens(msg_tokens)

        return selected

    def _structure(self, messages: list[dict]) -> list[dict]:
        """Structure messages for LLM consumption.

        Ensures messages are in the correct format and order.

        Args:
            messages: Messages to structure.

        Returns:
            Structured messages.
        """
        def get_sort_key(m: dict) -> str:
            """Get a string sort key for timestamp."""
            ts = m.get("timestamp", "")
            if isinstance(ts, datetime):
                return ts.isoformat()
            return str(ts) if ts else ""

        # Sort by timestamp to maintain conversation order
        structured = sorted(
            messages,
            key=get_sort_key
        )

        # Ensure required fields
        result = []
        for msg in structured:
            structured_msg = {
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            }
            result.append(structured_msg)

        return result

    def _compress(
        self,
        messages: list[dict],
        max_tokens: int,
        auto_compress: bool = False
    ) -> list[dict]:
        """Compress context if it exceeds token limit.

        Plan B integration:
        - If auto_compress=True, triggers Manager compression
        - Otherwise, does simple truncation

        Args:
            messages: Messages to compress.
            max_tokens: Maximum tokens.
            auto_compress: Whether to trigger Plan B compression.

        Returns:
            Compressed messages.
        """
        # Check current token count
        current_tokens = self._token_counter.count_messages(messages)

        if current_tokens <= max_tokens * 0.9:  # 10% buffer
            return messages

        # If auto_compress, trigger Plan B compression
        if auto_compress and self._manager.should_compress():
            logging.info(f"Auto-compression triggered: {current_tokens} tokens")
            self._manager.prune_tool_outputs()
            if self._manager.should_compress():
                self._manager.compress()
            # Re-gather after compression
            messages = self._gather(False, None)
            messages = self._select(messages, max_tokens)
            messages = self._structure(messages)

        # Final truncation if still over limit
        counter = TokenCounter(max_tokens=max_tokens)
        compressed = []

        for msg in messages:
            content = msg.get("content", "")
            msg_tokens = counter.count(content) + 4

            if counter._current_tokens + msg_tokens <= counter.effective_limit():
                compressed.append(msg)
                counter.add_tokens(msg_tokens)

        return compressed

    def _load_project_memory(self, project_path: str) -> Optional[str]:
        """Load project memory from CLAUDE.md file.

        Args:
            project_path: Path to the project.

        Returns:
            Project memory content if found, None otherwise.
        """
        claude_md_path = Path(project_path) / "CLAUDE.md"
        if claude_md_path.exists():
            try:
                return claude_md_path.read_text(encoding="utf-8")
            except Exception:
                pass
        return None

    def build_with_user_message(
        self,
        user_message: str,
        max_tokens: Optional[int] = None,
        include_project_memory: bool = False,
        project_path: Optional[str] = None,
        auto_compress: bool = False
    ) -> list[dict]:
        """Build context including a new user message.

        This is the primary method for preparing context before
        an LLM call.

        Args:
            user_message: The user's message.
            max_tokens: Maximum tokens for context.
            include_project_memory: Whether to include CLAUDE.md.
            project_path: Path to project.
            auto_compress: Whether to trigger Plan B compression.

        Returns:
            Context with user message appended.
        """
        # Build base context
        context = self.build(
            max_tokens=max_tokens,
            include_project_memory=include_project_memory,
            project_path=project_path,
            auto_compress=auto_compress
        )

        # Append user message
        context.append({
            "role": "user",
            "content": user_message
        })

        return context

    def estimate_tokens(self, messages: list[dict]) -> int:
        """Estimate total tokens in a list of messages.

        Args:
            messages: Messages to estimate.

        Returns:
            Estimated token count.
        """
        return self._token_counter.count_messages(messages)
