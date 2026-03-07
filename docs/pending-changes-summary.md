# 未提交修改分析摘要（git status + git diff）

## 一、修改概览（33 个已跟踪文件 + 若干未跟踪）

### 1. 代码与架构

| 区域 | 变更要点 |
|------|-----------|
| **agents** | `__init__.py`：导出 output_parser（MainAgentParser、ReviewerParser、QualityReportParser 等）；模块 doc 补充 BaseEnhancedAgent/BaseAgent 架构说明。`cli.py`：日志格式增加 `%(filename)s:%(lineno)d`。`scheduler.py`：ParallelScheduler 仅保留 Agent 级并发，Tool 级调度说明改为使用 ToolScheduler。 |
| **memory/embeddings** | 默认改为 fastembed（本地、无 PyTorch）；可选 embedding API（从 config/llm.yaml 读取 backend、use_api、api_key、base_url、model、batch_size）；移除 sentence-transformers。 |
| **tools** | `__init__.py`：导出 event_adapter 等。`base.py`、`prompt_loader.py`：小改动。 |
| **tui/__main__.py** | 新增 `--log-level` 参数；日志文件名带时间戳（如 tui_20260306_154855.log）；日志格式增加 `%(filename)s:%(lineno)d`。 |

### 2. 配置与依赖

- **config/llm.yaml**：embeddings 段（fastembed/API）、dashscope timeout 等。
- **config/tools.yaml**：工具相关配置。
- **pyproject.toml**：依赖调整（如 semantic 相关）。

### 3. 文档与 OpenSpec

- **docs/**：agent-mailbox-schema、project-notes-enhancement、tools-architecture-design、tui-agent-display-design 等更新。
- **openspec/**：enhance-tui-agent-display、archive enhance-project-notes、specs/semantic-search 等。

### 4. 测试

- **tests/agents**：test_parallel_workflow、test_scheduler 调整；新增 test_output_parser（未跟踪）。
- **tests/memory**：test_embeddings、test_project_notes（fastembed/API）。
- **tests/tools**：test_command 扩展；新增 test_event_adapter（未跟踪）。

### 5. 未跟踪文件

- **src/mini_coder/agents/output_parser.py**：主代理/Reviewer/Bash 结构化输出解析。
- **src/mini_coder/tools/event_adapter.py**：工具事件适配 TUI。
- **tests/agents/test_output_parser.py**、**tests/tools/test_event_adapter.py**。
- **docs/**：agents-tools-architecture-review、project-code-review、tui-agent-display-design-REVIEW、tui-orchestrator-flow-analysis 等。
- **openspec/changes/parallel-scheduler/**：并行调度相关变更。
- **.claude/worktrees/**：本地 worktree，一般不提交。

---

## 二、建议提交范围

- **纳入提交**：除 `.claude/settings.local.json`、`.claude/worktrees/` 外的所有已修改文件，以及未跟踪的 output_parser、event_adapter、对应测试、docs 中与本次改动相关的文档、openspec/changes/parallel-scheduler。
- **不提交**：`.claude/settings.local.json`（本地配置）、`.claude/worktrees/`（本地 worktree 目录）。
