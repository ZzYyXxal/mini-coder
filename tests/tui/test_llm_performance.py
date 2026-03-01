"""Performance tests for LLM service.

These tests ensure LLM service performance does not degrade over time.
Key metrics tested:
- First character response time
- Client connection reuse
- Streaming functionality
"""

import time
import pytest
from unittest.mock import Mock, patch, MagicMock
import json


class TestLLMClientReuse:
    """测试客户端连接复用。"""

    def test_sync_client_is_reused(self):
        """同步客户端应该被复用，不应该每次调用都创建新实例。"""
        import sys
        sys.path.insert(0, 'src')

        from mini_coder.llm.providers.openai_compatible import OpenAICompatibleProvider

        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://example.com",
            model="test-model",
        )

        # 第一次获取客户端
        client1 = provider._get_client()

        # 第二次获取客户端
        client2 = provider._get_client()

        # 应该是同一个实例
        assert client1 is client2, "HTTP 客户端应该被复用"

    def test_client_none_before_first_use(self):
        """客户端在首次使用前应该是 None。"""
        import sys
        sys.path.insert(0, 'src')

        from mini_coder.llm.providers.openai_compatible import OpenAICompatibleProvider

        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://example.com",
            model="test-model",
        )

        assert provider._client is None, "客户端初始化前应该是 None"


class TestStreamingPerformance:
    """测试流式输出性能。"""

    def test_streaming_yields_chunks_immediately(self):
        """流式输出应该立即产生数据块，不应该等待完整响应。"""
        import sys
        sys.path.insert(0, 'src')

        from mini_coder.llm.providers.openai_compatible import OpenAICompatibleProvider
        import httpx

        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://example.com",
            model="test-model",
        )

        # 模拟 SSE 响应
        mock_response = Mock()
        mock_response.iter_lines.return_value = [
            'data: {"choices":[{"delta":{"content":"A"}}]}',
            'data: {"choices":[{"delta":{"content":"B"}}]}',
            'data: {"choices":[{"delta":{"content":"C"}}]}',
            'data: [DONE]',
        ]

        mock_context = MagicMock()
        mock_context.__enter__ = Mock(return_value=mock_response)
        mock_context.__exit__ = Mock(return_value=False)

        with patch.object(provider, '_get_client') as mock_client:
            mock_client.return_value.stream.return_value = mock_context

            chunks = list(provider.send_message_stream("test"))

            # 应该有 4 个块：3 个 delta + 1 个 done
            assert len(chunks) == 4
            assert chunks[0] == {"type": "delta", "content": "A"}
            assert chunks[1] == {"type": "delta", "content": "B"}
            assert chunks[2] == {"type": "delta", "content": "C"}
            assert chunks[3] == {"type": "done", "content": ""}

    def test_streaming_handles_reasoning_content(self):
        """流式输出应该支持 reasoning_content 格式（ZHIPU AI 使用）。"""
        import sys
        sys.path.insert(0, 'src')

        from mini_coder.llm.providers.openai_compatible import OpenAICompatibleProvider

        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://example.com",
            model="test-model",
        )

        # 模拟包含 reasoning_content 的 SSE 响应
        mock_response = Mock()
        mock_response.iter_lines.return_value = [
            'data: {"choices":[{"delta":{"reasoning_content":"思考中..."}}]}',
            'data: {"choices":[{"delta":{"content":"答案"}}]}',
            'data: [DONE]',
        ]

        mock_context = MagicMock()
        mock_context.__enter__ = Mock(return_value=mock_response)
        mock_context.__exit__ = Mock(return_value=False)

        with patch.object(provider, '_get_client') as mock_client:
            mock_client.return_value.stream.return_value = mock_context

            chunks = list(provider.send_message_stream("test"))

            # reasoning_content 也应该被处理
            assert len(chunks) == 3
            assert chunks[0] == {"type": "delta", "content": "思考中..."}
            assert chunks[1] == {"type": "delta", "content": "答案"}


class TestFirstCharacterLatency:
    """测试首字符响应延迟。"""

    def test_first_character_latency_benchmark(self):
        """首字符响应时间应该小于 2 秒（基准测试）。

        注意：这个测试使用 mock，只验证代码路径不阻塞。
        真实性能测试应该使用真实 API。
        """
        import sys
        sys.path.insert(0, 'src')

        from mini_coder.llm.providers.openai_compatible import OpenAICompatibleProvider

        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://example.com",
            model="test-model",
        )

        # 模拟快速响应的流
        def quick_stream():
            yield 'data: {"choices":[{"delta":{"content":"H"}}]}'
            yield 'data: {"choices":[{"delta":{"content":"i"}}]}'
            yield 'data: [DONE]'

        mock_response = Mock()
        mock_response.iter_lines.return_value = list(quick_stream())

        mock_context = MagicMock()
        mock_context.__enter__ = Mock(return_value=mock_response)
        mock_context.__exit__ = Mock(return_value=False)

        with patch.object(provider, '_get_client') as mock_client:
            mock_client.return_value.stream.return_value = mock_context

            start = time.time()
            first_chunk = None
            for chunk in provider.send_message_stream("test"):
                if first_chunk is None:
                    first_chunk = chunk
                    latency = time.time() - start
                    # 在 mock 环境下，延迟应该几乎为 0
                    assert latency < 0.1, f"首字符延迟过高: {latency}s"
                    break

    @pytest.mark.skip(reason="需要手动运行真实 API 测试")
    def test_real_api_first_character_latency(self):
        """真实 API 首字符响应时间测试（需要手动运行）。

        运行方式: pytest --run-real-api tests/tui/test_llm_performance.py
        """
        import os
        import sys
        sys.path.insert(0, 'src')

        from mini_coder.llm.service import LLMService

        api_key = os.getenv("ZHIPU_API_KEY")
        if not api_key:
            pytest.skip("ZHIPU_API_KEY 环境变量未设置")

        service = LLMService("config/llm.yaml")

        start = time.time()
        first_chunk = True

        for chunk in service.chat_stream("你好"):
            if chunk.get('type') == 'delta' and first_chunk:
                latency = time.time() - start
                first_chunk = False
                # 真实 API 首字符延迟应该小于 3 秒
                assert latency < 3.0, f"首字符延迟过高: {latency}s (应 < 3s)"
                break


class TestConnectionManagement:
    """测试连接管理。"""

    def test_httpx_timeout_configuration(self):
        """httpx 客户端应该有合理的超时配置。"""
        import sys
        sys.path.insert(0, 'src')

        from mini_coder.llm.providers.openai_compatible import OpenAICompatibleProvider
        import httpx

        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://example.com",
            model="test-model",
        )

        client = provider._get_client()

        # 验证超时配置
        assert client.timeout is not None
        # 连接超时应该较短
        assert client.timeout.connect <= 10.0

    def test_conversation_history_is_maintained(self):
        """对话历史应该被正确维护。"""
        import sys
        sys.path.insert(0, 'src')

        from mini_coder.llm.providers.openai_compatible import OpenAICompatibleProvider

        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://example.com",
            model="test-model",
        )

        # 模拟响应
        mock_response = Mock()
        mock_response.iter_lines.return_value = [
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            'data: [DONE]',
        ]

        mock_context = MagicMock()
        mock_context.__enter__ = Mock(return_value=mock_response)
        mock_context.__exit__ = Mock(return_value=False)

        with patch.object(provider, '_get_client') as mock_client:
            mock_client.return_value.stream.return_value = mock_context

            # 第一次对话
            list(provider.send_message_stream("Hi"))

            # 验证历史
            assert len(provider._conversation) == 2
            assert provider._conversation[0]["role"] == "user"
            assert provider._conversation[0]["content"] == "Hi"
            assert provider._conversation[1]["role"] == "assistant"
            assert provider._conversation[1]["content"] == "Hello"

    def test_clear_history_resets_conversation(self):
        """清除历史应该重置对话。"""
        import sys
        sys.path.insert(0, 'src')

        from mini_coder.llm.providers.openai_compatible import OpenAICompatibleProvider

        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://example.com",
            model="test-model",
        )

        # 添加一些历史
        provider.add_to_history("user", "test")
        provider.add_to_history("assistant", "response")

        assert len(provider._conversation) == 2

        # 清除历史
        provider.clear_history()

        assert len(provider._conversation) == 0


class TestServiceIntegration:
    """测试 LLMService 集成。"""

    def test_service_uses_provider_correctly(self):
        """LLMService 应该正确使用 Provider。"""
        import sys
        sys.path.insert(0, 'src')

        from mini_coder.llm.service import LLMService
        from mini_coder.llm.providers.openai_compatible import OpenAICompatibleProvider

        # 创建临时配置文件
        import tempfile
        import yaml
        import os

        # 临时清除环境变量
        old_env = os.environ.get('ZHIPU_API_KEY')
        if 'ZHIPU_API_KEY' in os.environ:
            del os.environ['ZHIPU_API_KEY']

        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump({
                    'default_provider': 'zhipu',
                    'providers': {
                        'zhipu': {
                            'api_key': 'test-key',
                            'base_url': 'https://example.com',
                            'model': 'test-model',
                        }
                    }
                }, f)
                config_path = f.name

            service = LLMService(config_path)

            assert service.provider is not None
            assert isinstance(service.provider, OpenAICompatibleProvider)
            assert service.provider._api_key == 'test-key'
            assert service.provider._model == 'test-model'

            os.unlink(config_path)
        finally:
            # 恢复环境变量
            if old_env is not None:
                os.environ['ZHIPU_API_KEY'] = old_env

    def test_service_clear_history_delegates_to_provider(self):
        """LLMService.clear_history 应该委托给 Provider。"""
        import sys
        sys.path.insert(0, 'src')

        from mini_coder.llm.service import LLMService

        with patch('mini_coder.llm.service.LLMService._load_config'):
            service = LLMService.__new__(LLMService)
            service.provider = Mock()

            service.clear_history()

            service.provider.clear_history.assert_called_once()


# 性能基准常量
PERFORMANCE_THRESHOLDS = {
    'first_char_latency_seconds': 3.0,  # 首字符延迟阈值
    'client_init_seconds': 0.1,         # 客户端初始化阈值
    'stream_chunk_overhead_ms': 10,     # 每个块的额外开销阈值
}


class TestPerformanceThresholds:
    """性能阈值测试。"""

    def test_performance_thresholds_are_defined(self):
        """性能阈值应该被定义。"""
        assert 'first_char_latency_seconds' in PERFORMANCE_THRESHOLDS
        assert 'client_init_seconds' in PERFORMANCE_THRESHOLDS
        assert 'stream_chunk_overhead_ms' in PERFORMANCE_THRESHOLDS

        # 阈值应该是合理的
        assert PERFORMANCE_THRESHOLDS['first_char_latency_seconds'] <= 5.0
        assert PERFORMANCE_THRESHOLDS['client_init_seconds'] <= 1.0
