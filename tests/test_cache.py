"""Tests for the response cache."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from src.storage.cache import CacheStore, make_cache_key


class TestMakeCacheKey:
    def test_deterministic(self):
        k1 = make_cache_key("article-1", "gemini-flash")
        k2 = make_cache_key("article-1", "gemini-flash")
        assert k1 == k2

    def test_different_article_different_key(self):
        k1 = make_cache_key("article-1", "gemini-flash")
        k2 = make_cache_key("article-2", "gemini-flash")
        assert k1 != k2

    def test_different_model_different_key(self):
        k1 = make_cache_key("article-1", "gemini-flash")
        k2 = make_cache_key("article-1", "gpt-4o-mini")
        assert k1 != k2

    def test_key_is_hex_string(self):
        key = make_cache_key("article-1", "gemini-flash")
        assert len(key) == 64  # SHA256 hex digest
        int(key, 16)  # should not raise


class TestCacheStore:
    @pytest.fixture
    def cache(self):
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            yield CacheStore(db_path, default_ttl_days=7)

    def test_get_missing_returns_none(self, cache):
        assert cache.get("summary", "nonexistent") is None

    def test_set_then_get(self, cache):
        data = {"summary": "test", "key_takeaways": ["a"]}
        cache.set("summary", "key1", data)

        result = cache.get("summary", "key1")

        assert result == data

    def test_get_expired_returns_none(self, cache):
        """Expired entries should not be returned."""
        data = {"summary": "old"}
        cache.set("summary", "key1", data, ttl_days=-1)  # already expired

        assert cache.get("summary", "key1") is None

    def test_different_kinds_are_separate(self, cache):
        cache.set("summary", "key1", {"a": 1})
        cache.set("other", "key1", {"b": 2})

        assert cache.get("summary", "key1") == {"a": 1}
        assert cache.get("other", "key1") == {"b": 2}

    def test_set_overwrites_existing(self, cache):
        cache.set("summary", "key1", {"v": 1})
        cache.set("summary", "key1", {"v": 2})

        assert cache.get("summary", "key1") == {"v": 2}

    def test_clear_all(self, cache):
        cache.set("summary", "k1", {"a": 1})
        cache.set("summary", "k2", {"b": 2})

        count = cache.clear()

        assert count == 2
        assert cache.get("summary", "k1") is None
        assert cache.get("summary", "k2") is None

    def test_clear_by_kind(self, cache):
        cache.set("summary", "k1", {"a": 1})
        cache.set("other", "k2", {"b": 2})

        count = cache.clear(kind="summary")

        assert count == 1
        assert cache.get("summary", "k1") is None
        assert cache.get("other", "k2") == {"b": 2}

    def test_stats_counts_active_entries(self, cache):
        cache.set("summary", "k1", {"a": 1})
        cache.set("summary", "k2", {"b": 2})

        stats = cache.stats()

        assert stats["total_entries"] == 2
        assert stats["expired_entries"] == 0

    def test_lazy_cleanup_removes_expired_on_set(self, cache):
        """Expired entries are cleaned up lazily on the next set() call."""
        cache.set("summary", "k1", {"a": 1}, ttl_days=-1)  # already expired

        # Not yet cleaned — but get() should still filter it
        assert cache.get("summary", "k1") is None

        # Next set() triggers cleanup
        cache.set("summary", "k2", {"b": 2})

        stats = cache.stats()
        assert stats["total_entries"] == 1  # only k2 remains
