"""Configuration management using Pydantic Settings."""

from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import AliasChoices, BaseModel, Field, HttpUrl, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.llm import PROVIDER_DEFAULTS

# XDG config directory for user configuration
XDG_CONFIG_PATH = Path.home() / ".config" / "feed"


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=[
            XDG_CONFIG_PATH / "config.env",  # User config (lower priority)
            ".env",  # Project .env (higher priority)
        ],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    llm_provider: Literal["gemini", "openai", "anthropic"] = Field(
        default="gemini",
        description="LLM provider to use",
    )
    llm_api_key: str = Field(
        ...,
        min_length=1,
        validation_alias=AliasChoices("LLM_API_KEY", "GOOGLE_API_KEY"),
        description="API key for configured LLM provider",
    )
    llm_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_MODEL", "GEMINI_MODEL"),
        description="Model name for configured LLM provider",
    )

    # API Keys
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
    max_tokens_per_summary: int = Field(default=500, description="Max tokens per article summary")

    # Paths
    config_dir: Path = Field(default=Path("config"), description="Config directory")
    data_dir: Path = Field(default=Path("data"), description="Data directory")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")

    @property
    def google_api_key(self) -> str:
        """Backward-compatible alias for legacy Google API key access."""
        return self.llm_api_key

    @property
    def gemini_model(self) -> str:
        """Backward-compatible alias for legacy Gemini model access."""
        return self.llm_model or PROVIDER_DEFAULTS["gemini"]

    @model_validator(mode="after")
    def apply_llm_defaults(self) -> Self:
        """Fill provider-specific model defaults when omitted."""
        provider = self.llm_provider

        # Migration safety: if a legacy GEMINI_MODEL is present but the selected
        # provider is not Gemini, ignore it and apply the provider default.
        # This prevents accidentally passing a Gemini model name to OpenAI or
        # Anthropic during staged env-var migrations.
        if (
            provider != "gemini"
            and self.llm_model
            and self.llm_model == PROVIDER_DEFAULTS["gemini"]
        ):
            self.llm_model = None

        if self.llm_model is None:
            self.llm_model = PROVIDER_DEFAULTS[provider]
        return self

    @model_validator(mode="after")
    def ensure_directories(self) -> Self:
        """Create necessary directories if they don't exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self


class FeedEntry(BaseModel):
    """Validated feed entry from feeds.yaml."""

    url: HttpUrl = Field(..., description="RSS/Atom feed URL")
    category: str = Field(default="Uncategorized")
    priority: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = Field(default=None)

    model_config = {"extra": "allow"}


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

        with open(self.config_path) as file_handle:
            data = yaml.safe_load(file_handle) or {}

        if not isinstance(data, dict):
            raise ValueError("Invalid feeds.yaml: top-level structure must be a mapping")

        raw_feeds = data.get("feeds", {})
        if raw_feeds is None:
            self._feeds = {}
            return
        if not isinstance(raw_feeds, dict):
            raise ValueError("Invalid feeds.yaml: 'feeds' must be a mapping")

        validated_feeds: dict[str, dict] = {}
        validation_errors: list[str] = []
        url_to_names: dict[str, list[str]] = {}

        for raw_name, raw_feed in raw_feeds.items():
            feed_name = str(raw_name).strip()
            if not feed_name:
                validation_errors.append("Feed name cannot be empty")
                continue
            if not isinstance(raw_feed, dict):
                validation_errors.append(f"{feed_name}: feed configuration must be a mapping")
                continue

            try:
                parsed = FeedEntry.model_validate(raw_feed)
            except ValidationError as exc:
                details = "; ".join(
                    f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}"
                    for err in exc.errors()
                )
                validation_errors.append(f"{feed_name}: {details}")
                continue

            entry = parsed.model_dump(mode="python")
            entry["url"] = str(parsed.url)
            validated_feeds[feed_name] = entry
            url_to_names.setdefault(entry["url"], []).append(feed_name)

        duplicate_url_errors = [
            f"Duplicate feed URL {url}: {', '.join(names)}"
            for url, names in url_to_names.items()
            if len(names) > 1
        ]
        validation_errors.extend(duplicate_url_errors)

        if validation_errors:
            rendered = "\n  - ".join(validation_errors)
            raise ValueError(f"Invalid feeds.yaml entries:\n  - {rendered}")

        self._feeds = validated_feeds

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


_settings: Settings | None = None


def get_settings() -> Settings:
    """Get application settings (singleton)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
