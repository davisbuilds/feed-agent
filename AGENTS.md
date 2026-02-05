# AI Agent Guide

This document is a guide for AI agents working on the Feed Agent project.

## Project Structure

```bash
substack-digest/
├── config/             # Configuration files (feeds.yaml)
├── src/                # Application source code
│   ├── analyze/        # Digest generation logic (Prompts, Summarizer, Builder)
│   ├── deliver/        # Email delivery (Jinja2 templates, Resend integration)
│   ├── ingest/         # RSS fetching and parsing
│   ├── storage/        # Database models and access
│   ├── cli.py          # Main CLI entry point
│   ├── config.py       # Settings management (Pydantic)
│   ├── logging_config.py # Logger setup
│   └── models.py       # Data models (Pydantic)
├── scripts/            # Automation scripts
├── tests/              # Pytest suite
└── docs/               # Project documentation
```

## Key Commands

The project uses `uv` for dependency management.

- **Run CLI**: `uv run feed`
- **Run Tests**: `uv run pytest`
- **Lint/Format**: `uv run ruff check .`
- **Install**: `uv sync` (or `uv pip install -e .`)

## Development Patterns

- **Configuration**: Use `src.config.get_settings()` to access environment variables.
- **Logging**: Use `src.logging_config.get_logger(__name__)`.
- **Database**: Use `src.storage.db.Database` for all SQLite (WAL mode) access.
- **Models**: All data structures are Pydantic models in `src.models`.

## Current Status (2026-01-25)

The project is fully functional. The current active phase is **Phase 6: Refactor**, specifically switching the LLM provider from Anthropic to Google Gemini.

### Recent Changes

- CLI renamed from `digest` to `feed`.
- Global verbose flag (`-v`) implemented.
- JSON output added to `feed status`.
