# Design: Command Tool 安全架构

## 1. 架构概览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CommandTool 安全架构                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   │
│  │   黑名单    │   │   白名单    │   │   权限确认    │   │   安全执行    │   │
│  │  BannedCheck │──▶│ AllowedCheck │──▶│ Permission   │──▶│ Executor    │   │
│  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘   │
│         │                   │                   │                  │                  │   │
│         ▼                   ▼                   ▼                  ▼                  │   │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │              CommandTool (统一入口)                                   │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 2. 模块设计

### 2.1 安全层级

```python
# src/mini_coder/tools/security.py

from enum import Enum
from typing import Set

class SecurityMode(str, Enum):
    """安全模式"""
    STRICT = "strict"      # 只有白名单
    NORMAL = "normal"      # 黑名单 + 白名单 + 确认
    TRUST = "trust"        # 只有黑名单

class SecurityLevel:
    """安全检查层级"""

    # 黑名单 - 直接拒绝
    BANNED_COMMANDS: Set[str] = {
        # 网络工具
        "curl", "curlie", "wget", "axel", "aria2c",
        "nc", "telnet", "lynx", "w3m", "links", "httpie", "xh",
        # 危险操作
        "rm -rf", "rm -r", "rmdir", "del",
        "sudo", "su", "passwd",
        "chmod", "chown",
        "dd", "mkfs", "fdisk", "format",
        # Shell 操作符
        # 注意: 这些在命令字符串中检测
    }

    # 白名单 - 无需确认
    SAFE_READ_ONLY: Set[str] = {
        # 基础命令
        "ls", "pwd", "echo", "whoami", "date", "cal", "uptime",
        "cat", "head", "tail", "less", "more", "wc",
        "which", "whereis", "env", "printenv",
        # Git 只读
        "git status", "git log", "git diff", "git show",
        "git branch", "git tag", "git remote", "git ls-files",
        "git rev-parse", "git config", "git describe", "git blame",
        # Python/Node 只读
        "python --version", "python -c", "pip --version",
        "node --version", "npm --version",
        "pytest --collect-only", "pytest --co",
    }

    # 需要确认的命令
    REQUIRES_CONFIRMATION: Set[str] = {
        # 文件操作
        "mkdir", "touch", "cp", "mv", "ln",
        "git add", "git commit", "git push", "git pull",
        "git checkout", "git merge", "git rebase",
        # 开发工具
        "pytest", "npm", "pip", "python", "node",
        "go", "cargo", "rustc",
    }
```

### 2.2 核心类

```python
# src/mini_coder/tools/command.py

from dataclasses import dataclass
from typing import Optional
from .security import SecurityMode, SecurityLevel
from .permission import PermissionService
from .executor import SafeExecutor

@dataclass
class CommandResult:
    """命令执行结果"""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    interrupted: bool = False
    execution_time_ms: int = 0

class CommandTool:
    """安全的命令执行工具"""

    def __init__(
        self,
        security_mode: SecurityMode = SecurityMode.NORMAL,
        permission_service: Optional[PermissionService] = None,
        timeout: int = 120,
    ):
        self.security_mode = security_mode
        self.permission_service = permission_service
        self.executor = SafeExecutor(timeout=timeout)
        self._security = SecurityLevel()

    def execute(self, command: str) -> CommandResult:
        """执行命令（三层安全检查）"""

        # Layer 1: 黑名单检查
        if self._security.is_banned(command):
            return CommandResult(
                success=False,
                stdout="",
                stderr=f"命令被禁止: 包含危险操作",
                exit_code=1,
            )

        # Layer 2: 白名单免审
        if self._security.is_safe_readonly(command):
            return self.executor.execute(command)

        # Layer 3: 根据安全模式处理
        if self.security_mode == SecurityMode.STRICT:
            return CommandResult(
                success=False,
                stdout="",
                stderr="严格模式下只允许安全命令",
                exit_code=1,
            )

        if self.security_mode == SecurityMode.TRUST:
            # 信任模式: 只有黑名单检查
            return self.executor.execute(command)

        # Normal 模式: 需要确认
        if self.permission_service and not self.permission_service.request(command):
            return CommandResult(
                success=False,
                stdout="",
                stderr="用户拒绝执行",
                exit_code=1,
            )

        return self.executor.execute(command)
```

### 2.3 权限服务

```python
# src/mini_coder/tools/permission.py

from typing import Dict, Optional, Set
from dataclasses import dataclass
from collections import defaultdict

@dataclass
class PermissionRequest:
    """权限请求"""
    id: str
    session_id: str
    command: str
    description: str

class PermissionService:
    """权限服务 - 管理命令执行权限"""

    def __init__(self):
        self._granted: Dict[str, Set[str]] = defaultdict(set)
        self._pending: Dict[str, PermissionRequest] = {}
        self._auto_approve_sessions: Set[str] = set()

    def request(self, session_id: str, command: str) -> bool:
        """请求执行权限"""
        # 检查是否已授权
        if session_id in self._auto_approve_sessions:
            return True

        # 检查缓存
        if command in self._granted.get(session_id, set()):
            return True

        # 创建权限请求
        request = PermissionRequest(
            id=str(uuid.uuid4()),
            session_id=session_id,
            command=command,
            description=f"执行命令: {command}"
        )

        # 发送确认请求 (通过回调)
        if self._on_request_callback:
            return self._on_request_callback(request)

        return False

    def grant(self, request_id: str, session_id: str, command: str) -> None:
        """授予权限"""
        if session_id not in self._granted:
            self._granted[session_id] = set()
        self._granted[session_id].add(command)

    def auto_approve_session(self, session_id: str) -> None:
        """自动批准会话 (信任模式)"""
        self._auto_approve_sessions.add(session_id)
```

### 2.4 ToolFilter 机制

```python
# src/mini_coder/tools/filter.py

from abc import ABC, abstractmethod
from typing import Set, List

class ToolFilter(ABC):
    """工具过滤器基类"""

    @abstractmethod
    def is_allowed(self, tool_name: str) -> bool:
        """检查工具是否允许"""
        pass

    def filter(self, all_tools: List[str]) -> List[str]:
        """过滤工具列表"""
        return [t for t in all_tools if self.is_allowed(t)]


class ReadOnlyFilter(ToolFilter):
    """只读过滤器 - 用于 explore/plan 代理"""

    ALLOWED: Set[str] = {
        # 文件读取
        "Read", "ReadTool",
        # 目录浏览
        "LS", "LSTool", "Glob", "GlobTool",
        # 搜索
        "Grep", "GrepTool",
        # 笔记读取
        "NoteRead", "NoteSearch",
        # Command 只读命令
        "Command_ls", "Command_pwd", "Command_cat",
        "Command_git_status", "Command_git_log",
    }

    def is_allowed(self, tool_name: str) -> bool:
        return tool_name in self.ALLOWED


class FullAccessFilter(ToolFilter):
    """完全访问过滤器 - 用于 code 代理"""

    DENIED: Set[str] = {
        # 危险命令
        "Command_sudo", "Command_rm_rf", "Command_dd",
        "Command_format", "Command_mkfs",
    }

    def is_allowed(self, tool_name: str) -> bool:
        return tool_name not in self.DENIED
```

## 3. 文件结构

```
src/mini_coder/tools/
├── __init__.py
├── base.py              # Tool 基类 (已存在)
├── command.py           # CommandTool 主类
├── security.py          # 安全层级定义
├── permission.py        # 权限服务
├── executor.py          # 安全执行器
├── filter.py            # ToolFilter 机制
└── config.py            # 配置加载
```

## 4. 配置

```yaml
# config/tools.yaml

command:
  security_mode: normal    # strict, normal, trust
  timeout:
    default: 120
    max: 600
  max_output_length: 30000
  permission_cache_ttl: 3600

  allowed_paths:
    - ${PROJECT_ROOT}
    - /tmp
```

## 5. 与现有系统集成

### 5.1 LLMService 集成

```python
# 在 LLMService 中添加 CommandTool
class LLMService:
    def __init__(self, ..., enable_command_tool: bool = True):
        if enable_command_tool:
            self._command_tool = CommandTool(
                security_mode=config.command.security_mode,
                permission_service=self._permission_service,
            )
```

### 5.2 子代理集成

```python
# 子代理使用 ToolFilter
from mini_coder.tools.filter import ReadOnlyFilter, FullAccessFilter

# Explore 代理 - 只读
explore_agent = Agent(tools=ReadOnlyFilter().filter(all_tools))

# Code 代理 - 完全访问
code_agent = Agent(tools=FullAccessFilter().filter(all_tools))
```

## 6. 安全考虑

### 6.1 命令注入防护

- 使用 `shell_quote` 转义特殊字符
- 避免使用 `shell=True`（已通过白名单验证的命令除外）
- 超时控制防止长时间运行

### 6.2 路径安全

- 检查工作目录是否在允许列表
- 禁止访问系统敏感目录 (/etc, /bin, /usr)
- 防止路径遍历攻击 (../)

### 6.3 输出控制

- 截断过长输出 (30KB)
- 记录执行时间
- 保留执行日志

## 7. 参考资源

- `knowledge-base/opencode/internal/llm/tools/bash.go`
- `knowledge-base/opencode/internal/permission/permission.go`
- `knowledge-base/hello-agents/code/chapter16/.../terminal_tool.py`
- `knowledge-base/helloagents/hello_agents/tools/tool_filter.py`
- `docs/command-execution-security-design.md`
