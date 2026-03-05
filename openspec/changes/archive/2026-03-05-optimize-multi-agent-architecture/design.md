# Design: Optimize Multi-Agent Architecture

## Context

### Background

mini-coder 项目当前的多 Agent 架构基于 `enhanced.py` 中的 `BaseEnhancedAgent` 基类实现，采用状态机驱动的工作流引擎（`orchestrator.py`）协调 Planner/Coder/Tester 三个 Agent。该架构存在以下局限性：

1. **提示词硬编码**：系统提示词直接写在 Python 代码中（如 `CoderAgent._build_coding_prompt()`），修改提示词需要改动代码并重新部署
2. **Agent 角色粗粒度**：仅有 Planner/Coder/Tester 三元组，缺乏专业的代码探索（Explorer）和质量评审（Reviewer）角色
3. **工具权限与 Agent 角色解耦不足**：ToolFilter 独立于 Agent 定义，运行时绑定逻辑不够直观
4. **缺少项目级定制能力**：无法根据不同项目的 CLAUDE.md 或编码规范动态调整 Agent 行为

### Reference Architecture

参考 Claude Code CLI 的子代理架构（基于社区逆向工程）：

| 子代理 | 用途 | 工具范围 | 实现方式 |
|--------|------|----------|---------|
| Explore | 只读代码库搜索 | Read, Grep, Glob | 系统提示词 + 工具过滤器 |
| Plan | 需求分析与规划 | Read, Grep, WebSearch | 系统提示词 + 工具过滤器 |
| General-purpose | 复杂多步任务 | 全部工具 | 系统提示词 + 工具过滤器 |

Claude Code 采用"代码框架 + 动态提示词注入"混合模式：
- 执行流程、工具循环、上下文管理由 TypeScript 源码硬编码
- 身份与行为由系统提示词定义，从编译后的字符串中选取、拼接、插值
- 支持自定义 Agent（`~/.claude/agents/*.md`）

### Constraints

- 保持 Python 3.10+ 语法要求
- 保持现有 LLM 服务接口（ZHIPU AI / DashScope）
- 保持与 `WorkflowOrchestrator` 的向后兼容性
- 提示词模板使用 Markdown 格式，支持占位符插值

## Goals / Non-Goals

**Goals:**

1. **提示词与代码分离**：系统提示词从 `prompts/system/*.md` 动态加载
2. **5 个核心子代理**：Explorer/Planner/Coder/Reviewer/Bash 独立实现（Reviewer 合并 CodeReviewer 职责）
3. **动态提示词注入**：支持占位符替换（如 `{{GLOB_TOOL_NAME}}`、`{{coding_standards}}`）
4. **工具权限与 Agent 绑定**：每个 Agent 类内置对应的 ToolFilter 逻辑
5. **项目规范注入**：支持从 `prompts/templates/project-context.md` 读取项目规范并注入提示词

**Non-Goals:**

1. **不改变工作流状态机**：`WorkflowOrchestrator` 的状态转换逻辑保持不变
2. **不引入新的 LLM 服务接口**：保持现有 `llm_service.chat()` 调用方式
3. **不改变黑板模式**：`Blackboard` 数据结构和接口保持不变
4. **不支持运行时 Agent 热切换**：Agent 类型在初始化时确定

## Decisions

### Decision 1: 提示词存储位置

**选择**: 使用 `prompts/system/*.md` 文件存储系统提示词

**理由**:
- `prompts/` 目录语义清晰，专门存放项目自身的提示词配置
- 与 `knowledge-base/` 分离，避免目录职责混乱（knowledge-base 只存放外部参考资料）
- 与 `tests/` 分离，测试代码在 tests/ 目录
- Markdown 格式便于人类阅读和版本控制
- 支持多语言扩展（如 `subagent-coder-zh.md`）

**目录结构**:
```
prompts/
├── system/                       # 系统提示词
│   ├── main-agent.md
│   ├── subagent-explorer.md
│   ├── subagent-planner.md
│   ├── subagent-coder.md
│   ├── subagent-reviewer.md
│   └── subagent-bash.md
└── templates/                    # 提示词模板片段
    ├── coding-standards.md
    └── project-context.md
```

**注意**: 不使用 CLAUDE.md，因为它是 Claude 专用的配置文件。mini-coder 应该有自己的项目提示词配置。

**替代方案**:
| 方案 | 优点 | 缺点 | 未选原因 |
|------|------|------|---------|
| Python 代码内常量 | 类型安全、编译时检查 | 修改提示词需重新部署 | 不够灵活 |
| YAML 配置文件 | 结构化好、支持嵌套 | 对非技术人员不友好 | Markdown 更易读 |
| 数据库存储 | 支持运行时更新 | 增加运维复杂度 | 过度设计 |
| knowledge-base/ | 与现有知识管理一致 | 目录职责混乱 | prompts/ 语义更清晰 |

### Decision 2: 动态提示词注入机制

**选择**: 使用 `PromptLoader` 类实现加载和插值

```python
class PromptLoader:
    def load(self, agent_type: str, context: Dict = None) -> str:
        # 1. 从缓存或文件读取
        # 2. 占位符替换：prompt.replace(f"{{{{{key}}}}}", str(value))
        # 3. 返回插值后的提示词
```

**占位符命名规范**: `{{identifier}}` 使用双花括号，避免与 Markdown 语法冲突

**预定义占位符**:
| 占位符 | 含义 | 默认值 |
|--------|------|--------|
| `{{GLOB_TOOL_NAME}}` | Glob 工具实际名称 | "Glob" |
| `{{GREP_TOOL_NAME}}` | Grep 工具实际名称 | "Grep" |
| `{{READ_TOOL_NAME}}` | Read 工具实际名称 | "Read" |
| `{{thoroughness}}` | Explorer 探索深度 | "medium" |
| `{{coding_standards}}` | 项目编码规范 | 从 config/coding-standards.md 读取 |
| `{{project_name}}` | 项目名称 | 从 CLAUDE.md 读取 |

### Decision 3: Agent 类结构

**选择**: 每个子代理继承 `BaseEnhancedAgent`，内置对应的 Capabilities 类。Reviewer 合并 CodeReviewer 职责。

```python
class ExplorerCapabilities(AgentCapabilities):
    def __init__(self):
        super().__init__(
            allowed_tools={"Read", "Grep", "Glob"},
            max_tool_calls=10,
        )

class ExplorerAgent(BaseEnhancedAgent):
    AGENT_TYPE = "explorer"
    DEFAULT_CAPABILITIES = ExplorerCapabilities()

class ReviewerCapabilities(AgentCapabilities):
    """合并原 Reviewer + CodeReviewer 职责"""
    def __init__(self):
        super().__init__(
            allowed_tools={"Read", "Grep", "Glob"},
            max_tool_calls=8,
        )

class ReviewerAgent(BaseEnhancedAgent):
    """代码质量评审 + 架构对齐检查"""
    AGENT_TYPE = "reviewer"
    DEFAULT_CAPABILITIES = ReviewerCapabilities()
```

**理由**:
- 保持与现有 `BaseEnhancedAgent` 的继承关系
- Capabilities 类内聚工具权限定义
- 合并 Reviewer/CodeReviewer 减少角色冗余
- 支持运行时自定义配置

### Decision 4: 工具过滤器与 Agent 绑定

**选择**: 在 Agent 初始化时自动应用对应的 ToolFilter

```python
class BaseEnhancedAgent:
    def __init__(self, ...):
        self.tool_filter = self._create_tool_filter()

    def _create_tool_filter(self) -> ToolFilter:
        # 根据 Agent 类型返回对应过滤器
```

**过滤器映射**:
| Agent | ToolFilter |
|-------|-----------|
| Explorer | ReadOnlyFilter |
| Planner | PlannerFilter (ReadOnly + WebSearch) |
| Coder | FullAccessFilter |
| Reviewer | ReadOnlyFilter |
| Bash | BashRestrictedFilter |

### Decision 5: 主代理派发逻辑

**选择**: 在 `Orchestrator` 中实现基于关键词匹配的意图分析 + LLM 兜底

```python
class Intent(Enum):
    EXPLORER = "explorer"
    PLANNER = "planner"
    CODER = "coder"
    REVIEWER = "reviewer"
    BASH = "bash"

def _analyze_intent(self, intent: str) -> Intent:
    # 1. 关键词匹配（快速路径）
    if any(kw in intent for kw in ["看看", "找找", "探索", "explore", "search"]):
        return Intent.EXPLORER
    elif any(kw in intent for kw in ["规划", "计划", "拆解", "plan", "design"]):
        return Intent.PLANNER
    elif any(kw in intent for kw in ["实现", "添加", "修改", "implement", "create"]):
        return Intent.CODER
    elif any(kw in intent for kw in ["评审", "检查", "review", "quality"]):
        return Intent.REVIEWER
    elif any(kw in intent for kw in ["测试", "运行", "execute", "test", "bash"]):
        return Intent.BASH

    # 2. LLM 兜底（模糊意图）
    return self._llm_analyze_intent(intent)
```

**理由**:
- 简单直接，易于调试和优化
- 支持中文和英文关键词
- 兜底策略：让 LLM 决策模糊意图

**替代方案**:
- 使用 LLM 分类意图：增加延迟和成本
- 使用规则引擎：过度设计

### Decision 6: 项目规范注入方式

**选择**: 从 `prompts/templates/project-context.md` 读取项目规范，通过 `{{project_context}}` 占位符注入

**理由**:
- 不依赖 CLAUDE.md（Claude 专用）
- mini-coder 应该有自己独立的项目提示词配置
- 配置文件方式支持多项目共享规范

## Risks / Trade-offs

### Risks

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 提示词文件缺失导致 Agent 无法初始化 | 高 | 提供内置兜底提示词（代码内常量） |
| 占位符替换逻辑与 Markdown 语法冲突 | 中 | 使用双花括号 `{{}}`，避免与 Jinja2 冲突 |
| 工具过滤器被绕过（安全漏洞） | 高 | 在 ToolFilter 层做最终校验，不信任 Agent |
| 提示词加载性能（I/O 瓶颈） | 低 | 使用缓存（PromptLoader._cache） |
| 向后兼容性破坏 | 中 | 保留原有类名导入，使用 deprecation warning |

### Trade-offs

| 决策 | 收益 | 成本 |
|------|------|------|
| 提示词与代码分离 | 便于迭代、审计、多语言 | 增加文件数量、部署复杂度 |
| 动态插值 | 支持项目级定制 | 增加运行时处理逻辑 |
| 5 个子代理独立实现 | 职责清晰、易于测试 | 代码量增加、维护成本上升 |
| 关键词匹配意图分析 | 简单、可预测 | 不够灵活，需维护关键词列表 |

## Migration Plan

### Phase 1: 基础设施（Week 1）

1. 创建 `prompts/system/` 和 `prompts/templates/` 目录
2. 编写 5 个核心子代理的提示词模板
3. 实现 `PromptLoader` 类（支持占位符验证）
4. 扩展现有 `BaseEnhancedAgent` 支持动态插值

**验收标准**:
- [ ] `PromptLoader.load("explorer", {...})` 返回插值后的提示词
- [ ] 提示词文件修改后无需重启即可生效（开发模式）
- [ ] 未替换占位符检测并警告

### Phase 2: 子代理重构（Week 2）

1. 创建 `ExplorerAgent`、`ReviewerAgent`、`BashAgent` 类
2. 重构 `PlannerAgent`、`CoderAgent` 使用新架构
3. Reviewer 合并 CodeReviewer 职责（架构对齐 + 代码质量）
4. 实现工具过滤器与 Agent 绑定逻辑
5. 编写单元测试

**验收标准**:
- [ ] 每个 Agent 类通过单元测试
- [ ] 工具过滤器正确拦截非法操作
- [ ] Reviewer 统一输出评审报告

### Phase 3: 主代理集成（Week 3）

1. 扩展 `WorkflowOrchestrator` 支持子代理派发
2. 实现意图分析逻辑
3. 实现记忆读写对接
4. 实现终端命令安全层

**验收标准**:
- [ ] 完整工作流测试通过
- [ ] 意图分析准确率 >= 90%

### Phase 4: 测试与优化（Week 4）

1. 编写集成测试（完整工作流）
2. 提示词调优（A/B 测试）
3. 性能优化（缓存、懒加载）
4. 文档更新

**验收标准**:
- [ ] 集成测试通过率 >= 95%
- [ ] 提示词迭代版本 >= 3 次
- [ ] 文档覆盖率 100%

### Rollback Strategy

若部署后发现问题，可通过以下方式回滚：

1. **配置开关**: 在 `config/agents.yaml` 中添加 `use_legacy_agents: true` 切换回旧 Agent
2. **代码回滚**: Git revert 最近一次提交
3. **渐进式发布**: 先在小范围测试环境验证，再全量发布

## Open Questions

1. **提示词版本管理**: 是否需要支持提示词的版本控制和灰度发布？
2. **多语言支持**: 是否需要支持提示词的多语言自动切换（根据用户 locale）？
3. **提示词评估**: 如何量化评估提示词的质量（如任务完成率、用户满意度）？
4. **热更新机制**: 是否需要支持提示词的运行时热更新（无需重启服务）？
