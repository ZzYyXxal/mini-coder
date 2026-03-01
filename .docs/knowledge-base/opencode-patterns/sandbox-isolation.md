---
title: OpenCode 沙箱隔离策略
language: python
pattern_type: sandbox_isolation
tags: [security, isolation, environment, opencode]
last_updated: 2024-01-15
source: opencode
author: based on anomalyco/opencode
---

# OpenCode 沙箱隔离策略

## 概述

OpenCode 的沙箱隔离策略是确保 AI Agent 代码在安全、隔离的环境中执行的关键设计。沙箱隔离防止 Agent 代码影响宿主系统，同时限制其访问系统资源。

## 核心概念

### 1. 进程隔离

使用独立的进程或线程运行 Agent 代码，防止共享内存状态污染。

**实现示例**：
```python
import subprocess
import threading
from typing import Dict, Any

class SandboxIsolation:
    """基于进程的沙箱隔离实现。"""

    def run_agent_code(
        self,
        code: str,
        input_data: Dict[str, Any],
        timeout: int = 30
    ) -> Dict[str, Any]:
        """在隔离进程中运行 Agent 代码。"""
        try:
            # 使用 subprocess 在新进程中执行代码
            result = subprocess.run(
                [sys.executable, "-c", code],
                input=str(input_data),
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd="/tmp/sandbox"  # 限制在临时目录
            )
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Execution timeout after {timeout}s",
                "output": None
            }
```

**使用场景**：
```python
# 使用示例
isolation = SandboxIsolation()

agent_code = """
def process_user_data(user_input: dict) -> dict:
    # Agent 处理逻辑
    return {"result": "processed", "data": user_input}
"""

input_data = {"name": "Alice", "age": 30}

result = isolation.run_agent_code(agent_code, input_data)
if result["success"]:
    print(f"Agent output: {result['output']}")
else:
    print(f"Agent failed: {result['error']}")
```

### 2. 文件系统隔离

限制 Agent 代码只能访问特定的、隔离的文件系统区域。

**实现示例**：
```python
import os
from pathlib import Path
from typing import Set

class FileSandbox:
    """文件系统沙箱隔离。"""

    def __init__(self, allowed_dirs: Set[str], allowed_extensions: Set[str]):
        self.allowed_dirs = allowed_dirs
        self.allowed_extensions = allowed_extensions

    def is_allowed_path(self, path: str) -> bool:
        """检查路径是否在允许的目录中。"""
        path_obj = Path(path)
        # 解析并检查每个路径组件
        for part in path_obj.parts:
            if str(part) not in self.allowed_dirs:
                return False
        return path_obj.suffix in self.allowed_extensions

    def safe_read_file(self, filepath: str) -> str:
        """安全地读取文件，验证路径。"""
        if not self.is_allowed_path(filepath):
            raise PermissionError(
                f"Access denied: {filepath} is not in allowed paths"
            )
        return Path(filepath).read_text()

# 使用示例
sandbox = FileSandbox(
    allowed_dirs={"/tmp/data", "/tmp/config"},
    allowed_extensions={".txt", ".json", ".csv"}
)

# 允许的访问
data = sandbox.safe_read_file("/tmp/data/users.json")  # ✅ 允许
config = sandbox.safe_read_file("/tmp/config/settings.json")  # ✅ 允许

# 不允许的访问
system_file = sandbox.safe_read_file("/etc/passwd")  # ❌ 拒绝
```

**目录结构建议**：
```
/tmp/sandbox/
├── data/           # 允许：只读数据文件
├── config/         # 允许：配置文件
├── output/          # 允许：Agent 输出
└── temp/           # 允许：临时文件
```

### 3. 环境变量隔离

使用隔离的环境变量，防止 Agent 代码访问系统配置。

**实现示例**：
```python
import os
from typing import Dict

class EnvIsolation:
    """环境变量隔离。"""

    ISOLATED_VARS = {
        "PATH": "/usr/local/bin:/tmp/sandbox/bin",
        "PYTHONPATH": "/usr/lib/python3:/tmp/sandbox/lib",
        "HOME": "/tmp/sandbox/home",
        "TEMP": "/tmp/sandbox/temp"
    }

    @classmethod
    def get_isolated_env(cls) -> Dict[str, str]:
        """获取隔离的环境变量。"""
        return cls.ISOLATED_VARS.copy()

    @classmethod
    def run_in_isolated_env(cls, command: str) -> Dict[str, Any]:
        """在隔离环境中运行命令。"""
        env = cls.get_isolated_env()
        env_str = " ".join([f"{k}={v}" for k, v in env.items()])
        full_command = f"{env_str} {command}"
        result = os.system(full_command)
        return {"success": result == 0, "command": full_command}

# 使用示例
env = EnvIsolation()

# 检查 Agent 代码中的路径是否越界
agent_code = """
import os
with open(os.getenv("HOME", "/home") + "/.env", "w") as f:
    f.write("data=secret")
"""

# 在隔离环境中运行
env.run_in_isolated_env("python agent_script.py")
```

### 4. 资源限制

限制 CPU、内存、磁盘 I/O 和网络访问，防止 Agent 消耗过多系统资源。

**实现示例**：
```python
import resource
import time
from typing import Dict

class ResourceLimiter:
    """资源限制器。"""

    def __init__(self, max_memory_mb: int = 100, max_time_seconds: int = 30):
        self.max_memory_mb = max_memory_mb
        self.max_time_seconds = max_time_seconds

    def set_limits(self):
        """设置资源限制。"""
        # 内存限制（Linux/macOS）
        resource.setrlimit(
            resource.RLIMIT_AS,
            (self.max_memory_mb * 1024 * 1024, self.max_memory_mb * 1024 * 1024)
        )

    def run_with_timeout(self, func, *args, **kwargs):
        """在限制下运行函数。"""
        import signal

        def timeout_handler(signum, frame):
            raise TimeoutError(f"Function exceeded {self.max_time_seconds}s timeout")

        signal.signal(signal.SIGALRM, timeout_handler)
        self.set_limits()
        signal.alarm(self.max_time_seconds)
        try:
            result = func(*args, **kwargs)
            signal.alarm(0)  # 取消超时
            return result
        except TimeoutError as e:
            return {"error": str(e), "timeout": True}
        finally:
            signal.alarm(0)

# 使用示例
limiter = ResourceLimiter(max_memory_mb=50, max_time_seconds=10)

def long_running_task():
    time.sleep(15)  # 超时

result = limiter.run_with_timeout(long_running_task)
if result.get("timeout"):
    print(f"Task was terminated due to timeout")
else:
    print(f"Task completed: {result}")
```

### 5. 网络访问控制

限制或完全禁用网络访问，防止 Agent 代码进行未授权的外部通信。

**实现示例**：
```python
import socket
from typing import List

class NetworkRestriction:
    """网络访问限制。"""

    BLOCKED_HOSTS = ["example.com", "malicious.com"]
    ALLOWED_PORTS = []

    def check_network_access(self, host: str, port: int) -> bool:
        """检查网络访问是否被允许。"""
        if host in self.BLOCKED_HOSTS:
            return False
        if self.ALLOWED_PORTS and port not in self.ALLOWED_PORTS:
            return False
        return True

    @classmethod
    def patch_socket(cls):
        """修补 socket 模块以限制网络访问。"""
        original_connect = socket.socket.connect

        def restricted_connect(self, *args, **kwargs):
            # 检查连接参数
            if len(args) >= 2:
                host, port = args[0], args[1]
                if not cls.check_network_access(host, port):
                    raise PermissionError(f"Network access to {host}:{port} is blocked")
            return original_connect(self, *args, **kwargs)

        socket.socket.connect = restricted_connect

# 在加载 Agent 代码前应用补丁
NetworkRestriction.patch_socket()
```

### 6. 完整的沙箱管理器

结合所有隔离策略的完整沙箱管理器。

```python
import os
import subprocess
from pathlib import Path
from typing import Dict, Any, List

class SandboxManager:
    """完整的沙箱管理器，结合所有隔离策略。"""

    def __init__(self, sandbox_dir: str = "/tmp/sandbox"):
        self.sandbox_dir = Path(sandbox_dir)
        self.setup_sandbox()

    def setup_sandbox(self):
        """初始化沙箱目录结构。"""
        # 创建沙箱目录
        (self.sandbox_dir / "data").mkdir(parents=True, exist_ok=True)
        (self.sandbox_dir / "config").mkdir(parents=True, exist_ok=True)
        (self.sandbox_dir / "output").mkdir(parents=True, exist_ok=True)
        (self.sandbox_dir / "temp").mkdir(parents=True, exist_ok=True)

    def prepare_agent_environment(self, code: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """准备并运行 Agent 代码。"""
        # 1. 将代码写入临时文件
        agent_file = self.sandbox_dir / "agent_code.py"
        agent_file.write_text(code)

        # 2. 准备输入文件
        input_file = self.sandbox_dir / "input.json"
        import json
        input_file.write_text(json.dumps(input_data))

        # 3. 执行命令
        cmd = [
            "python", str(agent_file),
            "--input", str(input_file),
            "--output", str(self.sandbox_dir / "output/result.json")
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(self.sandbox_dir),
                timeout=30,
                # 设置环境变量隔离
                env={
                    "PATH": "/usr/local/bin",
                    "PYTHONPATH": "/usr/lib/python3",
                    "HOME": str(self.sandbox_dir),
                    "TEMP": str(self.sandbox_dir / "temp")
                }
            )
            return self._parse_result(result)
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Execution timeout", "output": None}

    def _parse_result(self, result: subprocess.CompletedProcess) -> Dict[str, Any]:
        """解析命令执行结果。"""
        output = None
        if result.returncode == 0:
            # 读取输出文件
            result_file = self.sandbox_dir / "output/result.json"
            if result_file.exists():
                import json
                output = json.loads(result_file.read_text())
        return {
            "success": result.returncode == 0,
            "output": output,
            "returncode": result.returncode
        }

    def cleanup(self):
        """清理沙箱目录。"""
        import shutil
        if self.sandbox_dir.exists():
            shutil.rmtree(self.sandbox_dir)

# 使用示例
manager = SandboxManager()

# Agent 代码示例
agent_code = """
import sys
import json

def main():
    input_file = sys.argv[1]
    with open(input_file) as f:
        data = json.load(f)
    print(f"Processing: {data}")
    result = {"processed": True, "data": data}
    with open("output.json", "w") as f:
        json.dump(result, f)

if __name__ == "__main__":
    main()
"""

# 运行 Agent
result = manager.prepare_agent_environment(
    code=agent_code,
    input_data={"task": "test", "data": {"key": "value"}}
)

print(f"Agent execution result: {result}")
```

## 最佳实践建议

### 1. 多层防御

- 永远采用"默认拒绝"原则，只明确允许的操作
- 对所有用户输入进行严格验证
- 使用白名单而非黑名单

### 2. 监控和日志

```python
import logging
from typing import Dict, Any

class SandboxMonitor:
    """沙箱监控和日志。"""

    def __init__(self, log_file: str = "/tmp/sandbox.log"):
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def log_agent_action(self, action: str, details: Dict[str, Any]):
        """记录 Agent 操作。"""
        self.logger.info(f"Action: {action}")
        for key, value in details.items():
            self.logger.debug(f"  {key}: {value}")

    def detect_anomalies(self, output: Dict[str, Any]) -> List[str]:
        """检测异常行为。"""
        anomalies = []
        # 检测异常长的输出
        if "output" in output and len(str(output["output"])) > 10000:
            anomalies.append("Unusually long output detected")
        # 检测异常的文件访问
        if "files_accessed" in output:
            suspicious_files = output["files_accessed"]
            if len(suspicious_files) > 10:
                anomalies.append("Excessive file access detected")
        return anomalies

# 使用示例
monitor = SandboxMonitor()

# 监控 Agent 操作
monitor.log_agent_action(
    action="read_file",
    details={"file": "/tmp/data/users.json", "size": "1.2MB"}
)

# 检测异常
output = {
    "files_accessed": ["/etc/passwd", "/home/.ssh"],
    "output": "Malicious code generated"
}
anomalies = monitor.detect_anomalies(output)
if anomalies:
    print(f"Anomalies detected: {anomalies}")
```

### 3. 定期清理

```python
import shutil
import time
from pathlib import Path

class SandboxCleaner:
    """定期清理沙箱资源。"""

    def __init__(self, sandbox_dir: str = "/tmp/sandbox"):
        self.sandbox_dir = Path(sandbox_dir)
        self.max_age_seconds = 3600  # 1 小时

    def clean_old_files(self):
        """清理过期的临时文件。"""
        import os
        current_time = time.time()

        for temp_dir in [self.sandbox_dir / "temp", self.sandbox_dir / "output"]:
            if temp_dir.exists():
                for file in temp_dir.iterdir():
                    file_path = temp_dir / file
                    if file.is_file():
                        file_age = current_time - file.stat().st_mtime
                        if file_age > self.max_age_seconds:
                            os.remove(file_path)
                            print(f"Removed old file: {file}")

    def cleanup_all(self):
        """完全清理沙箱。"""
        if self.sandbox_dir.exists():
            shutil.rmtree(self.sandbox_dir)
            print(f"Cleaned up sandbox directory: {self.sandbox_dir}")

# 使用示例
cleaner = SandboxCleaner()

# 定期清理
cleaner.clean_old_files()

# 完全清理（在 Agent 执行后）
# cleaner.cleanup_all()
```

## 与 mini-coder 的集成

### 在 Planner 中的应用

当 Planner 规划需要沙箱隔离的功能时：

1. **识别隔离需求**：
   - 功能是否需要执行用户代码？
   - 是否需要访问敏感文件？
   - 是否需要网络访问？

2. **选择隔离级别**：
   ```markdown
   | 隔离级别 | 描述 | 适用场景 |
   |---------|------|---------|
   | 进程隔离 | 独立进程运行 | 通用 Agent 代码 |
   | 文件隔离 | 限制特定目录访问 | 需要文件访问 |
   | 完整沙箱 | 所有隔离策略 | 敏感操作 |
   ```

3. **生成实施计划**：
   在 implementation_plan.md 中包含沙箱配置步骤

### 在 Implementer 中的应用

Implementer 实现需要沙箱隔离的功能时：

1. **遵循隔离规范**：
   - 不使用绝对路径访问系统文件
   - 只使用 `data/` 和 `config/` 目录
   - 避免使用 `import os` 等系统级操作

2. **使用沙箱工具类**：
   - 对于简单隔离：使用 `FileSandbox`
   - 对于复杂隔离：使用 `SandboxManager`

3. **资源感知实现**：
   - 避免长运行操作
   - 及时释放资源

### 在 Tester 中的应用

Tester 验证沙箱隔离的实现：

1. **隔离测试**：
   - 测试 Agent 代码在沙箱中运行
   - 验证无法访问受限资源

2. **渗透测试（如适用）**：
   - 尝试绕过沙箱限制
   - 验证防御措施有效

## 安全注意事项

### 常见攻击向量

1. **路径遍历攻击**
   - 验证所有文件路径
   - 不允许 `../` 路径

2. **代码注入攻击**
   - 对用户输入进行严格验证
   - 不使用 `eval()` 或 `exec()` 处理不可信输入

3. **资源耗尽攻击**
   - 限制 CPU 和内存使用
   - 实现超时机制

4. **侧信道攻击**
   - 不允许 Agent 访问敏感文件
   - 限制信息泄露

### 应急响应

如果发现 Agent 表现异常或疑似恶意行为：

1. 立即停止执行
2. 记录详细日志
3. 隔离受影响的资源
4. 通知系统管理员
5. 进行安全审计

## 总结

OpenCode 的沙箱隔离策略提供了多层防御来安全地运行 AI Agent 代码：

- ✅ **进程隔离** - 在独立进程中运行
- ✅ **文件系统隔离** - 限制特定目录访问
- ✅ **环境变量隔离** - 使用隔离的环境
- ✅ **资源限制** - 限制 CPU、内存、I/O
- ✅ **网络访问控制** - 阻止或限制外部通信
- ✅ **监控和日志** - 记录所有操作
- ✅ **定期清理** - 清理临时资源

在实现 mini-coder 的相关功能时，应该考虑采用这些隔离策略来增强安全性。
