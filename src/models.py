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
    summary: str | None = Field(default=None, description="LLM-generated summary")
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
