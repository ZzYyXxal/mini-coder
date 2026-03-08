"""LangSmith tracing module for mini-coder.

Provides observability integration via LangSmith:
- configure_langsmith: Set up tracing
- get_client: Get LangSmith client
- is_tracing_enabled: Check if tracing is active
- get_trace_url: Get URL for a trace
"""

from .client import (
    configure_langsmith,
    get_client,
    is_tracing_enabled,
    get_trace_url,
)

__all__ = [
    "configure_langsmith",
    "get_client",
    "is_tracing_enabled",
    "get_trace_url",
]