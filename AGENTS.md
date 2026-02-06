# AI Agent Guide

This document is a guide for AI agents working on the Feed Agent project.

## Project Structure

```
feed/
├── config/              # Configuration files (feeds.yaml)
├── src/                 # Application source code
│   ├── analyze/         # Digest generation (Summarizer, DigestBuilder, Prompts)
│   ├── deliver/         # Email delivery (Jinja2 templates, Resend integration)
│   ├── ingest/          # RSS fetching and parsing
│   ├── llm/             # Multi-provider LLM abstraction layer
│   │   ├── base.py      # LLMClient protocol interface
│   │   ├── gemini.py    # Google Gemini provider
│   │   ├── openai.py    # OpenAI provider
│   │   └── anthropic.py # Anthropic provider
│   ├── storage/         # SQLite database (WAL mode)
│   ├── cli.py           # Typer CLI entry point
│   ├── config.py        # Pydantic Settings management
│   ├── logging_config.py
│   └── models.py        # Pydantic data models
├── scripts/             # Utility / automation scripts
├── tests/               # Pytest suite
└── docs/                # Project documentation
```

## Key Commands

The project uses `uv` for dependency management.

- **Run CLI**: `./feed <command>` (or `uv run feed <command>`)
- **Run Tests**: `uv run pytest`
- **Lint**: `uv run ruff check .`
- **Install**: `uv sync` (or `uv sync --extra dev` for dev tools)

## Development Patterns

- **Configuration**: `src.config.get_settings()` — Pydantic-based, reads `.env`.
- **Logging**: `src.logging_config.get_logger(__name__)`.
- **Database**: `src.storage.db.Database` — SQLite with WAL mode.
- **Models**: Pydantic models in `src.models`.
- **LLM access**: `src.llm.create_client(provider, api_key, model)` — factory with lazy imports. Supports `gemini` (default), `openai`, and `anthropic`.

## Current Status (2026-02-05)

The project is fully functional with multi-provider LLM support.

### Completed

- Provider-agnostic LLM abstraction (`src/llm/`) with Gemini, OpenAI, and Anthropic.
- Config migration from `ANTHROPIC_API_KEY` to `LLM_API_KEY` / `LLM_PROVIDER`.
- CLI renamed from `digest` to `feed` with global `--verbose` flag.
- JSON output for `feed status`.
- CLI robustness fixes (exit codes, timeouts, error handling).
- `./feed` wrapper script for simplified invocation.
