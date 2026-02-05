"""OpenAI implementation of the LLM client interface."""

import json
from typing import Any

from openai import OpenAI
from pydantic import BaseModel

from .base import LLMError, LLMResponse


class OpenAIClient:
    """OpenAI LLM provider."""

    def __init__(self, api_key: str, model: str):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def generate(
        self,
        prompt: str,
        system: str,
        response_schema: type[BaseModel],
    ) -> LLMResponse:
        """Generate JSON with OpenAI and normalize the response."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": response_schema.__name__,
                        "schema": response_schema.model_json_schema(),
                    },
                },
            )
        except Exception as exc:  # pragma: no cover - provider SDK behavior
            raise LLMError(f"OpenAI API call failed: {exc}") from exc

        message = response.choices[0].message if response.choices else None
        raw_text = _extract_openai_text(message)

        try:
            parsed = json.loads(raw_text) if raw_text else {}
        except Exception as exc:
            raise LLMError(f"OpenAI response parsing failed: {exc}") from exc

        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0) if usage else 0
        output_tokens = int(getattr(usage, "completion_tokens", 0) or 0) if usage else 0

        return LLMResponse(
            parsed=parsed,
            raw_text=raw_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


def _extract_openai_text(message: Any) -> str:
    """Extract text content from an OpenAI response message."""
    if message is None:
        return ""

    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text" and isinstance(part.get("text"), str):
                    text_parts.append(part["text"])
            else:
                text_value = getattr(part, "text", None)
                if isinstance(text_value, str):
                    text_parts.append(text_value)
        return "\n".join(text_parts)

    return str(content)
