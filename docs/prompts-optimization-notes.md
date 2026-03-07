# 提示词优化说明（参考 feature-dev / aider / OpenCode）

本文档说明对 `prompts/system/` 下主代理与子代理提示词的优化点及**每段修改原因**，便于后续维护与对照参考来源。

---

## 参考来源摘要

| 来源 | 要点 |
|------|------|
| **feature-dev** (agents/*.md, commands/feature-dev.md) | 每 agent 有明确 **Output Guidance**；YAML frontmatter；分阶段 + 占位符（如 `$ARGUMENTS`）；“Structure your response for maximum actionability”；confidence 与严重程度。 |
| **OpenCode** (internal/llm/prompt/*.go) | 注入 `<env>`（Working directory、git、platform、date）与 `<project>`；路径“always use the full path”并示例；简洁输出“fewer than 4 lines”“Answer directly”；“Do not add additional code explanation summary”；Project-Specific Context 注入。 |
| **aider** (coders/*_prompts.py) | 严格“Your response *MUST* use this format”；占位符 `{language}`、`{fence[0]}`、`{hash}` 等；architect “make them unambiguous and complete”；context “Only return existing files”；“NEVER RETURN CODE!”。 |

---

## 1. main-agent.md

| 修改点 | 原因 |
|--------|------|
| 在「结构化输出」标题下增加 **“仅可输出以下三种之一，不得混用或增加未约定格式；占位符含义见下”** | 与 aider/OpenCode 的“MUST use this format”一致，强调格式唯一性，便于解析。 |
| 新增 **「输出指引（Output Guidance）」** 小节：格式唯一、占位符说明、可解析性 | 参考 feature-dev 的 Output Guidance，明确块外不要前导/总结语，以及下游依赖“交由”解析派发。 |
| 占位符说明：`<类型简述>`、`<子问题N>`、`<子代理名>` 须替换为具体内容 | 避免模型输出未替换的占位符字面量，保证可解析性。 |

---

## 2. subagent-coder.md

| 修改点 | 原因 |
|--------|------|
| 结构化输出前增加 **“仅输出”** 及 **“占位符 `{{work_dir}}` 由系统注入为项目根目录”** | 明确 `{{work_dir}}` 的来源与用法，避免模型写 `/home/user/...`（OpenCode 的路径规范 + 此前 work_dir 注入需求）。 |
| 新增 **「输出指引」**：块即回复、路径可解析、占位符说明 | OpenCode：“After working on a file, just stop”；aider 的“MUST use this format”；确保“修改文件”行为可解析的路径列表。 |

---

## 3. subagent-planner.md

| 修改点 | 原因 |
|--------|------|
| 主产物说明中增加 **“若已知项目根目录则为 `{{work_dir}}/implementation_plan.md`”** 及 **“占位符 `{{work_dir}}` 由系统在注入时替换”** | 与 Coder 一致，支持未来对 Planner 注入 work_dir，产出路径可统一为基于项目根。 |
| 新增 **「输出指引」**：格式即契约、步骤可勾选、占位符 | aider architect：“make them unambiguous and complete”；feature-dev 的 phased checklist；便于下游与 Coder/Reviewer 解析。 |

---

## 4. subagent-explorer.md

| 修改点 | 原因 |
|--------|------|
| 结构化输出中 **“文件/位置”** 增加 **“建议带行号如 path/to/file.py:42”**；说明 **“路径须基于项目根（若已提供 `{{work_dir}}` 则使用…”** | feature-dev code-explorer：“Entry points with file:line references”；OpenCode/task：paths MUST be absolute；便于 Coder/Planner 跳转。 |
| 新增 **「输出指引」**：可定位、仅现有路径、单块回复 | code-explorer：“Include specific file paths and line numbers”；aider context：“Only return existing files”；避免冗长前言。 |

---

## 5. subagent-reviewer.md

| 修改点 | 原因 |
|--------|------|
| 在“仅可输出以下两种之一”后增加 **“不得出现部分通过或无 [Pass]/[Reject] 的模糊结论”** | 强调二元结论，避免中间态。 |
| 新增 **「输出指引」**：二元结论、可操作（文件:行号+建议）、严重程度排序与 [架构|质量|风格] | feature-dev code-reviewer：“confidence-based”“Structure your response for maximum actionability”；每条 Reject 含路径、行号、建议。 |

---

## 6. subagent-bash.md

| 修改点 | 原因 |
|--------|------|
| 结构化输出说明中增加 **“有失败时给出可定位信息（如用例名、文件:行号）”** | 与 Reviewer/Coder 一致，失败时可定位。 |
| 新增 **「输出指引」**：每节必填、失败可定位、单块回复 | OpenCode 的明确 env/project 块风格；便于上游统一解析【质量报告】。 |

---

## 7. general-purpose.md

| 修改点 | 原因 |
|--------|------|
| 增加 **“仅输出”** 与 **“以【分析结果】为唯一结构化块”** | 与其它子代理一致，单块、无多余前言。 |
| 新增 **「输出指引」**：单块回复、路径绝对 | OpenCode task：“file paths you return MUST be absolute”；aider 简洁输出。 |

---

## 8. mini-coder-guide.md

| 修改点 | 原因 |
|--------|------|
| 增加 **“仅使用”** 与 **“占位符须替换为具体内容”** | 避免占位符未替换。 |
| 新增 **「输出指引」**：依据可查、仅答所问、单块回复 | feature-dev 的可追溯性；“依据”栏填写实际引用来源。 |

---

## 占位符与注入约定

- **`{{work_dir}}`**：在 Coder 中由 TUI 派发前写入 blackboard，并在 `_build_coding_prompt()` 中通过 `_load_system_prompt(context={"work_dir": ...})` 注入；Planner/Explorer 的提示词中已预留该占位符，若后续在派发路径中为二者注入 `work_dir`，则会在加载时被替换。
- **其它占位符**：`<类型简述>`、`<子问题N>`、`<子代理名>`、`<文件绝对路径>:<行号>` 等均为**输出格式占位**，表示模型应填写的具体内容，非系统运行时替换。
- **格式化输出**：所有子代理均约定“仅输出一个结构化块”“块外不冗长前言/总结”，与 OpenCode/aider 的简洁、可解析风格一致。

---

## 文件清单（已修改）

- `prompts/system/main-agent.md`
- `prompts/system/subagent-coder.md`
- `prompts/system/subagent-planner.md`
- `prompts/system/subagent-explorer.md`
- `prompts/system/subagent-reviewer.md`
- `prompts/system/subagent-bash.md`
- `prompts/system/general-purpose.md`
- `prompts/system/mini-coder-guide.md`
