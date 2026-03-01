---
title: Pydantic 数据验证模式
language: python
pattern_type: data_validation
tags: [pydantic, validation, typing, data_model]
last_updated: 2024-01-15
source: custom
author: based on Pydantic v2 best practices
---

# Pydantic 数据验证模式

## 概述

Pydantic v2 是 Python 生态中最流行的数据验证库，提供了强大的运行时类型检查、数据解析和模型定义。本文档总结了 Pydantic v2 的核心用法和最佳实践。

## 核心特性

### 1. 类型验证

```python
from pydantic import BaseModel, EmailStr, Field, field_validator

class User(BaseModel):
    """用户数据模型，带有 Pydantic v2 验证。"""

    name: str
    age: int = Field(ge=0, description="用户年龄")
    email: EmailStr
    bio: str | None = None

    @field_validator('name')
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        """验证用户名不能为空。"""
        if not v or v.strip() == "":
            raise ValueError("name cannot be empty")
        return v

# 验证示例
try:
    user = User(
        name="",  # 会触发验证错误
        age=25,
        email="user@example.com"
    )
except ValueError as e:
    print(f"Validation error: {e}")
```

### 2. 字段验证器

Pydantic v2 的验证器比 v1 更强大，支持更多的验证场景。

**类型检查验证器**：
```python
from pydantic import BaseModel, field_validator, ValidationInfo

class Product(BaseModel):
    """产品模型，带有类型检查。"""

    price: float
    quantity: int
    discount_rate: float

    @field_validator('price', 'quantity', 'discount_rate')
    @classmethod
    def price_and_quantity_must_be_positive(cls, v):
        """确保价格和数量为正数。"""
        if v.price <= 0:
            raise ValueError("price must be positive")
        if v.quantity <= 0:
            raise ValueError("quantity must be positive")
        return v

    @field_validator('discount_rate')
    @classmethod
    def discount_rate_must_be_valid_range(cls, v):
        """确保折扣率在 0-1 范围内。"""
        if not 0 <= v.discount_rate <= 1:
            raise ValueError("discount_rate must be between 0 and 1")
        return v

    def calculate_total(self) -> float:
        """计算折后总价。"""
        return self.price * self.quantity * (1 - self.discount_rate)
```

**自定义验证错误消息**：
```python
from pydantic import BaseModel, ValidationError

class User(BaseModel):
    name: str

    class Config:
        # 自定义错误消息
        json_schema_extra = {"example": "Custom error message"}

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if len(v) < 2:
            raise ValueError("name must be at least 2 characters long")
        return v

try:
    user = User(name="A")  # 会触发自定义错误
except ValidationError as e:
    print(e.json())
    # 输出: {"type": "value_error", "loc": ["name"], "msg": "name must be at least 2 characters long"}
```

### 3. 嵌套模型

Pydantic 支持复杂的嵌套模型结构。

```python
from pydantic import BaseModel, EmailStr, HttpUrl
from typing import List, Optional

class Address(BaseModel):
    """地址模型。"""
    street: str
    city: str
    zip_code: str = Field(min_length=5, max_length=10)
    country: str = "US"

class User(BaseModel):
    """用户模型，包含嵌套地址。"""

    name: str
    email: EmailStr
    phone: str | None = None
    address: Address
    website: HttpUrl | None = None
    preferences: dict[str, str] = {}

class UserList(BaseModel):
    """用户列表模型。"""

    users: List[User]
    total: int
    page: int = Field(ge=1)

# 使用示例
user = User(
    name="John Doe",
    email="john@example.com",
    address=Address(
        street="123 Main St",
        city="Springfield",
        zip_code="01101"
    )
)
print(user.model_dump_json(indent=2))
```

### 4. 数据验证与解析

```python
from pydantic import BaseModel, validator

class UserData(BaseModel):
    """带有自定义验证器的用户数据。"""

    username: str
    password: str

    @validator('password')
    @classmethod
    def password_must_be_strong(cls, v):
        """验证密码强度。"""
        if len(v) < 8:
            raise ValueError("password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("password must contain at least one digit")
        return v

# JSON 数据解析
import json

json_data = '{"username": "test", "password": "weak123"}'

try:
    user = UserData.model_validate_json(json_data)
    print(f"Valid user: {user}")
except ValidationError as e:
    print(f"Validation failed: {e}")
```

### 5. 配置选项

```python
from pydantic import BaseModel, ConfigDict

class Settings(BaseModel):
    """带有配置选项的模型。"""

    debug: bool = False
    max_retries: int = 3
    timeout: int = 30

    class Config:
        # 验证赋值时自动转换类型
        validate_assignment = True
        # 禁止额外字段
        extra = "forbid"
        # 允许字段别名
        allow_population_by_field_name = True

settings = Settings(
    debug=True,
    max_retries=5  # 会被拒绝（默认值是3）
    timeout=60  # 会被拒绝（默认值是30）
)
# ValueError: max_retries must be <= 3

try:
    settings = Settings(debug=True)
    print(f"Valid settings: {settings}")
except ValidationError as e:
    print(f"Validation failed: {e}")
```

### 6. 序列化与 JSON 支持

```python
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime

class Event(BaseModel):
    """事件模型，自动支持序列化。"""

    id: str
    name: str
    timestamp: datetime
    data: Dict[str, Any]

# 自动序列化
event = Event(
    id="evt-001",
    name="User Login",
    timestamp=datetime.now(),
    data={"user_id": 123, "ip": "192.168.1.1"}
)

# 输出为 JSON
print(event.model_dump_json(indent=2))

# 输出为字典
print(event.model_dump())

# 输出为 Pydantic JSON 格式
import pydantic.json
print(pydantic.to_json(event))
```

### 7. 使用与 FastAPI 集成

```python
from fastapi import FastAPI
from fastapi import HTTPException
from pydantic import BaseModel

app = FastAPI()

class User(BaseModel):
    name: str
    age: int

@app.post("/users/")
async def create_user(user: User) -> User:
    """使用 Pydantic 模型的 API 端点。"""
    return user

@app.get("/users/{user_id}")
async def get_user(user_id: int) -> User:
    """获取用户的 API 端点。"""
    # 模拟数据库查询
    if user_id == 999:
        raise HTTPException(status_code=404, detail="User not found")

    # 返回模拟数据
    return User(name="John", age=30)

# 使用 Pydantic 的验证
from pydantic import BaseModel, Field

class CreateUser(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    email: str
    age: int = Field(ge=18, description="User must be 18 years or older")

@app.post("/users/")
async def create_user(user: CreateUser) -> User:
    """创建用户，自动进行验证。"""
    return user
```

## 最佳实践

### 1. 验证策略

**分层验证**：
- 在字段级进行基本验证（如 `min_length`, `max_length`）
- 使用 `@field_validator` 进行跨字段验证
- 使用 `@model_validator` 进行整个模型验证

**错误处理**：
```python
try:
    user = User(name="", age=25)  # 无效的名称
except ValidationError as e:
    # 获取所有错误
    errors = e.errors()

    # 格式化错误消息
    error_messages = []
    for error in errors:
        location = ".".join(str(loc) for loc in error["loc"])
        message = error["msg"]
        error_messages.append(f"{location}: {message}")

    # 返回用户友好的错误
    print(f"Validation failed:\n{chr(10).join(error_messages)}")
```

### 2. 性能优化

**延迟验证**：
```python
from pydantic import BaseModel, FieldValidator, field_validator

class LazyValidationModel(BaseModel):
    """支持延迟验证的模型。"""

    name: str
    _validated: bool = False

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """延迟验证器。"""
        cls._validated = True  # 标记为已验证
        return v

# 使用场景：先创建对象（不验证），稍后验证
user = LazyValidationModel(name="John")  # 不触发验证

# 在需要验证时手动调用
user_dict = user.model_dump()
validated_user = LazyValidationModel.model_validate(user_dict)
```

**使用 Pydantic 的 JSON 序列化**：
- 比内置的 `json.dumps()` 快速得多
- 使用 `model.model_dump_json()` 获取 JSON

```python
import time
from pydantic import BaseModel

class Item(BaseModel):
    name: str
    price: float

data = [Item(f"item-{i}", i * 1.99) for i in range(1000)]

# 比较序列化性能
start = time.time()
json_output = [item.model_dump() for item in data]
json.dumps(json_output)  # 内置方法
json_time = time.time() - start

start = time.time()
pydantic_output = [item.model_dump_json() for item in data]
"[json.dumps(item) for item in pydantic_output]"
pydantic_time = time.time() - start

print(f"JSON dumps: {json_time:.4f}s")
print(f"Pydantic JSON: {pydantic_time:.4f}s")
print(f"Pydantic is {json_time/pydantic_time:.2f}x faster")
```

### 3. 高级用法

**根验证器**：
```python
from pydantic import BaseModel, RootValidator, field_validator

class Container(BaseModel):
    """带有根验证器的容器模型。"""

    items: list[str]

    @root_validator('items')
    @classmethod
    def items_must_not_be_empty(cls, v):
        """根验证器：确保列表不为空。"""
        if len(v) == 0:
            raise ValueError("items cannot be empty")
        return v

# 测试
container = Container(items=["item1", "item2"])  # ✅ 有效
try:
    empty_container = Container(items=[])  # ❌ 会触发验证错误
except ValueError as e:
    print(f"Validation failed: {e}")
```

**模型继承与组合**：
```python
from pydantic import BaseModel
from typing import List

class Person(BaseModel):
    name: str
    age: int

class Employee(Person):
    """员工模型，继承自 Person。"""
    employee_id: str
    department: str
    salary: float

class Company(BaseModel):
    """公司模型，包含员工列表。"""
    name: str
    employees: List[Employee]

# 使用示例
company = Company(
    name="Acme Corp",
    employees=[
        Employee(name="Alice", age=30, employee_id="E001", department="Engineering", salary=80000),
        Employee(name="Bob", age=25, employee_id="E002", department="Sales", salary=75000),
    ]
)

print(company.model_dump_json(indent=2))
```

### 4. 测试策略

**单元测试**：
```python
import pytest
from pydantic import BaseModel, ValidationError

class User(BaseModel):
    name: str
    email: str

def test_valid_user():
    """测试有效用户。"""
    user = User(name="John", email="john@example.com")
    assert user.name == "John"
    assert user.email == "john@example.com"

def test_invalid_email():
    """测试无效邮箱。"""
    with pytest.raises(ValidationError) as exc_info:
        User(name="John", email="invalid-email")

    # 验证错误信息
    assert "email" in str(exc_info.value)

def test_name_too_short():
    """测试名称太短。"""
    with pytest.raises(ValidationError):
        User(name="", email="test@example.com")
```

**Mock 和 Fixtures**：
```python
import pytest
from pydantic import BaseModel
from typing import Generator

@pytest.fixture
def user_data():
    """用户数据 fixture。"""
    return {
        "name": "Test User",
        "email": "test@example.com",
        "age": 30
    }

class User(BaseModel):
    name: str
    email: str
    age: int

def test_with_fixture(user_data):
    """使用 fixture 的测试。"""
    user = User(**user_data)
    assert user.name == "Test User"
```

## 与 mini-coder 的集成建议

### 1. 在 Planner 中的应用

当 Planner 规划数据模型时：

1. **推荐 Pydantic v2**：
   - 提供完整的字段验证
   - 使用类型提示确保类型安全
   - 考虑嵌套模型结构

2. **提供验证模板**：
```python
from pydantic import BaseModel, Field, EmailStr, HttpUrl, validator

class UserCreate(BaseModel):
    """用户创建模型模板。"""

    name: str = Field(min_length=2, max_length=50)
    email: EmailStr
    age: int = Field(ge=18, description="User must be 18 or older")
    phone: str | None = None
    website: HttpUrl | None = None

    @validator('website')
    @classmethod
    def validate_website_if_provided(cls, v):
        """只在提供网站时验证 URL。"""
        if v is not None:
            # 自定义 URL 验证
            from urllib.parse import urlparse
            result = urlparse(v)
            if not all([result.scheme, result.netloc]):
                raise ValueError("Invalid URL format")
        return v
```

### 2. 在 Implementer 中的应用

Implementer 实现数据模型时应遵循：

1. **使用 Pydantic v2** 而非其他库
2. **所有字段都有完整的类型提示**
3. **添加适当的验证器**
4. **处理 ValidationError 异常**
5. **使用 Field 而非默认值来提供更友好的错误消息**

### 3. 在 Tester 中的应用

Tester 验证数据模型时应检查：

1. **所有字段都有类型提示**
2. **验证器正确工作**
3. **嵌套模型结构合理**
4. **配置选项正确设置**
5. **序列化输出正确**

## 迁移指南

### 从 Pydantic v1 迁移到 v2

**主要变更**：

1. **验证器语法**：
   ```python
   # v1 语法
   validator = ["name"]

   # v2 语法（推荐）
   @field_validator("name")
   @classmethod
   def validate_name(cls, v):
       ...
   ```

2. **类型提示变更**：
   ```python
   # v1
   from typing import Optional
   email: Optional[str] = None

   # v2（推荐）
   email: str | None = None
   ```

3. **错误处理**：
   ```python
   # v1
   try:
       user = User.parse_obj(data)
   except ValidationError as e:
       print(f"Validation failed: {e}")

   # v2（推荐）
   try:
       user = User.model_validate(data)
   except ValidationError as e:
       # e.json() 提供结构化错误
       # e.errors() 提供详细错误列表
       for error in e.errors():
           print(f"Error in {error['loc']}: {error['msg']}")
   ```

4. **配置选项**：
   ```python
   # v1
   class Config:
       use_enum_values = True

   # v2
   class Config:
       validate_assignment = True
       extra = "forbid"
   ```

## 总结

Pydantic v2 是构建类型安全、可验证的 Python 应用的理想选择。通过合理使用其特性，可以：

- ✅ 在运行时捕获类型错误
- ✅ 提供清晰、用户友好的验证错误
- ✅ 支持复杂的嵌套模型结构
- ✅ 集成良好与现代 Python 生态（如 FastAPI）
- ✅ 提供高性能的序列化选项

在开发 mini-coder 时，建议将 Pydantic v2 作为数据验证的首选方案。
