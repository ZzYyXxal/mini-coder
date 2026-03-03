"""Tests for SubAgent with tool filtering."""

import pytest
from unittest.mock import Mock, MagicMock

from src.mini_coder.agents import SubAgent, SubAgentConfig
from src.mini_coder.tools.filter import (
    ToolFilter,
    ReadOnlyFilter,
    FullAccessFilter,
    StrictFilter,
    CustomFilter,
)


class MockLLMService:
    """Mock LLM Service for testing."""

    def __init__(self):
        self._tools = {
            "Read": Mock(),
            "Write": Mock(),
            "LS": Mock(),
            "Glob": Mock(),
            "Grep": Mock(),
            "Edit": Mock(),
            "Command": Mock(),
            "Bash": Mock(),
        }

    def get_registered_tools(self):
        return self._tools

    def chat(self, message: str, **kwargs) -> str:
        return f"Response: {message}"


class TestSubAgentConfig:
    """Tests for SubAgentConfig."""

    def test_create_config_defaults(self) -> None:
        """Test creating config with defaults."""
        config = SubAgentConfig(name="test")

        assert config.name == "test"
        assert config.agent_type == "custom"
        assert config.tool_filter is None
        assert config.system_prompt is None

    def test_create_config_with_values(self) -> None:
        """Test creating config with specific values."""
        filter_instance = ReadOnlyFilter()
        config = SubAgentConfig(
            name="explore_agent",
            agent_type="explore",
            tool_filter=filter_instance,
            system_prompt="You are a helpful assistant.",
        )

        assert config.name == "explore_agent"
        assert config.agent_type == "explore"
        assert config.tool_filter is filter_instance
        assert config.system_prompt == "You are a helpful assistant."


class TestSubAgent:
    """Tests for SubAgent."""

    @pytest.fixture
    def llm_service(self) -> MockLLMService:
        """Create mock LLM service."""
        return MockLLMService()

    def test_create_explore_subagent(self, llm_service: MockLLMService) -> None:
        """Test creating explore subagent with read-only filter."""
        agent = SubAgent.create_explore(llm_service)

        assert agent.config.agent_type == "explore"
        assert isinstance(agent._filter, ReadOnlyFilter)

        # Check tool filtering
        assert agent.is_tool_allowed("Read") is True
        assert agent.is_tool_allowed("Write") is False
        assert agent.is_tool_allowed("LS") is True
        assert agent.is_tool_allowed("Grep") is True

    def test_create_plan_subagent(self, llm_service: MockLLMService) -> None:
        """Test creating plan subagent with read-only filter."""
        agent = SubAgent.create_plan(llm_service)

        assert agent.config.agent_type == "plan"
        assert isinstance(agent._filter, ReadOnlyFilter)

    def test_create_code_subagent(self, llm_service: MockLLMService) -> None:
        """Test creating code subagent with full access filter."""
        agent = SubAgent.create_code(llm_service)

        assert agent.config.agent_type == "code"
        assert isinstance(agent._filter, FullAccessFilter)

        # Check tool filtering
        assert agent.is_tool_allowed("Read") is True
        assert agent.is_tool_allowed("Write") is True
        assert agent.is_tool_allowed("Edit") is True
        assert agent.is_tool_allowed("Command_sudo") is False
        assert agent.is_tool_allowed("Bash") is False

    def test_create_custom_subagent(self, llm_service: MockLLMService) -> None:
        """Test creating custom subagent with custom filter."""
        custom_filter = CustomFilter(
            allowed={"Read", "Grep", "LS"},
            mode="whitelist"
        )
        agent = SubAgent.create_custom(llm_service, tool_filter=custom_filter)

        assert agent.config.agent_type == "custom"
        assert agent._filter is custom_filter

        assert agent.is_tool_allowed("Read") is True
        assert agent.is_tool_allowed("Grep") is True
        assert agent.is_tool_allowed("Write") is False

    def test_available_tools(self, llm_service: MockLLMService) -> None:
        """Test getting available tools for subagent."""
        agent = SubAgent.create_explore(llm_service)
        tools = agent.available_tools

        assert "Read" in tools
        assert "LS" in tools
        assert "Grep" in tools
        assert "Write" not in tools
        assert "Edit" not in tools

    def test_chat_with_tool_context(self, llm_service: MockLLMService) -> None:
        """Test chat method includes tool context."""
        agent = SubAgent.create_explore(llm_service)
        response = agent.chat("Explore the codebase")

        # Should include tool context in message
        assert "Response:" in response
        assert "Read" in response  # Tool name should be in the context

    def test_custom_name(self, llm_service: MockLLMService) -> None:
        """Test creating subagent with custom name."""
        agent = SubAgent.create_explore(llm_service, name="my_explore")
        assert agent.config.name == "my_explore"

    def test_custom_system_prompt(self, llm_service: MockLLMService) -> None:
        """Test creating subagent with custom system prompt."""
        prompt = "You are an expert code explorer."
        agent = SubAgent.create_explore(llm_service, system_prompt=prompt)
        assert agent.config.system_prompt == prompt


class TestSubAgentDefaults:
    """Tests for default filter mappings."""

    def test_default_filter_mapping(self) -> None:
        """Test that default filters are correctly mapped."""
        assert SubAgent.DEFAULT_FILTERS["explore"] == ReadOnlyFilter
        assert SubAgent.DEFAULT_FILTERS["plan"] == ReadOnlyFilter
        assert SubAgent.DEFAULT_FILTERS["code"] == FullAccessFilter
        assert SubAgent.DEFAULT_FILTERS["custom"] == StrictFilter

    def test_unknown_agent_type_uses_strict(self) -> None:
        """Test that unknown agent types use StrictFilter."""
        llm_service = MockLLMService()
        config = SubAgentConfig(name="unknown", agent_type="unknown_type")
        agent = SubAgent(llm_service, config)

        assert isinstance(agent._filter, StrictFilter)


class TestSubAgentToolFilterIntegration:
    """Integration tests for subagent tool filtering."""

    @pytest.fixture
    def llm_service(self) -> MockLLMService:
        """Create mock LLM service."""
        return MockLLMService()

    def test_explore_blocks_write_operations(self, llm_service: MockLLMService) -> None:
        """Test that explore subagent blocks write operations."""
        agent = SubAgent.create_explore(llm_service)

        # Read operations allowed
        assert agent.is_tool_allowed("Read") is True
        assert agent.is_tool_allowed("Glob") is True

        # Write operations blocked
        assert agent.is_tool_allowed("Write") is False
        assert agent.is_tool_allowed("Edit") is False

    def test_code_allows_write_but_blocks_dangerous(self, llm_service: MockLLMService) -> None:
        """Test that code subagent allows writes but blocks dangerous tools."""
        agent = SubAgent.create_code(llm_service)

        # Write operations allowed
        assert agent.is_tool_allowed("Write") is True
        assert agent.is_tool_allowed("Edit") is True

        # Dangerous tools blocked
        assert agent.is_tool_allowed("Command_sudo") is False
        assert agent.is_tool_allowed("Command_rm_rf") is False
        assert agent.is_tool_allowed("Bash") is False

    def test_filter_additional_tools(self, llm_service: MockLLMService) -> None:
        """Test adding additional tools to filter."""
        # Explore with additional allowed tools
        filter_instance = ReadOnlyFilter(additional_allowed=["MyCustomTool"])
        config = SubAgentConfig(
            name="custom_explore",
            agent_type="explore",
            tool_filter=filter_instance,
        )
        agent = SubAgent(llm_service, config)

        assert agent.is_tool_allowed("Read") is True
        assert agent.is_tool_allowed("MyCustomTool") is True
        assert agent.is_tool_allowed("Write") is False
