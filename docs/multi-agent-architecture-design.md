# Mini-Coder 多 Agent 系统架构设计

> **版本**: 2.0
> **最后更新**: 2026-03-04
> **设计目标**: 基于"代码框架 + 动态提示词注入"混合模式，实现 5 个专业化子代理的 coding agent 系统

---

## 1. 架构概览

### 1.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         主代理 (Main Agent)                              │
│  身份：协调者 + 记忆管理 + 终端执行                                       │
│  能力：理解意图、派发子代理、读写记忆、执行命令（带安全策略）               │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ 按任务类型派发
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│   Explorer    │     │    Planner    │     │    Coder      │
│  (只读探索)    │     │  (规划分析)   │     │ (代码生成)     │
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
| **主代理** | 协调者、记忆与终端执行 | 全部（含记忆、终端、派发子代理） | 理解请求、派发、汇总、执行命令、更新记忆 |
| **Explorer** | 只读代码库搜索 | Read, Grep, Glob | 需要"先搞清楚代码结构/位置"且不修改时 |
| **Planner** | 需求分析与任务规划 | Read, Grep, WebSearch | 需要拆解复杂任务、制定实现计划时 |
| **Coder** | 代码生成与编辑 | Read, Write, Edit, Grep, Glob | 实现新功能、按需求写代码 |
| **Reviewer** | 代码质量评审 | Read, Grep, Glob | 代码完成后评审质量、检查规范 |
| **Bash** | 终端执行与测试验证 | Read, Bash, Glob | 运行测试、执行命令、验证质量 |

### 1.3 实现机制："代码框架 + 动态提示词注入"

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
主代理提示词 = 身份段 + 派发规则段 + 记忆段 + 终端安全段 + 输出段
子代理提示词 = 身份段 + 工具约束段 + 行为准则段 + 输出要求段
```

**动态插值占位符**:
- `{{GLOB_TOOL_NAME}}` → 实际工具名（如 `Glob`）
- `{{thoroughness}}` → `quick` / `medium` / `thorough`（Explorer 探索深度）
- `{{project_name}}` → 从 CLAUDE.md 读取的项目名称
- `{{coding_standards}}` → 从 CLAUDE.md 读取的编码规范

---

## 3. 各 Agent 详细设计

### 3.1 主代理 (Main Agent)

**身份与角色**:
```
你是简易 Coding Agent 的主代理，负责：
1. 协调者 - 理解用户请求，派发合适的子代理
2. 记忆管理 - 读取/写入持久记忆，保留项目要点、用户偏好
3. 终端执行 - 在安全策略下执行终端命令
```

**工具权限**: 全部工具（包括子代理派发、记忆读写、终端命令执行）

**派发规则**:
```
用户请求 → 主代理分析 → 派发决策

├─ "看看/找找/分析代码结构" → Explorer
├─ "规划/拆解/设计/方案" → Planner
├─ "实现/添加/修改/写代码" → Coder
├─ "评审/检查/质量/规范" → Reviewer
└─ "测试/运行/执行命令" → Bash
```

**记忆读写时机**:
```
会话开始 → 主代理读取相关记忆 → 用于理解上下文
    │
    └─→ 子代理执行任务
         │
         └─→ 主代理汇总 → 解析「可写入记忆的摘要」→ 写入记忆
```

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

### 4.1 标准工作流（完整流程）

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户请求                                   │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                       主代理分析                                  │
│  1. 理解意图  2. 检查记忆  3. 决定派发策略                        │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
   ┌──────────┐     ┌──────────┐     ┌──────────┐
   │ Explorer │     │ Planner  │     │  Coder   │
   │  探索    │ ──▶ │  规划    │ ──▶ │  实现    │
   └──────────┘     └──────────┘     └────┬─────┘
                                          │
                                          ▼
                                   ┌──────────────┐
                                   │  Reviewer    │
                                   │   评审       │
                                   └──────┬───────┘
                                          │
                            ┌─────────────┴─────────────┐
                            │ 通过？                     │
                            │ 是 ↓    │    否 ↓         │
                            ▼         ▼                 ▼
                     ┌────────────┐            ┌────────────┐
                     │    Bash    │            │   Coder    │
                     │   测试验证  │            │   修正     │
                     └─────┬──────┘            └─────┬──────┘
                           │                         │
                           │         ┌───────────────┘
                           │         ▼
                           │    ┌──────────┐
                           └───▶│ Reviewer │ (再次评审)
                                └──────────┘
                                     │
                                     ▼
                               ┌────────────┐
                               │   完成     │
                               │ 更新记忆   │
                               └────────────┘
```

### 4.2 简化工作流（简单任务）

```
用户请求 → 主代理 → Coder → Reviewer → Bash → 完成
         (直接派发，跳过规划)
```

适用于：小修复、单文件修改、明确的代码添加

### 4.3 探索工作流（复杂任务）

```
用户请求 → 主代理 → Explorer → Planner → Coder → Reviewer → Bash → 完成
         (先探索代码结构)  (再制定计划)   (再实现)
```

适用于：新功能开发、跨模块修改、需要理解现有代码的任务

### 4.4 修复工作流（Bug 修复）

```
用户请求 + 报错信息 → 主代理 → Fixer(Bash 角色) → Reviewer → Bash → 完成
                      (直接派发修复)      (验证修复)
```

适用于：有明确报错信息的 Bug 修复

---

## 5. 提示词文件结构

### 5.1 文件组织

```
mini-coder/
├── docs/
│   └── knowledge-base/mini-coder-agent-prompts/
│       ├── main-agent.md              # 主代理系统提示词
│       ├── subagent-explorer.md       # Explorer 子代理系统提示词
│       ├── subagent-planner.md        # Planner 子代理系统提示词
│       ├── subagent-coder.md          # Coder 子代理系统提示词
│       ├── subagent-reviewer.md       # Reviewer 子代理系统提示词
│       └── subagent-bash.md           # Bash 子代理系统提示词
├── config/
│   └── agents.yaml                    # Agent 配置（可选）
└── src/mini_coder/
    └── agents/
        ├── __init__.py
        ├── base.py                    # Agent 基类
        ├── main.py                   # 主代理
        ├── explorer.py               # Explorer 子代理
        ├── planner.py                # Planner 子代理
        ├── coder.py                  # Coder 子代理
        ├── reviewer.py               # Reviewer 子代理
        ├── bash.py                   # Bash 子代理
        └── blackboard.py             # 黑板模式
```

### 5.2 提示词加载与插值

**加载方式**（混合方案）:
```python
class PromptLoader:
    """提示词加载器"""

    def __init__(self, prompt_dir: str = "knowledge-base/mini-coder-agent-prompts"):
        self.prompt_dir = Path(prompt_dir)
        self._cache: Dict[str, str] = {}

    def load(self, agent_type: str, context: Dict = None) -> str:
        """加载并插值提示词"""
        # 1. 从缓存或文件读取
        if agent_type not in self._cache:
            file_path = self.prompt_dir / f"{agent_type}.md"
            self._cache[agent_type] = file_path.read_text(encoding="utf-8")

        # 2. 占位符替换
        prompt = self._cache[agent_type]
        if context:
            for key, value in context.items():
                prompt = prompt.replace(f"{{{{{key}}}}}", str(value))

        return prompt
```

**占位符示例**:
```markdown
你是 {{AGENT_NAME}} Agent。

可用工具：{{ALLOWED_TOOLS}}
探索深度：{{thoroughness}}
项目规范：{{coding_standards}}
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

### 6.2 黑板模式（共享上下文）

```python
class Blackboard:
    """共享黑板 - Agent 间共享上下文和工件"""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self._artifacts: Dict[str, Any] = {}
        self._context: Dict[str, Any] = {}
        self._event_log: List[Event] = []

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
| **主代理/协调层** | `src/mini_coder/agents/orchestrator.py` | 工作流状态机、派发子代理 | 主代理"理解请求、派发、汇总" |
| **Agent 基类** | `src/mini_coder/agents/base.py` | `BaseAgent`, `AgentConfig` | 子代理继承基类 |
| **子代理实现** | `src/mini_coder/agents/enhanced.py` | `PlannerAgent`, `CoderAgent`, `TesterAgent` | 可扩展为 5 个独立子代理 |
| **工具过滤** | `src/mini_coder/tools/filter.py` | `ReadOnlyFilter`, `FullAccessFilter` | Explorer 用只读，Coder/Fixer 用完全访问 |
| **黑板** | `src/mini_coder/agents/enhanced.py` | `Blackboard` 类 | 共享上下文 |

### 8.2 扩展建议

若引入新的 5 子代理模式（Explorer, Planner, Coder, Reviewer, Bash），可：

1. **新增独立 Agent 类**:
   - 在 `enhanced.py` 或独立文件中创建 `ExplorerAgent`, `PlannerAgent`, `CoderAgent`, `ReviewerAgent`, `BashAgent`
   - 每个类继承 `BaseEnhancedAgent`
   - 覆盖 `get_system_prompt()` 返回对应提示词

2. **工具过滤器映射**:
   - `ExplorerAgent` → `ReadOnlyFilter`
   - `PlannerAgent` → `ReadOnlyFilter`（或宽松一些）
   - `CoderAgent` → `FullAccessFilter`
   - `ReviewerAgent` → `ReadOnlyFilter`
   - `BashAgent` → 自定义 `BashRestrictedFilter`

3. **主代理逻辑**（在 `orchestrator.py`）:
   - 根据用户输入决定派发哪个子代理
   - 创建对应 Agent 实例，注入任务与上下文
   - 执行并收集 `AgentResult`
   - 汇总并可选写记忆

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

### A.1 主代理提示词模板

```markdown
## 身份与角色

你是简易 Coding Agent 的主代理，负责：
1. 协调者 - 理解用户请求，派发合适的子代理
2. 记忆管理 - 读取/写入持久记忆
3. 终端执行 - 在安全策略下执行终端命令

## 派发规则

- **Explorer**: "看看/找找/分析代码结构" → 只读探索
- **Planner**: "规划/拆解/设计/方案" → 任务规划
- **Coder**: "实现/添加/修改/写代码" → 代码实现
- **Reviewer**: "评审/检查/质量/规范" → 代码评审
- **Bash**: "测试/运行/执行命令" → 终端执行

## 记忆系统

读取：会话开始读取相关记忆
写入：子代理完成后，解析「可写入记忆的摘要」并保存

## 终端命令执行

仅你可发起终端执行
白名单：pytest, mypy, flake8, python, ls, cat
需确认：pip install, git commit
黑名单：rm -rf, mkfs, chmod 777

## 输出与汇总

子代理返回后，用简洁自然语言汇报结果
引用文件使用绝对路径或项目内相对路径
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
