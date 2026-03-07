"""CommandTool - 安全的命令执行工具 (v2.0)

基于 BaseTool 2.0 框架，支持：
- 动态提示词加载（从 prompts/tools/command.md）
- 事件回调（TUI 集成）
- 配置字典支持
"""

import logging
from typing import Optional, Dict, Any, Callable, Union
from .base import BaseTool, ToolParameter, ToolResponse
from .security import SecurityMode, SecurityLevel
from .permission import PermissionService
from .executor import SafeExecutor, CommandResult

logger = logging.getLogger(__name__)


class CommandTool(BaseTool):
    """安全的命令执行工具 (v2.0)

    提供三层安全防护：
    1. 黑名单检查 - 直接拒绝危险命令
    2. 白名单免审 - 安全命令无需确认
    3. 权限确认 - 其他命令需要用户确认

    支持的安全模式：
    - strict: 只有白名单命令可以执行
    - normal: 黑名单 + 白名单 + 权限确认 (默认)
    - trust: 只有黑名单检查

    Usage:
    ```python
    tool = CommandTool(
        security_mode="normal",
        event_callback=my_callback,
        config={"timeout": 120, "max_output_length": 30000},
    )
    ```
    """

    # 类变量 - 工具类型和默认提示词路径
    TOOL_TYPE = "command"
    DEFAULT_PROMPT_PATH = "tools/command.md"

    def __init__(
        self,
        security_mode: SecurityMode = SecurityMode.NORMAL,
        permission_service: Optional[PermissionService] = None,
        timeout: int = 120,
        name: str = "Command",
        description: Optional[str] = None,
        event_callback: Optional[Callable[[str, str, Dict[str, Any]], None]] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """初始化 CommandTool

        Args:
            security_mode: 安全模式
            permission_service: 权限服务
            timeout: 默认超时时间 (秒)
            name: 工具名称
            description: 工具描述
            event_callback: 事件回调函数（用于 TUI 显示）
            config: 工具配置字典
        """
        # 向后兼容：支持旧的 SecurityMode 字符串
        if isinstance(security_mode, str):
            security_mode = SecurityMode(security_mode)

        # 从配置加载参数（如果提供了 config）
        config = config or {}
        if "security_mode" in config and isinstance(config["security_mode"], str):
            config["security_mode"] = SecurityMode(config["security_mode"])

        # 使用 description 参数或从 config 获取
        tool_description = description or config.get("description", "执行系统命令（安全检查）")

        # 调用父类初始化
        super().__init__(
            name=name,
            description=tool_description,
            prompt_path=self.DEFAULT_PROMPT_PATH,
            event_callback=event_callback,
            config=config,
        )

        self.security_mode = config.get("security_mode", security_mode)
        self._permission_service = permission_service
        self._executor = SafeExecutor(
            timeout=config.get("timeout", timeout),
            max_output_length=config.get("max_output_length", 30000),
            allowed_paths=config.get("allowed_paths"),
        )

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
        cwd = parameters.get("cwd")
        timeout = parameters.get("timeout")
        logger.info(f"[CommandTool] Executing: {command[:100]}{'...' if len(command) > 100 else ''}")

        if not command:
            logger.warning("[CommandTool] Empty command received")
            return ToolResponse.error(
                code="INVALID_COMMAND",
                message="命令不能为空"
            )

        # 通知事件：开始执行
        self.notify_event("start", {"command": command})

        # 安全检查并执行（支持 cwd 限制工作目录）
        result = self._execute_with_security(command, timeout=timeout, cwd=cwd)

        # 通知事件：完成
        self.notify_event("complete", {
            "command": command,
            "exit_code": result.exit_code,
            "duration_ms": result.execution_time_ms,
        })

        if result.success:
            logger.info(f"[CommandTool] Success: exit_code={result.exit_code}, time={result.execution_time_ms}ms")
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
            logger.error(f"[CommandTool] Failed: exit_code={result.exit_code}, stderr={result.stderr[:100] if result.stderr else 'None'}")
            # 通知事件：错误
            self.notify_event("error", {
                "command": command,
                "error_code": "EXECUTION_FAILED",
                "error_message": result.stderr or f"命令执行失败 (exit code: {result.exit_code})",
            })

            return ToolResponse.error(
                code="EXECUTION_FAILED",
                message=result.stderr or f"命令执行失败 (exit code: {result.exit_code})"
            )

    def _execute_with_security(
        self,
        command: str,
        timeout: Optional[int] = None,
        cwd: Optional[str] = None,
    ) -> CommandResult:
        """带安全检查的执行，支持 cwd 限制工作目录。

        Args:
            command: 要执行的命令
            timeout: 可选的超时时间
            cwd: 可选的工作目录（若设置了 allowed_paths 则必须在其内）
        """
        # Layer 1: 黑名单检查
        if self._executor._security.is_banned(command):
            logger.warning(f"[CommandTool] Command BANNED: {command[:50]}...")
            self.notify_event("security_check", {
                "command": command,
                "category": "banned",
            })
            return CommandResult(
                success=False,
                stdout="",
                stderr="命令被禁止：包含危险操作",
                exit_code=1,
            )

        # Layer 2: 白名单检查 - 安全命令直接执行
        if self._executor._security.is_safe_readonly(command):
            logger.debug(f"[CommandTool] Command SAFE (whitelist): {command[:50]}...")
            self.notify_event("security_check", {
                "command": command,
                "category": "safe",
            })
            return self._executor.execute(command, timeout=timeout, cwd=cwd)

        # Layer 3: 根据安全模式处理
        if self.security_mode == SecurityMode.STRICT:
            logger.warning(f"[CommandTool] Command BLOCKED (strict mode): {command[:50]}...")
            return CommandResult(
                success=False,
                stdout="",
                stderr="严格模式下只允许安全命令",
                exit_code=1,
            )

        if self.security_mode == SecurityMode.TRUST:
            logger.debug(f"[CommandTool] Command ALLOWED (trust mode): {command[:50]}...")
            return self._executor.execute(command, timeout=timeout, cwd=cwd)

        # Normal 模式：需要确认
        logger.debug(f"[CommandTool] Command requires confirmation: {command[:50]}...")
        if self._session_id and self._permission_service:
            if not self._permission_service.request(
                self._session_id,
                command,
                f"执行命令：{command}"
            ):
                logger.info(f"[CommandTool] Command DENIED by user: {command[:50]}...")
                self.notify_event("permission_request", {
                    "command": command,
                    "reason": "用户拒绝执行",
                })
                return CommandResult(
                    success=False,
                    stdout="",
                    stderr="用户拒绝执行",
                    exit_code=1,
                )

        return self._executor.execute(command, timeout=timeout, cwd=cwd)

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
                name="cwd",
                type="string",
                description="可选的工作目录，需在 allowed_paths 内",
                required=False
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
            tuple[bool, str]: (是否安全，原因)
        """
        if self._executor._security.is_banned(command):
            return False, "命令在黑名单中"

        if self._executor._security.is_safe_readonly(command):
            return True, "安全命令，无需确认"

        if self.security_mode == SecurityMode.STRICT:
            return False, "严格模式下只允许白名单命令"

        if self.security_mode == SecurityMode.TRUST:
            return True, "信任模式，只有黑名单检查"

        return False, "需要用户确认"

    def get_security_mode(self) -> SecurityMode:
        """获取当前安全模式"""
        # security_mode might be str due to backward compatibility (converted in __init__)
        mode = self.security_mode
        if isinstance(mode, str):
            return SecurityMode(mode)
        # At this point mode should be SecurityMode, but type checker sees it as Any
        return mode  # type: ignore[no-any-return]

    def set_security_mode(self, mode: SecurityMode) -> None:
        """设置安全模式"""
        self.security_mode = mode

    def get_available_commands(self) -> dict[str, list[str]]:
        """获取可用的命令列表

        Returns:
            包含 safe_commands 和 banned_commands 的字典
        """
        return {
            "safe_commands": list(self._executor._security.SAFE_READ_ONLY),
            "banned_commands": list(self._executor._security.BANNED_COMMANDS),
            "requires_confirmation": list(self._executor._security.REQUIRES_CONFIRMATION),
        }

    def _get_prompt_context(self) -> Dict[str, Any]:
        """供 prompt 占位符插值使用的上下文（与 prompts/tools/command.md 中的 {{key}} 对应）。"""
        mode = self.get_security_mode()
        return {
            "security_mode": mode.value if hasattr(mode, "value") else str(mode),
            "timeout": getattr(self._executor, "timeout", 120),
            "max_timeout": getattr(self._executor, "timeout", 120),
            "max_output_length": getattr(self._executor, "max_output_length", 30000),
            "allowed_paths": (
                ", ".join(self._executor.allowed_paths)
                if getattr(self._executor, "allowed_paths", None)
                else "未限制"
            ),
        }

    def get_system_prompt(self, context: Optional[Dict[str, Any]] = None) -> str:
        """加载系统提示词并注入占位符（{{security_mode}}、{{timeout}} 等）。"""
        merged = {**self._get_prompt_context(), **(context or {})}
        return super().get_system_prompt(merged)
