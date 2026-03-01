# Mini-Coder 子代理系统使用指南

本指南说明如何使用 mini-coder 的子代理系统进行开发。子代理是外部 Claude Code 技能，通过 CLI 调用来辅助开发 mini-coder 项目本身。

## 系统概述

### 子代理列表

| 子代理 | 中文名称 | 主要职责 |
|--------|----------|----------|
| orchestrator | 主编排器 | 工作流协调、任务路由、死循环检测 |
| architectual-consultant | 架构顾问 | 模式识别、技术选型、最佳实践建议 |
| planner | 规划师 | 任务分解、TDD 规划、依赖管理 |
| implementer | 执行工程师 | 代码实现、TDD 实践、代码质量 |
| tester | 环境测试员 | 测试执行、质量验证、覆盖率审计 |

### 工作流

```
用户请求 → Orchestrator（协调）
              ↓
    ┌─────────┼─────────┐
    ↓         ↓         ↓
Planner → Architectural → Implementer
    ↓         ↓         ↓
        └─────→──────┘
              ↓
          Tester（验证）
```

## 快速开始

### 1. 启动新任务

```bash
# 使用 Orchestrator 启动新任务
/orchestrator "实现用户认证功能"

Orchestrator 将：
1. 创建任务并跟踪状态
2. 根据任务类型路由到适当的子代理
3. 监控任务进度
4. 检测死循环并触发干预
```

### 2. 获取架构建议

```bash
# 使用 Architectural Consultant 获取技术建议
/architectural-consultant "为用户认证模块提供架构建议"

Architectural Consultant 将：
1. 分析需求
2. 搜索知识库（OpenCode、HelloAgent）
3. 必要时进行网络搜索
4. 提供技术选型对比
5. 给出最佳实践建议
```

### 3. 创建实施计划

```bash
# 使用 Planner 生成实施计划
/planner "实现用户认证功能"

Planner 将：
1. 分析项目结构
2. 生成 implementation_plan.md
3. 强制 TDD 序列（红-绿-重构）
4. 规划依赖关系
5. 识别边界条件

### 4. 实现代码

```bash
# 使用 Implementer 实施代码
/implementer "实施步骤 1.2：User 模型"

Implementer 将：
1. 遵循 TDD 红绿重构循环
2. 编写完整的类型提示（Type Hints）
3. 添加 Google 风格 Docstrings
4. 使用 str_replace 工具高效编辑
5. 确保代码高内聚低耦合
```

### 5. 测试验证

```bash
# 使用 Tester 验证代码质量
/tester "运行所有测试"

Tester 将：
1. 运行 pytest 测试
2. 执行 mypy 类型检查
3. 检查代码覆盖率
4. 运行 flake8 代码风格检查
5. 生成详细测试报告
```

## 配置文件

### 子代理配置（config/subagents.yaml）

```yaml
# 子代理行为配置
orchestrator:
  max_retries: 3
  dead_loop_threshold: 4
  parallel_safe_steps: []

architectural-consultant:
  enable_web_search: true
  max_search_results: 5
  knowledge_sources:
    - opencode
    - helloagent
    - custom

planner:
  tdd_enforced: true
  coverage_requirement: 0.8
  max_plan_depth: 5

implementer:
  token_optimization: true
  prefer_str_replace: true
  code_quality_level: high

tester:
  coverage_threshold: 0.8
  type_checking: strict
  style_checking: enabled
  timeout_seconds: 30
```

### 知识库配置（config/knowledge-base.yaml）

```yaml
# 知识库配置
sources:
  opencode:
    repo: "https://github.com/anomalyco/opencode"
    patterns:
      - sandbox_isolation
      - environment_management
    auto_update: true
    update_interval_days: 7

  helloagent:
    repo: "https://github.com/jjyaoao/helloagents"
    patterns:
      - self_reflection
      - memory_mechanisms
    auto_update: true
    update_interval_days: 14

  local:
    path: "docs/knowledge-base"
    auto_update: false

search:
  use_vector_search: false
  max_results_per_query: 10
  cache_enabled: true
  cache_size_mb: 100
```

### 工作流配置（config/workflow.yaml）

```yaml
# 工作流配置
phases:
  - name: planning
    required_agent: planner
    output: implementation_plan.md
    timeout_minutes: 5

  - name: architecture
    required_agent: architectural-consultant
    output: architecture_recommendation.md
    timeout_minutes: 10

  - name: implementation
    required_agent: implementer
    output: implemented_code.py
    timeout_minutes: 30

  - name: testing
    required_agent: tester
    output: test_report.json
    timeout_minutes: 10

rules:
  enforce_sequence: true
  allow_parallel: []
  require_phase_completion: true

intervention:
  auto_trigger: true
  intervention_threshold: 3
  escalate_to: human
```

## 知识库使用

### 访问知识库

知识库位于 `docs/knowledge-base/` 目录，包含：

```
docs/knowledge-base/
├── index.md (索引文件)
├── opencode-patterns/ (OpenCode 模式)
│   ├── sandbox-isolation.md
│   └── environment-management.md
├── helloagent-patterns/ (HelloAgent 模式)
│   └── self-reflection.md
└── python-best-practices/ (Python 最佳实践)
    ├── data-validation.md
    └── type-hints.md
```

### 更新知识库

```bash
# 更新 OpenCode 模式
git -C docs/knowledge-base/opencode-code clone \
  --depth 1 \
  https://github.com/anomalyco/opencode.git

# 更新 HelloAgent 模式
git -C docs/knowledge-base/helloagent-code clone \
  --depth 1 \
  https://github.com/jjyaoao/helloagents.git

# 提取关键文件到知识库
cp docs/knowledge-base/opencode-code/src/opencode/sandbox.py \
   docs/knowledge-base/opencode-patterns/sandbox-isolation.md

cp docs/knowledge-base/helloagent-code/code/chapter9/codebase_maintainer.py \
   docs/knowledge-base/helloagent-patterns/self-reflection.md
```

## 常见工作流场景

### 场景 1：实现新功能

```bash
# 1. Orchestrator 启动任务
/orchestrator "开始任务：实现用户认证功能"

# Orchestrator 自动调用 Planner

# 2. Planner 生成计划
/planner "实现用户认证功能"
# 输出：implementation_plan.md

# 3. 获取架构建议
/architectural-consultant "为用户认证提供架构建议"
# 输出：技术选型对比表、最佳实践

# 4. 实现代码
/implementer "按照计划实施"
# 逐个步骤实施，每个步骤包含测试和实现

# 5. 验证质量
/tester "运行测试验证"
# 输出：测试报告、覆盖率、类型检查结果

# 6. Orchestrator 汇聚结果
/orchestrator "完成当前任务"
# 输出：完整的任务报告
```

### 场景 2：修复 Bug

```bash
# 1. Orchestrator 启动修复任务
/orchestrator "开始修复：登录页面崩溃问题"

# 2. Planner 分析问题
/planner "修复登录页面崩溃"
# 输出：问题分析、修复步骤

# 3. 如果需要架构建议
/architectural-consultant "分析崩溃原因"
# 输出：可能的根本原因、替代方案

# 4. Implementer 实施修复
/implementer "实施修复步骤"
# TDD 方式：先写失败测试，再实现修复

# 5. Tester 验证修复
/tester "验证修复"
# 输出：修复验证报告

# 6. 如果失败，触发自我反思
/tester "检测到死循环"
# Orchestrator 自动触发自我反思和替代方案
```

### 场景 3：代码重构

```bash
# 1. Planner 规划分解重构任务
/planner "重构用户模块以提高内聚"

# 2. Architectural Consultant 提供建议
/architectural-consultant "重构建议：模块化策略"

# 3. Implementer 执行重构
/implementer "逐步重构，保持测试通过"

# 4. Tester 验证重构质量
/tester "验证重构后质量"
```

## CLI 命令示例

### 直接调用子代理

```bash
# 调用 Orchestrator
/orchestrator [参数]

# 调用 Architectural Consultant
/architectural-consultant [参数]

# 调用 Planner
/planner [参数]

# 调用 Implementer
/implementer [参数]

# 调用 Tester
/tester [参数]
```

### 常用命令序列

```bash
# 完整的开发流程
1. /orchestrator "开始新功能开发"
2. /planner "分析需求并创建计划"
3. /architectural-consultant "获取架构建议"
4. /implementer "实施功能（分步骤）"
5. /tester "验证实现"
6. /orchestrator "完成并汇总结果"

# Bug 修复流程
1. /orchestrator "开始修复 Bug"
2. /planner "分析并规划修复"
3. /architectural-consultant "如果需要，获取建议"
4. /implementer "实施修复"
5. /tester "验证修复"
```

## 监控和调试

### 查看任务状态

```bash
# 查看当前任务状态
/orchestrator "检查任务状态"

# 输出示例：
"""
当前任务：task-001
状态：implementing
进度：50%
最近操作：
  - planner: 生成完成
  - implementer: 正在实施步骤 1
"""
```

### 调试子代理

```bash
# 启用详细输出
/tester --verbose "运行测试"

# 查看子代理日志
# 日志位置：.mini-coder/logs/

# 检查配置文件
cat config/subagents.yaml
cat config/knowledge-base.yaml
cat config/workflow.yaml
```

## 最佳实践

### 1. 遵循 TDD 红绿重构

1. **红（Red）**：编写失败测试
2. **绿（Green）**：编写最小实现
3. **重构（Refactor）**：优化代码

### 2. 使用 Orchestrator 协调工作

- 始终通过 Orchestrator 启动任务
- 让 Orchestrator 处理任务路由和状态管理
- 利用 Orchestrator 的死循环检测

### 3. 充分利用 Architectural Consultant

- 在复杂功能前咨询架构建议
- 利用知识库中的模式
- 考虑提供的替代方案

### 4. 保持测试质量

- 确保测试覆盖率 ≥ 80%
- 运行类型检查（mypy）
- 遵循代码风格规范

### 5. 定期更新知识库

- 定期从 OpenCode 和 HelloAgent 获取最新模式
- 添加自定义最佳实践到知识库
- 更新知识库元数据

## 故障排除

### 常见问题

**问题 1**：子代理未响应
- **解决方案**：检查 Claude Code CLI 连接和配置

**问题 2**：测试覆盖率不足
- **解决方案**：使用 /tester 识别未覆盖的代码

**问题 3**：死循环检测未触发
- **解决方案**：检查 Orchestrator 配置中的阈值设置

**问题 4**：知识库搜索无结果
- **解决方案**：更新知识库或调整搜索参数

## 贡献

### 添加新的知识模式

1. 在 `docs/knowledge-base/` 的相应目录创建新文件
2. 使用 YAML frontmatter 添加元数据
3. 更新 `docs/knowledge-base/index.md` 索引
4. 测试 Architectural Consultant 能否找到新模式

### 改进子代理技能

1. 编辑 `.claude/skills/` 中的相应 SKILL.md 文件
2. 改进指令和示例
3. 更新检查清单
4. 测试改进后的技能

## 相关资源

- [OpenSpec 工作流文档](../openspec/README.md)
- [subagent.md](../subagent.md) - 详细的子代理定义
- [CLAUDE.md](../CLAUDE.md) - 项目开发指南
- [Pydantic 文档](https://docs.pydantic.dev/)
- [pytest 文档](https://docs.pytest.org/)

## 许可证

本系统和相关文档遵循 mini-coder 项目的许可证。
