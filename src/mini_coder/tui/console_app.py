"""Console-based TUI application using Rich framework.

This module provides a REPL-style interface for mini-coder,
using Rich Console for output and handling user input directly.
"""

import asyncio
import io
import logging
import signal
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.syntax import Syntax
from rich.text import Text

from mini_coder.tui.models.config import Config
from mini_coder.tui.models.thinking import ThinkingHistory


class AppState(Enum):
    """Application state enumeration."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


class WorkingMode(Enum):
    """Working mode enumeration."""

    PLAN = "plan"
    CODE = "code"
    EXECUTE = "execute"

    def __str__(self) -> str:
        """Return display name for the mode."""
        return self.value.upper()


@dataclass
class UIState:
    """State of the TUI UI."""

    current_screen: str = "welcome"
    thinking_visible: bool = False
    working_mode: WorkingMode = WorkingMode.PLAN


class MiniCoderConsole:
    """Console-based TUI for mini-coder using Rich.

    This class provides a REPL-style terminal interface with:
    - Welcome message
    - Working mode indicator
    - Simple input handling with immediate character echo
    - Backspace support
    - Mode switching with Tab
    - Ctrl+C and Ctrl+D for exit
    """

    TITLE = "mini-coder"

    def __init__(self, config: Config, directory: str | None = None) -> None:
        """Initialize the console application.

        Args:
            config: Configuration for the application.
            directory: Optional working directory path.
        """
        self.config = config
        self._console = Console()
        self._working_directory: Path | None = None
        self._state = AppState.IDLE
        self._ui_state = UIState()
        self._thinking_history = ThinkingHistory()

        if directory:
            self._working_directory = Path(directory).resolve()

        # Set up signal handlers for clean exit
        signal.signal(signal.SIGINT, self._handle_sigint)

    def _handle_sigint(self, signum: int, frame: object) -> None:
        """Handle SIGINT (Ctrl+C) for clean exit."""
        self._console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(130)

    @property
    def working_directory(self) -> Path | None:
        """Get the current working directory."""
        return self._working_directory

    @working_directory.setter
    def working_directory(self, value: Path | None) -> None:
        """Set the working directory."""
        self._working_directory = value
        # Update config if remembering last directory
        if value and self.config.working_directory.remember_last:
            self.config.working_directory.default_path = str(value)

    @property
    def state(self) -> AppState:
        """Get the current application state."""
        return self._state

    def set_state(self, state: AppState) -> None:
        """Set the application state.

        Args:
            state: New application state.
        """
        old_state = self._state
        self._state = state
        logging.debug(f"State changed: {old_state.value} -> {state.value}")

    def _toggle_working_mode(self) -> None:
        """Toggle to the next working mode in cycle."""
        modes = list(WorkingMode)
        current_index = modes.index(self._ui_state.working_mode)
        next_index = (current_index + 1) % len(modes)
        self._ui_state.working_mode = modes[next_index]
        logging.info(f"Working mode changed to: {self._ui_state.working_mode}")

    def _display_header(self) -> None:
        """Display the welcome message."""
        self._console.print()
        self._console.print(
            Panel.fit(
                "[bold cyan]mini-coder[/bold cyan]\n\n"
                "[dim]AI Coding Assistant[/dim]",
                title="Welcome",
                border_style="cyan",
            )
        )
        self._console.print(
            "[dim]Ready to help you write, debug, and understand code.[/dim]"
        )
        self._console.print(
            "[dim]Press [Tab] to cycle modes: PLAN -> CODE -> EXECUTE[/dim]"
        )
        self._console.print()

    def _get_user_input(self) -> str | None:
        """Get user input with mode indicator.

        Uses a custom implementation that provides immediate character echo.
        Handles:
        - Immediate character display
        - Backspace
        - Enter key (returns empty string, not None)
        - Tab for mode switching
        - Ctrl+C and Ctrl+D for exit

        Returns:
            User input string, or None if user wants to exit.
        """
        try:
            mode_display = Text()
            mode_display.append(str(self._ui_state.working_mode), style="bold cyan")
            mode_display.append(" ▶ ", style="default")

            buffer = ""

            while True:
                # Clear and redraw prompt with current buffer
                sys.stdout.write("\r\033[K")  # Clear line
                self._console.print(mode_display, end="")
                sys.stdout.write(buffer)
                sys.stdout.flush()

                # Read single character
                try:
                    char = sys.stdin.read(1)
                except EOFError:
                    # EOF - break out of the input loop immediately
                    # Don't call _console.print() here, return directly
                    return buffer.strip() if buffer else ""

                # Handle empty character (EOF in cbreak mode)
                if not char:
                    return buffer.strip() if buffer else ""

                # Handle Ctrl+C
                if ord(char) == 3:  # Ctrl+C
                    self._console.print()
                    return None

                # Handle Ctrl+D (EOF)
                if ord(char) == 4:  # Ctrl+D
                    self._console.print()
                    return None

                # Handle Enter key
                if char == "\r" or char == "\n":
                    self._console.print()
                    # Return buffer content (empty string is valid - user just pressed Enter)
                    return buffer.strip()

                # Handle Tab - toggle mode
                if char == "\t":
                    self._toggle_working_mode()
                    # Update mode display
                    mode_display = Text()
                    mode_display.append(str(self._ui_state.working_mode), style="bold cyan")
                    mode_display.append(" ▶ ", style="default")
                    continue

                # Handle backspace
                if char and (char == "\x7f" or char == "\b"):
                    if buffer:
                        buffer = buffer[:-1]
                    continue

                # Handle escape sequences (arrow keys)
                if char and char == "\x1b":
                    # Read the next two characters
                    next_char = sys.stdin.read(1)
                    if next_char == "[":
                        # Read the third character
                        arrow_key = sys.stdin.read(1)
                        # Could handle arrow keys here if needed
                    continue

                # Handle printable characters (including space, ASCII 32+)
                if char and ord(char) >= 32:
                    buffer += char

        except KeyboardInterrupt:
            self._console.print()
            return None

    def _get_user_input_simple(self) -> str | None:
        """Get user input for non-TTY (piped/redirected) input.

        This method reads from stdin directly, properly handling EOF for
        piped or redirected stdin without interfering with pytest output capture.

        Returns:
            User input string, or None if EOF reached.
        """
        try:
            mode_display = Text()
            mode_display.append(str(self._ui_state.working_mode), style="bold cyan")
            mode_display.append(" ▶ ", style="default")
            self._console.print(mode_display, end="")

            # Read a line from stdin
            line = sys.stdin.readline()

            if not line:  # EOF reached
                return None

            self._console.print()  # Move to new line after input
            return line.strip()

        except (EOFError, OSError):
            # EOF reached or stdin closed
            return None

    def _get_llm_config_path(self) -> Path | None:
        """Resolve path to LLM config (config/llm.yaml).

        Prefers working_directory/config/llm.yaml, then cwd/config/llm.yaml.
        """
        for base in (self._working_directory, Path.cwd()):
            if base is None:
                continue
            path = base / "config" / "llm.yaml"
            if path.is_file():
                return path
        # Fallback: cwd when no working_directory set
        path = Path.cwd() / "config" / "llm.yaml"
        return path if path.is_file() else None

    def _call_llm_stream_and_display(self, user_input: str) -> bool:
        """Run streaming LLM call and display output (sync, optimized)."""
        from mini_coder.llm.service import LLMService

        llm_config_path = self._get_llm_config_path()
        if not llm_config_path:
            logging.warning("LLM config not found (config/llm.yaml); skipping LLM call")
            return False
        try:
            # 复用 LLMService 实例（避免重复创建客户端）
            if not hasattr(self, '_llm_service') or self._llm_service is None:
                self._llm_service = LLMService(str(llm_config_path))

            # 使用同步流式方法（避免 asyncio.run 开销）
            first = True
            for event in self._llm_service.chat_stream(user_input):
                if event.get("type") == "delta":
                    content = event.get("content") or ""
                    if content:
                        self._console.print(content, end="")
                        if getattr(self._console, "file", None) is not None:
                            self._console.file.flush()
                        first = False
            self._console.print()
            return not first
        except Exception as e:
            logging.exception("LLM stream failed: %s", e)
            return False

    def _display_thinking(self, message: str = "Processing...") -> None:
        """Display thinking status.

        Args:
            message: Status message to display.
        """
        spinner = Spinner("dots", text=f"[bold blue]{message}[/bold blue]")
        self._console.print(spinner)

    def _display_response(self, response: str) -> None:
        """Display AI response.

        Args:
            response: The response text to display.
        """
        self._console.print(Markdown(response))

    def _display_code(self, code: str, language: str = "python") -> None:
        """Display code with syntax highlighting.

        Args:
            code: The code to display.
            language: Programming language for syntax highlighting.
        """
        self._console.print(Syntax(code, language, theme="monokai", line_numbers=True))

    def _display_mode_footer(self) -> None:
        """Display the mode footer."""
        self._console.print(
            f"Mode: [bold green]{self._ui_state.working_mode}[/bold green]",
            justify="right",
        )

    def run(self) -> int:
        """Run the console application.

        Returns:
            Exit code (0 for success, non-zero for error).
        """
        # Set terminal to raw mode for character-by-character input
        import termios
        import tty

        old_settings = None
        is_tty = sys.stdin.isatty()

        try:
            logging.info("mini-coder console started")

            # Save terminal settings (if available and it's a TTY)
            if is_tty:
                try:
                    old_settings = termios.tcgetattr(sys.stdin.fileno())
                    tty.setcbreak(sys.stdin.fileno())
                except (OSError, AttributeError, io.UnsupportedOperation, termios.error):
                    # Running in test environment or non-tty
                    is_tty = False

            # Display welcome message
            self._display_header()

            # Main REPL loop
            while True:
                # Get user input
                if is_tty:
                    user_input = self._get_user_input()
                else:
                    user_input = self._get_user_input_simple()

                # Check for exit conditions
                if user_input is None:
                    break

                # Check for quit commands
                if user_input.lower() in ("q", "quit", "exit"):
                    break

                # Check for empty input (Enter without typing)
                if not user_input:
                    continue

                # Process the input
                self.set_state(AppState.RUNNING)
                logging.info(f"Processing user input: {user_input[:50]}...")

                # Show thinking status, then newline so streamed response appears below
                self._display_thinking("Processing your request...")
                self._console.print()

                # Stream LLM response and print as it arrives
                ok = self._call_llm_stream_and_display(user_input)
                self._console.print()
                if not ok:
                    self._console.print(
                        Panel(
                            f"[bold]Input received:[/bold] {user_input}\n\n"
                            "[dim]No response (check config/llm.yaml and API keys).[/dim]",
                            border_style="blue",
                        )
                    )
                    self._console.print()

                self.set_state(AppState.IDLE)

            self._console.print("[yellow]Goodbye![/yellow]")
            return 0

        except Exception as e:
            logging.error(f"Application error: {e}", exc_info=True)
            self._console.print(f"[red]Error: {e}[/red]")
            return 1
        finally:
            # Restore terminal settings
            if old_settings is not None:
                try:
                    termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
                except Exception:
                    pass


def run_console_app(config: Config, directory: str | None = None) -> int:
    """Run the console application.

    Args:
        config: Configuration for the application.
        directory: Optional working directory path.

    Returns:
        Exit code (0 for success, non-zero for error).
    """
    app = MiniCoderConsole(config, directory=directory)
    return app.run()
