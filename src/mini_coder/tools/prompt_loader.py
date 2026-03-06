"""PromptLoader - Dynamic prompt loader for tools

Provides dynamic prompt loading with template interpolation:
1. Load prompts from markdown files
2. Placeholder interpolation ({{key}} syntax)
3. Caching for performance
4. Fallback prompts when file is missing
"""

from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class PromptLoader:
    """Dynamic prompt loader with template interpolation

    Usage:
    ```python
    loader = PromptLoader()
    prompt = loader.load("tools/command.md", {"security_mode": "normal"})
    ```
    """

    DEFAULT_PROMPT_DIR = "prompts"

    def __init__(self, base_dir: Optional[str] = None):
        """Initialize prompt loader

        Args:
            base_dir: Base directory for prompts (default: "prompts")
        """
        self.base_dir = Path(base_dir or self.DEFAULT_PROMPT_DIR)
        self._cache: Dict[str, str] = {}

        # Ensure directory exists (for development)
        if not self.base_dir.exists():
            logger.debug(f"Prompt directory does not exist: {self.base_dir}")

    def load(
        self,
        prompt_path: str,
        context: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
    ) -> str:
        """Load and interpolate prompt template

        Args:
            prompt_path: Path relative to base_dir (e.g., "tools/command.md")
            context: Context dictionary for interpolation
            use_cache: Whether to use cached prompt

        Returns:
            Interpolated prompt string
        """
        # Check cache
        if use_cache and prompt_path in self._cache:
            prompt = self._cache[prompt_path]
            logger.debug(f"Loaded cached prompt: {prompt_path}")
        else:
            # Load from file
            prompt = self._load_from_file(prompt_path)
            if prompt is None:
                # File not found, use fallback
                prompt = self._get_fallback_prompt(prompt_path)
                logger.warning(f"Using fallback prompt for: {prompt_path}")
            elif use_cache:
                self._cache[prompt_path] = prompt
                logger.debug(f"Loaded and cached prompt: {prompt_path}")

        # Interpolate context
        if context:
            prompt = self._interpolate(prompt, context)

        return prompt

    def _load_from_file(self, prompt_path: str) -> Optional[str]:
        """Load prompt from file

        Args:
            prompt_path: Path relative to base_dir

        Returns:
            File content, or None if file doesn't exist
        """
        full_path = self.base_dir / prompt_path

        if full_path.exists():
            logger.debug(f"Loading prompt from: {full_path}")
            return full_path.read_text(encoding="utf-8")

        return None

    def _get_fallback_prompt(self, prompt_path: str) -> str:
        """Get fallback prompt when file is missing

        Args:
            prompt_path: Path that was requested

        Returns:
            Fallback prompt string
        """
        # Extract tool name from path
        tool_name = Path(prompt_path).stem  # e.g., "command" from "tools/command.md"

        return f"""# {tool_name.title()} Tool

You are the **{tool_name.title()}** tool.

## Purpose

This tool provides functionality for {tool_name} operations.

## Usage

Follow the tool's parameter requirements to use it effectively.

## Note

This is a fallback prompt. The actual prompt file ({prompt_path}) was not found.
Please ensure the prompt file exists in the prompts directory.
"""

    def _interpolate(self, prompt: str, context: Dict[str, Any]) -> str:
        """Execute placeholder interpolation

        Args:
            prompt: Raw prompt string
            context: Context dictionary with replacement values

        Returns:
            Interpolated prompt string
        """
        for key, value in context.items():
            placeholder = f"{{{{{key}}}}}"  # {{key}}
            prompt = prompt.replace(placeholder, str(value))
        return prompt

    def clear_cache(self) -> None:
        """Clear prompt cache"""
        self._cache.clear()
        logger.debug("Prompt cache cleared")

    def preload(self, prompt_paths: Optional[list[str]] = None) -> None:
        """Preload prompts into cache

        Args:
            prompt_paths: List of prompt paths to preload
        """
        if prompt_paths is None:
            # Preload common tool prompts
            prompt_paths = [
                "tools/command.md",
            ]

        for path in prompt_paths:
            try:
                self.load(path, use_cache=True)
            except Exception as e:
                logger.warning(f"Failed to preload prompt {path}: {e}")

    def get_cached_prompts(self) -> list[str]:
        """Get list of cached prompt paths

        Returns:
            List of cached prompt paths
        """
        return list(self._cache.keys())
