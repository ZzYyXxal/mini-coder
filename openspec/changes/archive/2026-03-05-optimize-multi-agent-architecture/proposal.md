# Proposal: Optimize Multi-Agent Architecture

## Why

当前 mini-coder 的多 Agent 架构基于 LangGraph/AutoGen/CrewAI 风格的"状态机 + 黑板"模式实现，但存在以下问题：

1. **Agent 职责边界模糊**：当前的 Planner/Coder/Tester 三元组缺乏更细粒度的专业化分工，如代码探索、架构咨询、代码评审等角色缺失或未明确定义
2. **工具权限控制不够精细**：现有 ToolFilter 体系（ReadOnlyFilter/FullAccessFilter/StrictFilter）未与具体 Agent 角色深度绑定
3. **提示词与代码耦合**：系统提示词硬编码在 Python 源码中，不便于迭代优化和多语言支持
4. **缺少动态提示词注入机制**：无法根据项目规范（如 CLAUDE.md）动态调整 Agent 行为
5. **Claude Code 子代理架构的启发**：参考 Claude Code 的"代码框架 + 动态提示词注入"混合模式，以及 Explore/Plan/General-purpose 三元组设计，可以实现更清晰的 Agent 职责分离

本优化旨在采用 Claude Code 风格的架构，为 mini-coder 主题提供更合理、更可维护的多 Agent 实现。

## What Changes

### 架构模式变化

从当前的"状态机驱动 + 硬编码提示词"模式转变为"代码框架 + 动态提示词注入"混合模式：

| 组件 | 当前实现 | 优化后 |
|------|---------|--------|
| **执行流程** | 状态机硬编码（保持不变） | 状态机硬编码（保持不变） |
| **身份定义** | Python 代码内硬编码 | 从 `prompts/system/*.md` 动态加载 |
| **子代理类型** | Planner/Coder/Tester | Explorer/Planner/Coder/Reviewer/Bash（无专家代理） |
| **工具权限** | ToolFilter 类 | ToolFilter 与 Agent 角色深度绑定 |
| **项目规范** | 无 | 支持 CLAUDE.md 动态注入 |

### Agent 角色重组

引入 5 个核心子代理（无专家代理，ArchitecturalConsultant 非必需）：

| 角色 | 职责 | 工具范围 | 过滤器 |
|------|------|----------|--------|
| **Explorer** | 只读代码库搜索 | Read, Grep, Glob, Bash(只读) | ReadOnlyFilter |
| **Planner** | 需求分析与任务规划 | Read, Grep, WebSearch | ReadOnlyFilter (+WebSearch) |
| **Coder** | 代码生成与编辑 | Read, Write, Edit, Grep, Glob, Bash(受限) | FullAccessFilter |
| **Reviewer** | 代码质量评审 + 架构对齐检查 | Read, Grep, Glob | ReadOnlyFilter |
| **Bash** | 终端执行与测试验证 | Read, Bash, Glob | BashRestrictedFilter |

### 提示词文件结构

```
mini-coder/
├── prompts/                          # 新增：Agent 提示词目录
│   ├── system/                       # 系统提示词
│   │   ├── main-agent.md
│   │   ├── subagent-explorer.md
│   │   ├── subagent-planner.md
│   │   ├── subagent-coder.md
│   │   ├── subagent-reviewer.md
│   │   └── subagent-bash.md
│   └── templates/                    # 提示词模板片段
│       ├── coding-standards.md
│       └── project-context.md
├── src/mini_coder/agents/
│   ├── prompt_loader.py              # 新增：提示词加载器
│   ├── base.py                       # 扩展：支持动态插值
│   ├── enhanced.py                   # 重构：5 个子代理独立类
│   └── orchestrator.py               # 扩展：主代理派发逻辑
├── knowledge-base/                   # 保持不变：外部参考资料
│   ├── hello-agents/
│   ├── claude-analysis/
│   └── ...
├── tests/                            # 保持不变：测试代码
│   ├── unit/
│   └── integration/
└── config/
    └── agents.yaml                   # 新增：Agent 配置
```

## Capabilities

### New Capabilities

- **Explorer Agent** (`subagent-explorer`): 只读代码库搜索，支持快速探索代码结构、定位文件、搜索实现
- **Reviewer Agent** (`subagent-reviewer`): 代码质量评审，支持架构对齐检查、类型提示检查、代码规范检查
- **Bash Agent** (`subagent-bash`): 终端执行与测试验证，支持命令白名单/黑名单机制
- **Dynamic Prompt Injection** (`prompt-injection`): 支持从 Markdown 文件加载系统提示词，运行时常量插值替换
- **Project Standards Injection** (`project-standards`): 支持从 CLAUDE.md 或配置文件读取项目规范并注入到 Agent 提示词

### Modified Capabilities

- **Planner Agent**: 从当前的"需求分析 + 规划"扩展为独立角色，增加 WebSearch/WebFetch 能力用于技术调研
- **Coder Agent**: 保持代码实现职责，工具权限与 FullAccessFilter 深度绑定
- **Tester Agent**: 重构为 Bash Agent，职责从"测试执行"扩展为"终端命令执行 + 质量验证"
- **Reviewer Agent**: 合并原 Reviewer 和 CodeReviewer 职责，统一负责代码质量评审和架构对齐检查

## Impact

### 受影响的模块

| 模块 | 变更类型 | 说明 |
|------|---------|------|
| `src/mini_coder/agents/base.py` | 扩展 | 增加 PromptLoader 集成，支持动态插值 |
| `src/mini_coder/agents/enhanced.py` | 重构 | 5 个子代理独立类实现 |
| `src/mini_coder/agents/orchestrator.py` | 扩展 | 主代理派发逻辑，意图分析，终端安全层 |
| `src/mini_coder/agents/prompt_loader.py` | 新增 | 提示词加载器实现 |
| `src/mini_coder/tools/filter.py` | 扩展 | 新增 BashRestrictedFilter，PlannerFilter |
| `prompts/system/` | 新增 | 5 个提示词模板文件 |
| `prompts/templates/` | 新增 | 提示词模板片段 |
| `config/agents.yaml` | 新增 | Agent 配置文件 |

### 依赖关系

- 无新增外部依赖
- 保持现有 Python 3.10+ 要求
- 保持现有 LLM 服务接口（ZHIPU AI / DashScope）

### 向后兼容性

- 保留现有的 `PlannerAgent`、`CoderAgent`、`TesterAgent` 类名（通过导入重定向）
- 现有的 `WorkflowOrchestrator` 接口保持不变
- 现有的 `Blackboard`、`Event`、`AgentCapabilities` 等数据结构保持不变

### 迁移路径

1. **阶段 1**: 创建提示词模板文件，实现 PromptLoader
2. **阶段 2**: 重构 enhanced.py，实现 5 个子代理独立类
3. **阶段 3**: 扩展 orchestrator.py，实现主代理派发逻辑
4. **阶段 4**: 编写集成测试，验证完整工作流
5. **阶段 5**: 文档更新与提示词调优
