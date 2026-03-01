"""Tests for console-based TUI application."""

from pathlib import Path

from mini_coder.tui.console_app import AppState, MiniCoderConsole, UIState, WorkingMode
from mini_coder.tui.models.config import Config


class TestMiniCoderConsole:
    """Tests for MiniCoderConsole application class."""

    def test_create_console_with_config(self) -> None:
        """Test creating console with config."""
        config = Config()
        app = MiniCoderConsole(config)

        assert app.config is config

    def test_create_console_with_directory(self) -> None:
        """Test creating console with directory."""
        config = Config()
        app = MiniCoderConsole(config, directory="/test/path")

        assert app.working_directory == Path("/test/path").resolve()

    def test_console_initialization(self) -> None:
        """Test console initializes correctly."""
        config = Config()
        app = MiniCoderConsole(config)

        assert app.config is config
        assert app.working_directory is None

    def test_console_has_title(self) -> None:
        """Test console has title set."""
        config = Config()
        app = MiniCoderConsole(config)

        assert app.TITLE == "mini-coder"

    def test_set_working_directory(self) -> None:
        """Test setting working directory."""
        config = Config()
        app = MiniCoderConsole(config)

        new_dir = Path("/new/path")
        app.working_directory = new_dir

        assert app.working_directory == new_dir

    def test_set_working_directory_updates_config(self) -> None:
        """Test setting working directory updates config when remembering last."""
        config = Config()
        config.working_directory.remember_last = True
        app = MiniCoderConsole(config)

        new_dir = Path("/test/remember")
        app.working_directory = new_dir

        assert config.working_directory.default_path == str(new_dir)

    def test_get_state(self) -> None:
        """Test getting application state."""
        config = Config()
        app = MiniCoderConsole(config)

        assert app.state == AppState.IDLE

    def test_set_state(self) -> None:
        """Test setting application state."""
        config = Config()
        app = MiniCoderConsole(config)

        app.set_state(AppState.RUNNING)
        assert app.state == AppState.RUNNING

        app.set_state(AppState.PAUSED)
        assert app.state == AppState.PAUSED

        app.set_state(AppState.COMPLETED)
        assert app.state == AppState.COMPLETED

    def test_default_ui_state(self) -> None:
        """Test default UI state."""
        config = Config()
        app = MiniCoderConsole(config)

        assert app._ui_state.current_screen == "welcome"
        assert app._ui_state.thinking_visible is False
        assert app._ui_state.working_mode == WorkingMode.PLAN

    def test_thinking_history_initialized(self) -> None:
        """Test thinking history is initialized."""
        config = Config()
        app = MiniCoderConsole(config)

        assert app._thinking_history is not None

    def test_console_object_initialization(self) -> None:
        """Test that console object is created."""
        config = Config()
        app = MiniCoderConsole(config)

        assert hasattr(app, "_console")
        assert app._console is not None


class TestConsoleAppState:
    """Tests for AppState enum."""

    def test_app_state_values(self) -> None:
        """Verify all app states exist."""
        assert AppState.IDLE.value == "idle"
        assert AppState.RUNNING.value == "running"
        assert AppState.PAUSED.value == "paused"
        assert AppState.COMPLETED.value == "completed"


class TestConsoleWorkingMode:
    """Tests for WorkingMode enum."""

    def test_working_mode_values(self) -> None:
        """Verify all working modes exist."""
        assert WorkingMode.PLAN.value == "plan"
        assert WorkingMode.CODE.value == "code"
        assert WorkingMode.EXECUTE.value == "execute"

    def test_working_mode_str(self) -> None:
        """Verify working mode string representation."""
        assert str(WorkingMode.PLAN) == "PLAN"
        assert str(WorkingMode.CODE) == "CODE"
        assert str(WorkingMode.EXECUTE) == "EXECUTE"


class TestConsoleWorkingModeFunctionality:
    """Tests for working mode functionality."""

    def test_app_default_mode(self) -> None:
        """Test app starts with PLAN mode."""
        config = Config()
        app = MiniCoderConsole(config)

        assert app._ui_state.working_mode == WorkingMode.PLAN

    def test_toggle_mode_cycles(self) -> None:
        """Test toggling mode cycles through all modes."""
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


class TestConsoleUIState:
    """Tests for UIState dataclass."""

    def test_ui_state_defaults(self) -> None:
        """Test UIState has correct defaults."""
        ui_state = UIState()

        assert ui_state.current_screen == "welcome"
        assert ui_state.thinking_visible is False
        assert ui_state.working_mode == WorkingMode.PLAN

    def test_ui_state_custom_values(self) -> None:
        """Test UIState with custom values."""
        ui_state = UIState(
            current_screen="thinking",
            thinking_visible=True,
            working_mode=WorkingMode.CODE,
        )

        assert ui_state.current_screen == "thinking"
        assert ui_state.thinking_visible is True
        assert ui_state.working_mode == WorkingMode.CODE


class TestRunConsoleApp:
    """Tests for run_console_app function."""

    def test_run_console_app_function_exists(self) -> None:
        """Test run_console_app function exists and can be called."""
        from mini_coder.tui.console_app import run_console_app

        assert callable(run_console_app)

    def test_run_console_app_creates_console(self) -> None:
        """Test run_console_app creates and returns exit code."""
        # We can't actually run it in tests (it's interactive)
        # but we can verify the function signature and basic behavior
        config = Config()
        app = MiniCoderConsole(config)
        assert app is not None
        assert hasattr(app, "run")
        assert callable(app.run)
