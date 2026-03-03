"""Subagent module with tool filtering support.

Provides subagent creation with configurable tool access control.
"""

from typing import Optional, List, Dict, Any
from ..tools.filter import ToolFilter, ReadOnlyFilter, FullAccessFilter, StrictFilter


class SubAgentConfig:
    """Subagent configuration.

    Attributes:
        name: Agent name.
        agent_type: Agent type (explore, plan, code, custom).
        tool_filter: Tool filter to apply.
        system_prompt: Optional system prompt for the agent.
    """

    def __init__(
        self,
        name: str,
        agent_type: str = "custom",
        tool_filter: Optional[ToolFilter] = None,
        system_prompt: Optional[str] = None,
    ):
        """Initialize subagent config.

        Args:
            name: Agent name.
            agent_type: Agent type (explore, plan, code, custom).
            tool_filter: Tool filter to apply.
            system_prompt: Optional system prompt.
        """
        self.name = name
        self.agent_type = agent_type
        self.tool_filter = tool_filter
        self.system_prompt = system_prompt


class SubAgent:
    """Subagent with tool filtering.

    A subagent is a specialized agent with restricted tool access
    based on its role (explore, plan, code, etc.).

    Usage:
        # Create explore subagent (read-only)
        explore_agent = SubAgent.create_explore(llm_service)

        # Create code subagent (full access except dangerous tools)
        code_agent = SubAgent.create_code(llm_service)

        # Create custom subagent with custom filter
        custom_filter = CustomFilter(allowed={"Read", "Grep"})
        custom_agent = SubAgent(llm_service, tool_filter=custom_filter)
    """

    # Default filters for each agent type
    DEFAULT_FILTERS: Dict[str, type] = {
        "explore": ReadOnlyFilter,
        "plan": ReadOnlyFilter,
        "code": FullAccessFilter,
        "custom": StrictFilter,
    }

    def __init__(
        self,
        llm_service: Any,
        config: SubAgentConfig,
    ):
        """Initialize subagent.

        Args:
            llm_service: LLM service instance for chat.
            config: Subagent configuration.
        """
        self.llm_service = llm_service
        self.config = config
        self._filter = config.tool_filter or self._get_default_filter()

    def _get_default_filter(self) -> ToolFilter:
        """Get default filter for agent type."""
        filter_class = self.DEFAULT_FILTERS.get(self.config.agent_type, StrictFilter)
        return filter_class()

    @property
    def available_tools(self) -> List[str]:
        """Get list of available tools for this subagent."""
        if not hasattr(self.llm_service, 'get_registered_tools'):
            return []

        all_tools = list(self.llm_service.get_registered_tools().keys())
        return self._filter.filter(all_tools)

    def is_tool_allowed(self, tool_name: str) -> bool:
        """Check if a tool is allowed for this subagent.

        Args:
            tool_name: Tool name to check.

        Returns:
            True if tool is allowed, False otherwise.
        """
        return self._filter.is_allowed(tool_name)

    def chat(self, message: str, **kwargs) -> str:
        """Send message through subagent.

        Args:
            message: User message.
            **kwargs: Additional arguments for LLM.

        Returns:
            AI response.
        """
        # Add tool filter context to the message
        allowed_tools = self.available_tools
        if allowed_tools:
            tool_context = f"Available tools: {', '.join(allowed_tools)}"
            message = f"{tool_context}\n\n{message}"

        return self.llm_service.chat(message, **kwargs)

    @classmethod
    def create_explore(cls, llm_service: Any, **kwargs) -> "SubAgent":
        """Create explore subagent with read-only filter.

        Args:
            llm_service: LLM service instance.
            **kwargs: Additional arguments for SubAgentConfig.

        Returns:
            SubAgent instance.
        """
        config = SubAgentConfig(
            name=kwargs.get("name", "explore"),
            agent_type="explore",
            system_prompt=kwargs.get("system_prompt"),
        )
        return cls(llm_service, config)

    @classmethod
    def create_plan(cls, llm_service: Any, **kwargs) -> "SubAgent":
        """Create plan subagent with read-only filter.

        Args:
            llm_service: LLM service instance.
            **kwargs: Additional arguments for SubAgentConfig.

        Returns:
            SubAgent instance.
        """
        config = SubAgentConfig(
            name=kwargs.get("name", "plan"),
            agent_type="plan",
            system_prompt=kwargs.get("system_prompt"),
        )
        return cls(llm_service, config)

    @classmethod
    def create_code(cls, llm_service: Any, **kwargs) -> "SubAgent":
        """Create code subagent with full access filter.

        Args:
            llm_service: LLM service instance.
            **kwargs: Additional arguments for SubAgentConfig.

        Returns:
            SubAgent instance.
        """
        config = SubAgentConfig(
            name=kwargs.get("name", "code"),
            agent_type="code",
            system_prompt=kwargs.get("system_prompt"),
        )
        return cls(llm_service, config)

    @classmethod
    def create_custom(
        cls,
        llm_service: Any,
        tool_filter: ToolFilter,
        **kwargs
    ) -> "SubAgent":
        """Create custom subagent with custom filter.

        Args:
            llm_service: LLM service instance.
            tool_filter: Custom tool filter.
            **kwargs: Additional arguments for SubAgentConfig.

        Returns:
            SubAgent instance.
        """
        config = SubAgentConfig(
            name=kwargs.get("name", "custom"),
            agent_type="custom",
            tool_filter=tool_filter,
            system_prompt=kwargs.get("system_prompt"),
        )
        return cls(llm_service, config)
