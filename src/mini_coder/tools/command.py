"""CommandTool - 安全的命令执行工具"""

from typing import Optional, Dict, Any
from .base import Tool, ToolParameter, ToolResponse
from .security import SecurityMode, SecurityLevel
from .permission import PermissionService
from .executor import SafeExecutor, CommandResult


class CommandTool(Tool):
    """安全的命令执行工具

    提供三层安全防护：
    1. 黑名单检查 - 直接拒绝危险命令
    2. 白名单免审 - 安全命令无需确认
    3. 权限确认 - 其他命令需要用户确认

    支持的安全模式：
    - strict: 只有白名单命令可以执行
    - normal: 黑名单 + 白名单 + 权限确认 (默认)
    - trust: 只有黑名单检查
    """

    def __init__(
        self,
        security_mode: SecurityMode = SecurityMode.NORMAL,
        permission_service: Optional[PermissionService] = None,
        timeout: int = 120,
        name: str = "Command",
        description: Optional[str] = None,
    ):
        """初始化 CommandTool

        Args:
            security_mode: 安全模式
            permission_service: 权限服务
            timeout: 默认超时时间 (秒)
            name: 工具名称
            description: 工具描述
        """
        super().__init__(
            name=name,
            description=description or "执行系统命令（安全检查）"
        )

        self.security_mode = security_mode
        self._permission_service = permission_service
        self._security = SecurityLevel()
        self._executor = SafeExecutor(timeout=timeout)

        # 当前会话 ID（由外部设置）
        self._session_id: Optional[str] = None

    def set_session_id(self, session_id: str) -> None:
        """设置当前会话 ID

        Args:
            session_id: 会话 ID
        """
        self._session_id = session_id

    def run(self, parameters: Dict[str, Any]) -> ToolResponse:
        """执行命令

        Args:
            parameters: 工具参数，包含:
                - command: 要执行的命令
                - timeout: 可选的超时时间

        Returns:
            ToolResponse: 执行结果
        """
        command = parameters.get("command", "")

        if not command:
            return ToolResponse.error(
                code="INVALID_COMMAND",
                message="命令不能为空"
            )

        # 执行命令
        result = self._execute_with_security(command, parameters.get("timeout"))

        if result.success:
            output = result.stdout
            if result.stderr:
                output += "\n[stderr]\n" + result.stderr

            return ToolResponse.success(
                text=output,
                data={
                    "command": command,
                    "exit_code": result.exit_code,
                    "execution_time_ms": result.execution_time_ms,
                }
            )
        else:
            return ToolResponse.error(
                code="EXECUTION_FAILED",
                message=result.stderr or f"命令执行失败 (exit code: {result.exit_code})"
            )

    def _execute_with_security(
        self,
        command: str,
        timeout: Optional[int] = None
    ) -> CommandResult:
        """带安全检查的执行

        Args:
            command: 要执行的命令
            timeout: 可选的超时时间

        Returns:
            CommandResult: 执行结果
        """
        # Layer 1: 黑名单检查
        if self._security.is_banned(command):
            return CommandResult(
                success=False,
                stdout="",
                stderr="命令被禁止：包含危险操作",
                exit_code=1,
            )

        # Layer 2: 白名单检查 - 安全命令直接执行
        if self._security.is_safe_readonly(command):
            return self._executor.execute(command, timeout=timeout)

        # Layer 3: 根据安全模式处理
        if self.security_mode == SecurityMode.STRICT:
            return CommandResult(
                success=False,
                stdout="",
                stderr="严格模式下只允许安全命令",
                exit_code=1,
            )

        if self.security_mode == SecurityMode.TRUST:
            # 信任模式：只有黑名单检查
            return self._executor.execute(command, timeout=timeout)

        # Normal 模式：需要确认
        if self._session_id:
            if not self._permission_service.request(
                self._session_id,
                command,
                f"执行命令：{command}"
            ):
                return CommandResult(
                    success=False,
                    stdout="",
                    stderr="用户拒绝执行",
                    exit_code=1,
                )

        return self._executor.execute(command, timeout=timeout)

    def get_parameters(self) -> list[ToolParameter]:
        """获取工具参数定义"""
        return [
            ToolParameter(
                name="command",
                type="string",
                description="要执行的命令",
                required=True
            ),
            ToolParameter(
                name="timeout",
                type="integer",
                description="超时时间（秒），默认 120",
                required=False,
                default=120
            ),
        ]

    def is_command_safe(self, command: str) -> tuple[bool, str]:
        """检查命令是否安全

        Args:
            command: 要检查的命令

        Returns:
            tuple[bool, str]: (是否安全, 原因)
        """
        if self._security.is_banned(command):
            return False, "命令在黑名单中"

        if self._security.is_safe_readonly(command):
            return True, "安全命令，无需确认"

        if self.security_mode == SecurityMode.STRICT:
            return False, "严格模式下只允许白名单命令"

        if self.security_mode == SecurityMode.TRUST:
            return True, "信任模式，只有黑名单检查"

        return False, "需要用户确认"

    def get_security_mode(self) -> SecurityMode:
        """获取当前安全模式"""
        return self.security_mode

    def set_security_mode(self, mode: SecurityMode) -> None:
        """设置安全模式"""
        self.security_mode = mode

    def get_available_commands(self) -> dict[str, list[str]]:
        """获取可用的命令列表

        Returns:
            包含 safe_commands 和 banned_commands 的字典
        """
        return {
            "safe_commands": list(self._security.SAFE_READ_ONLY),
            "banned_commands": list(self._security.BANNED_COMMANDS),
            "requires_confirmation": list(self._security.REQUIRES_CONFIRMATION),
        }
