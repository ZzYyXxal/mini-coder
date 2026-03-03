"""Tool base classes and types"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


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
