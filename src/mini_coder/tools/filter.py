"""ToolFilter - 工具过滤器机制

用于控制子代理可以访问的工具集合。
灵感来自 HelloAgents 的 ToolFilter 机制。
"""

from abc import ABC, abstractmethod
from typing import Set, List, Optional


class ToolFilter(ABC):
    """工具过滤器基类

    用于在子代理运行时限制可用工具集合。

    使用场景:
    - explore 代理：只允许只读工具
    - plan 代理：只允许只读工具
    - code 代理：允许大部分工具，排除危险工具
    - 用户自定义：完全控制工具访问
    """

    @abstractmethod
    def is_allowed(self, tool_name: str) -> bool:
        """检查工具是否允许使用

        Args:
            tool_name: 工具名称

        Returns:
            bool: 是否允许
        """
        pass

    def filter(self, all_tools: List[str]) -> List[str]:
        """过滤工具列表

        Args:
            all_tools: 所有可用工具名称列表

        Returns:
            过滤后的工具名称列表
        """
        return [tool for tool in all_tools if self.is_allowed(tool)]


class ReadOnlyFilter(ToolFilter):
    """只读工具过滤器

    只允许使用只读工具，适用于：
    - explore（探索代码库）
    - plan（规划任务）
    - summary（归纳信息）
    """

    # 只读工具白名单
    READONLY_TOOLS: Set[str] = {
        # 文件读取
        "Read", "ReadTool",
        # 目录浏览
        "LS", "LSTool", "Glob", "GlobTool",
        # 搜索
        "Grep", "GrepTool",
        # 技能
        "Skill", "SkillTool",
        # 笔记读取
        "NoteRead", "NoteSearch", "NoteList",
        # Command 只读命令（通过 CommandTool 执行）
        "Command_ls", "Command_pwd", "Command_cat",
        "Command_git_status", "Command_git_log", "Command_git_diff",
        "Command_git_branch", "Command_git_show",
        "Command_head", "Command_tail", "Command_wc",
    }

    def __init__(self, additional_allowed: Optional[List[str]] = None):
        """初始化只读过滤器

        Args:
            additional_allowed: 额外允许的工具名称列表
        """
        self.allowed_tools = self.READONLY_TOOLS.copy()
        if additional_allowed:
            self.allowed_tools.update(additional_allowed)

    def is_allowed(self, tool_name: str) -> bool:
        """检查是否为只读工具"""
        return tool_name in self.allowed_tools

    def add_allowed_tool(self, tool_name: str) -> None:
        """添加工具到白名单

        Args:
            tool_name: 工具名称
        """
        self.allowed_tools.add(tool_name)

    def remove_allowed_tool(self, tool_name: str) -> None:
        """从白名单移除工具

        Args:
            tool_name: 工具名称
        """
        self.allowed_tools.discard(tool_name)


class FullAccessFilter(ToolFilter):
    """完全访问过滤器

    允许使用所有工具（除了明确禁止的危险工具），适用于：
    - code（代码实现）
    - refactor（代码重构）
    """

    # 危险工具黑名单
    DENIED_TOOLS: Set[str] = {
        # 危险命令工具
        "Command_sudo",
        "Command_rm_rf",
        "Command_dd",
        "Command_format",
        "Command_mkfs",
        "Command_chmod",
        "Command_chown",
        # 其他危险工具
        "Bash", "BashTool",
        "Terminal", "TerminalTool",
        "Execute", "ExecuteTool",
    }

    def __init__(self, additional_denied: Optional[List[str]] = None):
        """初始化完全访问过滤器

        Args:
            additional_denied: 额外禁止的工具名称列表
        """
        self.denied_tools = self.DENIED_TOOLS.copy()
        if additional_denied:
            self.denied_tools.update(additional_denied)

    def is_allowed(self, tool_name: str) -> bool:
        """检查是否允许（不在黑名单中）"""
        return tool_name not in self.denied_tools

    def add_denied_tool(self, tool_name: str) -> None:
        """添加工具到黑名单

        Args:
            tool_name: 工具名称
        """
        self.denied_tools.add(tool_name)

    def remove_denied_tool(self, tool_name: str) -> None:
        """从黑名单移除工具

        Args:
            tool_name: 工具名称
        """
        self.denied_tools.discard(tool_name)


class CustomFilter(ToolFilter):
    """自定义工具过滤器

    用户可以明确指定允许或禁止的工具列表。

    使用模式:
    - whitelist: 只允许列表中的工具
    - blacklist: 禁止列表中的工具，其他都允许
    """

    def __init__(
        self,
        allowed: Optional[Set[str]] = None,
        denied: Optional[Set[str]] = None,
        mode: str = "whitelist"
    ):
        """初始化自定义过滤器

        Args:
            allowed: 允许的工具名称集合（白名单模式）
            denied: 禁止的工具名称集合（黑名单模式）
            mode: 过滤模式，"whitelist"（白名单）或 "blacklist"（黑名单）
        """
        self.allowed = allowed if allowed else set()
        self.denied = denied if denied else set()
        self.mode = mode

        if mode not in ("whitelist", "blacklist"):
            raise ValueError(f"Invalid mode: {mode}. Must be 'whitelist' or 'blacklist'")

    def is_allowed(self, tool_name: str) -> bool:
        """检查是否允许"""
        if self.mode == "whitelist":
            return tool_name in self.allowed
        else:  # blacklist
            return tool_name not in self.denied

    def add_allowed(self, tool_name: str) -> None:
        """添加工具到白名单（仅 whitelist 模式）"""
        if self.mode == "whitelist":
            self.allowed.add(tool_name)

    def add_denied(self, tool_name: str) -> None:
        """添加工具到黑名单（仅 blacklist 模式）"""
        if self.mode == "blacklist":
            self.denied.add(tool_name)


class StrictFilter(ToolFilter):
    """严格过滤器

    只有明确列出的工具才允许使用。
    适用于高度受限的场景。
    """

    # 严格允许的工具列表
    ALLOWED_TOOLS: Set[str] = {
        # 基础工具
        "Read", "LS", "Glob", "Grep",
        # Command 安全命令
        "Command_ls", "Command_pwd", "Command_cat",
        "Command_git_status",
        # 笔记
        "NoteRead", "NoteSearch",
    }

    def __init__(self, additional_allowed: Optional[List[str]] = None):
        """初始化严格过滤器

        Args:
            additional_allowed: 额外允许的工具名称列表
        """
        self.allowed_tools = self.ALLOWED_TOOLS.copy()
        if additional_allowed:
            self.allowed_tools.update(additional_allowed)

    def is_allowed(self, tool_name: str) -> bool:
        """检查是否在严格允许列表中"""
        return tool_name in self.allowed_tools
