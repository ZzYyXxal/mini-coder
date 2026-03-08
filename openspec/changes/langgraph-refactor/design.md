# Design: LangGraph + LangSmith 重构

## 架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           TUI Layer (保留)                               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      LangGraph Orchestration Layer                       │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                        StateGraph                                  │  │
│  │  ┌────────┐    ┌────────┐    ┌────────┐    ┌────────┐            │  │
│  │  │ router │───▶│explorer│───▶│planner │───▶│ coder  │            │  │
│  │  └────────┘    └────────┘    └────────┘    └────────┘            │  │
│  │       │                                         │                  │  │
│  │       └────────▶│reviewer│───▶│  bash  │◀──────┘                  │  │
│  │                 └────────┘    └────────┘                          │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      LangSmith Observability Layer                       │
└─────────────────────────────────────────────────────────────────────────┘
```

## 状态定义

```python
class CodingAgentState(TypedDict):
    messages: Annotated[list, add_messages]
    user_request: str
    current_stage: str
    agent_messages: List[AgentMessage]  # 保留定向投递
    exploration_result: Optional[str]
    implementation_plan: Optional[str]
    code_changes: List[Dict[str, str]]
    review_result: Optional[Dict[str, Any]]
    test_result: Optional[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]  # 支持 DAG
    errors: List[str]
    retry_count: int
```

## 关键决策

### 1. Mailbox 简化而非删除
- 保留 `AgentMessage` 类型（`to_agent`, `from_agent`）
- 删除 `TaskBrief`, `SubagentResult`（映射到 State 字段）
- 原因：LangGraph 无定向投递概念

### 2. ToolScheduler 保留
- DAG 依赖（`depends_on`）无 LangGraph 对应
- Placeholder 解析（`{{call_id.output}}`）无替代
- 在节点内部调用 ToolScheduler

### 3. TDD 开发模式
- 每个模块先写测试
- 最小实现使测试通过
- 增量重构