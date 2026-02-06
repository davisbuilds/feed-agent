# Feed Agent

A personal newsletter intelligence agent that reads your RSS subscriptions, analyzes content with AI, and delivers a beautifully crafted daily digest to your inbox.

## Vision

Transform newsletter overload into actionable insight. Instead of 50+ unread newsletters creating guilt and FOMO, receive one thoughtfully curated email each morning with categorical breakdowns, key takeaways, and actionable insights.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                            Feed Agent                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│   │    Ingest    │───▶│   Analyze    │───▶│   Deliver    │          │
│   └──────────────┘    └──────────────┘    └──────────────┘          │
│          │                   │                   │                   │
│          ▼                   ▼                   ▼                   │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│   │  RSS Feeds   │    │ Claude SDK   │    │    Resend    │          │
│   │  feedparser  │    │ Sonnet 4     │    │ React Email  │          │
│   └──────────────┘    └──────────────┘    └──────────────┘          │
│                              │                                       │
│                              ▼                                       │
│                       ┌──────────────┐                              │
│                       │   SQLite     │                              │
│                       │  (tracking)  │                              │
│                       └──────────────┘                              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Design Principles

1. **Simplicity First** — Prefer stdlib over dependencies. Each component should be understandable in isolation.

2. **Graceful Degradation** — If one feed fails, process the rest. If Claude is slow, queue and retry. Never lose data.

3. **Beautiful Output** — The daily digest is the product. Invest in typography, hierarchy, and scannability.

4. **Observable** — Clear logging, easy debugging. Know exactly what happened and why.

5. **Configurable** — Feeds, categories, delivery time, email style — all in one YAML file.

## Project Structure

```
feed/
├── src/
│   ├── __init__.py
│   ├── config.py          # Configuration loading & validation
│   ├── models.py          # Data models (Article, Digest, Category)
│   ├── ingest/
│   │   ├── __init__.py
│   │   ├── feeds.py       # RSS feed fetching
│   │   └── parser.py      # Content extraction & cleaning
│   ├── analyze/
│   │   ├── __init__.py
│   │   ├── summarizer.py  # Claude summarization
│   │   ├── categorizer.py # Topic classification
│   │   └── prompts.py     # Prompt templates
│   ├── deliver/
│   │   ├── __init__.py
│   │   ├── email.py       # Resend integration
│   │   └── templates/     # Email templates
│   └── storage/
│       ├── __init__.py
│       └── db.py          # SQLite operations
├── config/
│   ├── feeds.yaml         # Your subscriptions
│   └── settings.yaml      # Agent configuration
├── tests/
│   ├── __init__.py
│   ├── test_ingest.py
│   ├── test_analyze.py
│   └── test_deliver.py
├── scripts/
│   └── run_digest.py      # Main entry point
├── pyproject.toml
├── README.md
└── .env.example
```

## Technology Choices

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python 3.12+ | Rich ecosystem, excellent for data processing |
| RSS Parsing | `feedparser` | Battle-tested, handles malformed feeds gracefully |
| AI | Claude Sonnet 4 | Best balance of quality/speed/cost for summarization |
| SDK | `anthropic` | Official Python SDK, simple and well-documented |
| Email | Resend | Developer-friendly API, great deliverability |
| Templates | `jinja2` | Powerful, familiar, works for HTML email |
| Storage | SQLite | Zero-config, portable, perfect for single-user |
| Config | YAML | Human-readable, supports comments |
| CLI | `typer` | Modern, type-safe, auto-generates help |

## Implementation Phases

| Phase | Focus | Deliverable |
|-------|-------|-------------|
| 0 | Setup | Project scaffold, dependencies, config system |
| 1 | Ingest | Feed fetching, parsing, deduplication, storage |
| 2 | Analyze | Claude integration, summarization, categorization |
| 3 | Deliver | Email templates, Resend integration |
| 4 | Orchestrate | CLI, scheduling, end-to-end pipeline |
| 5 | Polish | Error handling, monitoring, refinements |

## Key Metrics

Track these to measure success:

- **Coverage**: % of subscribed feeds successfully processed
- **Latency**: Time from run start to email sent
- **Quality**: Manual review of summary accuracy (spot check)
- **Cost**: Claude API spend per digest
- **Engagement**: Do you actually read the digest? (self-reported)

## Getting Started

See `01-PHASE-SETUP.md` to begin implementation.
