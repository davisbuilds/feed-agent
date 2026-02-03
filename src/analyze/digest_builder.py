"""
Builds the daily digest by synthesizing summaries.
"""

import json
from collections import defaultdict
from datetime import datetime, timezone
from uuid import uuid4

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from src.config import get_settings
from src.logging_config import get_logger
from src.models import Article, ArticleStatus, CategoryDigest, DailyDigest

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
    must_read_overall: list[str] = Field(description="URLs of exceptionally valuable articles")


class DigestBuilder:
    """Builds a complete daily digest from summarized articles."""
    
    def __init__(self, api_key: str | None = None, model: str | None = None):
        if api_key is None or model is None:
            settings = get_settings()
            api_key = api_key or settings.google_api_key
            model = model or settings.gemini_model

        self.client = genai.Client(api_key=api_key)
        self.model_name = model
        
    def build_digest(self, articles: list[Article]) -> DailyDigest:
        """
        Build a complete daily digest from articles.
        
        Args:
            articles: List of summarized articles
        
        Returns:
            Complete DailyDigest ready for delivery
        """
        logger.info(f"Building digest from {len(articles)} articles")
        
        # Group by category
        by_category: dict[str, list[Article]] = defaultdict(list)
        for article in articles:
            by_category[article.category].append(article)
        
        # Build category digests
        category_digests: list[CategoryDigest] = []
        
        for category_name, category_articles in sorted(by_category.items()):
            logger.info(f"Processing category: {category_name} ({len(category_articles)} articles)")
            
            category_digest = self._build_category_digest(
                category_name, 
                category_articles,
            )
            category_digests.append(category_digest)
        
        # Generate overall synthesis
        overall_themes, must_read = self._synthesize_overall(category_digests)
        
        # Assemble final digest
        digest = DailyDigest(
            id=str(uuid4())[:8],
            date=datetime.now(timezone.utc),
            categories=category_digests,
            total_articles=len(articles),
            total_feeds=len({a.feed_url for a in articles}),
            overall_themes=overall_themes,
            must_read=must_read,
        )
        
        logger.info(f"Digest built: {digest.total_articles} articles, {len(digest.categories)} categories")
        
        return digest
    
    def _build_category_digest(
        self, 
        category_name: str, 
        articles: list[Article],
    ) -> CategoryDigest:
        """Build digest for a single category."""
        
        # Format article summaries
        summaries_text = "\n\n".join([
            f"**{a.title}** ({a.feed_name})\n"
            f"URL: {a.url}\n"
            f"Summary: {a.summary or 'No summary available'}\n"
            f"Key points: {', '.join(a.key_takeaways) if a.key_takeaways else 'None'}"
            for a in articles
        ])
        
        # Get synthesis from Gemini
        synthesis = ""
        top_takeaways: list[str] = []
        must_read: list[str] = []
        
        if len(articles) > 1:
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=CATEGORY_SYNTHESIS_USER.format(
                        category=category_name,
                        article_summaries=summaries_text,
                    ),
                    config=types.GenerateContentConfig(
                        system_instruction=DIGEST_SYNTHESIS_SYSTEM,
                        response_mime_type="application/json",
                        response_schema=CategorySynthesisResponse,
                        http_options=types.HttpOptions(timeout=120_000),
                    )
                )

                if hasattr(response, "parsed") and response.parsed:
                     parsed_obj = response.parsed
                     if isinstance(parsed_obj, BaseModel):
                         parsed = parsed_obj.model_dump()
                     else:
                        parsed = parsed_obj
                else:
                    parsed = json.loads(response.text)

                
                synthesis = parsed.get("synthesis", "")
                top_takeaways = parsed.get("top_takeaways", [])
                must_read = parsed.get("must_read", [])
                
            except Exception as e:
                logger.warning(f"Category synthesis failed: {e}")
                # Fall back to simple aggregation
                synthesis = f"Today's {category_name} coverage includes {len(articles)} articles."
                top_takeaways = []
                for a in articles[:3]:
                    if a.key_takeaways:
                        top_takeaways.append(a.key_takeaways[0])
        else:
            # Single article - use its summary directly
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
        
        # Format category summaries
        summaries_text = "\n\n".join([
            f"**{cd.name}** ({cd.article_count} articles)\n"
            f"Synthesis: {cd.synthesis}\n"
            f"Key takeaways: {', '.join(cd.top_takeaways) if cd.top_takeaways else 'None'}"
            for cd in category_digests
        ])
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=OVERALL_SYNTHESIS_USER.format(
                    category_summaries=summaries_text,
                ),
                config=types.GenerateContentConfig(
                    system_instruction=OVERALL_SYNTHESIS_SYSTEM,
                    response_mime_type="application/json",
                    response_schema=OverallSynthesisResponse,
                    http_options=types.HttpOptions(timeout=120_000),
                )
            )

            if hasattr(response, "parsed") and response.parsed:
                parsed_obj = response.parsed
                if isinstance(parsed_obj, BaseModel):
                    parsed = parsed_obj.model_dump()
                else:
                    parsed = parsed_obj

            else:
                 parsed = json.loads(response.text)
            
            return (
                parsed.get("overall_themes", []),
                parsed.get("must_read_overall", []),
            )
            
        except Exception as e:
            logger.warning(f"Overall synthesis failed: {e}")
            return [], []
