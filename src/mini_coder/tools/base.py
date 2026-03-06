"""Tool base classes and types

Provides base classes for tools:
- Tool: Original base class (v1.0) - kept for backward compatibility
- BaseTool: Enhanced base class (v2.0) with dynamic prompt loading and event callbacks
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ToolErrorCode(str, Enum):
    """工具错误代码"""
    INVALID_COMMAND = "INVALID_COMMAND"
    EXECUTION_ERROR = "EXECUTION_ERROR"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    NOT_FOUND = "NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass
class ToolParameter:
    """工具参数定义

    Attributes:
        name: 参数名称
        type: 参数类型 (string, integer, number, boolean, array, object)
        description: 参数描述
        required: 是否必需
        default: 默认值
    """
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None


@dataclass
class ToolResponse:
    """工具响应

    Attributes:
        text: 响应文本
        data: 附加数据
        stats: 统计信息
        context: 上下文信息
        error_code: 错误代码（如果有错误）
    """
    text: str
    data: Optional[Dict[str, Any]] = None
    stats: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None

    @classmethod
    def success(
        cls,
        text: str = "",
        data: Optional[Dict[str, Any]] = None,
        stats: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> "ToolResponse":
        """创建成功响应"""
        return cls(
            text=text,
            data=data,
            stats=stats,
            context=context
        )

    @classmethod
    def error(
        cls,
        code: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> "ToolResponse":
        """创建错误响应"""
        return cls(
            text=message,
            data=data,
            error_code=code
        )

    @classmethod
    def partial(
        cls,
        text: str = "",
        data: Optional[Dict[str, Any]] = None,
    ) -> "ToolResponse":
        """创建部分响应（用于流式输出）"""
        return cls(
            text=text,
            data=data
        )


class Tool(ABC):
    """工具基类

    所有工具必须继承此类并实现以下方法：
    - run(): 执行工具
    - get_parameters(): 获取参数定义
    """

    def __init__(self, name: str, description: str):
        """初始化工具

        Args:
            name: 工具名称
            description: 工具描述
        """
        self.name = name
        self.description = description

    @abstractmethod
    def run(self, parameters: Dict[str, Any]) -> ToolResponse:
        """执行工具

        Args:
            parameters: 工具参数字典

        Returns:
            ToolResponse: 工具响应
        """
        pass

    @abstractmethod
    def get_parameters(self) -> list[ToolParameter]:
        """获取工具参数定义

        Returns:
            参数列表
        """
        pass

    def validate_parameters(self, parameters: Dict[str, Any]) -> tuple[bool, str]:
        """验证参数

        Args:
            parameters: 参数列表

        Returns:
            (是否有效，错误消息)
        """
        for param in self.get_parameters():
            if param.required and param.name not in parameters:
                return False, f"缺少必需参数：{param.name}"
        return True, ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式

        Returns:
            工具信息的字典
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default,
                }
                for p in self.get_parameters()
            ]
        }

    def __str__(self) -> str:
        return f"Tool(name={self.name})"

    def __repr__(self) -> str:
        return self.__str__()


# ==================== BaseTool 2.0 ====================
# Enhanced base class with dynamic prompt loading and event callbacks


class BaseTool(ABC):
    """Base class for all tools with dynamic prompt support (v2.0)

    Features:
    - Dynamic prompt loading from files (prompts/tools/*.md)
    - Event callback support for TUI integration
    - Configuration via config dict
    - Backward compatible with original Tool interface

    Usage:
    ```python
    class CommandTool(BaseTool):
        TOOL_TYPE = "command"
        DEFAULT_PROMPT_PATH = "tools/command.md"

        def __init__(self, event_callback=None, config=None):
            super().__init__(
                name="Command",
                description="Safe system command executor",
                prompt_path=self.DEFAULT_PROMPT_PATH,
                event_callback=event_callback,
                config=config,
            )
    ```
    """

    # Class variables
    TOOL_TYPE: str = "base"
    DEFAULT_PROMPT_PATH: Optional[str] = None

    def __init__(
        self,
        name: str,
        description: str,
        prompt_path: Optional[str] = None,
        event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize BaseTool

        Args:
            name: Tool name
            description: Tool description
            prompt_path: Path to prompt template (relative to prompts/)
            event_callback: Callback for tool events (for TUI display)
            config: Tool configuration dict
        """
        self.name = name
        self.description = description
        self.config = config or {}
        self._event_callback = event_callback

        # Initialize prompt loader
        from mini_coder.tools.prompt_loader import PromptLoader
        self._prompt_loader = PromptLoader()
        self._prompt_path = prompt_path

        logger.info(f"Initialized BaseTool: {self.name}")

    @abstractmethod
    def run(self, parameters: Dict[str, Any]) -> "ToolResponse":
        """Execute the tool

        Args:
            parameters: Tool parameters

        Returns:
            ToolResponse: Tool execution result
        """
        pass

    @abstractmethod
    def get_parameters(self) -> List[ToolParameter]:
        """Get tool parameter definitions

        Returns:
            List of parameter definitions
        """
        pass

    def get_system_prompt(self, context: Optional[Dict[str, Any]] = None) -> str:
        """Get tool-specific system prompt

        Args:
            context: Context for prompt interpolation

        Returns:
            System prompt string
        """
        if self._prompt_path:
            return self._prompt_loader.load(self._prompt_path, context)
        return self._get_default_prompt()

    def _get_default_prompt(self) -> str:
        """Get default system prompt (override in subclass)

        Returns:
            Default prompt string
        """
        return f"You are the {self.name} tool. {self.description}"

    def notify_event(self, event_type: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Notify tool event to callback (for TUI display)

        Args:
            event_type: Event type (e.g., "start", "progress", "complete", "error")
            data: Event data
        """
        if self._event_callback:
            try:
                self._event_callback(
                    tool_name=self.name,
                    event_type=event_type,
                    data=data or {},
                )
            except Exception as e:
                logger.exception(f"Event callback error in {self.name}: {e}")

    def validate_parameters(self, parameters: Dict[str, Any]) -> tuple[bool, str]:
        """Validate parameters

        Args:
            parameters: Parameter dictionary

        Returns:
            (is_valid, error_message)
        """
        for param in self.get_parameters():
            if param.required and param.name not in parameters:
                return False, f"Missing required parameter: {param.name}"
        return True, ""

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value
        """
        return self.config.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        """Convert tool to dictionary format

        Returns:
            Tool information dictionary
        """
        return {
            "name": self.name,
            "description": self.description,
            "tool_type": self.TOOL_TYPE,
            "prompt_path": self._prompt_path,
            "config": self.config,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default,
                }
                for p in self.get_parameters()
            ],
        }

    def __str__(self) -> str:
        return f"BaseTool(name={self.name}, type={self.TOOL_TYPE})"

    def __repr__(self) -> str:
        return self.__str__()
