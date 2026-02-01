"""Tests for the analysis module."""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from types import SimpleNamespace

from src.models import Article, ArticleStatus, CategoryDigest
from src.analyze.summarizer import Summarizer
from src.analyze.digest_builder import DigestBuilder


@pytest.fixture
def sample_article():
    """Create a sample article for testing."""
    return Article(
        id="test123456789012",
        url="https://example.com/test",
        title="Test Article About AI",
        author="Test Author",
        feed_name="Test Feed",
        feed_url="https://example.com/feed",
        published=datetime.now(timezone.utc),
        content="This is a test article about artificial intelligence and its impact on society. " * 20,
        word_count=200,
        category="Technology",
    )


class TestSummarizer:
    """Tests for the Summarizer class."""
    
    @patch("src.analyze.summarizer.genai.Client")
    def test_summarize_article_success(self, mock_client_cls, sample_article):
        """Test successful article summarization."""
        # Mock Gemini response
        mock_response = Mock()
        # Mock the parsed object that SDK returns
        mock_response.parsed = {
            "summary": "Test summary",
            "key_takeaways": ["insight1"],
            "action_items": [],
            "topics": ["AI"],
            "sentiment": "neutral",
            "importance": 3
        }
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50
        
        mock_client = Mock()
        mock_client.models.generate_content.return_value = mock_response
        mock_client_cls.return_value = mock_client
        
        summarizer = Summarizer(api_key="test-key", model="test-model")
        result = summarizer.summarize_article(sample_article)

        assert result["success"] is True
        assert result["summary"] == "Test summary"
        assert result["key_takeaways"] == ["insight1"]
        assert result["tokens_used"] == 150
    
    @patch("src.analyze.summarizer.genai.Client")
    def test_summarize_article_handles_api_error(self, mock_client_cls, sample_article):
        """Test handling of API errors."""
        mock_client = Mock()
        mock_client.models.generate_content.side_effect = Exception("API Error")
        mock_client_cls.return_value = mock_client
        
        summarizer = Summarizer(api_key="test-key", model="test-model")
        result = summarizer.summarize_article(sample_article)

        assert result["success"] is False
        assert "API Error" in result["error"]


class TestDigestBuilder:
    """Tests for the DigestBuilder class."""
    
    def test_groups_articles_by_category(self, sample_article):
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
                published=datetime.now(timezone.utc),
                content="Different content",
                word_count=100,
                category="Business",
                summary="Test summary",
            ),
        ]
        
        # We need to mock GenAI for the builder
        with patch("src.analyze.digest_builder.genai.Client"):
            builder = DigestBuilder(api_key="test-key", model="test-model")
            
            # Since we can't easily inspect private method logic without calling build_digest,
            # we'll mock the internal aggregation methods or just check the result structure.
            # But here we just want to verify the grouping logic works as part of build_digest.
            
            # Mock the generation calls to avoid errors
            mock_client = builder.client
            mock_response = Mock()
            mock_response.parsed = {
                "synthesis": "Category synthesis",
                "top_takeaways": [],
                "must_read": [],
                "overall_themes": [],
                "headline": "Headline",
                "must_read_overall": []
            }
            mock_client.models.generate_content.return_value = mock_response

            digest = builder.build_digest(articles)
            
            assert len(digest.categories) == 2
            category_names = {c.name for c in digest.categories}
            assert "Technology" in category_names
            assert "Business" in category_names
