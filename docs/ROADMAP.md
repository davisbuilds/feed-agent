# Roadmap

This is a lightweight snapshot, not a release contract.

## Completed Highlights

- v0.3.0 pipeline: ingest → analyze → deliver with Rich/text/JSON output.
- Multi-provider LLM abstraction (Gemini, OpenAI, Anthropic) with structured output.
- SQLite-backed response cache with 7-day TTL and lazy expiration.
- Exponential backoff retry wrapper for transient LLM failures.
- Cron and launchd scheduler backends with `feed schedule`.
- Feed diagnostics (`feed test`) with URL validation and parser health checks.
- Email delivery via Resend API with Jinja2 HTML + plain text templates.
- XDG config convention for run-anywhere CLI usage.
- CI pipeline with ruff linting and pytest on PR/push to main.

## Planned / Open Areas

- See `docs/plans/` for active planning documents.
