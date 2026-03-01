"""Configuration models for TUI.

This module provides dataclasses for TUI configuration including
animation settings, thinking display settings, and working directory settings.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml


class AnimationSpeed(Enum):
    """Typewriter animation speed presets."""

    SLOW = "slow"
    NORMAL = "normal"
    FAST = "fast"


class ThinkingDensity(Enum):
    """Thinking display density modes."""

    VERBOSE = "verbose"
    NORMAL = "normal"
    CONCISE = "concise"


@dataclass
class AnimationSettings:
    """Settings for typewriter animation."""

    speed: AnimationSpeed = AnimationSpeed.NORMAL
    custom_delay_ms: int = 10
    pause_on_space: bool = True
    batch_size: int = 3

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "speed": self.speed.value,
            "custom_delay_ms": self.custom_delay_ms,
            "pause_on_space": self.pause_on_space,
            "batch_size": self.batch_size,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnimationSettings":
        """Create from dictionary."""
        return cls(
            speed=AnimationSpeed(data.get("speed", AnimationSpeed.NORMAL.value)),
            custom_delay_ms=data.get("custom_delay_ms", 10),
            pause_on_space=data.get("pause_on_space", True),
            batch_size=data.get("batch_size", 3),
        )


@dataclass
class ThinkingSettings:
    """Settings for AI thinking visualization."""

    display_mode: ThinkingDensity = ThinkingDensity.NORMAL
    history_max_entries: int = 100
    collapse_by_default: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "display_mode": self.display_mode.value,
            "history_max_entries": self.history_max_entries,
            "collapse_by_default": self.collapse_by_default,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ThinkingSettings":
        """Create from dictionary."""
        return cls(
            display_mode=ThinkingDensity(
                data.get("display_mode", ThinkingDensity.NORMAL.value)
            ),
            history_max_entries=data.get("history_max_entries", 100),
            collapse_by_default=data.get("collapse_by_default", False),
        )


@dataclass
class WorkingDirectorySettings:
    """Settings for working directory management."""

    remember_last: bool = True
    default_path: str = "."

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "remember_last": self.remember_last,
            "default_path": self.default_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkingDirectorySettings":
        """Create from dictionary."""
        return cls(
            remember_last=data.get("remember_last", True),
            default_path=data.get("default_path", "."),
        )


@dataclass
class Config:
    """Main TUI configuration."""

    animation: AnimationSettings = field(default_factory=AnimationSettings)
    thinking: ThinkingSettings = field(default_factory=ThinkingSettings)
    working_directory: WorkingDirectorySettings = field(
        default_factory=WorkingDirectorySettings
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "animation": self.animation.to_dict(),
            "thinking": self.thinking.to_dict(),
            "working_directory": self.working_directory.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        """Create from dictionary."""
        return cls(
            animation=AnimationSettings.from_dict(data.get("animation", {})),
            thinking=ThinkingSettings.from_dict(data.get("thinking", {})),
            working_directory=WorkingDirectorySettings.from_dict(
                data.get("working_directory", {})
            ),
        )

    def save_to_file(self, path: Path) -> None:
        """Save configuration to YAML file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False)

    @classmethod
    def load_from_file(cls, path: Path) -> "Config":
        """Load configuration from YAML file."""
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
        return cls.from_dict(data)

    @classmethod
    def load_or_create(cls, path: Path) -> "Config":
        """Load configuration from file, or create default if not exists."""
        if path.exists():
            return cls.load_from_file(path)
        config = cls()
        config.save_to_file(path)
        return config

    @classmethod
    def get_default_config_path(cls) -> Path:
        """Get the default configuration file path."""
        config_dir = Path.home() / ".mini-coder"
        return config_dir / "tui.yaml"
