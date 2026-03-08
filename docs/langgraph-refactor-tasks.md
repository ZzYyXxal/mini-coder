# LangGraph 重构迁移任务计划

> **版本**: 1.0
> **日期**: 2026-03-07
> **预计工期**: 7 周

---

## 任务概览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        迁移阶段总览                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Phase 1          Phase 2          Phase 3          Phase 4            │
│  基础设施         图构建          工具迁移          Agent 角色          │
│  Week 1-2         Week 2-3         Week 3-4          Week 4-5           │
│                                                                         │
│  ┌─────┐         ┌─────┐         ┌─────┐         ┌─────┐             │
│  │依赖 │         │状态 │         │工具 │         │角色 │             │
│  │安装 │   ───▶  │定义 │   ───▶  │包装 │   ───▶  │迁移 │             │
│  │配置 │         │节点 │         │MCP  │         │提示词│             │
│  └─────┘         └─────┘         └─────┘         └─────┘             │
│                                                                         │
│  Phase 5          Phase 6          Phase 7                              │
│  TUI 集成         测试验证         清理发布                              │
│  Week 5-6         Week 6-7          Week 7                              │
│                                                                         │
│  ┌─────┐         ┌─────┐         ┌─────┐                              │
│  │适配 │         │单元 │         │删除 │                              │
│  │流式 │   ───▶  │集成 │   ───▶  │废弃 │                              │
│  │输出 │         │测试 │         │文档 │                              │
│  └─────┘         └─────┘         └─────┘                              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: 基础设施迁移 (Week 1-2)

### 1.1 依赖安装 [Day 1-2]

**任务**: 更新 `pyproject.toml`，添加 LangGraph 生态依赖

```toml
# 新增依赖
dependencies = [
    # 现有...
    "langgraph>=0.2.0",
    "langchain-core>=0.3.0",
    "langchain-anthropic>=0.3.0",
    "langchain-openai>=0.2.0",
    "langsmith>=0.1.0",
]

[project.optional-dependencies]
mcp = ["langchain-mcp-adapters>=0.1.0"]
```

**验收标准**:
- [ ] `pip install -e ".[mcp]"` 成功
- [ ] `import langgraph` 无错误
- [ ] `import langsmith` 无错误

### 1.2 LangSmith 配置 [Day 2-3]

**任务**: 创建 `src/mini_coder/tracing/client.py`

```python
# tracing/client.py
import os
from langsmith import Client

def configure_langsmith(project_name: str = "mini-coder"):
    """配置 LangSmith 追踪"""
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = project_name
    # API Key 从环境变量读取
    return Client()
```

**验收标准**:
- [ ] LangSmith 项目创建成功
- [ ] 基础追踪可用

### 1.3 目录结构创建 [Day 3]

**任务**: 创建新的模块目录

```bash
mkdir -p src/mini_coder/graph
mkdir -p src/mini_coder/tracing
touch src/mini_coder/graph/__init__.py
touch src/mini_coder/graph/state.py
touch src/mini_coder/graph/nodes.py
touch src/mini_coder/graph/edges.py
touch src/mini_coder/graph/builder.py
touch src/mini_coder/tracing/__init__.py
touch src/mini_coder/tracing/client.py
touch src/mini_coder/tools/mcp_adapter.py
```

### 1.4 状态定义 [Day 4-5]

**任务**: 创建 `graph/state.py`，定义 LangGraph 状态

```python
# graph/state.py
from typing import TypedDict, List, Dict, Any, Optional, Annotated
from langgraph.graph import add_messages

class AgentMessage(TypedDict):
    """简化的 Agent 间消息（保留定向投递）"""
    message_id: str
    to_agent: str
    from_agent: str
    content: str
    created_at: float

class CodingAgentState(TypedDict):
    """编码 Agent 状态"""
    # 消息历史
    messages: Annotated[list, add_messages]

    # 基础字段
    user_request: str
    current_stage: str
    task_id: str
    session_id: str

    # Agent 消息（保留定向投递）
    agent_messages: List[AgentMessage]

    # 阶段结果
    exploration_result: Optional[str]
    implementation_plan: Optional[str]
    code_changes: List[Dict[str, str]]
    review_result: Optional[Dict[str, Any]]
    test_result: Optional[Dict[str, Any]]

    # 工具调用结果（支持 DAG）
    tool_results: List[Dict[str, Any]]

    # 错误与重试
    errors: List[str]
    retry_count: int
    max_retries: int

    # 元数据
    project_path: str
    metadata: Dict[str, Any]
```

**验收标准**:
- [ ] State 类型定义完整
- [ ] 类型检查通过 `mypy graph/state.py`

---

## Phase 2: 图构建 (Week 2-3)

### 2.1 节点函数实现 [Day 6-10]

**任务**: 创建 `graph/nodes.py`，实现各 Agent 节点

```python
# graph/nodes.py
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
import uuid
import time

async def router_node(state: CodingAgentState) -> dict:
    """路由节点 - 分析意图决定后续路径"""
    intent = _analyze_intent(state["user_request"])

    return {
        "current_stage": "routing",
        "metadata": {"intent": intent},
    }

async def explorer_node(state: CodingAgentState) -> dict:
    """Explorer 节点 - 只读代码库探索"""
    from mini_coder.tools.search_tools import get_search_tools
    from mini_coder.agents.prompts import EXPLORER_PROMPT

    agent = create_react_agent(
        model=_get_model("haiku"),
        tools=get_search_tools(),
        state_modifier=EXPLORER_PROMPT,
    )

    result = await agent.ainvoke({
        "messages": state["messages"] + [
            HumanMessage(content=f"探索任务: {state['user_request']}")
        ]
    })

    # 追加 Agent 消息（保留定向投递）
    agent_message = AgentMessage(
        message_id=str(uuid.uuid4()),
        to_agent="planner",
        from_agent="explorer",
        content=result["messages"][-1].content,
        created_at=time.time(),
    )

    return {
        "exploration_result": result["messages"][-1].content,
        "agent_messages": [agent_message],
        "current_stage": "explored",
    }

async def planner_node(state: CodingAgentState) -> dict:
    """Planner 节点 - 需求分析与任务规划"""
    # ... 类似实现

async def coder_node(state: CodingAgentState) -> dict:
    """Coder 节点 - 代码实现（支持 DAG 工具调用）"""
    from mini_coder.agents.tool_scheduler import ToolScheduler

    agent = create_react_agent(
        model=_get_model("sonnet"),
        tools=get_coder_tools(),
    )

    result = await agent.ainvoke({
        "messages": _build_coder_messages(state)
    })

    # 如果响应包含 DAG tool_calls，使用 ToolScheduler
    tool_calls = _parse_tool_calls(result)
    if _has_dag_dependencies(tool_calls):
        scheduler = ToolScheduler()
        tool_result = await scheduler.execute_batch(tool_calls, _get_tool_registry())
        # 处理结果...

    return {
        "code_changes": [...],
        "agent_messages": [AgentMessage(...)],
    }

async def reviewer_node(state: CodingAgentState) -> dict:
    """Reviewer 节点 - 代码评审"""
    # ... 实现

async def bash_node(state: CodingAgentState) -> dict:
    """Bash 节点 - 测试验证"""
    # ... 实现

async def complete_node(state: CodingAgentState) -> dict:
    """完成节点 - 汇总结果"""
    return {"current_stage": "completed"}
```

**验收标准**:
- [ ] 所有节点函数实现完成
- [ ] 每个节点单元测试通过

### 2.2 边与路由逻辑 [Day 11-12]

**任务**: 创建 `graph/edges.py`

```python
# graph/edges.py
from typing import Literal

def route_by_intent(state: CodingAgentState) -> Literal["explore", "plan", "code", "simple"]:
    """根据意图路由"""
    intent = state.get("metadata", {}).get("intent", "")

    if "explore" in intent or "search" in intent:
        return "explore"
    elif "plan" in intent or "design" in intent:
        return "plan"
    elif "simple" in intent or len(state["user_request"]) < 100:
        return "simple"
    else:
        return "code"

def check_review_result(state: CodingAgentState) -> Literal["pass", "reject", "max_retry"]:
    """检查评审结果"""
    if state["retry_count"] >= state["max_retries"]:
        return "max_retry"

    review = state.get("review_result", {})
    if review.get("passed", False):
        return "pass"
    return "reject"

def check_test_result(state: CodingAgentState) -> Literal["pass", "fail"]:
    """检查测试结果"""
    test = state.get("test_result", {})
    if test.get("all_passed", False):
        return "pass"
    return "fail"
```

### 2.3 图构建器 [Day 13-14]

**任务**: 创建 `graph/builder.py`

```python
# graph/builder.py
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from .state import CodingAgentState
from .nodes import *
from .edges import *

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

        # 条件路由
        graph.add_conditional_edges("router", route_by_intent, {
            "explore": "explorer",
            "plan": "planner",
            "code": "coder",
            "simple": "coder",
        })

        # 标准流程
        graph.add_edge("explorer", "planner")
        graph.add_edge("planner", "coder")
        graph.add_edge("coder", "reviewer")

        # 评审分支
        graph.add_conditional_edges("reviewer", check_review_result, {
            "pass": "bash",
            "reject": "coder",
            "max_retry": "complete",
        })

        # 测试分支
        graph.add_conditional_edges("bash", check_test_result, {
            "pass": "complete",
            "fail": "coder",
        })

        graph.add_edge("complete", END)

        return graph.compile(checkpointer=self.checkpointer)
```

**验收标准**:
- [ ] 图编译成功
- [ ] 简单流程测试通过

---

## Phase 3: 工具迁移 (Week 3-4)

### 3.1 现有工具包装 [Day 15-18]

**任务**: 将现有工具包装为 LangChain Tool

```python
# tools/file_tools.py
from langchain_core.tools import tool
from mini_coder.tools.executor import SafeExecutor

@tool
def read_file(path: str) -> str:
    """读取文件内容

    Args:
        path: 文件路径（绝对路径或相对路径）

    Returns:
        文件内容
    """
    from pathlib import Path
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file: {e}"

@tool
def write_file(path: str, content: str) -> str:
    """写入文件

    Args:
        path: 文件路径
        content: 文件内容

    Returns:
        操作结果
    """
    from pathlib import Path
    try:
        Path(path).write_text(content, encoding="utf-8")
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing file: {e}"

@tool
def execute_command(command: str, timeout: int = 120) -> str:
    """执行系统命令（带安全检查）

    Args:
        command: 要执行的命令
        timeout: 超时时间（秒）

    Returns:
        命令输出
    """
    executor = SafeExecutor(timeout=timeout)
    result = executor.execute(command)
    if result.success:
        return result.stdout
    return f"Error: {result.stderr}"
```

**验收标准**:
- [ ] 所有工具包装完成
- [ ] 工具可以独立调用

### 3.2 MCP 适配器 [Day 19-20]

**任务**: 创建 `tools/mcp_adapter.py`

```python
# tools/mcp_adapter.py
from typing import List
from langchain_core.tools import BaseTool

class MCPToolAdapter:
    """MCP 工具适配器"""

    async def load_tools(self, config_path: str = "config/mcp.yaml") -> List[BaseTool]:
        """从配置加载 MCP 工具"""
        import yaml

        with open(config_path) as f:
            config = yaml.safe_load(f)

        tools = []
        for server in config.get("servers", []):
            server_tools = await self._load_server_tools(server)
            tools.extend(server_tools)

        return tools
```

### 3.3 ToolScheduler 适配 [Day 21]

**任务**: 适配 ToolScheduler 到 LangChain Tool

```python
# tools/tool_scheduler_adapter.py
from mini_coder.agents.tool_scheduler import ToolScheduler, ToolCall
from langchain_core.tools import BaseTool

class LangChainToolScheduler:
    """LangChain Tool 调度器适配"""

    def __init__(self, tools: List[BaseTool]):
        self._registry = {t.name: t for t in tools}
        self._scheduler = ToolScheduler()

    async def execute_dag(self, tool_calls: List[ToolCall]) -> ToolBatchResult:
        """执行 DAG 工具调用"""
        return await self._scheduler.execute_batch(tool_calls, self._registry)
```

---

## Phase 4: Agent 角色迁移 (Week 4-5)

### 4.1 角色定义提取 [Day 22-25]

**任务**: 从 `enhanced.py` 提取 Agent 角色定义到 `agents/roles.py`

```python
# agents/roles.py
from dataclasses import dataclass
from typing import List, Type

@dataclass
class AgentRole:
    """Agent 角色定义"""
    name: str
    description: str
    allowed_tools: List[str]
    model: str  # "haiku" | "sonnet"
    prompt_key: str

# 定义角色
EXPLORER_ROLE = AgentRole(
    name="Explorer",
    description="只读代码库搜索专家",
    allowed_tools=["Read", "Glob", "Grep"],
    model="haiku",
    prompt_key="subagent-explorer",
)

PLANNER_ROLE = AgentRole(
    name="Planner",
    description="需求分析与任务规划专家",
    allowed_tools=["Read", "Grep", "WebSearch"],
    model="sonnet",
    prompt_key="subagent-planner",
)

CODER_ROLE = AgentRole(
    name="Coder",
    description="代码实现专家",
    allowed_tools=["Read", "Write", "Edit", "Grep", "Glob"],
    model="sonnet",
    prompt_key="subagent-coder",
)

REVIEWER_ROLE = AgentRole(
    name="Reviewer",
    description="代码质量评审专家",
    allowed_tools=["Read", "Grep", "Glob"],
    model="sonnet",
    prompt_key="subagent-reviewer",
)

BASH_ROLE = AgentRole(
    name="Bash",
    description="终端执行与测试验证专家",
    allowed_tools=["Read", "Bash", "Glob"],
    model="sonnet",
    prompt_key="subagent-bash",
)
```

### 4.2 提示词整合 [Day 26-28]

**任务**: 创建 `agents/prompts.py`，整合提示词

```python
# agents/prompts.py
from mini_coder.agents.prompt_loader import PromptLoader

_loader = PromptLoader()

EXPLORER_PROMPT = _loader.load("subagent-explorer")
PLANNER_PROMPT = _loader.load("subagent-planner")
CODER_PROMPT = _loader.load("subagent-coder")
REVIEWER_PROMPT = _loader.load("subagent-reviewer")
BASH_PROMPT = _loader.load("subagent-bash")
```

---

## Phase 5: TUI 集成 (Week 5-6)

### 5.1 图运行器 [Day 29-31]

**任务**: 创建 `tui/graph_runner.py`

```python
# tui/graph_runner.py
from mini_coder.graph.builder import CodingAgentGraphBuilder
from mini_coder.graph.state import CodingAgentState

class GraphRunner:
    """图执行器 - TUI 调用入口"""

    def __init__(self):
        self._builder = CodingAgentGraphBuilder()
        self._graph = self._builder.build()

    async def run(self, user_request: str, session_id: str = None) -> CodingAgentState:
        """执行编码任务"""
        initial_state = {
            "user_request": user_request,
            "session_id": session_id or str(uuid.uuid4()),
            "messages": [],
            "agent_messages": [],
            "current_stage": "pending",
            "retry_count": 0,
            "max_retries": 3,
        }

        config = {"configurable": {"thread_id": session_id}}
        result = await self._graph.ainvoke(initial_state, config)
        return result

    async def stream(self, user_request: str, session_id: str = None):
        """流式执行"""
        initial_state = {...}

        config = {"configurable": {"thread_id": session_id}}
        async for event in self._graph.astream(initial_state, config):
            yield event
```

### 5.2 TUI 适配 [Day 32-35]

**任务**: 适配 `console_app.py` 使用 GraphRunner

```python
# tui/console_app.py 修改
# 替换 Orchestrator 调用为 GraphRunner

from mini_coder.tui.graph_runner import GraphRunner

class ConsoleApp:
    def __init__(self):
        self._runner = GraphRunner()

    async def handle_user_input(self, user_input: str):
        # 使用 GraphRunner 替代 Orchestrator
        async for event in self._runner.stream(user_input, self._session_id):
            # 处理流式事件
            self._render_event(event)
```

---

## Phase 6: 测试验证 (Week 6-7)

### 6.1 单元测试 [Day 36-40]

**任务**: 创建测试文件

```bash
# 新增测试文件
tests/graph/test_state.py
tests/graph/test_nodes.py
tests/graph/test_builder.py
tests/tools/test_langchain_tools.py
tests/integration/test_graph_workflow.py
```

**测试用例**:

```python
# tests/graph/test_nodes.py
import pytest
from mini_coder.graph.nodes import explorer_node, planner_node
from mini_coder.graph.state import CodingAgentState

@pytest.mark.asyncio
async def test_explorer_node():
    state = CodingAgentState(
        user_request="查找登录相关的代码",
        messages=[],
        agent_messages=[],
        current_stage="pending",
        # ...
    )

    result = await explorer_node(state)

    assert "exploration_result" in result
    assert result["current_stage"] == "explored"
    assert len(result["agent_messages"]) == 1
    assert result["agent_messages"][0]["from_agent"] == "explorer"
```

### 6.2 集成测试 [Day 41-45]

**任务**: 端到端测试

```python
# tests/integration/test_graph_workflow.py
@pytest.mark.asyncio
async def test_full_coding_workflow():
    """测试完整编码流程"""
    runner = GraphRunner()

    result = await runner.run("实现一个简单的加法函数")

    assert result["current_stage"] == "completed"
    assert len(result["code_changes"]) > 0
```

---

## Phase 7: 清理与发布 (Week 7)

### 7.1 删除废弃代码 [Day 46-48]

**任务**: 删除不再需要的代码

```bash
# 删除文件
rm src/mini_coder/agents/orchestrator.py
rm src/mini_coder/agents/scheduler.py
rm src/mini_coder/llm/providers/anthropic.py
rm src/mini_coder/llm/providers/zhipu.py
# ... 其他废弃文件
```

**保留文件**:
- `agents/mailbox.py` - 简化后保留 AgentMessage
- `agents/tool_scheduler.py` - DAG 功能保留
- `agents/base.py` - 简化后保留配置类型

### 7.2 文档更新 [Day 49-50]

**任务**: 更新文档

- [ ] 更新 `CLAUDE.md`
- [ ] 更新 `README.md`
- [ ] 更新 `docs/multi-agent-architecture-design.md`

### 7.3 发布准备 [Day 51-52]

**任务**: 版本发布

- [ ] 更新版本号到 `v2.0.0`
- [ ] 生成 CHANGELOG
- [ ] 创建 Git Tag

---

## 风险与缓解

| 风险 | 影响 | 缓解措施 | 负责人 |
|------|------|----------|--------|
| LangGraph API 变更 | 高 | 使用稳定版本，锁定依赖版本 | - |
| DAG 功能兼容性 | 中 | 保留 ToolScheduler，逐步迁移 | - |
| TUI 流式输出适配 | 中 | 保留现有流式接口，适配新实现 | - |
| 测试覆盖不足 | 中 | 每个 Phase 必须有对应测试 | - |

---

## 验收标准

### Phase 1 完成标准
- [ ] LangGraph 依赖安装成功
- [ ] LangSmith 配置完成
- [ ] 状态类型定义完成

### Phase 2 完成标准
- [ ] 所有节点函数实现
- [ ] 图编译成功
- [ ] 简单流程测试通过

### Phase 3 完成标准
- [ ] 工具包装完成
- [ ] MCP 适配器可用
- [ ] ToolScheduler 适配完成

### Phase 4 完成标准
- [ ] Agent 角色定义完成
- [ ] 提示词整合完成

### Phase 5 完成标准
- [ ] TUI 集成完成
- [ ] 流式输出正常

### Phase 6 完成标准
- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试通过

### Phase 7 完成标准
- [ ] 废弃代码删除
- [ ] 文档更新
- [ ] v2.0.0 发布