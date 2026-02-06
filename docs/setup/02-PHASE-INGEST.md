# Phase 1: Content Ingestion

**Goal**: Build a robust system to fetch RSS feeds, parse article content, extract clean text, and store articles in SQLite with deduplication.

**Estimated Time**: 3-4 hours

**Dependencies**: Phase 0 completed

---

## Overview

The ingestion layer is the foundation of the agent. It must be:

- **Resilient**: One broken feed shouldn't crash the system
- **Efficient**: Fetch only new articles, cache appropriately
- **Clean**: Extract readable text from HTML chaos
- **Trackable**: Know exactly what was fetched and when

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Feed URLs   │────▶│   Fetch     │────▶│   Parse     │────▶│   Store     │
│ (YAML)      │     │ (feedparser)│     │ (bs4/lxml)  │     │  (SQLite)   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                           │                   │                   │
                           ▼                   ▼                   ▼
                    Handle timeouts      Strip HTML          Deduplicate
                    Retry failures       Extract text        Track status
                    Validate feeds       Clean content       Index by date
```

---

## Tasks

### 1.1 Database Schema

Create `src/storage/db.py`:

```python
"""
SQLite database operations for article storage.

Design decisions:
- Single file database for simplicity
- WAL mode for concurrent reads
- Indexes on common query patterns
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator

from src.models import Article, ArticleStatus


class Database:
    """SQLite database wrapper for article storage."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create tables if they don't exist."""
        with self._connection() as conn:
            conn.executescript("""
                -- Enable WAL mode for better concurrency
                PRAGMA journal_mode=WAL;
                
                -- Articles table
                CREATE TABLE IF NOT EXISTS articles (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    author TEXT DEFAULT 'Unknown',
                    feed_name TEXT NOT NULL,
                    feed_url TEXT NOT NULL,
                    published TEXT NOT NULL,
                    content TEXT DEFAULT '',
                    word_count INTEGER DEFAULT 0,
                    category TEXT DEFAULT 'Uncategorized',
                    status TEXT DEFAULT 'pending',
                    summary TEXT,
                    key_takeaways TEXT,  -- JSON array
                    action_items TEXT,   -- JSON array
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Indexes for common queries
                CREATE INDEX IF NOT EXISTS idx_articles_published 
                    ON articles(published DESC);
                CREATE INDEX IF NOT EXISTS idx_articles_status 
                    ON articles(status);
                CREATE INDEX IF NOT EXISTS idx_articles_feed 
                    ON articles(feed_url);
                CREATE INDEX IF NOT EXISTS idx_articles_category 
                    ON articles(category);
                
                -- Feed status tracking
                CREATE TABLE IF NOT EXISTS feed_status (
                    feed_url TEXT PRIMARY KEY,
                    feed_name TEXT NOT NULL,
                    last_checked TEXT,
                    last_success TEXT,
                    last_error TEXT,
                    consecutive_failures INTEGER DEFAULT 0
                );
                
                -- Digest history
                CREATE TABLE IF NOT EXISTS digests (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    article_count INTEGER NOT NULL,
                    categories TEXT NOT NULL,  -- JSON
                    sent_at TEXT,
                    email_id TEXT  -- From Resend
                );
            """)

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def article_exists(self, article_id: str) -> bool:
        """Check if an article already exists."""
        with self._connection() as conn:
            result = conn.execute(
                "SELECT 1 FROM articles WHERE id = ?", 
                (article_id,)
            ).fetchone()
            return result is not None

    def save_article(self, article: Article) -> bool:
        """
        Save an article to the database.
        
        Returns True if new article, False if already existed.
        """
        import json
        
        if self.article_exists(article.id):
            return False
        
        with self._connection() as conn:
            conn.execute("""
                INSERT INTO articles (
                    id, url, title, author, feed_name, feed_url,
                    published, content, word_count, category, status,
                    summary, key_takeaways, action_items
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                article.id,
                str(article.url),
                article.title,
                article.author,
                article.feed_name,
                article.feed_url,
                article.published.isoformat(),
                article.content,
                article.word_count,
                article.category,
                article.status.value,
                article.summary,
                json.dumps(article.key_takeaways),
                json.dumps(article.action_items),
            ))
        return True

    def get_pending_articles(self, limit: int = 100) -> list[Article]:
        """Get articles that need summarization."""
        import json
        
        with self._connection() as conn:
            rows = conn.execute("""
                SELECT * FROM articles 
                WHERE status = 'pending'
                ORDER BY published DESC
                LIMIT ?
            """, (limit,)).fetchall()
        
        return [self._row_to_article(row) for row in rows]

    def get_articles_since(
        self, 
        since: datetime, 
        status: ArticleStatus | None = None
    ) -> list[Article]:
        """Get articles published since a given time."""
        with self._connection() as conn:
            if status:
                rows = conn.execute("""
                    SELECT * FROM articles 
                    WHERE published >= ? AND status = ?
                    ORDER BY published DESC
                """, (since.isoformat(), status.value)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM articles 
                    WHERE published >= ?
                    ORDER BY published DESC
                """, (since.isoformat(),)).fetchall()
        
        return [self._row_to_article(row) for row in rows]

    def update_article_summary(
        self,
        article_id: str,
        summary: str,
        key_takeaways: list[str],
        action_items: list[str],
    ) -> None:
        """Update an article with its summary."""
        import json
        
        with self._connection() as conn:
            conn.execute("""
                UPDATE articles SET
                    summary = ?,
                    key_takeaways = ?,
                    action_items = ?,
                    status = 'summarized',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                summary,
                json.dumps(key_takeaways),
                json.dumps(action_items),
                article_id,
            ))

    def update_article_status(
        self, 
        article_id: str, 
        status: ArticleStatus
    ) -> None:
        """Update article processing status."""
        with self._connection() as conn:
            conn.execute("""
                UPDATE articles SET
                    status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status.value, article_id))

    def _row_to_article(self, row: sqlite3.Row) -> Article:
        """Convert a database row to an Article model."""
        import json
        from dateutil.parser import parse as parse_date
        
        return Article(
            id=row["id"],
            url=row["url"],
            title=row["title"],
            author=row["author"],
            feed_name=row["feed_name"],
            feed_url=row["feed_url"],
            published=parse_date(row["published"]),
            content=row["content"],
            word_count=row["word_count"],
            category=row["category"],
            status=ArticleStatus(row["status"]),
            summary=row["summary"],
            key_takeaways=json.loads(row["key_takeaways"] or "[]"),
            action_items=json.loads(row["action_items"] or "[]"),
        )

    def update_feed_status(
        self,
        feed_url: str,
        feed_name: str,
        success: bool,
        error: str | None = None,
    ) -> None:
        """Track feed fetch status."""
        with self._connection() as conn:
            now = datetime.utcnow().isoformat()
            
            if success:
                conn.execute("""
                    INSERT INTO feed_status (feed_url, feed_name, last_checked, last_success, consecutive_failures)
                    VALUES (?, ?, ?, ?, 0)
                    ON CONFLICT(feed_url) DO UPDATE SET
                        feed_name = excluded.feed_name,
                        last_checked = excluded.last_checked,
                        last_success = excluded.last_success,
                        consecutive_failures = 0
                """, (feed_url, feed_name, now, now))
            else:
                conn.execute("""
                    INSERT INTO feed_status (feed_url, feed_name, last_checked, last_error, consecutive_failures)
                    VALUES (?, ?, ?, ?, 1)
                    ON CONFLICT(feed_url) DO UPDATE SET
                        feed_name = excluded.feed_name,
                        last_checked = excluded.last_checked,
                        last_error = ?,
                        consecutive_failures = consecutive_failures + 1
                """, (feed_url, feed_name, now, error, error))
```

- [ ] Create `src/storage/db.py`
- [ ] Test database creation with `Database(Path("data/test.db"))`

### 1.2 Feed Fetcher

Create `src/ingest/feeds.py`:

```python
"""
RSS feed fetching with error handling and timeout management.
"""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

import feedparser
from dateutil.parser import parse as parse_date

from src.logging_config import get_logger
from src.models import Article

logger = get_logger("feeds")


class FeedResult(NamedTuple):
    """Result of fetching a feed."""
    
    feed_url: str
    feed_name: str
    articles: list[Article]
    success: bool
    error: str | None = None


def generate_article_id(url: str) -> str:
    """Generate a unique ID for an article based on its URL."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def fetch_feed(
    feed_url: str,
    feed_name: str,
    category: str = "Uncategorized",
    lookback_hours: int = 48,
    max_articles: int = 10,
    timeout: int = 30,
) -> FeedResult:
    """
    Fetch and parse an RSS feed.
    
    Args:
        feed_url: URL of the RSS feed
        feed_name: Human-readable name for the feed
        category: Category to assign to articles
        lookback_hours: Only include articles from this many hours ago
        max_articles: Maximum number of articles to return
        timeout: Request timeout in seconds
    
    Returns:
        FeedResult with articles or error information
    """
    logger.info(f"Fetching feed: {feed_name}")
    
    try:
        # feedparser handles timeouts via request_headers
        feed = feedparser.parse(
            feed_url,
            request_headers={"User-Agent": "FeedAgent/1.0"},
        )
        
        # Check for feed-level errors
        if feed.bozo and feed.bozo_exception:
            error_msg = str(feed.bozo_exception)
            # Some bozo exceptions are recoverable (e.g., CharacterEncodingOverride)
            if not feed.entries:
                logger.warning(f"Feed error for {feed_name}: {error_msg}")
                return FeedResult(
                    feed_url=feed_url,
                    feed_name=feed_name,
                    articles=[],
                    success=False,
                    error=error_msg,
                )
        
        # Determine feed title
        actual_feed_name = feed.feed.get("title", feed_name)
        
        # Calculate cutoff time
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        
        articles: list[Article] = []
        
        for entry in feed.entries[:max_articles * 2]:  # Fetch extra, filter by date
            # Parse publication date
            published = _parse_entry_date(entry)
            if published is None:
                logger.debug(f"Skipping entry without date: {entry.get('title', 'Unknown')}")
                continue
            
            # Skip old articles
            if published < cutoff:
                continue
            
            # Extract article URL
            url = entry.get("link", "")
            if not url:
                continue
            
            # Create article
            article = Article(
                id=generate_article_id(url),
                url=url,
                title=entry.get("title", "Untitled"),
                author=_extract_author(entry),
                feed_name=actual_feed_name,
                feed_url=feed_url,
                published=published,
                content="",  # Will be populated by parser
                category=category,
            )
            
            articles.append(article)
            
            if len(articles) >= max_articles:
                break
        
        logger.info(f"Found {len(articles)} new articles from {feed_name}")
        
        return FeedResult(
            feed_url=feed_url,
            feed_name=actual_feed_name,
            articles=articles,
            success=True,
        )
        
    except Exception as e:
        logger.error(f"Failed to fetch {feed_name}: {e}")
        return FeedResult(
            feed_url=feed_url,
            feed_name=feed_name,
            articles=[],
            success=False,
            error=str(e),
        )


def _parse_entry_date(entry: dict) -> datetime | None:
    """Parse publication date from feed entry."""
    # Try different date fields
    for field in ["published_parsed", "updated_parsed", "created_parsed"]:
        if parsed := entry.get(field):
            try:
                from time import mktime
                return datetime.fromtimestamp(mktime(parsed), tz=timezone.utc)
            except (ValueError, OverflowError):
                continue
    
    # Try string parsing as fallback
    for field in ["published", "updated", "created"]:
        if date_str := entry.get(field):
            try:
                return parse_date(date_str)
            except (ValueError, ParserError):
                continue
    
    return None


def _extract_author(entry: dict) -> str:
    """Extract author name from feed entry."""
    # Try author field
    if author := entry.get("author"):
        return author
    
    # Try author_detail
    if author_detail := entry.get("author_detail"):
        if name := author_detail.get("name"):
            return name
    
    # Try authors list
    if authors := entry.get("authors"):
        if authors and (name := authors[0].get("name")):
            return name
    
    return "Unknown"


def fetch_all_feeds(
    feeds_config: dict[str, dict],
    lookback_hours: int = 48,
    max_articles_per_feed: int = 10,
) -> list[FeedResult]:
    """
    Fetch all configured feeds.
    
    Args:
        feeds_config: Dictionary of feed configurations
        lookback_hours: Only include articles from this many hours ago
        max_articles_per_feed: Maximum articles per feed
    
    Returns:
        List of FeedResults
    """
    results: list[FeedResult] = []
    
    for feed_name, config in feeds_config.items():
        url = config.get("url")
        if not url:
            logger.warning(f"Feed {feed_name} has no URL configured")
            continue
        
        category = config.get("category", "Uncategorized")
        
        result = fetch_feed(
            feed_url=url,
            feed_name=feed_name,
            category=category,
            lookback_hours=lookback_hours,
            max_articles=max_articles_per_feed,
        )
        
        results.append(result)
    
    return results
```

- [ ] Create `src/ingest/feeds.py`
- [ ] Test with a single feed URL

### 1.3 Content Parser

Create `src/ingest/parser.py`:

```python
"""
Article content extraction and cleaning.

Handles HTML parsing, text extraction, and content normalization.
"""

import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from src.logging_config import get_logger
from src.models import Article

logger = get_logger("parser")

# Tags to remove entirely (including content)
REMOVE_TAGS = {
    "script", "style", "nav", "header", "footer", "aside",
    "form", "button", "input", "iframe", "noscript",
    "svg", "canvas", "video", "audio",
}

# Tags that typically contain the main content
CONTENT_TAGS = {"article", "main", "div.post-content", "div.entry-content"}

# Minimum word count to consider content valid
MIN_WORD_COUNT = 50


def fetch_article_content(article: Article, timeout: int = 30) -> Article:
    """
    Fetch and parse the full content of an article.
    
    Args:
        article: Article with URL to fetch
        timeout: Request timeout in seconds
    
    Returns:
        Article with content and word_count populated
    """
    logger.debug(f"Fetching content: {article.title}")
    
    try:
        response = httpx.get(
            str(article.url),
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        response.raise_for_status()
        
        html = response.text
        content = extract_text_content(html, str(article.url))
        word_count = len(content.split())
        
        # Update article
        article.content = content
        article.word_count = word_count
        
        logger.debug(f"Extracted {word_count} words from {article.title}")
        
        return article
        
    except httpx.HTTPError as e:
        logger.warning(f"HTTP error fetching {article.url}: {e}")
        return article
    except Exception as e:
        logger.error(f"Error fetching {article.url}: {e}")
        return article


def extract_text_content(html: str, base_url: str = "") -> str:
    """
    Extract clean text content from HTML.
    
    Args:
        html: Raw HTML string
        base_url: Base URL for resolving relative links
    
    Returns:
        Cleaned text content
    """
    soup = BeautifulSoup(html, "lxml")
    
    # Remove unwanted tags
    for tag in soup.find_all(REMOVE_TAGS):
        tag.decompose()
    
    # Try to find main content container
    content_element = None
    
    # Try Substack-specific selectors first
    for selector in [
        "div.body.markup",           # Substack posts
        "article.post",              # Many blogs
        "div.post-content",          # Common pattern
        "article",                   # Semantic HTML
        "main",                      # Semantic HTML
        "div.entry-content",         # WordPress
        "div.article-content",       # News sites
    ]:
        if "." in selector:
            tag, class_name = selector.split(".", 1)
            content_element = soup.find(tag, class_=class_name)
        else:
            content_element = soup.find(selector)
        
        if content_element:
            break
    
    # Fall back to body
    if not content_element:
        content_element = soup.body or soup
    
    # Extract text with some structure
    text_parts: list[str] = []
    
    for element in content_element.descendants:
        if element.name in {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote"}:
            text = element.get_text(separator=" ", strip=True)
            if text:
                # Add heading markers for context
                if element.name.startswith("h"):
                    text = f"\n## {text}\n"
                elif element.name == "blockquote":
                    text = f"> {text}"
                text_parts.append(text)
    
    # Join and clean
    content = "\n\n".join(text_parts)
    content = clean_text(content)
    
    return content


def clean_text(text: str) -> str:
    """
    Clean and normalize text content.
    
    - Remove excessive whitespace
    - Normalize unicode
    - Remove common artifacts
    """
    # Normalize unicode whitespace
    text = re.sub(r"[\u00a0\u2000-\u200b\u2028\u2029\u202f\u205f\u3000]", " ", text)
    
    # Remove excessive newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    
    # Remove excessive spaces
    text = re.sub(r" {2,}", " ", text)
    
    # Remove common newsletter artifacts
    patterns_to_remove = [
        r"Subscribe to .+? newsletter",
        r"Share this post",
        r"Leave a comment",
        r"Read more at .+",
        r"Click here to .+",
        r"Unsubscribe",
        r"View in browser",
        r"Forward to a friend",
    ]
    
    for pattern in patterns_to_remove:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    
    return text.strip()


def process_articles(
    articles: list[Article],
    fetch_content: bool = True,
    min_word_count: int = MIN_WORD_COUNT,
) -> list[Article]:
    """
    Process a list of articles, optionally fetching content.
    
    Args:
        articles: List of articles to process
        fetch_content: Whether to fetch full article content
        min_word_count: Minimum words to keep article
    
    Returns:
        List of processed articles (may be fewer than input)
    """
    processed: list[Article] = []
    
    for article in articles:
        if fetch_content:
            article = fetch_article_content(article)
        
        # Skip articles with too little content
        if article.word_count < min_word_count:
            logger.debug(f"Skipping article with {article.word_count} words: {article.title}")
            continue
        
        processed.append(article)
    
    return processed
```

- [ ] Create `src/ingest/parser.py`
- [ ] Test content extraction with a Substack article URL

### 1.4 Ingestion Orchestrator

Create `src/ingest/__init__.py`:

```python
"""
Content ingestion module.

Coordinates feed fetching, content parsing, and storage.
"""

from datetime import datetime, timezone
from pathlib import Path

from src.config import FeedConfig, get_settings
from src.logging_config import get_logger
from src.models import Article, ArticleStatus, DigestStats
from src.storage.db import Database

from .feeds import fetch_all_feeds
from .parser import process_articles

logger = get_logger("ingest")

__all__ = ["run_ingestion", "IngestResult"]


class IngestResult:
    """Result of an ingestion run."""
    
    def __init__(self):
        self.feeds_checked: int = 0
        self.feeds_successful: int = 0
        self.feeds_failed: int = 0
        self.articles_found: int = 0
        self.articles_new: int = 0
        self.articles_processed: int = 0
        self.errors: list[str] = []
        self.duration_seconds: float = 0.0
    
    def __str__(self) -> str:
        return (
            f"Ingestion: {self.feeds_successful}/{self.feeds_checked} feeds, "
            f"{self.articles_new} new articles ({self.duration_seconds:.1f}s)"
        )


def run_ingestion(
    db: Database | None = None,
    feed_config: FeedConfig | None = None,
    fetch_content: bool = True,
) -> IngestResult:
    """
    Run the full ingestion pipeline.
    
    1. Load feed configuration
    2. Fetch all feeds
    3. Parse and extract content
    4. Deduplicate and store
    
    Args:
        db: Database instance (creates one if not provided)
        feed_config: Feed configuration (loads from default if not provided)
        fetch_content: Whether to fetch full article content
    
    Returns:
        IngestResult with statistics
    """
    import time
    start_time = time.time()
    
    settings = get_settings()
    result = IngestResult()
    
    # Initialize database if needed
    if db is None:
        db = Database(settings.data_dir / "articles.db")
    
    # Load feed config if needed
    if feed_config is None:
        feed_config = FeedConfig(settings.config_dir / "feeds.yaml")
    
    feeds = feed_config.feeds
    if not feeds:
        logger.warning("No feeds configured")
        return result
    
    logger.info(f"Starting ingestion for {len(feeds)} feeds")
    result.feeds_checked = len(feeds)
    
    # Fetch all feeds
    feed_results = fetch_all_feeds(
        feeds_config=feeds,
        lookback_hours=settings.lookback_hours,
        max_articles_per_feed=settings.max_articles_per_feed,
    )
    
    # Process each feed result
    all_articles: list[Article] = []
    
    for feed_result in feed_results:
        # Update feed status in database
        db.update_feed_status(
            feed_url=feed_result.feed_url,
            feed_name=feed_result.feed_name,
            success=feed_result.success,
            error=feed_result.error,
        )
        
        if feed_result.success:
            result.feeds_successful += 1
            all_articles.extend(feed_result.articles)
        else:
            result.feeds_failed += 1
            result.errors.append(f"{feed_result.feed_name}: {feed_result.error}")
    
    result.articles_found = len(all_articles)
    logger.info(f"Found {result.articles_found} articles from {result.feeds_successful} feeds")
    
    # Deduplicate against existing articles
    new_articles: list[Article] = []
    for article in all_articles:
        if not db.article_exists(article.id):
            new_articles.append(article)
    
    result.articles_new = len(new_articles)
    logger.info(f"{result.articles_new} articles are new")
    
    if not new_articles:
        result.duration_seconds = time.time() - start_time
        return result
    
    # Fetch and process content
    if fetch_content:
        logger.info("Fetching article content...")
        new_articles = process_articles(new_articles, fetch_content=True)
    
    result.articles_processed = len(new_articles)
    
    # Store articles
    for article in new_articles:
        db.save_article(article)
    
    logger.info(f"Stored {result.articles_processed} articles")
    
    result.duration_seconds = time.time() - start_time
    logger.info(str(result))
    
    return result
```

- [ ] Create `src/ingest/__init__.py`

### 1.5 Test Ingestion

Create `scripts/test_ingest.py`:

```python
"""Test the ingestion pipeline with real feeds."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import FeedConfig, get_settings
from src.ingest import run_ingestion
from src.logging_config import setup_logging
from src.storage.db import Database


def main() -> None:
    """Run a test ingestion."""
    setup_logging("DEBUG")
    settings = get_settings()
    
    print("=" * 60)
    print("Testing Ingestion Pipeline")
    print("=" * 60)
    
    # Use test database
    db_path = settings.data_dir / "test_articles.db"
    db = Database(db_path)
    print(f"\nUsing database: {db_path}")
    
    # Load feeds
    feed_config = FeedConfig(settings.config_dir / "feeds.yaml")
    feeds = feed_config.feeds
    print(f"Found {len(feeds)} configured feeds:")
    for name, config in feeds.items():
        print(f"  • {name}: {config.get('url', 'NO URL')}")
    
    print("\n" + "-" * 60)
    print("Running ingestion...")
    print("-" * 60 + "\n")
    
    result = run_ingestion(db=db, feed_config=feed_config)
    
    print("\n" + "=" * 60)
    print("Results")
    print("=" * 60)
    print(f"Feeds checked:    {result.feeds_checked}")
    print(f"Feeds successful: {result.feeds_successful}")
    print(f"Feeds failed:     {result.feeds_failed}")
    print(f"Articles found:   {result.articles_found}")
    print(f"Articles new:     {result.articles_new}")
    print(f"Articles stored:  {result.articles_processed}")
    print(f"Duration:         {result.duration_seconds:.2f}s")
    
    if result.errors:
        print("\nErrors:")
        for error in result.errors:
            print(f"  ✗ {error}")
    
    # Show sample articles
    print("\n" + "-" * 60)
    print("Sample Articles")
    print("-" * 60)
    
    articles = db.get_pending_articles(limit=5)
    for article in articles:
        print(f"\n📰 {article.title}")
        print(f"   Author: {article.author}")
        print(f"   Feed: {article.feed_name}")
        print(f"   Words: {article.word_count}")
        print(f"   Published: {article.published}")
        if article.content:
            preview = article.content[:200].replace("\n", " ")
            print(f"   Preview: {preview}...")


if __name__ == "__main__":
    main()
```

- [ ] Create `scripts/test_ingest.py`
- [ ] Run `uv run python scripts/test_ingest.py`
- [ ] Verify articles are fetched and stored correctly

### 1.6 Unit Tests

Create `tests/test_ingest.py`:

```python
"""Tests for the ingestion module."""

import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from src.models import Article
from src.storage.db import Database
from src.ingest.feeds import generate_article_id, fetch_feed
from src.ingest.parser import clean_text, extract_text_content


class TestArticleId:
    """Tests for article ID generation."""
    
    def test_same_url_same_id(self):
        """Same URL should produce same ID."""
        url = "https://example.com/article"
        assert generate_article_id(url) == generate_article_id(url)
    
    def test_different_url_different_id(self):
        """Different URLs should produce different IDs."""
        url1 = "https://example.com/article1"
        url2 = "https://example.com/article2"
        assert generate_article_id(url1) != generate_article_id(url2)
    
    def test_id_length(self):
        """ID should be 16 characters."""
        url = "https://example.com/article"
        assert len(generate_article_id(url)) == 16


class TestDatabase:
    """Tests for database operations."""
    
    @pytest.fixture
    def db(self):
        """Create a temporary database."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            yield Database(db_path)
    
    def test_article_not_exists(self, db):
        """Non-existent article should return False."""
        assert not db.article_exists("nonexistent")
    
    def test_save_and_check_exists(self, db):
        """Saved article should exist."""
        article = Article(
            id="test123",
            url="https://example.com/test",
            title="Test Article",
            feed_name="Test Feed",
            feed_url="https://example.com/feed",
            published=datetime.now(timezone.utc),
        )
        
        assert db.save_article(article) is True
        assert db.article_exists("test123")
    
    def test_save_duplicate_returns_false(self, db):
        """Saving duplicate should return False."""
        article = Article(
            id="test123",
            url="https://example.com/test",
            title="Test Article",
            feed_name="Test Feed",
            feed_url="https://example.com/feed",
            published=datetime.now(timezone.utc),
        )
        
        assert db.save_article(article) is True
        assert db.save_article(article) is False


class TestTextCleaning:
    """Tests for text cleaning."""
    
    def test_removes_excessive_whitespace(self):
        """Should normalize whitespace."""
        text = "Hello    world"
        assert clean_text(text) == "Hello world"
    
    def test_removes_excessive_newlines(self):
        """Should reduce multiple newlines."""
        text = "Hello\n\n\n\nWorld"
        assert clean_text(text) == "Hello\n\nWorld"
    
    def test_removes_newsletter_artifacts(self):
        """Should remove common newsletter text."""
        text = "Great content here. Subscribe to our newsletter for more."
        cleaned = clean_text(text)
        assert "Subscribe" not in cleaned


class TestContentExtraction:
    """Tests for HTML content extraction."""
    
    def test_extracts_paragraph_text(self):
        """Should extract text from paragraphs."""
        html = "<html><body><p>Hello World</p></body></html>"
        content = extract_text_content(html)
        assert "Hello World" in content
    
    def test_removes_scripts(self):
        """Should remove script content."""
        html = "<html><body><script>alert('bad')</script><p>Good</p></body></html>"
        content = extract_text_content(html)
        assert "alert" not in content
        assert "Good" in content
    
    def test_preserves_headings(self):
        """Should mark headings."""
        html = "<html><body><h2>Title</h2><p>Content</p></body></html>"
        content = extract_text_content(html)
        assert "## Title" in content
```

- [ ] Create `tests/test_ingest.py`
- [ ] Run `uv run pytest tests/test_ingest.py -v`

---

## Completion Checklist

- [ ] Database creates tables correctly
- [ ] Feeds are fetched without errors
- [ ] Content is extracted from HTML
- [ ] Articles are deduplicated
- [ ] Articles are stored in database
- [ ] Test script shows sample articles
- [ ] Unit tests pass

## Troubleshooting

**Feed returns no articles**
- Check if the feed URL is correct (open in browser)
- Some feeds require specific User-Agent headers
- Increase `lookback_hours` for infrequent publishers

**Content extraction is empty**
- The site may block automated requests
- Try increasing timeout
- Check if site uses JavaScript rendering (may need Playwright)

**Database errors**
- Ensure `data/` directory exists
- Check file permissions

## Next Phase

Once ingestion is working reliably, proceed to `03-PHASE-ANALYZE.md` to implement Claude summarization.
