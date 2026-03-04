"""Coding Agent 入口点

Usage:
    python -m mini_coder.agents "实现一个计算器功能"
    python -m mini_coder.agents --interactive
"""

from .cli import main

if __name__ == "__main__":
    main()
