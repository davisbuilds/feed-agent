# Architecture

## High-Level Flow

1. **Ingest**: RSS feeds are fetched concurrently via `httpx` and parsed with `feedparser`.
2. **Analyze**: Pending articles are summarized by the LLM client (Gemini, OpenAI, or Anthropic) with structured output.
3. **Deliver**: The digest is rendered to terminal (Rich/text/JSON) or sent via email (Resend API + Jinja2 templates).

The full pipeline runs as `feed run`. Individual stages can be invoked separately via `feed ingest`, `feed analyze`, and `feed send`.

## CLI Layer

`src/cli.py` uses Typer + Rich for 10 commands:

```text
init, run, schedule, ingest, analyze, send, test, status, config, cache
```

Global options: `--verbose`, `--version`.

## LLM Abstraction

Provider-agnostic design in `src/llm/`:

- `base.py`: `LLMClient` protocol interface + `LLMResponse` dataclass.
- `gemini.py`, `openai.py`, `anthropic.py`: Provider implementations with structured JSON output.
- `retry.py`: `RetryClient` wrapper with exponential backoff (retryable: timeouts, 429, 5xx).
- `__init__.py`: Factory `create_client(provider, api_key, model)` with lazy imports and per-provider defaults.

Provider defaults:

| Provider | Default Model |
|----------|--------------|
| `gemini` | `gemini-3-flash-preview` |
| `openai` | `gpt-4o-mini` |
| `anthropic` | `claude-sonnet-4-20250514` |

## Storage Layer

SQLite with WAL mode in `src/storage/`:

### Tables

| Table | Purpose |
|-------|---------|
| `articles` | Fetched articles with status, summary, takeaways, and metadata |
| `feed_status` | Per-feed health tracking (last checked, consecutive failures) |
| `digests` | Generated digest records with send status |
| `cache` | LLM response cache with TTL and lazy expiration |

### Cache

`CacheStore` in `src/storage/cache.py`:

- SHA256 keys from `article_id:model`.
- 7-day default TTL.
- Lazy expiration on write.
- `--no-cache` flag bypasses cache for fresh summaries.

## Configuration

`src/config.py` uses Pydantic Settings with two-tier env resolution:

1. `~/.config/feed/config.env` — user-level XDG config.
2. `.env` in working directory — project-level override (higher priority).

Feed definitions loaded from `settings.config_dir / "feeds.yaml"` (YAML with per-feed URL, category, priority).

## Scheduler

`src/scheduler.py` supports two backends:

- **cron**: Standard crontab entries.
- **launchd**: macOS plist generation.

Configured via `feed schedule --backend auto|cron|launchd --frequency daily|weekly --time HH:MM`.

## Delivery

`src/deliver/`:

- `email.py`: `EmailSender` using Resend API.
- `renderer.py`: `EmailRenderer` with Jinja2 HTML + plain text templates.

## Directory Map

```text
src/analyze/              # Summarizer, digest builder, prompts
src/deliver/              # Email sender + Jinja2 renderer
src/ingest/               # Feed fetcher + parser
src/llm/                  # Provider clients (3) + retry wrapper
src/storage/              # SQLite DB + response cache
src/cli.py                # Typer CLI entry point
src/config.py             # Pydantic Settings + XDG support
src/models.py             # Shared Pydantic models
src/scheduler.py          # Cron/launchd scheduling
scripts/                  # Utility scripts (healthcheck, preview, setup)
tests/                    # Pytest suite (8 files)
config/                   # Default feeds.yaml
```
