"""Embedding service for semantic search.

默认使用 fastembed（本地、无 PyTorch）；当配置中明确启用 embedding API 时使用在线 API。

Example:
    >>> from mini_coder.memory import LocalEmbeddingService
    >>> service = LocalEmbeddingService()  # 默认 fastembed
    >>> embedding = service.embed("Hello world")

配置（config/llm.yaml）:
    embeddings:
      backend: "fastembed"   # 默认，或 "api" 使用在线 API
      # 使用 API 时需配置：
      # use_api: true
      # api_key: "DASHSCOPE_EMBEDDING_API_KEY"
      # base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
      # model: "text-embedding-v4"
      # fastembed 可选：batch_size: 32  # 每批条数，控制内存
"""

import logging
import os
from pathlib import Path
from typing import Any, Literal, Optional

import numpy as np

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# 默认 API 配置（当使用 api 且未从文件加载时）
DEFAULT_EMBEDDING_API_CONFIG = {
    "api_key": "DASHSCOPE_EMBEDDING_API_KEY",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "model": "text-embedding-v4",
}

# fastembed 默认模型（384 维，语义检索兼容）
FASTEMBED_DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"

# 仅 fastembed 后端（移除 sentence-transformers）
try:
    from fastembed import TextEmbedding as FastEmbedTextEmbedding
    _FASTEMBED_AVAILABLE = True
except ImportError:
    _FASTEMBED_AVAILABLE = False
    FastEmbedTextEmbedding = None  # type: ignore


def _check_openai_available() -> bool:
    """检查 openai 包是否可用（用于 API 后端）。"""
    import importlib.util
    return importlib.util.find_spec("openai") is not None


def _load_embedding_config_from_yaml() -> dict:
    """从 llm.yaml 加载 embeddings 配置。

    Returns:
        配置字典，可能包含 backend, use_api, api_key, base_url, model, batch_size 等。
    """
    config_paths = [
        Path.cwd() / "config" / "llm.yaml",
        Path.home() / ".mini-coder" / "config" / "llm.yaml",
    ]
    for config_path in config_paths:
        if config_path.exists():
            try:
                import yaml
                with open(config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                if config and "embeddings" in config:
                    logger.debug("Loaded embeddings config from %s", config_path)
                    return dict(config["embeddings"])
            except Exception as e:
                logger.warning("Failed to load embeddings config from %s: %s", config_path, e)
    return {}


class EmbeddingConfig(BaseModel):
    """嵌入服务配置。

    Attributes:
        model_name: 模型名（fastembed 或 API 的 model）。
        backend: "fastembed"（默认）或 "api"。
        use_api: 为 true 时强制使用 API，等价于 backend="api"。
        api_key: API 密钥或环境变量名。
        base_url: API base URL。
        cache_size: 内存中缓存嵌入数量上限。
        normalize: 是否 L2 归一化。
        batch_size: fastembed 批处理条数上限，避免单批过大占内存。
    """

    model_name: str = FASTEMBED_DEFAULT_MODEL
    backend: Literal["fastembed", "api"] = "fastembed"
    use_api: bool = False
    api_key: str = ""
    base_url: str = ""
    cache_size: int = 1000
    normalize: bool = True
    batch_size: int = 32


class LocalEmbeddingService:
    """本地/在线嵌入服务：默认 fastembed，配置启用时使用 embedding API。

    不使用 sentence-transformers（避免 PyTorch 占内存）；fastembed 批处理受 batch_size 限制。
    """

    # API 模型常用维度（如 text-embedding-v4）
    API_DEFAULT_DIMENSION = 1024

    def __init__(
        self,
        model_name: Optional[str] = None,
        config: Optional[EmbeddingConfig] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        config_path: Optional[str] = None,
    ):
        """初始化嵌入服务。

        配置优先级（从高到低）：
        1. 传入的 config / model_name / api_key / base_url
        2. config_path 或自动查找的 llm.yaml 中的 embeddings 段
        3. 默认：backend=fastembed，batch_size=32

        Args:
            model_name: 模型名（覆盖配置）。
            config: 配置对象；若为 None 则从 YAML 加载或使用默认。
            api_key: API 密钥（仅 API 后端）。
            base_url: API base URL（仅 API 后端）。
            config_path: 指定 llm.yaml 路径（可选）。
        """
        self._config_path = config_path
        self._loaded_yaml: Optional[dict] = None

        self._api_key = api_key
        self._base_url = base_url
        self._model_name_arg = model_name

        if config is not None:
            self.config = config
            if api_key is not None:
                self.config.api_key = api_key
            if base_url is not None:
                self.config.base_url = base_url
            if model_name is not None:
                self.config.model_name = model_name
            self._resolve_backend_and_model()
        else:
            self.config = EmbeddingConfig()
            self._load_yaml_and_apply()
            self._resolve_backend_and_model()

        self.model_name = self.config.model_name
        self._backend: Literal["fastembed", "api"] = self.config.backend
        self._model: Optional[Any] = None
        self._dimension: Optional[int] = None
        self._client: Optional[Any] = None
        self._available: Optional[bool] = None

    def _load_yaml_and_apply(self) -> None:
        """从 YAML 加载 embeddings 配置并合并到 self.config。"""
        if self._loaded_yaml is not None:
            return
        paths = [Path(self._config_path)] if self._config_path else []
        paths += [
            Path.cwd() / "config" / "llm.yaml",
            Path.home() / ".mini-coder" / "config" / "llm.yaml",
        ]
        yaml_config: dict = {}
        for p in paths:
            if not p.exists():
                continue
            try:
                import yaml
                with open(p, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if data and "embeddings" in data:
                    yaml_config = dict(data["embeddings"])
                    break
            except Exception as e:
                logger.debug("Skip config %s: %s", p, e)

        self._loaded_yaml = yaml_config

        if not yaml_config:
            return

        if "backend" in yaml_config:
            self.config.backend = str(yaml_config["backend"]).lower()
            if self.config.backend not in ("fastembed", "api"):
                self.config.backend = "fastembed"
        if yaml_config.get("use_api") is True:
            self.config.use_api = True
            self.config.backend = "api"
        if "model" in yaml_config:
            self.config.model_name = str(yaml_config["model"])
        if "api_key" in yaml_config:
            self.config.api_key = str(yaml_config["api_key"])
        if "base_url" in yaml_config:
            self.config.base_url = str(yaml_config["base_url"])
        if "batch_size" in yaml_config:
            try:
                self.config.batch_size = max(1, int(yaml_config["batch_size"]))
            except (TypeError, ValueError):
                pass

        if self._model_name_arg is not None:
            self.config.model_name = self._model_name_arg
        if self._api_key is not None:
            self.config.api_key = self._api_key
        if self._base_url is not None:
            self.config.base_url = self._base_url

    def _resolve_backend_and_model(self) -> None:
        """根据 config 确定 backend 和 model_name。"""
        if self.config.use_api:
            self.config.backend = "api"
        if self.config.backend == "api":
            if not self.config.model_name or self.config.model_name == FASTEMBED_DEFAULT_MODEL:
                self.config.model_name = DEFAULT_EMBEDDING_API_CONFIG["model"]
            return
        # fastembed
        if not self.config.model_name or self.config.model_name in (
            "text-embedding-v4",
            "all-MiniLM-L6-v2",
        ):
            self.config.model_name = FASTEMBED_DEFAULT_MODEL
        self.model_name = self.config.model_name

    @property
    def is_available(self) -> bool:
        """嵌入服务是否可用。"""
        if self._available is not None:
            return self._available
        if self._backend == "fastembed":
            self._available = _FASTEMBED_AVAILABLE
            if not self._available:
                logger.warning(
                    "fastembed not installed. Semantic search will be disabled. "
                    "Install with: pip install fastembed"
                )
        else:
            self._available = self._init_api_client()
        return self._available

    def _init_api_client(self) -> bool:
        """初始化 API 客户端（懒加载）。"""
        if self._client is not None:
            return True
        if not _check_openai_available():
            logger.warning(
                "openai package not installed. Semantic search (API) will be disabled. "
                "Install with: pip install openai"
            )
            return False
        key = self._get_api_key()
        if not key:
            logger.warning(
                "No embedding API key. Set DASHSCOPE_EMBEDDING_API_KEY or embeddings.api_key in config."
            )
            return False
        try:
            from openai import OpenAI
            base = self.config.base_url or DEFAULT_EMBEDDING_API_CONFIG["base_url"]
            self._client = OpenAI(api_key=key, base_url=base)
            logger.info("Embedding API initialized: model=%s", self.model_name)
            return True
        except Exception as e:
            logger.warning("Failed to init embedding API client: %s", e)
            return False

    def _get_api_key(self) -> Optional[str]:
        """从配置或环境变量获取 API key。"""
        raw = self.config.api_key or os.getenv("DASHSCOPE_EMBEDDING_API_KEY")
        if not raw:
            return None
        if raw.isupper() and "_" in raw:
            return os.getenv(raw)
        return raw

    @property
    def dimension(self) -> int:
        """嵌入向量维度。"""
        if self._dimension is not None:
            return self._dimension
        if self._backend == "api":
            self._dimension = self.API_DEFAULT_DIMENSION
            return self._dimension
        if self._backend == "fastembed" and self._available:
            self._load_fastembed_model()
            self._dimension = self._get_fastembed_dimension()
        else:
            self._dimension = 384
        return self._dimension

    def _load_fastembed_model(self) -> None:
        """懒加载 fastembed 模型。"""
        if self._model is not None or not _FASTEMBED_AVAILABLE:
            return
        logger.info("Loading embedding model: %s (fastembed)", self.model_name)
        self._model = FastEmbedTextEmbedding(model_name=self.model_name)

    def _get_fastembed_dimension(self) -> int:
        """获取 fastembed 向量维度并缓存。"""
        if self._dimension is not None:
            return self._dimension
        if self._model is None:
            return 384
        out = list(self._model.embed(["x"]))
        dim = len(out[0]) if out and len(out[0]) > 0 else 384
        self._dimension = dim
        return dim

    def _normalize_if(self, arr: np.ndarray) -> np.ndarray:
        """按 config.normalize 做 L2 归一化。"""
        if not self.config.normalize:
            return arr
        norms = np.linalg.norm(arr, axis=-1, keepdims=True) + 1e-10
        return (arr / norms).astype(np.float32)

    def embed(self, text: str) -> np.ndarray:
        """单条文本嵌入。"""
        if not self.is_available:
            raise RuntimeError(
                "Embedding service not available. "
                "Install fastembed or configure embedding API (openai + api_key)."
            )

        if self._backend == "api":
            return self._embed_api_single(text)

        self._load_fastembed_model()
        emb_list = list(self._model.embed([text]))
        if not emb_list:
            return np.zeros(self._get_fastembed_dimension(), dtype=np.float32)
        return self._normalize_if(np.array(emb_list[0], dtype=np.float32))

    def _embed_api_single(self, text: str) -> np.ndarray:
        """API 单条嵌入。"""
        resp = self._client.embeddings.create(model=self.model_name, input=text)
        emb = np.array(resp.data[0].embedding, dtype=np.float32)
        return self._normalize_if(emb)

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        """批量文本嵌入。fastembed 下按 batch_size 分批以控制内存。"""
        if not self.is_available:
            raise RuntimeError(
                "Embedding service not available. "
                "Install fastembed or configure embedding API (openai + api_key)."
            )
        if not texts:
            return np.array([])

        if self._backend == "api":
            return self._embed_api_batch(texts)

        self._load_fastembed_model()
        batch_size = max(1, getattr(self.config, "batch_size", 32))
        out_list: list[np.ndarray] = []
        for i in range(0, len(texts), batch_size):
            chunk = texts[i : i + batch_size]
            emb_list = list(self._model.embed(chunk))
            if emb_list:
                out_list.append(np.array(emb_list, dtype=np.float32))
        if not out_list:
            dim = self._get_fastembed_dimension()
            return np.zeros((0, dim), dtype=np.float32)
        out = np.concatenate(out_list, axis=0)
        return self._normalize_if(out)

    def _embed_api_batch(self, texts: list[str]) -> np.ndarray:
        """API 批量嵌入。"""
        resp = self._client.embeddings.create(model=self.model_name, input=texts)
        emb = np.array([item.embedding for item in resp.data], dtype=np.float32)
        return self._normalize_if(emb)

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """两向量余弦相似度。"""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    @staticmethod
    def cosine_similarity_batch(query: np.ndarray, embeddings: np.ndarray) -> np.ndarray:
        """查询向量与多条嵌入的余弦相似度。"""
        if len(embeddings) == 0:
            return np.array([])
        q = query / (np.linalg.norm(query) + 1e-10)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-10
        return np.dot(embeddings / norms, q)

    def get_similarity(self, text1: str, text2: str) -> float:
        """两段文本的语义相似度（0~1）。"""
        if not self.is_available:
            w1 = set(text1.lower().split())
            w2 = set(text2.lower().split())
            if not w1 or not w2:
                return 0.0
            return len(w1 & w2) / len(w1 | w2)
        e1 = self.embed(text1)
        e2 = self.embed(text2)
        return (self.cosine_similarity(e1, e2) + 1) / 2


# 任一后端可用即视为可用（运行时由 LocalEmbeddingService.is_available 决定）
EMBEDDINGS_AVAILABLE = _FASTEMBED_AVAILABLE or _check_openai_available()
