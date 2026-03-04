# Spec: ToolFilter

## Overview

工具过滤器机制，用于控制子代理可以访问的工具集合。灵感来自 HelloAgents。

## Interface

```python
class ToolFilter(ABC):
    """工具过滤器基类"""

    @abstractmethod
    def is_allowed(self, tool_name: str) -> bool:
        """检查工具是否允许使用"""
        pass

    def filter(self, all_tools: list[str]) -> list[str]:
        """过滤工具列表"""
        return [t for t in all_tools if self.is_allowed(t)]
```

## Built-in Filters

### ReadOnlyFilter

用于 explore/plan 等只读代理。

```python
class ReadOnlyFilter(ToolFilter):
    ALLOWED: Set[str] = {
        # 文件读取
        "Read", "ReadTool",
        # 目录浏览
        "LS", "LSTool", "Glob", "GlobTool",
        # 搜索
        "Grep", "GrepTool",
        # 笔记
        "NoteRead", "NoteSearch",
        # Command 只读
        "Command_ls", "Command_pwd", "Command_cat",
        "Command_git_status", "Command_git_log",
    }
```

### FullAccessFilter

用于 code 代理，排除危险工具。

```python
class FullAccessFilter(ToolFilter):
    DENIED: Set[str] = {
        "Command_sudo",
        "Command_rm_rf",
        "Command_dd",
        "Command_format",
    }
```

### CustomFilter

用户自定义过滤器。

```python
class CustomFilter(ToolFilter):
    def __init__(
        self,
        allowed: Optional[Set[str]] = None,
        denied: Optional[Set[str]] = None,
        mode: str = "whitelist"  # or "blacklist"
    ): ...
```

## Usage

```python
# 创建只读子代理
explore_agent = Agent(
    name="explore",
    tools=ReadOnlyFilter().filter(all_tools)
)

# 创建完全访问子代理
code_agent = Agent(
    name="code",
    tools=FullAccessFilter().filter(all_tools)
)
```

## Dependencies

None
