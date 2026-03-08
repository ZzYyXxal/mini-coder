"""Tests for LangChain tool wrappers.

TDD Phase 3: Red - Write tests first.
"""
import pytest
from pathlib import Path
import tempfile
import os


class TestReadFileTool:
    """Tests for read_file tool."""

    def test_read_file_returns_content(self):
        """read_file should return file content."""
        from mini_coder.tools.langchain_tools import read_file

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Hello, World!")
            f.flush()

            result = read_file.invoke({"path": f.name})

            os.unlink(f.name)
            assert result == "Hello, World!"

    def test_read_file_handles_missing_file(self):
        """read_file should handle missing file gracefully."""
        from mini_coder.tools.langchain_tools import read_file

        result = read_file.invoke({"path": "/nonexistent/file.txt"})

        assert "Error" in result or "not found" in result.lower()


class TestWriteFileTool:
    """Tests for write_file tool."""

    def test_write_file_creates_file(self):
        """write_file should create a new file."""
        from mini_coder.tools.langchain_tools import write_file

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.txt")

            result = write_file.invoke({"path": path, "content": "Test content"})

            assert os.path.exists(path)
            assert Path(path).read_text() == "Test content"

    def test_write_file_overwrites_existing(self):
        """write_file should overwrite existing file."""
        from mini_coder.tools.langchain_tools import write_file

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.txt")
            Path(path).write_text("Old content")

            result = write_file.invoke({"path": path, "content": "New content"})

            assert Path(path).read_text() == "New content"


class TestEditFileTool:
    """Tests for edit_file tool."""

    def test_edit_file_replaces_text(self):
        """edit_file should replace old text with new text."""
        from mini_coder.tools.langchain_tools import edit_file

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.py")
            Path(path).write_text("def hello():\n    print('world')")

            result = edit_file.invoke({
                "path": path,
                "old_text": "print('world')",
                "new_text": "print('hello')"
            })

            assert "print('hello')" in Path(path).read_text()

    def test_edit_file_handles_missing_old_text(self):
        """edit_file should handle missing old_text."""
        from mini_coder.tools.langchain_tools import edit_file

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.py")
            Path(path).write_text("def hello():\n    pass")

            result = edit_file.invoke({
                "path": path,
                "old_text": "nonexistent",
                "new_text": "replacement"
            })

            assert "Error" in result or "not found" in result.lower()


class TestGlobTool:
    """Tests for glob tool."""

    def test_glob_finds_files(self):
        """glob should find matching files."""
        from mini_coder.tools.langchain_tools import glob_files

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            Path(os.path.join(tmpdir, "a.py")).touch()
            Path(os.path.join(tmpdir, "b.py")).touch()
            Path(os.path.join(tmpdir, "c.txt")).touch()

            result = glob_files.invoke({"pattern": os.path.join(tmpdir, "*.py")})

            assert "a.py" in result
            assert "b.py" in result
            assert "c.txt" not in result


class TestGrepTool:
    """Tests for grep tool."""

    def test_grep_finds_matches(self):
        """grep should find matching lines."""
        from mini_coder.tools.langchain_tools import grep_files

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.py")
            Path(path).write_text("def hello():\n    print('hello')\n    return 1")

            result = grep_files.invoke({
                "pattern": "print",
                "path": tmpdir
            })

            assert "print" in result


class TestExecuteCommandTool:
    """Tests for execute_command tool."""

    def test_execute_command_runs_safe_command(self):
        """execute_command should run safe commands."""
        from mini_coder.tools.langchain_tools import execute_command

        result = execute_command.invoke({"command": "echo 'test'"})

        assert "test" in result

    def test_execute_command_has_timeout(self):
        """execute_command should respect timeout."""
        from mini_coder.tools.langchain_tools import execute_command

        # This should complete within timeout
        result = execute_command.invoke({
            "command": "echo 'fast'",
            "timeout": 5
        })

        assert "fast" in result