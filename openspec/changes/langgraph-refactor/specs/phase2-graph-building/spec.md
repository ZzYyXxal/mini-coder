# Spec: Phase 2 - 图构建

## 目标

构建 LangGraph 工作流图，实现各 Agent 节点和路由逻辑。

## 任务清单

### 2.1 节点函数 (TDD)
- 测试: router_node
- 测试: explorer_node
- 测试: planner_node
- 测试: coder_node
- 测试: reviewer_node
- 测试: bash_node
- 实现各节点函数

### 2.2 边与路由 (TDD)
- 测试: route_by_intent
- 测试: check_review_result
- 测试: check_test_result
- 实现路由函数

### 2.3 图构建器 (TDD)
- 测试: 图编译
- 测试: 简单流程执行
- 实现 CodingAgentGraphBuilder

## 验收标准

- [ ] 所有节点函数测试通过
- [ ] 路由函数测试通过
- [ ] 图编译成功
- [ ] mypy 类型检查通过