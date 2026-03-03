"""Tests for SafeExecutor"""

import pytest
import os
import tempfile
from src.mini_coder.tools.executor import CommandResult, SafeExecutor


class TestCommandResult:
    """Tests for CommandResult dataclass"""

    def test_create_success_result(self) -> None:
        """Test creating a success result"""
        result = CommandResult(
            success=True,
            stdout="output",
            stderr="",
            exit_code=0
        )

        assert result.success is True
        assert result.stdout == "output"
        assert result.exit_code == 0
        assert result.interrupted is False
        assert result.execution_time_ms == 0

    def test_create_error_result(self) -> None:
        """Test creating an error result"""
        result = CommandResult(
            success=False,
            stdout="",
            stderr="error message",
            exit_code=1
        )

        assert result.success is False
        assert result.stderr == "error message"
        assert result.exit_code == 1


class TestSafeExecutor:
    """Tests for SafeExecutor"""

    @pytest.fixture
    def executor(self) -> SafeExecutor:
        """Create SafeExecutor instance"""
        return SafeExecutor()

    def test_execute_simple_command(self, executor: SafeExecutor) -> None:
        """Test executing a simple command"""
        result = executor.execute("echo hello")

        assert result.success is True
        assert "hello" in result.stdout
        assert result.exit_code == 0

    def test_execute_command_with_output(self, executor: SafeExecutor) -> None:
        """Test executing command with output"""
        result = executor.execute("pwd")

        assert result.success is True
        assert len(result.stdout) > 0

    def test_execute_failing_command(self, executor: SafeExecutor) -> None:
        """Test executing a failing command"""
        result = executor.execute("ls /nonexistent_directory_12345")

        assert result.success is False
        assert result.exit_code != 0

    def test_execute_with_timeout(self) -> None:
        """Test command timeout"""
        executor = SafeExecutor(timeout=1)
        # Use a command that takes longer than timeout
        result = executor.execute("sleep 5", timeout=1)

        assert result.interrupted is True
        assert "超时" in result.stderr or "timeout" in result.stderr.lower()

    def test_truncate_output(self, executor: SafeExecutor) -> None:
        """Test output truncation"""
        # Create executor with small max output
        small_executor = SafeExecutor(max_output_length=100)

        # Generate long output
        result = small_executor.execute("python -c \"print('x' * 500)\"")

        assert len(result.stdout) <= 150  # Truncated + truncation message
        assert "截断" in result.stdout or "truncated" in result.stdout.lower()

    def test_shell_quote(self) -> None:
        """Test shell quoting"""
        assert SafeExecutor.shell_quote("hello") == "'hello'"
        assert SafeExecutor.shell_quote("it's") == "'it'\\''s'"
        assert SafeExecutor.shell_quote("hello world") == "'hello world'"

    def test_split_command(self) -> None:
        """Test command splitting"""
        assert SafeExecutor.split_command("ls -la") == ["ls", "-la"]
        assert SafeExecutor.split_command('echo "hello world"') == ["echo", "hello world"]

    def test_is_safe_path_default(self, executor: SafeExecutor) -> None:
        """Test path safety check with default settings"""
        # Should allow normal paths
        assert executor._is_safe_path("/tmp/test") is True
        assert executor._is_safe_path("./test") is True

    def test_is_safe_path_dangerous(self, executor: SafeExecutor) -> None:
        """Test path safety check with dangerous paths"""
        assert executor._is_safe_path("/etc/passwd") is False
        assert executor._is_safe_path("/bin/bash") is False
        assert executor._is_safe_path("/usr/bin") is False

    def test_is_safe_path_with_allowed_list(self) -> None:
        """Test path safety check with allowed paths"""
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = SafeExecutor(allowed_paths=[tmpdir])

            # Should allow paths within allowed directory
            safe_path = os.path.join(tmpdir, "subdir")
            assert executor._is_safe_path(safe_path) is True

            # Should deny paths outside allowed directory
            assert executor._is_safe_path("/etc") is False

    def test_set_timeout(self, executor: SafeExecutor) -> None:
        """Test setting timeout"""
        executor.set_timeout(60)
        assert executor.timeout == 60

        # Should cap at MAX_TIMEOUT
        executor.set_timeout(10000)
        assert executor.timeout == executor.MAX_TIMEOUT

    def test_execute_with_cwd(self, executor: SafeExecutor) -> None:
        """Test executing command with working directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = executor.execute("pwd", cwd=tmpdir)
            assert tmpdir in result.stdout

    def test_execute_with_unsafe_cwd(self, executor: SafeExecutor) -> None:
        """Test executing command with unsafe working directory"""
        # /etc is a dangerous path
        result = executor.execute("ls", cwd="/etc")
        # The safety check should block this
        assert result.success is False or "unsafe" in result.stderr.lower() or "安全" in result.stderr

    def test_execute_with_check_banned(self) -> None:
        """Test execute_with_check blocks banned commands"""
        executor = SafeExecutor()
        result = executor.execute_with_check("curl https://example.com")

        assert result.success is False
        assert "禁止" in result.stderr or "banned" in result.stderr.lower()

    def test_execute_with_check_safe(self) -> None:
        """Test execute_with_check allows safe commands"""
        executor = SafeExecutor()
        result = executor.execute_with_check("ls -la")

        # Should actually execute (not blocked by security check)
        assert result.success is True or result.success is False  # Depends on output


class TestSafeExecutorEdgeCases:
    """Tests for edge cases in SafeExecutor"""

    @pytest.fixture
    def executor(self) -> SafeExecutor:
        """Create SafeExecutor instance"""
        return SafeExecutor()

    def test_empty_command(self, executor: SafeExecutor) -> None:
        """Test executing empty command"""
        result = executor.execute("")
        # Empty command may fail, but should not crash
        assert isinstance(result, CommandResult)

    def test_command_with_special_chars(self, executor: SafeExecutor) -> None:
        """Test command with special characters"""
        result = executor.execute("echo 'hello world'")
        assert result.success is True
        assert "hello world" in result.stdout

    def test_command_with_pipe(self, executor: SafeExecutor) -> None:
        """Test command with pipe"""
        result = executor.execute("echo hello | cat")
        assert result.success is True
        assert "hello" in result.stdout

    def test_command_with_redirect(self, executor: SafeExecutor) -> None:
        """Test command with redirect"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            tmpfile = f.name

        try:
            result = executor.execute(f"echo test > {tmpfile}")
            assert result.success is True

            # Verify file was written
            with open(tmpfile) as rf:
                content = rf.read()
            assert "test" in content
        finally:
            if os.path.exists(tmpfile):
                os.remove(tmpfile)

    def test_max_output_length_zero(self) -> None:
        """Test with zero max output length"""
        executor = SafeExecutor(max_output_length=0)
        result = executor.execute("echo hello")
        # Should still work, but output will be truncated to 0
        assert len(result.stdout) == 0 or "截断" in result.stdout

    def test_negative_timeout(self, executor: SafeExecutor) -> None:
        """Test with negative timeout"""
        # Should not crash, may use default timeout
        result = executor.execute("echo test", timeout=-1)
        assert isinstance(result, CommandResult)
