"""LLM Service module.

使用 OpenAI SDK 兼容接口统一管理 LLM 服务。
支持对话、流式响应、多轮对话、上下文记忆管理。
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Any

from .providers.openai_compatible import OpenAICompatibleProvider

# Patterns that might confuse the model or indicate commands
SUSPICIOUS_PATTERNS = [
    r'^/[a-zA-Z]+$',  # Slash commands like /session, /help
    r'^[^\w\s]{5,}$',  # Repeated special characters
    r'[\x00-\x08\x0b\x0c\x0e-\x1f]',  # Control characters
]

# Maximum input length to prevent context explosion
MAX_INPUT_LENGTH = 50000


class LLMService:
    """LLM Service - 使用 OpenAI SDK 兼容接口，集成上下文记忆管理。"""

    def __init__(
        self,
        config_path: str,
        enable_memory: bool = True,
        enable_notes: bool = True,
        auto_extract_notes: bool = False,
        extraction_confidence: float = 0.8,
        enable_command_tool: bool = True,
    ) -> None:
        """初始化 LLM 服务。

        Args:
            config_path: 配置文件路径（YAML）。
            enable_memory: 是否启用上下文记忆管理。
            enable_notes: 是否启用项目笔记管理（NoteTool-like）。
            auto_extract_notes: 是否自动从响应中提取笔记。
            extraction_confidence: 自动提取的置信度阈值。
            enable_command_tool: 是否启用命令执行工具。
        """
        self.config_path = config_path
        self.provider: Optional[OpenAICompatibleProvider] = None
        self.provider_name: str = "zhipu"
        self._enable_memory = enable_memory
        self._enable_notes = enable_notes
        self._auto_extract_notes = auto_extract_notes
        self._extraction_confidence = extraction_confidence
        self._enable_command_tool = enable_command_tool
        self._context_manager = None
        self._context_builder = None
        self._notes_manager = None
        self._note_extractor = None
        self._command_tool = None
        self._tools_registry: Dict[str, Any] = {}
        self._load_config()
        self._init_memory()
        self._init_note_extractor()
        self._init_command_tool()
        self._init_tools_registry()

    def _load_config(self) -> None:
        """从 YAML 文件加载配置。"""
        import yaml
        import os

        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
                self.provider_name = config.get('default_provider', 'zhipu')

                # 获取提供商配置
                providers = config.get('providers', {})
                provider_config = providers.get(self.provider_name, {})

                # 从环境变量获取 API Key（优先级高于配置文件）
                api_key = os.getenv(f"{self.provider_name.upper()}_API_KEY")
                if not api_key:
                    api_key = provider_config.get('api_key', '')

                # 创建统一的 OpenAI 兼容提供商
                self.provider = OpenAICompatibleProvider(
                    api_key=api_key,
                    base_url=provider_config.get('base_url', ''),
                    model=provider_config.get('model', ''),
                    system_prompt="你是一个简洁、有用的 AI 助手。请直接回答问题，不需要展示思考过程。",
                )

        except FileNotFoundError:
            # 配置文件不存在，使用默认值
            self.provider_name = 'zhipu'
            import os
            self.provider = OpenAICompatibleProvider(
                api_key=os.getenv("ZHIPU_API_KEY", ""),
                base_url="https://open.bigmodel.cn/api/paas/v4/",
                model="glm-5",
                system_prompt="你是一个简洁、有用的 AI 助手。请直接回答问题，不需要展示思考过程。",
            )

    def _init_memory(self) -> None:
        """初始化上下文记忆管理。"""
        if not self._enable_memory:
            return

        try:
            from mini_coder.memory import (
                ContextMemoryManager, MemoryConfig, ContextBuilder,
                ProjectNotesManager
            )
            import yaml

            # 尝试加载记忆配置
            config_dir = Path(self.config_path).parent
            memory_config_path = config_dir / "memory.yaml"

            if memory_config_path.exists():
                with open(memory_config_path, 'r') as f:
                    config_data = yaml.safe_load(f)
                memory_config = MemoryConfig(**config_data)
            else:
                memory_config = MemoryConfig()

            self._context_manager = ContextMemoryManager(config=memory_config)

            # Initialize project notes manager (NoteTool-like)
            if self._enable_notes:
                try:
                    self._notes_manager = ProjectNotesManager(
                        storage_path=memory_config.storage_path.replace("memory", "notes")
                    )
                except Exception as e:
                    logging.warning(f"Failed to initialize notes manager: {e}")
                    self._notes_manager = None

            self._context_builder = ContextBuilder(
                manager=self._context_manager,
                max_tokens=128000,
                notes_manager=self._notes_manager
            )

        except ImportError:
            # memory 模块不可用，禁用记忆功能
            self._enable_memory = False
            self._context_manager = None
            self._context_builder = None
            self._notes_manager = None

    def _init_note_extractor(self) -> None:
        """Initialize note extractor for auto-extraction."""
        if not self._auto_extract_notes or not self._notes_manager:
            return

        try:
            from mini_coder.memory import NoteExtractor
            self._note_extractor = NoteExtractor(
                confidence_threshold=self._extraction_confidence
            )
        except ImportError:
            self._note_extractor = None

    def _init_command_tool(self) -> None:
        """初始化命令执行工具。"""
        if not self._enable_command_tool:
            return

        try:
            import yaml
            from mini_coder.tools import (
                CommandTool,
                PermissionService,
                SecurityMode,
            )

            # 尝试加载工具配置
            config_dir = Path(self.config_path).parent
            tools_config_path = config_dir / "tools.yaml"

            security_mode = SecurityMode.NORMAL
            timeout = 120
            permission_cache_enabled = True

            if tools_config_path.exists():
                with open(tools_config_path, 'r') as f:
                    config_data = yaml.safe_load(f)
                    command_config = config_data.get('command', {})

                    # 安全模式
                    mode_str = command_config.get('security_mode', 'normal')
                    security_mode = SecurityMode.from_string(mode_str)

                    # 超时设置
                    timeout_config = command_config.get('timeout', {})
                    timeout = timeout_config.get('default', 120)

                    # 权限缓存
                    perm_config = command_config.get('permission', {})
                    permission_cache_enabled = perm_config.get('cache_enabled', True)

            # 初始化权限服务
            permission_service = PermissionService()
            if permission_cache_enabled:
                permission_service.auto_approve_session()

            # 初始化命令工具
            self._command_tool = CommandTool(
                security_mode=security_mode,
                permission_service=permission_service,
                timeout=timeout,
            )

        except ImportError as e:
            logging.warning(f"Failed to initialize CommandTool: {e}")
            self._command_tool = None
        except Exception as e:
            logging.warning(f"Failed to initialize CommandTool: {e}")
            self._command_tool = None

    def _init_tools_registry(self) -> None:
        """初始化工具注册表。"""
        # 注册命令工具
        if self._command_tool:
            self._tools_registry["Command"] = self._command_tool

    def _extract_and_save_notes(self, response: str) -> int:
        """Extract and save notes from LLM response.

        Args:
            response: The LLM response text.

        Returns:
            Number of notes extracted and saved.
        """
        if not self._note_extractor or not self._notes_manager:
            return 0

        try:
            extracted = self._note_extractor.extract(response)
            saved_count = 0

            for note in extracted:
                if note.confidence >= self._extraction_confidence:
                    self._notes_manager.add_note(
                        category=note.category,
                        title=note.title,
                        content=note.content,
                        tags=["auto-extracted"]
                    )
                    saved_count += 1
                else:
                    # Low confidence - save with pending confirmation tag
                    self._notes_manager.add_note(
                        category=note.category,
                        title=f"[待确认] {note.title}",
                        content=note.content,
                        tags=["auto-extracted", "needs-confirmation"]
                    )
                    saved_count += 1

            return saved_count
        except Exception as e:
            logging.warning(f"Failed to extract notes: {e}")
            return 0

    @property
    def memory_enabled(self) -> bool:
        """检查是否启用了上下文记忆。"""
        return self._enable_memory and self._context_manager is not None

    @property
    def session_id(self) -> Optional[str]:
        """获取当前会话 ID。"""
        if self._context_manager:
            return self._context_manager.current_session_id
        return None

    def _validate_input(self, message: str) -> tuple[bool, str]:
        """Validate user input before sending to LLM.

        Args:
            message: User input message.

        Returns:
            Tuple of (is_valid, processed_message or error_message).
        """
        # Check for empty input
        if not message or not message.strip():
            return False, "Empty message"

        # Check for excessive length
        if len(message) > MAX_INPUT_LENGTH:
            logging.warning(f"Input truncated from {len(message)} to {MAX_INPUT_LENGTH} chars")
            message = message[:MAX_INPUT_LENGTH] + "... [truncated]"

        # Check for suspicious patterns that might confuse the model
        for pattern in SUSPICIOUS_PATTERNS:
            if re.search(pattern, message):
                # For slash commands, provide a helpful hint
                if re.match(r'^/[a-zA-Z]+$', message.strip()):
                    logging.info(f"Received unrecognized command-like input: {message}")
                    # Don't reject, but log it for monitoring
                else:
                    logging.warning(f"Input contains suspicious pattern: {pattern}")

        # Check for potential binary/control content
        if any(ord(c) < 32 and c not in '\n\r\t' for c in message):
            # Remove control characters
            message = ''.join(c if ord(c) >= 32 or c in '\n\r\t' else '' for c in message)
            logging.warning("Removed control characters from input")

        return True, message

    def start_session(self, project_path: Optional[str] = None) -> str:
        """开始新的会话。

        Args:
            project_path: 可选的项目路径。

        Returns:
            会话 ID。
        """
        # Set project path on notes manager
        if self._notes_manager and project_path:
            self._notes_manager.set_project(project_path)

        if self._context_manager:
            return self._context_manager.start_session(project_path)
        return ""

    def save_session(self) -> None:
        """保存当前会话。"""
        if self._context_manager:
            self._context_manager.save_session()

    def load_session(self, session_id: str) -> bool:
        """加载之前的会话。

        Args:
            session_id: 会话 ID。

        Returns:
            是否成功加载。
        """
        if self._context_manager:
            result = self._context_manager.load_session(session_id)
            if result:
                self._sync_provider_history()
            return result
        return False

    def list_sessions(self) -> List[str]:
        """列出所有保存的会话。

        Returns:
            会话 ID 列表。
        """
        if self._context_manager:
            return self._context_manager.list_sessions()
        return []

    def restore_latest_session(self) -> bool:
        """恢复最近的会话。

        Returns:
            是否成功恢复。
        """
        if self._context_manager:
            result = self._context_manager.restore_latest_session()
            if result:
                self._sync_provider_history()
            return result
        return False

    def _sync_provider_history(self) -> None:
        """同步 Provider 的对话历史与 ContextManager。"""
        if not self.provider or not self._context_manager:
            return

        # 清空 Provider 的历史
        self.provider.clear_history()

        # 从 ContextManager 获取所有消息并同步到 Provider
        context = self._context_manager.get_context(max_tokens=1000000)  # 获取全部
        for msg in context:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if content:
                self.provider.add_to_history(role, content)

    def chat(self, message: str, **kwargs) -> str:
        """发送消息并获取响应（非流式）。

        Args:
            message: 用户消息。
            **kwargs: 额外参数。

        Returns:
            AI 响应内容。
        """
        if self.provider is None:
            raise ValueError("No LLM provider configured.")

        # Validate input
        is_valid, processed_message = self._validate_input(message)
        if not is_valid:
            return f"[Error] {processed_message}"

        # 添加用户消息到上下文
        if self._context_manager:
            self._context_manager.add_message("user", processed_message)

        # 获取响应
        response = self.provider.send_message(processed_message, **kwargs)

        # 添加助手响应到上下文
        if self._context_manager and response:
            self._context_manager.add_message("assistant", response)

        return response

    def chat_stream(self, message: str, **kwargs):
        """发送消息并获取流式响应。

        GSSC 流水线 + Plan B 内存管理:
        1. Validate - 输入验证
        2. Pre-check (GSSC) - 使用 ContextBuilder 检查并压缩
        3. Add - 添加用户消息
        4. Stream - 流式响应（使用 GSSC 构建的上下文）
        5. Complete - 添加助手响应

        Args:
            message: 用户消息。
            **kwargs: 额外参数。

        Yields:
            Dict 包含 type 和 content 字段。
        """
        if self.provider is None:
            raise ValueError("No LLM provider configured.")

        # 1. Validate - 输入验证
        is_valid, processed_message = self._validate_input(message)
        if not is_valid:
            yield {"type": "error", "content": processed_message}
            return

        # 2. Pre-check (GSSC) - 使用 ContextBuilder 进行压缩和上下文构建
        compression_stats = {}
        if self._context_builder:
            # 使用 build_with_compression 触发 Plan B 压缩
            _, compression_stats = self._context_builder.build_with_compression(
                max_tokens=128000
            )

            # 报告压缩结果
            if compression_stats.get("pruned_tokens", 0) > 0:
                yield {"type": "system", "content": f"[已清理 {compression_stats['pruned_tokens']} tokens 的工具输出]"}

            if compression_stats.get("compressed_messages", 0) > 0:
                count = compression_stats["compressed_messages"]
                yield {"type": "system", "content": f"[已压缩 {count} 条消息]"}

        # 3. Add - 添加用户消息到上下文
        if self._context_manager:
            self._context_manager.add_message("user", processed_message)

        # 4. Stream - 使用 GSSC 构建的上下文获取流式响应
        full_response = ""

        if self._context_builder:
            # 使用 ContextBuilder 构建完整的上下文（包括用户消息）
            context = self._context_builder.build_with_user_message(
                user_message=processed_message,
                max_tokens=128000,
                auto_compress=False  # 已经在步骤2处理过压缩
            )

            # 使用预构建的上下文发送请求
            for chunk in self.provider.send_with_context(context, **kwargs):
                if chunk.get("type") == "delta":
                    content = chunk.get("content", "")
                    full_response += content
                yield chunk
        else:
            # 回退到旧的流程（不使用 GSSC）
            for chunk in self.provider.send_message_stream(processed_message, **kwargs):
                if chunk.get("type") == "delta":
                    content = chunk.get("content", "")
                    full_response += content
                yield chunk

        # 5. Complete - 添加完整响应到上下文
        if self._context_manager and full_response:
            self._context_manager.add_message("assistant", full_response)

        # 6. Auto-extract - 自动提取笔记
        if self._auto_extract_notes and self._note_extractor and full_response:
            extracted = self._extract_and_save_notes(full_response)
            if extracted > 0:
                yield {"type": "system", "content": f"[自动提取 {extracted} 条笔记]"}

    async def async_chat(self, message: str, **kwargs) -> str:
        """异步发送消息并获取响应。

        Args:
            message: 用户消息。
            **kwargs: 额外参数。

        Returns:
            AI 响应内容。
        """
        if self.provider is None:
            raise ValueError("No LLM provider configured.")

        # 添加用户消息到上下文
        if self._context_manager:
            self._context_manager.add_message("user", message)

        response = await self.provider.async_send_message(message, **kwargs)

        # 添加助手响应到上下文
        if self._context_manager and response:
            self._context_manager.add_message("assistant", response)

        return response

    async def async_chat_stream(self, message: str, **kwargs):
        """异步发送消息并获取流式响应。

        GSSC 流水线 + Plan B 内存管理:
        1. Validate - 输入验证
        2. Pre-check (GSSC) - 使用 ContextBuilder 检查并压缩
        3. Add - 添加用户消息
        4. Stream - 流式响应（使用 GSSC 构建的上下文）
        5. Complete - 添加助手响应

        Args:
            message: 用户消息。
            **kwargs: 额外参数。

        Yields:
            Dict 包含 type 和 content 字段。
        """
        if self.provider is None:
            raise ValueError("No LLM provider configured.")

        # 1. Validate - 输入验证
        is_valid, processed_message = self._validate_input(message)
        if not is_valid:
            yield {"type": "error", "content": processed_message}
            return

        # 2. Pre-check (GSSC) - 使用 ContextBuilder 进行压缩和上下文构建
        compression_stats = {}
        if self._context_builder:
            # 使用 build_with_compression 触发 Plan B 压缩
            _, compression_stats = self._context_builder.build_with_compression(
                max_tokens=128000
            )

            # 报告压缩结果
            if compression_stats.get("pruned_tokens", 0) > 0:
                yield {"type": "system", "content": f"[已清理 {compression_stats['pruned_tokens']} tokens 的工具输出]"}

            if compression_stats.get("compressed_messages", 0) > 0:
                count = compression_stats["compressed_messages"]
                yield {"type": "system", "content": f"[已压缩 {count} 条消息]"}

        # 3. Add - 添加用户消息到上下文
        if self._context_manager:
            self._context_manager.add_message("user", processed_message)

        # 4. Stream - 使用 GSSC 构建的上下文获取流式响应
        full_response = ""

        if self._context_builder:
            # 使用 ContextBuilder 构建完整的上下文（包括用户消息）
            context = self._context_builder.build_with_user_message(
                user_message=processed_message,
                max_tokens=128000,
                auto_compress=False  # 已经在步骤2处理过压缩
            )

            # 使用预构建的上下文发送请求
            for chunk in self.provider.send_with_context(context, **kwargs):
                if chunk.get("type") == "delta":
                    content = chunk.get("content", "")
                    full_response += content
                yield chunk
        else:
            # 回退到旧的流程（不使用 GSSC）
            async for chunk in self.provider.async_send_message_stream(processed_message, **kwargs):
                if chunk.get("type") == "delta":
                    content = chunk.get("content", "")
                    full_response += content
                yield chunk

        # 5. Complete - 添加完整响应到上下文
        if self._context_manager and full_response:
            self._context_manager.add_message("assistant", full_response)

    def clear_history(self) -> None:
        """清除对话历史。"""
        # region agent log
        try:
            import json
            import time
            from pathlib import Path

            log_path = Path("/root/LLM/mini-coder/.cursor/debug-61572a.log")
            log_entry = {
                "sessionId": "61572a",
                "runId": "pre-fix",
                "hypothesisId": "H3",
                "location": "src/mini_coder/llm/service.py:604",
                "message": "LLMService.clear_history called",
                "data": {
                    "provider_name": getattr(self, "provider_name", None),
                    "has_provider": self.provider is not None,
                    "has_context_manager": getattr(self, "_context_manager", None) is not None,
                },
                "timestamp": int(time.time() * 1000),
            }
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception:
            pass
        # endregion

        if self.provider:
            self.provider.clear_history()
        if getattr(self, '_context_manager', None):
            self._context_manager.clear()

    def set_provider(self, provider_name: str) -> None:
        """切换提供商。

        Args:
            provider_name: 提供商名称。
        """
        self.provider_name = provider_name
        self._load_config()

    # ==================== Project Notes Management (NoteTool-like) ====================

    @property
    def notes_enabled(self) -> bool:
        """检查是否启用了项目笔记。"""
        return self._enable_notes and self._notes_manager is not None

    def add_note(
        self,
        category: str,
        title: str,
        content: str,
        tags: Optional[List[str]] = None
    ) -> Optional[str]:
        """添加项目笔记。

        Args:
            category: 笔记类别 (decision, todo, pattern, info, block)。
            title: 笔记标题。
            content: 笔记内容（支持 Markdown）。
            tags: 可选标签列表。

        Returns:
            笔记 ID，如果笔记功能未启用则返回 None。
        """
        if not self._notes_manager:
            return None

        note = self._notes_manager.add_note(
            category=category,
            title=title,
            content=content,
            tags=tags
        )
        return note.id

    def add_decision(self, title: str, content: str, tags: Optional[List[str]] = None) -> Optional[str]:
        """添加设计决策笔记。"""
        return self.add_note("decision", title, content, tags)

    def add_todo(self, title: str, content: str, tags: Optional[List[str]] = None) -> Optional[str]:
        """添加待办事项。"""
        return self.add_note("todo", title, content, tags)

    def add_pattern(self, title: str, content: str, tags: Optional[List[str]] = None) -> Optional[str]:
        """添加代码模式/约定笔记。"""
        return self.add_note("pattern", title, content, tags)

    def add_info(self, title: str, content: str, tags: Optional[List[str]] = None) -> Optional[str]:
        """添加项目信息笔记。"""
        return self.add_note("info", title, content, tags)

    def add_block(self, title: str, content: str, tags: Optional[List[str]] = None) -> Optional[str]:
        """添加阻塞问题笔记。"""
        return self.add_note("block", title, content, tags)

    def complete_todo(self, note_id: str) -> bool:
        """标记待办事项为完成。

        Args:
            note_id: 笔记 ID。

        Returns:
            是否成功完成。
        """
        if not self._notes_manager:
            return False
        note = self._notes_manager.complete_note(note_id)
        return note is not None

    def resolve_block(self, note_id: str) -> bool:
        """解决阻塞问题。

        Args:
            note_id: 笔记 ID。

        Returns:
            是否成功解决。
        """
        if not self._notes_manager:
            return False
        note = self._notes_manager.update_note(note_id, status=3)  # RESOLVED
        return note is not None

    def list_notes(
        self,
        category: Optional[str] = None,
        active_only: bool = True
    ) -> List[Dict]:
        """列出项目笔记。

        Args:
            category: 可选类别过滤。
            active_only: 是否只显示活跃笔记。

        Returns:
            笔记列表。
        """
        if not self._notes_manager:
            return []

        notes = self._notes_manager.get_notes(
            category=category,
            active_only=active_only
        )
        return [
            {
                "id": n.id,
                "category": n.category,
                "title": n.title,
                "content": n.content[:100] + "..." if len(n.content) > 100 else n.content,
                "tags": n.tags,
                "status": n.status,
            }
            for n in notes
        ]

    def search_notes(self, query: str) -> List[Dict]:
        """搜索项目笔记。

        Args:
            query: 搜索关键词。

        Returns:
            匹配的笔记列表。
        """
        if not self._notes_manager:
            return []

        notes = self._notes_manager.search_notes(query)
        return [
            {
                "id": n.id,
                "category": n.category,
                "title": n.title,
                "content": n.content[:100] + "..." if len(n.content) > 100 else n.content,
                "tags": n.tags,
            }
            for n in notes
        ]

    def delete_note(self, note_id: str) -> bool:
        """删除项目笔记。

        Args:
            note_id: 笔记 ID。

        Returns:
            是否成功删除。
        """
        if not self._notes_manager:
            return False
        return self._notes_manager.delete_note(note_id)

    def get_notes_stats(self) -> Dict:
        """获取笔记统计信息。

        Returns:
            统计信息字典。
        """
        if not self._notes_manager:
            return {"total": 0, "active": 0}
        return self._notes_manager.get_stats()

    # ==================== Command Tool Integration ====================

    @property
    def command_tool_enabled(self) -> bool:
        """检查是否启用了命令执行工具。"""
        return self._enable_command_tool and self._command_tool is not None

    def execute_command(
        self,
        command: str,
        timeout: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """执行命令（通过 CommandTool）。

        Args:
            command: 要执行的命令。
            timeout: 可选的超时时间（秒）。

        Returns:
            执行结果字典，包含：
                - success: bool, 是否成功
                - stdout: str, 标准输出
                - stderr: str, 错误输出
                - exit_code: int, 退出码
                - execution_time_ms: int, 执行时间
            如果命令工具未启用，返回 None。
        """
        if not self._command_tool:
            return None

        # 设置会话 ID（如果有）
        if self._context_manager and self._context_manager.current_session_id:
            self._command_tool.set_session_id(self._context_manager.current_session_id)

        # 执行命令
        result = self._command_tool._execute_with_security(command, timeout)

        return {
            "success": result.success,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "execution_time_ms": result.execution_time_ms,
        }

    def is_command_safe(self, command: str) -> tuple[bool, str]:
        """检查命令是否安全。

        Args:
            command: 要检查的命令。

        Returns:
            tuple[bool, str]: (是否安全，原因)
        """
        if not self._command_tool:
            return True, "命令工具未启用"
        return self._command_tool.is_command_safe(command)

    def get_available_commands(self) -> Dict[str, Any]:
        """获取可用的命令列表。

        Returns:
            包含 safe_commands, banned_commands, requires_confirmation 的字典。
        """
        if not self._command_tool:
            return {"safe_commands": [], "banned_commands": [], "requires_confirmation": []}
        return self._command_tool.get_available_commands()

    def get_registered_tools(self) -> Dict[str, Any]:
        """获取已注册的工具字典。

        Returns:
            工具名称到工具实例的映射。
        """
        return self._tools_registry.copy()

    def register_tool(self, name: str, tool: Any) -> None:
        """注册自定义工具。

        Args:
            name: 工具名称。
            tool: 工具实例。
        """
        self._tools_registry[name] = tool

    def unregister_tool(self, name: str) -> None:
        """注销工具。

        Args:
            name: 工具名称。
        """
        self._tools_registry.pop(name, None)

    # ==================== Semantic Search & Relations ====================

    def search_notes_semantic(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.7
    ) -> List[Dict]:
        """语义搜索笔记。

        Args:
            query: 搜索查询。
            top_k: 返回的最大结果数。
            threshold: 相似度阈值。

        Returns:
            匹配的笔记列表（包含相似度分数）。
        """
        if not self._notes_manager:
            return []

        notes = self._notes_manager.search_notes(
            query=query,
            semantic=True,
            top_k=top_k,
            threshold=threshold
        )
        return [
            {
                "id": n.id,
                "category": n.category,
                "title": n.title,
                "content": n.content[:100] + "..." if len(n.content) > 100 else n.content,
                "tags": n.tags,
            }
            for n in notes
        ]

    def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: str = "related_to"
    ) -> bool:
        """添加笔记关系。

        Args:
            source_id: 源笔记 ID。
            target_id: 目标笔记 ID。
            relation_type: 关系类型 (related_to, depends_on, blocks, implements, supersedes, derived_from)。

        Returns:
            是否成功添加。
        """
        if not self._notes_manager:
            return False

        source_note = self._notes_manager.get_note(source_id)
        target_note = self._notes_manager.get_note(target_id)

        if not source_note or not target_note:
            return False

        source_note.add_relation(target_id, relation_type)
        self._notes_manager._save_project_notes()
        return True

    def get_related_notes(
        self,
        note_id: str,
        depth: int = 1
    ) -> List[Dict]:
        """获取相关笔记。

        Args:
            note_id: 笔记 ID。
            depth: 关系深度（1 = 直接相关，2 = 间接相关）。

        Returns:
            相关笔记列表。
        """
        if not self._notes_manager:
            return []

        # Get the note
        note = self._notes_manager.get_note(note_id)
        if not note:
            return []

        # Get directly related notes
        related_ids = note.relations.copy()
        result = []

        # BFS for depth > 1
        if depth > 1:
            visited = set(related_ids)
            visited.add(note_id)
            current_level = related_ids.copy()

            for _ in range(depth - 1):
                next_level = []
                for rid in current_level:
                    related_note = self._notes_manager.get_note(rid)
                    if related_note:
                        for nid in related_note.relations:
                            if nid not in visited:
                                visited.add(nid)
                                next_level.append(nid)
                related_ids.extend(next_level)
                current_level = next_level

        # Build result
        for rid in related_ids:
            related_note = self._notes_manager.get_note(rid)
            if related_note:
                relation_type = note.relation_types.get(rid, "related_to")
                result.append({
                    "id": related_note.id,
                    "category": related_note.category,
                    "title": related_note.title,
                    "content": related_note.content[:100] + "..." if len(related_note.content) > 100 else related_note.content,
                    "tags": related_note.tags,
                    "relation_type": relation_type,
                })

        return result
