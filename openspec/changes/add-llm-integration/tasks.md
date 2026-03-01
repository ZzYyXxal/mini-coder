# LLM Integration Tasks

LLM 集成功能开发任务清单。

---

## 阶段 1：LLM 服务基础架构

- [ ] 创建 `src/mini_coder/llm/` 目录
- [ ] 实现 `LLMProvider` 抽象基类 (`src/mini_coder/llm/providers/base.py`)
- [ ] 实现 `LLMService` 服务类 (`src/mini_coder/llm/service.py`)

## 阶段 2：服务提供商实现

- [ ] 实现 Claude/Anthropic API 提供商 (`src/mini_coder/llm/providers/anthropic.py`)
- [ ] 实现 ZHIPU AI API 提供商 (`src/mini_coder/llm/providers/zhipu.py`)
- [ ] 实现 OpenAI 兼容接口 (`src/mini_coder/llm/providers/openai.py`)
- [ ] 实现自定义/通用 API (`src/mini_coder/llm/providers/custom.py`)

## 阶段 3：TUI 对话界面实现

- [ ] 创建对话输入组件 (`src/mini_coder/tui/llm_chat.py`)
- [ ] 集成到 TUI 入口 (`src/mini_coder/tui/__main__.py`)
- [ ] 添加配置文件 (`config/llm.yaml`)

## 阶段 4：TUI 入口集成

- [ ] 修改 `src/mini_coder/tui/__main__.py` 添加 LLM 启动选项
- [ ] 修改 `src/mini_coder/tui/models/config.py` 添加 LLM 配置支持

## 阶段 5：配置文件创建

- [ ] 创建配置文件 `config/llm.yaml`
- [ ] 添加默认提供商和 API 密钥配置

## 阶段 6：文档更新

- [ ] 更新 `docs/knowledge-base/` 添加 LLM 集成文档

---

## 验收标准

### 功能验收

- [ ] 支持多提供商切换
- [ ] 流式输出正常工作
- [ ] 配置文件可以动态加载和保存

### 非功能验收

- [ ] 代码遵循项目架构
- [ ] 配置格式符合 YAML 规范
