# Operations

## Local Development

```bash
uv sync
./feed <command>
```

Or equivalently: `uv run feed <command>`.

## Useful Commands

```bash
uv sync                          # Install dependencies
uv sync --extra dev              # Install with dev tools
./feed init                      # Interactive setup wizard
./feed run                       # Full pipeline (terminal output)
./feed run --send                # Full pipeline (email delivery)
uv run python -m pytest          # Run tests (NOT uv run pytest)
uv run ruff check .              # Lint
```

## CI

Workflow: `.github/workflows/ci.yml`

Triggers:

- Pull requests to `main`
- Pushes to `main`

Jobs run in parallel:

- Lint: `uv run ruff check` (on actively maintained paths).
- Test: `uv run python -m pytest -v`.

CI runtime details:

- Python 3.12
- uv with `uv sync --extra dev`

## Environment Variables

### Required

| Variable | Used For |
|----------|----------|
| `LLM_API_KEY` | LLM provider authentication |
| `RESEND_API_KEY` | Email delivery via Resend |
| `EMAIL_FROM` | Sender email address |
| `EMAIL_TO` | Recipient email address |

### Optional

| Variable | Default | Used For |
|----------|---------|----------|
| `LLM_PROVIDER` | `gemini` | Provider selection (`gemini`, `openai`, `anthropic`) |
| `LLM_MODEL` | per-provider | Model override |
| `CONFIG_DIR` | `config/` | Path to `feeds.yaml` directory |
| `DATA_DIR` | `data/` | SQLite data directory |
| `DIGEST_HOUR` | `7` | Hour for scheduled digests (0-23) |
| `DIGEST_TIMEZONE` | `America/New_York` | Timezone for scheduling |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## XDG Config Paths

- User-level config: `~/.config/feed/config.env` (created by `feed init`).
- User-level feeds: `~/.config/feed/feeds.yaml`.
- Project `.env` overrides XDG config.
- Run `feed config` to see active paths.

## Scripts

Utility scripts in `scripts/`:

| Script | Purpose |
|--------|---------|
| `healthcheck.py` | Verify environment and dependencies |
| `verify_setup.py` | Validate configuration |
| `list_models.py` | List available models for configured provider |
| `preview_email.py` | Preview email template rendering |
| `run_ingest.py` | Test ingestion pipeline manually |
| `run_analyze.py` | Test analysis pipeline manually |
| `run_email.py` | Test email delivery manually |
| `setup_cron.py` | Configure cron scheduling |
| `setup_launchd.py` | Configure launchd scheduling |

## Data

- Article database: `data/articles.db` (SQLite, WAL mode).
- Cache database: co-located in the same SQLite file.
- Do not commit `data/` or `*.db` files.
