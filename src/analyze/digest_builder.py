"""Builds the daily digest by synthesizing summarized articles."""

from collections import defaultdict
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from src.config import get_settings
from src.llm import LLMClient, create_client
from src.logging_config import get_logger
from src.models import Article, CategoryDigest, DailyDigest

from .prompts import (
    CATEGORY_SYNTHESIS_USER,
    DIGEST_SYNTHESIS_SYSTEM,
    OVERALL_SYNTHESIS_SYSTEM,
    OVERALL_SYNTHESIS_USER,
)

logger = get_logger("digest_builder")


class CategorySynthesisResponse(BaseModel):
    """Structured response for category synthesis."""

    synthesis: str = Field(..., description="2-4 sentence summary of the category")
    top_takeaways: list[str] = Field(description="List of most important insights")
    must_read: list[str] = Field(description="URLs of must-read articles")


class OverallSynthesisResponse(BaseModel):
    """Structured response for overall digest synthesis."""

    overall_themes: list[str] = Field(description="List of major cross-cutting themes")
    headline: str = Field(..., description="Compelling one-sentence headline")
    must_read_overall: list[str] = Field(
        description="URLs of exceptionally valuable articles"
    )


class DigestBuilder:
    """Builds a complete daily digest from summarized articles."""

    def __init__(self, client: LLMClient | None = None):
        if client is None:
            settings = get_settings()
            client = create_client(
                provider=settings.llm_provider,
                api_key=settings.llm_api_key,
                model=settings.llm_model,
            )

        self.client = client

    def build_digest(self, articles: list[Article]) -> DailyDigest:
        """Build a complete daily digest from articles."""
        logger.info(f"Building digest from {len(articles)} articles")

        by_category: dict[str, list[Article]] = defaultdict(list)
        for article in articles:
            by_category[article.category].append(article)

        category_digests: list[CategoryDigest] = []
        for category_name, category_articles in sorted(by_category.items()):
            logger.info(f"Processing category: {category_name} ({len(category_articles)} articles)")
            category_digest = self._build_category_digest(category_name, category_articles)
            category_digests.append(category_digest)

        overall_themes, must_read = self._synthesize_overall(category_digests)

        digest = DailyDigest(
            id=str(uuid4())[:8],
            date=datetime.now(UTC),
            categories=category_digests,
            total_articles=len(articles),
            total_feeds=len({article.feed_url for article in articles}),
            overall_themes=overall_themes,
            must_read=must_read,
        )

        logger.info(
            f"Digest built: {digest.total_articles} articles, {len(digest.categories)} categories"
        )
        return digest

    def _build_category_digest(
        self,
        category_name: str,
        articles: list[Article],
    ) -> CategoryDigest:
        """Build digest for a single category."""
        summaries_text = "\n\n".join(
            [
                f"**{article.title}** ({article.feed_name})\n"
                f"URL: {article.url}\n"
                f"Summary: {article.summary or 'No summary available'}\n"
                "Key points: "
                f"{', '.join(article.key_takeaways) if article.key_takeaways else 'None'}"
                for article in articles
            ]
        )

        synthesis = ""
        top_takeaways: list[str] = []

        if len(articles) > 1:
            try:
                response = self.client.generate(
                    prompt=CATEGORY_SYNTHESIS_USER.format(
                        category=category_name,
                        article_summaries=summaries_text,
                    ),
                    system=DIGEST_SYNTHESIS_SYSTEM,
                    response_schema=CategorySynthesisResponse,
                )
                parsed = response.parsed
                synthesis = parsed.get("synthesis", "")
                top_takeaways = parsed.get("top_takeaways", [])
            except Exception as exc:
                logger.warning(f"Category synthesis failed: {exc}")
                synthesis = f"Today's {category_name} coverage includes {len(articles)} articles."
                for article in articles[:3]:
                    if article.key_takeaways:
                        top_takeaways.append(article.key_takeaways[0])
        else:
            article = articles[0]
            synthesis = article.summary or f"One article from {article.feed_name}."
            top_takeaways = article.key_takeaways[:3]

        return CategoryDigest(
            name=category_name,
            article_count=len(articles),
            articles=articles,
            synthesis=synthesis,
            top_takeaways=top_takeaways,
        )

    def _synthesize_overall(
        self,
        category_digests: list[CategoryDigest],
    ) -> tuple[list[str], list[str]]:
        """Generate overall themes across all categories."""
        if not category_digests:
            return [], []

        summaries_text = "\n\n".join(
            [
                f"**{digest.name}** ({digest.article_count} articles)\n"
                f"Synthesis: {digest.synthesis}\n"
                "Key takeaways: "
                f"{', '.join(digest.top_takeaways) if digest.top_takeaways else 'None'}"
                for digest in category_digests
            ]
        )

        try:
            response = self.client.generate(
                prompt=OVERALL_SYNTHESIS_USER.format(category_summaries=summaries_text),
                system=OVERALL_SYNTHESIS_SYSTEM,
                response_schema=OverallSynthesisResponse,
            )
            parsed = response.parsed
            return (parsed.get("overall_themes", []), parsed.get("must_read_overall", []))
        except Exception as exc:
            logger.warning(f"Overall synthesis failed: {exc}")
            return [], []
