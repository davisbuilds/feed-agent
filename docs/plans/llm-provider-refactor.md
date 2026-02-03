# LLM Provider Abstraction Refactor

## Problem

The codebase is hardwired to Google Gemini via the `google-genai` SDK. Swapping to
OpenAI or Anthropic requires changes across 8+ files spanning config, core logic,
scripts, and tests. There are also leftover artifacts from an earlier Anthropic
integration (`.env.example` references `ANTHROPIC_API_KEY`, `verify_setup.py`
checks `import anthropic` and `settings.claude_model`) that conflict with the
current Gemini implementation.

### Current LLM touchpoints (exhaustive)

| File | Lines | What it does |
|------|-------|--------------|
| `src/config.py` | 25, 41 | `google_api_key` field, `gemini_model` default |
| `src/analyze/summarizer.py` | 11-12, 56 | `from google import genai`, `genai.Client()` |
| `src/analyze/summarizer.py` | 85-93 | `client.models.generate_content()` with `types.GenerateContentConfig` |
| `src/analyze/summarizer.py` | 97-105 | Response parsing: `response.parsed`, `response.text` |
| `src/analyze/summarizer.py` | 109-110 | Token counting: `response.usage_metadata.prompt_token_count` |
| `src/analyze/digest_builder.py` | 10-11, 51 | Same `genai` imports and client init |
| `src/analyze/digest_builder.py` | 122-135 | `generate_content()` for category synthesis |
| `src/analyze/digest_builder.py` | 190-201 | `generate_content()` for overall synthesis |
| `src/analyze/__init__.py` | 34-36 | Cost constants (Anthropic Sonnet pricing, not Gemini) |
| `src/analyze/__init__.py` | 89-90 | `Summarizer()` / `DigestBuilder()` construction |
| `src/cli.py` | 375-379, 389 | Displays `google_api_key` and `gemini_model` in `config` command |
| `scripts/healthcheck.py` | 43-44 | Checks `settings.google_api_key` |
| `scripts/list_models.py` | 1, 6 | `genai.Client()` to list available models |
| `scripts/verify_setup.py` | 26-29, 67 | Checks `import anthropic`, references `settings.claude_model` (stale) |
| `.env.example` | 2 | `ANTHROPIC_API_KEY=sk-ant-...` (stale) |
| `tests/test_analyze.py` | 33, 62, 99 | Mocks `genai.Client` by import path |

### Provider-specific API differences that matter

| Concern | Gemini (`google-genai`) | OpenAI | Anthropic |
|---------|------------------------|--------|-----------|
| Client init | `genai.Client(api_key=)` | `openai.OpenAI(api_key=)` | `anthropic.Anthropic(api_key=)` |
| Generate | `client.models.generate_content(model=, contents=, config=)` | `client.chat.completions.create(model=, messages=)` | `client.messages.create(model=, messages=, system=)` |
| System prompt | `config.system_instruction` (string) | `messages[0].role="system"` | `system=` top-level param |
| Structured output | `response_mime_type="application/json"` + `response_schema=PydanticModel` | `response_format={"type":"json_schema", "json_schema":...}` | `tools` with JSON schema or prefill trick |
| Response text | `response.text` or `response.parsed` | `response.choices[0].message.content` | `response.content[0].text` |
| Token usage | `response.usage_metadata.prompt_token_count` / `.candidates_token_count` | `response.usage.prompt_tokens` / `.completion_tokens` | `response.usage.input_tokens` / `.output_tokens` |

---

## Design

### Core abstraction: `LLMClient` protocol

A single protocol class that each provider implements. This is the only contract
the rest of the codebase depends on.

```python
# src/llm/base.py

from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel


@dataclass
class LLMResponse:
    """Provider-agnostic response from an LLM call."""
    parsed: dict            # The parsed JSON response
    raw_text: str           # Raw text fallback
    input_tokens: int       # Tokens in the prompt
    output_tokens: int      # Tokens in the completion


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
```

This captures exactly what `summarizer.py` and `digest_builder.py` need:
a prompt, a system instruction, a Pydantic schema, and back comes parsed JSON
plus token counts. Nothing else leaks through.

### Provider implementations

```
src/llm/
    __init__.py          # re-exports create_client()
    base.py              # LLMResponse dataclass + LLMClient protocol
    gemini.py            # GeminiClient(LLMClient)
    openai.py            # OpenAIClient(LLMClient)
    anthropic.py         # AnthropicClient(LLMClient)
```

Each file is ~40-60 lines. The provider-specific parsing, token counting, and
structured output handling lives entirely inside its own module.

Example -- `gemini.py`:

```python
# src/llm/gemini.py

import json
from google import genai
from google.genai import types
from pydantic import BaseModel

from .base import LLMClient, LLMResponse


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
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_schema=response_schema,
            ),
        )

        # Parse response
        if hasattr(response, "parsed") and response.parsed:
            obj = response.parsed
            parsed = obj.model_dump() if isinstance(obj, BaseModel) else obj
        else:
            parsed = json.loads(response.text)

        # Token counts
        usage = response.usage_metadata
        input_tokens = (usage.prompt_token_count or 0) if usage else 0
        output_tokens = (usage.candidates_token_count or 0) if usage else 0

        return LLMResponse(
            parsed=parsed,
            raw_text=response.text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
```

`openai.py` and `anthropic.py` follow the same shape but use their respective
SDK calls and response formats.

### Factory function

```python
# src/llm/__init__.py

from .base import LLMClient, LLMResponse
from typing import Literal

Provider = Literal["gemini", "openai", "anthropic"]

def create_client(provider: Provider, api_key: str, model: str) -> LLMClient:
    """Create an LLM client for the given provider."""
    match provider:
        case "gemini":
            from .gemini import GeminiClient
            return GeminiClient(api_key=api_key, model=model)
        case "openai":
            from .openai import OpenAIClient
            return OpenAIClient(api_key=api_key, model=model)
        case "anthropic":
            from .anthropic import AnthropicClient
            return AnthropicClient(api_key=api_key, model=model)
        case _:
            raise ValueError(f"Unknown LLM provider: {provider}")
```

Lazy imports so you only need the SDK for the provider you're using.

### Config changes

```python
# src/config.py -- replace Gemini-specific fields

class Settings(BaseSettings):
    # LLM Provider
    llm_provider: Literal["gemini", "openai", "anthropic"] = Field(
        default="gemini",
        description="LLM provider to use",
    )
    llm_api_key: str = Field(
        ...,
        min_length=1,
        description="API key for the configured LLM provider",
    )
    llm_model: str = Field(
        default="gemini-2.0-flash",
        description="Model name for the configured LLM provider",
    )

    # ... rest unchanged ...
```

This replaces the current `google_api_key` and `gemini_model` fields. The env
vars become `LLM_PROVIDER`, `LLM_API_KEY`, and `LLM_MODEL`. For backwards
compatibility during migration, we can keep `GOOGLE_API_KEY` as an alias for
`LLM_API_KEY` with a deprecation warning (see step 6 below), but this is
optional.

### Default models per provider

The `llm_model` default in config only covers Gemini. Each provider module
should define its own sensible default so the user can just set provider + key:

```python
PROVIDER_DEFAULTS = {
    "gemini": "gemini-2.0-flash",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-20250514",
}
```

The config validator can fill in the default based on `llm_provider` if
`llm_model` isn't explicitly set.

---

## Implementation Steps

### Step 1: Create `src/llm/` module with `base.py`

**Files:** new `src/llm/__init__.py`, new `src/llm/base.py`

Define `LLMResponse` dataclass and `LLMClient` protocol. No external
dependencies. This is the contract everything else codes against.

### Step 2: Extract `GeminiClient` into `src/llm/gemini.py`

**Files:** new `src/llm/gemini.py`

Move the Gemini-specific code out of `summarizer.py` and `digest_builder.py`
into a single provider module. The duplicated response-parsing logic
(`hasattr(response, "parsed")...`) that currently exists in both files
gets consolidated here.

### Step 3: Refactor `Summarizer` and `DigestBuilder` to use `LLMClient`

**Files:** `src/analyze/summarizer.py`, `src/analyze/digest_builder.py`

Replace direct `genai` usage with the `LLMClient` protocol:

```python
# Before (summarizer.py)
from google import genai
from google.genai import types

class Summarizer:
    def __init__(self, api_key=None, model=None):
        self.client = genai.Client(api_key=api_key)
        self.model_name = model

    def summarize_article(self, article):
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(...)
        )
        # ... 15 lines of response parsing ...

# After (summarizer.py)
from src.llm import LLMClient

class Summarizer:
    def __init__(self, client: LLMClient | None = None):
        if client is None:
            settings = get_settings()
            client = create_client(
                provider=settings.llm_provider,
                api_key=settings.llm_api_key,
                model=settings.llm_model,
            )
        self.client = client

    def summarize_article(self, article):
        response = self.client.generate(
            prompt=prompt,
            system=ARTICLE_SUMMARY_SYSTEM,
            response_schema=ArticleSummaryResponse,
        )
        # response.parsed is already a dict -- no parsing logic needed
```

Key changes:
- Constructor accepts an `LLMClient` instead of `api_key` + `model` strings
- All provider-specific code removed (no `genai` imports, no `types`, no
  response parsing)
- The duplicated `hasattr(response, "parsed")` blocks disappear entirely
- Same change applied to `DigestBuilder`

### Step 4: Update config

**Files:** `src/config.py`, `.env.example`

- Replace `google_api_key` + `gemini_model` with `llm_provider` + `llm_api_key` + `llm_model`
- Update `.env.example` to show the new variable names
- Add per-provider model defaults via a validator

### Step 5: Update CLI and scripts

**Files:** `src/cli.py`, `scripts/healthcheck.py`, `scripts/list_models.py`, `scripts/verify_setup.py`

- `cli.py` `config` command: display `llm_provider`, `llm_api_key`, `llm_model`
  instead of `google_api_key`, `gemini_model`
- `healthcheck.py`: check `settings.llm_api_key` instead of `settings.google_api_key`
- `list_models.py`: use the factory to create the right client, or note that
  model listing is provider-specific (Gemini supports it, others don't in the
  same way)
- `verify_setup.py`: fix stale `import anthropic` check and `settings.claude_model`
  reference -- check the correct provider SDK

### Step 6: Update `src/analyze/__init__.py` cost estimation

**Files:** `src/analyze/__init__.py`

The current cost constants reference Anthropic Sonnet pricing despite using
Gemini. Replace with a per-provider cost table:

```python
COST_PER_1K_TOKENS = {
    "gemini":    {"input": 0.000075, "output": 0.00030},   # Gemini 2.0 Flash
    "openai":    {"input": 0.000150, "output": 0.00060},   # GPT-4o-mini
    "anthropic": {"input": 0.003000, "output": 0.01500},   # Claude Sonnet
}
```

### Step 7: Add `OpenAIClient` and `AnthropicClient`

**Files:** new `src/llm/openai.py`, new `src/llm/anthropic.py`

Implement the two additional providers. Each is ~40-60 lines following the
same pattern as `GeminiClient`. The main differences:

**OpenAI structured output:**
```python
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
parsed = json.loads(response.choices[0].message.content)
```

**Anthropic structured output:**
```python
response = self.client.messages.create(
    model=self.model,
    system=system,
    max_tokens=4096,
    messages=[{"role": "user", "content": prompt}],
)
parsed = json.loads(response.content[0].text)
```

Note: Anthropic doesn't have native `response_format` like OpenAI/Gemini.
The prompt templates already include "Respond with JSON in this exact format"
instructions, which works reliably with Claude. Alternatively, tool use can
enforce schema compliance. Either approach is fine; the prompt-based approach
is simpler and matches the existing prompt design.

### Step 8: Update dependencies

**Files:** `pyproject.toml`

Make provider SDKs optional:

```toml
[project.optional-dependencies]
gemini = ["google-genai>=0.3.0"]
openai = ["openai>=1.0.0"]
anthropic = ["anthropic>=0.40.0"]
```

Keep `google-genai` in the default `dependencies` for backwards compatibility,
or move all three to optional and document `uv pip install feed[gemini]` etc.

### Step 9: Update tests

**Files:** `tests/test_analyze.py`

Tests currently mock `genai.Client` by import path. After refactor, they
should inject a mock `LLMClient` directly -- no patching needed:

```python
# Before
@patch("src.analyze.summarizer.genai.Client")
def test_summarize_article_success(self, mock_client_cls, sample_article):
    mock_response = Mock()
    mock_response.parsed = {...}
    mock_response.usage_metadata.prompt_token_count = 100
    mock_client_cls.return_value.models.generate_content.return_value = mock_response
    summarizer = Summarizer(api_key="test-key", model="test-model")

# After
def test_summarize_article_success(self, sample_article):
    mock_client = Mock(spec=LLMClient)
    mock_client.generate.return_value = LLMResponse(
        parsed={"summary": "Test summary", "key_takeaways": ["insight1"], ...},
        raw_text="...",
        input_tokens=100,
        output_tokens=50,
    )
    summarizer = Summarizer(client=mock_client)
```

This is cleaner: no `@patch` decorators, no knowledge of provider internals,
and the tests verify behavior rather than implementation.

### Step 10: Clean up stale references

**Files:** `scripts/verify_setup.py`, `.env.example`, `src/analyze/prompts.py`

- Remove `import anthropic` check from `verify_setup.py`; replace with a check
  for the configured provider's SDK
- Fix `.env.example` to show `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`
- `prompts.py` docstring says "Claude interactions" -- update to be generic

---

## File change summary

| File | Change type | Scope |
|------|-------------|-------|
| `src/llm/__init__.py` | **New** | Factory function, re-exports |
| `src/llm/base.py` | **New** | `LLMResponse` + `LLMClient` protocol |
| `src/llm/gemini.py` | **New** | `GeminiClient` implementation |
| `src/llm/openai.py` | **New** | `OpenAIClient` implementation |
| `src/llm/anthropic.py` | **New** | `AnthropicClient` implementation |
| `src/config.py` | **Modify** | Replace `google_api_key`/`gemini_model` with generic fields |
| `src/analyze/summarizer.py` | **Modify** | Accept `LLMClient`, remove all `genai` imports |
| `src/analyze/digest_builder.py` | **Modify** | Same as summarizer |
| `src/analyze/__init__.py` | **Modify** | Per-provider cost table, construct via factory |
| `src/analyze/prompts.py` | **Modify** | Docstring only |
| `src/cli.py` | **Modify** | Display generic provider/model in `config` command |
| `scripts/healthcheck.py` | **Modify** | Check `llm_api_key` instead of `google_api_key` |
| `scripts/list_models.py` | **Modify** | Use factory or make provider-aware |
| `scripts/verify_setup.py` | **Modify** | Fix stale anthropic/claude references |
| `.env.example` | **Modify** | New variable names |
| `pyproject.toml` | **Modify** | Optional provider dependencies |
| `tests/test_analyze.py` | **Modify** | Inject `LLMClient` mock instead of patching `genai` |

**New files:** 5 (all in `src/llm/`)
**Modified files:** 12
**Deleted files:** 0

---

## Migration path for existing users

1. `LLM_API_KEY` replaces `GOOGLE_API_KEY`. If desired, the config validator
   can check for `GOOGLE_API_KEY` as a fallback and log a deprecation warning.
2. `LLM_PROVIDER` defaults to `"gemini"` so existing Gemini users only need
   to rename one env var.
3. `LLM_MODEL` defaults per-provider, so it can be omitted if the user is
   happy with the default.

Minimal migration for an existing Gemini user:
```bash
# Before
GOOGLE_API_KEY=AIza...

# After
LLM_API_KEY=AIza...
# LLM_PROVIDER=gemini  (default, can omit)
# LLM_MODEL=gemini-2.0-flash  (default, can omit)
```

To switch to Anthropic:
```bash
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-...
# LLM_MODEL=claude-sonnet-4-20250514  (default for anthropic, can omit)
```

---

## Risks and tradeoffs

**Structured output fidelity varies by provider.** Gemini and OpenAI have
native JSON schema enforcement. Anthropic relies on prompt instructions (or
tool use as an alternative). The prompt templates already ask for JSON, so
this works in practice, but schema violations are possible with Anthropic and
would need to be handled in the `AnthropicClient.generate()` method (e.g.,
retry or raise).

**Provider-specific features are lost.** Gemini's `response.parsed` auto-
deserializes into Pydantic models. OpenAI's structured outputs have refusal
detection. These niceties get absorbed into each provider module and aren't
exposed through the generic `LLMResponse`. This is acceptable since the
callers only need a parsed dict.

**`list_models.py` is inherently provider-specific.** Each SDK has a different
model listing API (or none at all). This script could dispatch per-provider,
or just be documented as Gemini-only.

**Adding a new provider** requires writing one ~50-line file in `src/llm/`,
adding it to the factory `match` statement, and adding default model/cost
entries. No changes to summarizer, digest builder, config schema, or tests.
