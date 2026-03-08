"""LangSmith tracing client for mini-coder.

This module provides LangSmith integration for observability:
- Full request tracing
- Token usage metrics
- Latency tracking
- Feedback collection
"""
import os
from typing import Optional

from langsmith import Client

# Global client instance
_client: Optional[Client] = None


def configure_langsmith(project_name: str = "mini-coder") -> Client:
    """Configure LangSmith tracing.

    Sets environment variables and initializes the LangSmith client.
    The LANGCHAIN_API_KEY should be set in the environment.

    Args:
        project_name: LangSmith project name (default: "mini-coder")

    Returns:
        LangSmith Client instance
    """
    global _client

    # Enable tracing
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = project_name

    # Initialize client
    _client = Client()

    return _client


def get_client() -> Client:
    """Get the LangSmith client instance.

    If not already configured, configures with default settings.

    Returns:
        LangSmith Client instance
    """
    global _client

    if _client is None:
        _client = configure_langsmith()

    return _client


def is_tracing_enabled() -> bool:
    """Check if LangSmith tracing is enabled.

    Returns:
        True if LANGCHAIN_TRACING_V2 is set to "true"
    """
    return os.environ.get("LANGCHAIN_TRACING_V2") == "true"


def get_trace_url(run_id: str, project_name: str = "mini-coder") -> str:
    """Get the LangSmith trace URL for a run.

    Args:
        run_id: The run ID from LangSmith
        project_name: Project name (default: "mini-coder")

    Returns:
        URL to view the trace in LangSmith
    """
    return f"https://smith.langchain.com/o/default/projects/p/{project_name}/r/{run_id}"