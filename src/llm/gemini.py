"""Google Gemini implementation of the LLM client interface."""

import json

from google import genai
from google.genai import types
from pydantic import BaseModel

from .base import LLMError, LLMResponse


class GeminiClient:
    """Google Gemini LLM provider."""

    def __init__(self, api_key: str, model: str):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def generate(
        self,
        prompt: str,
        system: str,
        response_schema: type[BaseModel],
    ) -> LLMResponse:
        """Generate JSON with Gemini and normalize the response."""
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    http_options=types.HttpOptions(timeout=120_000),
                ),
            )
        except Exception as exc:  # pragma: no cover - provider SDK behavior
            raise LLMError(f"Gemini API call failed: {exc}") from exc

        raw_text = getattr(response, "text", "") or ""

        try:
            if hasattr(response, "parsed") and response.parsed:
                parsed_obj = response.parsed
                if isinstance(parsed_obj, BaseModel):
                    parsed = parsed_obj.model_dump()
                else:
                    parsed = parsed_obj
            elif raw_text:
                parsed = json.loads(raw_text)
            else:
                parsed = {}
        except Exception as exc:
            raise LLMError(f"Gemini response parsing failed: {exc}") from exc

        usage = getattr(response, "usage_metadata", None)
        input_tokens = int(getattr(usage, "prompt_token_count", 0) or 0) if usage else 0
        output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0) if usage else 0

        return LLMResponse(
            parsed=parsed,
            raw_text=raw_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
