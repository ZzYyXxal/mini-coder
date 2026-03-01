"""Entry point for the TUI application.

This module provides the CLI argument parsing and initialization
for the mini-coder TUI application.
"""

import argparse
import logging
import sys
from pathlib import Path

from mini_coder.tui.models.config import (AnimationSpeed, Config,
                                          ThinkingDensity)

# Debug log file when TUI is running (so you can tail -f in another terminal)
TUI_DEBUG_LOG = Path.cwd() / ".cursor" / "tui-debug.log"


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments for the TUI application.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        prog="mini-coder-tui",
        description="Terminal User Interface for mini-coder AI coding assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--directory",
        "-d",
        type=str,
        default=None,
        help="Working directory for the session (default: prompt or use last used)",
    )

    parser.add_argument(
        "--animation-speed",
        "-a",
        type=str,
        choices=["slow", "normal", "fast"],
        default=None,
        help="Typewriter animation speed (default: normal from config)",
    )

    parser.add_argument(
        "--animation-delay",
        type=int,
        default=None,
        help="Custom animation delay in milliseconds (overrides speed preset)",
    )

    parser.add_argument(
        "--thinking-density",
        type=str,
        choices=["verbose", "normal", "concise"],
        default=None,
        help="AI thinking display density (default: normal from config)",
    )

    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version=f"%(prog)s {get_version()}",
    )

    return parser.parse_args()


def get_version() -> str:
    """Get the application version.

    Returns:
        Version string.
    """
    try:
        from mini_coder.tui import __version__

        return __version__
    except ImportError:
        return "0.1.0"


def setup_logging(level: int = logging.INFO) -> None:
    """Configure logging for the application.

    Logs are also written to .cursor/tui-debug.log so you can inspect
    them while the TUI is running (e.g. tail -f .cursor/tui-debug.log).

    Args:
        level: Logging level (default: INFO).
    """
    fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt=datefmt,
    )
    # Append debug log to file so it's visible while TUI is active
    try:
        TUI_DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(TUI_DEBUG_LOG, mode="a", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
        root = logging.getLogger()
        root.addHandler(fh)
        root.setLevel(logging.DEBUG)
    except OSError:
        pass


def load_config_with_args(args: argparse.Namespace) -> Config:
    """Load configuration, applying CLI overrides.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Configuration with CLI overrides applied.
    """
    config = Config.load_or_create(Config.get_default_config_path())

    # Apply CLI overrides
    if args.animation_speed:
        config.animation.speed = AnimationSpeed(args.animation_speed)

    if args.animation_delay is not None:
        config.animation.custom_delay_ms = args.animation_delay

    if args.thinking_density:
        config.thinking.display_mode = ThinkingDensity(args.thinking_density)

    # Save updated config
    config.save_to_file(Config.get_default_config_path())

    return config


def main() -> int:
    """Main entry point for the TUI application.

    Returns:
        Exit code (0 for success, non-zero for error).
    """
    args = parse_arguments()
    setup_logging()

    try:
        config = load_config_with_args(args)

        # Import and run the application
        from mini_coder.tui.app import MiniCoderTUI

        app = MiniCoderTUI(config, directory=args.directory)
        return app.run()

    except KeyboardInterrupt:
        logging.info("Interrupted by user")
        return 130
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
