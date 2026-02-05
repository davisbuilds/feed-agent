"""Provider-agnostic LLM interface and shared types."""

from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel


class LLMError(Exception):
    """Raised when an LLM provider call fails."""


@dataclass
class LLMResponse:
    """Provider-agnostic response from an LLM call."""

    parsed: dict[str, Any]
    raw_text: str
    input_tokens: int
    output_tokens: int


class LLMClient(Protocol):
    """Protocol that all LLM providers must implement."""

    def generate(
        self,
        prompt: str,
        system: str,
        response_schema: type[BaseModel],
    ) -> LLMResponse:
        """Generate a structured JSON response."""
        ...
