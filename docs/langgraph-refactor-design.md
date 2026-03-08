# Mini-Coder LangGraph + LangSmith 重构设计文档

> **版本**: 1.0
> **创建日期**: 2026-03-07
> **目标**: 将项目迁移至 LangGraph + LangSmith 架构，专注于多 Agent 协作

---

## 1. 执行摘要

### 1.1 重构动机

当前项目自实现了完整的工具系统、调度器和状态机。为了更好地专注于多 Agent 协作逻辑，将底层基础设施迁移至成熟的框架：

| 痛点 | LangGraph/LangSmith 解决方案 |
|------|------------------------------|
| 自实现状态机 (orchestrator.py 55KB+) | LangGraph 图引擎原生支持 |
| 手动并行调度 (scheduler.py) | LangGraph 内置并行执行 |
| 无可观测性 | LangSmith 全链路追踪 |
| 自实现工具调用循环 | LangGraph 工具节点自动循环 |
| LLM Provider 手动封装 | LangChain 集成多 Provider |

### 1.2 重构范围

```
┌─────────────────────────────────────────────────────────────────────┐
│                         重构范围总览                                  │
├─────────────────────────────────────────────────────────────────────┤
│  保留层 (业务逻辑)                                                    │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                   │
│  │  Agent 协作  │ │  记忆系统   │ │  TUI 界面   │                   │
│  │  定义与逻辑  │ │  (memory/) │ │   (tui/)    │                   │
│  └─────────────┘ └─────────────┘ └─────────────┘                   │
├─────────────────────────────────────────────────────────────────────┤
│  替换层 (基础设施)                                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              LangGraph + LangSmith                           │   │
│  │  - 状态图 (StateGraph)    - 工具节点 (ToolNode)              │   │
│  │  - 并行执行              - 追踪与监控                        │   │
│  └─────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│  新增层 (MCP 集成)                                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              LangGraph MCP Adapter                           │   │
│  │  - MCP 工具自动发现    - MCP 协议适配                         │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. 现有架构分析

### 2.1 当前代码结构

```
src/mini_coder/
├── agents/              # ~150KB, 核心 Agent 系统
│   ├── orchestrator.py  # 55KB - 状态机 + 工作流协调
│   ├── base.py          # 30KB - Agent 基类
│   ├── enhanced.py      # 53KB - 增强型 Agent 实现
│   ├── scheduler.py     # 15KB - 并行调度器
│   ├── mailbox.py       # 12KB - Agent 间消息协议
│   └── tool_scheduler.py # 8KB - Tool 级并行
├── tools/               # ~50KB, 工具系统
│   ├── base.py          # 基类定义
│   ├── command.py       # 命令执行
│   ├── executor.py      # 安全执行器
│   ├── security.py      # 安全策略
│   ├── permission.py    # 权限服务
│   └── filter.py        # 工具过滤器
├── llm/                 # ~40KB, LLM 服务
│   ├── service.py       # 30KB - 核心服务
│   └── providers/       # 10KB - 各 Provider 实现
├── memory/              # ~35KB, 记忆系统
│   ├── manager.py       # 上下文记忆管理
│   ├── working_memory.py
│   └── persistent_store.py
└── tui/                 # TUI 界面 (保留)
```

### 2.2 功能映射表

| 功能 | 当前实现 | LangGraph 对应 |
|------|----------|---------------|
| 状态机 | `WorkflowOrchestrator` (orchestrator.py) | `StateGraph` |
| Agent 节点 | `BaseAgent`, `BaseEnhancedAgent` | `langgraph.prebuilt.create_react_agent` |
| 工具调用循环 | 手动 `_invoke_llm` + 工具执行 | `ToolNode` 自动处理 |
| 并行调度 | `ParallelScheduler` (scheduler.py) | `StateGraph` + `asyncio.gather` |
| Agent 间通信 | `MailboxMessage`, `Blackboard` | `State` 注入 |
| 工具过滤 | `ToolFilter` 系列 | 工具绑定 + Agent 配置 |
| 追踪日志 | `logging` + 自定义 | LangSmith Tracing |

---

## 3. 目标架构设计

### 3.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           TUI Layer (保留)                               │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  console_app.py  │  app.py  │  llm_chat.py  │  rendering.py      │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Agent Collaboration Layer (新增)                    │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                      Agent Definitions                             │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐     │  │
│  │  │Explorer │ │ Planner │ │  Coder  │ │Reviewer │ │  Bash   │     │  │
│  │  │ (只读)  │ │ (规划)  │ │ (实现)  │ │ (评审)  │ │ (测试)  │     │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘     │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                   Collaboration Patterns                           │  │
│  │  - Sequential: Explorer → Planner → Coder → Reviewer → Bash       │  │
│  │  - Parallel: 多 Agent 并发探索/实现                                │  │
│  │  - Conditional: 基于评审结果分支                                   │  │
│  └───────────────────────────────────────────────────────────────────┘  │
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
│  │       │         ┌────────┐    ┌────────┐       │                  │  │
│  │       └────────▶│reviewer│───▶│  bash  │◀──────┘                  │  │
│  │                 └────────┘    └────────┘                          │  │
│  │                      │                                              │  │
│  │                      ▼                                              │  │
│  │               ┌────────────┐                                       │  │
│  │               │  complete  │                                       │  │
│  │               └────────────┘                                       │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                  Tool Integration                                  │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │  │
│  │  │  Read/Write  │  │   Command    │  │  MCP Tools   │            │  │
│  │  │   Tools      │  │    Tool      │  │  (Auto-discovery)│         │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘            │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      LangSmith Observability Layer                       │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  - Trace: 完整请求链路追踪                                         │  │
│  │  - Metrics: Token 使用、延迟、成功率                               │  │
│  │  - Feedback: 质量评估与反馈收集                                    │  │
│  │  - Datasets: 测试数据集管理                                        │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 核心模块设计

#### 3.2.1 状态定义

```python
from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph

class AgentState(TypedDict):
    """LangGraph 状态定义 - 替代 Blackboard"""
    # 任务相关
    task_id: str
    user_request: str
    current_stage: str  # pending, exploring, planning, coding, reviewing, testing, completed

    # 共享上下文
    exploration_result: Optional[str]
    implementation_plan: Optional[str]
    code_changes: List[Dict[str, str]]  # [{file, content, action}]
    review_result: Optional[Dict[str, Any]]

    # 工件存储
    artifacts: Dict[str, Any]

    # 错误与重试
    errors: List[str]
    retry_count: int
    max_retries: int

    # 元数据
    session_id: str
    metadata: Dict[str, Any]
```

#### 3.2.2 图定义

```python
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, AIMessage

def build_coding_agent_graph():
    """构建主工作流图"""

    # 创建状态图
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("router", router_node)        # 意图路由
    graph.add_node("explorer", explorer_node)    # 代码探索
    graph.add_node("planner", planner_node)      # 规划分析
    graph.add_node("coder", coder_node)          # 代码实现
    graph.add_node("reviewer", reviewer_node)    # 代码评审
    graph.add_node("bash", bash_node)            # 测试验证
    graph.add_node("complete", complete_node)    # 完成处理

    # 定义边
    graph.set_entry_point("router")

    # 条件路由
    graph.add_conditional_edges(
        "router",
        route_by_intent,
        {
            "explore": "explorer",
            "plan": "planner",
            "code": "coder",
            "simple": "coder",  # 简单任务直接编码
        }
    )

    # 标准流程
    graph.add_edge("explorer", "planner")
    graph.add_edge("planner", "coder")
    graph.add_edge("coder", "reviewer")

    # 评审分支
    graph.add_conditional_edges(
        "reviewer",
        check_review_result,
        {
            "pass": "bash",
            "reject": "coder",  # 打回修改
            "max_retry": "complete"  # 达到最大重试
        }
    )

    # 测试分支
    graph.add_conditional_edges(
        "bash",
        check_test_result,
        {
            "pass": "complete",
            "fail": "coder"  # 测试失败重新实现
        }
    )

    graph.add_edge("complete", END)

    return graph.compile()
```

#### 3.2.3 Agent 节点实现

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage

async def explorer_node(state: AgentState) -> dict:
    """Explorer 节点 - 只读代码库探索"""

    # 获取只读工具
    tools = get_readonly_tools()  # Read, Glob, Grep

    # 创建 Agent
    agent = create_react_agent(
        model=get_model("haiku"),  # 使用快速模型
        tools=tools,
        state_modifier=explorer_prompt,
    )

    # 执行
    result = await agent.ainvoke({
        "messages": [HumanMessage(content=state["user_request"])]
    })

    return {
        "exploration_result": result["messages"][-1].content,
        "current_stage": "explored",
    }

async def planner_node(state: AgentState) -> dict:
    """Planner 节点 - 需求分析与任务规划"""

    tools = get_planner_tools()  # Read, Grep, WebSearch

    agent = create_react_agent(
        model=get_model("sonnet"),
        tools=tools,
        state_modifier=planner_prompt,
    )

    context = f"""
    用户请求: {state['user_request']}
    探索结果: {state.get('exploration_result', '无')}
    """

    result = await agent.ainvoke({
        "messages": [HumanMessage(content=context)]
    })

    return {
        "implementation_plan": result["messages"][-1].content,
        "current_stage": "planned",
    }
```

### 3.3 工具集成设计

#### 3.3.1 现有工具适配

```python
from langchain_core.tools import tool
from mini_coder.tools.executor import SafeExecutor

@tool
def execute_command(command: str, timeout: int = 120) -> str:
    """执行系统命令（带安全检查）"""
    executor = SafeExecutor(timeout=timeout)
    result = executor.execute(command)
    return result.stdout if result.success else f"Error: {result.stderr}"

@tool
def read_file(path: str) -> str:
    """读取文件内容"""
    # 复用现有逻辑
    ...

@tool
def write_file(path: str, content: str) -> str:
    """写入文件"""
    ...
```

#### 3.3.2 MCP 工具集成

```python
from langchain_mcp_adapters import load_mcp_tools

async def load_mcp_tools_from_config():
    """从配置加载 MCP 工具"""
    config = load_config("config/mcp.yaml")

    tools = []
    for server in config["servers"]:
        server_tools = await load_mcp_tools(
            server_name=server["name"],
            command=server["command"],
            args=server.get("args", []),
        )
        tools.extend(server_tools)

    return tools
```

### 3.4 LangSmith 集成

```python
import os
from langsmith import Client

# 配置 LangSmith
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "your-api-key"
os.environ["LANGCHAIN_PROJECT"] = "mini-coder"

# 自定义追踪
from langsmith.run_helpers import traceable

@traceable(name="explorer_search", run_type="tool")
async def explorer_search(query: str, state: AgentState):
    """带追踪的探索搜索"""
    ...

# 反馈收集
client = Client()
def log_feedback(run_id: str, score: float, comment: str = ""):
    client.create_feedback(
        run_id=run_id,
        key="user_rating",
        score=score,
        comment=comment,
    )
```

---

## 4. 删除内容清单

### 4.1 完全删除

| 文件/模块 | 原因 | 代码量 |
|----------|------|--------|
| `agents/orchestrator.py` | 被 LangGraph StateGraph 替代 | ~55KB |
| `agents/scheduler.py` | 被 LangGraph 并行执行替代 | ~15KB |
| `agents/tool_scheduler.py` | 被 LangGraph ToolNode 替代 | ~8KB |
| `llm/providers/*.py` | 被 LangChain ChatModel 替代 | ~10KB |
| `llm/service.py` (部分) | LLM 调用迁移到 LangChain | ~20KB |

**总计删除**: ~108KB 代码

### 4.2 保留并适配

| 文件/模块 | 适配内容 | 原因 |
|----------|----------|------|
| `agents/mailbox.py` | 简化消息类型，保留定向投递 | LangGraph State 无 `to_agent` 概念 |
| `agents/tool_scheduler.py` (部分) | 保留 DAG 并行逻辑 | LangGraph ToolNode 不支持 `depends_on` |

**⚠️ 重要修正：mailbox.py 不能完全删除**

```
┌─────────────────────────────────────────────────────────────────┐
│           mailbox.py 功能保留分析                                │
├─────────────────────────────────────────────────────────────────┤
│  功能                    │ LangGraph 对应        │ 决策        │
├─────────────────────────────────────────────────────────────────┤
│  TaskBrief              │ State 字段            │ 删除        │
│  SubagentResult         │ State 字段            │ 删除        │
│  MailboxMessage         │ State + checkpointer  │ 简化保留    │
│  ParallelTaskGroup      │ 图分支                │ 删除        │
│  ToolBatchRequest (DAG) │ 无对应                │ 保留        │
└─────────────────────────────────────────────────────────────────┘
```

**保留原因**：

1. **定向投递** (`to_agent/from_agent`)
   - LangGraph State 是全局共享的，没有"发给谁"的概念
   - 调试时需要追踪"哪个 Agent 产出了什么"
   - 解决方案：保留简化的 `MailboxMessage` 作为 State 的补充

2. **Tool DAG 并行** (`ToolBatchRequest` + `depends_on`)
   - LangGraph `ToolNode` 不支持工具间的 DAG 依赖
   - 例如：`ToolCall(depends_on=["call_1"])` 必须等 `call_1` 完成后才执行
   - 解决方案：保留 `ToolScheduler` 的 DAG 执行逻辑

### 4.2 大幅简化

| 文件/模块 | 简化内容 | 保留内容 |
|----------|----------|----------|
| `agents/base.py` | 移除工具循环、状态管理 | Agent 配置、结果类型 |
| `agents/enhanced.py` | 移除手动 LLM 调用 | Agent 角色定义、提示词 |
| `tools/base.py` | 移除执行逻辑 | 工具定义接口 |
| `tools/command.py` | 简化为 LangChain Tool | 安全检查逻辑保留 |

### 4.3 删除的类/函数

```python
# 删除的类
- WorkflowOrchestrator      # 被 StateGraph 替代
- ParallelScheduler         # 被内置并行替代
- ToolScheduler            # 被 ToolNode 替代
- MailboxMessage           # 被 State 替代
- TaskBrief                # 被 State 字段替代
- SubagentResult           # 被 State 更新替代
- ParallelTaskGroup        # 被图分支替代
- OpenAICompatibleProvider # 被 LangChain ChatModel 替代

# 删除的函数
- _invoke_llm()            # 被 Agent.ainvoke() 替代
- _invoke_llm_stream()     # 被 Agent.astream() 替代
- _execute_agent_task()    # 被图节点执行替代
- _run_agent()             # 被图编译执行替代
```

---

## 5. 新增内容清单

### 5.1 新增文件结构

```
src/mini_coder/
├── agents/
│   ├── __init__.py           # 导出
│   ├── base.py               # 简化后的 Agent 定义
│   ├── roles.py              # Agent 角色定义 (从 enhanced.py 提取)
│   ├── prompts.py            # Agent 提示词 (从 prompts/ 整合)
│   └── capabilities.py       # Agent 能力定义 (工具过滤等)
├── graph/                    # 新增: LangGraph 图定义
│   ├── __init__.py
│   ├── state.py              # 状态定义
│   ├── nodes.py              # 节点实现
│   ├── edges.py              # 边与路由逻辑
│   ├── builder.py            # 图构建器
│   └── config.py             # 图配置
├── tools/                    # 简化后的工具
│   ├── __init__.py
│   ├── file_tools.py         # 文件工具 (Read, Write, Edit)
│   ├── search_tools.py       # 搜索工具 (Grep, Glob)
│   ├── command_tool.py       # 命令工具 (简化版)
│   └── mcp_adapter.py        # 新增: MCP 适配器
├── tracing/                  # 新增: LangSmith 追踪
│   ├── __init__.py
│   ├── client.py             # LangSmith 客户端
│   ├── decorators.py         # 追踪装饰器
│   └── feedback.py           # 反馈收集
├── memory/                   # 保留并适配
│   ├── state_adapter.py      # 新增: State <-> Memory 适配
│   └── ... (其他保留)
└── tui/                      # 保留
    ├── graph_runner.py       # 新增: 图执行器 (替代 orchestrator 调用)
    └── ... (其他保留)
```

### 5.2 新增依赖

```toml
# pyproject.toml 新增依赖
dependencies = [
    # 现有依赖...
    "numpy>=1.24.0",

    # 新增 LangGraph 生态
    "langgraph>=0.2.0",
    "langchain-core>=0.3.0",
    "langchain-anthropic>=0.3.0",  # Claude 支持
    "langchain-openai>=0.2.0",     # OpenAI 兼容 API
    "langsmith>=0.1.0",            # 追踪与评估

    # MCP 支持 (可选)
    "langchain-mcp-adapters>=0.1.0",
]

[project.optional-dependencies]
# 开发依赖新增
dev = [
    # 现有...
    "pytest>=7.0.0",
    # 新增
    "langgraph-sdk>=0.1.0",  # 本地开发服务器
]
```

### 5.3 新增核心代码

#### 5.3.1 `graph/state.py`

```python
"""LangGraph 状态定义"""
from typing import TypedDict, List, Dict, Any, Optional, Annotated
from langgraph.graph import add_messages

class CodingAgentState(TypedDict):
    """编码 Agent 状态

    替代原有的 Blackboard + Mailbox 系统
    """
    # 消息历史 (自动合并)
    messages: Annotated[list, add_messages]

    # 阶段状态
    current_stage: str
    user_request: str
    task_id: str

    # Agent 结果
    exploration_result: Optional[str]
    implementation_plan: Optional[str]
    code_changes: List[Dict[str, str]]
    review_result: Optional[Dict[str, Any]]
    test_result: Optional[Dict[str, Any]]

    # 工件与错误
    artifacts: Dict[str, Any]
    errors: List[str]
    retry_count: int

    # 元数据
    session_id: str
    project_path: str
```

#### 5.3.2 `graph/nodes.py`

```python
"""LangGraph 节点实现"""
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage

async def router_node(state: CodingAgentState) -> dict:
    """路由节点 - 分析意图决定后续路径"""
    from mini_coder.agents.roles import analyze_intent

    intent = analyze_intent(state["user_request"])

    return {
        "current_stage": "routing",
        "metadata": {"intent": intent},
    }

async def explorer_node(state: CodingAgentState) -> dict:
    """探索节点 - 只读代码库搜索"""
    from mini_coder.tools.search_tools import get_search_tools
    from mini_coder.agents.prompts import EXPLORER_PROMPT

    agent = create_react_agent(
        model=get_model("haiku"),
        tools=get_search_tools(),
        state_modifier=EXPLORER_PROMPT,
    )

    result = await agent.ainvoke({
        "messages": state["messages"] + [
            HumanMessage(content=f"探索任务: {state['user_request']}")
        ]
    })

    return {
        "exploration_result": result["messages"][-1].content,
        "messages": result["messages"],
    }

# ... 其他节点实现
```

#### 5.3.3 `graph/builder.py`

```python
"""图构建器"""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

class CodingAgentGraphBuilder:
    """编码 Agent 图构建器"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.checkpointer = MemorySaver()

    def build(self) -> CompiledGraph:
        """构建完整的编码 Agent 图"""
        graph = StateGraph(CodingAgentState)

        # 添加节点
        graph.add_node("router", router_node)
        graph.add_node("explorer", explorer_node)
        graph.add_node("planner", planner_node)
        graph.add_node("coder", coder_node)
        graph.add_node("reviewer", reviewer_node)
        graph.add_node("bash", bash_node)
        graph.add_node("complete", complete_node)

        # 设置入口
        graph.set_entry_point("router")

        # 添加条件边
        graph.add_conditional_edges("router", self._route_by_intent, {
            "explore": "explorer",
            "plan": "planner",
            "code": "coder",
            "simple": "coder",
        })

        # 标准流程边
        graph.add_edge("explorer", "planner")
        graph.add_edge("planner", "coder")
        graph.add_edge("coder", "reviewer")

        # 评审分支
        graph.add_conditional_edges("reviewer", self._check_review, {
            "pass": "bash",
            "reject": "coder",
            "max_retry": "complete",
        })

        # 测试分支
        graph.add_conditional_edges("bash", self._check_test, {
            "pass": "complete",
            "fail": "coder",
        })

        graph.add_edge("complete", END)

        return graph.compile(checkpointer=self.checkpointer)

    def _route_by_intent(self, state: CodingAgentState) -> str:
        """根据意图路由"""
        ...

    def _check_review(self, state: CodingAgentState) -> str:
        """检查评审结果"""
        ...

    def _check_test(self, state: CodingAgentState) -> str:
        """检查测试结果"""
        ...
```

#### 5.3.4 `tracing/client.py`

```python
"""LangSmith 追踪客户端"""
import os
from langsmith import Client
from langsmith.run_helpers import traceable

class TracingClient:
    """LangSmith 追踪客户端"""

    def __init__(self, project_name: str = "mini-coder"):
        self.client = Client()
        self.project_name = project_name

        # 配置环境
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_PROJECT"] = project_name

    def create_run(self, name: str, run_type: str, inputs: dict):
        """创建追踪运行"""
        return self.client.create_run(
            name=name,
            run_type=run_type,
            inputs=inputs,
        )

    def log_feedback(self, run_id: str, score: float, key: str = "user_rating"):
        """记录反馈"""
        self.client.create_feedback(
            run_id=run_id,
            key=key,
            score=score,
        )

    def get_trace_url(self, run_id: str) -> str:
        """获取追踪 URL"""
        return f"https://smith.langchain.com/o/default/projects/p/{self.project_name}/r/{run_id}"
```

#### 5.3.5 `tools/mcp_adapter.py`

```python
"""MCP 工具适配器"""
from typing import List, Dict, Any
from langchain_core.tools import BaseTool

class MCPToolAdapter:
    """MCP 工具适配器 - 将 MCP 服务器工具转换为 LangChain 工具"""

    def __init__(self, config_path: str = "config/mcp.yaml"):
        self.config_path = config_path
        self._tools: List[BaseTool] = []

    async def load_tools(self) -> List[BaseTool]:
        """加载所有 MCP 工具"""
        import yaml

        with open(self.config_path) as f:
            config = yaml.safe_load(f)

        for server in config.get("servers", []):
            tools = await self._load_server_tools(server)
            self._tools.extend(tools)

        return self._tools

    async def _load_server_tools(self, server_config: Dict[str, Any]) -> List[BaseTool]:
        """加载单个 MCP 服务器的工具"""
        # 使用 langchain-mcp-adapters 加载
        from langchain_mcp_adapters import load_mcp_tools

        return await load_mcp_tools(
            server_name=server_config["name"],
            command=server_config["command"],
            args=server_config.get("args", []),
            env=server_config.get("env", {}),
        )
```

---

## 6. 保留内容清单

### 6.1 完全保留

| 模块/文件 | 原因 |
|----------|------|
| `memory/` 全部 | 记忆系统与 LangGraph 正交，可独立工作 |
| `tui/` 全部 | 用户界面，只需适配调用方式 |
| `config/` | 配置文件，适配新格式 |
| `prompts/system/` | 提示词文件，继续使用 |

### 6.2 适配后保留

| 模块/文件 | 适配内容 |
|----------|----------|
| `tools/security.py` | 安全策略逻辑保留，包装为 Tool |
| `tools/permission.py` | 权限服务保留，集成到 ToolNode |
| `tools/executor.py` | SafeExecutor 保留，作为 Command Tool 底层 |
| `agents/base.py` | AgentConfig, AgentResult 类型保留 |

### 6.3 保留的类型定义

```python
# 保留的类型和配置
class AgentConfig:
    name: str
    description: str
    tool_filter: str  # 用于工具绑定选择
    max_iterations: int
    system_prompt: str
    prompt_path: str

class AgentResult:
    success: bool
    output: str
    error: str
    artifacts: Dict[str, str]
```

---

## 7. 迁移计划

### 7.1 阶段划分

```
Phase 1: 基础设施 (Week 1-2)
├── 添加 LangGraph/LangSmith 依赖
├── 创建 graph/ 目录结构
├── 实现状态定义 (state.py)
└── 配置 LangSmith 追踪

Phase 2: 图构建 (Week 2-3)
├── 实现节点函数 (nodes.py)
├── 定义边与路由 (edges.py)
├── 构建完整图 (builder.py)
└── 测试图执行

Phase 3: 工具迁移 (Week 3-4)
├── 现有工具包装为 LangChain Tool
├── 实现 MCP 适配器
├── 工具过滤逻辑适配
└── 安全策略集成

Phase 4: Agent 角色迁移 (Week 4-5)
├── 提取 Agent 角色定义 (roles.py)
├── 迁移提示词 (prompts.py)
├── 适配能力定义 (capabilities.py)
└── 测试各 Agent 节点

Phase 5: TUI 集成 (Week 5-6)
├── 创建 graph_runner.py
├── 适配 console_app.py
├── 流式输出适配
└── 端到端测试

Phase 6: 清理与优化 (Week 6-7)
├── 删除废弃代码
├── 更新文档
├── 性能优化
└── 发布 v2.0
```

### 7.2 兼容性策略

```python
# 提供兼容层，渐进迁移
class LegacyOrchestratorAdapter:
    """旧 Orchestrator 接口适配器"""

    def __init__(self):
        self.graph = CodingAgentGraphBuilder().build()

    def dispatch(self, task: str, context: dict = None):
        """兼容旧接口"""
        result = self.graph.invoke({
            "user_request": task,
            "messages": [],
        })
        return self._convert_result(result)
```

### 7.3 测试策略

```python
# 保留现有测试，新增 LangGraph 测试
tests/
├── agents/           # 现有 Agent 测试 (适配)
├── graph/            # 新增: 图测试
│   ├── test_state.py
│   ├── test_nodes.py
│   └── test_builder.py
├── tools/            # 工具测试 (适配)
└── integration/      # 集成测试
    └── test_full_workflow.py
```

---

## 8. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| LangGraph API 变更 | 高 | 使用稳定版本，关注更新日志 |
| 学习曲线 | 中 | 先实现 POC，逐步迁移 |
| 性能差异 | 中 | 基准测试，必要时优化 |
| 功能缺失 | 低 | 检查 LangGraph 功能覆盖 |

---

## 9. 成功指标

| 指标 | 当前 | 目标 |
|------|------|------|
| 核心代码量 | ~300KB | ~180KB (-40%) |
| 可观测性 | 无 | 全链路追踪 |
| 并行执行 | 手动实现 | 框架原生 |
| MCP 集成 | 无 | 开箱即用 |
| 新增测试 | - | 覆盖率 >80% |

---

## 附录 A: 参考资料

- [LangGraph 文档](https://langchain-ai.github.io/langgraph/)
- [LangSmith 文档](https://docs.smith.langchain.com/)
- [LangChain MCP Adapters](https://github.com/langchain-ai/langchain-mcp-adapters)
- [现有架构文档](./multi-agent-architecture-design.md)

## 附录 B: 示例代码

完整的示例代码见 `examples/langgraph_demo.py` (待创建)。