"""ToolFilter - 工具过滤器机制

用于控制子代理可以访问的工具集合。
灵感来自 HelloAgents 的 ToolFilter 机制。
"""

from abc import ABC, abstractmethod
from typing import Set, List, Optional
from pathlib import Path
import fnmatch


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


class BashRestrictedFilter(ToolFilter):
    """Bash 命令限制过滤器

    用于 Bash Agent，限制可执行的命令：
    - 白名单：直接执行
    - 黑名单：禁止执行
    - 需确认：需要用户确认

    适用于：
    - bash（终端执行与测试验证）
    """

    # 命令白名单（直接执行）
    WHITELIST: Set[str] = {
        # 测试
        "pytest", "python -m pytest",
        # 类型检查
        "mypy", "python -m mypy",
        # 代码风格
        "flake8", "black --check", "ruff",
        # 信息查看
        "ls", "cat", "head", "tail", "pwd", "wc",
        # Python
        "python", "python -m",
        # Git 只读
        "git status", "git log", "git diff", "git branch", "git show",
    }

    # 命令黑名单（直接禁止）
    BLACKLIST: Set[str] = {
        "rm -rf",
        "mkfs",
        "chmod 777",
        "curl|bash",
        "dd",
        "sudo",
        "Command_sudo",
        "Command_rm_rf",
        "Command_dd",
        "Command_format",
        "Command_mkfs",
        "Command_chmod",
        "Command_chown",
    }

    # 需要确认的命令
    REQUIRE_CONFIRM: Set[str] = {
        "pip install",
        "pipenv install",
        "poetry add",
        "poetry install",
        "git commit",
        "git push",
        "npm install",
        "npm run build",
        "make",
    }

    def __init__(
        self,
        whitelist: Optional[Set[str]] = None,
        blacklist: Optional[Set[str]] = None,
        require_confirm: Optional[Set[str]] = None
    ):
        """初始化 Bash 限制过滤器

        Args:
            whitelist: 额外允许的命令（添加到默认白名单）
            blacklist: 额外禁止的命令（添加到默认黑名单）
            require_confirm: 需要确认的命令（添加到默认列表）
        """
        self.whitelist = self.WHITELIST.copy()
        self.blacklist = self.BLACKLIST.copy()
        self.require_confirm = self.REQUIRE_CONFIRM.copy()

        if whitelist:
            self.whitelist.update(whitelist)
        if blacklist:
            self.blacklist.update(blacklist)
        if require_confirm:
            self.require_confirm.update(require_confirm)

    def is_allowed(self, command: str) -> bool:
        """检查命令是否允许（在白名单中且不在黑名单中）"""
        # 黑名单优先
        if self._matches_blacklist(command):
            return False
        # 检查是否在白名单中
        return self._matches_whitelist(command)

    def needs_confirm(self, command: str) -> bool:
        """检查命令是否需要用户确认

        Args:
            command: 命令字符串

        Returns:
            bool: 是否需要确认
        """
        if self._matches_blacklist(command):
            return False  # 黑名单直接拒绝，不需要确认
        return self._matches_confirm_list(command)

    def _matches_blacklist(self, command: str) -> bool:
        """检查是否匹配黑名单"""
        for pattern in self.blacklist:
            if pattern in command:
                return True
        return False

    def _matches_whitelist(self, command: str) -> bool:
        """检查是否匹配白名单"""
        for pattern in self.whitelist:
            if pattern in command:
                return True
        return False

    def _matches_confirm_list(self, command: str) -> bool:
        """检查是否需要确认"""
        for pattern in self.require_confirm:
            if pattern in command:
                return True
        return False

    def get_command_status(self, command: str) -> str:
        """获取命令状态

        Args:
            command: 命令字符串

        Returns:
            str: "allowed" / "needs_confirm" / "denied"
        """
        if self._matches_blacklist(command):
            return "denied"
        if self._matches_confirm_list(command):
            return "needs_confirm"
        if self._matches_whitelist(command):
            return "allowed"
        return "denied"  # 不在白名单的默认拒绝


class PlannerFilter(ReadOnlyFilter):
    """Planner 专用过滤器

    继承 ReadOnlyFilter，额外允许 WebSearch 和 WebFetch 用于技术调研

    适用于：
    - planner（需求分析与任务规划）
    """

    def __init__(self, additional_allowed: Optional[List[str]] = None):
        """初始化 Planner 过滤器

        Args:
            additional_allowed: 额外允许的工具名称列表
        """
        super().__init__(additional_allowed)
        # Planner 额外允许 Web 搜索工具
        self.allowed_tools.update({
            "WebSearch",
            "WebFetch",
        })


class WorkDirFilter(ToolFilter):
    """工作目录访问控制过滤器

    用于限制 Agent 只能访问工作目录内的文件，防止访问敏感文件或修改自身代码。

    功能:
    1. 检查文件路径是否在工作目录内
    2. 检查路径是否匹配 denied patterns
    3. 拒绝访问工作目录外的路径

    适用于：
    - 所有需要文件访问的 Agent
    """

    # 默认禁止的模式（相对于工作目录）
    DEFAULT_DENIED_PATTERNS: List[str] = [
        "../**",           # 禁止访问父目录
        "/etc/**",         # 禁止访问系统目录
        "/usr/**",         # 禁止访问系统目录
        "/bin/**",         # 禁止访问系统目录
        "/sbin/**",        # 禁止访问系统目录
        "**/.env",         # 禁止访问.env 文件
        "**/credentials*", # 禁止访问凭证文件
        "**/*.key",        # 禁止访问密钥文件
        "**/.ssh/**",      # 禁止访问 SSH 目录
    ]

    def __init__(
        self,
        workdir: Path,
        denied_patterns: Optional[List[str]] = None,
        allowed_patterns: Optional[List[str]] = None
    ):
        """初始化工作目录过滤器

        Args:
            workdir: 工作目录路径
            denied_patterns: 额外禁止的路径模式（添加到默认列表）
            allowed_patterns: 允许的路径模式（用于更精细的控制）
        """
        self.workdir = workdir.resolve()
        self.denied_patterns = self.DEFAULT_DENIED_PATTERNS.copy()
        if denied_patterns:
            self.denied_patterns.extend(denied_patterns)
        self.allowed_patterns = allowed_patterns or ["**/*"]  # 默认允许所有工作目录内的文件

    def is_path_allowed(self, path: Path) -> bool:
        """检查路径是否允许访问

        Args:
            path: 要检查的路径

        Returns:
            bool: 是否允许访问
        """
        # 解析路径（解析符号链接和..）
        try:
            resolved_path = path.resolve()
        except (OSError, ValueError):
            return False

        # 1. 必须在工作目录内
        try:
            resolved_path.relative_to(self.workdir)
        except ValueError:
            # 路径不在工作目录内
            return False

        # 2. 不能匹配 denied patterns
        path_str = str(resolved_path)
        relative_path = resolved_path.relative_to(self.workdir)
        relative_str = str(relative_path)

        for pattern in self.denied_patterns:
            if self._matches_pattern(path_str, pattern) or self._matches_pattern(relative_str, pattern):
                return False

        # 3. 必须匹配 allowed patterns
        for pattern in self.allowed_patterns:
            if self._matches_pattern(relative_str, pattern):
                return True

        # 没有匹配任何允许的模式
        return False

    def _matches_pattern(self, path: str, pattern: str) -> bool:
        """检查路径是否匹配 glob 模式

        Args:
            path: 路径字符串
            pattern: glob 模式（支持 ** 递归匹配）

        Returns:
            bool: 是否匹配
        """
        import pathlib

        # 使用 pathlib 的 glob 匹配
        path_obj = pathlib.PurePath(path)

        # 处理 ** 模式
        if "**" in pattern:
            # 对于 **/* 模式，匹配任何路径
            if pattern == "**/*":
                return True
            # 对于其他 ** 模式，使用 fnmatch
            fnmatch_pattern = pattern.replace("**", "*")
            return fnmatch.fnmatch(path, fnmatch_pattern) or fnmatch.fnmatch(str(path_obj.name), fnmatch_pattern)
        else:
            # 简单模式匹配
            return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(str(path_obj.name), pattern)

    def is_allowed(self, tool_name: str) -> bool:
        """检查工具是否允许使用（此过滤器不限制工具类型）

        Args:
            tool_name: 工具名称

        Returns:
            bool: 是否允许（总是返回 True，实际检查在路径级别）
        """
        return True  # 工具本身允许，路径检查在其他方法中

    def check_path(self, path: str | Path) -> tuple[bool, str]:
        """检查路径并返回详细结果

        Args:
            path: 要检查的路径

        Returns:
            tuple[bool, str]: (是否允许，原因)
        """
        path = Path(path)

        # 解析路径
        try:
            resolved_path = path.resolve()
        except (OSError, ValueError) as e:
            return False, f"无法解析路径：{e}"

        # 检查工作目录
        try:
            resolved_path.relative_to(self.workdir)
        except ValueError:
            return False, f"路径在工作目录外：{resolved_path} (workdir: {self.workdir})"

        # 检查 denied patterns
        path_str = str(resolved_path)
        relative_path = resolved_path.relative_to(self.workdir)
        relative_str = str(relative_path)

        for pattern in self.denied_patterns:
            if self._matches_pattern(path_str, pattern) or self._matches_pattern(relative_str, pattern):
                return False, f"路径匹配禁止模式：{pattern}"

        # 检查 allowed patterns
        for pattern in self.allowed_patterns:
            if self._matches_pattern(relative_str, pattern):
                return True, "路径允许访问"

        return False, f"路径不匹配任何允许的模式"
