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

    # Loop detection constants
    MAX_RESPONSE_LENGTH = 50000  # Maximum characters in a single response
    MAX_REPEATED_PATTERN = 5     # Maximum times a pattern can repeat consecutively
    PATTERN_MIN_LENGTH = 5       # Minimum length for pattern detection

    def _detect_loop(self, content: str, full_response: str) -> bool:
        """Detect if the LLM is in a loop.

        Args:
            content: The latest chunk of content.
            full_response: The full response so far.

        Returns:
            True if a loop is detected, False otherwise.
        """
        # Check 1: Maximum response length
        if len(full_response) > self.MAX_RESPONSE_LENGTH:
            logging.warning(f"Loop detected: response exceeded {self.MAX_RESPONSE_LENGTH} chars")
            return True

        # Check 2: Repeated pattern detection
        # Look for patterns that repeat consecutively
        if len(content) >= self.PATTERN_MIN_LENGTH:
            # Check if the last N chars repeat more than MAX_REPEATED_PATTERN times
            for pattern_len in range(self.PATTERN_MIN_LENGTH, min(len(content) + 1, 50)):
                pattern = content[-pattern_len:]
                # Count consecutive repetitions at the end of full_response
                count = 0
                pos = len(full_response)
                while pos >= pattern_len and full_response[pos - pattern_len:pos] == pattern:
                    count += 1
                    pos -= pattern_len

                if count >= self.MAX_REPEATED_PATTERN:
                    logging.warning(f"Loop detected: pattern '{pattern[:20]}...' repeated {count} times")
                    return True

        # Check 3: Known loop patterns (e.g., "Unknown" repeating)
        known_patterns = ["Unknown", "undefined", "null", "NaN", "ERROR"]
        for pattern in known_patterns:
            # Check if pattern appears many times consecutively
            repeated = pattern * self.MAX_REPEATED_PATTERN
            if repeated in full_response:
                logging.warning(f"Loop detected: known pattern '{pattern}' repeating")
                return True

        return False

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
                # 尝试恢复最近的会话，如果没有则启动新会话
                if self._llm_service.memory_enabled:
                    if not self._llm_service.restore_latest_session():
                        # 没有可恢复的会话，启动新会话
                        self._llm_service.start_session(str(self._working_directory) if self._working_directory else None)

            # 使用同步流式方法（避免 asyncio.run 开销）
            first = True
            full_response = ""
            loop_detected = False

            for event in self._llm_service.chat_stream(user_input):
                if event.get("type") == "delta":
                    content = event.get("content") or ""
                    if content:
                        full_response += content

                        # Check for loop
                        if self._detect_loop(content, full_response):
                            loop_detected = True
                            self._console.print()
                            self._console.print(
                                "\n[yellow]⚠ Response interrupted: loop detected[/yellow]"
                            )
                            logging.warning("LLM response interrupted due to loop detection")
                            break

                        self._console.print(content, end="")
                        if getattr(self._console, "file", None) is not None:
                            self._console.file.flush()
                        first = False

            self._console.print()

            if loop_detected:
                self._console.print(
                    "[dim]The AI response was interrupted to prevent infinite output. "
                    "This may indicate an issue with the model or context.[/dim]"
                )

            return not first
        except Exception as e:
            logging.exception("LLM stream failed: %s", e)
            return False

    def _handle_special_commands(self, user_input: str) -> bool:
        """Handle special commands like /memory, /sessions.

        Args:
            user_input: The user input to check.

        Returns:
            True if the input was a special command, False otherwise.
        """
        if not user_input.startswith("/"):
            return False

        command = user_input.lower().strip()

        if command == "/memory":
            self._show_memory_status()
            return True

        if command in ("/sessions", "/session"):
            self._show_sessions()
            return True

        if command.startswith("/save"):
            self._save_current_session()
            return True

        if command.startswith("/restore"):
            self._restore_session(command)
            return True

        if command == "/help":
            self._show_help()
            return True

        return False

    def _show_memory_status(self) -> None:
        """Display memory status."""
        if not hasattr(self, '_llm_service') or self._llm_service is None:
            self._console.print("[yellow]Memory: LLM service not initialized[/yellow]")
            return

        if not self._llm_service.memory_enabled:
            self._console.print("[yellow]Memory: Disabled[/yellow]")
            return

        manager = self._llm_service._context_manager
        self._console.print(Panel(
            f"[bold]Memory Status[/bold]\n"
            f"Session ID: {manager.current_session_id or 'None'}\n"
            f"Messages: {manager.message_count}\n"
            f"Token Ratio: {manager.token_ratio:.1%}",
            border_style="blue"
        ))

    def _show_sessions(self) -> None:
        """Display saved sessions."""
        if not hasattr(self, '_llm_service') or self._llm_service is None:
            self._console.print("[yellow]Sessions: LLM service not initialized[/yellow]")
            return

        sessions = self._llm_service.list_sessions()
        if not sessions:
            self._console.print("[yellow]No saved sessions[/yellow]")
            return

        self._console.print(Panel(
            "[bold]Saved Sessions[/bold]\n" + "\n".join(f"  • {s}" for s in sessions),
            border_style="blue"
        ))

    def _save_current_session(self) -> None:
        """Save the current session."""
        if not hasattr(self, '_llm_service') or self._llm_service is None:
            self._console.print("[yellow]Session: LLM service not initialized[/yellow]")
            return

        if not self._llm_service.memory_enabled:
            self._console.print("[yellow]Session: Memory disabled[/yellow]")
            return

        self._llm_service.save_session()
        self._console.print(f"[green]Session saved: {self._llm_service.session_id}[/green]")

    def _restore_session(self, command: str) -> None:
        """Restore a session."""
        if not hasattr(self, '_llm_service') or self._llm_service is None:
            self._console.print("[yellow]Session: LLM service not initialized[/yellow]")
            return

        parts = command.split()
        if len(parts) < 2:
            # Try to restore latest session
            if self._llm_service.restore_latest_session():
                self._console.print(f"[green]Restored latest session: {self._llm_service.session_id}[/green]")
            else:
                self._console.print("[yellow]No session to restore[/yellow]")
            return

        session_id = parts[1]
        if self._llm_service.load_session(session_id):
            self._console.print(f"[green]Restored session: {session_id}[/green]")
        else:
            self._console.print(f"[red]Session not found: {session_id}[/red]")

    def _show_help(self) -> None:
        """Display help for special commands."""
        self._console.print(Panel(
            "[bold]Special Commands[/bold]\n"
            "  /memory   - Show memory status\n"
            "  /sessions - List saved sessions\n"
            "  /save     - Save current session\n"
            "  /restore  - Restore latest session\n"
            "  /restore <id> - Restore specific session\n"
            "  /help     - Show this help",
            border_style="blue"
        ))

    def _cleanup(self) -> None:
        """Cleanup resources before exit."""
        if hasattr(self, '_llm_service') and self._llm_service is not None:
            if self._llm_service.memory_enabled:
                self._llm_service.save_session()

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

                # Handle special commands
                if self._handle_special_commands(user_input):
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

            # Save session before exit
            self._cleanup()

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
