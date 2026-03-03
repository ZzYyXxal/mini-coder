# Spec: CommandTool

## Overview

安全的命令执行工具，提供多层安全防护机制，包括黑名单检查、白名单免审和权限确认。

## Interface

```python
class CommandTool(Tool):
    """安全的命令执行工具"""

    def __init__(
        self,
        security_mode: SecurityMode = SecurityMode.NORMAL,
        permission_service: Optional[PermissionService] = None,
        timeout: int = 120,
    ): ...

    def execute(self, command: str) -> CommandResult:
        """执行命令

    def execute_with_output(
        self,
        command: str,
    ) -> Tuple[bool, str, str]:
        """执行命令并返回输出"""

    def is_command_safe(self, command: str) -> bool:
        """检查命令是否安全"""

    def get_security_mode(self) -> SecurityMode:
        """获取当前安全模式"""
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| command | string | Yes | 要执行的命令 |
| timeout | integer | No | 超时时间（秒），默认 120 |

## Returns

### CommandResult

```python
@dataclass
class CommandResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    interrupted: bool = False
    execution_time_ms: int = 0
```

## Security Levels

### Layer 1: Banned Check

黑名单命令直接拒绝，包括:
- 网络工具: curl, wget, nc, telnet
- 危险操作: rm -rf, sudo, dd, mkfs
- Shell 操作符 (检测)

### Layer 2: Safe ReadOnly

白名单命令无需确认
包括:
- 基础命令: ls, pwd, echo, whoami, date
- Git 只读: git status, log, diff, branch
- 开发工具: pytest, npm, pip, python

### Layer 3: Permission

非白名单命令需要用户确认
通过 PermissionService 请求权限

## Security Modes

| Mode | Behavior |
|------|----------|
| strict | 只有白名单命令，| normal | 黑名单 + 白名单 + 确认 (默认)
| trust | 只有黑名单检查 |

## Error Handling

| Error | Condition | Response |
|-------|-----------|----------|
| BannedCommandError | 命令在黑名单 | success=False, stderr=错误信息 |
| PermissionDeniedError | 用户拒绝 | success=False, stderr=错误信息 |
| TimeoutError | 执行超时 | success=False, interrupted=True |
| ExecutionError | 执行失败 | success=False, exit_code != 0 |

## Dependencies

- SecurityLevel
- PermissionService
- SafeExecutor
