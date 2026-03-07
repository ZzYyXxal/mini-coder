# Proposal: Parallel Scheduler System

## Why

当前系统缺少并行执行能力，子代理只能顺序执行，Tool 调用也是串行执行，导致任务执行效率低下。需要实现 Agent 级和 Tool 级的并行调度系统，提升整体执行效率。

## What Changes

- 新增 `ParallelScheduler` 统一管理 Agent 级并发
- 新增 `ToolScheduler` 管理 Agent 内部 Tool 并发
- 扩展 Mailbox Schema 支持并行任务派发和结果收集
- Orchestrator 集成异步派发方法
- BaseEnhancedAgent 支持异步执行和 Mailbox 协议

## Capabilities

### New Capabilities

- `parallel-agent-dispatch`: 并行派发多个子代理任务，支持并发控制和失败策略
- `parallel-tool-execution`: Agent 内部并行调用多个 Tool，支持 DAG 依赖
- `mailbox-batch-protocol`: 批量任务派发和结果收集的结构化消息协议

### Modified Capabilities

- `orchestrator-dispatch`: 扩展支持异步派发方法 `dispatch_async()`, `dispatch_parallel_async()`
- `agent-execution`: 扩展支持异步执行 `execute_async()` 和 Mailbox 协议入口 `execute_from_mailbox()`

## Impact

- `src/mini_coder/agents/mailbox.py`: 新增并行 Schema 数据结构
- `src/mini_coder/agents/scheduler.py`: 新增 ParallelScheduler 类
- `src/mini_coder/agents/tool_scheduler.py`: 新增 ToolScheduler 类
- `src/mini_coder/agents/orchestrator.py`: 集成异步派发方法
- `src/mini_coder/agents/enhanced.py`: 扩展异步执行支持
- `tests/agents/test_scheduler.py`: 新增单元测试
- `tests/agents/test_parallel_workflow.py`: 新增集成测试