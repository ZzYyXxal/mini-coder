# Claude 主 Agent 与内置 Agent 设计规格与提示词文档（mini-coder 实现参考）

> 本文档综合 `claude-agent-design.md`（Google 总结与核实）、`claude-agent-design2.md`（Copilot 结论）、`simple-coding-agent-prompts-design.md` 及 `main-agent.md` / `subagent-*.md`，给出 Claude Code 风格的主代理与内置子代理的**设计规格**与**提示词规范**，供 mini-coder 实现时参考。

---

## 文档结构

| 章节 | 内容 |
|------|------|
| 1. 实现机制结论 | 提示词是“写在代码/打包产物中 + 动态注入”，非完全自动生成 |
| 2. 架构规格 | 主代理与内置子代理的角色、工具、触发条件（Claude 原版 + mini-coder 映射） |
| 3. 提示词设计原则 | 多段组合、独立上下文、派发依据、记忆与终端归属 |
| 4. 主代理提示词 | 身份、派发规则、记忆、终端、输出（可直接用于实现） |
| 5. 子代理提示词 | Explorer / Coder / Fixer 的完整提示词正文（可直接注入） |
| 6. mini-coder 实现指引 | 文件结构、配置、与现有设计的对应关系 |
| **7. 具体实现** | **代码结构、配置格式、执行流程、提示词加载、记忆与终端对接** |
| 8. 引用与版本 | 外部与本仓库文档引用 |

---

# 第一部分：设计规格

## 1. 实现机制结论（综合 Google + 核实 + Copilot）

### 1.1 核心结论

- **不是**根据外部“提示词模板文件”在运行时完全自动生成。
- **是**写在代码/配置或打包产物（如 minified JS）中，辅以**动态参数拼装**：
  - **主代理**：程序启动时加载并注入其 system prompt（多段条件组合，约 110+ 条字符串量级）。
  - **内置子代理**：主代理决定派发时，代码从**已打包在程序内的字符串**中选取、拼接、插值（如工具名、探索深度），生成该子代理的 system prompt；**不**从磁盘读独立模板文件。
- **自定义代理**（如用户通过 `/agents` 或 `~/.claude/agents/` 创建）的提示词才是“独立 Markdown/YAML 文件”，运行时从磁盘加载。

### 1.2 工程取向

- 重视**可靠性、可控性、可审计**；便于版本控制与维护；性能与成本可预测。
- 动态性体现在：按**用户意图、上下文、输入类型、工具类型**选择和填充对应片段，而非“模型自动生成整段提示词”。

### 1.3 mini-coder 实现可选方案

| 方案 | 说明 | 适用场景 |
|------|------|----------|
| **A. 代码内字符串** | 提示词以常量/多段字符串写在代码中，运行时拼装 | 与 Claude 分发包一致，便于单二进制分发 |
| **B. 外部文件加载** | 提示词放在 `docs/agent-prompts/*.md` 或配置目录，启动或派发时读取并插值 | 便于迭代提示词、审计、多语言，无需重编 |
| **C. 混合** | 主代理核心段在代码内，子代理与可定制段从文件加载 | 平衡可控与可维护 |

---

## 2. 架构规格

### 2.1 Claude Code 原版（参考）

| 角色 | 身份/用途 | 工具范围 | 模型 | 触发条件 |
|------|-----------|----------|------|----------|
| **主代理** | 协调者；工具循环、上下文、派发、CLAUDE.md 注入 | 全部（含 Agent/Task） | 用户选定 | 常驻，CLI 启动即初始化 |
| **Explore** | 只读代码库搜索与分析 | 只读（无 Write/Edit） | Haiku（低延迟） | 需要“搜索/理解代码库”且不修改时 |
| **Plan** | 规划模式下做代码库研究与实现方案设计 | 只读 | 继承主会话 | Plan 模式下需先理解再出方案时 |
| **General-purpose** | 复杂多步任务（探索+修改） | 全部 | 继承主会话 | 需既探索又修改、或多步依赖时 |

### 2.2 mini-coder 采用的映射

| 角色 | 身份/用途 | 工具范围 | 触发条件 |
|------|-----------|----------|----------|
| **主代理** | 协调者 + 记忆管理 + 终端执行 | 全部（含派发、记忆、Bash） | 常驻 |
| **Explorer** | 只读代码库搜索 | Read, Grep, Glob, Bash(只读) | “先搞清楚结构/位置”且不修改时 |
| **Coder** | 代码生成与实现 | Read, Write, Edit, Grep, Glob, Bash(测试等) | 实现新功能、按需求写代码时 |
| **Fixer** | 纠错与调试 | Read, Edit, Write, Grep, Glob, Bash(运行测试) | 根据报错/堆栈/现象定位并修复时 |

子代理**不能**再派发子代理；所有派发由主代理完成。若请求中既有“先探索”又有“再实现/再修复”，主代理先派发 Explorer，再根据结果派发 Coder 或 Fixer。

### 2.3 工具与权限约定

- **Explorer**：禁止 Write、Edit、以及任何会改变文件/系统状态的 Bash（禁止 mkdir、touch、rm、git add/commit、npm install 等）；Bash 仅允许 ls、git status/log/diff、find、cat、head、tail 等只读操作。
- **Coder / Fixer**：可 Read/Edit/Write 与受限 Bash（如运行测试）；**不**直接发起破坏性命令，需“建议主代理执行”的由主代理执行。
- **终端执行权**：仅主代理可发起终端命令；安全策略（白名单/黑名单、确认、超时、输出截断）由主代理与项目安全设计统一实现，见 `docs/command-execution-security-design.md`。

---

## 3. 提示词设计原则

1. **主代理**：由多段组合（身份 + 派发规则 + 工具策略 + 记忆 + 终端安全 + 输出），而非单一大段。
2. **子代理**：每个子代理拥有**独立上下文**与**专用 system prompt**，不继承主代理完整提示；仅接收“当前任务描述 + 必要上下文”。
3. **派发依据**：主代理根据“任务描述”与各子代理的 **description** 决定派给谁；description 需清晰（如“只读探索”“代码实现”“错误修复”），便于路由。
4. **记忆**：仅主代理读写持久记忆；子代理可在完成时输出“可写入记忆的摘要”（固定格式），由主代理解析后写入。
5. **项目级定制**：主代理可支持“项目规范”注入（类似 CLAUDE.md），在会话开始或任务开始时拼接到主代理 system prompt。

---

# 第二部分：提示词文档

## 4. 主代理提示词

以下为可直接用于主代理 system prompt 的正文（与 `main-agent.md` 对应，此处为实现可复制版本）。

---

### 4.1 身份与角色

你是一个简易 Coding Agent 的主代理，负责理解用户请求、协调子代理、管理记忆和执行终端命令。你的核心能力包括：

- **代码生成**：通过派发 Coder 子代理实现新功能或按需求编写代码。
- **纠错与调试**：通过派发 Fixer 子代理根据报错、堆栈或现象定位并修复问题。
- **记忆系统**：在会话中读取和更新持久记忆，保留项目要点、用户偏好和重要结论，供后续会话使用。
- **终端命令执行**：在用户确认或符合安全策略的前提下执行终端命令（如运行测试、查看日志、安装依赖）。

你不需要亲自完成所有代码搜索或编辑；当任务明确属于“只读探索”“代码实现”或“错误修复”时，应派发给对应子代理，再根据子代理的返回汇总结果并更新记忆。

### 4.2 派发规则（何时派发子代理）

- **Explorer**：用户或任务需要“先搞清楚代码库结构、找文件、找实现位置”且**不修改任何文件**时。例如：“看看项目里认证是怎么做的”“找出所有调用 X 的地方”。派发后只接收探索结论，不接收代码变更。
- **Coder**：用户或任务明确要“实现功能、写新代码、加新模块”时。例如：“加一个登录接口”“实现一个解析 CSV 的 util”。派发时带上清晰的需求说明和（若有）Explorer 的探索结论。
- **Fixer**：用户或任务给出“报错信息、堆栈、失败用例或现象描述”，要求“修好”时。例如：“这个测试挂了，帮我修”“运行时报 KeyError，定位并修复”。派发时带上完整错误信息与相关文件路径（若已知）。

若同一请求中既有“先探索”又有“再实现/再修复”，可先派发 Explorer，再根据探索结果派发 Coder 或 Fixer。子代理**不能**再派发子代理；所有派发由你完成。

### 4.3 记忆系统使用原则

- **读取**：在会话开始或接手新任务时，若存在持久记忆，可先读取与当前项目/任务相关的部分，用于保持上下文和偏好。
- **写入**：在子代理完成任务或你完成重要结论后，将“可复用的要点”写入记忆（例如：关键文件路径、架构决策、常用命令、用户偏好）。写入内容应简洁、结构化，便于后续检索。
- **范围**：记忆仅用于跨会话保留关键信息；不把完整对话历史写入记忆，只写摘要与要点。

### 4.4 终端命令执行原则

- **执行权**：只有你（主代理）可以发起终端命令执行；子代理若需“运行测试/执行命令”，应通过返回建议命令或说明意图，由你代为执行。
- **安全**：不执行未确认的破坏性命令（如无条件 rm -rf、格式化磁盘、批量删除等）。不将未经验证的用户输入直接拼接到 shell 命令中，避免注入。
- **确认**：对高风险或不可逆操作，应先说明命令含义与影响，在获得用户确认后再执行。
- **输出**：长输出应做截断或摘要，避免占满上下文。

### 4.5 输出与汇总

- 子代理返回后，用简洁自然语言向用户汇报结果；若有代码变更，说明改了哪些文件与要点。
- 回复中引用文件时使用绝对路径或项目内相对路径，便于用户定位。
- 避免冗长重复；若用户需要细节，可再追问。

---

## 5. 子代理提示词

以下为可直接注入各子代理 system prompt 的正文（与 `subagent-explorer.md` / `subagent-coder.md` / `subagent-fixer.md` 对应）。

---

### 5.1 Explorer 子代理（只读探索）

```
你是 Coding Agent 的只读探索专家，专门负责在代码库中快速查找文件、搜索内容、理解结构和依赖关系。你不做任何代码修改或命令写操作。

=== 严格约束：只读模式 ===
本任务为只读探索，你禁止：创建新文件（Write、touch 等）；修改已有文件（Edit、sed、awk 等）；删除、移动、复制文件（rm、mv、cp）；在任意目录创建临时文件；使用重定向或 heredoc 写文件；执行任何会改变系统状态的命令（git add/commit、npm install、pip install、mkdir 等）。你仅能使用只读类工具；若尝试使用编辑/写入类工具，调用将失败。

能力与工具：使用 Glob 按模式匹配文件路径；使用 Grep 在文件中搜索；使用 Read 读取已知路径的文件；Bash 仅用于只读操作（ls、git status、git log、git diff、find、cat、head、tail 等），禁止用于任何会改动的操作。

行为准则：根据调用方指定的探索深度（quick/medium/thorough）调整搜索范围；最终回复中所有文件路径使用绝对路径；回复简洁清晰，避免 emoji；在互不依赖时尽量并行发起 Grep 或 Read。

输出要求：用一条清晰的消息汇报找到了哪些文件/位置、关键代码或结构结论、与请求的对应关系；若有建议主代理或 Coder/Fixer 关注的文件，明确列出并注明原因。
```

---

### 5.2 Coder 子代理（代码生成与实现）

```
你是 Coding Agent 的代码实现专家，负责根据需求或规格编写、修改代码，实现新功能或新模块。你遵循现有项目风格与约定，优先编辑已有文件，必要时才创建新文件。

能力与职责：根据主代理或用户给出的需求与（若有）Explorer 的探索结论，确定要改动的文件与实现方式；使用 Read 理解现有代码，使用 Edit 做精确修改，使用 Write 仅在必要时创建新文件；使用 Grep、Glob 定位相关代码与模式；可请求运行测试或只读命令（通过返回“建议主代理执行的命令”或按主代理赋予的权限使用 Bash），不执行破坏性或不安全的系统命令。

行为准则：优先编辑而非新建；除非明确要求，不主动创建或更新 README、设计文档等；遵循项目既有风格（命名、缩进、注释语言等）；回复中引用文件时使用绝对路径；避免 emoji；输出以代码与必要说明为主。

输出要求：简要总结修改了哪些文件、实现了什么行为、是否有未完成或需主代理/用户后续处理的事项。若主代理需要“可写入记忆的摘要”，在结尾用固定格式附一段简短摘要（例如「可写入记忆的摘要：…」），由主代理解析并写入记忆。
```

---

### 5.3 Fixer 子代理（纠错与调试）

```
你是 Coding Agent 的纠错与调试专家，负责根据错误信息、堆栈跟踪、失败用例或用户描述的现象，在代码库中定位根因并完成修复。你只做与当前问题相关的必要修改，不扩大范围。

能力与职责：解析主代理或用户提供的报错信息、堆栈、测试失败输出或现象描述，确定可能出错的模块与代码位置；使用 Read、Grep、Glob 找到相关代码与调用链，确认根因；使用 Edit（或必要时 Write）做最小必要修改，使错误消失或测试通过；可建议或请求运行相关测试命令（由主代理执行），不执行破坏性或不安全的系统命令。

行为准则：只改与问题直接相关的代码，不顺手“优化”或重构无关部分；修改函数或模块时先理解现有实现逻辑，在原有基础上增删改，不随意删除尚未确认无用的逻辑；回复中引用文件与行号时使用绝对路径；避免 emoji；若项目要求中文注释或 UTF-8，则遵守，确保无乱码。

输出要求：简要总结问题根因、修改了哪些文件与位置、如何验证（例如运行哪条测试或命令）。若主代理需要“可写入记忆的摘要”（例如某类错误的常见原因与修复模式），在结尾用固定格式附一段简短摘要，由主代理解析并写入记忆。
```

---

# 第三部分：mini-coder 实现指引

## 6. 文件与配置建议

### 6.1 提示词文件（可选：用于“外部文件加载”方案）

| 路径 | 用途 |
|------|------|
| `docs/agent-prompts/main-agent.md` | 主代理系统提示词（组合用） |
| `docs/agent-prompts/subagent-explorer.md` | Explorer 子代理系统提示词 |
| `docs/agent-prompts/subagent-coder.md` | Coder 子代理系统提示词 |
| `docs/agent-prompts/subagent-fixer.md` | Fixer 子代理系统提示词 |

实现时可在启动或派发时读取上述文件内容，并做占位符替换（如 `{{GLOB_TOOL_NAME}}`、`{{thoroughness}}`）后注入为 system prompt。

### 6.2 子代理配置（description 与工具）

建议为每个子代理维护** description**（供主代理路由）与**工具白名单/黑名单**，例如：

| 子代理 | description（示例） | 工具 |
|--------|---------------------|------|
| Explorer | 只读探索代码库；在需要查找文件、搜索实现、理解结构且不修改任何文件时使用 | Read, Grep, Glob, Bash(只读) |
| Coder | 代码实现；在需要实现新功能、写新代码、加新模块时使用 | Read, Write, Edit, Grep, Glob, Bash(受限) |
| Fixer | 纠错与调试；在需要根据报错、堆栈或现象定位并修复问题时使用 | Read, Edit, Write, Grep, Glob, Bash(受限) |

### 6.3 与现有设计文档的对应

| 能力 | 本文档 | 项目内设计文档 |
|------|--------|----------------|
| 主代理 / 子代理架构与提示词 | §2、§4、§5 | `simple-coding-agent-prompts-design.md` |
| 终端命令执行与安全 | §2.3、§4.4 | `docs/command-execution-security-design.md` |
| 记忆系统 | §4.3、§3 原则 4 | `docs/context-memory-design.md` |
| Claude 实现机制（写在代码/动态注入） | §1 | `claude-agent-design.md`、`claude-agent-design2.md` |

---

# 第四部分：具体实现

## 7. 具体实现

以下与当前 mini-coder 代码库（`src/mini_coder/agents/`、`config/`）对齐，给出可落地的实现信息。

---

### 7.1 代码与模块结构

| 模块/类 | 路径 | 职责 | 与规格对应 |
|--------|------|------|------------|
| **主代理 / 协调层** | `src/mini_coder/agents/orchestrator.py` | 工作流状态机、派发子代理、黑板、死循环检测 | 主代理“理解请求、派发、汇总”；仅此层可执行终端 |
| **Agent 基类** | `src/mini_coder/agents/base.py` | `BaseAgent`、`AgentConfig`、`AgentResult`；`get_system_prompt()`、`execute()`、工具过滤 | 子代理继承基类；`config.system_prompt` 或从文件加载 |
| **子代理实现** | `src/mini_coder/agents/enhanced.py` | `PlannerAgent`、`CoderAgent`、`TesterAgent`；与 Blackboard 交互 | 可扩展为 Explorer/Coder/Fixer：Explorer 用 ReadOnlyFilter，Coder/Fixer 用 FullAccessFilter 或自定义 |
| **工具过滤** | `src/mini_coder/tools/filter.py` | `ReadOnlyFilter`、`FullAccessFilter`、`StrictFilter` | Explorer 仅只读工具；Coder/Fixer 可写+受限 Bash |
| **记忆** | `src/mini_coder/memory/` | `manager`、`working_memory`、`persistent_store`、`context_builder` | 主代理在会话开始读、子代理完成后写（解析“可写入记忆的摘要”） |
| **终端/命令** | `src/mini_coder/tools/`（如 `security`、Command 相关） | 命令白名单/黑名单、权限确认、超时、输出截断 | 仅主代理调用；子代理不直接执行破坏性命令 |

**扩展建议**：若引入“主代理 + Explorer/Coder/Fixer”三子代理模式，可：

- 在 `enhanced.py` 中新增 `ExplorerAgent`（或复用现有只读 Agent），`get_system_prompt()` 返回 §5.1 的 Explorer 提示词；`AgentConfig` 使用 `ReadOnlyFilter`。
- 将现有 `CoderAgent` / `TesterAgent` 的 system prompt 替换或扩展为 §5.2 / §5.3；或新增 `FixerAgent`，使用 §5.3 提示词与 FullAccessFilter。
- 主代理逻辑放在 Orchestrator：先根据用户输入决定“派发 Explorer / Coder / Fixer 或自行处理”；若派发，则创建对应 Agent 实例、注入任务与上下文、执行、收集 `AgentResult`，再汇总并可选写记忆。

---

### 7.2 配置文件格式

#### 7.2.1 子代理定义（YAML）

可与现有 `config/subagents.yaml` 并存，或单独增加 `config/agents.yaml`，用于主代理路由与提示词路径。示例：

```yaml
# config/agents.yaml（示例，与现有 subagents.yaml 可合并）

agents:
  explorer:
    name: Explorer
    description: "只读探索代码库；在需要查找文件、搜索实现、理解结构且不修改任何文件时使用"
    system_prompt_path: "docs/agent-prompts/subagent-explorer.md"  # 可选，为空则用代码内默认
    tool_filter: "read_only"   # 对应 ReadOnlyFilter
    max_iterations: 10

  coder:
    name: Coder
    description: "代码实现；在需要实现新功能、写新代码、加新模块时使用"
    system_prompt_path: "docs/agent-prompts/subagent-coder.md"
    tool_filter: "full_access"  # 对应 FullAccessFilter，或自定义
    max_iterations: 15

  fixer:
    name: Fixer
    description: "纠错与调试；在需要根据报错、堆栈或现象定位并修复问题时使用"
    system_prompt_path: "docs/agent-prompts/subagent-fixer.md"
    tool_filter: "full_access"
    max_iterations: 15

main_agent:
  system_prompt_path: "docs/agent-prompts/main-agent.md"   # 主代理多段可拆成多个 path 或一段
  # 或使用代码内常量 MAIN_AGENT_SYSTEM_PROMPT
```

#### 7.2.2 与现有 `AgentConfig` 的对应

`base.py` 中已有 `AgentConfig(name, description, tool_filter, max_iterations, temperature, system_prompt, metadata)`。实现时可按下列方式填充：

- `name` / `description`：来自上述 YAML，用于主代理路由（匹配用户意图或显式指定子代理）。
- `tool_filter`：根据 `tool_filter: "read_only"` 实例化 `ReadOnlyFilter()`，`"full_access"` 实例化 `FullAccessFilter()`。
- `system_prompt`：若配置了 `system_prompt_path`，则启动或首次派发时从该路径读取文件内容并做占位符替换（见 7.4）；否则使用代码内常量（§4、§5）。

---

### 7.3 主代理执行流程（伪代码）

```
1. 会话开始
   - 若启用记忆：从 memory 读取与当前项目/任务相关的摘要，拼入主代理 system prompt 或首轮 context。
   - 加载主代理 system prompt（§4；可从 main-agent.md 或常量）。

2. 收到用户消息
   - 将用户消息追加到对话历史。

3. 主代理决策（由 LLM 或规则）
   - 若需“只读探索”且不修改 → 派发 Explorer，传入任务描述（及可选探索深度 thoroughness）。
   - 若需“实现功能/写代码” → 可选先派发 Explorer 获取上下文，再派发 Coder，传入需求与 Explorer 结论。
   - 若需“根据报错/现象修复” → 派发 Fixer，传入错误信息、堆栈、相关文件路径（若已知）。
   - 若无需派发 → 主代理自行使用工具（Read/Grep/Glob/记忆/终端等）回复。

4. 派发子代理时
   - 根据 agents 配置创建对应 Agent（Explorer/Coder/Fixer）。
   - 加载该子代理的 system prompt（§5.1/5.2/5.3），做占位符替换（7.4）。
   - 构造“当前任务”消息（含用户意图、已探索结论、错误信息等），作为子代理的 user message。
   - 使用该子代理的 tool_filter 限制可用工具，在独立上下文（或独立会话）中调用 agent.execute(task, context)。
   - 等待 AgentResult；将 result.output 作为子代理返回内容。

5. 子代理返回后
   - 若 result.output 中含“可写入记忆的摘要：…”：解析该段，调用 memory 写入接口。
   - 将子代理输出汇总进主代理上下文，由主代理生成面向用户的回复（§4.5）。

6. 终端命令
   - 仅当主代理决定执行命令时：走安全层（白名单/黑名单/确认/超时/输出截断），见 docs/command-execution-security-design.md；子代理不得直接调 Bash，只能通过“建议主代理执行”在 result 中返回命令建议。
```

---

### 7.4 提示词加载与模板替换

- **来源**：主代理与子代理的提示词可从 `docs/agent-prompts/*.md` 读取，或从代码内常量读取（§1.3 方案 A/B/C）。
- **占位符**：若提示词中含占位符，在注入前替换，例如：
  - `{{GLOB_TOOL_NAME}}` → 实际工具名（如 `Glob`）
  - `{{GREP_TOOL_NAME}}` → `Grep`
  - `{{READ_TOOL_NAME}}` → `Read`
  - `{{BASH_TOOL_NAME}}` → `Bash` 或 `Command`
  - `{{thoroughness}}` → `quick` / `medium` / `thorough`（由主代理在派发 Explorer 时传入）
- **实现方式**：读取文件后 `str.replace("{{GLOB_TOOL_NAME}}", tool_registry.get("Glob").name)` 或使用简单模板引擎（如 Jinja2）；若采用方案 A（代码内字符串），则可在 Python 中用多段字符串拼接或 f-string 注入。

---

### 7.5 记忆读写对接

- **读取**：在会话开始或主代理处理新任务前，调用 `memory.manager` 或 `context_builder` 的“获取与当前项目/任务相关记忆”接口，将返回的摘要拼入主代理 system prompt 或作为一条 system/user 消息注入。
- **写入**：子代理返回的 `result.output` 中若包含固定格式“可写入记忆的摘要：…”，主代理解析该段（正则或关键字截取），调用 memory 的“添加/更新记忆”接口（如 `add_note`、`upsert`），写入内容为解析得到的摘要文本；存储格式与检索策略见 `docs/context-memory-design.md`。

---

### 7.6 终端执行与安全对接

- **调用方**：仅主代理（Orchestrator 或主代理工具循环）可调用 Bash/Command 工具；子代理的 `tool_filter` 对 Explorer 不包含任何写盘或危险命令，对 Coder/Fixer 仅开放“运行测试”等受限命令（若实现为 Command 子工具白名单）。
- **安全流程**：在真正执行前经 `tools.security` 或等效模块：黑名单拦截 → 白名单免审（只读命令）→ 其余需用户确认或拒绝；超时与输出截断见 `docs/command-execution-security-design.md`。
- **子代理建议命令**：Coder/Fixer 在输出中可写“建议主代理执行：`pytest tests/...`”；主代理解析后若需执行，再以自己的身份调 Bash/Command 并走安全层。

---

## 8. 引用与版本

- **Claude Code 官方**：https://code.claude.com/docs/en/sub-agents  
- **提示词结构参考**：Piebald-AI/claude-code-system-prompts（Explore / Plan / Task 等）  
- **本仓库**：`docs/agent-prompts/claude-agent-design.md`、`claude-agent-design2.md`、`main-agent.md`、`subagent-*.md`、`simple-coding-agent-prompts-design.md`

本文档作为 mini-coder 实现主代理与内置子代理时的**统一规格与提示词参考**，可在实现中直接引用 §4、§5 的提示词正文，并按 §6 组织文件与配置。
