# Quick Reference & Cheatsheet

A condensed reference for the Feed Agent.

---

## Project Structure

```
feed/
├── src/
│   ├── config.py           # Settings & feed config
│   ├── models.py           # Pydantic data models
│   ├── pipeline.py         # Main orchestration
│   ├── logging_config.py   # Logging setup
│   ├── ingest/             # RSS fetching & parsing
│   ├── analyze/            # Claude summarization
│   ├── deliver/            # Email templates & sending
│   ├── storage/            # SQLite database
│   └── utils/              # Retry, notifications, validators
├── config/
│   ├── feeds.yaml          # Your newsletter subscriptions
│   └── settings.yaml       # Optional overrides
├── scripts/
│   └── run_digest.py       # CLI entry point
├── data/                   # Database & backups (gitignored)
├── logs/                   # Log files (gitignored)
├── .env                    # API keys (gitignored)
└── pyproject.toml          # Dependencies
```

---

## CLI Commands

```bash
# Full pipeline
./feed run                  # Ingest → Analyze → Send
./feed run --skip-send      # Run without sending email
./feed run -v               # Verbose output

# Individual phases
./feed ingest               # Only fetch new articles
./feed analyze              # Only summarize pending articles
./feed send                 # Send from summarized articles
./feed send --test          # Send test email

# Status & info
./feed status               # Article counts & recent items
./feed stats                # Detailed database statistics
./feed config               # Verify configuration
./feed validate             # Test API connections

# Maintenance
./feed cleanup --days 30    # Preview old article cleanup
./feed cleanup --execute    # Actually delete old articles
./feed backup               # Create database backup
```

---

## Configuration

### Environment Variables (.env)

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...
RESEND_API_KEY=re_...
EMAIL_FROM=digest@yourdomain.com
EMAIL_TO=you@email.com

# Optional
DIGEST_HOUR=7
DIGEST_TIMEZONE=America/New_York
CLAUDE_MODEL=claude-sonnet-4-20250514
MAX_ARTICLES_PER_FEED=10
LOOKBACK_HOURS=24
LOG_LEVEL=INFO
```

### Feed Configuration (config/feeds.yaml)

```yaml
feeds:
  stratechery:
    url: https://stratechery.com/feed/
    category: Tech Strategy
    priority: 5

  simon_willison:
    url: https://simonwillison.net/atom/everything/
    category: AI & Development
    priority: 5

  your_favorite:
    url: https://newsletter.substack.com/feed
    category: General
    priority: 3
```

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `src/config.py` | Settings management, feed loading |
| `src/models.py` | Article, Digest, Category models |
| `src/ingest/feeds.py` | RSS fetching with feedparser |
| `src/ingest/parser.py` | HTML content extraction |
| `src/analyze/prompts.py` | Claude prompt templates |
| `src/analyze/summarizer.py` | Article summarization |
| `src/analyze/digest_builder.py` | Cross-article synthesis |
| `src/deliver/email.py` | Resend integration |
| `src/deliver/templates/` | Jinja2 email templates |
| `src/storage/db.py` | SQLite operations |
| `src/pipeline.py` | Full pipeline with error handling |

---

## Data Models

```python
# Article - Single newsletter post
Article(
    id: str,              # URL hash
    url: HttpUrl,
    title: str,
    author: str,
    feed_name: str,
    published: datetime,
    content: str,         # Extracted text
    category: str,
    status: ArticleStatus,  # pending/summarized/failed
    summary: str | None,
    key_takeaways: list[str],
    action_items: list[str],
)

# DailyDigest - Complete digest
DailyDigest(
    id: str,
    date: datetime,
    categories: list[CategoryDigest],
    total_articles: int,
    overall_themes: list[str],
    must_read: list[str],
)
```

---

## Scheduling

### macOS (launchd)

```bash
# Generate and install
uv run python scripts/setup_launchd.py

# Control
launchctl load ~/Library/LaunchAgents/com.user.feed.plist
launchctl start com.user.feed
launchctl list | grep feed
```

### Linux/cron

```bash
# Edit crontab
crontab -e

# Add line (7 AM daily)
0 7 * * * cd /path/to/feed && /path/to/python scripts/run_digest.py run >> logs/digest.log 2>&1
```

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| No articles found | Feed URLs valid? `lookback_hours` too short? |
| Summaries empty | Anthropic API key valid? Content extracted? |
| Email not received | Resend key valid? Check spam folder |
| High costs | Reduce `max_articles_per_feed`, filter feeds |
| Pipeline slow | Network issues? Too many articles? |

### Debug Commands

```bash
# Verbose output
./feed run -v

# Check logs
tail -f logs/digest_$(date +%Y%m%d).log

# Test API connections
./feed validate

# Check database
./feed stats
```

---

## Cost Estimation

With 50 newsletters, ~5 articles each, daily:

| Component | Tokens | Cost/day |
|-----------|--------|----------|
| Summaries | ~125K | ~$0.40 |
| Synthesis | ~10K | ~$0.03 |
| **Total** | ~135K | ~$0.50 |

Monthly: ~$15 (Sonnet pricing)

---

## Implementation Order

1. **Phase 0**: Project setup, dependencies
2. **Phase 1**: RSS ingestion, database
3. **Phase 2**: Claude summarization
4. **Phase 3**: Email templates, Resend
5. **Phase 4**: CLI, scheduling
6. **Phase 5**: Error handling, polish

Total time: 15-20 hours

---

## Quick Test Sequence

```bash
# 1. Verify setup
./feed config
./feed validate

# 2. Test ingestion
./feed ingest -v

# 3. Test analysis (uses API)
./feed analyze -v

# 4. Test email
./feed send --test

# 5. Full run (dry)
./feed run --skip-send

# 6. Full run
./feed run
```
