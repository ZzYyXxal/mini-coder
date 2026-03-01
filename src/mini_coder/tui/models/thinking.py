"""AI thinking message models.

This module provides data structures for representing AI reasoning steps
and thought processes in the TUI.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class ThinkingType(Enum):
    """Type of thinking message."""

    PLAN = "PLAN"
    ANALYSIS = "ANALYSIS"
    REFLECTION = "REFLECTION"


@dataclass
class ThinkingMessage:
    """A single AI thinking message."""

    step: int
    timestamp: datetime
    message_type: ThinkingType
    content: str
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "step": self.step,
            "timestamp": self.timestamp.isoformat(),
            "message_type": self.message_type.value,
            "content": self.content,
            "metadata": self.metadata or {},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ThinkingMessage":
        """Create from dictionary."""
        return cls(
            step=data["step"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            message_type=ThinkingType(data["message_type"]),
            content=data["content"],
            metadata=data.get("metadata"),
        )

    def to_markdown(self) -> str:
        """Convert to markdown format."""
        prefix = f"[{self.message_type.value}]"
        return f"## {prefix} Step {self.step}\n\n{self.content}"

    def get_color(self) -> str:
        """Get the color for displaying this message type."""
        color_map = {
            ThinkingType.PLAN: "blue",
            ThinkingType.ANALYSIS: "purple",
            ThinkingType.REFLECTION: "yellow",
        }
        return color_map.get(self.message_type, "white")


class ThinkingHistory:
    """Container for thinking message history."""

    def __init__(self, max_entries: int = 100) -> None:
        """Initialize the thinking history.

        Args:
            max_entries: Maximum number of entries to store.
        """
        self.max_entries = max_entries
        self._messages: list[ThinkingMessage] = []
        self._next_step = 1

    def add(self, message: ThinkingMessage) -> None:
        """Add a message to the history.

        Args:
            message: Message to add.
        """
        self._messages.append(message)
        # Enforce max entries
        if len(self._messages) > self.max_entries:
            self._messages = self._messages[-self.max_entries :]

    def get_all(self) -> list[ThinkingMessage]:
        """Get all messages in the history.

        Returns:
            List of all messages.
        """
        return list(self._messages)

    def get_by_type(self, message_type: ThinkingType) -> list[ThinkingMessage]:
        """Get messages of a specific type.

        Args:
            message_type: Type of messages to retrieve.

        Returns:
            List of messages of the specified type.
        """
        return [msg for msg in self._messages if msg.message_type == message_type]

    def search(self, query: str) -> list[ThinkingMessage]:
        """Search messages for a query string.

        Args:
            query: Search query.

        Returns:
            List of messages matching the query.
        """
        query_lower = query.lower()
        return [msg for msg in self._messages if query_lower in msg.content.lower()]

    def clear(self) -> None:
        """Clear all messages from the history."""
        self._messages.clear()
        self._next_step = 1

    def to_markdown(self) -> str:
        """Export history to markdown format.

        Returns:
            Markdown string containing all messages.
        """
        sections = []
        for message in self._messages:
            sections.append(message.to_markdown())
        return "\n\n---\n\n".join(sections)

    def to_json(self) -> str:
        """Export history to JSON format.

        Returns:
            JSON string containing all messages.
        """
        return json.dumps(
            [msg.to_dict() for msg in self._messages],
            indent=2,
        )

    def get_next_step(self) -> int:
        """Get the next step number.

        Returns:
            Next step number.
        """
        return self._next_step

    def increment_step(self) -> None:
        """Increment the step counter."""
        self._next_step += 1
