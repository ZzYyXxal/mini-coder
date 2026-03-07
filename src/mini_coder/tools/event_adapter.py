"""Tool Event Adapter - 桥接工具事件与 TUI 回调

将 BaseTool 2.0 的事件回调转换为 TUI 可识别的格式，
实现工具执行过程的可视化展示。
"""

import time
from typing import Callable, Dict, Any, Optional, List
from dataclasses import dataclass, field


@dataclass
class ToolEvent:
    """工具事件数据结构"""
    tool_name: str
    event_type: str
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)


class ToolEventAdapter:
    """工具事件适配器

    将 BaseTool 2.0 的 notify_event 回调转换为 TUI 的 on_tool_called 格式。

    Usage:
    ```python
    # 在 TUI 中创建适配器
    adapter = ToolEventAdapter(tui_console.on_tool_called)

    # 创建 CommandTool 时使用适配器的回调
    tool = CommandTool(event_callback=adapter.create_callback())

    # 或者直接注册多个工具
    adapter.register_tool(command_tool)
    ```
    """

    # 事件类型映射到 TUI 状态
    EVENT_STATUS_MAP = {
        "start": "starting",
        "complete": "completed",
        "error": "failed",
        "security_check": "security_check",
        "permission_request": "permission_request",
    }

    def __init__(
        self,
        tui_callback: Optional[Callable[[str, str, str, float, Optional[str]], None]] = None,
        event_filter: Optional[List[str]] = None,
    ):
        """初始化适配器

        Args:
            tui_callback: TUI 的 on_tool_called 回调函数
                        签名: (tool_name, args, status, duration, result)
            event_filter: 要过滤的事件类型列表（None 表示接收所有事件）
        """
        self._tui_callback = tui_callback
        self._event_filter = event_filter
        self._events: List[ToolEvent] = []
        self._active_tools: Dict[str, float] = {}  # tool_name -> start_time

    def create_callback(self) -> Callable[[str, str, Dict[str, Any]], None]:
        """创建事件回调函数

        Returns:
            可传递给 BaseTool 的 event_callback 参数的回调函数
        """
        def callback(tool_name: str, event_type: str, data: Dict[str, Any]) -> None:
            self.on_tool_event(tool_name, event_type, data)

        return callback

    def on_tool_event(
        self,
        tool_name: str,
        event_type: str,
        data: Dict[str, Any]
    ) -> None:
        """处理工具事件

        Args:
            tool_name: 工具名称
            event_type: 事件类型
            data: 事件数据
        """
        # 过滤事件
        if self._event_filter and event_type not in self._event_filter:
            return

        # 记录事件
        event = ToolEvent(
            tool_name=tool_name,
            event_type=event_type,
            data=data,
        )
        self._events.append(event)

        # 转换为 TUI 回调格式
        if self._tui_callback:
            self._dispatch_to_tui(event)

    def _dispatch_to_tui(self, event: ToolEvent) -> None:
        """将事件分发到 TUI

        Args:
            event: 工具事件
        """
        tool_name = event.tool_name
        event_type = event.event_type
        data = event.data

        if event_type == "start":
            # 记录开始时间
            self._active_tools[tool_name] = event.timestamp

            # 获取命令参数
            args = data.get("command", "")
            self._tui_callback(
                tool_name=tool_name,
                args=args,
                status="starting",
                duration=0.0,
                result=None,
            )

        elif event_type == "complete":
            # 计算执行时间
            start_time = self._active_tools.pop(tool_name, event.timestamp)
            duration = event.timestamp - start_time

            # 获取命令和结果
            args = data.get("command", "")
            exit_code = data.get("exit_code", 0)

            self._tui_callback(
                tool_name=tool_name,
                args=args,
                status="completed",
                duration=duration,
                result=f"exit_code={exit_code}",
            )

        elif event_type == "error":
            # 计算执行时间
            start_time = self._active_tools.pop(tool_name, event.timestamp)
            duration = event.timestamp - start_time

            # 获取错误信息
            args = data.get("command", "")
            error_message = data.get("error_message", "Unknown error")

            self._tui_callback(
                tool_name=tool_name,
                args=args,
                status="failed",
                duration=duration,
                result=error_message,
            )

        elif event_type == "security_check":
            # 安全检查事件
            args = data.get("command", "")
            category = data.get("category", "unknown")

            # 只记录，不调用 TUI（避免干扰）
            # 可以在 debug 模式下显示

        elif event_type == "permission_request":
            # 权限请求事件
            args = data.get("command", "")
            reason = data.get("reason", "")

            self._tui_callback(
                tool_name=tool_name,
                args=args,
                status="permission_request",
                duration=0.0,
                result=reason,
            )

    def register_tool(self, tool: Any) -> None:
        """注册工具到适配器

        自动设置工具的 event_callback。

        Args:
            tool: BaseTool 实例
        """
        if hasattr(tool, '_event_callback'):
            # 设置工具的事件回调
            tool._event_callback = self.create_callback()

    def get_events(self, tool_name: Optional[str] = None) -> List[ToolEvent]:
        """获取事件历史

        Args:
            tool_name: 可选的工具名称过滤

        Returns:
            事件列表
        """
        if tool_name:
            return [e for e in self._events if e.tool_name == tool_name]
        return self._events.copy()

    def clear_events(self) -> None:
        """清除事件历史"""
        self._events.clear()
        self._active_tools.clear()

    def set_tui_callback(
        self,
        callback: Callable[[str, str, str, float, Optional[str]], None]
    ) -> None:
        """设置 TUI 回调

        Args:
            callback: TUI 的 on_tool_called 回调函数
        """
        self._tui_callback = callback


class ToolEventCollector:
    """工具事件收集器

    用于测试和调试，收集所有工具事件而不触发 TUI 回调。
    """

    def __init__(self):
        """初始化收集器"""
        self._events: List[ToolEvent] = []

    def create_callback(self) -> Callable[[str, str, Dict[str, Any]], None]:
        """创建事件回调函数"""
        def callback(tool_name: str, event_type: str, data: Dict[str, Any]) -> None:
            self._events.append(ToolEvent(
                tool_name=tool_name,
                event_type=event_type,
                data=data,
            ))
        return callback

    def get_events(self) -> List[ToolEvent]:
        """获取所有事件"""
        return self._events.copy()

    def get_events_by_type(self, event_type: str) -> List[ToolEvent]:
        """按类型获取事件"""
        return [e for e in self._events if e.event_type == event_type]

    def get_events_by_tool(self, tool_name: str) -> List[ToolEvent]:
        """按工具名获取事件"""
        return [e for e in self._events if e.tool_name == tool_name]

    def clear(self) -> None:
        """清除所有事件"""
        self._events.clear()

    def has_event(self, event_type: str) -> bool:
        """检查是否有特定类型的事件"""
        return any(e.event_type == event_type for e in self._events)

    def count_events(self, event_type: Optional[str] = None) -> int:
        """统计事件数量"""
        if event_type:
            return len(self.get_events_by_type(event_type))
        return len(self._events)