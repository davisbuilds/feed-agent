"""Article summarization via provider-agnostic LLM client."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from src.storage.cache import CacheStore

from pydantic import BaseModel, Field

from src.config import get_settings
from src.llm import LLMClient, create_client
from src.logging_config import get_logger
from src.models import Article

from .prompts import ARTICLE_SUMMARY_SYSTEM, ARTICLE_SUMMARY_USER

logger = get_logger("summarizer")


class ArticleSummaryResponse(BaseModel):
    """Structured response schema for article summaries."""

    summary: str = Field(..., description="2-3 sentence summary")
    key_takeaways: list[str] = Field(description="Up to 5 key insights")
    action_items: list[str] = Field(description="Up to 3 actionable items")
    topics: list[str] = Field(description="Up to 5 topics")
    sentiment: str = Field(description="positive, negative, neutral, or mixed")
    importance: int = Field(description="1-5 scale of importance")


class SummaryResult(TypedDict):
    """Result of summarizing an article."""

    success: bool
    article_id: str
    summary: str | None
    key_takeaways: list[str]
    action_items: list[str]
    tokens_used: int
    error: str | None


class Summarizer:
    """Handles article summarization with an LLM provider client."""

    def __init__(self, client: LLMClient | None = None):
        if client is None:
            settings = get_settings()
            client = create_client(
                provider=settings.llm_provider,
                api_key=settings.llm_api_key,
                model=settings.llm_model,
            )

        self.client = client

    def summarize_article(
        self,
        article: Article,
        cache: CacheStore | None = None,
        model_name: str | None = None,
    ) -> SummaryResult:
        """Generate a summary for a single article."""
        # Check cache first
        if cache and model_name:
            from src.storage.cache import make_cache_key

            cache_key = make_cache_key(article.id, model_name)
            try:
                cached = cache.get("summary", cache_key)
                if cached is not None:
                    logger.info(f"Cache hit: {article.title[:50]}...")
                    return SummaryResult(**cached)
            except Exception as exc:
                logger.warning(f"Cache read failed, falling through to LLM: {exc}")
                cache_key = None
        else:
            cache_key = None

        logger.info(f"Summarizing: {article.title[:50]}...")

        content = article.content
        if len(content) > 30000:
            content = content[:30000] + "\n\n[Content truncated...]"

        user_prompt = ARTICLE_SUMMARY_USER.format(
            title=article.title,
            author=article.author,
            feed_name=article.feed_name,
            published=article.published.strftime("%Y-%m-%d"),
            content=content,
        )

        try:
            response = self.client.generate(
                prompt=user_prompt,
                system=ARTICLE_SUMMARY_SYSTEM,
                response_schema=ArticleSummaryResponse,
            )
            parsed = response.parsed
            tokens_used = response.input_tokens + response.output_tokens

            logger.debug(f"Summary generated ({tokens_used} tokens)")
            result = SummaryResult(
                success=True,
                article_id=article.id,
                summary=parsed.get("summary"),
                key_takeaways=parsed.get("key_takeaways", []),
                action_items=parsed.get("action_items", []),
                tokens_used=tokens_used,
                error=None,
            )

            # Store in cache on success
            if cache and cache_key:
                cache.set("summary", cache_key, dict(result))

            return result

        except Exception as exc:
            logger.error(f"Summarization error: {exc}")
            return SummaryResult(
                success=False,
                article_id=article.id,
                summary=None,
                key_takeaways=[],
                action_items=[],
                tokens_used=0,
                error=str(exc),
            )

    def summarize_batch(
        self,
        articles: list[Article],
        on_progress: Callable[[int, int, Article], None] | None = None,
        cache: CacheStore | None = None,
        model_name: str | None = None,
    ) -> list[SummaryResult]:
        """Summarize multiple articles concurrently."""
        if not articles:
            return []

        results: list[SummaryResult] = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_article = {
                executor.submit(
                    self.summarize_article, article, cache, model_name
                ): article for article in articles
            }

            for i, future in enumerate(as_completed(future_to_article)):
                article = future_to_article[future]
                if on_progress:
                    on_progress(i, len(articles), article)

                try:
                    result = future.result()
                    results.append(result)
                except Exception as exc:
                    logger.error(f"Failed to process {article.title}: {exc}")
                    results.append(
                        SummaryResult(
                            success=False,
                            article_id=article.id,
                            summary=None,
                            key_takeaways=[],
                            action_items=[],
                            tokens_used=0,
                            error=str(exc),
                        )
                    )

        result_map = {result["article_id"]: result for result in results}
        ordered_results: list[SummaryResult] = []
        for article in articles:
            ordered_results.append(
                result_map.get(
                    article.id,
                    SummaryResult(
                        success=False,
                        article_id=article.id,
                        summary=None,
                        key_takeaways=[],
                        action_items=[],
                        tokens_used=0,
                        error="Missing summary result",
                    ),
                )
            )
        return ordered_results
