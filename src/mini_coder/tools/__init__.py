"""Tools package - 安全的命令执行工具

Provides tool base classes and utilities:
- Tool: Original base class (v1.0) - backward compatible
- BaseTool: Enhanced base class (v2.0) with dynamic prompt loading
- PromptLoader: Dynamic prompt loader with template interpolation
- CommandTool: Safe system command executor
- ToolFilter: Tool access control filters
"""

from .security import SecurityMode, SecurityLevel
from .permission import PermissionRequest, PermissionService
from .executor import CommandResult, SafeExecutor
from .base import (
    Tool,
    ToolParameter,
    ToolResponse,
    ToolErrorCode,
    BaseTool,  # v2.0
)
from .prompt_loader import PromptLoader  # v2.0
from .command import CommandTool
from .filter import (
    ToolFilter,
    ReadOnlyFilter,
    FullAccessFilter,
    CustomFilter,
    StrictFilter,
    BashRestrictedFilter,
    WorkDirFilter,
)

__all__ = [
    # v1.0 - Backward compatible
    "SecurityMode",
    "SecurityLevel",
    "PermissionRequest",
    "PermissionService",
    "CommandResult",
    "SafeExecutor",
    "Tool",
    "ToolParameter",
    "ToolResponse",
    "ToolErrorCode",
    "CommandTool",
    "ToolFilter",
    "ReadOnlyFilter",
    "FullAccessFilter",
    "CustomFilter",
    "StrictFilter",
    # v2.0 - New
    "BaseTool",
    "PromptLoader",
    "BashRestrictedFilter",
    "WorkDirFilter",
]
