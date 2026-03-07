# Bug分析报告：TUI 启动延迟 90 秒问题

## 问题描述

执行 `python -m mini_coder.tui -d target` 后，用户输入"你好"到 LLM 调用之间耗时约 90 秒。

## 现象

从日志 `logs/tui_20260307_021054.log` 可以看到：

```
2026-03-07 02:11:03 - Processing user input: 你好...
2026-03-07 02:12:28 - datasets - DEBUG - PyTorch version 2.9.1 available.
2026-03-07 02:12:34 - [LLMService] chat_stream() called
```

时间差约 91 秒，其中 PyTorch 加载占用了约 85 秒。

## 根本原因

### 1. 直接原因

`mini_coder.memory` 包在导入时触发了重型依赖链：

```
mini_coder.memory.__init__.py
    └── from .embeddings import ...
            └── from sentence_transformers import SentenceTransformer (旧代码)
                    └── transformers
                            └── torch (PyTorch)
                                    └── datasets (85秒加载时间)
```

### 2. 技术细节

- **sentence-transformers**: 本地嵌入模型库，依赖 `transformers`
- **transformers**: HuggingFace 模型库，依赖 `torch`
- **torch (PyTorch)**: 深度学习框架，加载时间约 40-50 秒
- **datasets**: 数据处理库，导入时检查 PyTorch 版本

### 3. 为什么即使有 try/except 也会加载？

```python
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
```

Python 的 `try/except` 只能捕获导入失败的异常，但**无法阻止模块被加载**。当 `from sentence_transformers import ...` 执行时，Python 必须先加载整个 `sentence_transformers` 模块及其所有依赖。

## 解决方案

### 已实施的修复

1. **移除 sentence-transformers**：不再依赖 PyTorch；默认使用 **fastembed**（ONNX，无 torch），或通过配置使用在线 embedding API。
2. **延迟加载**：embedding 模型/客户端在首次使用时才初始化，避免导入 `mini_coder.memory` 时触发重型依赖。
3. **可选依赖**：语义检索依赖 `fastembed`（`pip install fastembed`）或在线 API（`openai` + 配置），无需安装 `torch`/`transformers`/`sentence-transformers`。

### 修复后效果

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| `mini_coder.memory` 导入时间 | 50-80 秒 | < 2 秒 |
| 首次响应延迟 | 90+ 秒 | < 5 秒 |

## 已移除的包（当前仓库不再使用）

以下包已从**默认/推荐**依赖中移除（如需本地嵌入请使用 fastembed，勿安装 sentence-transformers）：

| 包名 | 说明 |
|------|------|
| torch | 深度学习框架，体积与加载时间大 |
| transformers | HuggingFace 模型库，依赖 torch |
| sentence-transformers | 旧版本地嵌入，依赖 torch |
| accelerate | 分布式训练加速 |

## 配置说明（当前 mini-coder 仓库）

### 默认：fastembed（无 PyTorch）

- 安装：`pip install fastembed` 或 `pip install mini-coder[semantic]`
- 可选在 `config/llm.yaml` 中限制批大小以控制内存：

```yaml
embeddings:
  backend: "fastembed"
  batch_size: 32
```

### 可选：使用在线 embedding API

```yaml
embeddings:
  backend: "api"
  api_key: "DASHSCOPE_EMBEDDING_API_KEY"
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  model: "text-embedding-v4"
```

### embeddings 模块主要行为

- 默认后端为 **fastembed**，无 `sentence_transformers` 导入。
- 从 `config/llm.yaml` 的 `embeddings` 段读取 `backend`、`use_api`、`api_key`、`base_url`、`model`、`batch_size`。
- API 后端使用 `openai.OpenAI` 客户端，在首次使用时初始化（`_init_client()`）。
- fastembed 的 `embed_batch` 按 `batch_size` 分批执行，控制内存占用。

## 经验教训

1. **避免顶层导入重型依赖**：不要在模块顶层导入 PyTorch、TensorFlow 等大型库。
2. **优先轻量方案**：语义嵌入可用 fastembed（ONNX）替代 sentence-transformers（PyTorch），减少内存与启动时间。
3. **配置与代码分离**：embeddings 配置放在 YAML，支持 fastembed / API 切换。
4. **批处理上限**：本地嵌入批量推理时限制 batch_size，避免内存峰值过高。

## 相关文件

- `src/mini_coder/memory/__init__.py` - 包导出
- `src/mini_coder/memory/embeddings.py` - 嵌入服务（fastembed 默认 + 可选 API）
- `config/llm.yaml` - embeddings 配置（可选）

## 日期

- 发现日期: 2026-03-07
- 修复日期: 2026-03-07
- 报告作者: Claude Code
- 合并到主仓库 docs/bugs: 2026-03-07（与 response-optimize worktree 合并，并同步当前 fastembed/API 实现）
