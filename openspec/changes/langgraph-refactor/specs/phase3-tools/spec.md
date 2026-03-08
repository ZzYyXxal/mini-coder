# Spec: Phase 3 - 工具迁移

## 目标

将现有工具包装为 LangChain Tool，适配 ToolScheduler 支持 DAG 依赖。

## 任务清单

### 3.1 文件工具 (TDD)
- 测试: read_file tool
- 测试: write_file tool
- 测试: edit_file tool
- 实现 LangChain Tool 包装

### 3.2 搜索工具 (TDD)
- 测试: glob tool
- 测试: grep tool
- 实现搜索工具包装

### 3.3 命令工具 (TDD)
- 测试: execute_command tool
- 测试: 安全检查
- 实现命令工具包装

### 3.4 ToolScheduler 适配 (TDD)
- 测试: LangChain Tool DAG 执行
- 实现 LangChainToolScheduler

## 验收标准

- [ ] 所有工具测试通过
- [ ] 安全检查测试通过
- [ ] DAG 执行测试通过
- [ ] mypy 类型检查通过