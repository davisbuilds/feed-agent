"""Anthropic implementation of the LLM client interface."""

import json
from typing import Any

from anthropic import Anthropic
from pydantic import BaseModel

from .base import LLMError, LLMResponse


class AnthropicClient:
    """Anthropic LLM provider."""

    def __init__(self, api_key: str, model: str):
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def generate(
        self,
        prompt: str,
        system: str,
        response_schema: type[BaseModel],
    ) -> LLMResponse:
        """Generate JSON with Anthropic and normalize the response."""
        schema_json = json.dumps(response_schema.model_json_schema(), indent=2)
        user_prompt = (
            f"{prompt}\n\n"
            "Return valid JSON matching this schema exactly:\n"
            f"{schema_json}"
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                system=system,
                max_tokens=4096,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except Exception as exc:  # pragma: no cover - provider SDK behavior
            raise LLMError(f"Anthropic API call failed: {exc}") from exc

        raw_text = _extract_anthropic_text(response.content)

        try:
            parsed = json.loads(raw_text) if raw_text else {}
        except Exception as exc:
            raise LLMError(f"Anthropic response parsing failed: {exc}") from exc

        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0) if usage else 0
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0) if usage else 0

        return LLMResponse(
            parsed=parsed,
            raw_text=raw_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


def _extract_anthropic_text(blocks: Any) -> str:
    """Extract text content from Anthropic response blocks."""
    if not blocks:
        return ""

    text_parts: list[str] = []
    for block in blocks:
        if isinstance(block, dict):
            if block.get("type") == "text" and isinstance(block.get("text"), str):
                text_parts.append(block["text"])
            continue

        block_type = getattr(block, "type", None)
        block_text = getattr(block, "text", None)
        if block_type == "text" and isinstance(block_text, str):
            text_parts.append(block_text)

    return "\n".join(text_parts)
