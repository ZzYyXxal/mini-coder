"""Tests for interactive console app functionality using mocking."""

from unittest.mock import MagicMock, patch

from mini_coder.tui.console_app import (
    AppState,
    MiniCoderConsole,
    WorkingMode,
)
from mini_coder.tui.models.config import Config


class TestConsoleAppInteractiveMethods:
    """Tests for interactive methods in console app."""

    def test_display_header(self) -> None:
        """Test display_header method exists and can be called."""
        config = Config()
        app = MiniCoderConsole(config)

        # Method should exist and be callable
        assert hasattr(app, "_display_header")
        assert callable(app._display_header)

    def test_display_thinking_method_exists(self) -> None:
        """Test _display_thinking method exists and can be called."""
        config = Config()
        app = MiniCoderConsole(config)

        # Method should exist and be callable
        assert hasattr(app, "_display_thinking")
        assert callable(app._display_thinking)

    @patch("mini_coder.tui.console_app.Console.print")
    def test_display_thinking_with_custom_message(
        self, mock_print: MagicMock
    ) -> None:
        """Test _display_thinking with custom message."""
        from rich.spinner import Spinner

        config = Config()
        app = MiniCoderConsole(config)

        app._display_thinking("Custom message")

        # Verify Console.print was called with a Spinner
        mock_print.assert_called_once()
        args, _ = mock_print.call_args
        assert isinstance(args[0], Spinner)

    def test_display_response_method_exists(self) -> None:
        """Test _display_response method exists and can be called."""
        config = Config()
        app = MiniCoderConsole(config)

        # Method should exist and be callable
        assert hasattr(app, "_display_response")
        assert callable(app._display_response)

    @patch("mini_coder.tui.console_app.Console.print")
    def test_display_response_with_markdown(self, mock_print: MagicMock) -> None:
        """Test _display_response processes markdown."""
        from rich.markdown import Markdown

        config = Config()
        app = MiniCoderConsole(config)

        app._display_response("Test response")

        # Verify Console.print was called
        mock_print.assert_called_once()
        args, _ = mock_print.call_args
        assert len(args) == 1
        assert isinstance(args[0], Markdown)

    def test_display_code_method_exists(self) -> None:
        """Test _display_code method exists and can be called."""
        config = Config()
        app = MiniCoderConsole(config)

        # Method should exist and be callable
        assert hasattr(app, "_display_code")
        assert callable(app._display_code)

    @patch("mini_coder.tui.console_app.Console.print")
    def test_display_code_with_syntax(self, mock_print: MagicMock) -> None:
        """Test _display_code with syntax highlighting."""
        from rich.syntax import Syntax

        config = Config()
        app = MiniCoderConsole(config)

        code = "def hello():\n    return 'world'"
        app._display_code(code, language="python")

        # Verify Console.print was called with Syntax
        mock_print.assert_called_once()
        args, _ = mock_print.call_args
        assert len(args) == 1
        assert isinstance(args[0], Syntax)
        # Syntax is constructed with line_numbers=True and theme="monokai"

    def test_display_mode_footer_method_exists(self) -> None:
        """Test _display_mode_footer method exists and can be called."""
        config = Config()
        app = MiniCoderConsole(config)

        # Method should exist and be callable
        assert hasattr(app, "_display_mode_footer")
        assert callable(app._display_mode_footer)

    @patch("mini_coder.tui.console_app.Console.print")
    def test_display_mode_footer(self, mock_print: MagicMock) -> None:
        """Test _display_mode_footer displays current mode."""
        config = Config()
        app = MiniCoderConsole(config)

        app._ui_state.working_mode = WorkingMode.CODE
        app._display_mode_footer()

        # Verify Console.print was called
        mock_print.assert_called_once()
        args, kwargs = mock_print.call_args
        assert "CODE" in args[0]
        assert kwargs.get("justify") == "right"

    @patch("mini_coder.tui.console_app.Console.print")
    def test_display_mode_footer_plan_mode(self, mock_print: MagicMock) -> None:
        """Test _display_mode_footer with PLAN mode."""
        config = Config()
        app = MiniCoderConsole(config)

        app._ui_state.working_mode = WorkingMode.PLAN
        app._display_mode_footer()

        args, _ = mock_print.call_args
        assert "PLAN" in args[0]

    @patch("mini_coder.tui.console_app.Console.print")
    def test_display_mode_footer_execute_mode(self, mock_print: MagicMock) -> None:
        """Test _display_mode_footer with EXECUTE mode."""
        config = Config()
        app = MiniCoderConsole(config)

        app._ui_state.working_mode = WorkingMode.EXECUTE
        app._display_mode_footer()

        args, _ = mock_print.call_args
        assert "EXECUTE" in args[0]

    def test_run_method_exists(self) -> None:
        """Test run method exists and is callable."""
        config = Config()
        app = MiniCoderConsole(config)

        # Method should exist and be callable
        assert hasattr(app, "run")
        assert callable(app.run)

    def test_handle_sigint_method_exists(self) -> None:
        """Test _handle_sigint method exists."""
        config = Config()
        app = MiniCoderConsole(config)

        # Method should exist and be callable
        assert hasattr(app, "_handle_sigint")
        assert callable(app._handle_sigint)

    @patch("sys.exit")
    @patch("mini_coder.tui.console_app.Console.print")
    def test_handle_sigint_exits(
        self, mock_print: MagicMock, mock_exit: MagicMock
    ) -> None:
        """Test _handle_sigint calls sys.exit."""
        import signal

        config = Config()
        app = MiniCoderConsole(config)

        app._handle_sigint(signal.SIGINT, None)

        # Verify print was called and sys.exit was called
        mock_print.assert_called_once()
        args, _ = mock_print.call_args
        assert "Interrupted" in str(args[0])
        mock_exit.assert_called_once_with(130)


class TestConsoleAppStateTransitions:
    """Tests for state transitions in console app."""

    def test_multiple_state_transitions(self) -> None:
        """Test multiple state transitions."""
        config = Config()
        app = MiniCoderConsole(config)

        # Test transitioning through all states
        app.set_state(AppState.RUNNING)
        assert app.state == AppState.RUNNING

        app.set_state(AppState.PAUSED)
        assert app.state == AppState.PAUSED

        # Test changing back to RUNNING
        assert app.state == AppState.PAUSED
        app.set_state(AppState.RUNNING)
        assert app.state == AppState.RUNNING

        app.set_state(AppState.COMPLETED)
        assert app.state == AppState.COMPLETED

        app.set_state(AppState.IDLE)
        assert app.state == AppState.IDLE


class TestConsoleWorkingModeTransitions:
    """Tests for working mode transitions."""

    def test_multiple_toggle_cycles(self) -> None:
        """Test multiple toggle cycles."""
        config = Config()
        app = MiniCoderConsole(config)

        # Test multiple cycles
        for _ in range(6):
            app._toggle_working_mode()

        # After 6 toggles (2 full cycles), should be back at PLAN
        assert app._ui_state.working_mode == WorkingMode.PLAN

    def test_mode_persistence(self) -> None:
        """Test that mode persists across operations."""
        config = Config()
        app = MiniCoderConsole(config)

        # Set to CODE
        app._ui_state.working_mode = WorkingMode.CODE

        # Perform some state changes
        app.set_state(AppState.RUNNING)
        app.set_state(AppState.PAUSED)

        # Mode should still be CODE
        assert app._ui_state.working_mode == WorkingMode.CODE


class TestConsoleAppErrorHandling:
    """Tests for error handling in console app."""

    @patch("mini_coder.tui.console_app.Console.print")
    def test_run_method_exception_handling(self, mock_print: MagicMock) -> None:
        """Test run method handles exceptions."""
        config = Config()
        app = MiniCoderConsole(config)

        # Mock _get_user_input to raise an exception
        # Also mock sys.stdin.isatty at the console_app module level
        with patch("mini_coder.tui.console_app.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = True
            with patch.object(app, "_get_user_input", side_effect=Exception("Test error")):
                result = app.run()

        # Should handle exception and return non-zero exit code
        assert result == 1
        # Verify error message was printed
        error_calls = [call for call in mock_print.call_args_list if "Error" in str(call)]
        assert len(error_calls) > 0

    def test_run_method_return_type(self) -> None:
        """Test run method returns int."""
        config = Config()
        app = MiniCoderConsole(config)

        # Mock _get_user_input to immediately return None (quit)
        with patch.object(app, "_get_user_input", return_value=None):
            result = app.run()

        # Should return int
        assert isinstance(result, int)


class TestConsoleAppUIState:
    """Tests for UI state management."""

    def test_ui_state_screen_changes(self) -> None:
        """Test UI state screen transitions."""
        config = Config()
        app = MiniCoderConsole(config)

        # Change screen
        app._ui_state.current_screen = "thinking"
        assert app._ui_state.current_screen == "thinking"

        app._ui_state.current_screen = "default"
        assert app._ui_state.current_screen == "default"

        app._ui_state.current_screen = "welcome"
        assert app._ui_state.current_screen == "welcome"

    def test_ui_state_thinking_visible(self) -> None:
        """Test UI state thinking visibility."""
        config = Config()
        app = MiniCoderConsole(config)

        # Initially false
        assert app._ui_state.thinking_visible is False

        # Set to true
        app._ui_state.thinking_visible = True
        assert app._ui_state.thinking_visible is True

        # Set back to false
        app._ui_state.thinking_visible = False
        assert app._ui_state.thinking_visible is False

    def test_ui_state_all_modes(self) -> None:
        """Test UI state with all working modes."""
        config = Config()
        app = MiniCoderConsole(config)

        for mode in WorkingMode:
            app._ui_state.working_mode = mode
            assert app._ui_state.working_mode == mode
            assert str(app._ui_state.working_mode) == mode.value.upper()
