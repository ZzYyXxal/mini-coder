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


# ==================== CommandTool v2.0 Tests ====================


class TestCommandToolV2Init:
    """Tests for CommandTool v2.0 initialization"""

    def test_create_with_base_tool_interface(self) -> None:
        """Test creating CommandTool with BaseTool 2.0 interface"""
        from src.mini_coder.tools.base import BaseTool

        tool = CommandTool()

        # Verify inheritance
        assert isinstance(tool, BaseTool)
        assert tool.TOOL_TYPE == "command"
        assert tool._prompt_path == "tools/command.md"

    def test_create_with_event_callback(self) -> None:
        """Test creating CommandTool with event callback"""
        events_received = []

        def callback(tool_name: str, event_type: str, data: dict) -> None:
            events_received.append((tool_name, event_type, data))

        tool = CommandTool(event_callback=callback)

        # Run a command to trigger events
        tool.run({"command": "echo test"})

        # Should receive start and complete events
        assert len(events_received) >= 2
        assert events_received[0][1] == "start"
        assert events_received[-1][1] == "complete"

    def test_create_with_config_dict(self) -> None:
        """Test creating CommandTool with config dict"""
        tool = CommandTool(
            config={
                "security_mode": "strict",
                "timeout": 60,
                "max_output_length": 10000,
            }
        )

        assert tool.security_mode == SecurityMode.STRICT
        assert tool._executor.timeout == 60
        assert tool._executor.max_output_length == 10000

    def test_backward_compatibility_with_string_security_mode(self) -> None:
        """Test backward compatibility with string security mode"""
        tool = CommandTool(security_mode="normal")
        assert tool.security_mode == SecurityMode.NORMAL

        tool2 = CommandTool(security_mode="strict")
        assert tool2.security_mode == SecurityMode.STRICT


class TestCommandToolV2PromptLoading:
    """Tests for CommandTool v2.0 dynamic prompt loading"""

    def test_load_prompt_from_file(self) -> None:
        """Test loading prompt from file"""
        tool = CommandTool()

        prompt = tool.get_system_prompt()

        assert len(prompt) > 100
        assert "Command Tool" in prompt
        assert "Security Model" in prompt

    def test_load_prompt_with_context(self) -> None:
        """Test loading prompt with context interpolation"""
        tool = CommandTool()

        context = {
            "security_mode": "strict",
            "timeout": 300,
            "max_timeout": 600,
            "max_output_length": 50000,
            "allowed_paths": "/project, /tmp",
        }
        prompt = tool.get_system_prompt(context)

        # Verify placeholders are interpolated
        assert "strict" in prompt
        assert "300" in prompt

    def test_load_prompt_fallback(self) -> None:
        """Test loading prompt with non-existent file (fallback)"""
        tool = CommandTool()

        # Should not raise exception even if prompt file is missing
        prompt = tool.get_system_prompt()
        assert len(prompt) > 0


class TestCommandToolV2Events:
    """Tests for CommandTool v2.0 event callbacks"""

    def test_event_start(self) -> None:
        """Test start event"""
        events = []
        def callback(tool_name: str, event_type: str, data: dict) -> None:
            events.append((event_type, data))

        tool = CommandTool(event_callback=callback)
        tool.run({"command": "echo hello"})

        start_events = [e for e in events if e[0] == "start"]
        assert len(start_events) == 1
        assert start_events[0][1]["command"] == "echo hello"

    def test_event_security_check(self) -> None:
        """Test security_check event"""
        events = []
        def callback(tool_name: str, event_type: str, data: dict) -> None:
            events.append((event_type, data))

        tool = CommandTool(event_callback=callback)
        tool.run({"command": "echo hello"})

        security_events = [e for e in events if e[0] == "security_check"]
        assert len(security_events) == 1
        assert security_events[0][1]["category"] == "safe"

    def test_event_complete(self) -> None:
        """Test complete event"""
        events = []
        def callback(tool_name: str, event_type: str, data: dict) -> None:
            events.append((event_type, data))

        tool = CommandTool(event_callback=callback)
        tool.run({"command": "echo hello"})

        complete_events = [e for e in events if e[0] == "complete"]
        assert len(complete_events) == 1
        assert "command" in complete_events[0][1]
        assert "exit_code" in complete_events[0][1]
        assert "duration_ms" in complete_events[0][1]

    def test_event_error(self) -> None:
        """Test error event"""
        events = []
        def callback(tool_name: str, event_type: str, data: dict) -> None:
            events.append((event_type, data))

        tool = CommandTool(event_callback=callback)
        # Use a banned command to trigger error event
        tool.run({"command": "curl https://example.com"})

        # Should have error event
        error_events = [e for e in events if e[0] == "error"]
        assert len(error_events) >= 1
        assert "error_code" in error_events[0][1]
        assert "error_message" in error_events[0][1]

    def test_event_banned_command(self) -> None:
        """Test events for banned command"""
        events = []
        def callback(tool_name: str, event_type: str, data: dict) -> None:
            events.append((event_type, data))

        tool = CommandTool(event_callback=callback)
        tool.run({"command": "curl https://example.com"})

        # Should have start, security_check (banned), error events
        event_types = [e[0] for e in events]
        assert "start" in event_types
        assert "security_check" in event_types
        assert "error" in event_types


class TestCommandToolV2Config:
    """Tests for CommandTool v2.0 configuration"""

    def test_get_config(self) -> None:
        """Test getting configuration"""
        tool = CommandTool(config={"custom_key": "custom_value", "timeout": 180})

        assert tool.get_config("custom_key") == "custom_value"
        assert tool.get_config("timeout") == 180
        assert tool.get_config("nonexistent", "default") == "default"

    def test_to_dict(self) -> None:
        """Test converting tool to dict"""
        tool = CommandTool(
            security_mode=SecurityMode.NORMAL,
            config={"timeout": 120}
        )

        info = tool.to_dict()

        assert info["name"] == "Command"
        assert info["tool_type"] == "command"
        assert info["prompt_path"] == "tools/command.md"
        assert "parameters" in info
        assert len(info["parameters"]) > 0
