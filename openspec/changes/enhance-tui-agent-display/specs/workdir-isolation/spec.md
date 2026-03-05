# Spec: Working Directory Isolation

## Requirement

实现工作目录隔离机制，确保 mini-coder 只能访问指定的工作目录，防止修改自身代码或访问敏感文件。

## Functional Requirements

### FR1: Working Directory Selection

启动时选择工作目录。

**Behavior:**
- 如果 `config/workdir.yaml` 中配置了 `default_path`，使用该路径
- 如果 `remember_last` 为 true 且有上次记录，使用该路径
- 如果 `always_ask` 为 true，启动时总是询问
- 用户可以通过命令行参数 `--workdir` 指定

### FR2: Access Control

限制 Agent 只能访问工作目录内的文件。

**Allowed Operations:**
- 读取工作目录内的文件
- 写入工作目录内的文件
- 执行工作目录内的命令

**Denied Operations:**
- 访问工作目录的父目录（`../`）
- 访问系统目录（`/etc/`, `/usr/`, etc.）
- 访问敏感文件（`.env`, `credentials*`, `*.key`, etc.）

### FR3: WorkDir Filter

实现工具级别的访问控制过滤器。

**Filter Behavior:**
- 检查文件路径是否在工作目录内
- 检查路径是否匹配 denied patterns
- 拒绝访问工作目录外的路径

### FR4: WorkDir Display

在 TUI 中显示当前工作目录。

**Display:**
```
Work Dir: ~/projects/my-app
```

## Non-Functional Requirements

### NFR1: Security

访问控制必须可靠，不能被绕过。

### NFR2: Usability

用户应该能够方便地配置工作目录。

### NFR3: Compatibility

不应该破坏现有的文件操作功能。

## Configuration

**config/workdir.yaml:**
```yaml
working_directory:
  default_path: ""
  remember_last: true
  always_ask: false

access_control:
  allowed_patterns:
    - "**/*"
  denied_patterns:
    - "../**"
    - "/etc/**"
    - "/usr/**"
    - "/bin/**"
    - "/sbin/**"
    - "**/.env"
    - "**/credentials*"
    - "**/*.key"
    - "**/.ssh/**"
```

## Implementation Details

### WorkDirFilter Class

```python
class WorkDirFilter(ToolFilter):
    """工作目录访问控制过滤器"""

    def __init__(self, workdir: Path, config: dict):
        self.workdir = workdir.resolve()
        self.denied_patterns = config.get('denied_patterns', [])

    def is_path_allowed(self, path: Path) -> bool:
        """检查路径是否允许访问"""
        path = path.resolve()

        # 必须在工作目录内
        try:
            path.relative_to(self.workdir)
        except ValueError:
            return False

        # 不能匹配 denied patterns
        for pattern in self.denied_patterns:
            if path.match(pattern):
                return False

        return True
```

## Acceptance Criteria

- [ ] 启动时正确选择工作目录
- [ ] 工作目录显示在 TUI header
- [ ] 拒绝访问工作目录外的路径
- [ ] 拒绝访问敏感文件
- [ ] 工作目录内的操作正常

## Security Considerations

1. **Path Traversal** - 必须解析 `..` 和符号链接
2. **Race Conditions** - 检查和访问之间不能有竞争条件
3. **Default Deny** - 默认拒绝，显式允许

## Open Questions

1. 是否需要白名单模式（只允许特定文件）？
2. 是否需要日志记录被拒绝的访问尝试？
