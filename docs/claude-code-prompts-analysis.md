# Claude Code 系统提示词分析与总结

本文档分析 `knowledge-base/claude-code-system-prompts` 中的 Claude Code 提示词，用于优化 mini-coder 的 agent 与工具提示词：**功能一致处直接参考内容，无对应功能处参考写法和风格**。

---

## 一、整体结构

### 1. 文件组织

- **工具描述**：`system-prompts/tool-description-<name>.md`（如 `readfile`、`write`、`edit`、`grep`、`glob`、`bash-*`、`todowrite`、`agent-*`）。
- **系统提醒**：`system-reminder-*.md`（如 output-style、plan-mode、token-usage）。
- **元数据**：每个文件顶部为 HTML 注释形式的 frontmatter，包含 `name`、`description`、`ccVersion`、可选 `variables` 列表。

### 2. 通用写法

| 要素 | 写法 |
|------|------|
| 首句 | 一句概括工具用途（如 "Reads a file from the local filesystem." / "Executes a given bash command and returns its output."）。 |
| 主体 | 用 **Usage:** 或 **Usage notes:** 引出要点，下列 bullet；必要时用 **CRITICAL** / **IMPORTANT** 单独强调。 |
| 变量 | 占位符形如 `${VAR}`、`${CONDITION()?\`...\`:""}`，由系统在注入时替换。 |
| 禁止/偏好 | 明确写 "NEVER..."、"DO NOT..."、"Prefer... — Only use..."、"ALWAYS use X for Y. NEVER use Z."。 |

---

## 二、按工具类型归纳

### ReadFile

- **首句**：Reads a file from the local filesystem. You can access any file directly by using this tool.
- **要点**：file_path 必须为绝对路径；默认读前 N 行，可指定 offset/limit；长行截断；可读图片/PDF/ipynb；不能读目录（用 ls）；可单次调用多工具并行读多个文件；空文件会返回系统提醒。
- **风格**：Assume 类假设（如“若用户提供路径则视为有效”）写清，减少模型犹豫。

### Write

- **首句**：Writes a file to the local filesystem.
- **要点**：会覆盖已存在文件；**Prefer Edit for modifying existing files** — 仅用 Write 创建新文件或完整重写；NEVER 主动创建 *.md/README 除非用户明确要求；Only use emojis if the user explicitly requests it。

### Edit

- **首句**：Performs exact string replacements in files.
- **要点**：从 Read 输出编辑时保留缩进，且不要包含行号前缀；**ALWAYS prefer editing existing files**，NEVER write new files unless explicitly required；old_string 不唯一会 FAIL，需更大上下文或 replace_all；replace_all 用于整文件重命名等。

### Grep

- **首句**：A powerful search tool built on ripgrep.
- **要点**：**ALWAYS use Grep for search. NEVER invoke grep/rg via Bash**；支持 regex、glob/type 过滤、content/files_with_matches/count 模式；跨行用 multiline: true；大范围开放搜索可交给 Agent/Task 多轮。

### Glob

- **首句**：无单独首句，直接 bullet 列表。
- **要点**：按文件名模式匹配；支持 `**/*.js` 等；结果按修改时间排序；按名找文件用 Glob，开放多轮搜索用 Agent；可单次并行多次搜索。

### Bash（多条碎片组合）

- **概述**：Executes a given bash command and returns its output.
- **工作目录**：The working directory persists between commands, but shell state does not.
- **路径**：Always quote file paths that contain spaces with double quotes.
- **专用工具优先**：IMPORTANT: Avoid using Bash for find/grep/cat/head/tail/sed/awk — use the dedicated tool; 读文件用 Read (NOT cat/head/tail)；编辑用 Edit (NOT sed/awk)；内容搜索用 Grep (NOT grep/rg)。
- **描述**：Write a clear, concise description of what your command does（简单 5–10 词，复杂带上下文）。
- **换行**：DO NOT use newlines to separate commands。

### TodoWrite

- **首句**：Use this tool to create and manage a structured task list...
- **结构**：**When to Use** / **When NOT to Use** / **Examples**（含 \<example\> 与 \<reasoning\>）/ **Task States and Management**（pending, in_progress, completed；content vs activeForm；一次仅一个 in_progress；完成即标记；不可在未完成/失败时标 completed）。

### Agent（子代理）

- **首句**：Launch a new agent to handle complex, multi-step tasks autonomously.
- **要点**：列出 Available agent types and the tools they have access to；说明 subagent_type 或 fork 继承上下文；Usage notes：简短描述(3–5 词)、可并发多 agent、结果需你转述给用户、resume 用法、明确说明是否写代码还是仅调研、可 worktree 隔离。

### WebSearch

- **首句**：无，直接 bullet。
- **要点**：用于截止日后信息；结果以 search result blocks + markdown 链接返回；**CRITICAL**：回答后 **MUST** 包含 "Sources:" 段，列出 markdown 链接；支持域名过滤；用当前年月变量。

---

## 三、与 mini-coder 的对应关系

| Claude Code | mini-coder | 建议 |
|--------------|------------|------|
| ReadFile / Write / Edit / Grep / Glob | 由运行环境提供，filter 中按名引用 | 若日后自建工具描述，采用“首句 + Usage 列表 + NEVER/Prefer”风格。 |
| Bash（overview + 多条碎片） | **Command** 工具（prompts/tools/command.md） | 直接参考：首句概括、Usage、专用工具优先、路径引号、命令描述、禁止换行分隔。 |
| TodoWrite | 暂无对应 | 若增加任务列表工具，可参考 When to Use / When NOT / Task States。 |
| Agent | 主代理 + 子代理（Explorer/Planner/Coder/Reviewer/Bash） | 参考：简短描述、结果转述、明确任务与上下文。 |
| WebSearch | 若有 WebSearch/WebFetch | 参考：Sources 必填、当前时间。 |

---

## 四、风格要点（用于优化 mini-coder 提示词）

1. **首句定性**：用一句说明“是什么/做什么”，再展开。
2. **Usage 清单**：用 "Usage:" 或 "Usage notes:" 列要点，便于扫描。
3. **禁止与偏好**：NEVER / DO NOT / Prefer X — Only use Y for Z；专用工具优先于通用 Bash。
4. **占位符**：可配置项用 `{{variable}}` 或 `${VAR}` 形式，在文档中注明“由系统/配置注入”。
5. **CRITICAL / IMPORTANT**：关键约束单独成段或加粗，避免埋没在长段中。
6. **结构化输出**：若需模型输出固定格式，给出示例（如 WebSearch 的 Sources 格式、TodoWrite 的 content/activeForm）。

---

## 五、已应用的优化

- **prompts/tools/command.md**：按上述风格重写——首句概括、**Usage** 列表（命令参数、路径引号、命令描述、禁止换行）、**IMPORTANT - 优先使用专用工具**（Read 而非 cat/head/tail，Edit 而非 sed/awk，Grep 而非 grep/rg）、安全策略与结构化输出保留，占位符 `{{security_mode}}`、`{{timeout}}`、`{{max_output_length}}`、`{{allowed_paths}}` 由配置注入。
- **prompts/system/**：此前已按 feature-dev/aider/OpenCode 增加输出指引与占位符；与 Claude Code 一致处：简洁、可解析、禁止/偏好明确。若需在子代理中强调“优先专用工具”，可在 Bash/Explorer 等系统提示中加一句：读文件用 Read、搜索用 Grep、改文件用 Edit，避免用 Command 执行 cat/grep/sed/awk。
