# Feed Agent 📬

Your personal newsletter intelligence agent. This tool aggregates RSS feeds (Substack, blogs, etc.), summarizes them using Google's Gemini models, and sends you a high-quality daily digest email.

## Features

- **Automated Ingestion**: Concurrently fetches articles from RSS/Atom feeds.
- **AI-Powered Analysis**: Uses Google Gemini to summarize articles, extract key takeaways, and synthesize trends.
- **Smart Categorization**: Groups updates by category (e.g., Tech, AI, Business) for easier reading.
- **Daily Email Digest**: Delivers a clean, responsive HTML email summary to your inbox.
- **Local First**: Stores all data in a local SQLite database for privacy and speed.

## Tech Stack

- **Python 3.12+**
- **LLM**: Google Gemini (via `google-genai` SDK)
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

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Edit `.env` with your API keys:

```ini
GOOGLE_API_KEY=your_gemini_api_key
RESEND_API_KEY=your_resend_api_key
EMAIL_FROM=digest@yourdomain.com
EMAIL_TO=you@example.com
GEMINI_MODEL=gemini-3-flash  # or gemini-3-pro
```

Configure your feeds in `config/feeds.yaml`:

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

The application uses a CLI named `feed`. Run it via the `./feed` wrapper script.

### Main Pipeline

Run the full daily workflow (Ingest → Analyze → Send):

```bash
./feed run
```

### Individual Commands

| Command | Description |
|---------|-------------|
| `./feed status` | Show pipeline statistics and recent articles |
| `./feed ingest` | Fetch new articles from feeds |
| `./feed analyze` | Summarize pending articles with AI |
| `./feed send` | Generate and send the email digest |
| `./feed config` | Verify configuration settings |

### Options

- `--verbose` / `-v`: Enable debug logging.
- `--skip-send`: Run ingestion and analysis but skip sending the email.
- `--test`: Send a test email to verify delivery settings.

## Development

Run the test suite:

```bash
uv run pytest
```

Alternatively, you can use `uv run feed <command>` instead of the wrapper script.

The project includes a few helper scripts in `scripts/`:
- `run_ingest.py`: Test the ingestion pipeline manually.
- `run_analyze.py`: Test the analysis pipeline manually.
