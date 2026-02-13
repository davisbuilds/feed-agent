"""
SQLite database operations for article storage.

Design decisions:
- Single file database for simplicity
- WAL mode for concurrent reads
- Indexes on common query patterns
"""

import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

from src.models import Article, ArticleStatus


class Database:
    """SQLite database wrapper for article storage."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
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

                -- Response cache with TTL
                CREATE TABLE IF NOT EXISTS cache (
                    kind TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT NOT NULL,
                    PRIMARY KEY (kind, key)
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
        Uses INSERT OR IGNORE for atomic deduplication.
        """
        with self._connection() as conn:
            cursor = conn.execute("""
                INSERT OR IGNORE INTO articles (
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
                json.dumps(article.key_takeaways or []),
                json.dumps(article.action_items or []),
            ))
        return cursor.rowcount > 0

    def get_pending_articles(self, limit: int = 100) -> list[Article]:
        """Get articles that need summarization."""
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
            now = datetime.now(timezone.utc).isoformat()
            
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
