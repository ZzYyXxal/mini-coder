# 命令执行安全机制设计

> **状态**: 探索阶段
> **日期**: 2026-03-04
> **参考项目**: aider, OpenCode, Hello-Agents, HelloAgents

## 1. 背景

mini-coder 需要实现一个命令执行功能，允许 AI 调用系统命令查看目录或修改文件。这个功能有一定风险
需要实现多层安全防护机制。

## 2. 参考项目对比分析

### 2.1 架构对比

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        命令执行安全机制对比                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐ │
│  │   Aider     │    │  OpenCode   │    │Hello-Agents │    │ HelloAgents │ │
│  ├─────────────┤    ├─────────────┤    ├─────────────┤    ├─────────────┤ │
│  │ 无安全检查  │    │ 完善安全    │    │ 白名单模式  │    │ ToolFilter  │ │
│  │ 直接执行    │    │ 多层防护    │    │ 严格限制    │    │ 子代理隔离  │ │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘ │
│         │                  │                  │                  │          │
│         ▼                  ▼                  ▼                  ▼          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐ │
│  │ 风险：高    │    │ 风险：低    │    │ 风险：最低  │    │ 风险：低    │ │
│  │ 灵活：高    │    │ 灵活：中    │    │ 灵活：低    │    │ 灵活：高    │ │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 详细对比

| 特性 | Aider | OpenCode | Hello-Agents | HelloAgents |
|------|-------|----------|--------------|-------------|
| **语言** | Python | Go | Python | Python |
| **黑名单** | ❌ 无 | ✅ 有 | ❌ 无 | ⚠️ 通过 ToolFilter |
| **白名单** | ❌ 无 | ✅ 有 (免审) | ✅ 有 (严格) | ✅ 有 (可配置) |
| **权限系统** | ❌ 无 | ✅ 完整 | ❌ 无 | ⚠️ 可扩展 |
| **超时控制** | ⚠️ 可选 | ✅ 默认 2 分钟 | ✅ 15 秒固定 | ✅ 可配置 |
| **输出截断** | ❌ 无 | ✅ 30KB | ❌ 无 | ✅ 通过 ToolResponse |
| **路径检查** | ❌ 无 | ❌ 无 | ✅ 有 | ⚠️ 可扩展 |
| **Shell注入** | ⚠️ 高风险 | ✅ shellQuote | ⚠️ 中风险 | ✅ 沙箱隔离 |
| **持久Shell** | ❌ 无 | ✅ 有 | ❌ 无 | ❌ 无 |
| **安全模式** | ❌ 无 | ❌ 无 | ✅ strict/warning | ✅ ToolFilter |
| **子代理隔离** | ❌ 无 | ❌ 无 | ❌ 无 | ✅ 有 |

## 3. 核心发现

### 3.1 OpenCode - 最完善的安全架构

**亮点**:
1. **三层防护**: 黑名单 → 白名单免审 → 权限确认
2. **持久化 Shell**: 状态保持，效率高
3. **权限服务**: pubsub 模式，支持 UI 交互确认
4. **输出截断**: 防止输出过大

```go
// OpenCode 三层安全检查
if isBanned(command) {
    return Error("command is not allowed")
}
if isSafeReadOnly(command) {
    return execute(command)  // 无需确认
}
if !permission.Request(command) {
    return Error("permission denied")
}
return execute(command)
```

### 3.2 Hello-Agents - 最严格的白名单

**亮点**:
1. **命令白名单**: 只允许预定义的安全命令
2. **参数验证**: 检查每个参数是否在允许列表
3. **路径安全**: 防止访问敏感路径
4. **两种模式**: strict (拒绝) / warning (警告)

```python
# Hello-Agents 白名单
allowed_commands = {
    "ls": [], "pwd": [], "cat": ["*"],
    "grep": ["-i", "-n", "-r"],
    # ... 更多安全命令
}

# 危险关键词检测
dangerous_keywords = [
    "rm", "sudo", "chmod", "dd", ">", "|", ";"
]
```

### 3.3 HelloAgents - 最优雅的架构

**亮点**:
1. **ToolFilter 机制**: 控制子代理可访问的工具
2. **ReadOnlyFilter**: 只读代理只能用只读工具
3. **FullAccessFilter**: 实现代理可以用大部分工具
4. **@tool_action 装饰器**: 自动生成子工具

```python
# HelloAgents ToolFilter 机制
class ReadOnlyFilter(ToolFilter):
    READONLY_TOOLS = {
        "Read", "LS", "Glob", "Grep", "Skill"
    }

    def is_allowed(self, tool_name: str) -> bool:
        return tool_name in self.READONLY_TOOLS

# 子代理运行时应用过滤器
agent.run_as_subagent(tool_filter=ReadOnlyFilter())
```

## 4. 推荐方案

### 4.1 混合架构

结合 OpenCode 的多层防护 + Hello-Agents 的严格白名单 + HelloAgents 的 ToolFilter 机制:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    mini-coder 命令执行安全架构                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        CommandTool                                   │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                     │   │
│  │  ┌─────────────┐                                                    │   │
│  │  │ Layer 1     │ ← 黑名单检查 (OpenCode)                           │   │
│  │  │ 黑名单      │   curl, wget, rm -rf, sudo, dd                    │   │
│  │  └──────┬──────┘                                                    │   │
│  │         │ 拒绝                                                      │   │
│  │         ▼ 通过                                                      │   │
│  │  ┌─────────────┐                                                    │   │
│  │  │ Layer 2     │ ← 白名单免审 (OpenCode + Hello-Agents)             │   │
│  │  │ 安全命令    │   ls, pwd, cat, git status, pytest                 │   │
│  │  └──────┬──────┘                                                    │   │
│  │         │ 免审执行                                                  │   │
│  │         ▼ 需要确认                                                  │   │
│  │  ┌─────────────┐                                                    │   │
│  │  │ Layer 3     │ ← 权限请求 (OpenCode)                              │   │
│  │  │ 权限确认    │   用户确认 / 缓存授权 / 自动批准                    │   │
│  │  └──────┬──────┘                                                    │   │
│  │         │ 批准                                                      │   │
│  │         ▼                                                           │   │
│  │  ┌─────────────┐                                                    │   │
│  │  │ Layer 4     │ ← 执行 (Aider + OpenCode)                          │   │
│  │  │ 安全执行    │   超时控制、输出截断、shellQuote                    │   │
│  │  └─────────────┘                                                    │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     ToolFilter 机制 (HelloAgents)                    │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                     │   │
│  │  ReadOnlyFilter:  explore/plan 代理只能用只读工具                   │   │
│  │  FullAccessFilter: code 代理可以用大部分工具                        │   │
│  │  CustomFilter: 用户自定义过滤规则                                    │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 安全层级详解

#### Layer 1: 黑名单 (Banned Commands)

```python
BANNED_COMMANDS = frozenset([
    # 网络工具
    "curl", "wget", "nc", "telnet", "aria2c",
    # 危险删除
    "rm -rf", "rm -r", "rmdir",
    # 权限提升
    "sudo", "su", "doas",
    # 磁盘操作
    "dd", "mkfs", "fdisk", "format",
    # 权限修改
    "chmod", "chown",
    # 系统控制
    "shutdown", "reboot", "halt", "init",
])
```

#### Layer 2: 白名单 (Safe Commands - 无需确认)

```python
SAFE_READ_ONLY = frozenset([
    # 文件系统查看
    "ls", "pwd", "echo", "whoami", "date", "uname",
    "cat", "head", "tail", "less", "more", "wc",
    "find", "which", "whereis", "file", "stat",
    "du", "df", "tree",

    # Git 只读
    "git status", "git log", "git diff", "git show",
    "git branch", "git tag", "git remote", "git ls-files",

    # 开发工具
    "python --version", "node --version", "go version",
    "pytest --collect-only", "pip list", "npm list",
])

SAFE_WRITE_PROJECT = frozenset([
    # 项目内操作 (需要工作目录限制)
    "mkdir", "touch", "cp", "mv",  # 仅限项目目录内
    "git add", "git commit", "git checkout",
    "pytest", "python -m", "npm run", "go test",
])
```

#### Layer 3: 权限系统

```python
class PermissionService:
    """权限管理服务"""

    def request(self, command: str, context: dict) -> bool:
        """请求执行权限"""
        # 1. 检查缓存授权
        if self._is_cached(command, context):
            return True

        # 2. 检查自动批准会话
        if self._is_auto_approve_session(context["session_id"]):
            return True

        # 3. 请求用户确认 (通过 TUI 或 API)
        return self._request_user_confirmation(command, context)

    def grant_persistent(self, command: str, context: dict):
        """持久授权 (记住选择)"""
        self._cache[command] = context

    def auto_approve_session(self, session_id: str):
        """自动批准会话 (信任模式)"""
        self._auto_sessions.add(session_id)
```

#### Layer 4: 安全执行

```python
class SafeExecutor:
    """安全命令执行器"""

    TIMEOUT_DEFAULT = 120  # 2 分钟
    TIMEOUT_MAX = 600      # 10 分钟
    OUTPUT_MAX = 30000     # 30KB

    def execute(
        self,
        command: str,
        timeout: int = TIMEOUT_DEFAULT,
        cwd: str | None = None,
    ) -> CommandResult:
        """安全执行命令"""

        # 1. Shell 引号转义 (OpenCode)
        safe_command = self._shell_quote(command)

        # 2. 工作目录限制
        if cwd and not self._is_safe_path(cwd):
            raise SecurityError(f"Unsafe working directory: {cwd}")

        # 3. 超时控制
        timeout = min(timeout, self.TIMEOUT_MAX)

        # 4. 执行并捕获输出
        result = subprocess.run(
            safe_command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )

        # 5. 输出截断
        stdout = self._truncate(result.stdout)
        stderr = self._truncate(result.stderr)

        return CommandResult(
            success=result.returncode == 0,
            stdout=stdout,
            stderr=stderr,
            exit_code=result.returncode,
        )

    def _shell_quote(self, command: str) -> str:
        """安全转义 shell 命令 (OpenCode)"""
        return "'" + command.replace("'", "'\\''") + "'"

    def _truncate(self, output: str) -> str:
        """截断过长输出 (OpenCode)"""
        if len(output) <= self.OUTPUT_MAX:
            return output
        half = self.OUTPUT_MAX // 2
        return (
            output[:half] +
            f"\n\n... [{len(output) - self.OUTPUT_MAX} chars truncated] ...\n\n" +
            output[-half:]
        )

    def _is_safe_path(self, path: str) -> bool:
        """检查路径安全性 (Hello-Agents)"""
        # 不允许绝对路径访问系统目录
        dangerous = ["/etc", "/bin", "/usr", "/var", "/sys", "/proc"]
        return not any(path.startswith(d) for d in dangerous)
```

### 4.3 ToolFilter 机制

```python
from abc import ABC, abstractmethod
from typing import Set

class ToolFilter(ABC):
    """工具过滤器基类 (HelloAgents)"""

    @abstractmethod
    def is_allowed(self, tool_name: str) -> bool:
        """检查工具是否允许使用"""
        pass

    def filter(self, all_tools: list[str]) -> list[str]:
        """过滤工具列表"""
        return [t for t in all_tools if self.is_allowed(t)]


class ReadOnlyFilter(ToolFilter):
    """只读工具过滤器 - 用于 explore/plan 代理"""

    ALLOWED: Set[str] = {
        "Read", "LS", "Glob", "Grep",
        "Skill", "NoteRead", "NoteSearch",
        # CommandTool 只读命令
        "Command_ls", "Command_cat", "Command_git_status",
    }

    def is_allowed(self, tool_name: str) -> bool:
        return tool_name in self.ALLOWED


class FullAccessFilter(ToolFilter):
    """完全访问过滤器 - 用于 code 代理"""

    DENIED: Set[str] = {
        "Command_sudo", "Command_rm_rf", "Command_dd",
        # 危险命令工具
    }

    def is_allowed(self, tool_name: str) -> bool:
        return tool_name not in self.DENIED


class StrictFilter(ToolFilter):
    """严格过滤器 - 只有白名单命令"""

    ALLOWED: Set[str] = {
        "Read", "Write", "Edit",
        "Command_ls", "Command_pwd", "Command_cat",
        "Command_git_status", "Command_pytest",
    }

    def is_allowed(self, tool_name: str) -> bool:
        return tool_name in self.ALLOWED
```

## 5. 安全模式

| 模式 | 描述 | 适用场景 |
|------|------|----------|
| `strict` | 只有白名单命令，其他全部拒绝 | 生产环境、不受信任的代码 |
| `normal` | 黑名单 + 白名单免审 + 权限确认 | 开发环境 (默认) |
| `trust` | 只有黑名单检查，其他直接执行 | 完全信任的自动化场景 |

```python
class SecurityMode(str, Enum):
    STRICT = "strict"   # 只有白名单
    NORMAL = "normal"   # 黑名单 + 确认
    TRUST = "trust"     # 只有黑名单
```

## 6. 配置文件

```yaml
# config/tools.yaml

command:
  # 安全模式: strict, normal, trust
  security_mode: normal

  # 超时设置 (秒)
  timeout:
    default: 120
    max: 600

  # 输出限制
  max_output_length: 30000

  # 持久 Shell (OpenCode)
  persistent_shell: true

  # 工作目录限制
  allowed_paths:
    - ${PROJECT_ROOT}
    - /tmp

  # 自定义黑名单 (追加)
  banned_commands:
    - my_dangerous_command

  # 自定义白名单 (追加)
  safe_commands:
    - my_safe_command

  # 权限缓存
  permission_cache:
    enabled: true
    ttl: 3600  # 1 小时
```

## 7. 实施计划

### Phase 1: 基础安全 (2-3 天)
- [ ] 创建 `CommandTool` 基础类
- [ ] 实现黑名单检查
- [ ] 实现白名单免审
- [ ] 基本的 subprocess 执行
- [ ] 超时控制

### Phase 2: 权限系统 (2-3 天)
- [ ] 实现 `PermissionService`
- [ ] TUI 确认对话框
- [ ] 权限缓存和持久化
- [ ] 自动批准会话

### Phase 3: ToolFilter 机制 (2-3 天)
- [ ] 实现 `ToolFilter` 基类
- [ ] `ReadOnlyFilter` 和 `FullAccessFilter`
- [ ] 与子代理系统集成
- [ ] 配置文件支持

### Phase 4: 高级功能 (2-3 天)
- [ ] 持久化 Shell 会话 (可选)
- [ ] 输出截断
- [ ] 工作目录限制
- [ ] 路径安全检查

### Phase 5: 集成测试 (1-2 天)
- [ ] 与 LLMService 集成
- [ ] 安全测试用例
- [ ] 文档完善

## 8. 参考资源

### 知识库文件
- `knowledge-base/aider/aider/run_cmd.py` - Aider 命令执行
- `knowledge-base/opencode/internal/llm/tools/bash.go` - OpenCode Bash 工具
- `knowledge-base/opencode/internal/permission/permission.go` - OpenCode 权限系统
- `knowledge-base/opencode/internal/llm/tools/shell/shell.go` - OpenCode 持久 Shell
- `knowledge-base/hello-agents/code/chapter16/.../terminal_tool.py` - Hello-Agents 终端工具
- `knowledge-base/helloagents/hello_agents/tools/tool_filter.py` - HelloAgents 工具过滤器
- `knowledge-base/helloagents/hello_agents/tools/base.py` - HelloAgents 工具基类

### 关键代码片段

#### OpenCode 黑名单
```go
var bannedCommands = []string{
    "alias", "curl", "curlie", "wget", "axel", "aria2c",
    "nc", "telnet", "lynx", "w3m", "links", "httpie", "xh",
    "http-prompt", "chrome", "firefox", "safari",
}
```

#### OpenCode 白名单
```go
var safeReadOnlyCommands = []string{
    "ls", "echo", "pwd", "date", "cal", "uptime", "whoami", "id", "groups",
    "git status", "git log", "git diff", "git show", "git branch",
    "go version", "go test", "go build", "go run",
}
```

#### Hello-Agents 路径检查
```python
def _is_dangerous_path(self, path):
    dangerous_patterns = ["../", "..\\", "~/", "/etc", "/bin", "/usr", "/var", "/sys"]
    for pattern in dangerous_patterns:
        if pattern in path:
            return True
    return False
```

#### HelloAgents ToolFilter
```python
class ReadOnlyFilter(ToolFilter):
    READONLY_TOOLS: Set[str] = {
        "Read", "ReadTool",
        "LS", "LSTool",
        "Glob", "GlobTool",
        "Grep", "GrepTool",
        "Skill", "SkillTool",
    }
```
