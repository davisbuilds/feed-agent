"""
Article summarization using Google Gemini (via google-genai SDK).

Uses structured output for reliable JSON extraction.
"""

import json
from typing import TypedDict, Callable
import typing

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from src.config import get_settings
from src.logging_config import get_logger
from src.models import Article, ArticleStatus

from .prompts import ARTICLE_SUMMARY_SYSTEM, ARTICLE_SUMMARY_USER

logger = get_logger("summarizer")


class ArticleSummaryResponse(BaseModel):
    """Structured response from Gemini for article summaries."""
    
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
    """Handles article summarization with Google Gemini."""
    
    def __init__(self, api_key: str | None = None, model: str | None = None):
        if api_key is None or model is None:
            settings = get_settings()
            api_key = api_key or settings.google_api_key
            model = model or settings.gemini_model

        self.client = genai.Client(api_key=api_key)
        self.model_name = model
    
    def summarize_article(self, article: Article) -> SummaryResult:
        """
        Generate a summary for a single article.
        
        Args:
            article: Article to summarize
        
        Returns:
            SummaryResult with summary or error
        """
        logger.info(f"Summarizing: {article.title[:50]}...")
        
        # Truncate content if too long
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
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=ARTICLE_SUMMARY_SYSTEM,
                    response_mime_type="application/json",
                    response_schema=ArticleSummaryResponse,
                )
            )
            
            # Parse response - SDK automatically parses JSON for structured output
            # Check if parsed attribute exists, otherwise try text parsing
            if hasattr(response, "parsed") and response.parsed:
                parsed_obj = response.parsed
                # Convert pydantic object to dict if needed
                if isinstance(parsed_obj, BaseModel):
                    parsed = parsed_obj.model_dump()
                else:
                     parsed = parsed_obj
            else:
                 parsed = json.loads(response.text)

            
            # Estimate tokens
            usage = response.usage_metadata
            tokens_used = (usage.prompt_token_count or 0) + (usage.candidates_token_count or 0) if usage else 0
            
            logger.debug(f"Summary generated ({tokens_used} tokens)")
            
            return SummaryResult(
                success=True,
                article_id=article.id,
                summary=parsed.get("summary"),
                key_takeaways=parsed.get("key_takeaways", []),
                action_items=parsed.get("action_items", []),
                tokens_used=tokens_used,
                error=None,
            )
            
        except Exception as e:
            logger.error(f"Summarization error: {e}")
            return SummaryResult(
                success=False,
                article_id=article.id,
                summary=None,
                key_takeaways=[],
                action_items=[],
                tokens_used=0,
                error=str(e),
            )
    
    def summarize_batch(
        self, 
        articles: list[Article],
        on_progress: "Callable | None" = None,
    ) -> list[SummaryResult]:
        """
        Summarize multiple articles concurrently.
        
        Args:
            articles: List of articles to summarize
            on_progress: Optional callback(index, total, article) for progress
        
        Returns:
            List of SummaryResults
        """
        import concurrent.futures
        
        results: list[SummaryResult] = [None] * len(articles)
        total = len(articles)
        completed = 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            # Create a map of future -> index to maintain order and report progress
            future_to_index = {
                executor.submit(self.summarize_article, article): i 
                for i, article in enumerate(articles)
            }
            
            for future in concurrent.futures.as_completed(future_to_index):
                i = future_to_index[future]
                article = articles[i]
                
                # Report progress
                if on_progress:
                    on_progress(completed, total, article)
                
                try:
                    result = future.result()
                    results[i] = result
                except Exception as e:
                    logger.error(f"Error checking future for article {article.id}: {e}")
                    results[i] = SummaryResult(
                        success=False,
                        article_id=article.id,
                        summary=None,
                        key_takeaways=[],
                        action_items=[],
                        tokens_used=0,
                        error=str(e),
                    )
                
                completed += 1
        
        successful = sum(1 for r in results if r and r["success"])
        logger.info(f"Summarized {successful}/{total} articles")
        
        return results
