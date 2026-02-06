# Phase 0: Project Setup & Foundation

**Goal**: Establish a clean, well-structured Python project with proper tooling, configuration system, and core data models.

**Estimated Time**: 2-3 hours

---

## Prerequisites

Before starting, ensure you have:

- [ ] Python 3.12+ installed (`python --version`)
- [ ] `uv` package manager installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- [ ] Anthropic API key (from console.anthropic.com)
- [ ] Resend API key (from resend.com/api-keys)
- [ ] A verified domain in Resend (or use their test domain initially)

---

## Tasks

### 0.1 Initialize Project

```bash
# Create project directory
mkdir feed && cd feed

# Initialize with uv (creates pyproject.toml)
uv init --name feed --python 3.12

# Create directory structure
mkdir -p src/{ingest,analyze,deliver,storage}
mkdir -p config tests scripts
touch src/__init__.py
touch src/{ingest,analyze,deliver,storage}/__init__.py
```

- [ ] Run initialization commands
- [ ] Verify directory structure matches architecture diagram

### 0.2 Configure Dependencies

Update `pyproject.toml`:

```toml
[project]
name = "feed"
version = "0.1.0"
description = "Personal newsletter intelligence agent"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "anthropic>=0.40.0",      # Claude SDK
    "feedparser>=6.0.0",      # RSS parsing
    "resend>=2.0.0",          # Email delivery
    "httpx>=0.27.0",          # HTTP client (used by anthropic)
    "beautifulsoup4>=4.12.0", # HTML parsing
    "lxml>=5.0.0",            # Fast HTML/XML parser
    "pyyaml>=6.0.0",          # Config files
    "pydantic>=2.0.0",        # Data validation
    "pydantic-settings>=2.0", # Environment config
    "typer>=0.12.0",          # CLI framework
    "rich>=13.0.0",           # Beautiful terminal output
    "python-dateutil>=2.9.0", # Date parsing
    "jinja2>=3.1.0",          # Email templates
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "ruff>=0.6.0",
    "mypy>=1.11.0",
    "pre-commit>=3.8.0",
]

[project.scripts]
digest = "scripts.run_digest:main"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM"]

[tool.mypy]
python_version = "3.12"
strict = true
```

- [ ] Update `pyproject.toml` with dependencies
- [ ] Run `uv sync` to install dependencies
- [ ] Run `uv sync --dev` to install dev dependencies

### 0.3 Environment Configuration

Create `.env.example`:

```bash
# API Keys
ANTHROPIC_API_KEY=sk-ant-...
RESEND_API_KEY=re_...

# Email Configuration
EMAIL_FROM=digest@yourdomain.com
EMAIL_TO=you@email.com

# Optional: Override defaults
# DIGEST_HOUR=7
# DIGEST_TIMEZONE=America/New_York
# LOG_LEVEL=INFO
```

Create `.env` (copy and fill in your values):

```bash
cp .env.example .env
# Edit .env with your actual keys
```

- [ ] Create `.env.example` template
- [ ] Create `.env` with your actual API keys
- [ ] Add `.env` to `.gitignore`

### 0.4 Configuration System

Create `src/config.py`:

```python
"""
Configuration management using Pydantic Settings.

Loads from environment variables and YAML config files.
"""

from pathlib import Path
from typing import Self

import yaml
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Keys
    anthropic_api_key: str = Field(..., description="Anthropic API key")
    resend_api_key: str = Field(..., description="Resend API key")

    # Email
    email_from: str = Field(..., description="Sender email address")
    email_to: str = Field(..., description="Recipient email address")

    # Scheduling
    digest_hour: int = Field(default=7, ge=0, le=23, description="Hour to send digest (0-23)")
    digest_timezone: str = Field(default="America/New_York", description="Timezone for scheduling")

    # Processing
    max_articles_per_feed: int = Field(default=10, description="Max articles to fetch per feed")
    lookback_hours: int = Field(default=24, description="Hours to look back for new articles")
    
    # Claude
    claude_model: str = Field(default="claude-sonnet-4-20250514", description="Claude model to use")
    max_tokens_per_summary: int = Field(default=500, description="Max tokens per article summary")

    # Paths
    config_dir: Path = Field(default=Path("config"), description="Config directory")
    data_dir: Path = Field(default=Path("data"), description="Data directory")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")

    @model_validator(mode="after")
    def ensure_directories(self) -> Self:
        """Create necessary directories if they don't exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self


class FeedConfig:
    """Configuration for RSS feeds."""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self._feeds: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        """Load feeds from YAML file."""
        if not self.config_path.exists():
            self._feeds = {}
            return
        
        with open(self.config_path) as f:
            data = yaml.safe_load(f) or {}
        
        self._feeds = data.get("feeds", {})

    @property
    def feeds(self) -> dict[str, dict]:
        """Get all configured feeds."""
        return self._feeds

    def get_feed_urls(self) -> list[str]:
        """Get list of all feed URLs."""
        urls = []
        for feed in self._feeds.values():
            if url := feed.get("url"):
                urls.append(url)
        return urls

    def get_category(self, feed_url: str) -> str:
        """Get category for a feed URL."""
        for feed in self._feeds.values():
            if feed.get("url") == feed_url:
                return feed.get("category", "Uncategorized")
        return "Uncategorized"


# Global settings instance (lazy loaded)
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get application settings (singleton)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
```

- [ ] Create `src/config.py`
- [ ] Test configuration loads correctly

### 0.5 Data Models

Create `src/models.py`:

```python
"""
Core data models for the digest agent.

Using Pydantic for validation and serialization.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl


class ArticleStatus(str, Enum):
    """Processing status for an article."""
    
    PENDING = "pending"
    PROCESSING = "processing"
    SUMMARIZED = "summarized"
    FAILED = "failed"
    SKIPPED = "skipped"


class Article(BaseModel):
    """A newsletter article from an RSS feed."""

    id: str = Field(..., description="Unique identifier (URL hash)")
    url: HttpUrl = Field(..., description="Article URL")
    title: str = Field(..., description="Article title")
    author: str = Field(default="Unknown", description="Author name")
    feed_name: str = Field(..., description="Name of the source feed")
    feed_url: str = Field(..., description="URL of the source feed")
    published: datetime = Field(..., description="Publication timestamp")
    content: str = Field(default="", description="Full article content (HTML stripped)")
    word_count: int = Field(default=0, description="Word count of content")
    category: str = Field(default="Uncategorized", description="Content category")
    status: ArticleStatus = Field(default=ArticleStatus.PENDING, description="Processing status")
    
    # Populated after analysis
    summary: str | None = Field(default=None, description="Claude-generated summary")
    key_takeaways: list[str] = Field(default_factory=list, description="Key insights")
    action_items: list[str] = Field(default_factory=list, description="Actionable items")


class CategoryDigest(BaseModel):
    """Digest content for a single category."""

    name: str = Field(..., description="Category name")
    article_count: int = Field(..., description="Number of articles in category")
    articles: list[Article] = Field(default_factory=list, description="Articles in category")
    synthesis: str = Field(default="", description="Cross-article synthesis")
    top_takeaways: list[str] = Field(default_factory=list, description="Top insights across articles")


class DailyDigest(BaseModel):
    """Complete daily digest ready for delivery."""

    id: str = Field(..., description="Unique digest identifier")
    date: datetime = Field(..., description="Digest date")
    categories: list[CategoryDigest] = Field(default_factory=list, description="Categorized content")
    total_articles: int = Field(default=0, description="Total articles processed")
    total_feeds: int = Field(default=0, description="Total feeds checked")
    processing_time_seconds: float = Field(default=0.0, description="Time to generate digest")
    
    # Meta insights
    overall_themes: list[str] = Field(default_factory=list, description="Cross-category themes")
    must_read: list[str] = Field(default_factory=list, description="URLs of must-read articles")


class DigestStats(BaseModel):
    """Statistics about digest generation."""

    feeds_checked: int = 0
    feeds_successful: int = 0
    feeds_failed: int = 0
    articles_found: int = 0
    articles_new: int = 0
    articles_summarized: int = 0
    tokens_used: int = 0
    cost_estimate_usd: float = 0.0
    duration_seconds: float = 0.0
```

- [ ] Create `src/models.py`
- [ ] Verify models can be instantiated

### 0.6 Sample Feed Configuration

Create `config/feeds.yaml`:

```yaml
# Feed Agent - Feed Configuration
#
# Format:
#   feed_name:
#     url: RSS feed URL
#     category: Category for grouping (optional)
#     priority: 1-5, higher = more important (optional)
#     notes: Personal notes about this feed (optional)

feeds:
  # Technology
  stratechery:
    url: https://stratechery.com/feed/
    category: Tech Strategy
    priority: 5
    notes: Ben Thompson's analysis - always worth reading

  simon_willison:
    url: https://simonwillison.net/atom/everything/
    category: AI & Development
    priority: 5

  # Example Substacks (replace with your actual subscriptions)
  example_newsletter:
    url: https://example.substack.com/feed
    category: General
    priority: 3

# Categories define the sections in your digest
# Articles are grouped by category, then sorted by priority within each

categories:
  - name: Tech Strategy
    description: Business and strategy analysis
    color: "#3B82F6"  # Blue

  - name: AI & Development
    description: AI news, tools, and technical content
    color: "#8B5CF6"  # Purple

  - name: General
    description: Everything else worth reading
    color: "#6B7280"  # Gray
```

- [ ] Create `config/feeds.yaml`
- [ ] Add 3-5 of your actual newsletter feeds for testing

### 0.7 Logging Setup

Create `src/logging_config.py`:

```python
"""
Logging configuration for the digest agent.

Uses rich for beautiful terminal output.
"""

import logging
import sys
from typing import Literal

from rich.console import Console
from rich.logging import RichHandler

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def setup_logging(level: LogLevel = "INFO") -> logging.Logger:
    """
    Configure logging with rich handler.
    
    Returns the root logger configured for the application.
    """
    console = Console(stderr=True)
    
    handler = RichHandler(
        console=console,
        show_time=True,
        show_path=False,
        rich_tracebacks=True,
        tracebacks_show_locals=True,
    )
    
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[handler],
    )
    
    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    logging.getLogger("feedparser").setLevel(logging.WARNING)
    
    return logging.getLogger("substack_agent")


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a specific module."""
    return logging.getLogger(f"substack_agent.{name}")
```

- [ ] Create `src/logging_config.py`

### 0.8 Git Setup

Create `.gitignore`:

```gitignore
# Environment
.env
.env.local
.venv/
venv/

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
*.egg-info/
dist/
build/

# Data
data/
*.db
*.sqlite

# IDE
.idea/
.vscode/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Testing
.pytest_cache/
.coverage
htmlcov/

# Type checking
.mypy_cache/

# Logs
*.log
logs/
```

Initialize git:

```bash
git init
git add .
git commit -m "Initial project setup"
```

- [ ] Create `.gitignore`
- [ ] Initialize git repository
- [ ] Make initial commit

### 0.9 Verify Setup

Create `scripts/verify_setup.py`:

```python
"""Verify that the project is set up correctly."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def main() -> None:
    """Run setup verification."""
    print("🔍 Verifying project setup...\n")
    
    errors: list[str] = []
    
    # Check Python version
    print(f"Python version: {sys.version}")
    if sys.version_info < (3, 12):
        errors.append("Python 3.12+ required")
    else:
        print("✅ Python version OK")
    
    # Check imports
    print("\nChecking dependencies...")
    try:
        import anthropic
        print(f"✅ anthropic {anthropic.__version__}")
    except ImportError as e:
        errors.append(f"anthropic: {e}")
    
    try:
        import feedparser
        print(f"✅ feedparser {feedparser.__version__}")
    except ImportError as e:
        errors.append(f"feedparser: {e}")
    
    try:
        import resend
        print("✅ resend")
    except ImportError as e:
        errors.append(f"resend: {e}")
    
    try:
        from bs4 import BeautifulSoup
        print("✅ beautifulsoup4")
    except ImportError as e:
        errors.append(f"beautifulsoup4: {e}")
    
    try:
        import yaml
        print("✅ pyyaml")
    except ImportError as e:
        errors.append(f"pyyaml: {e}")
    
    try:
        import pydantic
        print(f"✅ pydantic {pydantic.__version__}")
    except ImportError as e:
        errors.append(f"pydantic: {e}")
    
    # Check configuration
    print("\nChecking configuration...")
    try:
        from config import get_settings
        settings = get_settings()
        print(f"✅ Settings loaded")
        print(f"   Claude model: {settings.claude_model}")
        print(f"   Email from: {settings.email_from}")
    except Exception as e:
        errors.append(f"Configuration: {e}")
    
    # Check feeds config
    print("\nChecking feeds config...")
    feeds_path = Path("config/feeds.yaml")
    if feeds_path.exists():
        try:
            from config import FeedConfig
            feed_config = FeedConfig(feeds_path)
            urls = feed_config.get_feed_urls()
            print(f"✅ Found {len(urls)} configured feeds")
        except Exception as e:
            errors.append(f"Feeds config: {e}")
    else:
        errors.append("config/feeds.yaml not found")
    
    # Summary
    print("\n" + "=" * 50)
    if errors:
        print("❌ Setup verification FAILED")
        print("\nErrors:")
        for error in errors:
            print(f"  • {error}")
        sys.exit(1)
    else:
        print("✅ Setup verification PASSED")
        print("\nReady to proceed to Phase 1!")


if __name__ == "__main__":
    main()
```

- [ ] Create `scripts/verify_setup.py`
- [ ] Run `uv run python scripts/verify_setup.py`
- [ ] Fix any issues reported

---

## Completion Checklist

- [ ] All directories created
- [ ] Dependencies installed and importable
- [ ] `.env` configured with API keys
- [ ] `config/feeds.yaml` has at least 3 test feeds
- [ ] `verify_setup.py` passes all checks
- [ ] Initial git commit made

## Next Phase

Once all checks pass, proceed to `02-PHASE-INGEST.md` to implement the content ingestion layer.
