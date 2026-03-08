# Tasks: LangGraph 重构

## Phase 1: 基础设施 (Week 1-2) ✅

### 1.1 依赖安装 [Day 1-2] ✅
- [x] 更新 pyproject.toml 添加 LangGraph 依赖
- [x] 验证安装成功

### 1.2 目录结构 [Day 3] ✅
- [x] 创建 graph/ 目录
- [x] 创建 tracing/ 目录

### 1.3 状态定义 (TDD) [Day 4-5] ✅
- [x] 编写 state.py 测试用例
- [x] 实现 CodingAgentState 类型
- [x] 实现 AgentMessage 类型
- [x] mypy 类型检查通过

---

## Phase 2: 图构建 (Week 2-3) ✅

### 2.1 节点函数 (TDD) [Day 6-10] ✅
- [x] 测试: router_node
- [x] 测试: explorer_node
- [x] 测试: planner_node
- [x] 测试: coder_node
- [x] 测试: reviewer_node
- [x] 测试: bash_node
- [x] 实现各节点函数

### 2.2 边与路由 (TDD) [Day 11-12] ✅
- [x] 测试: route_by_intent
- [x] 测试: check_review_result
- [x] 测试: check_test_result
- [x] 实现路由函数

### 2.3 图构建器 (TDD) [Day 13-14] ✅
- [x] 测试: 图编译
- [x] 测试: 简单流程执行
- [x] 实现 CodingAgentGraphBuilder

---

## Phase 3: 工具迁移 (Week 3-4) ✅

### 3.1 工具包装 (TDD) [Day 15-18] ✅
- [x] 测试: read_file tool
- [x] 测试: write_file tool
- [x] 测试: edit_file tool
- [x] 测试: glob_files tool
- [x] 测试: grep_files tool
- [x] 测试: execute_command tool
- [x] 实现 LangChain Tool 包装

### 3.2 ToolScheduler 适配 (TDD) [Day 19-21] ✅
- [x] 测试: execute_single_tool
- [x] 测试: execute_parallel_tools
- [x] 测试: execute_dag_tools
- [x] 实现 LangChainToolScheduler

---

## Phase 4: Agent 角色 (Week 4-5) ✅

### 4.1 角色定义 [Day 22-25] ✅
- [x] 测试: AgentRole 类型
- [x] 实现 roles.py

### 4.2 提示词整合 [Day 26-28] ✅
- [x] 测试: 提示词加载
- [x] 实现 prompts.py

---

## Phase 5: TUI 集成 (Week 5-6) ✅

### 5.1 图运行器 (TDD) [Day 29-31] ✅
- [x] 测试: GraphRunner.run()
- [x] 测试: GraphRunner.stream()
- [x] 实现 graph_runner.py

### 5.2 TUI 适配 [Day 32-35] ✅
- [x] 测试: console_app 集成
- [x] 适配 TUI 调用

---

## Phase 6: 测试验证 (Week 6-7) ✅

### 6.1 单元测试 [Day 36-40] ✅
- [x] 覆盖率 > 80% (graph模块)

### 6.2 集成测试 [Day 41-45] ✅
- [x] 端到端流程测试

---

## Phase 7: 清理发布 (Week 7) ✅

### 7.1 删除废弃代码 [Day 46-48]
- [ ] 删除 orchestrator.py (保留，仍有TUI依赖)
- [ ] 删除 scheduler.py (保留，仍有依赖)
- [ ] 删除 llm/providers/ (已移除)

### 7.2 文档更新 [Day 49-50] ✅
- [x] 更新 CLAUDE.md
- [x] 更新 README.md

### 7.3 发布 [Day 51-52] ✅
- [x] 版本更新到 v0.2.0