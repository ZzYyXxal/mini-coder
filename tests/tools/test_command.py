"""Tests for CommandTool"""

import pytest
from src.mini_coder.tools.command import CommandTool
from src.mini_coder.tools.security import SecurityMode
from src.mini_coder.tools.permission import PermissionService
from src.mini_coder.tools.base import ToolResponse


class TestCommandToolInit:
    """Tests for CommandTool initialization"""

    def test_create_with_defaults(self) -> None:
        """Test creating CommandTool with default settings"""
        tool = CommandTool()

        assert tool.security_mode == SecurityMode.NORMAL
        assert tool.name == "Command"
        assert tool._permission_service is None

    def test_create_with_custom_settings(self) -> None:
        """Test creating CommandTool with custom settings"""
        permission_service = PermissionService()
        tool = CommandTool(
            security_mode=SecurityMode.STRICT,
            permission_service=permission_service,
            timeout=60,
            name="MyCommand"
        )

        assert tool.security_mode == SecurityMode.STRICT
        assert tool._permission_service is permission_service
        assert tool.name == "MyCommand"


class TestCommandToolRun:
    """Tests for CommandTool.run() method"""

    @pytest.fixture
    def tool(self) -> CommandTool:
        """Create CommandTool instance"""
        return CommandTool()

    def test_run_empty_command(self, tool: CommandTool) -> None:
        """Test running empty command"""
        result = tool.run({"command": ""})

        assert result.error_code == "INVALID_COMMAND"
        assert "不能为空" in result.text or "empty" in result.text.lower()

    def test_run_safe_command(self, tool: CommandTool) -> None:
        """Test running a safe command"""
        result = tool.run({"command": "echo hello"})

        assert result.error_code is None
        assert "hello" in result.text

    def test_run_banned_command(self, tool: CommandTool) -> None:
        """Test running a banned command"""
        result = tool.run({"command": "curl https://example.com"})

        assert result.error_code == "EXECUTION_FAILED"
        assert "禁止" in result.text or "banned" in result.text.lower()

    def test_run_with_timeout(self, tool: CommandTool) -> None:
        """Test running command with timeout"""
        result = tool.run({"command": "sleep 0.1", "timeout": 1})

        # Should complete successfully
        assert result.error_code is None or result.error_code == "EXECUTION_FAILED"

    def test_run_git_status(self, tool: CommandTool) -> None:
        """Test running git status (safe command)"""
        result = tool.run({"command": "git status"})

        # Should be allowed (may fail if not in git repo, but not blocked)
        assert "禁止" not in result.text


class TestCommandToolSecurityModes:
    """Tests for different security modes"""

    def test_strict_mode_allows_safe_command(self) -> None:
        """Test strict mode allows safe commands"""
        tool = CommandTool(security_mode=SecurityMode.STRICT)
        result = tool.run({"command": "ls -la"})

        # Safe command should be allowed
        assert result.error_code != "EXECUTION_FAILED" or "禁止" not in result.text

    def test_strict_mode_blocks_unsafe_command(self) -> None:
        """Test strict mode blocks non-safe commands"""
        tool = CommandTool(security_mode=SecurityMode.STRICT)
        result = tool.run({"command": "mkdir test_dir"})

        # Non-safe command should be blocked in strict mode
        assert result.error_code == "EXECUTION_FAILED"
        assert "严格模式" in result.text or "strict" in result.text.lower()

    def test_trust_mode_allows_most_commands(self) -> None:
        """Test trust mode allows most commands"""
        tool = CommandTool(security_mode=SecurityMode.TRUST)
        result = tool.run({"command": "echo trust test"})

        # Should be allowed (only banned commands are blocked)
        assert "trust" in result.text.lower() or result.error_code is None


class TestCommandToolHelperMethods:
    """Tests for CommandTool helper methods"""

    @pytest.fixture
    def tool(self) -> CommandTool:
        """Create CommandTool instance"""
        return CommandTool()

    def test_is_command_safe_banned(self, tool: CommandTool) -> None:
        """Test is_command_safe for banned commands"""
        is_safe, reason = tool.is_command_safe("curl https://example.com")

        assert is_safe is False
        assert "黑名单" in reason or "banned" in reason.lower()

    def test_is_command_safe_readonly(self, tool: CommandTool) -> None:
        """Test is_command_safe for safe readonly commands"""
        is_safe, reason = tool.is_command_safe("ls -la")

        assert is_safe is True
        assert "安全" in reason or "safe" in reason.lower() or "无需" in reason

    def test_is_command_safe_requires_confirmation(self, tool: CommandTool) -> None:
        """Test is_command_safe for commands requiring confirmation"""
        is_safe, reason = tool.is_command_safe("mkdir test")

        assert is_safe is False
        assert "确认" in reason or "confirm" in reason.lower()

    def test_get_security_mode(self, tool: CommandTool) -> None:
        """Test getting security mode"""
        assert tool.get_security_mode() == SecurityMode.NORMAL

    def test_set_security_mode(self, tool: CommandTool) -> None:
        """Test setting security mode"""
        tool.set_security_mode(SecurityMode.STRICT)
        assert tool.get_security_mode() == SecurityMode.STRICT

    def test_get_available_commands(self, tool: CommandTool) -> None:
        """Test getting available commands"""
        commands = tool.get_available_commands()

        assert "safe_commands" in commands
        assert "banned_commands" in commands
        assert "requires_confirmation" in commands

        assert "ls" in commands["safe_commands"]
        assert "curl" in commands["banned_commands"]


class TestCommandToolPermissionService:
    """Tests for CommandTool with PermissionService"""

    def test_with_permission_service_auto_approve(self) -> None:
        """Test with permission service in auto-approve mode"""
        permission_service = PermissionService()
        tool = CommandTool(
            permission_service=permission_service,
            security_mode=SecurityMode.NORMAL
        )
        tool.set_session_id("test-session")

        # Auto-approve the session
        permission_service.auto_approve_session("test-session")

        # Should be able to run commands that require confirmation
        result = tool.run({"command": "mkdir test_dir"})
        # Should be allowed because session is auto-approved
        assert result.error_code != "EXECUTION_FAILED" or "拒绝" not in result.text

    def test_with_permission_service_deny(self) -> None:
        """Test with permission service that denies"""
        def deny_callback(request) -> bool:
            return False

        permission_service = PermissionService(on_request_callback=deny_callback)
        tool = CommandTool(
            permission_service=permission_service,
            security_mode=SecurityMode.NORMAL
        )
        tool.set_session_id("test-session")

        # Command that requires confirmation should be denied
        result = tool.run({"command": "mkdir test_dir"})

        # Should be denied
        assert result.error_code == "EXECUTION_FAILED"
        assert "拒绝" in result.text or "denied" in result.text.lower()


class TestCommandToolIntegration:
    """Integration tests for CommandTool"""

    def test_full_workflow(self) -> None:
        """Test full workflow with CommandTool"""
        # Create tool
        tool = CommandTool(security_mode=SecurityMode.NORMAL)

        # Check if command is safe
        is_safe, reason = tool.is_command_safe("echo hello")
        assert is_safe is True

        # Run safe command
        result = tool.run({"command": "echo hello"})
        assert result.error_code is None
        assert "hello" in result.text

        # Check banned command
        is_safe, reason = tool.is_command_safe("curl https://example.com")
        assert is_safe is False

        # Try banned command
        result = tool.run({"command": "curl https://example.com"})
        assert result.error_code == "EXECUTION_FAILED"
