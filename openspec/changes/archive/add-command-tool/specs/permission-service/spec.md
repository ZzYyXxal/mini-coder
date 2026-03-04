# Spec: PermissionService

## Overview

权限服务管理命令执行的授权机制，支持会话级权限缓存和自动批准。

## Interface

```python
class PermissionService:
    def __init__(self, on_request_callback: Optional[Callable] = None): ...

    def request(self, session_id: str, command: str) -> bool:
        """请求执行权限，返回是否批准"""

    def grant(self, request_id: str, session_id: str, command: str) -> None:
        """授予权限"""

    def grant_persistent(self, session_id: str, command: str) -> None:
        """持久授予权限 (会话内缓存)"""

    def auto_approve_session(self, session_id: str) -> None:
        """设置会话为自动批准模式"""

    def revoke(self, session_id: str, command: str) -> None:
        """撤销权限"""
```

## PermissionRequest

```python
@dataclass
class PermissionRequest:
    id: str           # 请求 ID
    session_id: str   # 会话 ID
    command: str      # 请求的命令
    description: str  # 请求描述
    timestamp: float  # 请求时间戳
```

## Permission Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                      Permission Request Flow                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. CommandTool.execute()                                        │
│         │                                                        │
│         ▼                                                        │
│  2. Check: Is command in SAFE_READ_ONLY?                        │
│         │ Yes → Execute directly                                 │
│         │ No → Continue                                          │
│         ▼                                                        │
│  3. Check: Is session auto-approved?                            │
│         │ Yes → Execute directly                                 │
│         │ No → Continue                                          │
│         ▼                                                        │
│  4. Check: Is command in granted permissions?                   │
│         │ Yes → Execute directly                                 │
│         │ No → Continue                                          │
│         ▼                                                        │
│  5. Create PermissionRequest                                     │
│         │                                                        │
│         ▼                                                        │
│  6. Call on_request_callback(request)                           │
│         │                                                        │
│         ▼                                                        │
│  7. Wait for user response                                       │
│         │                                                        │
│         ├─────▶ Approved → Grant → Execute                      │
│         │                                                        │
│         └─────▶ Denied → Return error                           │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## Configuration

```yaml
# config/tools.yaml

permission:
  cache_enabled: true
  cache_ttl: 3600  # 1 hour
  auto_approve_sessions: []
  request_timeout: 30  # seconds
```

## Callback Interface

```python
# TUI 回调示例
def on_permission_request(request: PermissionRequest) -> bool:
    """显示确认对话框，返回用户选择"""
    # 显示命令和描述
    # 等待用户选择：允许/拒绝/总是允许
    return user_approved
```

## Dependencies

None
