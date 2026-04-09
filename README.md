# Feed 📬

Your personal newsletter intelligence agent. Aggregates RSS feeds (Substack, blogs, etc.), summarizes them with AI, and delivers a daily digest to your terminal or inbox.

Current CLI version: `v0.3.0`.

## Quickstart

```bash
# 1. Clone and install
git clone https://github.com/davisbuilds/feed.git
cd feed
uv sync

# 2. Run the setup wizard (configures API keys and feeds)
./feed init

# 3. Run your first digest
./feed run
```

You'll need an LLM API key (Gemini, OpenAI, or Anthropic). The wizard will also offer to configure email delivery — this is optional and can be skipped if you only want terminal output. Run `./feed --help` for command info.

## Features

- **Automated Ingestion**: Concurrently fetches articles from Substack, RSS, and Atom feeds.
- **AI-Powered Analysis**: Summarizes articles, extracts key takeaways, and synthesizes trends.
- **Multi-Provider LLM**: Supports Google Gemini (default), OpenAI, and Anthropic.
- **Smart Categorization**: Groups updates by category (e.g., Tech, AI, Business) for easier reading.
- **Terminal-First Output**: Rich, plain text, or JSON output to the terminal; email delivery via `--send` (requires a [Resend](https://resend.com) account and a verified sender domain); clipboard copy via `--copy`.
- **Local First**: Stores all data in a local SQLite database for privacy and speed.
- **XDG Config**: Global config at `~/.config/feed/` so you can run `feed` from any directory.
- **Feed Diagnostics**: `feed test` validates URL reachability, parser health, redirects, and entry counts.
- **Response Cache + Retry**: SQLite-backed LLM cache with TTL, retry with exponential backoff, and `--no-cache` controls.

## Tech Stack

- **Python 3.12+**
- **LLM**: Gemini, OpenAI, Anthropic, etc
- **Email**: Resend API
- **CLI**: Typer & Rich
- **Data**: SQLite & Pydantic
- **Package Manager**: uv

## Setup

### 1. Prerequisites

Ensure you have [uv](https://github.com/astral-sh/uv) installed (recommended) or use standard pip.

```bash
# Install uv (macOS/Linux)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/davisbuilds/feed.git
cd feed
uv sync
```

### 2b. Global CLI Install / Reinstall

If you want `feed` available globally (not only `./feed` from this repo), install as an editable uv tool from the repo root:

```bash
uv tool install --editable .
```

To refresh a stale global install after local updates:

```bash
uv tool uninstall feed
uv tool install --editable .
```

### 3. Configuration

The quickest way to get started is the interactive setup wizard:

```bash
./feed init
```

This creates `~/.config/feed/config.env` with your API keys and copies a sample `feeds.yaml`. You can then run `feed` from any directory.

The email configuration step is **optional** — press Enter to skip it if you only want terminal output. Email delivery via `--send` requires a [Resend](https://resend.com) account and a verified sender domain. You can add these settings later by re-running `feed init --force`.

#### Manual configuration

Alternatively, create a `.env` file in the project root (takes priority over the XDG config):

```ini
LLM_PROVIDER=gemini            # gemini (default), openai, or anthropic
LLM_API_KEY=your_api_key
# LLM_MODEL=                   # optional; defaults per provider

# Required only for email delivery (feed run --send)
# Needs a Resend account (resend.com) and a verified sender domain
# RESEND_API_KEY=your_resend_api_key
# EMAIL_FROM=digest@yourdomain.com
# EMAIL_TO=you@example.com
```

Config is loaded from two locations (higher priority wins):

1. `~/.config/feed/config.env` — user-level (XDG)
2. `.env` in the current directory — project-level override

#### Config Resolution (Important)

- `feed` always evaluates both config sources above. A `.env` in your current working directory overrides values from `~/.config/feed/config.env`.
- The active feeds file is resolved as `CONFIG_DIR/feeds.yaml`.
- If `CONFIG_DIR` is not set, it defaults to `config/`, which is relative to the current working directory.
- This means running from the repo often uses `./config/feeds.yaml`, while true run-anywhere behavior uses `CONFIG_DIR=~/.config/feed`.
- Run `feed config` to see exactly which env file and config directory are active. Use `feed config --json` for machine-readable output.

Configure your feeds in `config/feeds.yaml` (or `~/.config/feed/feeds.yaml` when using XDG):

```yaml
feeds:
  stratechery:
    url: https://stratechery.com/feed/
    category: Tech Strategy

  simon_willison:
    url: https://simonwillison.net/atom/everything/
    category: Engineering
```

## Usage

The CLI is called `feed`. Run it via the `./feed` wrapper script (or `uv run feed`).

### Quick Reference

```text
run      [--send] [--copy] [--format rich|text|json] [--no-cache]
schedule [--status] [--backend auto|cron|launchd] [--frequency daily|weekly] [--time HH:MM] [--install]
ingest
analyze  [--copy] [--format rich|text|json] [--no-cache]
send     [--test] [--format rich|text|json]
test     [--url URL | --name NAME | --all] [--strict] [--timeout N] [--lookback-hours N] [--max-articles N]
status   [--json]
config
cache    [--clear]
init     [--force]
```

### Main Pipeline

Run the full daily workflow (Ingest → Analyze → display digest):

```bash
./feed run                     # Rich terminal output (default)
./feed run --copy              # Also copy digest as markdown to clipboard
./feed run --format text       # Plain text output
./feed run --format json       # JSON output
./feed run --send              # Send digest via email instead
./feed run --copy --send       # Send email AND copy to clipboard
./feed schedule                # Preview default schedule (Fri 17:00)
./feed schedule --status       # Inspect installed schedule status
./feed schedule --install      # Install schedule (auto backend)
./feed schedule --backend cron --install
```

Run `feed --help` or `feed <command> --help` for the full list of options per command. See [docs/system/FEATURES.md](docs/system/FEATURES.md) for a detailed CLI and options reference.

## Project Structure

```text
feed/
├── config/              # Default feeds.yaml
├── src/
│   ├── analyze/         # Summarizer + digest builder
│   ├── deliver/         # Email sender + templates
│   ├── ingest/          # Feed fetch + parse/test logic
│   ├── llm/             # Provider clients + retry wrapper
│   ├── storage/         # SQLite DB + cache store
│   ├── cli.py           # Typer CLI entry point
│   ├── config.py        # Pydantic settings + XDG support
│   └── models.py        # Shared models
├── scripts/             # Utility scripts (healthcheck, preview, setup helpers)
├── tests/               # Pytest suite
└── docs/                # Design docs and plans
```

## Documentation

- Contributor workflow and PR expectations: [CONTRIBUTING.md](CONTRIBUTING.md)
- Agent implementation guidance: [AGENTS.md](AGENTS.md)
- Architecture and code organization: [docs/system/ARCHITECTURE.md](docs/system/ARCHITECTURE.md)
- Feature and CLI reference: [docs/system/FEATURES.md](docs/system/FEATURES.md)
- Runtime operations (env, CI, scripts): [docs/system/OPERATIONS.md](docs/system/OPERATIONS.md)
- Product roadmap snapshot: [docs/project/ROADMAP.md](docs/project/ROADMAP.md)
- Testing strategy: [docs/plans/TEST_PLAN.md](docs/plans/TEST_PLAN.md)
- Git history and branch policy: [docs/project/GIT_HISTORY_POLICY.md](docs/project/GIT_HISTORY_POLICY.md)

## Development

Run the test suite:

```bash
uv run python -m pytest
```

Alternatively, you can use `uv run feed <command>` instead of the wrapper script.

The project includes a few helper scripts in `scripts/`:
- `run_ingest.py`: Test the ingestion pipeline manually.
- `run_analyze.py`: Test the analysis pipeline manually.
