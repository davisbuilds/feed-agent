"""Tests for the ingestion module."""

import concurrent.futures
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, Mock

from src.models import Article, ArticleStatus
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


class TestAtomicSave:
    """Tests for atomic article save (DATA-1 fix)."""

    @pytest.fixture
    def db(self):
        """Create a temporary database."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            yield Database(db_path)

    def _make_article(self, id: str, url: str) -> Article:
        return Article(
            id=id,
            url=url,
            title="Test",
            feed_name="Feed",
            feed_url="https://example.com/feed",
            published=datetime.now(timezone.utc),
        )

    def test_concurrent_duplicate_saves(self, db):
        """Concurrent saves of the same article should not raise."""
        article = self._make_article("dup123", "https://example.com/dup")

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(db.save_article, article) for _ in range(4)]
            for f in concurrent.futures.as_completed(futures):
                results.append(f.result())

        # Exactly one should return True (inserted), rest False (ignored)
        assert results.count(True) == 1
        assert results.count(False) == 3

    def test_save_returns_false_for_duplicate_url(self, db):
        """Two articles with same URL should be deduplicated by UNIQUE constraint."""
        a1 = self._make_article("id_aaa", "https://example.com/same")
        a2 = self._make_article("id_bbb", "https://example.com/same")

        assert db.save_article(a1) is True
        # Same URL, different ID -- still rejected by url UNIQUE constraint
        # INSERT OR IGNORE handles this without raising
        assert db.save_article(a2) is False


class TestFeedTimeout:
    """Tests for feed fetching timeout (CONC-1 fix)."""

    @patch("src.ingest.feeds.httpx.get")
    def test_fetch_feed_uses_httpx_with_timeout(self, mock_get):
        """fetch_feed should use httpx.get with the timeout parameter."""
        mock_response = Mock()
        mock_response.content = b"<rss><channel><title>Test</title></channel></rss>"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        fetch_feed(
            feed_url="https://example.com/feed.xml",
            feed_name="Test",
            timeout=15,
        )

        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args
        assert call_kwargs.kwargs["timeout"] == 15
        assert call_kwargs.kwargs["follow_redirects"] is True

    @patch("src.ingest.feeds.httpx.get")
    def test_fetch_feed_handles_timeout_error(self, mock_get):
        """A timeout from httpx should produce a failed FeedResult, not a crash."""
        import httpx
        mock_get.side_effect = httpx.TimeoutException("timed out")

        result = fetch_feed(
            feed_url="https://example.com/slow-feed.xml",
            feed_name="Slow Feed",
            timeout=5,
        )

        assert result.success is False
        assert "timed out" in result.error


class TestFeedStatusTimestamp:
    """Tests for deprecated datetime.utcnow() replacement (DATA-2 fix)."""

    @pytest.fixture
    def db(self):
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            yield Database(db_path)

    def test_feed_status_uses_utc_aware_timestamp(self, db):
        """update_feed_status should store timezone-aware ISO timestamps."""
        db.update_feed_status(
            feed_url="https://example.com/feed",
            feed_name="Test Feed",
            success=True,
        )

        with db._connection() as conn:
            row = conn.execute(
                "SELECT last_checked FROM feed_status WHERE feed_url = ?",
                ("https://example.com/feed",),
            ).fetchone()

        ts = row[0]
        # datetime.now(timezone.utc).isoformat() includes +00:00
        assert "+00:00" in ts
