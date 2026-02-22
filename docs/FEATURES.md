# Features

Product-surface reference for Feed.

## Feed Ingestion

- Concurrent RSS/Atom feed fetching via `httpx` with configurable timeouts.
- Per-feed categories and priority metadata in `feeds.yaml`.
- Feed diagnostics (`feed test`): validates URL reachability, parser health, redirects, entry counts.
- Bot-filter retry with browser-style headers on 403/404.
- Feed health tracking with consecutive failure counts.

## AI Analysis

- Structured summarization: 2-3 sentence summary, key takeaways (up to 5), action items (up to 3).
- Topic extraction and sentiment classification.
- Importance scoring (1-5 scale).
- Category-level synthesis with cross-article trend analysis.
- Must-read selection based on importance scoring.

## Output and Delivery

- Terminal output: Rich (default), plain text, or JSON format.
- Email delivery via Resend API with Jinja2 HTML + plain text templates.
- `--send` flag on `run` command for email delivery.
- Test email mode via `feed send --test`.

## Scheduling

- Recurring digest generation via `feed schedule`.
- Backends: `cron` (Linux/macOS) and `launchd` (macOS).
- Configurable frequency (`daily`, `weekly`) and time.
- Status inspection via `feed schedule --status`.

## Cache and Retry

- SQLite-backed LLM response cache with 7-day TTL.
- SHA256 cache keys from article ID + model name.
- `--no-cache` flag forces fresh summaries.
- Exponential backoff retry for transient LLM failures (timeouts, 429, 5xx).

## CLI Command Reference

| Command | Key Flags | Purpose |
|---------|-----------|---------|
| `init` | `--force` | Interactive setup wizard |
| `run` | `--send`, `--format`, `--no-cache` | Full pipeline: ingest → analyze → output |
| `schedule` | `--backend`, `--frequency`, `--time`, `--install`, `--status` | Recurring job management |
| `ingest` | | Fetch new articles |
| `analyze` | `--format`, `--no-cache` | Summarize pending articles |
| `send` | `--test`, `--format` | Email digest delivery |
| `test` | `--url`, `--name`, `--all`, `--strict` | Feed URL validation |
| `status` | `--json` | Pipeline statistics |
| `config` | | Show active configuration |
| `cache` | `--clear` | Cache statistics or clear |

## Configuration Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `LLM_PROVIDER` | `gemini` | LLM provider (`gemini`, `openai`, `anthropic`) |
| `LLM_API_KEY` | (required) | API key for chosen provider |
| `LLM_MODEL` | per-provider | Model override |
| `RESEND_API_KEY` | (required) | Email delivery API key |
| `EMAIL_FROM` | (required) | Sender email address |
| `EMAIL_TO` | (required) | Recipient email address |
| `CONFIG_DIR` | `config/` | Path to `feeds.yaml` directory |
| `DATA_DIR` | `data/` | SQLite data directory |
