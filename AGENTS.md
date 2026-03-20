# AI Agent Guide

Guidance for coding agents working in this repository.

Newsletter intelligence CLI: fetches RSS feeds, generates AI-powered digests, and delivers them via email.

## Project Structure

```
feed/
├── config/              # Configuration files (feeds.yaml)
├── src/                 # Application source code
│   ├── analyze/         # Digest generation (Summarizer, DigestBuilder, Prompts)
│   ├── deliver/         # Email delivery (Jinja2 templates, Resend integration)
│   ├── ingest/          # RSS fetching, parsing, and feed testing
│   ├── llm/             # Multi-provider LLM abstraction layer
│   │   ├── base.py      # LLMClient protocol interface
│   │   ├── gemini.py    # Google Gemini provider
│   │   ├── openai.py    # OpenAI provider
│   │   ├── anthropic.py # Anthropic provider
│   │   └── retry.py     # RetryClient with exponential backoff
│   ├── storage/         # SQLite database + cache store (WAL mode)
│   │   ├── db.py        # Main article database
│   │   └── cache.py     # LLM response cache (TTL + lazy expiration)
│   ├── cli.py           # Typer CLI entry point
│   ├── config.py        # Pydantic Settings management
│   ├── logging_config.py
│   └── models.py        # Pydantic data models
├── scripts/             # Utility / automation scripts
├── tests/               # Pytest suite
└── docs/                # Project documentation
```

## Key Files Reference

| Purpose | Location |
|---------|----------|
| CLI entry point (Typer) | `src/cli.py` |
| Pydantic Settings (XDG + `.env`) | `src/config.py` |
| Pydantic data models | `src/models.py` |
| Feed management | `src/ingest/feeds.py` |
| RSS/XML parsing | `src/ingest/parser.py` |
| Article summarization | `src/analyze/summarizer.py` |
| Digest assembly | `src/analyze/digest_builder.py` |
| LLM prompts | `src/analyze/prompts.py` |
| LLM client protocol | `src/llm/base.py` |
| Retry wrapper (exponential backoff) | `src/llm/retry.py` |
| Email delivery (Resend) | `src/deliver/email.py` |
| Email template rendering (Jinja2) | `src/deliver/renderer.py` |
| SQLite database (WAL mode) | `src/storage/db.py` |
| LLM response cache (TTL) | `src/storage/cache.py` |
| Feed definitions | `config/feeds.yaml` |
| CI config | `.github/workflows/ci.yml` |
| Environment template | `.env.example` |

## Key Commands

The project uses `uv` for dependency management.

- **Run CLI**: `./feed <command>` (or `uv run feed <command>`)
- **Run Tests**: `uv run python -m pytest` (NOT `uv run pytest` — that fails with "No such file or directory")
- **Lint**: `uv run ruff check .`
- **Install**: `uv sync` (or `uv sync --extra dev` for dev tools)

## Configuration & XDG Convention

Settings are loaded via Pydantic Settings from two env-file locations (higher priority wins):

1. `~/.config/feed/config.env` — user-level XDG config (created by `feed init`)
2. `.env` in the working directory — project-level override

The XDG path is defined in `src.config.XDG_CONFIG_PATH` (`~/.config/feed/`). The `feed init` wizard writes `config.env` and copies `feeds.yaml` into this directory, so users can run `feed` from any location.

### Runtime Resolution Notes

- Do not assume `config/feeds.yaml` is always active.
- Active feed path is `settings.config_dir / "feeds.yaml"` and `settings.config_dir` is driven by env resolution.
- Env precedence is: `~/.config/feed/config.env` then `.env` in current working directory (cwd `.env` overrides XDG).
- Before editing feed configuration for a user, verify active paths with `feed config` (or `feed config --json` for machine-readable output).
- When users ask to "standardize" feeds, compare and sync both `config/feeds.yaml` and `~/.config/feed/feeds.yaml` as requested.

Key config variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | `gemini`, `openai`, or `anthropic` | `gemini` |
| `LLM_API_KEY` | API key for the chosen provider | (required) |
| `LLM_MODEL` | Model override | per-provider default |
| `RESEND_API_KEY` | Resend email API key | (required) |
| `EMAIL_FROM` | Sender email address | (required) |
| `EMAIL_TO` | Recipient email address | (required) |
| `CONFIG_DIR` | Path to feeds.yaml directory | `config/` |
| `DATA_DIR` | Path to SQLite data directory | `data/` |

## Development Patterns

- **Configuration**: `src.config.get_settings()` — Pydantic-based, reads XDG and `.env`.
- **Logging**: `src.logging_config.get_logger(__name__)`.
- **Database**: `src.storage.db.Database` — SQLite with WAL mode.
- **Cache**: `src.storage.cache.CacheStore` — SQLite-backed response cache with TTL.
- **Models**: Pydantic models in `src.models`.
- **LLM access**: `src.llm.create_client(provider, api_key, model)` — factory with lazy imports, wrapped in `RetryClient` with exponential backoff. Supports `gemini` (default), `openai`, and `anthropic`.

## Coding Conventions

Ruff is configured with strict rules. Watch for these common issues:

- **`datetime.UTC`** not `timezone.utc` — ruff UP017 enforces the modern alias.
- **`collections.abc.Generator`** not `typing.Generator` — ruff UP035 enforces modern imports.
- **Forward-ref type hints**: Use `from __future__ import annotations` + `TYPE_CHECKING` block instead of string annotations like `"Foo | None"` — string annotations trigger ruff F821 (undefined name).
- **Import ordering**: `from collections.abc` sorts before `from contextlib` — ruff I001 enforces isort-style ordering.

## Testing

**Pre-push check**: Before pushing updates to the remote, run the full CI workflow locally with `uv run ruff check .` and `uv run python -m pytest`.

**TDD**: Use red/green TDD for new features and major changes.

## CLI Overview

Commands: `init`, `run`, `schedule`, `ingest`, `test`, `analyze`, `send`, `status`, `config`, `cache`. Run `feed --help` or `feed <command> --help` for options. See `docs/system/FEATURES.md` for a detailed reference.

Notable flags:

- `--copy` on `run` and `analyze`: copies digest as markdown to the system clipboard (uses `pbcopy` on macOS, `xclip`/`xsel` on Linux). Works independently of `--send` and `--format`.
