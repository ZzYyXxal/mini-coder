"""Entry point for the TUI application.

This module provides the CLI argument parsing and initialization
for the mini-coder TUI application.
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from mini_coder.tui.models.config import (AnimationSpeed, Config,
                                          ThinkingDensity)

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

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="DEBUG",
        help="日志级别，写入 logs/tui_*.log（默认: DEBUG，含 [LLM REQ]/[LLM RSP] 预览）",
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


def setup_logging(level: int = logging.DEBUG) -> None:
    """Configure logging for the application.

    Logs go only to a file under a log directory (no console output),
    so the TUI interface is not cluttered. Log file name includes creation
    timestamp, e.g. logs/tui_20260306_154855.log (under cwd) or
    ~/.mini-coder/logs/tui_20260306_154855.log.

    Args:
        level: Logging level for the file (default: DEBUG).
    """
    # 包含文件名与行号，便于定位日志来源
    fmt = "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    # 文件名带创建时间戳，便于按会话区分
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_basename = f"tui_{ts}.log"
    for log_dir in (Path.cwd() / "logs", Path.home() / ".mini-coder" / "logs"):
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / log_basename
            fh = logging.FileHandler(log_path, mode="a", encoding="utf-8")
            fh.setLevel(level)
            fh.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
            root.addHandler(fh)
            break
        except OSError:
            continue
    if not root.handlers:
        # No file could be opened: add a null handler so nothing goes to console
        root.addHandler(logging.NullHandler())
    # Reduce noise from Rich's markdown parser
    logging.getLogger("markdown_it").setLevel(logging.INFO)


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
    level = getattr(logging, args.log_level.upper(), logging.DEBUG)
    setup_logging(level=level)

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
