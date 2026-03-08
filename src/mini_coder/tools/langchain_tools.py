"""LangChain tool wrappers for mini-coder.

This module wraps existing tool functionality into LangChain Tool format
for use with LangGraph workflows.

Tools provided:
- read_file: Read file contents
- write_file: Write content to file
- edit_file: Replace text in file
- glob_files: Find files matching pattern
- grep_files: Search for pattern in files
- execute_command: Run shell commands (with security checks)
"""

import os
import subprocess
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool


@tool
def read_file(path: str) -> str:
    """Read the contents of a file.

    Args:
        path: Path to the file (absolute or relative)

    Returns:
        File contents as string, or error message if file not found
    """
    try:
        file_path = Path(path)
        if not file_path.exists():
            return f"Error: File not found: {path}"
        return file_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file: {e}"


@tool
def write_file(path: str, content: str) -> str:
    """Write content to a file, creating it if necessary.

    Args:
        path: Path to the file
        content: Content to write

    Returns:
        Success message or error
    """
    try:
        file_path = Path(path)
        # Create parent directories if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} characters to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


@tool
def edit_file(path: str, old_text: str, new_text: str) -> str:
    """Edit a file by replacing old_text with new_text.

    Args:
        path: Path to the file
        old_text: Text to find and replace
        new_text: Replacement text

    Returns:
        Success message or error
    """
    try:
        file_path = Path(path)
        if not file_path.exists():
            return f"Error: File not found: {path}"

        content = file_path.read_text(encoding="utf-8")
        if old_text not in content:
            return f"Error: Text not found in file: {old_text[:50]}..."

        new_content = content.replace(old_text, new_text)
        file_path.write_text(new_content, encoding="utf-8")
        return f"Successfully replaced text in {path}"
    except Exception as e:
        return f"Error editing file: {e}"


@tool
def glob_files(pattern: str) -> str:
    """Find files matching a glob pattern.

    Args:
        pattern: Glob pattern (e.g., "**/*.py" or "/absolute/path/*.py")

    Returns:
        Newline-separated list of matching files
    """
    try:
        path_obj = Path(pattern)
        # Handle absolute paths
        if path_obj.is_absolute():
            base_dir = path_obj.parent if path_obj.name else path_obj
            glob_pattern = path_obj.name if path_obj.name else "*"
            matches = list(base_dir.glob(glob_pattern))
        else:
            matches = list(Path(".").glob(pattern))

        if not matches:
            return "No files found matching pattern"
        return "\n".join(str(m) for m in matches)
    except Exception as e:
        return f"Error globbing files: {e}"


@tool
def grep_files(pattern: str, path: str = ".") -> str:
    """Search for pattern in files.

    Args:
        pattern: Regular expression pattern to search
        path: Directory to search in (default: current directory)

    Returns:
        Matching lines with file paths
    """
    try:
        import re

        results = []
        regex = re.compile(pattern)
        search_path = Path(path)

        for file_path in search_path.rglob("*"):
            if file_path.is_file():
                try:
                    content = file_path.read_text(encoding="utf-8")
                    for i, line in enumerate(content.splitlines(), 1):
                        if regex.search(line):
                            results.append(f"{file_path}:{i}: {line.strip()}")
                except (UnicodeDecodeError, PermissionError):
                    continue

        if not results:
            return "No matches found"
        return "\n".join(results[:100])  # Limit output
    except Exception as e:
        return f"Error searching files: {e}"


@tool
def execute_command(command: str, timeout: int = 120) -> str:
    """Execute a shell command with security checks.

    Args:
        command: Command to execute
        timeout: Timeout in seconds (default: 120)

    Returns:
        Command output or error message
    """
    # Security check - block dangerous commands
    dangerous_patterns = [
        "rm -rf /",
        "mkfs",
        "dd if=",
        "> /dev/sd",
        "chmod 777 /",
        "curl | bash",
        "wget | bash",
    ]

    for pattern in dangerous_patterns:
        if pattern in command:
            return f"Error: Dangerous command blocked: {pattern}"

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"

        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"

        return output if output.strip() else "(no output)"
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds"
    except Exception as e:
        return f"Error executing command: {e}"


from typing import Any, List


# Tool collections for different agents
def get_readonly_tools() -> List[Any]:
    """Get read-only tools for Explorer agent."""
    return [read_file, glob_files, grep_files]


def get_coder_tools() -> List[Any]:
    """Get full-access tools for Coder agent."""
    return [read_file, write_file, edit_file, glob_files, grep_files, execute_command]


def get_bash_tools() -> List[Any]:
    """Get tools for Bash agent."""
    return [read_file, glob_files, execute_command]