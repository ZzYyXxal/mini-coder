# ProjectNotes 增强方案

本文档记录 mini-coder 项目笔记系统（NoteTool-like）的三个增强方向分析和实施方案。

## 背景

mini-coder 已实现 ProjectNotes 系统，提供 NoteTool 类似的功能：
- 5 种笔记类别：decision, todo, pattern, info, block
- 4 种状态：ACTIVE, COMPLETED, ARCHIVED, RESOLVED
- CRUD 操作、搜索、持久化
- 通过 ContextBuilder 集成到 GSSC pipeline

## 当前架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    ProjectNotes 系统架构                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐                    │
│  │  ProjectNote    │    │ NoteCategory    │                    │
│  │  - id           │    │ - DECISION      │ ← 架构决策         │
│  │  - category     │    │ - TODO          │ ← 待办任务         │
│  │  - title        │    │ - PATTERN       │ ← 代码模式         │
│  │  - content      │    │ - INFO          │ ← 重要信息         │
│  │  - status       │    │ - BLOCK         │ ← 阻塞问题         │
│  │  - tags         │    └─────────────────┘                    │
│  │  - timestamps   │                                            │
│  └─────────────────┘    ┌─────────────────┐                    │
│                         │ NoteStatus       │                    │
│  ┌─────────────────┐    │ - ACTIVE        │ ← 活跃             │
│  │ ProjectNotes    │    │ - COMPLETED     │ ← 已完成           │
│  │ Manager         │    │ - ARCHIVED      │ ← 已归档           │
│  │ - CRUD          │    │ - RESOLVED      │ ← 已解决           │
│  │ - Search        │    └─────────────────┘                    │
│  │ - Persistence   │                                            │
│  │ - Context Fmt   │                                            │
│  └─────────────────┘                                            │
│           │                                                     │
│           ▼                                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  ContextBuilder (GSSC)                   │   │
│  │  Gather → Select → Structure → Compress                  │   │
│  │                                                          │   │
│  │  Notes 优先级: CRITICAL (永不压缩)                        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 与 Hello-Agents NoteTool 对比

| 特性 | Hello-Agents NoteTool | mini-coder ProjectNotes | 状态 |
|------|----------------------|------------------------|------|
| 结构化笔记类型 | ✅ memory/notetool | ✅ 5种category | ✅ 已实现 |
| 持久化存储 | ✅ | ✅ JSON per-project | ✅ 已实现 |
| CRUD 操作 | ✅ | ✅ 完整CRUD | ✅ 已实现 |
| 搜索功能 | ✅ | ✅ 内容/标签搜索 | ✅ 已实现 |
| 上下文集成 | ✅ 自动注入 | ✅ GSSC pipeline | ✅ 已实现 |
| 待办管理 | ✅ | ✅ TODO category | ✅ 已实现 |
| 状态管理 | ✅ | ✅ 4种状态 | ✅ 已实现 |
| 语义搜索 | ❓ 可能支持 | ⚠️ Phase 2 计划 | 📋 可选 |
| 自动提取 | ✅ Agent自动 | ❌ 需手动创建 | 📋 可扩展 |
| 笔记关联 | ❓ | ❌ 无 | 📋 可扩展 |

---

## 增强方向一：自动笔记提取

### 1.1 问题分析

```
┌─────────────────────────────────────────────────────────────────┐
│                    当前问题：手动创建笔记                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  用户 ──▶ LLM ──▶ 响应 ──▶ [手动] ──▶ 创建笔记                   │
│                                                                 │
│  问题：                                                         │
│  • 用户需要主动记录决策                                          │
│  • 容易遗漏重要信息                                              │
│  • 增加 cognitive load                                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    目标：自动提取关键信息                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  用户 ──▶ LLM ──▶ 响应 ──▶ [自动分析] ──▶ 自动创建笔记           │
│                              │                                  │
│                              ▼                                  │
│                    ┌─────────────────┐                          │
│                    │ 检测模式:       │                          │
│                    │ • "我们决定..." │                          │
│                    │ • "方案是..."   │                          │
│                    │ • "阻塞..."     │                          │
│                    │ • "待办..."     │                          │
│                    └─────────────────┘                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 技术方案

#### 方案 A：规则匹配（轻量级）

```python
# 文件: src/mini_coder/memory/note_extractor.py

EXTRACTION_PATTERNS = {
    "decision": [
        r"(我们)?决定[采用使用](.+?)[作为用于]",
        r"选择(.+?)方案",
        r"最终方案[是为](.+)",
        r"architecture decision:(.+)",
    ],
    "todo": [
        r"需要[完成实现做](.+)",
        r"待办[事项]?:(.+)",
        r"TODO:(.+)",
        r"下一步[是要](.+)",
    ],
    "block": [
        r"[遇到有]阻塞[问题]?:(.+)",
        r"无法继续(.+)",
        r"卡在(.+)",
        r"blocked by:(.+)",
    ],
    "pattern": [
        r"[使用采用]模式:(.+)",
        r"代码规范:(.+)",
        r"命名规则:(.+)",
    ],
}

class NoteExtractor:
    """从 LLM 响应中自动提取笔记。"""

    def extract(self, content: str) -> list[ExtractedNote]:
        """提取潜在笔记。"""
        notes = []
        for category, patterns in EXTRACTION_PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    notes.append(ExtractedNote(
                        category=category,
                        content=match,
                        confidence=0.7,  # 规则匹配置信度
                        source="rule"
                    ))
        return notes
```

#### 方案 B：LLM 辅助提取（智能）

```python
EXTRACTION_PROMPT = """分析以下对话内容，提取关键项目信息。

对话内容:
{content}

请提取以下类型的信息（JSON 格式）:
{{
  "decisions": ["决策1", "决策2"],
  "todos": ["待办1", "待办2"],
  "blocks": ["阻塞问题"],
  "patterns": ["发现的模式/规范"]
}}

只提取明确提到的信息，不要推断。
如果没有某类信息，返回空数组。
"""

class LLMNoteExtractor:
    """使用 LLM 智能提取笔记。"""

    def __init__(self, llm_service: LLMService):
        self.llm = llm_service

    async def extract(self, content: str) -> list[ExtractedNote]:
        """使用 LLM 提取笔记。"""
        prompt = EXTRACTION_PROMPT.format(content=content[:2000])
        response = await self.llm.async_chat(prompt)
        return self._parse_response(response)
```

### 1.3 集成方案

```python
# 修改: src/mini_coder/llm/service.py

class LLMService:
    def __init__(self, ..., auto_extract_notes: bool = False):
        self._auto_extract = auto_extract_notes
        self._note_extractor = NoteExtractor() if auto_extract_notes else None

    async def async_chat_stream(self, message: str, **kwargs):
        # ... 现有逻辑 ...

        # 5. Complete - 添加完整响应到上下文
        if self._context_manager and full_response:
            self._context_manager.add_message("assistant", full_response)

            # 6. Auto-extract - 自动提取笔记
            if self._auto_extract and self._notes_manager:
                await self._extract_and_save_notes(full_response)

    async def _extract_and_save_notes(self, response: str):
        """从响应中提取并保存笔记。"""
        extracted = await self._note_extractor.extract(response)

        for note in extracted:
            if note.confidence > 0.8:  # 高置信度自动保存
                self._notes_manager.add_note(
                    category=note.category,
                    title=note.title,
                    content=note.content,
                    tags=["auto-extracted"]
                )
            else:  # 低置信度标记待确认
                self._notes_manager.add_note(
                    category=note.category,
                    title=f"[待确认] {note.title}",
                    content=note.content,
                    tags=["auto-extracted", "needs-confirmation"]
                )
```

### 1.4 实施步骤

| 步骤 | 任务 | 文件 | 复杂度 |
|------|------|------|--------|
| 1 | 创建 `NoteExtractor` 基础类 | `memory/note_extractor.py` | 低 |
| 2 | 实现规则匹配模式 | `memory/note_extractor.py` | 低 |
| 3 | 添加 `ExtractedNote` 模型 | `memory/note_extractor.py` | 低 |
| 4 | 集成到 `LLMService` | `llm/service.py` | 中 |
| 5 | 添加配置选项 | `config/memory.yaml` | 低 |
| 6 | 编写单元测试 | `tests/memory/test_extractor.py` | 中 |
| 7 | (可选) 实现 LLM 辅助提取 | `memory/note_extractor.py` | 高 |

---

## 增强方向二：语义搜索

### 2.1 问题分析

```
┌─────────────────────────────────────────────────────────────────┐
│                    当前问题：关键词搜索                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  搜索 "数据库" ──▶ 匹配 "使用 PostgreSQL 数据库"                  │
│                                                                 │
│  无法匹配：                                                      │
│  • "存储层使用关系型数据库" (没有"数据库"关键词)                   │
│  • "数据持久化方案" (语义相似但词不同)                            │
│  • "DB 选择" (缩写)                                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    目标：语义相似度搜索                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  搜索 "数据库" ──▶ Embedding ──▶ 向量相似度匹配                  │
│       │                              │                          │
│       ▼                              ▼                          │
│  [0.1, 0.3, ...]              匹配所有语义相似的笔记              │
│                                     │                           │
│                                     ▼                           │
│                    • "存储层使用关系型数据库"                     │
│                    • "数据持久化方案"                             │
│                    • "PostgreSQL 配置"                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 技术方案

#### 本地 Embedding（推荐：fastembed，无 PyTorch）

```python
# 文件: src/mini_coder/memory/embeddings.py（当前实现摘要）

from fastembed import TextEmbedding
import numpy as np

class LocalEmbeddingService:
    """本地/在线嵌入服务：默认 fastembed，可选配置 embedding API。"""

    def __init__(self, config=None):
        # 默认 backend="fastembed"，模型如 BAAI/bge-small-en-v1.5（384 维）
        # 配置 backend="api" 时使用 OpenAI 兼容 API
        self.config = config or EmbeddingConfig()
        self._model = None  # 懒加载

    def embed(self, text: str) -> np.ndarray:
        """生成单条文本 embedding。"""
        # fastembed: list(self._model.embed([text]))[0]
        # API: self._client.embeddings.create(...)
        ...

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        """批量生成 embeddings；fastembed 下按 batch_size 分批以控制内存。"""
        ...

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """计算余弦相似度。"""
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
```

### 2.3 数据模型扩展

```python
# 修改: src/mini_coder/memory/project_notes.py

class ProjectNote(BaseModel):
    # ... 现有字段 ...

    # 新增：向量搜索支持
    embedding: Optional[list[float]] = Field(
        default=None,
        description="Note content embedding for semantic search"
    )
    embedding_model: Optional[str] = Field(
        default=None,
        description="Model used to generate embedding"
    )

    def needs_embedding(self, model_name: str) -> bool:
        """Check if note needs (re)embedding."""
        return self.embedding is None or self.embedding_model != model_name
```

### 2.4 搜索服务

```python
# 文件: src/mini_coder/memory/semantic_search.py

class SemanticNoteSearch:
    """语义笔记搜索服务。"""

    def __init__(
        self,
        notes_manager: ProjectNotesManager,
        embedding_service: LocalEmbeddingService
    ):
        self.notes = notes_manager
        self.embeddings = embedding_service
        self._index_cache: dict[str, np.ndarray] = {}

    def build_index(self, project_key: str) -> None:
        """为项目的笔记构建搜索索引。"""
        notes = self.notes.get_notes(active_only=False)

        texts = [f"{n.title} {n.content}" for n in notes]
        embeddings = self.embeddings.embed_batch(texts)

        self._index_cache[project_key] = {
            "note_ids": [n.id for n in notes],
            "embeddings": embeddings
        }

    def search(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.7
    ) -> list[tuple[ProjectNote, float]]:
        """语义搜索笔记。

        Returns:
            List of (note, similarity_score) tuples.
        """
        query_embedding = self.embeddings.embed(query)

        results = []
        for note_id, note_emb in zip(
            self._index_cache["note_ids"],
            self._index_cache["embeddings"]
        ):
            similarity = LocalEmbeddingService.cosine_similarity(
                query_embedding, note_emb
            )
            if similarity >= threshold:
                note = self.notes.get_note(note_id)
                if note:
                    results.append((note, similarity))

        # 按相似度排序
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
```

### 2.5 实施步骤

| 步骤 | 任务 | 文件 | 复杂度 |
|------|------|------|--------|
| 1 | 添加 `fastembed` 可选依赖（或配置 embedding API） | `pyproject.toml` / `config/llm.yaml` | 低 |
| 2 | 创建 `LocalEmbeddingService` | `memory/embeddings.py` | 中 |
| 3 | 扩展 `ProjectNote` 模型 | `memory/project_notes.py` | 低 |
| 4 | 创建 `SemanticNoteSearch` | `memory/semantic_search.py` | 高 |
| 5 | 集成到 `ProjectNotesManager` | `memory/project_notes.py` | 中 |
| 6 | 添加配置选项 | `config/memory.yaml` | 低 |
| 7 | 实现索引持久化 | `memory/semantic_search.py` | 中 |
| 8 | 编写单元测试 | `tests/memory/test_semantic_search.py` | 中 |

---

## 增强方向三：笔记关联

### 3.1 问题分析

```
┌─────────────────────────────────────────────────────────────────┐
│                    当前问题：笔记孤立                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Note A: "使用 FastAPI"          Note B: "Repository Pattern"    │
│       └── 孤立，无关联                  └── 孤立，无关联          │
│                                                                 │
│  Note C: "需要添加 API 测试"      Note D: "使用 pytest"          │
│       └── 与 A 相关但未链接             └── 与 C 相关但未链接     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    目标：建立笔记关联网络                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Note A: "使用 FastAPI"                                          │
│       │                                                         │
│       ├── related_to ──▶ Note C: "需要添加 API 测试"             │
│       │                              │                          │
│       │                              └── related_to ──▶ Note D  │
│       │                                                         │
│       └── implements ──▶ Note B: "Repository Pattern"           │
│                                                                 │
│  形成知识图谱：                                                   │
│  Decision ──▶ Todo ──▶ Pattern                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 数据模型扩展

```python
# 文件: src/mini_coder/memory/note_relations.py

from enum import Enum
from pydantic import BaseModel
from datetime import datetime
from uuid import uuid4

class RelationType(str, Enum):
    """笔记关系类型。"""
    RELATED_TO = "related_to"        # 一般关联
    DEPENDS_ON = "depends_on"        # 依赖关系
    BLOCKS = "blocks"                # 阻塞关系
    IMPLEMENTS = "implements"        # 实现关系
    SUPERSEDES = "supersedes"        # 取代关系
    DERIVED_FROM = "derived_from"    # 派生关系


class NoteRelation(BaseModel):
    """笔记之间的关联关系。"""

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    source_id: str                   # 源笔记 ID
    target_id: str                   # 目标笔记 ID
    relation_type: RelationType      # 关系类型
    created_at: datetime = Field(default_factory=datetime.now)
    metadata: dict = Field(default_factory=dict)
```

```python
# 修改: src/mini_coder/memory/project_notes.py

class ProjectNote(BaseModel):
    # ... 现有字段 ...

    # 新增：关联支持
    relations: list[str] = Field(
        default_factory=list,
        description="IDs of related notes"
    )
    relation_types: dict[str, str] = Field(
        default_factory=dict,
        description="Map of note_id -> relation_type"
    )

    def add_relation(
        self,
        note_id: str,
        relation_type: RelationType = RelationType.RELATED_TO
    ) -> None:
        """添加关联笔记。"""
        if note_id not in self.relations:
            self.relations.append(note_id)
            self.relation_types[note_id] = relation_type.value
            self.touch()

    def remove_relation(self, note_id: str) -> None:
        """移除关联。"""
        if note_id in self.relations:
            self.relations.remove(note_id)
            self.relation_types.pop(note_id, None)
            self.touch()
```

### 3.3 关联管理器

```python
# 文件: src/mini_coder/memory/note_relations.py

class NoteRelationManager:
    """笔记关联管理器。"""

    def __init__(self, notes_manager: ProjectNotesManager):
        self.notes = notes_manager
        self._relations: dict[str, list[NoteRelation]] = {}

    def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: RelationType = RelationType.RELATED_TO,
        bidirectional: bool = False
    ) -> Optional[NoteRelation]:
        """添加笔记关联。"""
        # 验证笔记存在
        source = self.notes.get_note(source_id)
        target = self.notes.get_note(target_id)

        if not source or not target:
            return None

        # 创建关系
        relation = NoteRelation(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type
        )

        # 更新源笔记
        source.add_relation(target_id, relation_type)

        # 双向关系
        if bidirectional:
            reverse_type = self._get_reverse_type(relation_type)
            target.add_relation(source_id, reverse_type)

        # 缓存关系
        if source_id not in self._relations:
            self._relations[source_id] = []
        self._relations[source_id].append(relation)

        self.notes._save_project_notes()
        return relation

    def get_related_notes(
        self,
        note_id: str,
        depth: int = 1
    ) -> dict[str, list[str]]:
        """获取关联笔记图。"""
        result: dict[str, list[str]] = {}
        visited = {note_id}
        current_level = [note_id]

        for level in range(1, depth + 1):
            next_level = []
            result[str(level)] = []

            for nid in current_level:
                note = self.notes.get_note(nid)
                if note:
                    for related_id in note.relations:
                        if related_id not in visited:
                            visited.add(related_id)
                            next_level.append(related_id)
                            result[str(level)].append(related_id)

            current_level = next_level
            if not current_level:
                break

        return result
```

### 3.4 自动关联检测

```python
# 文件: src/mini_coder/memory/note_relations.py

class AutoRelationDetector:
    """自动检测笔记关联。"""

    def __init__(
        self,
        notes_manager: ProjectNotesManager,
        relation_manager: NoteRelationManager,
        similarity_threshold: float = 0.75
    ):
        self.notes = notes_manager
        self.relations = relation_manager
        self.threshold = similarity_threshold

    def detect_relations(
        self,
        note: ProjectNote,
        auto_link: bool = False
    ) -> list[tuple[str, RelationType, float]]:
        """检测笔记的潜在关联。

        Returns:
            List of (note_id, suggested_relation_type, confidence)
        """
        candidates = []
        all_notes = self.notes.get_notes(active_only=True)

        for other in all_notes:
            if other.id == note.id:
                continue

            # 计算相似度
            similarity = self._calculate_similarity(note, other)

            if similarity >= self.threshold:
                # 推断关系类型
                relation_type = self._infer_relation_type(note, other)
                candidates.append((other.id, relation_type, similarity))

        # 按相似度排序
        candidates.sort(key=lambda x: x[2], reverse=True)

        # 自动链接（可选）
        if auto_link:
            for other_id, rel_type, conf in candidates[:3]:  # 最多 3 个
                self.relations.add_relation(note.id, other_id, rel_type)

        return candidates

    def _calculate_similarity(
        self,
        note1: ProjectNote,
        note2: ProjectNote
    ) -> float:
        """计算两个笔记的相似度。"""
        # 方法 1：标签重叠
        tag_overlap = len(set(note1.tags) & set(note2.tags)) / max(
            len(set(note1.tags) | set(note2.tags)), 1
        )

        # 方法 2：内容相似度（简单词频）
        words1 = set(note1.content.lower().split())
        words2 = set(note2.content.lower().split())
        word_overlap = len(words1 & words2) / max(len(words1 | words2), 1)

        # 方法 3：类别关联规则
        category_bonus = self._get_category_affinity(note1.category, note2.category)

        # 综合得分
        return 0.3 * tag_overlap + 0.5 * word_overlap + 0.2 * category_bonus

    def _get_category_affinity(self, cat1: str, cat2: str) -> float:
        """获取类别之间的亲和度。"""
        # 定义类别关联规则
        affinity_rules = {
            ("decision", "pattern"): 0.8,   # 决策常与模式关联
            ("decision", "todo"): 0.6,      # 决策产生待办
            ("todo", "block"): 0.7,         # 待办可能被阻塞
            ("block", "todo"): 0.7,         # 阻塞影响待办
            ("pattern", "info"): 0.5,       # 模式与信息相关
        }

        if cat1 == cat2:
            return 0.9  # 同类高亲和

        return affinity_rules.get((cat1, cat2), affinity_rules.get((cat2, cat1), 0.3))

    def _infer_relation_type(
        self,
        note1: ProjectNote,
        note2: ProjectNote
    ) -> RelationType:
        """推断关系类型。"""
        # 基于类别的推断规则
        if note1.category == "decision" and note2.category == "todo":
            return RelationType.RELATED_TO  # 决策产生待办
        if note1.category == "todo" and note2.category == "block":
            return RelationType.DEPENDS_ON  # 待办依赖阻塞解决
        if note1.category == "decision" and note2.category == "pattern":
            return RelationType.IMPLEMENTS  # 决策实现模式

        return RelationType.RELATED_TO  # 默认
```

### 3.5 实施步骤

| 步骤 | 任务 | 文件 | 复杂度 |
|------|------|------|--------|
| 1 | 创建 `RelationType` 枚举 | `memory/note_relations.py` | 低 |
| 2 | 创建 `NoteRelation` 模型 | `memory/note_relations.py` | 低 |
| 3 | 扩展 `ProjectNote` 模型 | `memory/project_notes.py` | 低 |
| 4 | 实现 `NoteRelationManager` | `memory/note_relations.py` | 中 |
| 5 | 实现 `AutoRelationDetector` | `memory/note_relations.py` | 高 |
| 6 | 集成到 `LLMService` | `llm/service.py` | 中 |
| 7 | 添加配置选项 | `config/memory.yaml` | 低 |
| 8 | 编写单元测试 | `tests/memory/test_relations.py` | 中 |

---

## 实施路线图

```
┌─────────────────────────────────────────────────────────────────┐
│                      实施路线图                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Phase 1: 基础增强 (1-2 周)                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  方向三：笔记关联 (部分)                                  │   │
│  │  • 数据模型扩展 (relations 字段)                         │   │
│  │  • 基础 NoteRelationManager                              │   │
│  │  • 手动关联 API                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  Phase 2: 智能增强 (2-3 周)                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  方向一：自动提取                                         │   │
│  │  • 规则匹配 NoteExtractor                                │   │
│  │  • 集成到 chat_stream                                    │   │
│  │                                                          │   │
│  │  方向三：自动关联                                         │   │
│  │  • AutoRelationDetector                                  │   │
│  │  • 与自动提取联动                                        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  Phase 3: 高级功能 (3-4 周)                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  方向二：语义搜索                                         │   │
│  │  • 添加 embedding 依赖                                   │   │
│  │  • LocalEmbeddingService                                 │   │
│  │  • SemanticNoteSearch                                    │   │
│  │  • 索引构建与持久化                                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 依赖关系

```
方向一 (自动提取)          方向二 (语义搜索)          方向三 (笔记关联)
       │                          │                          │
       ▼                          ▼                          ▼
┌─────────────┐            ┌─────────────┐            ┌─────────────┐
│ 规则匹配    │            │ Embedding   │            │ 数据模型    │
│ (无依赖)    │            │ Service     │            │ (无依赖)    │
└─────────────┘            └─────────────┘            └─────────────┘
       │                          │                          │
       │                          │                          ▼
       │                          │                  ┌─────────────┐
       │                          │                  │ Relation    │
       │                          │                  │ Manager     │
       │                          │                  └─────────────┘
       │                          │                          │
       │                          ▼                          │
       │                   ┌─────────────┐                   │
       │                   │ Semantic    │                   │
       │                   │ Search      │◀──────────────────┘
       │                   └─────────────┘    (共享 embedding)
       │                          │
       ▼                          │
┌─────────────┐                   │
│ 与方向三    │───────────────────┘
│ 联动        │   (自动关联可使用语义搜索)
└─────────────┘
```

## 配置文件

```yaml
# config/memory.yaml

enabled: true
max_messages: 100
compression_threshold: 0.92
storage_path: ~/.mini-coder/memory

# NoteTool 增强
notes:
  # 自动提取
  auto_extract:
    enabled: true
    confidence_threshold: 0.8
    use_llm: false  # 是否使用 LLM 辅助

  # 语义搜索（嵌入配置见 config/llm.yaml embeddings 段）
  semantic_search:
    enabled: false  # Phase 3 启用
    # 默认使用 fastembed；backend: "api" 时使用在线 API
    similarity_threshold: 0.7
    index_cache_size: 1000

  # 笔记关联
  relations:
    enabled: true
    auto_detect: true
    auto_detect_threshold: 0.75
    max_auto_relations: 3
```

## 参考资源

- [Hello-Agents 第九章：上下文工程](https://gitee.com/qzl9999/Hello-Agents/blob/main/docs/chapter9/)
- [fastembed 文档](https://github.com/qdrant/fastembed)（默认本地嵌入）
- mini-coder 现有实现:
  - `src/mini_coder/memory/project_notes.py`
  - `src/mini_coder/memory/context_builder.py`
  - `src/mini_coder/llm/service.py`

---

## 实现状态 (2026-03-04)

### 已完成功能

#### 1. ProjectNote 模型扩展 ✅
- `relations: list[str]` - 关联笔记 ID 列表
- `relation_types: dict[str, str]` - 笔记 ID 到关系类型的映射
- `embedding: Optional[list[float]]` - 语义搜索向量
- `embedding_model: Optional[str]` - 使用的嵌入模型名称
- `add_relation()`, `remove_relation()`, `get_related_notes()`, `needs_embedding()` 方法

#### 2. 自动笔记提取 ✅
- `src/mini_coder/memory/note_extractor.py` - 规则匹配提取器
- `EXTRACTION_PATTERNS` - 支持中英文的决策、待办、阻塞、模式、信息提取
- `ExtractedNote` 模型 - 包含置信度评分
- `NoteExtractor` 类 - `extract()` 方法返回提取的笔记列表
- 集成到 `LLMService.chat_stream()` - 自动提取并保存笔记

#### 3. 笔记关联系统 ✅
- `src/mini_coder/memory/note_relations.py` - 关联管理模块
- `RelationType` 枚举 - 6 种关系类型
- `NoteRelation` 模型 - 源/目标 ID、关系类型、元数据
- `NoteRelationManager` - CRUD 操作、图遍历
- `AutoRelationDetector` - 基于标签/内容/类别亲和度的自动关联检测
- `CATEGORY_AFFINITY` - 类别间关系推断规则

#### 4. 语义搜索 ✅
- `src/mini_coder/memory/embeddings.py` - 嵌入服务（默认 fastembed，可选 API）
- `LocalEmbeddingService` - fastembed / OpenAI 兼容 API 双后端，批处理受 `batch_size` 限制
- `cosine_similarity()` - 静态方法计算向量相似度
- 优雅降级 - 无可用后端时回退关键词搜索或词重叠相似度
- `src/mini_coder/memory/semantic_search.py` - 语义搜索服务
- `SemanticNoteSearch` - `build_index()`, `search()`, `find_similar()`

#### 5. LLMService 集成 ✅
- `auto_extract_notes` 参数 - 启用自动提取
- `extraction_confidence` 参数 - 提取置信度阈值
- `_extract_and_save_notes()` - 私有方法
- `search_notes_semantic()` - 语义搜索便捷方法
- `add_relation()` - 添加关系便捷方法
- `get_related_notes()` - 获取相关笔记便捷方法（支持深度遍历）

#### 6. 配置 ✅
- `config/memory.yaml` - 完整配置选项
  - `notes.auto_extract.enabled/confidence_threshold/use_llm`
  - `notes.semantic_search.enabled/model/similarity_threshold/max_results`
  - `notes.relations.enabled/auto_detect/auto_detect_threshold/max_auto_relations`

#### 7. 依赖 ✅
- `pyproject.toml` 更新
  - `numpy>=1.24.0` - 核心依赖
  - `fastembed>=0.2.0` - 可选依赖 (semantic 组，默认本地嵌入)
  - `openai>=1.0.0` - 可选依赖 (semantic-api 组，使用 embedding API 时)

### 测试覆盖

- `tests/memory/test_project_notes.py` - 82 个测试
  - ProjectNote 模型测试
  - ProjectNotesManager 测试
  - 关系和嵌入字段测试
  - LLMService 新方法测试
  - 自动提取测试
- `tests/memory/test_extractor.py` - 18 个测试
- `tests/memory/test_relations.py` - 20 个测试
- `tests/memory/test_embeddings.py` - 13 个测试（需要网络）

### API 使用示例

```python
from mini_coder.llm.service import LLMService

# 初始化服务（启用自动提取）
service = LLMService(
    config_path="config/llm.yaml",
    enable_memory=True,
    enable_notes=True,
    auto_extract_notes=True
)
service.start_session("/path/to/project")

# 自动提取会在 chat_stream 中自动执行
async for chunk in service.chat_stream("我们需要使用 PostgreSQL"):
    print(chunk)

# 手动添加关系
note1_id = service.add_decision("Use FastAPI", "For async support")
note2_id = service.add_todo("Add API tests", "Test all endpoints")
service.add_relation(note1_id, note2_id, "related_to")

# 获取相关笔记
related = service.get_related_notes(note1_id, depth=2)

# 语义搜索（需要启用 semantic_search）
results = service.search_notes_semantic("database configuration", top_k=5)
```

### 待完成

- [x] mypy 类型检查
- [x] flake8 PEP 8 检查
- [x] 完整测试覆盖率报告
