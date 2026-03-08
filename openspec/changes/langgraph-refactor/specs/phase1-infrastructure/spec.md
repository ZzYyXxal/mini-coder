# Spec: Phase 1 - 基础设施迁移

## 目标

搭建 LangGraph + LangSmith 开发环境，定义核心状态类型。

## 任务清单

### 1.1 依赖安装 ✅
- 更新 `pyproject.toml`
- 验证安装

### 1.2 目录结构 ✅
- 创建 `graph/` 目录
- 创建 `tracing/` 目录

### 1.3 状态定义 (TDD) ✅
- 编写测试 `tests/graph/test_state.py`
- 实现 `graph/state.py`

## TDD 流程

```
1. 编写测试用例 (Red)
2. 运行测试确认失败
3. 实现最小代码 (Green)
4. 运行测试确认通过
5. 重构优化 (Refactor)
```

## 验收标准

- [x] `pip install -e ".[langgraph]"` 成功
- [x] `import langgraph` 无错误
- [x] 状态类型测试通过 (19 tests)
- [x] mypy 类型检查通过