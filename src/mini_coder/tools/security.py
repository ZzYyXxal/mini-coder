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

        # 文件查看
        "cat", "head", "tail", "less", "more", "wc",
        "stat", "file", "tree", "du", "df", "free",

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
