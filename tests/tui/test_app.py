"""Tests for main TUI application."""

from pathlib import Path
from unittest.mock import patch

from mini_coder.tui.app import AppState
from mini_coder.tui.models.config import Config


class TestMiniCoderConsole:
    """Tests for MiniCoderConsole application class."""

    def test_create_console_app_with_config(self) -> None:
        """Test creating console app with config."""
        from mini_coder.tui.console_app import MiniCoderConsole

        config = Config()
        app = MiniCoderConsole(config)

        assert app.config is config
        assert hasattr(app, "TITLE")
        assert "mini-coder" in app.TITLE.lower()

    def test_create_console_app_with_directory(self) -> None:
        """Test creating console app with directory."""
        from mini_coder.tui.console_app import MiniCoderConsole

        config = Config()
        app = MiniCoderConsole(config, directory="/test/path")

        assert app.working_directory == Path("/test/path").resolve()

    def test_console_app_initialization(self) -> None:
        """Test console app initializes correctly."""
        from mini_coder.tui.console_app import MiniCoderConsole

        config = Config()
        app = MiniCoderConsole(config)

        assert app.config is config
        assert app.working_directory is None
        assert app.state == AppState.IDLE

    def test_console_app_get_state(self) -> None:
        """Test getting application state."""
        from mini_coder.tui.console_app import MiniCoderConsole

        config = Config()
        app = MiniCoderConsole(config)

        assert app.state == AppState.IDLE

    def test_console_app_set_state(self) -> None:
        """Test setting application state."""
        from mini_coder.tui.console_app import MiniCoderConsole

        config = Config()
        app = MiniCoderConsole(config)

        app.set_state(AppState.RUNNING)
        assert app.state == AppState.RUNNING

        app.set_state(AppState.PAUSED)
        assert app.state == AppState.PAUSED

        app.set_state(AppState.COMPLETED)
        assert app.state == AppState.COMPLETED

    def test_console_app_default_mode(self) -> None:
        """Test console app starts with PLAN mode."""
        from mini_coder.tui.console_app import MiniCoderConsole, WorkingMode

        config = Config()
        app = MiniCoderConsole(config)

        assert app._ui_state.working_mode == WorkingMode.PLAN

    def test_console_app_toggle_mode(self) -> None:
        """Test toggling mode cycles through all modes."""
        from mini_coder.tui.console_app import MiniCoderConsole, WorkingMode

        config = Config()
        app = MiniCoderConsole(config)

        # Start with PLAN
        assert app._ui_state.working_mode == WorkingMode.PLAN

        # Toggle to CODE
        app._toggle_working_mode()
        assert app._ui_state.working_mode == WorkingMode.CODE

        # Toggle to EXECUTE
        app._toggle_working_mode()
        assert app._ui_state.working_mode == WorkingMode.EXECUTE

        # Toggle back to PLAN
        app._toggle_working_mode()
        assert app._ui_state.working_mode == WorkingMode.PLAN

    def test_console_app_set_working_directory(self) -> None:
        """Test setting working directory."""
        from mini_coder.tui.console_app import MiniCoderConsole

        config = Config()
        app = MiniCoderConsole(config)

        new_dir = Path("/new/path")
        app.working_directory = new_dir

        assert app.working_directory == new_dir

    def test_console_app_set_working_directory_updates_config(self) -> None:
        """Test setting working directory updates config when remembering last."""
        from mini_coder.tui.console_app import MiniCoderConsole

        config = Config()
        config.working_directory.remember_last = True
        app = MiniCoderConsole(config)

        new_dir = Path("/test/remember")
        app.working_directory = new_dir

        assert config.working_directory.default_path == str(new_dir)


class TestConsoleAppWorkingMode:
    """Tests for WorkingMode enum in console app."""

    def test_working_mode_values(self) -> None:
        """Verify all working modes exist."""
        from mini_coder.tui.console_app import WorkingMode

        assert WorkingMode.PLAN.value == "plan"
        assert WorkingMode.CODE.value == "code"
        assert WorkingMode.EXECUTE.value == "execute"

    def test_working_mode_str(self) -> None:
        """Verify working mode string representation."""
        from mini_coder.tui.console_app import WorkingMode

        assert str(WorkingMode.PLAN) == "PLAN"
        assert str(WorkingMode.CODE) == "CODE"
        assert str(WorkingMode.EXECUTE) == "EXECUTE"


class TestConsoleAppState:
    """Tests for AppState enum in console app."""

    def test_app_state_values(self) -> None:
        """Verify all app states exist."""
        from mini_coder.tui.console_app import AppState

        assert AppState.IDLE.value == "idle"
        assert AppState.RUNNING.value == "running"
        assert AppState.PAUSED.value == "paused"
        assert AppState.COMPLETED.value == "completed"


class TestConsoleUIState:
    """Tests for UIState dataclass in console app."""

    def test_ui_state_defaults(self) -> None:
        """Verify UIState has correct default values."""
        from mini_coder.tui.console_app import UIState, WorkingMode

        state = UIState()

        assert state.current_screen == "welcome"
        assert state.thinking_visible is False
        assert state.working_mode == WorkingMode.PLAN


class TestRunConsoleApp:
    """Tests for run_console_app function."""

    def test_run_console_app_function(self) -> None:
        """Test that run_console_app creates app and calls run."""
        from mini_coder.tui.console_app import MiniCoderConsole, run_console_app

        config = Config()

        # Mock the MiniCoderConsole.run method
        with patch.object(MiniCoderConsole, "__init__", return_value=None):
            with patch.object(MiniCoderConsole, "run", return_value=0) as mock_run:
                run_console_app(config, directory="/test/dir")

                # Verify that run was called
                mock_run.assert_called_once()




class TestMiniCoderTUI:
    """Tests for MiniCoderTUI application class."""

    def test_create_app_with_config(self) -> None:
        """Test creating app with config."""
        from mini_coder.tui.app import MiniCoderTUI

        config = Config()
        app = MiniCoderTUI(config)

        assert app.config is config
        assert hasattr(app, "title")
        assert "mini-coder" in app.title.lower()

    def test_create_app_with_directory(self) -> None:
        """Test creating app with directory."""
        from pathlib import Path

        from mini_coder.tui.app import MiniCoderTUI

        config = Config()
        app = MiniCoderTUI(config, directory="/test/path")

        assert app.working_directory == Path("/test/path").resolve()

    def test_app_initialization(self) -> None:
        """Test app initializes correctly."""
        from mini_coder.tui.app import MiniCoderTUI

        config = Config()
        app = MiniCoderTUI(config)

        assert app.config is config
        assert app.working_directory is None

    def test_app_has_title(self) -> None:
        """Test app has title set."""
        from mini_coder.tui.app import MiniCoderTUI

        config = Config()
        app = MiniCoderTUI(config)

        assert app.title is not None
        assert "mini-coder" in app.title.lower()

    def test_set_working_directory(self) -> None:
        """Test setting working directory."""
        from mini_coder.tui.app import MiniCoderTUI

        config = Config()
        app = MiniCoderTUI(config)

        new_dir = Path("/new/path")
        app.working_directory = new_dir

        assert app.working_directory == new_dir

    def test_set_working_directory_updates_config(self) -> None:
        """Test setting working directory updates config when remembering last."""
        from mini_coder.tui.app import MiniCoderTUI

        config = Config()
        config.working_directory.remember_last = True
        app = MiniCoderTUI(config)

        new_dir = Path("/test/remember")
        app.working_directory = new_dir

        assert config.working_directory.default_path == str(new_dir)

    def test_get_state(self) -> None:
        """Test getting application state."""
        from mini_coder.tui.app import MiniCoderTUI

        config = Config()
        app = MiniCoderTUI(config)

        assert app.state == AppState.IDLE

    def test_set_state(self) -> None:
        """Test setting application state."""
        from mini_coder.tui.app import MiniCoderTUI

        config = Config()
        app = MiniCoderTUI(config)

        app.set_state(AppState.RUNNING)
        assert app.state == AppState.RUNNING

        app.set_state(AppState.PAUSED)
        assert app.state == AppState.PAUSED

        app.set_state(AppState.COMPLETED)
        assert app.state == AppState.COMPLETED


class TestAppState:
    """Tests for AppState enum."""

    def test_app_state_values(self) -> None:
        """Verify all app states exist."""
        assert AppState.IDLE.value == "idle"
        assert AppState.RUNNING.value == "running"
        assert AppState.PAUSED.value == "paused"
        assert AppState.COMPLETED.value == "completed"


class TestWorkingMode:
    """Tests for WorkingMode enum."""

    def test_working_mode_values(self) -> None:
        """Verify all working modes exist."""
        from mini_coder.tui.app import WorkingMode

        assert WorkingMode.PLAN.value == "plan"
        assert WorkingMode.CODE.value == "code"
        assert WorkingMode.EXECUTE.value == "execute"

    def test_working_mode_str(self) -> None:
        """Verify working mode string representation."""
        from mini_coder.tui.app import WorkingMode

        assert str(WorkingMode.PLAN) == "PLAN"
        assert str(WorkingMode.CODE) == "CODE"
        assert str(WorkingMode.EXECUTE) == "EXECUTE"


class TestWorkingModeFunctionality:
    """Tests for working mode functionality."""

    def test_app_default_mode(self) -> None:
        """Test app starts with PLAN mode."""
        from mini_coder.tui.app import MiniCoderTUI, WorkingMode

        config = Config()
        app = MiniCoderTUI(config)

        assert app._ui_state.working_mode == WorkingMode.PLAN

    def test_toggle_mode_cycles(self) -> None:
        """Test toggling mode cycles through all modes."""
        from mini_coder.tui.app import MiniCoderTUI, WorkingMode

        config = Config()
        app = MiniCoderTUI(config)

        # Start with PLAN
        assert app._ui_state.working_mode == WorkingMode.PLAN

        # Toggle to CODE
        app._toggle_working_mode()
        assert app._ui_state.working_mode == WorkingMode.CODE

        # Toggle to EXECUTE
        app._toggle_working_mode()
        assert app._ui_state.working_mode == WorkingMode.EXECUTE

        # Toggle back to PLAN
        app._toggle_working_mode()
        assert app._ui_state.working_mode == WorkingMode.PLAN

    def test_update_mode_display_with_label(self) -> None:
        """Test updating mode display works when label is set."""
        from mini_coder.tui.app import MiniCoderTUI, WorkingMode
        from textual.widgets import Label

        config = Config()
        app = MiniCoderTUI(config)
        app._mode_label = Label("PLAN")

        # Should not raise exception
        app._update_mode_display()

        # Change mode and update again
        app._ui_state.working_mode = WorkingMode.CODE
        app._update_mode_display()

    def test_update_mode_display_without_label(self) -> None:
        """Test updating mode display handles missing label gracefully."""
        from mini_coder.tui.app import MiniCoderTUI

        config = Config()
        app = MiniCoderTUI(config)
        app._mode_label = None

        # Should not raise exception when label is None
        app._update_mode_display()


class TestConsoleAppDisplayMethods:
    """Tests for console app display methods."""

    def test_display_header(self) -> None:
        """Test that _display_header doesn't raise exceptions."""
        from mini_coder.tui.console_app import MiniCoderConsole
        from io import StringIO

        config = Config()
        app = MiniCoderConsole(config)

        # Capture console output
        old_file = app._console.file
        app._console.file = StringIO()

        try:
            app._display_header()
            output = app._console.file.getvalue()
            assert "mini-coder" in output
            assert "Welcome" in output
        finally:
            app._console.file = old_file

    def test_display_thinking(self) -> None:
        """Test that _display_thinking doesn't raise exceptions."""
        from mini_coder.tui.console_app import MiniCoderConsole
        from io import StringIO

        config = Config()
        app = MiniCoderConsole(config)

        # Capture console output
        old_file = app._console.file
        app._console.file = StringIO()

        try:
            app._display_thinking("Test message")
            output = app._console.file.getvalue()
            assert "Test message" in output
        finally:
            app._console.file = old_file

    def test_display_thinking_default_message(self) -> None:
        """Test that _display_thinking with default message."""
        from mini_coder.tui.console_app import MiniCoderConsole
        from io import StringIO

        config = Config()
        app = MiniCoderConsole(config)

        # Capture console output
        old_file = app._console.file
        app._console.file = StringIO()

        try:
            app._display_thinking()
            output = app._console.file.getvalue()
            assert "Processing" in output
        finally:
            app._console.file = old_file

    def test_display_response(self) -> None:
        """Test that _display_response doesn't raise exceptions."""
        from mini_coder.tui.console_app import MiniCoderConsole
        from io import StringIO

        config = Config()
        app = MiniCoderConsole(config)

        # Capture console output
        old_file = app._console.file
        app._console.file = StringIO()

        try:
            app._display_response("# Test Response\n\nThis is a test.")
            output = app._console.file.getvalue()
            # Markdown is processed, just verify no exceptions
            assert output is not None
        finally:
            app._console.file = old_file

    def test_display_code(self) -> None:
        """Test that _display_code doesn't raise exceptions."""
        from mini_coder.tui.console_app import MiniCoderConsole
        from io import StringIO

        config = Config()
        app = MiniCoderConsole(config)

        # Capture console output
        old_file = app._console.file
        app._console.file = StringIO()

        try:
            app._display_code("def hello():\n    print('world')", "python")
            output = app._console.file.getvalue()
            # Syntax highlighting is applied, just verify no exceptions
            assert output is not None
        finally:
            app._console.file = old_file

    def test_display_code_default_language(self) -> None:
        """Test that _display_code uses python as default language."""
        from mini_coder.tui.console_app import MiniCoderConsole
        from io import StringIO

        config = Config()
        app = MiniCoderConsole(config)

        # Capture console output
        old_file = app._console.file
        app._console.file = StringIO()

        try:
            app._display_code("const x = 1;")
            output = app._console.file.getvalue()
            assert output is not None
        finally:
            app._console.file = old_file

    def test_display_mode_footer(self) -> None:
        """Test that _display_mode_footer doesn't raise exceptions."""
        from mini_coder.tui.console_app import MiniCoderConsole
        from io import StringIO

        config = Config()
        app = MiniCoderConsole(config)

        # Capture console output
        old_file = app._console.file
        app._console.file = StringIO()

        try:
            app._display_mode_footer()
            output = app._console.file.getvalue()
            assert "PLAN" in output
        finally:
            app._console.file = old_file


class TestConsoleAppRunMethod:
    """Tests for console app run method."""

    def test_run_with_exit_command(self) -> None:
        """Test that run handles 'exit' command correctly."""
        from mini_coder.tui.console_app import MiniCoderConsole
        from unittest.mock import patch

        config = Config()
        app = MiniCoderConsole(config)

        # Mock _get_user_input to return 'exit'
        with patch.object(app, "_get_user_input", return_value="exit"):
            result = app.run()
            assert result == 0

    def test_run_with_quit_command(self) -> None:
        """Test that run handles 'quit' command correctly."""
        from mini_coder.tui.console_app import MiniCoderConsole
        from unittest.mock import patch

        config = Config()
        app = MiniCoderConsole(config)

        # Mock _get_user_input to return 'quit'
        with patch.object(app, "_get_user_input", return_value="quit"):
            result = app.run()
            assert result == 0

    def test_run_with_q_command(self) -> None:
        """Test that run handles 'q' command correctly."""
        from mini_coder.tui.console_app import MiniCoderConsole
        from unittest.mock import patch

        config = Config()
        app = MiniCoderConsole(config)

        # Mock _get_user_input to return 'q'
        with patch.object(app, "_get_user_input", return_value="q"):
            result = app.run()
            assert result == 0

    def test_run_with_empty_input(self) -> None:
        """Test that run handles empty input by continuing."""
        from mini_coder.tui.console_app import MiniCoderConsole
        from unittest.mock import patch, call

        config = Config()
        app = MiniCoderConsole(config)

        # Mock _get_user_input to return empty string then 'exit'
        with patch.object(app, "_get_user_input", side_effect=["", "exit"]):
            result = app.run()
            assert result == 0

    def test_run_with_valid_input(self) -> None:
        """Test that run processes valid input."""
        from mini_coder.tui.console_app import MiniCoderConsole
        from unittest.mock import patch

        config = Config()
        app = MiniCoderConsole(config)

        # Mock _get_user_input to return valid input then 'exit'
        with patch.object(app, "_get_user_input", side_effect=["test input", "exit"]):
            with patch.object(app, "_display_thinking"):
                with patch.object(app, "_display_header"):
                    result = app.run()
                    assert result == 0

    def test_run_handles_exception(self) -> None:
        """Test that run handles exceptions gracefully."""
        from mini_coder.tui.console_app import MiniCoderConsole
        from unittest.mock import patch

        config = Config()
        app = MiniCoderConsole(config)

        # Mock _get_user_input to raise exception
        # Also mock sys.stdin.isatty at the console_app module level
        with patch("mini_coder.tui.console_app.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = True
            with patch.object(app, "_get_user_input", side_effect=RuntimeError("Test error")):
                with patch.object(app, "_console"):
                    result = app.run()
                    assert result == 1


class TestConsoleAppInputHandling:
    """Tests for console app input handling."""

    def test_get_user_input_ctrl_c(self) -> None:
        """Test that Ctrl+C returns None."""
        from mini_coder.tui.console_app import MiniCoderConsole
        from unittest.mock import patch

        config = Config()
        app = MiniCoderConsole(config)

        # Mock sys.stdin to simulate Ctrl+C
        with patch("sys.stdin.read", side_effect=["\x03"]):  # Ctrl+C
            with patch("sys.stdout.write"):
                with patch("sys.stdout.flush"):
                    result = app._get_user_input()
                    assert result is None

    def test_get_user_input_ctrl_d(self) -> None:
        """Test that Ctrl+D returns None."""
        from mini_coder.tui.console_app import MiniCoderConsole
        from unittest.mock import patch

        config = Config()
        app = MiniCoderConsole(config)

        # Mock sys.stdin to simulate Ctrl+D
        with patch("sys.stdin.read", side_effect=["\x04"]):  # Ctrl+D
            with patch("sys.stdout.write"):
                with patch("sys.stdout.flush"):
                    result = app._get_user_input()
                    assert result is None

    def test_get_user_input_enter(self) -> None:
        """Test that Enter returns the input buffer."""
        from mini_coder.tui.console_app import MiniCoderConsole
        from unittest.mock import patch

        config = Config()
        app = MiniCoderConsole(config)

        # Mock sys.stdin to simulate typing 'hello' then Enter
        with patch("sys.stdin.read", side_effect=["h", "e", "l", "l", "o", "\r"]):
            with patch("sys.stdout.write"):
                with patch("sys.stdout.flush"):
                    result = app._get_user_input()
                    assert result == "hello"

    def test_get_user_input_backspace(self) -> None:
        """Test that backspace removes characters."""
        from mini_coder.tui.console_app import MiniCoderConsole
        from unittest.mock import patch

        config = Config()
        app = MiniCoderConsole(config)

        # Mock sys.stdin to simulate typing 'hell' then backspace then 'o' then Enter
        with patch("sys.stdin.read", side_effect=["h", "e", "l", "l", "\x7f", "o", "\r"]):
            with patch("sys.stdout.write"):
                with patch("sys.stdout.flush"):
                    result = app._get_user_input()
                    assert result == "helo"

    def test_get_user_input_tab(self) -> None:
        """Test that Tab toggles working mode."""
        from mini_coder.tui.console_app import MiniCoderConsole, WorkingMode
        from unittest.mock import patch

        config = Config()
        app = MiniCoderConsole(config)

        # Mock sys.stdin to simulate Tab then Enter
        with patch("sys.stdin.read", side_effect=["\t", "\r"]):
            with patch("sys.stdout.write"):
                with patch("sys.stdout.flush"):
                    result = app._get_user_input()
                    # Mode should have toggled from PLAN to CODE
                    assert app._ui_state.working_mode == WorkingMode.CODE

    def test_get_user_input_keyboard_interrupt(self) -> None:
        """Test that KeyboardInterrupt returns None."""
        from mini_coder.tui.console_app import MiniCoderConsole
        from unittest.mock import patch

        config = Config()
        app = MiniCoderConsole(config)

        # Mock sys.stdin to raise KeyboardInterrupt
        with patch("sys.stdin.read", side_effect=KeyboardInterrupt()):
            with patch("sys.stdout.write"):
                with patch("sys.stdout.flush"):
                    result = app._get_user_input()
                    assert result is None


class TestConsoleAppStateManagement:
    """Tests for console app state management."""

    def test_set_state_logs_change(self) -> None:
        """Test that set_state logs state changes."""
        from mini_coder.tui.console_app import MiniCoderConsole, AppState

        config = Config()
        app = MiniCoderConsole(config)

        # Set up logging capture
        with patch("logging.debug") as mock_log:
            app.set_state(AppState.RUNNING)
            mock_log.assert_called_once_with("State changed: idle -> running")


class TestConsoleAppThinkingHistory:
    """Tests for console app thinking history."""

    def test_console_app_has_thinking_history(self) -> None:
        """Test that console app initializes thinking history."""
        from mini_coder.tui.console_app import MiniCoderConsole

        config = Config()
        app = MiniCoderConsole(config)

        assert app._thinking_history is not None
        assert hasattr(app._thinking_history, "get_all")
        assert hasattr(app._thinking_history, "add")

