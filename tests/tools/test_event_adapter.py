"""Tests for ToolEventAdapter and ToolEventCollector"""

import pytest
import time
from src.mini_coder.tools.event_adapter import (
    ToolEvent,
    ToolEventAdapter,
    ToolEventCollector,
)
from src.mini_coder.tools.command import CommandTool


class TestToolEvent:
    """Tests for ToolEvent dataclass"""

    def test_create_event(self) -> None:
        """Test creating a ToolEvent"""
        event = ToolEvent(
            tool_name="Command",
            event_type="start",
            data={"command": "echo hello"},
        )

        assert event.tool_name == "Command"
        assert event.event_type == "start"
        assert event.data["command"] == "echo hello"
        assert event.timestamp > 0

    def test_event_with_custom_timestamp(self) -> None:
        """Test creating event with custom timestamp"""
        custom_time = 1234567890.0
        event = ToolEvent(
            tool_name="Command",
            event_type="complete",
            data={"exit_code": 0},
            timestamp=custom_time,
        )

        assert event.timestamp == custom_time


class TestToolEventCollector:
    """Tests for ToolEventCollector"""

    def test_collect_events(self) -> None:
        """Test collecting events"""
        collector = ToolEventCollector()
        callback = collector.create_callback()

        # Simulate events
        callback("Command", "start", {"command": "echo hello"})
        callback("Command", "complete", {"exit_code": 0})

        events = collector.get_events()
        assert len(events) == 2
        assert events[0].event_type == "start"
        assert events[1].event_type == "complete"

    def test_get_events_by_type(self) -> None:
        """Test filtering events by type"""
        collector = ToolEventCollector()
        callback = collector.create_callback()

        callback("Command", "start", {"command": "ls"})
        callback("Command", "security_check", {"category": "safe"})
        callback("Command", "complete", {"exit_code": 0})
        callback("Command", "start", {"command": "pwd"})
        callback("Command", "complete", {"exit_code": 0})

        start_events = collector.get_events_by_type("start")
        assert len(start_events) == 2

        complete_events = collector.get_events_by_type("complete")
        assert len(complete_events) == 2

    def test_get_events_by_tool(self) -> None:
        """Test filtering events by tool name"""
        collector = ToolEventCollector()
        callback = collector.create_callback()

        callback("Command", "start", {"command": "ls"})
        callback("FileReader", "start", {"file": "test.txt"})

        command_events = collector.get_events_by_tool("Command")
        assert len(command_events) == 1
        assert command_events[0].tool_name == "Command"

    def test_clear_events(self) -> None:
        """Test clearing events"""
        collector = ToolEventCollector()
        callback = collector.create_callback()

        callback("Command", "start", {"command": "ls"})
        assert collector.count_events() == 1

        collector.clear()
        assert collector.count_events() == 0

    def test_has_event(self) -> None:
        """Test checking for event type"""
        collector = ToolEventCollector()
        callback = collector.create_callback()

        assert not collector.has_event("start")

        callback("Command", "start", {"command": "ls"})
        assert collector.has_event("start")
        assert not collector.has_event("complete")

    def test_count_events(self) -> None:
        """Test counting events"""
        collector = ToolEventCollector()
        callback = collector.create_callback()

        callback("Command", "start", {"command": "ls"})
        callback("Command", "complete", {"exit_code": 0})
        callback("Command", "start", {"command": "pwd"})

        assert collector.count_events() == 3
        assert collector.count_events("start") == 2
        assert collector.count_events("complete") == 1


class TestToolEventAdapter:
    """Tests for ToolEventAdapter"""

    def test_adapter_with_tui_callback(self) -> None:
        """Test adapter with TUI callback"""
        tui_calls = []

        def tui_callback(
            tool_name: str,
            args: str,
            status: str,
            duration: float,
            result: str | None,
        ) -> None:
            tui_calls.append({
                "tool_name": tool_name,
                "args": args,
                "status": status,
                "duration": duration,
                "result": result,
            })

        adapter = ToolEventAdapter(tui_callback=tui_callback)
        callback = adapter.create_callback()

        # Simulate start event
        callback("Command", "start", {"command": "echo hello"})
        assert len(tui_calls) == 1
        assert tui_calls[0]["status"] == "starting"
        assert tui_calls[0]["args"] == "echo hello"

    def test_adapter_complete_event(self) -> None:
        """Test adapter complete event with duration"""
        tui_calls = []

        def tui_callback(
            tool_name: str,
            args: str,
            status: str,
            duration: float,
            result: str | None,
        ) -> None:
            tui_calls.append({
                "status": status,
                "duration": duration,
            })

        adapter = ToolEventAdapter(tui_callback=tui_callback)
        callback = adapter.create_callback()

        # Simulate execution
        callback("Command", "start", {"command": "sleep 0.1"})
        time.sleep(0.05)  # Small delay
        callback("Command", "complete", {"command": "sleep 0.1", "exit_code": 0})

        assert len(tui_calls) == 2
        assert tui_calls[1]["status"] == "completed"
        assert tui_calls[1]["duration"] > 0

    def test_adapter_error_event(self) -> None:
        """Test adapter error event"""
        tui_calls = []

        def tui_callback(
            tool_name: str,
            args: str,
            status: str,
            duration: float,
            result: str | None,
        ) -> None:
            tui_calls.append({
                "status": status,
                "result": result,
            })

        adapter = ToolEventAdapter(tui_callback=tui_callback)
        callback = adapter.create_callback()

        callback("Command", "start", {"command": "bad_command"})
        callback("Command", "error", {
            "command": "bad_command",
            "error_code": "EXECUTION_FAILED",
            "error_message": "Command not found",
        })

        assert len(tui_calls) == 2
        assert tui_calls[1]["status"] == "failed"
        assert "Command not found" in tui_calls[1]["result"]

    def test_adapter_event_filter(self) -> None:
        """Test adapter with event filter"""
        tui_calls = []

        def tui_callback(tool_name, args, status, duration, result):
            tui_calls.append(status)

        # Only accept start and complete events
        adapter = ToolEventAdapter(
            tui_callback=tui_callback,
            event_filter=["start", "complete"],
        )
        callback = adapter.create_callback()

        callback("Command", "start", {"command": "ls"})
        callback("Command", "security_check", {"category": "safe"})  # Filtered
        callback("Command", "complete", {"exit_code": 0})

        # Only start and complete should trigger callback
        assert len(tui_calls) == 2
        assert tui_calls[0] == "starting"
        assert tui_calls[1] == "completed"

    def test_adapter_get_events(self) -> None:
        """Test adapter get_events method"""
        adapter = ToolEventAdapter()
        callback = adapter.create_callback()

        callback("Command", "start", {"command": "ls"})
        callback("Command", "complete", {"exit_code": 0})

        events = adapter.get_events()
        assert len(events) == 2

        command_events = adapter.get_events(tool_name="Command")
        assert len(command_events) == 2

    def test_adapter_clear_events(self) -> None:
        """Test adapter clear_events method"""
        adapter = ToolEventAdapter()
        callback = adapter.create_callback()

        callback("Command", "start", {"command": "ls"})
        assert len(adapter.get_events()) == 1

        adapter.clear_events()
        assert len(adapter.get_events()) == 0


class TestToolEventAdapterIntegration:
    """Integration tests for ToolEventAdapter with CommandTool"""

    def test_adapter_with_command_tool(self) -> None:
        """Test adapter integrated with CommandTool"""
        tui_calls = []

        def tui_callback(tool_name, args, status, duration, result):
            tui_calls.append({
                "tool_name": tool_name,
                "args": args,
                "status": status,
                "duration": duration,
            })

        adapter = ToolEventAdapter(tui_callback=tui_callback)
        tool = CommandTool(event_callback=adapter.create_callback())

        result = tool.run({"command": "echo hello"})

        assert result.error_code is None
        # Should have start and complete calls
        assert len(tui_calls) >= 2
        assert tui_calls[0]["status"] == "starting"
        assert tui_calls[-1]["status"] == "completed"

    def test_adapter_with_banned_command(self) -> None:
        """Test adapter with banned command"""
        tui_calls = []

        def tui_callback(tool_name, args, status, duration, result):
            tui_calls.append({"status": status, "args": args})

        adapter = ToolEventAdapter(tui_callback=tui_callback)
        tool = CommandTool(event_callback=adapter.create_callback())

        result = tool.run({"command": "curl https://example.com"})

        assert result.error_code == "EXECUTION_FAILED"
        # Should have start and failed calls
        statuses = [c["status"] for c in tui_calls]
        assert "starting" in statuses
        assert "failed" in statuses

    def test_register_tool(self) -> None:
        """Test register_tool method"""
        tui_calls = []

        def tui_callback(tool_name, args, status, duration, result):
            tui_calls.append(status)

        adapter = ToolEventAdapter(tui_callback=tui_callback)
        tool = CommandTool()  # No callback initially

        # Register tool to adapter
        adapter.register_tool(tool)

        # Now run command
        result = tool.run({"command": "echo test"})

        # Should have events now
        assert len(tui_calls) >= 2


class TestToolEventCollectorIntegration:
    """Integration tests for ToolEventCollector with CommandTool"""

    def test_collector_with_command_tool(self) -> None:
        """Test collector integrated with CommandTool"""
        collector = ToolEventCollector()
        tool = CommandTool(event_callback=collector.create_callback())

        result = tool.run({"command": "echo hello"})

        assert result.error_code is None
        assert collector.count_events() >= 2
        assert collector.has_event("start")
        assert collector.has_event("complete")

    def test_collector_multiple_commands(self) -> None:
        """Test collector with multiple commands"""
        collector = ToolEventCollector()
        tool = CommandTool(event_callback=collector.create_callback())

        tool.run({"command": "echo one"})
        tool.run({"command": "echo two"})
        tool.run({"command": "echo three"})

        # Should have 3 start and 3 complete events
        assert collector.count_events("start") == 3
        assert collector.count_events("complete") == 3

    def test_collector_security_check_events(self) -> None:
        """Test collector captures security_check events"""
        collector = ToolEventCollector()
        tool = CommandTool(event_callback=collector.create_callback())

        tool.run({"command": "ls -la"})

        security_events = collector.get_events_by_type("security_check")
        assert len(security_events) == 1
        assert security_events[0].data["category"] == "safe"