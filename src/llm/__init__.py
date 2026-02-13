"""LLM provider factory and shared exports."""

from typing import Literal

from .base import LLMClient, LLMError, LLMResponse
from .retry import RetryClient

Provider = Literal["gemini", "openai", "anthropic"]

PROVIDER_DEFAULTS: dict[Provider, str] = {
    "gemini": "gemini-3-flash-preview",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-20250514",
}


def create_client(
    provider: Provider,
    api_key: str,
    model: str | None = None,
    max_retries: int = 2,
) -> RetryClient:
    """Create an LLM client for the given provider, wrapped with retry logic."""
    if provider not in PROVIDER_DEFAULTS:
        raise LLMError(f"Unknown LLM provider: {provider}")

    resolved_model = model or PROVIDER_DEFAULTS[provider]

    try:
        match provider:
            case "gemini":
                from .gemini import GeminiClient

                inner = GeminiClient(api_key=api_key, model=resolved_model)
            case "openai":
                from .openai import OpenAIClient

                inner = OpenAIClient(api_key=api_key, model=resolved_model)
            case "anthropic":
                from .anthropic import AnthropicClient

                inner = AnthropicClient(api_key=api_key, model=resolved_model)
    except ImportError as exc:
        raise LLMError(
            f"Missing dependency for provider '{provider}'. "
            f"Install the '{provider}' extra to continue."
        ) from exc

    return RetryClient(inner, max_retries=max_retries)


__all__ = [
    "LLMClient",
    "LLMError",
    "LLMResponse",
    "PROVIDER_DEFAULTS",
    "Provider",
    "RetryClient",
    "create_client",
]
