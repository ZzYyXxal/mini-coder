# Mini-Coder 知识库索引

本知识库包含从顶级开源项目提取的工程精髓和最佳实践，用于辅助开发 mini-coder 项目本身。

## 知识库结构

```
docs/knowledge-base/
├── index.md (本文件)
├── opencode-patterns/      # OpenCode 沙箱隔离策略
│   └── sandbox-isolation.md
├── helloagent-patterns/    # HelloAgent 自我反思机制
│   ├── self-reflection.md
│   ├── recursive-thinking.md
│   └── codebase-maintainer.md
└── python-best-practices/   # Python 最佳实践
    └── data-validation.md
```

## 快速开始指南

### 1. 使用 Architectural Consultant 获取架构建议

当需要架构建议时，调用 Architectural Consultant 技能：
```bash
# 使用 Architectural Consultant 技能
/architectural-consultant "需要用户认证的架构建议"

Architectural Consultant 将：
1. 分析需求
2. 搜索知识库（OpenCode、HelloAgent）
3. 必要时进行网络搜索
4. 提供技术选型对比
5. 给出最佳实践建议
```

### 2. 下载知识库源代码

以下知识库文件有对应的 GitHub 源代码：

**HelloAgent 递归思维**：
- 源码：https://github.com/datawhalechina/hello-agents/blob/main/docs/chapter9/递归思维和自我反思.md
- 本地文件：docs/knowledge-base/helloagent-patterns/recursive-thinking.md

**HelloAgent 代码库维护助手**：
- 源码：https://github.com/datawhalechina/hello-agents/blob/main/code/chapter9/codebase_maintainer.py
- 本地文件：docs/knowledge-base/helloagent-patterns/codebase-maintainer.md

**OpenCode 沙箱隔离**：
- 源码：https://github.com/anomalyco/opencode
- 本地文件：docs/knowledge-base/opencode-patterns/sandbox-isolation.md

### 下载脚本

使用以下命令下载知识库源代码：

```bash
# 下载 HelloAgent 递归思维文档
curl -o docs/knowledge-base/helloagent-patterns/recursive-thinking.md \
  https://raw.githubusercontent.com/datawhalechina/hello-agents/main/docs/chapter9/递归思维和自我反思.md

# 下载 HelloAgent 代码库维护助手
curl -o docs/knowledge-base/helloagent-patterns/codebase-maintainer.md \
  https://raw.githubusercontent.com/datawhalechina/hello-agents/main/code/chapter9/codebase_maintainer.py

# 或者使用 Python 下载
python3 -c "
import urllib.request
import ssl

urls = [
    'https://raw.githubusercontent.com/datawhalechina/hello-agents/main/docs/chapter9/递归思维和自我反思.md',
    'https://raw.githubusercontent.com/datawhalechina/hello-agents/main/code/chapter9/codebase_maintainer.py'
]

for url in urls:
    filename = url.split('/')[-1]
    print(f'Downloading {filename}...')
    context = ssl._create_unverified_context()
    with urllib.request.urlopen(url, context=context, timeout=60) as f:
        content = f.read().decode('utf-8')
        with open(f'docs/knowledge-base/helloagent-patterns/{filename}', 'w', encoding='utf-8') as file:
            file.write(content)
    print(f'Downloaded {len(content)} bytes')
"
```

### 3. 使用方法

**方法 1：Architectural Consultant 搜索**
- Architectural Consultant 会自动搜索知识库中的相关模式
- 提供源代码的参考和最佳实践建议

**方法 2：直接查阅知识文件**
- 手动查看 `docs/knowledge-base/` 中的文件
- 使用 `grep` 或 `find` 搜索相关内容

**方法 3：使用子代理的提示模板**
- `/planner` - 参考 TDD 规划
- `/implementer` - 参考代码实现
- `/tester` - 参考质量验证
- `/architectural-consultant` - 获取架构建议

## 更新知识库

知识库应该定期更新以获取最新的最佳实践和模式。

### 更新命令

```bash
# 自动更新脚本（需要实现）
python scripts/update_knowledge_base.py

# 手动更新流程
1. 下载最新的源代码
2. 提取关键模式到知识库文件
3. 更新本索引文件
4. 测试 Architectural Consultant 能否找到新模式
```

### 贡献指南

如果你发现更好的模式或最佳实践，欢迎贡献到知识库：

1. 在相应的类别目录创建新的 `.md` 文件
2. 使用 YAML frontmatter 添加元数据
3. 更新本索引文件
4. 使用 OpenSpec 或其他协作工具进行讨论

## 元数据规范

每个知识文件应该包含以下元数据：

```yaml
---
title: 标题
language: python
pattern_type: [sandbox_isolation|async_patterns|data_validation|error_handling|self_reflection|agentic_development]
tags: [标签1, 标签2]
last_updated: 2024-01-15
author: 提供者姓名
source: [opencode|helloagent|custom]
---

## 质量标准

知识库文件应遵循以下质量标准：

- [ ] 清晰的代码示例
- [ ] 详细的解释和注释
- [ ] 明确的使用场景
- [ ] 优势和劣势分析
- [ ] 实际可用的代码片段
- [ ] 正确的语法高亮（使用 markdown 代码块）
- [ ] 相关的参考链接（如适用）

## 联系与支持

- **问题反馈**：如果发现知识库中的错误或不足，请提交 Issue
- **功能请求**：如果需要特定的模式或最佳实践，可以提出请求
- **讨论与协作**：使用 OpenSpec 或其他协作工具进行讨论

## 知识库内容概览

### OpenCode 模式

1. **沙箱隔离**（sandbox-isolation.md）
   - 进程隔离实现
   - 文件系统限制
   - 环境变量隔离
   - 资源限制
   - 完整沙箱管理器
   - 安全注意事项

### HelloAgent 模式

1. **递归思维**（recursive-thinking.md）
   - 递归问题分解
   - 最大深度限制
   - 子问题识别
   - 结果缓存

2. **自我反思**（self-reflection.md）
   - 反思记录格式
   - 失败模式分析
   - 成功率跟踪
   - 策略调整建议

3. **代码库维护助手**（codebase-maintainer.md）
   - Agentic 工具使用
   - TerminalTool 实现
   - NoteTool 实现
   - MemoryTool 实现
   - ContextBuilder 实现
   - FunctionCallAgent 集成

### Python 最佳实践

1. **数据验证**（data-validation.md）
   - Pydantic v2 类型验证
   - 字段验证器
   - 嵌套模型
   - JSON 数据解析
   - 与 FastAPI 集成

## 使用场景示例

### 示例 1：使用递归思维进行复杂任务分解

```python
from helloagent_patterns.recursive_thinking import RecursiveThinker

thinker = RecursiveThinker(max_depth=3)

def solve_subproblem(problem: str, context: list) -> str:
    """解决子问题的函数"""
    if "API" in problem:
        return "使用正确的 API 端点"
    return "已解决"

result = thinker.think("实现用户认证，需要处理权限、会话和密码存储", solve_subproblem)
if result.success:
    print(f"最终答案: {result.final_answer}")
else:
    print(f"需要调整策略: {result.errors}")
```

### 示例 2：使用代码库维护助手探索代码库

```python
from helloagent_patterns.codebase_maintainer import CodebaseMaintainer

maintainer = CodebaseMaintainer(
    project_name="mini-coder",
    codebase_path="./src",
    llm=HelloAgentsLLM()
)

# 探索代码库
response = maintainer.explore(target=".")
print(f"探索结果:\n{response}")

# 查找 TODO 项
response = maintainer.analyze(focus="TODO 项")
print(f"\n分析结果:\n{response}")
```

## 相关资源

- [HelloAgent 项目](https://github.com/datawhalechina/hello-agents)
- [OpenSpec 工作流文档](../openspec/README.md)
- [子代理系统使用指南](../subagent-system-guide.md)
- [子代理定义文档](../subagent.md)
- [CLAUDE.md](../CLAUDE.md) - 项目开发指南
