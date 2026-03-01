"""Main TUI application class.

This module provides the main application class for mini-coder TUI,
delegating to the Rich-based console implementation for better input handling.
"""

from pathlib import Path
from typing import Any

from mini_coder.tui.models.config import Config
from mini_coder.tui.models.thinking import ThinkingHistory

# Import console app for actual implementation
from mini_coder.tui.console_app import (
    AppState,
    MiniCoderConsole,
    UIState,
    WorkingMode,
)


class MiniCoderTUI:
    """Main TUI application for mini-coder.

    This class provides a terminal user interface by delegating to the
    Rich-based console implementation. It maintains compatibility with the
    existing API while using a simpler REPL-style interface.

    The console approach (similar to aider) provides:
    - Better keyboard input handling
    - Simpler focus management
    - More reliable text echo in the input field
    - Cleaner separation of concerns
    """

    TITLE = "mini-coder"

    def __init__(self, config: Config, directory: str | None = None) -> None:
        """Initialize the TUI application.

        Args:
            config: Configuration for the application.
            directory: Optional working directory path.
        """
        self.config = config
        self._console_app = MiniCoderConsole(config, directory=directory)
        self._thinking_history = ThinkingHistory()
        self._mode_label: Any = None  # For backward compatibility with tests

    @property
    def title(self) -> str:
        """Get the application title."""
        return self.TITLE

    @property
    def working_directory(self) -> Path | None:
        """Get the current working directory."""
        return self._console_app.working_directory

    @working_directory.setter
    def working_directory(self, value: Path | None) -> None:
        """Set the working directory."""
        self._console_app.working_directory = value

    @property
    def state(self) -> AppState:
        """Get the current application state."""
        return self._console_app.state

    def set_state(self, state: AppState) -> None:
        """Set the application state.

        Args:
            state: New application state.
        """
        self._console_app.set_state(state)

    @property
    def _ui_state(self) -> UIState:
        """Get the UI state (for backward compatibility)."""
        return self._console_app._ui_state

    def _toggle_working_mode(self) -> None:
        """Toggle to the next working mode in cycle."""
        self._console_app._toggle_working_mode()

    def _update_mode_display(self) -> None:
        """Update the mode display (for backward compatibility)."""
        # This is a no-op in console mode, as mode is displayed in prompt
        pass

    def run(  # type: ignore
        self,
        headless: bool = False,
        inline: bool = False,
        inline_no_clear: bool = False,
        mouse: bool = False,
        size: tuple[int, int] | None = None,
        auto_pilot: Any = None,
        loop: Any = None,
    ) -> int:
        """Run the TUI application.

        Args:
            headless: Run without a terminal (ignored in console mode).
            inline: Run inline (ignored in console mode).
            inline_no_clear: Run inline without clearing (ignored in console mode).
            mouse: Enable mouse support (ignored in console mode).
            size: Terminal size (ignored in console mode).
            auto_pilot: Auto pilot callback (ignored in console mode).
            loop: Event loop (ignored in console mode).

        Returns:
            Exit code (0 for success, non-zero for error).
        """
        # Delegate to console app implementation
        return self._console_app.run()


# Export classes for backward compatibility
__all__ = ["MiniCoderTUI", "AppState", "WorkingMode", "UIState"]
