"""SQLite-backed response cache with TTL."""

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Generator

from src.logging_config import get_logger

logger = get_logger("cache")


def make_cache_key(article_id: str, model: str) -> str:
    """Build a deterministic cache key from article ID and model name."""
    raw = f"{article_id}:{model}"
    return hashlib.sha256(raw.encode()).hexdigest()


class CacheStore:
    """SQLite-backed cache with TTL expiration."""

    def __init__(self, db_path: Path, default_ttl_days: int = 7):
        self.db_path = db_path
        self.default_ttl_days = default_ttl_days
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self._connection() as conn:
            conn.executescript("""
                PRAGMA journal_mode=WAL;

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
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get(self, kind: str, key: str) -> dict[str, Any] | None:
        """Get a cached value. Returns None if missing or expired."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as conn:
            row = conn.execute(
                "SELECT value FROM cache WHERE kind = ? AND key = ? AND expires_at > ?",
                (kind, key, now),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row["value"])

    def set(
        self,
        kind: str,
        key: str,
        value: dict[str, Any],
        ttl_days: int | None = None,
    ) -> None:
        """Store a value with TTL. Overwrites existing entries."""
        ttl = ttl_days if ttl_days is not None else self.default_ttl_days
        expires_at = datetime.now(timezone.utc) + timedelta(days=ttl)
        with self._connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO cache (kind, key, value, expires_at)
                   VALUES (?, ?, ?, ?)""",
                (kind, key, json.dumps(value), expires_at.isoformat()),
            )
            # Lazy cleanup of expired rows
            conn.execute(
                "DELETE FROM cache WHERE expires_at <= ?",
                (datetime.now(timezone.utc).isoformat(),),
            )

    def clear(self, kind: str | None = None) -> int:
        """Delete cached entries. Returns count deleted."""
        with self._connection() as conn:
            if kind:
                cursor = conn.execute("DELETE FROM cache WHERE kind = ?", (kind,))
            else:
                cursor = conn.execute("DELETE FROM cache")
            return cursor.rowcount

    def stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
            expired = conn.execute(
                "SELECT COUNT(*) FROM cache WHERE expires_at <= ?", (now,)
            ).fetchone()[0]
        return {
            "total_entries": total,
            "expired_entries": expired,
        }
