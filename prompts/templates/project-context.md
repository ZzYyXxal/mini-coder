# Project Context Template
# 项目上下文模板 - 用于注入到 Agent 提示词中

## 项目信息

- **项目名称**: mini-coder
- **项目描述**: 一个自定义的多 Agent 编码助手项目
- **技术栈**: Python 3.10+, pytest, mypy, pydantic, chromadb, langgraph

## 核心原则

1. **TDD (Test-Driven Development)**: 红→绿→重构循环
2. **严格类型提示**: PEP 484，完整的函数签名
3. **PEP 8 合规**: 代码风格检查强制
4. **Token 优化**: 优先定向编辑而非全文件重写
5. **Google 风格文档字符串**: 所有公共函数和类

## 架构概览

### 子代理系统

| 代理 | 职责 | 工具范围 |
|------|------|----------|
| Explorer | 只读代码库搜索 | Read, Grep, Glob |
| Planner | 需求分析与任务规划 | Read, Grep, WebSearch |
| Coder | 代码生成与编辑 | Read, Write, Edit, Bash(受限) |
| Reviewer | 代码质量评审 | Read, Grep, Glob |
| Bash | 终端执行与测试验证 | Read, Bash(受限) |

### 工作流

```
需求 → Explorer(探索) → Planner(规划) → Coder(实现) → Reviewer(评审) → Bash(测试验证)
```

## 重要文件路径

- 主入口：`src/mini_coder/agents/orchestrator.py`
- Agent 定义：`src/mini_coder/agents/base.py`
- 工具过滤器：`src/mini_coder/tools/filter.py`
- 提示词模板：`prompts/system/*.md`

## 测试命令

```bash
# 运行所有测试
pytest tests/ -v

# 类型检查
mypy src/ --strict

# 代码风格
flake8 src/

# 覆盖率检查
pytest tests/ --cov=src --cov-fail-under=80
```
