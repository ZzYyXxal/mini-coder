"""Integration tests for LLM Service with Context Memory.

Tests cover the integration between LLMService and ContextMemoryManager.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestLLMServiceContextIntegration:
    """Tests for LLMService with context memory integration."""

    @pytest.fixture
    def temp_config_dir(self, tmp_path: Path) -> Path:
        """Create a temporary config directory."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Create LLM config
        llm_config = config_dir / "llm.yaml"
        llm_config.write_text("""
default_provider: zhipu
providers:
  zhipu:
    api_key: test-key
    base_url: https://test.api/
    model: test-model
""")

        # Create memory config
        memory_config = config_dir / "memory.yaml"
        memory_config.write_text("""
enabled: true
max_messages: 10
compression_threshold: 0.92
storage_path: ~/.mini-coder/test-memory
""")

        return config_dir

    @pytest.fixture
    def mock_provider(self):
        """Create a mock LLM provider."""
        provider = MagicMock()
        provider.send_message.return_value = "Test response"
        provider.send_message_stream.return_value = iter([
            {"type": "delta", "content": "Test "},
            {"type": "delta", "content": "response"},
            {"type": "done", "content": ""}
        ])
        # Add support for send_with_context (GSSC integration)
        provider.send_with_context.return_value = iter([
            {"type": "delta", "content": "Test "},
            {"type": "delta", "content": "response"},
            {"type": "done", "content": ""}
        ])
        return provider

    def test_service_initializes_with_memory(self, temp_config_dir: Path) -> None:
        """Test that LLMService initializes with memory enabled."""
        from mini_coder.llm.service import LLMService

        config_path = str(temp_config_dir / "llm.yaml")
        service = LLMService(config_path, enable_memory=True)

        assert service.memory_enabled is True
        assert service._context_manager is not None

    def test_service_initializes_without_memory(self, temp_config_dir: Path) -> None:
        """Test that LLMService can be initialized without memory."""
        from mini_coder.llm.service import LLMService

        config_path = str(temp_config_dir / "llm.yaml")
        service = LLMService(config_path, enable_memory=False)

        assert service.memory_enabled is False

    def test_session_management(self, temp_config_dir: Path) -> None:
        """Test session management through LLMService."""
        from mini_coder.llm.service import LLMService

        config_path = str(temp_config_dir / "llm.yaml")
        service = LLMService(config_path, enable_memory=True)

        # Start session
        session_id = service.start_session("/test/project")
        assert session_id is not None
        assert service.session_id == session_id

        # List sessions
        sessions = service.list_sessions()
        # Initially no saved sessions

        # Save session
        service.save_session()

        # List sessions after save
        sessions = service.list_sessions()
        assert session_id in sessions

    def test_chat_adds_to_context(
        self,
        temp_config_dir: Path,
        mock_provider: MagicMock
    ) -> None:
        """Test that chat adds messages to context."""
        from mini_coder.llm.service import LLMService

        config_path = str(temp_config_dir / "llm.yaml")
        service = LLMService(config_path, enable_memory=True)
        service.provider = mock_provider

        service.start_session()
        response = service.chat("Hello")

        assert response == "Test response"
        assert service._context_manager.message_count == 2  # user + assistant

    def test_chat_stream_adds_to_context(
        self,
        temp_config_dir: Path,
        mock_provider: MagicMock
    ) -> None:
        """Test that chat_stream adds messages to context."""
        from mini_coder.llm.service import LLMService

        config_path = str(temp_config_dir / "llm.yaml")
        service = LLMService(config_path, enable_memory=True)
        service.provider = mock_provider

        service.start_session()

        # Consume the stream
        chunks = list(service.chat_stream("Hello"))

        # 3 chunks: 2 delta + 1 done
        assert len(chunks) == 3
        assert service._context_manager.message_count == 2  # user + assistant

    def test_clear_history_clears_context(self, temp_config_dir: Path) -> None:
        """Test that clear_history clears both provider and context."""
        from mini_coder.llm.service import LLMService

        config_path = str(temp_config_dir / "llm.yaml")
        service = LLMService(config_path, enable_memory=True)

        service.start_session()
        service._context_manager.add_message("user", "Test")

        service.clear_history()

        assert service._context_manager.message_count == 0

    def test_restore_latest_session(self, temp_config_dir: Path) -> None:
        """Test restoring the latest session."""
        from mini_coder.llm.service import LLMService

        config_path = str(temp_config_dir / "llm.yaml")
        service = LLMService(config_path, enable_memory=True)

        # Create and save a session
        session_id = service.start_session()
        service._context_manager.add_message("user", "Test message")
        service.save_session()

        # Start new session (clears context)
        service.start_session()
        assert service._context_manager.message_count == 0

        # Restore latest
        result = service.restore_latest_session()

        assert result is True
        assert service._context_manager.message_count == 1

    def test_load_session(self, temp_config_dir: Path) -> None:
        """Test loading a specific session."""
        from mini_coder.llm.service import LLMService

        config_path = str(temp_config_dir / "llm.yaml")
        service = LLMService(config_path, enable_memory=True)

        # Create and save a session
        session_id = service.start_session()
        service._context_manager.add_message("user", "Test message")
        service.save_session()

        # Start new session
        service.start_session()
        assert service._context_manager.message_count == 0

        # Load previous session
        result = service.load_session(session_id)

        assert result is True
        assert service._context_manager.message_count == 1

    def test_load_nonexistent_session(self, temp_config_dir: Path) -> None:
        """Test loading a session that doesn't exist."""
        from mini_coder.llm.service import LLMService

        config_path = str(temp_config_dir / "llm.yaml")
        service = LLMService(config_path, enable_memory=True)

        result = service.load_session("nonexistent")

        assert result is False


class TestLLMServiceSessionRestoreSync:
    """Tests for provider history synchronization during session restore.

    These tests verify the fix for the bug where:
    1. User says their name in a session
    2. Session is saved
    3. TUI is restarted (new LLMService instance)
    4. Session is restored
    5. Provider's internal history should be synchronized with ContextMemoryManager

    Bug: The provider's _conversation history was not synchronized after restore,
    causing the LLM to receive empty context even though ContextMemoryManager had
    the messages.
    """

    @pytest.fixture
    def temp_config_dir(self, tmp_path: Path) -> Path:
        """Create a temporary config directory."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Create LLM config
        llm_config = config_dir / "llm.yaml"
        llm_config.write_text("""
default_provider: zhipu
providers:
  zhipu:
    api_key: test-key
    base_url: https://test.api/
    model: test-model
""")

        # Create memory config with unique storage path
        import uuid
        unique_id = uuid.uuid4().hex[:8]
        memory_config = config_dir / "memory.yaml"
        memory_config.write_text(f"""
enabled: true
max_messages: 20
compression_threshold: 0.92
storage_path: ~/.mini-coder/test-memory-{unique_id}
""")

        return config_dir

    def test_provider_history_synced_after_load_session(
        self,
        temp_config_dir: Path
    ) -> None:
        """Test that provider history is synchronized after load_session.

        Regression test for: Session restored but provider history was empty,
        causing LLM to not receive conversation context.
        """
        from mini_coder.llm.service import LLMService

        config_path = str(temp_config_dir / "llm.yaml")

        # First service instance: create session with messages
        service1 = LLMService(config_path, enable_memory=True)
        session_id = service1.start_session()

        # Simulate conversation
        service1._context_manager.add_message("user", "我叫赵鹏飞")
        service1._context_manager.add_message("assistant", "你好，赵鹏飞！")

        # Save session
        service1.save_session()

        # Second service instance: simulate TUI restart
        service2 = LLMService(config_path, enable_memory=True)

        # Load the previous session
        result = service2.load_session(session_id)

        assert result is True

        # Verify ContextMemoryManager has messages
        assert service2._context_manager.message_count == 2

        # CRITICAL: Verify provider history is also synchronized
        # This was the bug - provider history was empty after restore
        provider_history = service2.provider._conversation
        assert len(provider_history) == 2, \
            f"Provider history should have 2 messages, got {len(provider_history)}"

        # Verify message content is correct
        assert provider_history[0]["role"] == "user"
        assert "赵鹏飞" in provider_history[0]["content"]
        assert provider_history[1]["role"] == "assistant"
        assert "赵鹏飞" in provider_history[1]["content"]

    def test_provider_history_synced_after_restore_latest(
        self,
        temp_config_dir: Path
    ) -> None:
        """Test that provider history is synchronized after restore_latest_session.

        This is the main flow used by TUI on startup.
        """
        from mini_coder.llm.service import LLMService

        config_path = str(temp_config_dir / "llm.yaml")

        # First service instance: create and save session
        service1 = LLMService(config_path, enable_memory=True)
        service1.start_session()
        service1._context_manager.add_message("user", "我的项目路径是 /home/user/project")
        service1._context_manager.add_message("assistant", "好的，我记住了你的项目路径")
        service1.save_session()

        # Second service instance: simulate TUI restart
        service2 = LLMService(config_path, enable_memory=True)

        # Restore latest session (what TUI does on startup)
        result = service2.restore_latest_session()

        assert result is True

        # Verify both ContextMemoryManager and Provider have history
        assert service2._context_manager.message_count == 2

        provider_history = service2.provider._conversation
        assert len(provider_history) == 2, \
            f"Provider history should be synced, got {len(provider_history)} messages"

        # Verify content
        assert "项目路径" in provider_history[0]["content"]

    def test_memory_persists_across_service_restarts(
        self,
        temp_config_dir: Path
    ) -> None:
        """Test full workflow: message -> save -> restart -> restore -> verify.

        This simulates the exact user scenario:
        1. User tells their name
        2. User saves session (/save)
        3. User exits TUI
        4. User restarts TUI
        5. User asks "what's my name" - should remember
        """
        from mini_coder.llm.service import LLMService

        config_path = str(temp_config_dir / "llm.yaml")

        # Step 1-2: User says name and saves
        service1 = LLMService(config_path, enable_memory=True)
        service1.start_session()
        service1._context_manager.add_message("user", "我叫赵鹏飞")
        service1._context_manager.add_message("assistant", "你好赵鹏飞，很高兴认识你！")
        service1.save_session()

        # Step 3-4: Simulate TUI restart (new service instance)
        service2 = LLMService(config_path, enable_memory=True)

        # Step 4: TUI auto-restores latest session on startup
        restored = service2.restore_latest_session()
        assert restored is True

        # Step 5: Verify the conversation context is available
        context = service2._context_manager.get_context(max_tokens=10000)

        # Find the user's name in context
        user_messages = [m for m in context if m["role"] == "user"]
        assert len(user_messages) == 1
        assert "赵鹏飞" in user_messages[0]["content"]

        # Also verify provider history (used for actual LLM calls)
        provider_history = service2.provider._conversation
        user_in_provider = [m for m in provider_history if m["role"] == "user"]
        assert len(user_in_provider) == 1
        assert "赵鹏飞" in user_in_provider[0]["content"]

    def test_sync_provider_history_handles_empty_session(
        self,
        temp_config_dir: Path
    ) -> None:
        """Test that syncing works correctly with empty sessions."""
        from mini_coder.llm.service import LLMService

        config_path = str(temp_config_dir / "llm.yaml")

        service1 = LLMService(config_path, enable_memory=True)
        session_id = service1.start_session()
        # Don't add any messages
        service1.save_session()

        service2 = LLMService(config_path, enable_memory=True)
        result = service2.load_session(session_id)

        assert result is True
        assert service2._context_manager.message_count == 0
        assert len(service2.provider._conversation) == 0

    def test_sync_provider_history_clears_existing_first(
        self,
        temp_config_dir: Path
    ) -> None:
        """Test that syncing clears existing provider history before restoring.

        This ensures we don't have duplicate or stale messages.
        """
        from mini_coder.llm.service import LLMService
        from unittest.mock import MagicMock

        config_path = str(temp_config_dir / "llm.yaml")

        # Create and save session with specific messages
        service1 = LLMService(config_path, enable_memory=True)
        session_id = service1.start_session()
        service1._context_manager.add_message("user", "Session 1 message")
        service1.save_session()

        # Create second service with pre-existing provider history
        # (simulating a service that has been used before)
        service2 = LLMService(config_path, enable_memory=True)
        service2.start_session()

        # Manually add to provider's conversation to simulate previous usage
        # (normally done via service.chat() but we're testing the sync directly)
        service2.provider._conversation.append({
            "role": "user",
            "content": "Stale message that should be cleared"
        })

        # Verify provider has the stale message
        assert len(service2.provider._conversation) == 1
        assert "Stale" in service2.provider._conversation[0]["content"]

        # Now load Session 1 - this should clear and replace with Session 1
        service2.load_session(session_id)

        # Provider should now only have Session 1 messages (stale message cleared)
        assert len(service2.provider._conversation) == 1
        assert "Session 1" in service2.provider._conversation[0]["content"]

    def test_restore_returns_false_when_no_sessions(
        self,
        temp_config_dir: Path
    ) -> None:
        """Test that restore_latest_session returns False when no sessions exist."""
        from mini_coder.llm.service import LLMService

        config_path = str(temp_config_dir / "llm.yaml")
        service = LLMService(config_path, enable_memory=True)

        # No sessions saved yet
        result = service.restore_latest_session()

        assert result is False
