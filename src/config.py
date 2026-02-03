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
    google_api_key: str = Field(..., min_length=1, description="Google Gemini API key")
    resend_api_key: str = Field(..., min_length=1, description="Resend API key")

    # Email
    email_from: str = Field(..., min_length=1, description="Sender email address")
    email_to: str = Field(..., min_length=1, description="Recipient email address")

    # Scheduling
    digest_hour: int = Field(default=7, ge=0, le=23, description="Hour to send digest (0-23)")
    digest_timezone: str = Field(default="America/New_York", description="Timezone for scheduling")

    # Processing
    max_articles_per_feed: int = Field(default=10, description="Max articles to fetch per feed")
    lookback_hours: int = Field(default=24, description="Hours to look back for new articles")
    
    # Gemini
    gemini_model: str = Field(default="gemini-3-flash-preview", description="Gemini model to use")
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
