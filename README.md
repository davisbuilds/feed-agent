# Feed 📬

Your personal newsletter intelligence agent. Aggregates RSS feeds (Substack, blogs, etc.), summarizes them with AI, and delivers a daily digest to your terminal or inbox.

## Features

- **Automated Ingestion**: Concurrently fetches articles from RSS/Atom feeds.
- **AI-Powered Analysis**: Summarizes articles, extracts key takeaways, and synthesizes trends.
- **Multi-Provider LLM**: Supports Google Gemini (default), OpenAI, and Anthropic.
- **Smart Categorization**: Groups updates by category (e.g., Tech, AI, Business) for easier reading.
- **Terminal-First Output**: Rich, plain text, or JSON output to the terminal; email delivery via `--send`.
- **Local First**: Stores all data in a local SQLite database for privacy and speed.
- **XDG Config**: Global config at `~/.config/feed/` so you can run `feed` from any directory.

## Tech Stack

- **Python 3.12+**
- **LLM**: Gemini, OpenAI, or Anthropic (provider-agnostic abstraction)
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

### 3. Configuration

The quickest way to get started is the interactive setup wizard:

```bash
./feed init
```

This creates `~/.config/feed/config.env` with your API keys and copies a sample `feeds.yaml`. You can then run `feed` from any directory.

#### Manual configuration

Alternatively, create a `.env` file in the project root (takes priority over the XDG config):

```ini
LLM_PROVIDER=gemini            # gemini (default), openai, or anthropic
LLM_API_KEY=your_api_key
# LLM_MODEL=                   # optional; defaults per provider
RESEND_API_KEY=your_resend_api_key
EMAIL_FROM=digest@yourdomain.com
EMAIL_TO=you@example.com
```

Config is loaded from two locations (higher priority wins):

1. `~/.config/feed/config.env` — user-level (XDG)
2. `.env` in the current directory — project-level override

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

### Main Pipeline

Run the full daily workflow (Ingest → Analyze → display digest):

```bash
./feed run                     # Rich terminal output (default)
./feed run --format text       # Plain text output
./feed run --format json       # JSON output
./feed run --send              # Send digest via email instead
```

### Individual Commands

| Command | Description |
|---------|-------------|
| `./feed init` | Interactive setup wizard (creates `~/.config/feed/`) |
| `./feed run` | Full pipeline: ingest, analyze, and display digest |
| `./feed status` | Show pipeline statistics and recent articles |
| `./feed ingest` | Fetch new articles from feeds |
| `./feed test --all` | Validate feed URLs and parser health for configured feeds |
| `./feed test --url <feed_url>` | Test a one-off feed URL before adding it |
| `./feed analyze` | Summarize pending articles with AI |
| `./feed send` | Generate and send the email digest |
| `./feed config` | Verify configuration and show config file locations |

### Options

- `--verbose` / `-v`: Enable debug logging.
- `--format`: Output format (`rich`, `text`, `json`). Applies to `run`, `analyze`, `send`.
- `--send`: Deliver digest via email instead of printing to terminal.

## Development

Run the test suite:

```bash
uv run pytest
```

Alternatively, you can use `uv run feed <command>` instead of the wrapper script.

The project includes a few helper scripts in `scripts/`:
- `run_ingest.py`: Test the ingestion pipeline manually.
- `run_analyze.py`: Test the analysis pipeline manually.
