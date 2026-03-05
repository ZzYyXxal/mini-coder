# Claude Code 子代理架构研究与 mini-coder 实现方案

> **研究日期**: 2026-03-04
> **来源**: Claude Code 官方文档 + 社区逆向工程 + 项目现有设计
> **目标**: 基于 Claude Code 的子代理架构，设计 mini-coder 的 5 子代理系统

---

## 第一部分：Claude Code 子代理架构研究

### 1. 实现机制结论

**"代码框架 + 动态提示词注入"混合模式**

| 层面 | 实现方式 | 说明 |
|------|---------|------|
| **执行流程** | 代码硬编码 | 工具循环、上下文管理由 TypeScript 源码实现 |
| **身份定义** | 系统提示词 | 约 3100 个 token 的内置系统提示词文件 |
| **内置子代理** | 代码 + 提示词模板 | 结构定义在代码，职责在 Markdown/YAML 模板 |
| **自定义代理** | 独立文件 | `~/.claude/agents/` 目录下的 Markdown 文件 |

**核实修正**:
- 内置提示词在分发包中**并非独立资源文件**，而是**打包在 minified JavaScript 中**
- 社区仓库 [Piebald-AI/claude-code-system-prompts](https://github.com/Piebald-AI/claude-code-system-prompts) 从编译后的源码中提取了这些提示词
- 运行时，代码从打包的字符串中**选取、拼接、插值**生成子代理的 system prompt

### 2. Claude Code 内置子代理类型

| 子代理 | 用途 | 工具范围 | 模型 | 触发条件 |
|--------|------|----------|------|---------|
| **Explore** | 只读代码库搜索与分析 | 只读（无 Write/Edit） | Haiku（低延迟） | 需要"搜索/理解代码库"且不修改时 |
| **Plan** | 规划模式下做代码库研究与实现方案设计 | 只读 | 继承主会话 | Plan 模式下需先理解再出方案时 |
| **General-purpose** | 复杂多步任务（探索 + 修改） | 全部 | 继承主会话 | 需既探索又修改、或多步依赖时 |

### 3. 子代理提示词结构（从社区逆向工程）

#### 3.1 Explore Agent

```markdown
You are an expert code explorer. Your task is to understand the codebase structure.

**Capabilities:**
- Search for files using Glob patterns
- Search for code content using Grep
- Read file contents

**Constraints:**
- DO NOT modify any files
- DO NOT create, delete, or edit files
- Focus on finding relevant files and code patterns

**Output:**
Report what you found with file paths and key code snippets.
```

#### 3.2 Plan Agent

```markdown
You are an expert software planner. Your task is to create an implementation plan.

**Capabilities:**
- Analyze requirements
- Break down tasks into atomic steps
- Identify dependencies
- Recommend technical approaches

**Output Format:**
1. Overview
2. Task breakdown (TDD: test first)
3. Dependencies
4. Technical recommendations
```

#### 3.3 Task (General-purpose) Agent

```markdown
You are an expert coder. Your task is to implement features or fix issues.

**Capabilities:**
- Read and understand existing code
- Write new code
- Edit existing code
- Run tests and commands

**Guidelines:**
- Follow existing project style
- Prefer editing over creating new files
- Write tests for new functionality
```

### 4. 动态提示词注入机制

```
┌─────────────────────────────────────────────────────────────┐
│              Claude Code 分发包 (minified JS)                │
│  - 主代理提示词常量 (MAIN_AGENT_SYSTEM_PROMPT)                │
│  - Explore 提示词常量 (EXPLORE_AGENT_SYSTEM_PROMPT)           │
│  - Plan 提示词常量 (PLAN_AGENT_SYSTEM_PROMPT)                 │
│  - Task 提示词常量 (TASK_AGENT_SYSTEM_PROMPT)                 │
│  - 动态插值逻辑：prompt.replace(/\{\{(\w+)\}\}/g, ...)      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
                    运行时加载并插值
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    注入的变量                                 │
│  - {{GLOB_TOOL_NAME}} → "Glob"                               │
│  - {{GREP_TOOL_NAME}} → "Grep"                               │
│  - {{thoroughness}} → "quick" / "medium" / "thorough"       │
│  - {{CLAUDE_MD_CONTENT}} → 从项目 CLAUDE.md 读取              │
└─────────────────────────────────────────────────────────────┘
```

---

## 第二部分：mini-coder 实现方案

### 1. 架构设计

#### 1.1 整体架构

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

#### 1.2 实现机制选择

**方案 C: 混合模式**（推荐）

| 组件 | 存放位置 | 理由 |
|------|---------|------|
| **主代理核心逻辑** | 代码内常量 | 执行流程、工具循环，需高可靠性 |
| **子代理提示词** | `knowledge-base/mini-coder-agent-prompts/*.md` | 便于迭代、审计、多语言 |
| **动态插值** | 运行时处理 | 根据上下文注入工具名、探索深度等 |
| **项目规范注入** | CLAUDE.md 动态读取 | 实现项目级定制 |

### 2. 5 个子代理设计

#### 2.1 Agent 总览

| 角色 | 身份 | 工具范围 | 过滤器 | 何时使用 |
|------|------|----------|--------|---------|
| **Explorer** | 只读代码库搜索 | Read, Grep, Glob | ReadOnlyFilter | 需要先搞清楚代码结构/位置且不修改时 |
| **Planner** | 需求分析与任务规划 | Read, Grep, WebSearch | ReadOnlyFilter | 需要拆解复杂任务、制定实现计划时 |
| **Coder** | 代码生成与编辑 | Read, Write, Edit, Grep, Glob | FullAccessFilter | 实现新功能、按需求写代码时 |
| **Reviewer** | 代码质量评审 | Read, Grep, Glob | ReadOnlyFilter | 代码完成后评审质量、检查规范时 |
| **Bash** | 终端执行与测试验证 | Read, Bash, Glob | BashRestrictedFilter | 运行测试、执行命令、验证质量时 |

#### 2.2 Explorer (只读探索)

**系统提示词模板** (`knowledge-base/mini-coder-agent-prompts/subagent-explorer.md`):

```markdown
# 身份

你是 Coding Agent 的**只读探索专家**，专门负责在代码库中快速查找文件、搜索内容、理解结构和依赖关系。

# 严格约束：只读模式

本任务为**只读探索**，你**禁止**进行以下任何操作：

- 创建新文件（禁止 Write、touch 或任何形式的文件创建）
- 修改已有文件（禁止 Edit、sed、awk 等改写操作）
- 删除、移动、复制文件（禁止 rm、mv、cp）
- 在任意目录（包括 /tmp）创建临时文件
- 使用重定向或 heredoc 向文件写入（禁止 `>`、`>>`、`|` 写文件）
- 执行任何会改变系统状态的命令（禁止 git add/commit、npm install、pip install、mkdir 等）

你**仅能**使用只读类工具：{{READ_TOOL_NAME}}、{{GREP_TOOL_NAME}}、{{GLOB_TOOL_NAME}}

# 能力与工具使用

- **文件匹配**：使用 Glob 按模式快速匹配文件路径
- **内容搜索**：使用 Grep 按正则或关键词在文件中搜索
- **读取文件**：在已知路径时使用 Read 读取文件内容
- **只读命令**：Bash 仅用于只读操作：ls、git status、git log、git diff、find、cat、head、tail 等

# 行为准则

- 根据调用方指定的"探索深度"（{{thoroughness}}）调整搜索范围与细致程度
- 在最终回复中，所有文件路径使用**绝对路径**，便于主代理与用户定位
- 回复简洁清晰，避免使用 emoji；直接以普通消息汇报发现
- 为加快响应，在互不依赖时尽量**并行**发起多次 Grep 或 Read，提高效率

# 输出要求

完成探索后，用一条清晰的消息汇报：找到了哪些文件/位置、关键代码或结构结论、与请求的对应关系。
若有"建议主代理或 Coder/Fixer 关注的文件"，可明确列出并注明原因。
```

**工具权限** (`ReadOnlyFilter`):

```python
class ReadOnlyFilter(ToolFilter):
    """只读过滤器 - Explorer/Planner/Reviewer 使用"""

    ALLOWED_TOOLS = {"Read", "Grep", "Glob"}
    ALLOWED_BASH = {"ls", "git status", "git log", "git diff", "find", "cat", "head", "tail"}

    def is_allowed(self, tool_name: str, action: str) -> bool:
        if tool_name in self.ALLOWED_TOOLS:
            return True
        if tool_name == "Bash" and any(cmd in action for cmd in self.ALLOWED_BASH):
            return True
        return False
```

#### 2.3 Planner (规划分析)

**系统提示词模板** (`knowledge-base/mini-coder-agent-prompts/subagent-planner.md`):

```markdown
# 身份

你是 Coding Agent 的**规划专家**，负责将模糊的自然语言需求拆解为符合 TDD 规则的原子化步骤。

# 核心能力

1. **需求分析** - 理解用户需求，识别边界条件
2. **任务分解** - 拆解为可执行的原子步骤（TDD：测试优先）
3. **技术选型** - 推荐合适的技术方案
4. **依赖分析** - 识别模块依赖关系

# 输出格式

创建 `implementation_plan.md` 文件，包含：

## 概述
[任务简述]

## 阶段划分

### 阶段 1: [名称]
- [ ] 步骤 1.1 [测试步骤]
- [ ] 步骤 1.2 [实现步骤]

## TDD 规则

**强制要求**：
1. 所有实现步骤前必须先编写测试
2. 测试必须明确断言和边界条件
3. 实现代码必须通过所有测试

## 依赖关系

| 步骤 | 前置步骤 | 并行安全 |
|------|---------|----------|
| 1.1 | 无 | 否 |
```

**工具权限** (`ReadOnlyFilter`，可扩展):

```python
class PlannerFilter(ReadOnlyFilter):
    """Planner 专用过滤器 - 在只读基础上增加 WebSearch"""

    ALLOWED_TOOLS = {"Read", "Grep", "Glob", "WebSearch", "WebFetch"}
```

#### 2.4 Coder (代码实现)

**系统提示词模板** (`knowledge-base/mini-coder-agent-prompts/subagent-coder.md`):

```markdown
# 身份

你是 Coding Agent 的**代码实现专家**，负责根据需求或规格编写、修改代码。

# 核心能力

- **代码生成**：编写新功能代码
- **代码编辑**：修改现有代码（优先编辑而非新建）
- **测试编写**：编写单元测试

# 行为准则

- **优先编辑而非新建**：能通过编辑现有文件完成的，不创建新文件
- **不主动写文档**：除非明确要求，不主动创建或更新 README、设计文档等
- **风格一致**：遵循项目既有风格（命名、缩进、注释语言等）
  {{coding_standards}}
- **路径与回复**：在回复中引用文件时使用**绝对路径**

# 输出要求

完成后给出简要总结：修改了哪些文件、实现了什么行为、是否有未完成或需主代理/用户后续处理的事项。

若主代理需要"可写入记忆的摘要"，在结尾用固定格式附一段简短摘要：

[可写入记忆的摘要]
- 关键文件：src/path/to/file.py
- 实现要点：...
- 注意事项：...
```

**工具权限** (`FullAccessFilter`):

```python
class FullAccessFilter(ToolFilter):
    """完全访问过滤器 - Coder 使用"""

    ALLOWED_TOOLS = {"Read", "Write", "Edit", "Grep", "Glob", "Bash"}
    DENIED_BASH = {"rm -rf", "mkfs", "chmod 777", "curl|bash", "dd", ">"}

    def is_allowed(self, tool_name: str, action: str) -> bool:
        if tool_name not in self.ALLOWED_TOOLS:
            return False
        if tool_name == "Bash" and any(d in action for d in self.DENIED_BASH):
            return False
        return True
```

#### 2.5 Reviewer (代码评审)

**系统提示词模板** (`knowledge-base/mini-coder-agent-prompts/subagent-reviewer.md`):

```markdown
# 身份

你是 Coding Agent 的**代码质量评审专家**，负责在代码实现完成后进行架构对齐检查和代码质量评审。

# 评审清单

## 1. 架构对齐检查

- 代码是否遵循 implementation_plan.md？
- 模块边界是否清晰？
- 依赖方向是否符合约束？

## 2. 代码质量检查

- **类型提示**：所有函数有完整类型标注（Python 3.10+ 语法）
- **文档字符串**：Google 风格，覆盖所有公共 API
- **命名**：清晰、描述性的名称，符合 PEP 8
- **复杂度**：识别过长函数 (>50 行)、过度复杂逻辑
- **重复**：识别重复逻辑

# 输出格式

**严格二选一**:

### 通过
【通过】代码符合架构和质量要求，可进入 Bash 测试验证

### 打回
【打回】需要修改以下问题：

1. [架构偏离] 具体文件：行号 - 问题描述 + 修改建议
2. [代码质量] 具体文件：行号 - 问题描述 + 修改建议
3. [规范违反] 具体文件：行号 - 问题描述 + 修改建议
```

**工具权限** (`ReadOnlyFilter`):

```python
# Reviewer 使用 ReadOnlyFilter，不能修改代码
```

#### 2.6 Bash (终端执行 + 测试验证)

**系统提示词模板** (`knowledge-base/mini-coder-agent-prompts/subagent-bash.md`):

```markdown
# 身份

你是 Coding Agent 的**终端执行与质量验证专家**，负责运行测试、执行命令、验证代码质量。

# 核心能力

1. **终端命令执行**（受限白名单）
2. **运行测试** - pytest
3. **类型检查** - mypy
4. **代码风格检查** - flake8
5. **覆盖率检查** - pytest --cov

# 命令白名单

| 类别 | 命令示例 | 执行策略 |
|------|---------|---------|
| **测试** | pytest, python -m pytest | 直接执行 |
| **类型检查** | mypy, python -m mypy | 直接执行 |
| **代码风格** | flake8, black --check | 直接执行 |
| **信息查看** | ls, cat, head, tail, pwd | 直接执行 |
| **Python 执行** | python, python -m | 直接执行 |

# 命令黑名单 (禁止执行)

- rm -rf, mkfs, chmod 777, curl|bash 等危险命令
- 需要用户确认：pip install, git commit, npm install

# 输出格式

生成质量报告：

## 测试结果
✅ 所有测试通过 / ❌ 测试失败 (详情)

## 类型检查
✅ 无类型错误 / ❌ 类型错误 (详情)

## 代码风格
✅ 无风格问题 / ❌ 风格问题 (详情)

## 覆盖率
✅ 覆盖率 >= 80% / ⚠️ 覆盖率不足 (详情)
```

**工具权限** (`BashRestrictedFilter`):

```python
class BashRestrictedFilter(ToolFilter):
    """Bash 专用过滤器 - 受限的命令执行"""

    ALLOWED_TOOLS = {"Read", "Bash", "Glob"}
    BASH_WHITELIST = {
        "pytest", "python -m pytest",
        "mypy", "python -m mypy",
        "flake8", "black --check",
        "python", "python -m",
        "ls", "cat", "head", "tail", "pwd", "whoami",
    }
    BASH_BLACKLIST = {"rm -rf", "mkfs", "chmod 777", "curl|bash", "dd", ">"}

    def is_allowed(self, tool_name: str, action: str) -> bool:
        if tool_name not in self.ALLOWED_TOOLS:
            return False
        if tool_name == "Bash":
            # 黑名单优先
            if any(d in action for d in self.BASH_BLACKLIST):
                return False
            # 白名单检查
            if not any(cmd in action for cmd in self.BASH_WHITELIST):
                return False  # 不在白名单的命令需要用户确认
        return True
```

### 3. 代码框架设计

#### 3.1 提示词加载器

```python
# src/mini_coder/agents/prompt_loader.py

from pathlib import Path
from typing import Dict, Optional

class PromptLoader:
    """提示词加载器 - 实现"动态提示词注入""""

    DEFAULT_PROMPT_DIR = "knowledge-base/mini-coder-agent-prompts"

    def __init__(self, prompt_dir: Optional[str] = None):
        self.prompt_dir = Path(prompt_dir or self.DEFAULT_PROMPT_DIR)
        self._cache: Dict[str, str] = {}

    def load(self, agent_type: str, context: Dict = None) -> str:
        """加载并插值提示词"""
        # 1. 从缓存或文件读取
        if agent_type not in self._cache:
            file_path = self.prompt_dir / f"subagent-{agent_type}.md"
            if file_path.exists():
                self._cache[agent_type] = file_path.read_text(encoding="utf-8")
            else:
                self._cache[agent_type] = self._get_default_prompt(agent_type)

        # 2. 占位符替换
        prompt = self._cache[agent_type]
        if context:
            for key, value in context.items():
                prompt = prompt.replace(f"{{{{{key}}}}}", str(value))

        return prompt

    def _get_default_prompt(self, agent_type: str) -> str:
        """获取默认提示词（内置兜底）"""
        # 此处可放置代码内常量提示词，作为文件不存在时的兜底
        defaults = {
            "explorer": EXPLORER_DEFAULT_PROMPT,
            "planner": PLANNER_DEFAULT_PROMPT,
            "coder": CODER_DEFAULT_PROMPT,
            "reviewer": REVIEWER_DEFAULT_PROMPT,
            "bash": BASH_DEFAULT_PROMPT,
        }
        return defaults.get(agent_type, "")
```

#### 3.2 动态插值上下文

```python
# 主代理在派发子代理时构建的上下文

def build_subagent_context(
    agent_type: str,
    task: str,
    exploration_result: str = None,
    user_preferences: Dict = None,
    project_standards: str = None,
) -> Dict[str, str]:
    """构建子代理提示词插值上下文"""

    context = {
        # 工具名（可与实际工具注册表对齐）
        "READ_TOOL_NAME": "Read",
        "GREP_TOOL_NAME": "Grep",
        "GLOB_TOOL_NAME": "Glob",
        "WRITE_TOOL_NAME": "Write",
        "EDIT_TOOL_NAME": "Edit",
        "BASH_TOOL_NAME": "Bash",

        # 探索深度（Explorer 专用）
        "thoroughness": "medium",  # quick / medium / thorough

        # 编码规范（Coder 专用）
        "coding_standards": project_standards or """
- 4 空格缩进
- 行长度 <= 79
- snake_case 命名
- 完整类型提示
- Google 风格文档字符串
""",

        # 任务描述
        "task_description": task,

        # 探索结论（若有）
        "exploration_result": exploration_result or "",
    }

    return context
```

#### 3.3 子代理基类

```python
# src/mini_coder/agents/base.py (扩展现有 base.py)

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

@dataclass
class AgentConfig:
    """Agent 配置"""
    name: str
    description: str
    tool_filter: str  # "read_only", "full_access", "bash_restricted"
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

### 4. 工作流设计

#### 4.1 标准工作流

```
用户请求 → 主代理分析
    │
    ├─ 需要探索？ → Explorer → 探索结论
    │
    ├─ 需要规划？ → Planner → implementation_plan.md
    │
    ├─ 需要实现？ → Coder → 代码工件
    │
    ├─ 需要评审？ → Reviewer → 通过/打回
    │   │
    │   └─ 打回 → Coder (修正)
    │
    └─ 需要测试？ → Bash → 质量报告
        │
        └─ 失败 → Coder (修正)
```

#### 4.2 主代理派发逻辑

```python
# src/mini_coder/agents/orchestrator.py (扩展现有 orchestrator.py)

class MainAgent:
    """主代理 - 协调者"""

    def __init__(self, llm_service, blackboard, prompt_loader: PromptLoader):
        self.llm_service = llm_service
        self.blackboard = blackboard
        self.prompt_loader = prompt_loader
        self.subagents: Dict[str, BaseAgent] = {}

    def _create_subagent(self, agent_type: str, context: Dict) -> BaseAgent:
        """创建子代理实例"""
        config = self._get_agent_config(agent_type)
        system_prompt = self.prompt_loader.load(agent_type, context)
        config.system_prompt = system_prompt

        # 根据类型创建对应子代理
        factories = {
            "explorer": ExplorerAgent,
            "planner": PlannerAgent,
            "coder": CoderAgent,
            "reviewer": ReviewerAgent,
            "bash": BashAgent,
        }
        factory = factories.get(agent_type)
        if not factory:
            raise ValueError(f"Unknown agent type: {agent_type}")

        return factory(self.llm_service, self.blackboard, config)

    def dispatch(self, intent: str, context: Dict = None) -> AgentResult:
        """派发任务到合适的子代理"""
        # 1. 分析意图，决定派发哪个子代理
        agent_type = self._analyze_intent(intent)

        # 2. 创建子代理
        subagent = self._create_subagent(agent_type, context or {})

        # 3. 执行
        result = subagent.execute(intent)

        # 4. 处理「可写入记忆的摘要」
        if result.memory_summary:
            self._write_to_memory(result.memory_summary)

        # 5. 汇总输出
        return self._summarize_result(result)

    def _analyze_intent(self, intent: str) -> str:
        """分析用户意图，决定派发哪个子代理"""
        intent = intent.lower()

        # 关键词匹配 + LLM 辅助决策
        if any(kw in intent for kw in ["看看", "找找", "搜索", "探索", "explore"]):
            return "explorer"
        elif any(kw in intent for kw in ["规划", "计划", "拆解", "方案", "plan"]):
            return "planner"
        elif any(kw in intent for kw in ["实现", "写代码", "添加", "修改", "implement"]):
            return "coder"
        elif any(kw in intent for kw in ["评审", "检查", "质量", "review"]):
            return "reviewer"
        elif any(kw in intent for kw in ["测试", "运行", "执行", "test", "bash"]):
            return "bash"
        else:
            # 默认：让 LLM 决策
            return self._llm_decide_intent(intent)
```

### 5. 配置文件

#### 5.1 Agent 配置 (YAML)

```yaml
# config/agents.yaml

agents:
  explorer:
    name: Explorer
    description: "只读探索代码库；在需要查找文件、搜索实现、理解结构且不修改任何文件时使用"
    system_prompt_path: "knowledge-base/mini-coder-agent-prompts/subagent-explorer.md"
    tool_filter: "read_only"
    max_iterations: 10
    context_defaults:
      thoroughness: "medium"

  planner:
    name: Planner
    description: "需求分析与任务规划；在需要拆解复杂任务、制定实现计划时使用"
    system_prompt_path: "knowledge-base/mini-coder-agent-prompts/subagent-planner.md"
    tool_filter: "planner"  # 只读 + WebSearch
    max_iterations: 15

  coder:
    name: Coder
    description: "代码实现；在需要实现新功能、写新代码、加新模块时使用"
    system_prompt_path: "knowledge-base/mini-coder-agent-prompts/subagent-coder.md"
    tool_filter: "full_access"
    max_iterations: 20
    context_defaults:
      coding_standards: "config/coding-standards.md"

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
```

#### 5.2 项目规范注入

```yaml
# config/coding-standards.md (示例)

# Python 编码规范

## 命名
- 函数/变量：snake_case
- 类：PascalCase
- 常量：UPPER_CASE

## 格式
- 缩进：4 空格
- 行长度：79 字符

## 类型提示
- 所有函数必须有完整类型提示
- 使用 Python 3.10+ 语法 (list[str] 而非 List[str])

## 文档字符串
- Google 风格
- 所有公共 API 必须有文档字符串
```

---

## 第三部分：实现路线图

### 阶段 1: 基础设施

1. 创建 `knowledge-base/mini-coder-agent-prompts/` 目录
2. 编写 5 个子代理的提示词模板
3. 实现 `PromptLoader` 类
4. 扩展现有 `BaseAgent` 支持动态插值

### 阶段 2: 子代理实现

1. 创建 `ExplorerAgent` (继承 `BaseEnhancedAgent`)
2. 创建 `PlannerAgent`
3. 创建 `CoderAgent`
4. 创建 `ReviewerAgent`
5. 创建 `BashAgent`

### 阶段 3: 主代理集成

1. 扩展 `Orchestrator` 支持子代理派发
2. 实现意图分析逻辑
3. 实现记忆读写对接
4. 实现终端命令安全层

### 阶段 4: 测试与优化

1. 编写各子代理的单元测试
2. 集成测试：完整工作流
3. 提示词调优
4. 性能优化

---

## 参考来源

- Claude Code 官方文档：https://code.claude.com/docs/en/sub-agents
- 提示词逆向工程：https://github.com/Piebald-AI/claude-code-system-prompts
- 本项目现有设计：
  - `docs/command-execution-security-design.md`
  - `docs/context-memory-design.md`
  - `knowledge-base/mini-coder-agent-prompts/implementation-mechanism.md`
  - `knowledge-base/mini-coder-agent-prompts/design-spec.md`
  - `docs/simple-coding-agent-prompts-design.md`
