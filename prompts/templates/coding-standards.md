# Coding Standards Template
# Template for injecting into Agent prompts

## Python Coding Standards

### 1. Type Hints

All functions must have complete type annotations (Python 3.10+ syntax):

```python
def calculate_total(items: list[Item], tax_rate: float) -> float:
    """Calculate total amount."""
    pass

def process_data(data: dict[str, Any]) -> list[str]:
    """Process data."""
    pass
```

### 2. Docstrings

All public APIs use Google-style docstrings:

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

### 3. Naming Conventions

- Functions/variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_CASE`
- Private members: `_prefix`

### 4. Code Style

- Indentation: 4 spaces
- Line limit: 79 characters
- Blank lines:
  - Between functions: 2 lines
  - Logical sections within functions: 1 line

### 5. Error Handling

- Explicitly handle boundary conditions
- Use specific exception types
- Provide meaningful error messages

### 6. Testing Standards

- TDD: Tests first
- Test coverage: >= 80%
- Test files: `tests/test_*.py`
- Use pytest framework

### 7. Project Structure

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