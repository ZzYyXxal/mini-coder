"""Unit tests for TUI configuration module."""

from pathlib import Path

import pytest

from mini_coder.tui.models.config import (AnimationSettings, AnimationSpeed,
                                          Config, ThinkingDensity,
                                          ThinkingSettings,
                                          WorkingDirectorySettings)


class TestAnimationSpeed:
    """Tests for AnimationSpeed enum."""

    def test_animation_speed_values(self) -> None:
        """Verify all animation speed presets exist."""
        assert AnimationSpeed.SLOW.value == "slow"
        assert AnimationSpeed.NORMAL.value == "normal"
        assert AnimationSpeed.FAST.value == "fast"


class TestThinkingDensity:
    """Tests for ThinkingDensity enum."""

    def test_thinking_density_values(self) -> None:
        """Verify all thinking density presets exist."""
        assert ThinkingDensity.VERBOSE.value == "verbose"
        assert ThinkingDensity.NORMAL.value == "normal"
        assert ThinkingDensity.CONCISE.value == "concise"


class TestAnimationSettings:
    """Tests for AnimationSettings dataclass."""

    def test_default_animation_settings(self) -> None:
        """Verify default animation settings."""
        settings = AnimationSettings()
        assert settings.speed == AnimationSpeed.NORMAL
        assert settings.custom_delay_ms == 10
        assert settings.pause_on_space is True
        assert settings.batch_size == 3

    def test_animation_settings_custom_values(self) -> None:
        """Verify custom animation settings."""
        settings = AnimationSettings(
            speed=AnimationSpeed.FAST,
            custom_delay_ms=5,
            pause_on_space=False,
            batch_size=5,
        )
        assert settings.speed == AnimationSpeed.FAST
        assert settings.custom_delay_ms == 5
        assert settings.pause_on_space is False
        assert settings.batch_size == 5


class TestThinkingSettings:
    """Tests for ThinkingSettings dataclass."""

    def test_default_thinking_settings(self) -> None:
        """Verify default thinking settings."""
        settings = ThinkingSettings()
        assert settings.display_mode == ThinkingDensity.NORMAL
        assert settings.history_max_entries == 100
        assert settings.collapse_by_default is False

    def test_thinking_settings_custom_values(self) -> None:
        """Verify custom thinking settings."""
        settings = ThinkingSettings(
            display_mode=ThinkingDensity.VERBOSE,
            history_max_entries=200,
            collapse_by_default=True,
        )
        assert settings.display_mode == ThinkingDensity.VERBOSE
        assert settings.history_max_entries == 200
        assert settings.collapse_by_default is True


class TestWorkingDirectorySettings:
    """Tests for WorkingDirectorySettings dataclass."""

    def test_default_working_directory_settings(self) -> None:
        """Verify default working directory settings."""
        settings = WorkingDirectorySettings()
        assert settings.remember_last is True
        assert settings.default_path == "."

    def test_working_directory_settings_custom_values(self) -> None:
        """Verify custom working directory settings."""
        settings = WorkingDirectorySettings(
            remember_last=False,
            default_path="/home/user/projects",
        )
        assert settings.remember_last is False
        assert settings.default_path == "/home/user/projects"


class TestConfig:
    """Tests for Config dataclass."""

    def test_default_config(self) -> None:
        """Verify default configuration."""
        config = Config()
        assert isinstance(config.animation, AnimationSettings)
        assert isinstance(config.thinking, ThinkingSettings)
        assert isinstance(config.working_directory, WorkingDirectorySettings)

    def test_config_custom_values(self) -> None:
        """Verify custom configuration."""
        config = Config(
            animation=AnimationSettings(speed=AnimationSpeed.FAST),
            thinking=ThinkingSettings(display_mode=ThinkingDensity.VERBOSE),
            working_directory=WorkingDirectorySettings(remember_last=False),
        )
        assert config.animation.speed == AnimationSpeed.FAST
        assert config.thinking.display_mode == ThinkingDensity.VERBOSE
        assert config.working_directory.remember_last is False

    def test_config_to_dict(self) -> None:
        """Verify configuration serialization to dictionary."""
        config = Config()
        config_dict = config.to_dict()
        assert isinstance(config_dict, dict)
        assert "animation" in config_dict
        assert "thinking" in config_dict
        assert "working_directory" in config_dict

    def test_config_from_dict(self) -> None:
        """Verify configuration deserialization from dictionary."""
        data = {
            "animation": {"speed": "fast", "custom_delay_ms": 5},
            "thinking": {"display_mode": "verbose", "history_max_entries": 200},
            "working_directory": {"remember_last": False, "default_path": "."},
        }
        config = Config.from_dict(data)
        assert config.animation.speed == AnimationSpeed.FAST
        assert config.animation.custom_delay_ms == 5
        assert config.thinking.display_mode == ThinkingDensity.VERBOSE
        assert config.thinking.history_max_entries == 200
        assert config.working_directory.remember_last is False


@pytest.fixture
def temp_config_file(tmp_path: Path) -> Path:
    """Create a temporary config file for testing."""
    config_file = tmp_path / "tui.yaml"
    return config_file


class TestConfigPersistence:
    """Tests for configuration persistence."""

    def test_save_to_file(self, temp_config_file: Path) -> None:
        """Verify configuration can be saved to file."""
        config = Config()
        config.save_to_file(temp_config_file)
        assert temp_config_file.exists()

    def test_load_from_file(self, temp_config_file: Path) -> None:
        """Verify configuration can be loaded from file."""
        original_config = Config(
            animation=AnimationSettings(speed=AnimationSpeed.FAST),
            thinking=ThinkingSettings(display_mode=ThinkingDensity.VERBOSE),
        )
        original_config.save_to_file(temp_config_file)

        loaded_config = Config.load_from_file(temp_config_file)
        assert loaded_config.animation.speed == AnimationSpeed.FAST
        assert loaded_config.thinking.display_mode == ThinkingDensity.VERBOSE

    def test_load_creates_default_file(self, tmp_path: Path) -> None:
        """Verify loading creates default config if file doesn't exist."""
        config_file = tmp_path / "new_tui.yaml"
        config = Config.load_or_create(config_file)
        assert config_file.exists()
        assert isinstance(config, Config)

    def test_load_with_custom_values(self, temp_config_file: Path) -> None:
        """Verify loading preserves custom values."""
        custom_config = Config(
            animation=AnimationSettings(
                speed=AnimationSpeed.SLOW,
                custom_delay_ms=20,
                pause_on_space=False,
            ),
            thinking=ThinkingSettings(
                display_mode=ThinkingDensity.CONCISE,
                history_max_entries=50,
            ),
        )
        custom_config.save_to_file(temp_config_file)

        loaded_config = Config.load_from_file(temp_config_file)
        assert loaded_config.animation.speed == AnimationSpeed.SLOW
        assert loaded_config.animation.custom_delay_ms == 20
        assert loaded_config.animation.pause_on_space is False
        assert loaded_config.thinking.display_mode == ThinkingDensity.CONCISE
        assert loaded_config.thinking.history_max_entries == 50
