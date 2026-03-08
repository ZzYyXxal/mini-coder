"""安全层级定义 - 命令执行安全检查"""

from enum import Enum
from typing import FrozenSet


class SecurityMode(str, Enum):
    """安全模式

    Attributes:
        STRICT: 只有白名单命令可以执行
        NORMAL: 黑名单 + 白名单 + 权限确认 (默认)
        TRUST: 只有黑名单检查，其他直接执行
    """
    STRICT = "strict"
    NORMAL = "normal"
    TRUST = "trust"

    @classmethod
    def from_string(cls, value: str) -> "SecurityMode":
        """Convert string to SecurityMode enum.

        Args:
            value: String value (case-insensitive)

        Returns:
            SecurityMode enum value, defaults to NORMAL if invalid
        """
        value = value.lower().strip()
        try:
            return cls(value)
        except ValueError:
            return cls.NORMAL


class SecurityLevel:
    """安全检查层级

    提供三层安全检查：
    1. 黑名单检查 - 直接拒绝危险命令
    2. 白名单检查 - 安全命令无需确认
    3. 权限确认 - 其他命令需要用户确认
    """

    # 黑名单 - 直接拒绝的命令
    BANNED_COMMANDS: FrozenSet[str] = frozenset([
        # 网络工具 - 可能泄露数据
        "curl", "curlie", "wget", "axel", "aria2c",
        "nc", "telnet", "lynx", "w3m", "links", "httpie", "xh",
        "http-prompt", "chrome", "firefox", "safari",

        # 危险删除操作
        "rm -rf", "rm -r", "rmdir", "del", "deltree",

        # 权限提升
        "sudo", "su", "doas", "runas",

        # 权限修改
        "chmod", "chown", "chgrp",

        # 磁盘操作
        "dd", "mkfs", "fdisk", "format", "parted",
        "mkpart", "resize2fs", "e2fsck",

        # 系统控制
        "shutdown", "reboot", "halt", "init", "systemctl",
        "service", "kill", "killall", "pkill",

        # 其他危险命令
        "nohup", "disown",
    ])

    # 白名单 - 安全的只读命令 (无需确认)
    SAFE_READ_ONLY: FrozenSet[str] = frozenset([
        # 基础命令
        "ls", "pwd", "echo", "whoami", "date", "cal", "uptime",
        "hostname", "uname", "env", "printenv", "set", "unset",
        "which", "whereis", "whatis", "type",

        # 文件查看与搜索
        "cat", "head", "tail", "less", "more", "wc",
        "stat", "file", "tree", "du", "df", "free",
        "grep", "find", "locate",

        # Git 只读操作
        "git status", "git log", "git diff", "git show",
        "git branch", "git tag", "git remote", "git ls-files",
        "git rev-parse", "git describe", "git blame", "git shortlog",
        "git config --get", "git config --list",
        "git ls-remote", "git reflog",

        # Python/Node/Go 只读
        "python --version", "python -c", "python -m",
        "python3 --version", "pip --version", "pip list", "pip show",
        "node --version", "npm --version", "npm list",
        "go version", "go env", "go list", "go doc",
        "cargo --version", "rustc --version",

        # 测试工具 (只读模式)
        "pytest --collect-only", "pytest --co",
        "python -m pytest --collect-only",
    ])

    # 需要确认的命令 (项目内操作)
    REQUIRES_CONFIRMATION: FrozenSet[str] = frozenset([
        # 文件操作
        "mkdir", "touch", "cp", "mv", "ln", "rm",
        "chmod", "chown",

        # Git 写操作
        "git add", "git commit", "git push", "git pull",
        "git checkout", "git merge", "git rebase",
        "git reset", "git revert", "git cherry-pick",

        # 开发工具
        "pytest", "python -m pytest",
        "npm test", "npm run", "npm install", "npm build",
        "pip install", "pip uninstall",
        "go test", "go build", "go run", "go install",
        "cargo test", "cargo build", "cargo run",

        # 编辑器
        "vim", "vi", "nano", "emacs", "code",
        "sed", "awk",
    ])

    # 工作目录内允许的文件操作（首词）：当 cwd 在 allowed_paths 内且命令不逃逸到父目录/绝对路径时放行
    WORK_DIR_FILE_OPS: FrozenSet[str] = frozenset([
        "rm", "rmdir", "touch", "mkdir", "cp", "mv", "ln",
    ])

    # 危险关键词 (在命令字符串中检测)
    DANGEROUS_KEYWORDS: FrozenSet[str] = frozenset([
        # Shell 操作符
        ">", ">>", "<", "|",
        "&&", "||", ";",
        "`", "$(", "${",
        "eval", "exec",
        "source", ".",

        # 危险路径
        "/etc/", "/bin/", "/usr/", "/var/", "/sys/", "/proc/",
        "~/.ssh", "/root",

        # 其他
        "eval", "exec", "source",
    ])

    def is_work_dir_safe_command(self, command: str) -> bool:
        """判断是否为「仅在工作目录内」的文件操作，用于在 cwd 在 allowed_paths 时放行读写删。

        条件：首词为 rm/rmdir/touch/mkdir/cp/mv/ln，且命令中不包含父目录或绝对路径（不逃逸工作目录）。
        """
        if not command or not command.strip():
            return False
        first = command.strip().split(maxsplit=1)[0].lower()
        if first not in self.WORK_DIR_FILE_OPS:
            return False
        # 禁止逃逸到父目录或绝对路径
        if " .." in command or " /" in command or command.strip().startswith("/"):
            return False
        return True

    def is_work_dir_safe_readonly_pipeline(self, command: str) -> bool:
        """判断是否为「工作目录内仅读」的 find+cat 类管道/exec，用于支持「读取所有文件（含递归）」等模糊请求。

        放行：find 开头的命令，且为 -exec cat 或 | xargs cat/head 等只读组合，且不含写/删动词。
        """
        if not command or not command.strip():
            return False
        c = command.strip()
        if not c.lower().startswith("find "):
            return False
        # 禁止写/删
        for w in (" rm ", " mv ", " chmod", " >", ">>", "rm ", "mv "):
            if w in c or c.startswith(w.strip()):
                return False
        # 只读模式之一：find ... -exec cat {} \;
        if " -exec " in c and " cat " in c and " {} " in c:
            return True
        # 只读模式之二：find ... | xargs cat 或 xargs head
        if " | " in c and "xargs" in c and ("cat" in c or "head" in c):
            return True
        # 仅 find 列举（无 -exec 无管道）也视为只读，如 find . -type f
        if " -exec " not in c and " | " not in c:
            return True
        return False

    def is_banned(self, command: str) -> bool:
        """检查命令是否在黑名单中

        Args:
            command: 要检查的命令字符串

        Returns:
            bool: 如果是黑名单命令返回 True
        """
        cmd_lower = command.lower().strip()

        # 检查完整命令匹配 (包括带参数的命令如 "rm -rf")
        for banned in self.BANNED_COMMANDS:
            if cmd_lower.startswith(banned + " ") or cmd_lower == banned:
                return True

        # 检查危险关键词
        for keyword in self.DANGEROUS_KEYWORDS:
            if keyword in command:
                # 特殊处理：允许单个 > 作为重定向 (但 >> 不允许)
                if keyword == ">" and ">>" not in command:
                    continue
                return True

        return False

    def is_safe_readonly(self, command: str) -> bool:
        """检查命令是否是安全的只读命令

        Args:
            command: 要检查的命令字符串

        Returns:
            bool: 如果是安全的只读命令返回 True
        """
        cmd_lower = command.lower().strip()

        # 提取命令的前几个词用于匹配
        words = cmd_lower.split()

        # 尝试匹配多词命令 (如 "git status", "python --version")
        for i in range(min(4, len(words)), 0, -1):
            prefix = " ".join(words[:i])
            if prefix in self.SAFE_READ_ONLY:
                return True

        # 检查单个命令
        if words and words[0] in self.SAFE_READ_ONLY:
            return True

        return False

    def requires_confirmation(self, command: str) -> bool:
        """检查命令是否需要用户确认

        Args:
            command: 要检查的命令字符串

        Returns:
            bool: 如果需要确认返回 True
        """
        cmd_lower = command.lower().strip()
        words = cmd_lower.split()

        # 尝试匹配多词命令
        for i in range(min(4, len(words)), 0, -1):
            prefix = " ".join(words[:i])
            if prefix in self.REQUIRES_CONFIRMATION:
                return True

        # 检查单个命令
        if words and words[0] in self.REQUIRES_CONFIRMATION:
            return True

        # 不在白名单的命令默认需要确认
        return True

    def get_command_category(self, command: str) -> str:
        """获取命令的安全类别

        Args:
            command: 要检查的命令字符串

        Returns:
            str: 'banned', 'safe', 或 'requires_confirmation'
        """
        if self.is_banned(command):
            return "banned"
        if self.is_safe_readonly(command):
            return "safe"
        return "requires_confirmation"
