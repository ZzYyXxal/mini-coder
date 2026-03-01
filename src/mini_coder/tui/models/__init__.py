"""Data models for TUI components."""

from mini_coder.tui.models.config import (AnimationSpeed, Config,
                                          ThinkingDensity)

__all__ = [
    "Config",
    "AnimationSpeed",
    "ThinkingDensity",
]

# Import thinking models when available
# try:
#     from mini_coder.tui.models.thinking import ThinkingMessage, ThinkingType
#
#     __all__.extend(["ThinkingMessage", "ThinkingType"])
# except ImportError:
#     pass
