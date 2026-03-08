"""Per-agent memory registry：每个 agent 独立记忆，且仅「关注项目进度」的 agent 使用 NoteTool。

- 每个 agent 类型拥有独立的 ContextMemoryManager / MemoryHook，存储路径按 agent 分目录。
- NoteTool（ProjectNotesManager）仅注入到 explorer、planner、coder 的 ContextBuilder；
  reviewer、bash 等不关注项目进度的 agent 不包含笔记上下文。
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .manager import ContextMemoryManager
from .context_builder import ContextBuilder
from .hook import MemoryHook
from .models import MemoryConfig

logger = logging.getLogger(__name__)

# 仅「关注项目进度」的 agent 使用 NoteTool（项目笔记）
AGENT_TYPES_WITH_NOTES = frozenset({"explorer", "planner", "coder"})

# 参与 per-agent 记忆的 agent 类型（与 SubAgentType.value 一致）
AGENT_TYPES_FOR_MEMORY = frozenset({
    "explorer", "planner", "coder", "reviewer", "bash",
    "general_purpose", "mini_coder_guide",
})


class AgentMemoryRegistry:
    """按 agent 类型提供独立记忆与 Hook；仅部分 agent 的 ContextBuilder 包含 NoteTool。"""

    def __init__(
        self,
        base_storage_path: str = "~/.mini-coder/memory",
        notes_manager: Optional[Any] = None,
        memory_config: Optional[MemoryConfig] = None,
    ):
        """初始化注册表。

        Args:
            base_storage_path: 记忆存储根目录，各 agent 使用子目录 base_storage_path/explorer 等。
            notes_manager: ProjectNotesManager，仅注入到 explorer/planner/coder 的 ContextBuilder。
            memory_config: 基础配置，仅 storage_path 会按 agent 覆盖。
        """
        self._base_path = Path(base_storage_path).expanduser()
        self._notes_manager = notes_manager
        self._config = memory_config or MemoryConfig()
        self._managers: Dict[str, ContextMemoryManager] = {}
        self._builders: Dict[str, ContextBuilder] = {}
        self._hooks: Dict[str, MemoryHook] = {}
        self._ensure_agent_memory()

    def _ensure_agent_memory(self) -> None:
        """为每个 agent 类型创建独立的 manager / context_builder / hook。"""
        for agent_type in AGENT_TYPES_FOR_MEMORY:
            storage_path = str(self._base_path / agent_type)
            config_dict = self._config.model_dump()
            config_dict["storage_path"] = storage_path
            config = MemoryConfig(**config_dict)
            manager = ContextMemoryManager(config=config)
            use_notes = agent_type in AGENT_TYPES_WITH_NOTES and self._notes_manager is not None
            builder = ContextBuilder(
                manager=manager,
                max_tokens=getattr(self._config, "max_context_tokens", 128000),
                notes_manager=self._notes_manager if use_notes else None,
            )
            hook = MemoryHook(manager=manager, context_builder=builder)
            self._managers[agent_type] = manager
            self._builders[agent_type] = builder
            self._hooks[agent_type] = hook
        logger.debug(
            "AgentMemoryRegistry: agents_with_notes=%s, all_agents=%s",
            sorted(AGENT_TYPES_WITH_NOTES),
            sorted(AGENT_TYPES_FOR_MEMORY),
        )

    def get_manager(self, agent_type: str) -> Optional[ContextMemoryManager]:
        """获取该 agent 类型的独立 ContextMemoryManager。"""
        return self._managers.get(agent_type)

    def get_context_builder(self, agent_type: str) -> Optional[ContextBuilder]:
        """获取该 agent 类型的 ContextBuilder（仅 explorer/planner/coder 带 notes_manager）。"""
        return self._builders.get(agent_type)

    def get_hook(self, agent_type: str) -> Optional[MemoryHook]:
        """获取该 agent 类型的 MemoryHook。"""
        return self._hooks.get(agent_type)

    def has_notes(self, agent_type: str) -> bool:
        """该 agent 是否使用 NoteTool（项目笔记）。"""
        return agent_type in AGENT_TYPES_WITH_NOTES and self._notes_manager is not None
