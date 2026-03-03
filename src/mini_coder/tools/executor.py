"""安全命令执行器 - 安全的 subprocess 封装"""

import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from typing import Optional
from .security import SecurityLevel


@dataclass
class CommandResult:
    """命令执行结果

    Attributes:
        success: 是否执行成功
        stdout: 标准输出
        stderr: 标准错误
        exit_code: 退出码
        interrupted: 是否被中断
        execution_time_ms: 执行时间 (毫秒)
    """
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    interrupted: bool = False
    execution_time_ms: int = 0


class SafeExecutor:
    """安全命令执行器

    提供安全的命令执行功能，包括：
    - 超时控制
    - 输出截断
    - Shell 引号转义
    - 工作目录限制
    """

    DEFAULT_TIMEOUT = 120  # 2 分钟
    MAX_TIMEOUT = 600      # 10 分钟
    MAX_OUTPUT_LENGTH = 30000  # 30KB

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        max_output_length: int = MAX_OUTPUT_LENGTH,
        allowed_paths: Optional[list[str]] = None,
    ):
        """初始化执行器

        Args:
            timeout: 默认超时时间 (秒)
            max_output_length: 最大输出长度
            allowed_paths: 允许的工作目录列表
        """
        self.timeout = timeout
        self.max_output_length = max_output_length
        self.allowed_paths = allowed_paths
        self._security = SecurityLevel()

    def execute(
        self,
        command: str,
        timeout: Optional[int] = None,
        cwd: Optional[str] = None,
    ) -> CommandResult:
        """执行命令

        Args:
            command: 要执行的命令
            timeout: 可选的超时时间 (秒)
            cwd: 可选的工作目录

        Returns:
            CommandResult: 执行结果
        """
        start_time = time.time()

        # 使用传入的超时或默认超时
        exec_timeout = timeout if timeout is not None else self.timeout
        # 限制最大超时
        exec_timeout = min(exec_timeout, self.MAX_TIMEOUT)

        # 检查工作目录
        if cwd and not self._is_safe_path(cwd):
            return CommandResult(
                success=False,
                stdout="",
                stderr=f"不安全的工作目录：{cwd}",
                exit_code=1,
            )

        try:
            # 执行命令
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=cwd,
            )

            stdout, stderr = process.communicate(timeout=exec_timeout)

            # 截断输出
            stdout = self._truncate_output(stdout)
            stderr = self._truncate_output(stderr)

            execution_time = int((time.time() - start_time) * 1000)

            return CommandResult(
                success=process.returncode == 0,
                stdout=stdout,
                stderr=stderr,
                exit_code=process.returncode or 0,
                execution_time_ms=execution_time,
            )

        except subprocess.TimeoutExpired:
            # 尝试终止进程
            try:
                process.kill()
            except Exception:
                pass

            execution_time = int((time.time() - start_time) * 1000)
            return CommandResult(
                success=False,
                stdout="",
                stderr=f"命令执行超时 (超过 {exec_timeout} 秒)",
                exit_code=-1,
                interrupted=True,
                execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            return CommandResult(
                success=False,
                stdout="",
                stderr=f"执行异常：{str(e)}",
                exit_code=-1,
                execution_time_ms=execution_time,
            )

    def execute_with_check(
        self,
        command: str,
        security: Optional[SecurityLevel] = None,
        **kwargs
    ) -> CommandResult:
        """执行命令前先进行安全检查

        Args:
            command: 要执行的命令
            security: 安全检查器 (可选，使用内部的如果未提供)
            **kwargs: 传递给 execute() 的参数

        Returns:
            CommandResult: 执行结果
        """
        sec = security or self._security

        # 检查是否被禁止
        if sec.is_banned(command):
            return CommandResult(
                success=False,
                stdout="",
                stderr="命令被禁止：包含危险操作",
                exit_code=1,
            )

        return self.execute(command, **kwargs)

    def _truncate_output(self, output: str) -> str:
        """截断过长的输出

        Args:
            output: 原始输出

        Returns:
            截断后的输出
        """
        if len(output) <= self.max_output_length:
            return output

        half = self.max_output_length // 2
        truncated_count = len(output) - self.max_output_length

        return (
            output[:half]
            + f"\n\n... [{truncated_count} 字符被截断] ...\n\n"
            + output[-half:]
        )

    def _is_safe_path(self, path: str) -> bool:
        """检查路径是否安全

        Args:
            path: 要检查的路径

        Returns:
            bool: 是否安全
        """
        # 如果有允许列表，检查是否在列表中
        if self.allowed_paths:
            real_path = os.path.realpath(path)
            for allowed in self.allowed_paths:
                real_allowed = os.path.realpath(allowed)
                if real_path.startswith(real_allowed):
                    return True
            return False

        # 默认检查：禁止访问系统敏感目录
        dangerous_prefixes = ["/etc", "/bin", "/usr", "/var", "/sys", "/proc", "/root"]

        # 处理相对路径
        if not os.path.isabs(path):
            # 相对路径，检查是否包含危险前缀
            if any(dangerous in path for dangerous in dangerous_prefixes):
                return False
            # 相对路径默认允许（在当前目录下）
            return True

        real_path = os.path.realpath(path)
        for prefix in dangerous_prefixes:
            if real_path == prefix or real_path.startswith(prefix + "/"):
                return False

        return True

    @staticmethod
    def shell_quote(s: str) -> str:
        """安全转义 shell 命令

        Args:
            s: 要转义的字符串

        Returns:
            转义后的字符串
        """
        return "'" + s.replace("'", "'\\''") + "'"

    @staticmethod
    def split_command(command: str) -> list[str]:
        """安全分割命令

        Args:
            command: 命令字符串

        Returns:
            分割后的命令列表
        """
        return shlex.split(command)

    def set_allowed_paths(self, paths: list[str]) -> None:
        """设置允许的工作目录列表

        Args:
            paths: 允许的目录列表
        """
        self.allowed_paths = paths

    def set_timeout(self, timeout: int) -> None:
        """设置默认超时时间

        Args:
            timeout: 超时时间 (秒)
        """
        self.timeout = min(timeout, self.MAX_TIMEOUT)
