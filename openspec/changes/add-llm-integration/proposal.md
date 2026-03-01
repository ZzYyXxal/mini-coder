# LLM Integration Proposal

## 变更概述

为 mini-coder 项目添加大语言模型（LLM）集成功能，实现在 TUI 与大模型进行对话的能力，并支持流式输出。

## 背景与需求

### 当前问题
- mini-coder 当前只有本地 TUI 界面，无法与外部大模型服务进行交互
- 用户希望在 TUI 中可以和大模型进行实时对话
- 需要支持流式输出（逐字显示响应），提升用户体验

### 目标
1. 接入大模型服务，支持多个提供商（Claude/Anthropic、ZHIPU AI、通义大模型API）
2. 在 TUI 中添加对话界面组件
3. 实现流式输出（stream），支持实时逐字显示大模型响应
4. 添加配置文件管理，支持动态切换不同模型和API配置

---

## 技术方案

### 方案选择

| 方案 | 描述 | 优势 | 劣势 | 推荐指数 |
|------|------|---------|---------|---------|
| **方案 1：Claude/Anthropic** | 使用官方 Anthropic API | 稳定可靠，功能全面 | 成本较高 | ⭐⭐⭐⭐ |
| **方案 2：ZHIPU AI** | 国产智谱服务，兼容OpenAI格式 | 响应快，中文友好 | ⭐⭐⭐ | 配额限制 |
| **方案 3：通义大模型API** | 灵活性高，支持多个平台 | 需要自行管理 | ⭐⭐ |

**推荐**：方案 1（Claude/Anthropic）作为主要接入方式，支持 ZHIPU 和通义 API 作为备选

---

## 实施范围

### 新增组件

1. **LLM 服务模块**（新增）
   - `src/mini_coder/llm/` - LLM 服务客户端
     - `service.py` - 服务接口抽象
     - `config.py` - 配置管理
     - `providers/` - 各大模型服务提供商实现
       - `anthropic.py` - Claude/Anthropic API
       - `zhipu.py` - ZHIPU AI API
       - `openai.py` - OpenAI 兼容接口
       - `custom.py` - 自定义/通用 API 支持

2. **TUI 对话组件**（新增/修改）
   - `src/mini_coder/tui/llm_chat.py` - LLM 聊天对话界面
     - 使用 Rich Console 实现类似 ChatGPT 的对话体验
     - 支持流式输出（逐字显示）
     - 支持消息历史记录
     - 支持多轮对话上下文

3. **配置文件**（新增）
   - `config/llm.yaml` - LLM 服务配置
     - 包含 API 密钥、模型选择、服务提供商配置

### 修改组件

1. **TUI 入口模块**
   - 修改 `src/mini_coder/tui/__main__.py` 添加 LLM 聊天选项
   - 修改 `src/mini_coder/tui/models/config.py` 添加 LLM 配置支持

---

## 验收标准

### 功能验收

- [ ] 可以在 TUI 中选择不同的 LLM 服务提供商
- [ ] 可以在配置文件中设置 API 密钥
- [ ] 流式输出正常工作，字符逐个显示
- [ ] 支持多轮对话，保持上下文
- [ ] LLM 配置可以动态加载和保存

### 非功能验收

- [ ] TUI 界面风格与现有设计保持一致
- [ ] 配置文件格式符合 YAML 规范
- [ ] 代码遵循项目现有架构和设计模式

---

## 实施计划

### 阶段 1：创建 LLM 服务模块

#### 1.1 实现服务接口抽象
- 文件：`src/mini_coder/llm/service.py`
- 内容：
  - 定义 `LLMService` 抽象基类
  - 实现 `send_message()` 同步方法
  - 实现 `send_message_stream()` 异步流式方法

#### 1.2 实现各服务提供商
- 文件：`src/mini_coder/llm/providers/anthropic.py`
- 内容：
  - 使用 Anthropic API v1.0+
  - 实现 Claude API 调用
  - 支持流式输出

- 文件：`src/mini_coder/llm/providers/zhipu.py`
- 内容：
  - 使用 ZHIPU AI API
  - 兼容 OpenAI 格式
  - 支持流式输出

- 文件：`src/mini_coder/llm/providers/openai.py`
- 内容：
  - 使用 OpenAI API（兼容格式）
  - 支持流式输出

- 文件：`src/mini_coder/llm/providers/custom.py`
- 内容：
  - 支持自定义/通用 API
  - 提供灵活的扩展接口

#### 1.3 创建配置文件
- 文件：`config/llm.yaml`
- 内容：
  - 定义默认服务提供商
  - 定义 API 密钥配置
  - 定义模型参数配置

### 阶段 2：实现 TUI 对话组件

#### 2.1 创建对话界面
- 文件：`src/mini_coder/tui/llm_chat.py`
- 功能：
  - 对话消息输入区域
  - 对话历史显示区域
  - LLM 流式响应显示区域
  - 使用 Rich Console 进行美化

#### 2.2 集成到 TUI 入口
- 修改 `src/mini_coder/tui/__main__.py` 添加 LLM 聊天选项
- 修改 `src/mini_coder/tui/models/config.py` 添加 LLM 配置字段

### 阶段 3：更新配置和文档

#### 3.1 更新配置文件
- 将 `config/llm.yaml` 添加到项目配置

#### 3.2 更新文档
- 更新 `docs/knowledge-base/` 添加 LLM 集成文档

---

## 风险评估

| 风险 | 影响 | 缓解措施 |
|--------|------|---------|
| API 密钥安全 | 避免将密钥硬编码到源码中 | 使用环境变量或配置文件 |
| 成本控制 | 大模型 API 调用可能产生额外费用 | 设置调用频率限制、成本预警 |
| 流式实现复杂度 | 流式输出需要管理缓冲区和中断逻辑 | 先实现简单版本 |

---

## 参考资源

- Anthropic API 文档：https://docs.anthropic.com/
- OpenAI API 文档：https://platform.openai.com/docs/
- ZHIPU AI 文档：https://open.bigmodel.cn/
- Rich Console 文档：https://rich.readthedocs.io/
