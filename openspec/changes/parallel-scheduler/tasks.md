# Tasks: Parallel Scheduler System

## 1. Core Implementation

- [x] 1.1 实现 `ParallelScheduler` 类
  - Agent 级 Semaphore 并发控制
  - `schedule_agent_single()` 单任务执行
  - `schedule_agent_batch()` 批量并行执行
  - 任务超时和取消机制
  - Agent 类型推断

- [x] 1.2 实现 `ToolScheduler` 类
  - DAG 依赖图构建
  - 拓扑排序生成执行批次
  - Placeholder 参数解析
  - 同层并行执行
  - LLM 响应解析

- [x] 1.3 扩展 Mailbox Schema
  - `ParallelTaskGroup` 数据结构
  - `ParallelResultGroup` 数据结构
  - `ToolCall` 和 `ToolCallResult` 数据结构
  - `ToolBatchRequest` 和 `ToolBatchResult` 数据结构
  - `MailboxMessage` 批量消息工厂方法

- [x] 1.4 集成 Orchestrator
  - `dispatch_async()` 异步单任务派发
  - `dispatch_parallel_async()` 异步并行派发
  - `get_scheduler_status()` 调度器状态查询

- [x] 1.5 更新 `__init__.py` 导出

## 2. Testing

- [x] 2.1 实现 `tests/agents/test_scheduler.py`
  - Semaphore 并发控制测试
  - 单任务执行测试
  - 批量执行测试
  - 超时测试
  - 取消测试

- [x] 2.2 实现 `tests/agents/test_parallel_workflow.py`
  - Orchestrator 并行派发测试
  - Tool 并行执行测试
  - DAG 依赖执行测试
  - 部分成功场景测试
  - 完整工作流集成测试

- [ ] 2.3 实现 `tests/tools/test_tool_scheduler.py`
  - DAG 构建测试
  - Placeholder 解析测试
  - LLM 响应解析测试

## 3. Documentation

- [x] 3.1 更新 `CLAUDE.md` 并行执行架构说明
- [ ] 3.2 更新 `docs/agent-mailbox-schema.md` 批量协议文档
- [ ] 3.3 添加使用示例到代码注释

## 4. Quality Assurance

- [ ] 4.1 运行 `pytest tests/agents/` 确保测试通过
- [ ] 4.2 运行 `mypy src/mini_coder/agents/` 类型检查
- [ ] 4.3 运行 `flake8 src/mini_coder/agents/` 代码风格检查