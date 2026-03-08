# Mini-Coder 多 Agent 系统架构设计

> **版本**: 3.0
> **最后更新**: 2026-03-08
> **重大变更**: Main Agent 与 Planner 合并为统一 Planner-Orchestrator
> **设计目标**: 基于"统一决策 Agent + 专业化子代理"的 coding agent 系统

---

## 1. 架构概览

### 1.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                统一 Planner-Orchestrator Agent                          │
│  身份：决策中枢 + 需求分析 + TDD 规划                                      │
│  决策：自己直接回答 / 直接派发 / 复杂任务拆解 / 无法完成请用户澄清          │
│  能力：一次 LLM 调用完成判断与规划，替代原先「主代理只出文本 + 路由再派发」  │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ 按四类决策执行
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│   Explorer    │     │    Planner    │     │    Coder      │
│  (只读探索)    │     │  (TDD 规划)   │     │ (代码生成)     │
│  Read-only    │     │  Analysis     │     │  Write/Edit   │
└───────────────┘     └───────────────┘     └───────────────┘
                                                │
                                ┌───────────────┴───────────────┐
                                ▼                               ▼
                       ┌───────────────┐             ┌───────────────┐
                       │   Reviewer    │             │    Bash       │
                       │ (代码评审)     │             │(终端执行 + 测试) │
                       │ Read+Analyze  │             │ Command+Test  │
                       └───────────────┘             └───────────────┘
```

### 1.2 Agent 角色与职责

| 角色 | 身份 | 工具范围 | 何时使用 |
|------|------|----------|----------|
| **统一 Planner-Orchestrator** | 决策中枢、需求分析、TDD 规划 | 无（只做决策与规划，不直接调用工具） | 每轮用户输入首先由此 Agent 处理，做四类决策 |
| **Explorer** | 只读代码库搜索 | Read, Grep, Glob | 需要"先搞清楚代码结构/位置"且不修改时 |
| **Planner** | 需求分析与任务规划 | Read, Grep, WebSearch | 需要拆解复杂任务、制定实现计划时 |
| **Coder** | 代码生成与编辑 | Read, Write, Edit, Grep, Glob | 实现新功能、按需求写代码 |
| **Reviewer** | 代码质量评审 | Read, Grep, Glob | 代码完成后评审质量、检查规范 |
| **Bash** | 终端执行与测试验证 | Read, Bash, Glob | 运行测试、执行命令、验证质量 |

### 1.3 核心架构变革：统一 Planner-Orchestrator

**旧架构问题**：
- 主代理只输出文本，再由 `_analyze_intent()` 做意图分析派发
- 两个独立的 LLM 调用（主代理 + 意图分析），割裂且低效
- 无法在规划阶段同时决定派发策略

**新架构优势**：
- **一次 LLM 调用完成判断与规划**：统一 Agent 直接输出四类决策之一
- **四类决策**：自己直接回答 / 直接派发单 agent / 复杂任务多步派发 / 无法完成请用户澄清
- **结构化输出**：下游可直接解析 `Agent:`, `Task:`, `Params:`, `Steps:` 并执行

```
┌─────────────────────────────────────────────────────────────┐
│                    代码框架 (Code Framework)                  │
│  - Agent 基类与继承体系                                        │
│  - 工具权限控制 (ToolFilter)                                  │
│  - 黑板模式 (Blackboard) 上下文管理                           │
│  - 工作流状态机 (Orchestrator)                                │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  动态提示词注入 (Dynamic Prompt Injection)    │
│  - 主代理提示词：多段组合 (身份 + 派发 + 记忆 + 终端)            │
│  - 子代理提示词：独立 Markdown 模板，运行时加载并插值            │
│  - 项目规范注入：CLAUDE.md 动态拼接到系统提示词                │
└─────────────────────────────────────────────────────────────┘
```

**核心设计理念**:
1. **执行流程、工具循环、上下文管理由代码实现** - 硬编码在 Python 源码中
2. **身份与行为由系统提示词定义** - 从 `knowledge-base/mini-coder-agent-prompts/*.md` 动态加载
3. **动态性体现在**：按用户意图、上下文、任务类型选择和填充对应提示词片段

---

## 2. 设计原则

### 2.1 核心原则

| 原则 | 说明 |
|------|------|
| **主代理不"单一大段提示词"** | 由多段组合（身份 + 工具策略 + 派发规则 + 记忆 + 终端安全） |
| **子代理独立上下文** | 每个子代理只收到自己的 system prompt + 当前任务，不继承主代理完整提示 |
| **派发依据 description** | 主代理根据"任务描述"和各子代理的 description 决定派给谁 |
| **记忆与终端在主代理** | 记忆的读写、终端命令的执行与安全策略由主代理统一处理 |
| **子代理不派发子代理** | 所有派发由主代理完成，子代理只执行单一任务 |
| **终端安全** | 采用白名单/黑名单 + 用户确认策略 |

### 2.2 提示词设计原则

```
统一 Agent 提示词 = 身份段 + 四类决策格式 + 子代理列表 + 输出约束
子代理提示词 = 身份段 + 工具约束段 + 行为准则段 + 输出要求段
```

**动态插值占位符**:
- `{{GLOB_TOOL_NAME}}` → 实际工具名（如 `Glob`）
- `{{thoroughness}}` → `quick` / `medium` / `thorough`（Explorer 探索深度）
- `{{project_name}}` → 从 CLAUDE.md 读取的项目名称
- `{{coding_standards}}` → 从 CLAUDE.md 读取的编码规范

---

## 3. 各 Agent 详细设计

### 3.1 统一 Planner-Orchestrator Agent

**身份与角色**:
```
你是统一 Planner-Orchestrator Agent，负责：
1. 决策中枢 - 接收用户消息后做四类决策
2. 需求分析 - 理解用户需求，识别问题类型
3. TDD 规划 - 在复杂任务中产出 implementation_plan
4. 派发驱动 - 不写代码、不执行命令，只做决策与规划，驱动子代理执行
```

**四类决策（输出必须且仅能选其一）**:

| 决策类型 | 输出格式 | 适用场景 |
|---------|---------|---------|
| **自己直接回答** | `[Simple Answer]` + 内容 | 寒暄、概念性问答、无需工具与改代码的解释 |
| **直接派发** | `[Direct Dispatch]` + Agent + Task + Params | 明确由一个子代理即可完成，任务与参数清晰 |
| **复杂任务** | `[Complex Task]` + Problem type + Steps | 需多步、多子代理协作，拆成子任务并标明每步由谁做 |
| **无法完成** | `[Cannot Handle]` + 原因 | 当前无法完成，需用户澄清或补充信息 |

**输出格式示例**:

1. 自己直接回答：
```
[Simple Answer]
<直接回答的正文>
```

2. 直接派发：
```
[Direct Dispatch]
Agent: CODER
Task: 实现用户登录功能，包含表单验证和 JWT 认证
Params:
work_dir: /path/to/project
```

3. 复杂任务：
```
[Complex Task]
Problem type: 新功能开发

Implementation plan:
1. 先写测试用例（TDD Red）
2. 实现核心逻辑（TDD Green）
3. 重构优化

Steps:
1. Agent: PLANNER
   Task: 拆解登录功能的 TDD 实现计划
2. Agent: CODER
   Task: 按计划实现登录功能
   Params:
   tdd_mode: true
3. Agent: REVIEWER
   Task: 评审代码质量与架构对齐
4. Agent: BASH
   Task: 运行测试验证
   Params:
   bash_mode: quality_report
```

4. 无法完成：
```
[Cannot Handle]
需要明确：1) 目标文件路径 2) 具体要实现的功能点
```

**派发规则**:
```
用户请求 → 统一 Agent 四类决策 → 执行

├─ [Simple Answer] → 直接返回回答
├─ [Direct Dispatch] → 创建指定子代理并执行
├─ [Complex Task] → 按 Steps 顺序依次派发
└─ [Cannot Handle] → 返回原因，等待用户澄清
```

**子代理列表**（名称必须 UPPERCASE 英文）:
- `EXPLORER` - 只读探索代码库
- `PLANNER` - TDD 规划/写 implementation_plan
- `CODER` - 写代码/改文件
- `REVIEWER` - 代码评审
- `BASH` - 终端/测试执行
- `MINI_CODER_GUIDE` - 使用指南
- `GENERAL_PURPOSE` - 通用只读

### 3.2 Explorer (只读探索)

**身份**: 只读代码库搜索专家

**严格约束 - 只读模式**:
- 禁止创建/修改/删除任何文件
- 禁止执行会改变系统状态的命令（mkdir, git add/commit, npm install 等）
- 仅使用只读工具：Read, Grep, Glob, Bash(只读操作)

**允许的命令**: `ls`, `git status`, `git log`, `git diff`, `find`, `cat`, `head`, `tail`

**输出要求**:
- 所有文件路径使用**绝对路径**
- 汇报发现的文件/位置、关键代码或结构结论
- 若有建议关注的文件，明确列出并注明原因

### 3.3 Planner (规划分析)

**身份**: 需求分析与任务规划专家

**能力**:
1. 需求分析 - 理解用户需求，识别边界条件
2. 任务分解 - 拆解为可执行的原子步骤（TDD：测试优先）
3. 技术选型 - 推荐合适的技术方案
4. 依赖分析 - 识别模块依赖关系

**输出**:
- 实现计划 (`implementation_plan.md`)
- 任务分解清单（带依赖关系）
- 技术方案建议

### 3.4 Coder (代码实现)

**身份**: 代码实现专家

**能力**:
1. 代码生成 - 编写新功能代码
2. 代码编辑 - 修改现有代码（优先编辑而非新建）
3. 测试编写 - 编写单元测试

**行为准则**:
- 优先编辑已有文件，必要时才创建新文件
- 遵循项目既有风格（命名、缩进、注释语言）
- 不主动写文档（除非明确要求）
- 回复中引用文件使用绝对路径

**输出要求**:
- 简要总结修改了哪些文件、实现了什么行为
- 若有未完成或需后续处理的事项，明确说明
- 可附「可写入记忆的摘要」供主代理保存

### 3.5 Reviewer (代码评审)

**身份**: 代码质量评审专家（只读，不能修改代码）

**评审清单**:
1. **架构对齐检查** - 是否符合 `implementation_plan.md`
2. **类型提示** - 所有函数有完整类型标注（Python 3.10+ 语法）
3. **文档字符串** - Google 风格，覆盖所有公共 API
4. **代码规范** - PEP 8 合规（命名、缩进、行长度）
5. **代码异味** - 识别重复逻辑、过长函数、不当依赖

**输出格式**:
```
【通过】代码符合架构和质量要求，可进入 Bash 测试验证

或

【打回】需要修改以下问题：

1. [架构偏离] 具体问题 + 修改建议
2. [代码质量] 具体问题 + 修改建议
3. [规范违反] 具体问题 + 修改建议
```

### 3.6 Bash (终端执行 + 测试验证)

**身份**: 终端执行与质量验证专家

**能力**:
1. 终端命令执行（受限白名单）
2. 运行测试 (pytest)
3. 类型检查 (mypy)
4. 代码风格检查 (flake8)
5. 覆盖率检查 (pytest --cov)

**工具权限**:
- 只读工具：Read, Glob
- 命令执行：Bash（白名单限制）

**命令白名单**:
| 类别 | 命令示例 | 执行策略 |
|------|---------|---------|
| **测试** | `pytest`, `python -m pytest` | 直接执行 |
| **类型检查** | `mypy`, `python -m mypy` | 直接执行 |
| **代码风格** | `flake8`, `black --check` | 直接执行 |
| **信息查看** | `ls`, `cat`, `head`, `tail`, `pwd` | 直接执行 |
| **Python 执行** | `python`, `python -m` | 直接执行 |

**命令黑名单** (需用户确认):
- `pip install`, `npm install` - 依赖安装
- `git commit`, `git push` - 版本控制写操作
- `rm`, `mv`, `cp` - 文件系统写操作

**禁止执行**:
- `rm -rf`, `mkfs`, `chmod 777`, `curl|bash` 等危险命令

### 3.7 质量流水线规格（何时跑、谁触发）

质量流水线（pytest + mypy + flake8 + coverage + 报告）**仅由用户、Planner 或 Orchestrator 显式触发**；Bash **不自行决定**是否跑测试。

- **何时跑**：用户明确要求「运行测试/验证质量/生成质量报告」、Orchestrator 在 dispatch 时传入 `bash_mode=quality_report`、或工作流进入 TESTING/VERIFYING 阶段由 TesterAgent 执行。
- **何时不跑**：未显式请求时；或意图为「写入/保存到本地」「执行单条命令」等且已通过 `bash_mode` 指定为 `confirm_save` / `single_command` 时。
- **实现约定**：BashAgent 仅在 `context["bash_mode"] == "quality_report"` 时执行流水线；缺省不跑，并提示调用方明确指定。详见 **docs/quality-pipeline-spec.md**。

---

## 4. 工作流设计

### 4.1 统一 Agent 决策流程

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户请求                                   │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                  统一 Planner-Orchestrator                       │
│           一次 LLM 调用完成判断与规划                              │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
   ┌──────────┐     ┌──────────┐     ┌──────────┐
   │ [Simple  │     │ [Direct  │     │ [Complex │
   │  Answer] │     │ Dispatch]│     │  Task]   │
   └────┬─────┘     └────┬─────┘     └────┬─────┘
        │                │                │
        ▼                ▼                ▼
   直接返回回答     创建指定子代理      按 Steps 顺序
                   并执行            依次派发
```

### 4.2 标准工作流（复杂任务）

当统一 Agent 输出 `[Complex Task]` 时：

```
用户请求
    │
    ▼
统一 Agent 输出 [Complex Task]
    │
    ├─ Problem type: 新功能开发
    ├─ Implementation plan: TDD 步骤
    └─ Steps:
        1. Agent: EXPLORER → 探索代码结构
        2. Agent: PLANNER → 制定实现计划
        3. Agent: CODER → 实现代码
        4. Agent: REVIEWER → 评审
        5. Agent: BASH → 测试验证
    │
    ▼
Orchestrator.run_unified() 按 Steps 顺序执行
    │
    ▼
每步：dispatch_with_agent(agent_type, task, params)
```

### 4.3 直接派发工作流（简单任务）

当统一 Agent 输出 `[Direct Dispatch]` 时：

```
用户请求
    │
    ▼
统一 Agent 输出 [Direct Dispatch]
    │
    ├─ Agent: CODER
    ├─ Task: 实现登录功能
    └─ Params: work_dir: /path/to/project
    │
    ▼
Orchestrator.dispatch_with_agent(CODER, task, params)
    │
    ▼
CoderAgent 执行并返回结果
```

### 4.4 简化工作流（直接回答）

当统一 Agent 输出 `[Simple Answer]` 时：

```
用户请求
    │
    ▼
统一 Agent 输出 [Simple Answer]
    │
    ▼
直接返回回答内容，无需派发子代理
```

适用于：寒暄、概念性问答、无需工具与改代码的解释

---

## 5. 提示词文件结构

### 5.1 文件组织

```
mini-coder/
├── prompts/system/
│   ├── unified-planner-orchestrator.md  # 统一 Agent 系统提示词（核心）
│   ├── subagent-explorer.md              # Explorer 子代理系统提示词
│   ├── subagent-planner.md               # Planner 子代理系统提示词
│   ├── subagent-coder.md                 # Coder 子代理系统提示词
│   ├── subagent-reviewer.md              # Reviewer 子代理系统提示词
│   └── subagent-bash.md                  # Bash 子代理系统提示词
├── src/mini_coder/
│   └── agents/
│       ├── __init__.py
│       ├── base.py                       # Agent 基类
│       ├── enhanced.py                   # 增强型 Agent（PlannerAgent, CoderAgent 等）
│       ├── orchestrator.py               # 工作流协调器（含 run_unified）
│       ├── output_parser.py              # 统一 Agent 输出解析器
│       ├── prompt_loader.py              # 提示词加载器
│       └── mailbox.py                    # Agent 间消息传递
```

### 5.2 统一 Agent 提示词结构

统一 Agent 提示词（`unified-planner-orchestrator.md`）包含：

```markdown
# Unified Planner-Orchestrator Agent

**Role**: 接收用户消息后做四类决策：自己直接回答、直接派发单个子代理、
复杂任务拆成多步并指定每步由谁做（及参数）、或无法完成且需用户澄清。

**When to use**: 用户每轮自然语言输入均由本 Agent 先处理；不写代码、
不执行命令，只做决策与规划，并驱动子代理执行。

---

## 四类决策（输出必须且仅能选其一）

1. **自己直接回答**：寒暄、概念性问答、无需工具与改代码的解释。
2. **直接派发**：明确由**一个**子代理即可完成，且任务与参数清晰。
3. **复杂任务**：需多步、多子代理协作；拆成子任务并标明每步由哪个 Agent 做。
4. **无法完成**：当前无法完成且没有合适子代理可完成，需用户澄清。

---

## 子代理列表（名称必须 UPPERCASE 英文）

EXPLORER, PLANNER, CODER, REVIEWER, BASH, MINI_CODER_GUIDE, GENERAL_PURPOSE

---

## 结构化输出格式

### 1. 自己直接回答
[Simple Answer]
<内容>

### 2. 直接派发
[Direct Dispatch]
Agent: <AGENT_NAME>
Task: <任务描述>
Params:
<可选参数>

### 3. 复杂任务
[Complex Task]
Problem type: <类型>
Implementation plan: <可选>
Steps:
1. Agent: <AGENT_NAME>
   Task: <任务>
   Params: <可选>

### 4. 无法完成
[Cannot Handle]
<原因与建议>
```

### 5.3 输出解析器

`output_parser.py` 负责解析统一 Agent 的结构化输出：

```python
class UnifiedOutputType(Enum):
    SIMPLE_ANSWER = "simple_answer"
    DIRECT_DISPATCH = "direct_dispatch"
    COMPLEX_TASK = "complex_task"
    CANNOT_HANDLE = "cannot_handle"
    UNKNOWN = "unknown"

@dataclass
class UnifiedOutput:
    output_type: UnifiedOutputType
    content: Optional[str] = None
    direct_dispatch: Optional[DirectDispatchOutput] = None
    steps: List[StepWithParams] = field(default_factory=list)

def parse_unified_output(text: str) -> UnifiedOutput:
    """解析统一 Agent 输出，返回四类之一"""
    ...
```

---

## 6. 代码框架设计

### 6.1 Agent 基类

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

@dataclass
class AgentConfig:
    """Agent 配置"""
    name: str
    description: str
    tool_filter: str  # "read_only", "full_access", "strict"
    max_iterations: int = 10
    system_prompt: Optional[str] = None
    system_prompt_path: Optional[str] = None

@dataclass
class AgentResult:
    """Agent 执行结果"""
    success: bool
    output: str = ""
    error: str = ""
    artifacts: Dict[str, str] = None
    tools_used: List[str] = None
    needs_user_decision: bool = False
    decision_reason: str = ""
    memory_summary: Optional[str] = None  # 「可写入记忆的摘要」

class BaseAgent(ABC):
    """Agent 基类"""

    AGENT_TYPE: str = "base"
    DEFAULT_CONFIG: AgentConfig = None

    def __init__(
        self,
        llm_service: Any,
        blackboard: Any,
        config: Optional[AgentConfig] = None,
    ):
        self.llm_service = llm_service
        self.blackboard = blackboard
        self.config = config or self.DEFAULT_CONFIG

    @abstractmethod
    def execute(self, task: str, context: Dict = None) -> AgentResult:
        """执行任务"""
        pass

    def get_system_prompt(self, context: Dict = None) -> str:
        """获取系统提示词（支持动态插值）"""
        if self.config.system_prompt:
            prompt = self.config.system_prompt
        elif self.config.system_prompt_path:
            prompt = Path(self.config.system_prompt_path).read_text(encoding="utf-8")
        else:
            prompt = self._get_default_system_prompt()

        # 占位符替换
        if context:
            for key, value in context.items():
                prompt = prompt.replace(f"{{{{{key}}}}}", str(value))

        return prompt

    def _get_default_system_prompt(self) -> str:
        """获取默认系统提示词（子类覆盖）"""
        raise NotImplementedError
```

### 6.2 黑板模式（共享上下文、工件与进度追踪）

Blackboard 承载**工作流/会话级**的上下文、工件与进度追踪，与 LangGraph 的「显式状态传递」一致：

- **共享上下文**：`work_dir`、`requirement`、`task_id` 等，由 Orchestrator 写入；子 Agent 通过 **dispatch_context** 在 `agent.execute(task, context=...)` 时显式注入获取。
- **工件存储**：`implementation_plan.md`（Planner 写）、`code:*`（Coder 写）；Reviewer 等由 Orchestrator 通过 **\_inject_reviewer_context** 从 Blackboard 取出并注入到本次调用的 `context`。
- **进度追踪**：步骤执行状态、文件变更记录、当前阶段等；供统一 Agent 查询项目进度。

```python
@dataclass
class StepProgress:
    """步骤进度追踪"""
    step_id: str                          # 步骤 ID，如 "1.1", "1.2"
    description: str                      # 步骤描述
    status: str = "pending"               # "pending" | "in_progress" | "completed" | "failed"
    agent: str = ""                       # 负责执行的 Agent
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    output_summary: str = ""
    error: str = ""


@dataclass
class FileChangeRecord:
    """文件变更记录"""
    path: str                             # 文件路径
    action: str                           # "created" | "modified" | "deleted"
    by: str                               # 执行的 Agent
    at: float                             # 变更时间
    summary: str = ""                     # 变更摘要


class Blackboard:
    """共享黑板 - 上下文、工件与进度追踪"""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self._artifacts: Dict[str, BlackboardArtifact] = {}
        self._context: Dict[str, Any] = {}
        self._event_log: List[Event] = []
        # 进度追踪（新增）
        self._step_progress: Dict[str, StepProgress] = {}
        self._file_changes: List[FileChangeRecord] = []
        self._current_phase: str = ""

    # === 工件管理 ===
    def add_artifact(self, name: str, content: Any, content_type: str, created_by: str):
        """添加工件"""
        self._artifacts[name] = {
            "content": content,
            "content_type": content_type,
            "created_by": created_by,
        }

    def get_artifact(self, name: str, default: Any = None) -> Any:
        """获取工件"""
        return self._artifacts.get(name, default)

    def set_context(self, key: str, value: Any):
        """设置上下文"""
        self._context[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        """获取上下文"""
        return self._context.get(key, default)

    def log_event(self, event: Event):
        """记录事件"""
        self._event_log.append(event)

    # === 进度追踪方法（新增） ===

    def init_steps_from_plan(self, plan_content: str) -> None:
        """从 implementation_plan 初始化步骤进度"""
        ...

    def mark_step_started(self, step_id: str, agent: str) -> None:
        """标记步骤开始执行"""
        ...

    def mark_step_completed(self, step_id: str, output_summary: str = "") -> None:
        """标记步骤完成"""
        ...

    def mark_step_failed(self, step_id: str, error: str) -> None:
        """标记步骤失败"""
        ...

    def record_file_change(self, path: str, action: str, by: str) -> None:
        """记录文件变更（created/modified/deleted）"""
        ...

    def get_progress_summary(self) -> Dict[str, Any]:
        """获取进度摘要：总步骤数、完成数、进度百分比、文件变更等"""
        ...

    def get_formatted_progress(self) -> str:
        """获取格式化的进度报告（供统一 Agent 或用户查询使用）"""
        ...
```

**进度追踪使用示例**：

```python
# 1. Planner 产出 implementation_plan 后初始化步骤
plan_content = blackboard.get_artifact_content("implementation_plan.md")
blackboard.init_steps_from_plan(plan_content)

# 2. Orchestrator 派发任务时标记步骤开始
blackboard.mark_step_started("1.1", "CODER")

# 3. Agent 执行完成时标记步骤完成
blackboard.mark_step_completed("1.1", "实现了登录验证功能")

# 4. Coder 写文件时记录变更
blackboard.record_file_change("src/auth/login.py", "created", "CODER")

# 5. 查询进度
progress = blackboard.get_formatted_progress()
# 输出:
# **项目进度**: 2/5 步骤完成 (40%)
# **当前执行**: 步骤 1.3
# **文件变更**: 新增 1 个，修改 2 个
```

### 6.3 工具过滤器

```python
class ToolFilter(ABC):
    """工具过滤器基类"""

    @abstractmethod
    def is_allowed(self, tool_name: str, action: str) -> bool:
        """检查工具/动作是否允许"""
        pass

class ReadOnlyFilter(ToolFilter):
    """只读过滤器 - Explorer 使用"""

    ALLOWED_TOOLS = {"Read", "Grep", "Glob"}
    ALLOWED_BASH = {"ls", "git status", "git log", "git diff", "find", "cat", "head", "tail"}

    def is_allowed(self, tool_name: str, action: str) -> bool:
        if tool_name in self.ALLOWED_TOOLS:
            return True
        if tool_name == "Bash" and action in self.ALLOWED_BASH:
            return True
        return False

class FullAccessFilter(ToolFilter):
    """完全访问过滤器 - Coder/Fixer 使用"""

    ALLOWED_TOOLS = {"Read", "Write", "Edit", "Grep", "Glob", "Bash"}
    DENIED_BASH = {"rm -rf", "mkfs", "chmod 777", "curl|bash"}

    def is_allowed(self, tool_name: str, action: str) -> bool:
        if tool_name not in self.ALLOWED_TOOLS:
            return False
        if tool_name == "Bash" and any(d in action for d in self.DENIED_BASH):
            return False
        return True
```

---

## 7. 配置示例

### 7.1 Agent 配置 (YAML)

```yaml
# config/agents.yaml

agents:
  explorer:
    name: Explorer
    description: "只读探索代码库；在需要查找文件、搜索实现、理解结构且不修改任何文件时使用"
    system_prompt_path: "knowledge-base/mini-coder-agent-prompts/subagent-explorer.md"
    tool_filter: "read_only"
    max_iterations: 10

  planner:
    name: Planner
    description: "需求分析与任务规划；在需要拆解复杂任务、制定实现计划时使用"
    system_prompt_path: "knowledge-base/mini-coder-agent-prompts/subagent-planner.md"
    tool_filter: "read_only"
    max_iterations: 15

  coder:
    name: Coder
    description: "代码实现；在需要实现新功能、写新代码、加新模块时使用"
    system_prompt_path: "knowledge-base/mini-coder-agent-prompts/subagent-coder.md"
    tool_filter: "full_access"
    max_iterations: 20

  reviewer:
    name: Reviewer
    description: "代码质量评审；在代码完成后评审质量、检查规范时使用"
    system_prompt_path: "knowledge-base/mini-coder-agent-prompts/subagent-reviewer.md"
    tool_filter: "read_only"
    max_iterations: 10

  bash:
    name: Bash
    description: "终端执行与测试验证；在需要运行测试、执行命令、验证质量时使用"
    system_prompt_path: "knowledge-base/mini-coder-agent-prompts/subagent-bash.md"
    tool_filter: "bash_restricted"
    max_iterations: 10
    bash_whitelist:
      - pytest
      - mypy
      - flake8
      - python
      - ls
      - cat
      - head
      - tail

main_agent:
  system_prompt_path: "knowledge-base/mini-coder-agent-prompts/main-agent.md"
```

### 7.2 工作流配置

```yaml
# config/workflow.yaml

workflow:
  max_retries: 3
  timeout_seconds: 600
  loop_detection_enabled: true

  stages:
    - name: analyze
      agent: planner
      description: "需求分析"
    - name: plan
      agent: planner
      description: "任务规划"
    - name: implement
      agent: coder
      description: "代码实现"
    - name: review
      agent: reviewer
      description: "代码评审"
    - name: test
      agent: bash
      description: "测试验证"

  transitions:
    review:
      passed: test
      failed: implement  # 打回重新实现
    test:
      passed: complete
      failed: implement  # 测试失败重新实现
```

---

## 8. 与现有代码的映射

### 8.1 当前代码结构

| 模块/类 | 路径 | 职责 | 与新架构对应 |
|--------|------|------|------------|
| **统一 Agent** | `orchestrator.run_unified()` | 四类决策、TDD 规划、派发驱动 | 替代原「主代理只出文本 + 路由再派发」 |
| **输出解析** | `agents/output_parser.py` | 解析 `[Simple Answer]` 等四类输出 | 新增，统一 Agent 专用 |
| **派发执行** | `orchestrator.dispatch_with_agent()` | 按解析结果创建并执行子代理 | 复用原有派发逻辑 |
| **Agent 基类** | `agents/base.py` | `BaseAgent`, `AgentConfig` | 子代理继承基类 |
| **子代理实现** | `agents/enhanced.py` | `PlannerAgent`, `CoderAgent`, `BashAgent` 等 | 5 个专业化子代理 |
| **工具过滤** | `tools/filter.py` | `ReadOnlyFilter`, `FullAccessFilter` | Explorer/Reviewer 用只读，Coder 用完全访问 |
| **黑板** | `agents/enhanced.py` | `Blackboard` 类 | 仅共享上下文与工件；Agent 间数据经 dispatch_context 显式传递，不再使用 Mailbox |
| **调试日志** | `utils/debug_logger.py` | 诊断 Agent 间上下文传递 | 新增，用于调试 |

### 8.2 核心流程：run_unified()

```python
def run_unified(self, user_message: str, context: Dict = None) -> EnhancedAgentResult:
    """统一 Planner-Orchestrator：先由统一 Agent 做四类决策，再按解析结果执行。"""
    # 1. 加载统一 Agent 提示词
    system_prompt = PromptLoader().load("unified-planner-orchestrator")

    # 2. 一次 LLM 调用
    response = self.llm_service.chat_one_shot(system_prompt, user_message)

    # 3. 解析输出
    parsed = parse_unified_output(response)

    # 4. 按四类决策执行
    if parsed.output_type == UnifiedOutputType.SIMPLE_ANSWER:
        return EnhancedAgentResult(success=True, output=parsed.content)

    if parsed.output_type == UnifiedOutputType.DIRECT_DISPATCH:
        return self.dispatch_with_agent(
            SubAgentType[parsed.direct_dispatch.agent],
            parsed.direct_dispatch.task,
            context=parsed.direct_dispatch.params
        )

    if parsed.output_type == UnifiedOutputType.COMPLEX_TASK:
        outputs = []
        for step in parsed.steps:
            result = self.dispatch_with_agent(
                SubAgentType[step.agent],
                step.task,
                context=step.params
            )
            outputs.append(result.output)
        return EnhancedAgentResult(success=True, output="\n".join(outputs))

    if parsed.output_type == UnifiedOutputType.CANNOT_HANDLE:
        return EnhancedAgentResult(success=True, output=parsed.content)

    return EnhancedAgentResult(success=True, output=parsed.raw_text)
```

### 8.3 TUI 路由变化

**旧流程（已废弃）**：
```
用户输入 → console_app._route_user_input() → orchestrator.dispatch()
         → _analyze_intent()（关键词 + LLM 兜底） → 创建子代理 → 执行
```

**新流程（统一 Agent）**：
```
用户输入 → console_app.main 路由 → orchestrator.run_unified()
         → 统一 Agent LLM 调用（一次完成决策与规划）
         → parse_unified_output() 解析
         → 按 [Simple Answer] / [Direct Dispatch] / [Complex Task] / [Cannot Handle] 执行
```

---

## 9. 终端命令执行安全设计

### 9.1 执行权限

- **仅主代理可发起终端执行**
- 子代理 Bash 可"请求运行测试或命令"，但由主代理代为执行

### 9.2 命令分类

| 类别 | 命令示例 | 执行策略 |
|------|---------|---------|
| **白名单** | pytest, mypy, flake8, python -m, ls, cat | 直接执行 |
| **需确认** | pip install, git commit, npm install | 用户确认后执行 |
| **黑名单** | rm -rf, mkfs, chmod 777, curl\|bash | 禁止执行 |

### 9.3 安全原则

1. 不执行未确认的破坏性命令
2. 不将未经验证的用户输入直接拼接到 shell 命令
3. 长时间或高风险命令需明确提示用户
4. 输出截断：长输出做摘要，避免占满上下文

---

## 10. 参考来源

- Claude Code 主代理与 Built-in 子代理：https://code.claude.com/docs/en/sub-agents
- 子代理提示词结构参考：Piebald-AI/claude-code-system-prompts
- 本项目：
  - `docs/command-execution-security-design.md` - 终端命令执行安全设计
  - `docs/context-memory-design.md` - 记忆系统设计
  - `knowledge-base/mini-coder-agent-prompts/implementation-mechanism.md` - Claude 主/子代理实现机制
  - `knowledge-base/mini-coder-agent-prompts/design-spec.md` - 提示词与设计规格

---

## 附录 A：提示词模板示例

### A.1 统一 Planner-Orchestrator 提示词模板

```markdown
# Unified Planner-Orchestrator Agent

**Role**: 接收用户消息后做四类决策：自己直接回答、直接派发单个子代理、
复杂任务拆成多步并指定每步由谁做（及参数）、或无法完成且需用户澄清。

**When to use**: 用户每轮自然语言输入均由本 Agent 先处理；不写代码、
不执行命令，只做决策与规划，并驱动子代理执行。

---

## 四类决策（输出必须且仅能选其一）

1. **自己直接回答**：寒暄、概念性问答、无需工具与改代码的解释。
2. **直接派发**：明确由**一个**子代理即可完成，且任务与参数清晰。
3. **复杂任务**：需多步、多子代理协作；拆成子任务并标明每步由哪个 Agent 做。
4. **无法完成**：当前无法完成且没有合适子代理可完成，需用户澄清。

---

## 子代理列表

EXPLORER, PLANNER, CODER, REVIEWER, BASH, MINI_CODER_GUIDE, GENERAL_PURPOSE

---

## 输出格式

[Simple Answer] / [Direct Dispatch] / [Complex Task] / [Cannot Handle]
```

### A.2 Explorer 提示词模板

```markdown
你是 Coding Agent 的**只读探索专家**。

=== 严格约束：只读模式 ===
禁止：创建/修改/删除文件、执行会改变系统状态的命令
仅能：Read, Grep, Glob, Bash(只读操作)

允许的 Bash 命令：ls, git status, git log, git diff, find, cat, head, tail

=== 行为准则 ===
- 根据探索深度 ({{thoroughness}}) 调整搜索范围
- 所有文件路径使用**绝对路径**
- 回复简洁，避免 emoji
- 并行发起多次搜索提高效率

=== 输出要求 ===
汇报：找到了哪些文件/位置、关键代码或结构结论
若有建议关注的文件，明确列出并注明原因
```

### A.3 Coder 提示词模板

```markdown
你是 Coding Agent 的**代码实现专家**。

=== 能力 ===
- 代码生成：编写新功能代码
- 代码编辑：修改现有代码（优先编辑而非新建）
- 测试编写：编写单元测试

=== 行为准则 ===
- 优先编辑已有文件，必要时才创建新文件
- 遵循项目风格：{{coding_standards}}
- 不主动写文档（除非明确要求）
- 回复中引用文件使用绝对路径

=== 输出要求 ===
简要总结修改了哪些文件、实现了什么行为
若有未完成或需后续处理的事项，明确说明

可写入记忆的摘要：...
```
