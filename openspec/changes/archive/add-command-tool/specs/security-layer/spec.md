# Spec: SecurityLayer

## Overview

安全层级定义，提供黑名单、白名单和安全模式的配置。

## Components

### SecurityMode

```python
class SecurityMode(str, Enum):
    STRICT = "strict"      # 只有白名单
    NORMAL = "normal"      # 黑名单 + 白名单 + 确认
    TRUST = "trust"        # 只有黑名单
```

### SecurityLevel

```python
class SecurityLevel:
    """安全检查层级"""

    BANNED_COMMANDS: Set[str]  # 黑名单
    SAFE_READ_ONLY: Set[str]   # 白名单 (免审)
    REQUIRES_CONFIRMATION: Set[str]  # 需确认

    def is_banned(self, command: str) -> bool
    def is_safe_readonly(self, command: str) -> bool
    def requires_confirmation(self, command: str) -> bool
```

## Banned Commands

| Command | Reason |
|---------|--------|
| curl, wget | 网络工具，可能泄露数据 |
| nc, telnet | 网络连接工具 |
| rm -rf, rm -r | 危险删除操作 |
| sudo, su | 权限提升 |
| chmod, chown | 权限修改 |
| dd, mkfs, fdisk | 磁盘操作 |

## Safe Read-Only Commands

| Command | Description |
|---------|-------------|
| ls, pwd | 目录浏览 |
| echo, whoami, date | 基础信息 |
| cat, head, tail | 文件读取 |
| git status, log, diff | Git 只读 |
| python --version | 版本信息 |
| pytest --collect-only | 测试收集 |

## Methods

### is_banned(command: str) -> bool

检查命令是否在黑名单中。

### is_safe_readonly(command: str) -> bool

检查命令是否是安全的只读命令。

### requires_confirmation(command: str) -> bool

检查命令是否需要用户确认。

## Dependencies

None
