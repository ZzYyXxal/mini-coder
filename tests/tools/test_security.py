"""Tests for SecurityLayer"""

import pytest
from src.mini_coder.tools.security import SecurityMode, SecurityLevel


class TestSecurityMode:
    """Tests for SecurityMode enum"""

    def test_security_mode_values(self) -> None:
        """Test all security mode values exist"""
        assert SecurityMode.STRICT.value == "strict"
        assert SecurityMode.NORMAL.value == "normal"
        assert SecurityMode.TRUST.value == "trust"

    def test_security_mode_from_string(self) -> None:
        """Test creating SecurityMode from string"""
        assert SecurityMode("strict") == SecurityMode.STRICT
        assert SecurityMode("normal") == SecurityMode.NORMAL
        assert SecurityMode("trust") == SecurityMode.TRUST


class TestSecurityLevel:
    """Tests for SecurityLevel class"""

    @pytest.fixture
    def security(self) -> SecurityLevel:
        """Create SecurityLevel instance"""
        return SecurityLevel()

    def test_banned_commands_network(self, security: SecurityLevel) -> None:
        """Test banned network commands"""
        assert security.is_banned("curl https://example.com") is True
        assert security.is_banned("wget file.txt") is True
        assert security.is_banned("nc -l 8080") is True
        assert security.is_banned("telnet localhost") is True

    def test_banned_commands_destructive(self, security: SecurityLevel) -> None:
        """Test banned destructive commands"""
        assert security.is_banned("rm -rf /") is True
        assert security.is_banned("rm -r directory") is True
        assert security.is_banned("sudo rm file") is True
        assert security.is_banned("dd if=/dev/zero") is True

    def test_banned_commands_shell_operators(self, security: SecurityLevel) -> None:
        """Test banned shell operators"""
        assert security.is_banned("echo test > file") is False  # Single > allowed
        assert security.is_banned("echo test >> file") is True  # >> not allowed
        assert security.is_banned("cmd1 && cmd2") is True
        assert security.is_banned("cmd1 || cmd2") is True
        assert security.is_banned("cmd1; cmd2") is True
        assert security.is_banned("eval echo test") is True

    def test_banned_commands_path_traversal(self, security: SecurityLevel) -> None:
        """Test banned path traversal"""
        assert security.is_banned("cat /etc/passwd") is True
        assert security.is_banned("ls /bin/") is True
        assert security.is_banned("cat ~/.ssh/id_rsa") is True

    def test_safe_readonly_basic(self, security: SecurityLevel) -> None:
        """Test safe read-only basic commands"""
        assert security.is_safe_readonly("ls") is True
        assert security.is_safe_readonly("pwd") is True
        assert security.is_safe_readonly("echo hello") is True
        assert security.is_safe_readonly("whoami") is True
        assert security.is_safe_readonly("date") is True

    def test_safe_readonly_with_args(self, security: SecurityLevel) -> None:
        """Test safe read-only commands with arguments"""
        assert security.is_safe_readonly("ls -la") is True
        assert security.is_safe_readonly("ls -al src/") is True
        assert security.is_safe_readonly("cat file.txt") is True
        assert security.is_safe_readonly("head -n 10 file.txt") is True
        assert security.is_safe_readonly("tail -f log.txt") is True

    def test_safe_readonly_git(self, security: SecurityLevel) -> None:
        """Test safe read-only git commands"""
        assert security.is_safe_readonly("git status") is True
        assert security.is_safe_readonly("git log --oneline") is True
        assert security.is_safe_readonly("git diff HEAD") is True
        assert security.is_safe_readonly("git branch -a") is True
        assert security.is_safe_readonly("git config --list") is True

    def test_safe_readonly_python(self, security: SecurityLevel) -> None:
        """Test safe read-only Python commands"""
        assert security.is_safe_readonly("python --version") is True
        assert security.is_safe_readonly("python -m pytest --collect-only") is True
        assert security.is_safe_readonly("pip list") is True
        assert security.is_safe_readonly("pip show pytest") is True

    def test_requires_confirmation(self, security: SecurityLevel) -> None:
        """Test commands that require confirmation"""
        assert security.requires_confirmation("mkdir new_dir") is True
        assert security.requires_confirmation("touch file.txt") is True
        assert security.requires_confirmation("cp src dst") is True
        assert security.requires_confirmation("mv old new") is True
        assert security.requires_confirmation("git add .") is True
        assert security.requires_confirmation("git commit -m 'test'") is True

    def test_get_command_category(self, security: SecurityLevel) -> None:
        """Test command category classification"""
        assert security.get_command_category("curl example.com") == "banned"
        assert security.get_command_category("ls -la") == "safe"
        assert security.get_command_category("mkdir test") == "requires_confirmation"

    def test_case_insensitive(self, security: SecurityLevel) -> None:
        """Test case insensitivity"""
        assert security.is_banned("CURL https://example.com") is True
        assert security.is_banned("rm -rf /") is True
        assert security.is_safe_readonly("LS -la") is True
        assert security.is_safe_readonly("GIT status") is True

    def test_empty_command(self, security: SecurityLevel) -> None:
        """Test empty command handling"""
        assert security.is_banned("") is False
        assert security.is_safe_readonly("") is False
        assert security.requires_confirmation("") is True

    def test_command_with_whitespace(self, security: SecurityLevel) -> None:
        """Test commands with extra whitespace"""
        assert security.is_banned("  curl   https://example.com  ") is True
        assert security.is_safe_readonly("  ls   -la  ") is True


class TestSecurityLevelEdgeCases:
    """Tests for edge cases in SecurityLevel"""

    @pytest.fixture
    def security(self) -> SecurityLevel:
        """Create SecurityLevel instance"""
        return SecurityLevel()

    def test_partial_command_match(self, security: SecurityLevel) -> None:
        """Test partial command matching"""
        # curl should be banned even with additional args
        assert security.is_banned("curl -X POST https://api.example.com") is True

        # git status should be safe even with args
        assert security.is_safe_readonly("git status --short") is True

    def test_similar_command_names(self, security: SecurityLevel) -> None:
        """Test similar command names"""
        # curl is banned, but curld (if it existed) should not be
        assert security.is_banned("curl") is True

        # rm is not in banned (only rm -rf), but should require confirmation
        assert security.is_banned("rm file") is False
        assert security.requires_confirmation("rm file") is True

    def test_git_subcommands(self, security: SecurityLevel) -> None:
        """Test git subcommands"""
        # Safe git commands
        assert security.is_safe_readonly("git status") is True
        assert security.is_safe_readonly("git log") is True

        # Git commands that need confirmation
        assert security.requires_confirmation("git add .") is True
        assert security.requires_confirmation("git commit -m 'test'") is True
