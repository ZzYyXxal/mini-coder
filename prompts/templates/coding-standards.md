# Coding Standards Template
# 项目编码规范模板 - 用于注入到 Agent 提示词中

## Python 编码规范

### 1. 类型提示 (Type Hints)

所有函数必须有完整的类型注解（Python 3.10+ 语法）：

```python
def calculate_total(items: list[Item], tax_rate: float) -> float:
    """计算总金额"""
    pass

def process_data(data: dict[str, Any]) -> list[str]:
    """处理数据"""
    pass
```

### 2. 文档字符串 (Docstrings)

所有公共 API 使用 Google 风格 docstrings：

```python
def process_data(data: dict) -> list:
    """Process input data and return results.

    Args:
        data: Input data dictionary.

    Returns:
        Processed results list.

    Raises:
        ValueError: If input data is invalid.
    """
```

### 3. 命名规范 (Naming)

- 函数/变量：`snake_case`
- 类：`PascalCase`
- 常量：`UPPER_CASE`
- 私有成员：`_prefix`

### 4. 代码风格 (Code Style)

- 缩进：4 空格
- 行限制：79 字符
- 空行：
  - 函数间：2 行
  - 函数内逻辑段落：1 行

### 5. 错误处理 (Error Handling)

- 明确处理边界条件
- 使用具体的异常类型
- 提供有意义的错误信息

### 6. 测试规范 (Testing)

- TDD：测试优先
- 测试覆盖率：>= 80%
- 测试文件：`tests/test_*.py`
- 使用 pytest 框架

### 7. 项目结构 (Project Structure)

```
project/
├── src/
│   └── project_name/
│       ├── __init__.py
│       ├── module1.py
│       └── module2.py
├── tests/
│   ├── __init__.py
│   ├── test_module1.py
│   └── test_module2.py
├── config/
└── prompts/
```
