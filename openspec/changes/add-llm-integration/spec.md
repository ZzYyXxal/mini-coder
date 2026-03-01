# LLM Integration Spec

## 功能描述

为 mini-coder TUI 添加大语言模型（LLM）集成功能，实现与大模型进行实时对话的能力，支持流式输出以提升用户体验。

---

## 需求分析

### 核心需求

1. **LLM 服务接入**
   - 支持多个大模型服务提供商（Claude/Anthropic、ZHIPU AI、通义API）
   - 提供统一的异步服务接口
   - 支持 API 密钥管理
   - 支持模型选择和参数配置

2. **TUI 对话界面**
   - 在 TUI 中添加对话输入组件
   - 实现流式输出（stream），支持逐字显示大模型响应
   - 保持对话历史记录
   - 支持多轮对话上下文传递

3. **配置管理**
   - 支持动态加载和保存 LLM 配置
   - 支持热切换不同服务提供商

---

## 技术规范

### 需求 1：LLM 服务接口

#### Requirement: 统一的异步 LLM 服务接口

**场景 1：用户发送消息并获取流式响应**

**WHEN** 开发者调用 `llm.send_message_stream()` 方法
**THEN** 系统调用 LLM 服务提供商的 API
**AND** LLM 服务提供商以流式（stream）返回响应
**AND** TUI 逐个字符显示流式响应到用户界面

**验收标准**：
- [ ] `llm.send_message_stream()` 方法存在并可调用
- [ ] 支持 Chat 接口格式
- [ ] 流式输出正常工作，字符逐个显示不阻塞
- [ ] 支持 JSON 格式的流式响应解析

#### Scenario: 消息发送

**输入**：
```python
message = "帮我写一个快速排序算法"
```

**输出**：
```python
response_stream = llm.send_message_stream(message)
async for chunk in response_stream:
    display_chunk(chunk)  # 逐个显示字符
```

---

### 需求 2：多提供商支持

#### Requirement: 可插拔的 LLM 服务提供商架构

**场景 2：支持多个大模型服务提供商**

**WHEN** 开发者添加新的服务提供商到 `src/mini_coder/llm/providers/` 目录
**THEN** LLM 服务可以在配置中选择使用哪个提供商
**AND** 每个服务提供商实现统一的接口规范

**验收标准**：
- [ ] 每个服务提供商类继承自 `LLMProvider` 基类
- [ ] 每个提供商实现 `send_message()` 同步方法
- [ ] 每个提供商实现 `send_message_stream()` 流式方法
- [ ] 服务提供商可以在配置中注册和选择

#### Scenario: 提供商选择

**输入**：
```python
# config/llm.yaml
provider: "anthropic"  # 或 "zhipu", "openai", "custom"
```

**输出**：
- TUI 显示可用的提供商列表
- 用户选择提供商后，调用对应服务

---

### 需求 3：流式输出实现

#### Requirement: 流式响应解析和显示

**场景 3：LLM 流式响应逐字显示**

**WHEN** LLM 服务返回流式数据（Server-Sent Events 格式）
**THEN** TUI 逐个解析并显示响应字符

**验收标准**：
- [ ] 支持 SSE (Server-Sent Events) 格式解析
- [ ] 正确处理流式响应的开始和结束标记
- [ ] 流式输出显示不阻塞主线程

#### Scenario: 流式输出

**输入**：
```python
# LLM 服务返回
"data: {\"choices\": [{\"message\": \"你好\", \"delta\": {\"content\": \"你好\"}}]}"

**输出处理**：
```python
for chunk in stream:
    for delta in event:
        if delta_type == "content_block_delta":
            print(delta.content)  # 逐个显示
        elif delta_type == "content_block":
            print(delta.content)
```

---

### 需求 4：配置文件管理

#### Requirement: LLM 配置文件支持

**场景 4：动态加载和保存 LLM 配置**

**WHEN** 用户在 TUI 中修改 LLM 配置或添加 API 密钥
**THEN** 配置文件更新并持久化到磁盘

**验收标准**：
- [ ] 配置文件位于 `config/llm.yaml`
- [ ] 配置可以在运行时动态加载
- [ ] 配置修改可以保存到文件
- [ ] API 密钥可以安全存储（建议使用环境变量）

#### Scenario: 配置加载

**输入**：
```python
# 保存配置
llm_config.update_provider("anthropic", api_key="xxx")
```

---

### 需求 5：TUI 入口集成

#### Requirement: TUI 启动入口支持 LLM 聊天

**场景 5：在 TUI 启动时支持 LLM 聊天模式**

**WHEN** 用户启动 TUI 时指定 `--llm-chat` 参数
**THEN** TUI 显示 LLM 聊天界面而不是默认的 REPL 界面

**验收标准**：
- [ ] `--llm-chat` 参数被正确解析
- [ ] LLM 聊天界面正常显示
- [ ] 可以通过配置切换回 REPL 模式

#### Scenario: LLM 聊天模式

**输入**：
```bash
python -m mini_coder.tui --llm-chat
```

**输出**：
```python
# 启动 LLM 聊天界面
start_llm_chat_interface()
```

---

## 架构设计

### 模块结构

```
src/mini_coder/
├── llm/
│   ├── service.py          # LLM 服务抽象
│   ├── config.py          # LLM 配置管理
│   └── providers/         # 服务提供商实现
│       ├── __init__.py
│       ├── base.py         # 基类
│       ├── anthropic.py    # Claude/Anthropic API
│       ├── zhipu.py        # ZHIPU AI API
│       ├── openai.py       # OpenAI API
│       └── custom.py       # 自定义/通用 API
├── tui/
│   ├── llm_chat.py     # LLM 聊天界面
│   └── models/
│       └── config.py     # 扩展配置模型
config/
└── llm.yaml              # LLM 配置文件
```

### 设计模式

#### 1. 服务接口抽象

**Base Class**: `LLMProvider`
- 提供统一的接口规范
- 每个方法：`send_message()`, `send_message_stream()`

#### 2. 流式处理

**AsyncIterator**: 返回异步生成器，逐个产生响应内容

```python
async def send_message_stream(self, messages, **kwargs):
    async for chunk in await self.send_message(messages, **kwargs):
        yield chunk
```

---

## 边界条件

### 1. API 密钥安全
- [ ] 密钥通过环境变量传递，不硬编码
- [ ] 配置文件中的密钥可以加密存储

### 2. 成本控制
- [ ] 设置调用频率限制
- [ ] 成本预估和预警功能

---

## 实施任务

### 阶段 1：实现 LLM 服务基础架构

#### 1.1 创建服务抽象基类
- 文件：`src/mini_coder/llm/providers/base.py`
- 定义 `LLMProvider` 抽象基类
- 实现 `send_message()` 方法

#### 1.2 实现 Claude/Anthropic 提供商
- 文件：`src/mini_coder/llm/providers/anthropic.py`
- 使用 Anthropic Messages API v1
- 实现 `send_message()` 方法

#### 1.3 实现流式接口
- 修改基类添加 `send_message_stream()` 方法
- 定义流式响应协议

### 阶段 2：创建 Anthropic 服务实现

#### 2.1 创建 Anthropic 服务类
- 文件：`src/mini_coder/llm/providers/anthropic.py`
- 内容：
  - 继承 `LLMProvider` 基类
  - 实现 Claude API 集成
  - 支持同步和流式方法

#### 2.2 实现流式输出
- 使用 Anthropic 的流式 API
- 正确处理 Server-Sent Events 格式

### 阶段 3：创建配置文件

#### 3.1 创建配置文件
- 文件：`config/llm.yaml`
- 内容：
  - 定义默认服务提供商
  - 定义 API 密钥字段

### 阶段 4：创建 TUI 对话界面

#### 4.1 创建对话界面
- 文件：`src/mini_coder/tui/llm_chat.py`
- 内容：
  - 使用 Rich Console 实现
  - 支持流式输出显示
  - 支持多轮对话

#### 4.2 集成到 TUI 入口
- 修改 `src/mini_coder/tui/__main__.py`
- 添加 LLM 聊天启动选项

### 阶段 5：测试和文档

#### 5.1 添加测试
- 创建 LLM 服务单元测试
- 更新文档

#### 5.2 更新配置文件
- 将配置添加到项目配置
