# AGENTS.md

`feed` is a newsletter intelligence CLI that fetches RSS feeds, generates AI-powered digests, and delivers them via email/terminal.

## Documentation Map

- `docs/system/ARCHITECTURE.md` — pipeline flow, CLI layer, LLM abstraction (provider defaults), storage tables, cache, scheduler backends, directory map.
- `docs/system/FEATURES.md` — full CLI command reference, config variables, ingestion/analysis/delivery features, scheduling, cache.
- `docs/system/OPERATIONS.md` — local dev, full command list (incl. the `uv run python -m pytest` form), env vars, XDG paths, scripts catalog, data files.
- `docs/project/ROADMAP.md` — shipped highlights and pointers to active plans under `docs/plans/`.
- `docs/project/GIT_HISTORY_POLICY.md` — history conventions.

## Quickstart

```bash
uv sync --extra dev
./feed init        # interactive setup
./feed run         # full pipeline
```

## Runtime Configuration Gotchas

Settings load via Pydantic Settings from two env-file locations (cwd `.env` overrides XDG):

1. `~/.config/feed/config.env` — user-level XDG config (created by `feed init`).
2. `.env` in current working directory — project-level override.

The `feed init` wizard writes `config.env` and copies `feeds.yaml` into the XDG dir, so users can run `feed` from any location.

- **Do not assume `config/feeds.yaml` is the active feed file.** Active path is `settings.config_dir / "feeds.yaml"` and `settings.config_dir` is driven by env resolution.
- Before editing feed configuration for a user, verify active paths with `feed config` (or `feed config --json` for machine-readable output).
- When users ask to "standardize" feeds, compare and sync both `config/feeds.yaml` and `~/.config/feed/feeds.yaml` as requested — neither is automatically authoritative.
- **Run tests with `uv run python -m pytest`**, not `uv run pytest` (the latter fails with "No such file or directory").

## Testing

- **Pre-push** (matches CI): `uv run ruff check .` and `uv run python -m pytest`.
- **TDD**: red/green for new features and major changes.

## Conventions Enforced Elsewhere

Ruff handles modern-Python style: `datetime.UTC` over `timezone.utc` (UP017), `collections.abc` imports (UP035), import ordering (I001), forward-ref hints via `from __future__ import annotations` + `TYPE_CHECKING`. Don't restate these here — fix any violations the linter flags.
