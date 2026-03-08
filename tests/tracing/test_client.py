"""Tests for LangSmith tracing client.

TDD tests for tracing configuration and client setup.
"""
import pytest
import os


class TestTracingConfig:
    """Tests for tracing configuration."""

    def test_configure_langsmith_sets_env_vars(self):
        """Should set LANGCHAIN_TRACING_V2 and LANGCHAIN_PROJECT."""
        from mini_coder.tracing.client import configure_langsmith

        # Clear any existing values
        os.environ.pop("LANGCHAIN_TRACING_V2", None)
        os.environ.pop("LANGCHAIN_PROJECT", None)

        configure_langsmith(project_name="test-project")

        assert os.environ.get("LANGCHAIN_TRACING_V2") == "true"
        assert os.environ.get("LANGCHAIN_PROJECT") == "test-project"

    def test_default_project_name(self):
        """Should use 'mini-coder' as default project name."""
        from mini_coder.tracing.client import configure_langsmith

        os.environ.pop("LANGCHAIN_PROJECT", None)

        configure_langsmith()

        assert os.environ.get("LANGCHAIN_PROJECT") == "mini-coder"


class TestTracingClient:
    """Tests for LangSmith client."""

    def test_get_client_returns_client(self):
        """Should return a LangSmith Client instance."""
        from mini_coder.tracing.client import get_client
        from langsmith import Client

        client = get_client()

        assert isinstance(client, Client)

    def test_is_tracing_enabled(self):
        """Should check if tracing is enabled."""
        from mini_coder.tracing.client import is_tracing_enabled

        # When not configured
        os.environ.pop("LANGCHAIN_TRACING_V2", None)
        assert is_tracing_enabled() is False

        # When configured
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        assert is_tracing_enabled() is True