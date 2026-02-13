"""Tests for the analysis module."""

from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

import pytest

from src.analyze.digest_builder import DigestBuilder
from src.analyze.summarizer import Summarizer
from src.llm.base import LLMResponse
from src.models import Article
from src.storage.cache import CacheStore, make_cache_key


@pytest.fixture
def sample_article() -> Article:
    """Create a sample article for testing."""
    return Article(
        id="test123456789012",
        url="https://example.com/test",
        title="Test Article About AI",
        author="Test Author",
        feed_name="Test Feed",
        feed_url="https://example.com/feed",
        published=datetime.now(UTC),
        content="This is a test article about artificial intelligence and its impact on society. "
        * 20,
        word_count=200,
        category="Technology",
    )


class TestSummarizer:
    """Tests for the Summarizer class."""

    def test_summarize_article_success(self, sample_article: Article) -> None:
        """Test successful article summarization."""
        mock_client = Mock()
        mock_client.generate.return_value = LLMResponse(
            parsed={
                "summary": "Test summary",
                "key_takeaways": ["insight1"],
                "action_items": [],
                "topics": ["AI"],
                "sentiment": "neutral",
                "importance": 3,
            },
            raw_text="{}",
            input_tokens=100,
            output_tokens=50,
        )

        summarizer = Summarizer(client=mock_client)
        result = summarizer.summarize_article(sample_article)

        assert result["success"] is True
        assert result["summary"] == "Test summary"
        assert result["key_takeaways"] == ["insight1"]
        assert result["tokens_used"] == 150

    def test_summarize_article_handles_api_error(self, sample_article: Article) -> None:
        """Test handling of API errors."""
        mock_client = Mock()
        mock_client.generate.side_effect = Exception("API Error")

        summarizer = Summarizer(client=mock_client)
        result = summarizer.summarize_article(sample_article)

        assert result["success"] is False
        assert "API Error" in (result["error"] or "")


class TestDigestBuilder:
    """Tests for the DigestBuilder class."""

    def test_groups_articles_by_category(self, sample_article: Article) -> None:
        """Test that articles are grouped correctly."""
        articles = [
            sample_article,
            Article(
                id="test456789012345",
                url="https://example.com/test2",
                title="Another Article",
                author="Another Author",
                feed_name="Another Feed",
                feed_url="https://example.com/feed2",
                published=datetime.now(UTC),
                content="Different content",
                word_count=100,
                category="Business",
                summary="Test summary",
            ),
        ]

        mock_client = Mock()
        mock_client.generate.return_value = LLMResponse(
            parsed={
                "synthesis": "Category synthesis",
                "top_takeaways": [],
                "must_read": [],
                "overall_themes": [],
                "headline": "Headline",
                "must_read_overall": [],
            },
            raw_text="{}",
            input_tokens=50,
            output_tokens=25,
        )

        builder = DigestBuilder(client=mock_client)
        digest = builder.build_digest(articles)

        assert len(digest.categories) == 2
        category_names = {category.name for category in digest.categories}
        assert "Technology" in category_names
        assert "Business" in category_names


class TestSummarizerCache:
    """Tests for cache integration in Summarizer."""

    @pytest.fixture
    def cache(self):
        with TemporaryDirectory() as tmpdir:
            yield CacheStore(Path(tmpdir) / "test.db")

    def test_cache_hit_skips_llm_call(self, sample_article: Article, cache) -> None:
        """Cached summaries should be returned without calling LLM."""
        mock_client = Mock()
        model_name = "gemini-3-flash-preview"
        key = make_cache_key(sample_article.id, model_name)
        cached_data = {
            "success": True,
            "article_id": sample_article.id,
            "summary": "cached summary",
            "key_takeaways": ["cached insight"],
            "action_items": [],
            "tokens_used": 100,
            "error": None,
        }
        cache.set("summary", key, cached_data)

        summarizer = Summarizer(client=mock_client)
        result = summarizer.summarize_article(
            sample_article, cache=cache, model_name=model_name
        )

        assert result["summary"] == "cached summary"
        assert result["key_takeaways"] == ["cached insight"]
        mock_client.generate.assert_not_called()

    def test_cache_miss_calls_llm_and_stores(self, sample_article: Article, cache) -> None:
        """Cache miss should call LLM and store the result."""
        mock_client = Mock()
        mock_client.generate.return_value = LLMResponse(
            parsed={
                "summary": "fresh summary",
                "key_takeaways": ["new"],
                "action_items": [],
                "topics": ["AI"],
                "sentiment": "neutral",
                "importance": 3,
            },
            raw_text="{}",
            input_tokens=100,
            output_tokens=50,
        )
        model_name = "gemini-3-flash-preview"
        key = make_cache_key(sample_article.id, model_name)

        summarizer = Summarizer(client=mock_client)
        result = summarizer.summarize_article(
            sample_article, cache=cache, model_name=model_name
        )

        assert result["summary"] == "fresh summary"
        mock_client.generate.assert_called_once()

        # Verify it was stored
        cached = cache.get("summary", key)
        assert cached is not None
        assert cached["summary"] == "fresh summary"

    def test_no_cache_still_works(self, sample_article: Article) -> None:
        """Summarizer should work without a cache (backward compatible)."""
        mock_client = Mock()
        mock_client.generate.return_value = LLMResponse(
            parsed={
                "summary": "normal summary",
                "key_takeaways": [],
                "action_items": [],
                "topics": [],
                "sentiment": "neutral",
                "importance": 3,
            },
            raw_text="{}",
            input_tokens=10,
            output_tokens=5,
        )

        summarizer = Summarizer(client=mock_client)
        result = summarizer.summarize_article(sample_article)

        assert result["success"] is True
        assert result["summary"] == "normal summary"
