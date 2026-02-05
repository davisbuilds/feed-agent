"""Tests for LLM factory behavior."""

from types import ModuleType

import pytest

from src.llm import LLMError, create_client


class _DummyClient:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model


def test_create_client_openai_uses_provider_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Factory should pass provider default model when model is omitted."""
    module = ModuleType("src.llm.openai")
    module.OpenAIClient = _DummyClient
    monkeypatch.setitem(__import__("sys").modules, "src.llm.openai", module)

    client = create_client(provider="openai", api_key="test-key")

    assert isinstance(client, _DummyClient)
    assert client.api_key == "test-key"
    assert client.model == "gpt-4o-mini"


def test_create_client_anthropic_uses_explicit_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Factory should preserve explicitly passed model."""
    module = ModuleType("src.llm.anthropic")
    module.AnthropicClient = _DummyClient
    monkeypatch.setitem(__import__("sys").modules, "src.llm.anthropic", module)

    client = create_client(provider="anthropic", api_key="test-key", model="claude-custom")

    assert isinstance(client, _DummyClient)
    assert client.model == "claude-custom"


def test_create_client_missing_dependency_raises_llm_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Factory should wrap dependency import errors as LLMError."""
    monkeypatch.delitem(__import__("sys").modules, "src.llm.openai", raising=False)

    with pytest.raises(LLMError):
        create_client(provider="openai", api_key="test-key")


def test_create_client_unknown_provider_raises_llm_error() -> None:
    """Factory should reject unsupported provider strings."""
    with pytest.raises(LLMError):
        create_client(provider="unknown", api_key="test-key")  # type: ignore[arg-type]
