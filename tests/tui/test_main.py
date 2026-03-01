"""Tests for TUI entry point and CLI argument parsing."""

import logging
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


class TestCLIArgumentParsing:
    """Tests for CLI argument parsing."""

    def test_parse_directory_argument(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test parsing --directory argument."""
        monkeypatch.setattr(
            sys, "argv", ["mini-coder-tui", "--directory", "/test/path"]
        )

        from mini_coder.tui.__main__ import parse_arguments

        args = parse_arguments()
        assert args.directory == "/test/path"

    def test_parse_animation_speed_argument(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test parsing --animation-speed argument."""
        monkeypatch.setattr(
            sys, "argv", ["mini-coder-tui", "--animation-speed", "fast"]
        )

        from mini_coder.tui.__main__ import parse_arguments

        args = parse_arguments()
        assert args.animation_speed == "fast"

    def test_parse_animation_delay_argument(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test parsing --animation-delay argument."""
        monkeypatch.setattr(sys, "argv", ["mini-coder-tui", "--animation-delay", "20"])

        from mini_coder.tui.__main__ import parse_arguments

        args = parse_arguments()
        assert args.animation_delay == 20

    def test_parse_version_argument(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test parsing --version argument."""
        monkeypatch.setattr(sys, "argv", ["mini-coder-tui", "--version"])

        from mini_coder.tui.__main__ import parse_arguments

        with pytest.raises(SystemExit):
            parse_arguments()

    def test_parse_help_argument(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test parsing --help argument."""
        monkeypatch.setattr(sys, "argv", ["mini-coder-tui", "--help"])

        from mini_coder.tui.__main__ import parse_arguments

        with pytest.raises(SystemExit):
            parse_arguments()

    def test_parse_no_arguments(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test parsing with no arguments."""
        monkeypatch.setattr(sys, "argv", ["mini-coder-tui"])

        from mini_coder.tui.__main__ import parse_arguments

        args = parse_arguments()
        assert args.directory is None
        assert args.animation_speed is None
        assert args.animation_delay is None

    def test_parse_all_arguments(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test parsing with all arguments."""
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "mini-coder-tui",
                "--directory",
                "/test",
                "--animation-speed",
                "slow",
                "--animation-delay",
                "15",
            ],
        )

        from mini_coder.tui.__main__ import parse_arguments

        args = parse_arguments()
        assert args.directory == "/test"
        assert args.animation_speed == "slow"
        assert args.animation_delay == 15


class TestGetVersion:
    """Tests for get_version function."""

    def test_get_version(self) -> None:
        """Test getting version string."""
        from mini_coder.tui.__main__ import get_version

        version = get_version()
        assert isinstance(version, str)
        assert len(version) > 0

    def test_get_version_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test get_version fallback when import fails."""
        from mini_coder.tui.__main__ import get_version

        # Make the import fail
        def mock_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "mini_coder.tui":
                raise ImportError("Mock import error")
            return __import__(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", mock_import)

        version = get_version()
        assert version == "0.1.0"


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_logging_defaults(self) -> None:
        """Test setting up logging with default level."""
        from mini_coder.tui.__main__ import setup_logging

        # Reset root logger to avoid test interference
        logging.getLogger().handlers.clear()

        setup_logging()
        # setup_logging always sets root to DEBUG level for file logging
        assert logging.getLogger().level == logging.DEBUG

    def test_setup_logging_debug(self) -> None:
        """Test setting up logging with debug level."""
        from mini_coder.tui.__main__ import setup_logging

        # Reset root logger to avoid test interference
        logging.getLogger().handlers.clear()

        setup_logging(logging.DEBUG)
        assert logging.getLogger().level == logging.DEBUG

    def test_setup_logging_oserror(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test setup_logging handles OSError gracefully."""
        from mini_coder.tui.__main__ import setup_logging

        # Reset root logger to avoid test interference
        logging.getLogger().handlers.clear()

        # Mock mkdir to raise OSError
        original_mkdir = Path.mkdir

        def mock_mkdir(self: Path, *args: object, **kwargs: object) -> None:
            if "cursor" in str(self):
                raise OSError("Mock OSError")
            return original_mkdir(self, *args, **kwargs)

        monkeypatch.setattr(Path, "mkdir", mock_mkdir)

        # Should not raise an exception
        setup_logging()
        # Logger should still be set up even if file handler fails
        assert logging.getLogger().handlers  # At least stream handler


class TestLoadConfigWithArgs:
    """Tests for load_config_with_args function."""

    def test_load_default_config(self, tmp_path: Path) -> None:
        """Test loading default config without CLI overrides."""
        from mini_coder.tui.__main__ import load_config_with_args

        # Create mock args
        class MockArgs:
            directory = None
            animation_speed = None
            animation_delay = None
            thinking_density = None

        args = MockArgs()

        # Override default config path
        from mini_coder.tui.models.config import Config

        original_get_path = Config.get_default_config_path
        Config.get_default_config_path = staticmethod(
            lambda: tmp_path / "test_tui.yaml"
        )

        try:
            config = load_config_with_args(args)
            assert isinstance(config, Config)
        finally:
            Config.get_default_config_path = original_get_path

    def test_load_config_with_animation_speed(self, tmp_path: Path) -> None:
        """Test loading config with animation speed override."""
        from mini_coder.tui.__main__ import load_config_with_args
        from mini_coder.tui.models.config import AnimationSpeed, Config

        class MockArgs:
            directory = None
            animation_speed = "fast"
            animation_delay = None
            thinking_density = None

        args = MockArgs()

        # Override default config path
        original_get_path = Config.get_default_config_path
        Config.get_default_config_path = staticmethod(
            lambda: tmp_path / "test_tui.yaml"
        )

        try:
            config = load_config_with_args(args)
            assert config.animation.speed == AnimationSpeed.FAST
        finally:
            Config.get_default_config_path = original_get_path

    def test_load_config_with_animation_delay(self, tmp_path: Path) -> None:
        """Test loading config with custom animation delay."""
        from mini_coder.tui.__main__ import load_config_with_args
        from mini_coder.tui.models.config import Config

        class MockArgs:
            directory = None
            animation_speed = None
            animation_delay = 25
            thinking_density = None

        args = MockArgs()

        # Override default config path
        original_get_path = Config.get_default_config_path
        Config.get_default_config_path = staticmethod(
            lambda: tmp_path / "test_tui.yaml"
        )

        try:
            config = load_config_with_args(args)
            assert config.animation.custom_delay_ms == 25
        finally:
            Config.get_default_config_path = original_get_path

    def test_load_config_with_thinking_density(self, tmp_path: Path) -> None:
        """Test loading config with thinking density override."""
        from mini_coder.tui.__main__ import load_config_with_args
        from mini_coder.tui.models.config import Config, ThinkingDensity

        class MockArgs:
            directory = None
            animation_speed = None
            animation_delay = None
            thinking_density = "verbose"

        args = MockArgs()

        # Override default config path
        original_get_path = Config.get_default_config_path
        Config.get_default_config_path = staticmethod(
            lambda: tmp_path / "test_tui.yaml"
        )

        try:
            config = load_config_with_args(args)
            assert config.thinking.display_mode == ThinkingDensity.VERBOSE
        finally:
            Config.get_default_config_path = original_get_path


class TestConfigPath:
    """Tests for default config path."""

    def test_get_default_config_path(self) -> None:
        """Test getting default config file path."""
        from mini_coder.tui.models.config import Config

        path = Config.get_default_config_path()
        assert isinstance(path, Path)
        assert path.name == "tui.yaml"
        assert ".mini-coder" in str(path)


class TestMainFunction:
    """Tests for main function."""

    def test_main_success(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test main function returns success."""
        from mini_coder.tui.__main__ import main
        from mini_coder.tui.models.config import Config

        # Mock sys.argv to avoid parsing real args
        monkeypatch.setattr(sys, "argv", ["mini-coder-tui"])

        # Mock config path
        original_get_path = Config.get_default_config_path
        Config.get_default_config_path = staticmethod(lambda: tmp_path / "test_tui.yaml")

        try:
            # Mock the TUI app - need to mock where it's imported
            with patch("mini_coder.tui.app.MiniCoderTUI") as mock_tui:
                mock_tui.return_value.run.return_value = 0
                result = main()
                assert result == 0
        finally:
            Config.get_default_config_path = original_get_path

    def test_main_keyboard_interrupt(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test main function handles KeyboardInterrupt."""
        from mini_coder.tui.__main__ import main
        from mini_coder.tui.models.config import Config

        # Mock sys.argv to avoid parsing real args
        monkeypatch.setattr(sys, "argv", ["mini-coder-tui"])

        # Mock config path
        original_get_path = Config.get_default_config_path
        Config.get_default_config_path = staticmethod(lambda: tmp_path / "test_tui.yaml")

        try:
            # Mock the TUI app to raise KeyboardInterrupt
            with patch("mini_coder.tui.app.MiniCoderTUI") as mock_tui:
                mock_tui.return_value.run.side_effect = KeyboardInterrupt()
                result = main()
                assert result == 130
        finally:
            Config.get_default_config_path = original_get_path

    def test_main_exception(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test main function handles exceptions."""
        from mini_coder.tui.__main__ import main
        from mini_coder.tui.models.config import Config

        # Mock sys.argv to avoid parsing real args
        monkeypatch.setattr(sys, "argv", ["mini-coder-tui"])

        # Mock config path
        original_get_path = Config.get_default_config_path
        Config.get_default_config_path = staticmethod(lambda: tmp_path / "test_tui.yaml")

        try:
            # Mock the TUI app to raise exception
            with patch("mini_coder.tui.app.MiniCoderTUI") as mock_tui:
                mock_tui.return_value.run.side_effect = RuntimeError("Test error")
                result = main()
                assert result == 1
        finally:
            Config.get_default_config_path = original_get_path

    def test_main_with_directory(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test main function passes directory to app."""
        from mini_coder.tui.__main__ import main
        from mini_coder.tui.models.config import Config

        # Mock sys.argv with directory
        monkeypatch.setattr(sys, "argv", ["mini-coder-tui", "--directory", "/test/dir"])

        # Mock config path
        original_get_path = Config.get_default_config_path
        Config.get_default_config_path = staticmethod(lambda: tmp_path / "test_tui.yaml")

        try:
            # Mock the TUI app
            with patch("mini_coder.tui.app.MiniCoderTUI") as mock_tui:
                mock_tui.return_value.run.return_value = 0
                main()
                # Check that directory was passed
                _, kwargs = mock_tui.call_args
                assert kwargs.get("directory") == "/test/dir"
        finally:
            Config.get_default_config_path = original_get_path
