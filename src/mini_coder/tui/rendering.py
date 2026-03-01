"""Typewriter text rendering for TUI.

This module provides the typewriter animation effect for displaying
text character by character with configurable speed and state management.
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator


class AnimationState(Enum):
    """State of the typewriter animation."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    CANCELED = "canceled"
    COMPLETED = "completed"


@dataclass
class TypewriterRenderer:
    """Renderer for typewriter text animation."""

    speed_preset_delay: dict[str, float] = field(
        default_factory=lambda: {
            "slow": 50.0,
            "normal": 20.0,
            "fast": 5.0,
        }
    )
    state: AnimationState = AnimationState.IDLE
    _pause_event: asyncio.Event = field(default_factory=asyncio.Event)
    _cancel_event: asyncio.Event = field(default_factory=asyncio.Event)

    def __post_init__(self) -> None:
        """Initialize the renderer."""
        self._pause_event.set()  # Start unpaused

    def get_delay(
        self, speed: str | None = None, custom_delay: int | None = None
    ) -> float:
        """Get the delay for animation.

        Args:
            speed: Speed preset ("slow", "normal", "fast").
            custom_delay: Custom delay in milliseconds.

        Returns:
            Delay in seconds.
        """
        if custom_delay is not None:
            return custom_delay / 1000.0

        if speed in self.speed_preset_delay:
            return self.speed_preset_delay[speed] / 1000.0

        return self.speed_preset_delay["normal"] / 1000.0

    def pause(self) -> None:
        """Pause the animation."""
        if self.state == AnimationState.RUNNING:
            self.state = AnimationState.PAUSED
            self._pause_event.clear()

    def resume(self) -> None:
        """Resume the animation."""
        if self.state == AnimationState.PAUSED:
            self.state = AnimationState.RUNNING
            self._pause_event.set()

    def cancel(self) -> None:
        """Cancel the animation."""
        if self.state in (AnimationState.RUNNING, AnimationState.PAUSED):
            self.state = AnimationState.CANCELED
            self._cancel_event.set()

    def reset(self) -> None:
        """Reset the renderer state."""
        self.state = AnimationState.IDLE
        self._pause_event.set()
        self._cancel_event.clear()

    async def render(
        self,
        text: str,
        speed: str | None = None,
        custom_delay: int | None = None,
        batch_size: int = 3,
        instant: bool = False,
    ) -> AsyncIterator[str]:
        """Render text character by character.

        Args:
            text: Text to render.
            speed: Speed preset.
            custom_delay: Custom delay in milliseconds.
            batch_size: Number of characters to render per batch.
            instant: If True, render immediately without animation.

        Yields:
            Rendered text chunks.
        """
        self.reset()
        self.state = AnimationState.RUNNING

        if instant:
            self.state = AnimationState.COMPLETED
            yield text
            return

        delay = self.get_delay(speed, custom_delay)

        for i in range(0, len(text), batch_size):
            # Check for cancellation
            if self._cancel_event.is_set():
                self.state = AnimationState.CANCELED
                yield text[i:]  # Yield remaining text
                return

            # Wait if paused
            await self._pause_event.wait()

            # Check for cancellation again after resume
            if self._cancel_event.is_set():
                self.state = AnimationState.CANCELED
                yield text[i:]
                return

            # Yield batch of characters
            chunk = text[i : i + batch_size]
            yield chunk

            # Wait for delay
            await asyncio.sleep(delay)

        self.state = AnimationState.COMPLETED
