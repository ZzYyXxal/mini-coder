# Proposal: LangGraph + LangSmith 重构

## 概述

将 mini-coder 项目迁移至 LangGraph + LangSmith 架构，专注于多 Agent 协作逻辑，将底层基础设施（状态机、工具调用、并行调度）迁移至成熟框架。

## 动机

| 痛点 | 解决方案 |
|------|----------|
| 自实现状态机 (55KB+) | LangGraph StateGraph |
| 手动并行调度 | LangGraph 内置并行 |
| 无可观测性 | LangSmith 全链路追踪 |
| LLM Provider 手动封装 | LangChain ChatModel |

## 范围

### 删除 (~100KB)
- `agents/orchestrator.py` - 被 StateGraph 替代
- `agents/scheduler.py` - 被内置并行替代
- `llm/providers/*.py` - 被 LangChain 替代

### 保留并适配 (~40KB)
- `agents/mailbox.py` - 保留 AgentMessage（定向投递）
- `agents/tool_scheduler.py` - 保留 DAG 依赖逻辑
- `agents/base.py` - 保留配置类型

### 新增 (~23KB)
- `graph/` - LangGraph 状态图定义
- `tracing/` - LangSmith 追踪集成
- `tools/mcp_adapter.py` - MCP 工具适配

## 开发模式

**TDD（测试驱动开发）**：
1. 先写测试用例
2. 实现最小代码使测试通过
3. 重构优化

## 风险

| 风险 | 缓解措施 |
|------|----------|
| DAG 功能无原生支持 | 保留 ToolScheduler |
| 定向投递无对应 | 保留 AgentMessage |