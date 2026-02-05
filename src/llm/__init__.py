"""LLM provider factory and shared exports."""

from typing import Literal

from .base import LLMClient, LLMError, LLMResponse

Provider = Literal["gemini", "openai", "anthropic"]

PROVIDER_DEFAULTS: dict[Provider, str] = {
    "gemini": "gemini-3-flash-preview",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-20250514",
}


def create_client(provider: Provider, api_key: str, model: str | None = None) -> LLMClient:
    """Create an LLM client for the given provider."""
    if provider not in PROVIDER_DEFAULTS:
        raise LLMError(f"Unknown LLM provider: {provider}")

    resolved_model = model or PROVIDER_DEFAULTS[provider]

    try:
        match provider:
            case "gemini":
                from .gemini import GeminiClient

                return GeminiClient(api_key=api_key, model=resolved_model)
            case "openai":
                from .openai import OpenAIClient

                return OpenAIClient(api_key=api_key, model=resolved_model)
            case "anthropic":
                from .anthropic import AnthropicClient

                return AnthropicClient(api_key=api_key, model=resolved_model)
    except ImportError as exc:
        raise LLMError(
            f"Missing dependency for provider '{provider}'. "
            f"Install the '{provider}' extra to continue."
        ) from exc


__all__ = [
    "LLMClient",
    "LLMError",
    "LLMResponse",
    "PROVIDER_DEFAULTS",
    "Provider",
    "create_client",
]
