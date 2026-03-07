# Agents 与 Tools 架构审视报告

> **更新日志**:
> - 2026-03-07: 完成修复项 #16, #17, #18

## 一、核心问题总结

### 1. ~~主 Agent 结构化输出未被代码解析~~ ✅ 已修复

**原问题**:
- `_analyze_intent()` 使用关键词匹配，不解析 `【简单回答】`/`【复杂任务】`/`【无法处理】` 结构

**修复** (2026-03-07):
- 新增 `output_parser.py`，实现 `MainAgentParser`、`ReviewerParser`、`QualityReportParser`
- 支持 `parse_main_agent_output()`、`parse_reviewer_output()`、`parse_quality_report()` 便捷函数
- 测试覆盖：`tests/agents/test_output_parser.py` (16 tests, 100% coverage)

---

### 2. ~~两套并行的 Agent 实现~~ ✅ 已修复

**原问题**:
- `base.py` 和 `enhanced.py` 都定义了 `PlannerAgent`, `CoderAgent`，接口不同

**修复** (2026-03-07):
- 移除 `base.py` 中的重复 `PlannerAgent`, `CoderAgent`, `TesterAgent` 定义
- `AgentTeam` 现在从 `enhanced.py` 导入这些类
- 保留 `base.py` 中的 `ExplorerAgent`, `ReviewerAgent`, `BashAgent`, `GeneralPurposeAgent`, `MiniCoderGuideAgent`

---

### 3. ~~Bash vs Tester 命名混乱~~ ✅ 已修复

**原问题**:
- Prompt 用 Bash，设计文档用 Tester，代码两者都有

**修复** (2026-03-07):
- `SubAgentType` 枚举移除 `TESTER`，统一使用 `BASH`
- 与 `prompts/system/main-agent.md` 中的子代理列表保持一致

---

### 4. ~~Prompt 文件未被 Agent 默认加载~~ ✅ 已修复

**原问题**:
- Agent 硬编码英文 prompt，未加载中文 prompt 文件

**修复** (2026-03-07):
- `BaseEnhancedAgent` 添加 `DEFAULT_PROMPT_PATH` 和 `_load_system_prompt()` 方法
- `PlannerAgent`、`CoderAgent`、`TesterAgent` 设置了 `DEFAULT_PROMPT_PATH`
- `_build_planning_prompt()` 和 `_build_coding_prompt()` 使用加载的 prompt

---

### 5. 子 Agent 结构化输出未强制执行 ⚠️ 部分完成

**原问题**:
- 定义了结构化输出格式，但未校验

**修复** (2026-03-07):
- ✅ 实现了 `ReviewerParser` 解析 `[Pass]`/`[Reject]`
- ✅ 实现了 `QualityReportParser` 解析 `【质量报告】`
- ⚠️ 仍需集成到 Agent 执行流程中进行自动校验

---

### 6. ~~Agent 类型枚举不一致~~ ✅ 已修复

**原问题**:
- `TESTER` 在枚举中但不在 prompt 定义的子代理列表中

**修复** (2026-03-07):
- `SubAgentType` 枚举与 `prompts/system/main-agent.md` 保持一致
- 当前枚举：`EXPLORER`, `PLANNER`, `CODER`, `REVIEWER`, `BASH`, `MINI_CODER_GUIDE`, `GENERAL_PURPOSE`

---

## 二、结构化输出规格对比

### 主 Agent (main-agent.md)

| 输出类型 | 格式 | 代码解析 |
|---------|------|---------|
| 【简单回答】 | 直接文本 | ✅ `MainAgentParser` |
| 【复杂任务】 | 问题类型 + 子问题列表 | ✅ `MainAgentParser` |
| 【无法处理】 | 说明文本 | ✅ `MainAgentParser` |

### 子 Agent 对比

| Agent | Prompt 输出格式 | 代码返回类型 | 格式解析 |
|-------|----------------|-------------|---------|
| Explorer | `【探索结果】目标/发现/建议` | `AgentResult` | ⚠️ 待实现 |
| Planner | `implementation_plan.md` | `AgentResult.artifacts` | N/A |
| Coder | `【实现结果】修改文件/内容/待处理` | `AgentResult` | ⚠️ 待实现 |
| Reviewer | `[Pass]` 或 `[Reject]` | `AgentResult` | ✅ `ReviewerParser` |
| Bash | `【质量报告】测试/类型/风格/覆盖率` | `AgentResult` | ✅ `QualityReportParser` |

---

## 三、职责与场景一致性分析

### ✅ 一致的部分

| Agent | Prompt 职责 | 代码实现 | 一致性 |
|-------|------------|---------|--------|
| Explorer | 只读探索 | `ReadOnlyFilter` | ✅ |
| Planner | TDD 规划 | `ReadOnlyFilter` | ✅ |
| Coder | 代码实现 | `FullAccessFilter` | ✅ |
| Reviewer | 质量评审 | `ReadOnlyFilter` | ✅ |
| Bash | 终端执行 | `BashRestrictedFilter` | ✅ |

---

## 四、已完成的修复

### Task #16: 统一 Agent 架构实现 ✅

- 移除 `base.py` 中的重复 Agent 类定义
- 更新 `AgentTeam` 使用 `enhanced.py` 的实现
- 更新 `SubAgentType` 枚举，移除 `TESTER`

### Task #17: Agent Prompt 文件集成 ✅

- `BaseEnhancedAgent` 添加 prompt 加载能力
- 各 Agent 设置 `DEFAULT_PROMPT_PATH`
- 更新 `__init__.py` 导出

### Task #18: 结构化输出解析器实现 ✅

- 实现 `MainAgentParser`、`ReviewerParser`、`QualityReportParser`
- 添加便捷函数：`parse_main_agent_output()`、`parse_reviewer_output()`、`parse_quality_report()`
- 完整测试覆盖 (16 tests)

---

## 五、Tools 审视

### CommandTool (`tools/command.py`)

| 项目 | Prompt 定义 | 代码实现 | 一致性 |
|------|------------|---------|--------|
| 安全策略 | 黑/白名单/需确认 | `SecurityMode` + `BannedCommands` | ✅ |
| 结构化输出 | `stdout/stderr/exit_code/execution_time_ms` | `ToolResponse` | ✅ |
| Prompt 加载 | `{{security_mode}}` 等占位符 | `_get_prompt_context()` | ✅ |

**结论**: CommandTool 实现与 prompt 一致。

---

## 六、后续待办

1. [ ] 将结构化输出解析集成到 Agent 执行流程
2. [ ] 实现 Explorer 和 Coder 的结构化输出解析器
3. [ ] 添加 LLM 输出格式校验（当输出不符合格式时的回退策略）