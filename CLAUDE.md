# CLAUDE.md

本文件为在本地仓库中编写、修改代码时提供给 Claude 的指引。

## Project Overview

**mini-coder** 是自定义 coding agent 项目，采用多 Agent 系统：由编排器协调 Explorer、Planner、Coder、Reviewer、Bash 等子代理完成开发工作流。

重要架构与设计见 `docs` 目录；重大架构变更会同步更新该目录文档。

## Development Environment Setup

### 运行环境脚本

```bash
bash claude_code_env.sh
```

将完成：安装 Node.js (v22)、全局安装 Claude Code CLI、配置 ZHIPU AI 凭证（按提示输入）。

### 配置与 API

- 配置目录：`~/.claude/settings.json`、`~/.claude.json`、`~/.claude/cache/`
- API：ZHIPU AI，Base URL `https://open.bigmodel.cn/api/anthropic/v1`，超时 3,000,000 ms

---

## Core Coding Agent Workflow

### Agent 角色（5 个子代理，动态提示词加载）

| Agent | 职责 | Tool Filter |
|-------|------|-------------|
| **Explorer** | 只读代码库搜索 | ReadOnlyFilter |
| **Planner** | 需求分析与 TDD 规划 | PlannerFilter (ReadOnly + WebSearch) |
| **Coder** | 按 TDD 实现代码 | FullAccessFilter |
| **Reviewer** | 代码质量与架构对齐评审 | ReadOnlyFilter |
| **Bash** | 终端执行与测试验证 | BashRestrictedFilter |

### TDD 流程与每次修改后 Review

开发必须遵循 **TDD**，且**每次代码修改完成后必须经 Reviewer 通过**再进入 Bash 测试或合并：

1. **TDD 流程**
   - **Red**：先写/补全 failing 的测试（明确断言与边界）。
   - **Green**：实现代码使测试通过。
   - **Refactor**：必要时重构，保持测试通过。

2. **每次修改完 Review**
   - Coder 完成一次修改（或一个原子步骤）后，由 **Reviewer** 做：
     - 架构对齐：是否符合 implementation_plan / 模块边界。
     - 代码质量：类型标注、docstring、PEP 8、复杂度。
   - **Pass** → 进入 Bash（pytest / mypy / flake8 / 质量报告）。
   - **Reject** → 回到 Coder 修改，再重新走 Review，不跳过。

不要在未通过 Review 的情况下直接跑完整流水线或合并代码。

### 工作流阶段概览

```
1. Explorer（可选）
   └─ 探索代码结构、定位相关文件

2. Planner
   └─ 需求分析，产出 TDD 实现计划（implementation_plan.md）

3. Coder（TDD）
   └─ 先测试（Red）→ 实现（Green）→ 必要时重构

4. Reviewer（每次修改后必过）
   └─ 架构对齐 + 代码质量 → Pass → Bash；Reject → 回到 Coder

5. Bash
   └─ pytest、mypy、flake8、质量报告
```

---

## Multi-Agent 架构要点

- **提示词**：`prompts/system/*.md`，占位符 `{{identifier}}`，缺文件时使用内置兜底。
- **统一 Planner-Orchestrator**：Main Agent 与 Planner 已合并为统一 Agent（`prompts/system/unified-planner-orchestrator.md`）。接收用户消息后做四类决策：**自己直接回答** / **直接派发单 agent**（带 Task、Params）/ **复杂任务**（拆成多步，每步指定 Agent + Task + Params）/ **无法完成**（请用户澄清）。TUI 的 main 路由使用 `run_unified()` 执行该流程。
- **派发**：`WorkflowOrchestrator.run_unified()`（统一四类决策）、`_analyze_intent()` + `dispatch()`（路由为 dispatch 时）、`dispatch_async()` / `dispatch_parallel_async()`。
- **并行**：支持多 Agent 并发（如 `dispatch_parallel_async`）及工具级 DAG（`{{call_id.output.field}}`），详见 `docs/agent-mailbox-schema.md`。
- **安全**：ToolFilter 控制工具权限；Bash 使用 BashRestrictedFilter（白名单/黑名单/确认）。

---

## 使用 Orchestrator

需要多 Agent 协同（规划、实现、评审、测试）时使用 `/orchestrator`：

```bash
/orchestrator "Plan feature: ..."
/orchestrator "Implement feature: ..." --enforce-quality
/orchestrator "Test feature: ..."
```

流程：Planner 规划 → Coder 按 TDD 实现 → **每次修改后 Reviewer 通过** → Bash 跑 pytest/mypy/flake8 与质量报告。

---

## Best Practices

1. **目标清晰**：任务有明确目的与验收标准。
2. **先规划**：复杂任务用 Planner 拆解为原子步骤（TDD 优先）。
3. **严格 TDD**：先写测试（Red）→ 实现通过（Green）→ 必要时重构。
4. **每次修改后 Review**：Coder 改完必过 Reviewer（架构 + 质量），再进 Bash；Reject 则回 Coder 修改。
5. **质量闭环**：Bash 跑完 pytest/mypy/flake8 后再视为完成。
6. **文档同步**：工作流或约定变更时更新 CLAUDE.md。

---

## Coding Standards

### Rich 输出样式

使用 Rich Console 时，复合样式标签必须完整闭合：

```python
# 正确
console.print("[dim yellow]文本[/dim yellow]")
# 错误 - 闭合不匹配会 MarkupError
console.print("[dim yellow]文本[/dim]")  # Error!
```

- 复合样式：`[style color]...[/style color]` 必须成对一致。
- 单一样式可用 `[/]` 简写。

---

## Project Status

仓库包含 TUI、多 Agent 编排与子代理（Explorer/Planner/Coder/Reviewer/Bash），工作流与 TDD + 每次修改后 Review 已写入本文档。
