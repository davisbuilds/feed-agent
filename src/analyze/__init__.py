"""Analysis module - LLM-powered intelligence layer."""

from datetime import UTC, datetime, timedelta
from typing import NamedTuple

from src.config import get_settings
from src.llm import create_client
from src.logging_config import get_logger
from src.models import Article, ArticleStatus, DailyDigest
from src.storage.db import Database

from .digest_builder import DigestBuilder
from .summarizer import Summarizer

logger = get_logger("analyze")

__all__ = ["run_analysis", "AnalysisResult"]


class AnalysisResult(NamedTuple):
    """Result of the analysis pipeline."""

    digest: DailyDigest | None
    articles_analyzed: int
    tokens_used: int
    cost_estimate_usd: float
    duration_seconds: float
    errors: list[str]


COST_PER_1K_TOKENS: dict[str, dict[str, float]] = {
    "gemini": {"input": 0.000075, "output": 0.00030},
    "openai": {"input": 0.000150, "output": 0.00060},
    "anthropic": {"input": 0.003000, "output": 0.01500},
}


def run_analysis(
    db: Database | None = None,
    lookback_hours: int | None = None,
    no_cache: bool = False,
) -> AnalysisResult:
    """Run the full analysis pipeline."""
    import time

    start_time = time.time()

    settings = get_settings()
    lookback_hours = lookback_hours or settings.lookback_hours
    provider = settings.llm_provider
    api_key = settings.llm_api_key
    model = settings.llm_model

    errors: list[str] = []
    total_tokens = 0

    if db is None:
        db = Database(settings.data_dir / "articles.db")

    # Set up cache unless disabled
    cache = None
    if not no_cache:
        from src.storage.cache import CacheStore

        cache = CacheStore(
            db_path=settings.data_dir / "articles.db",
            default_ttl_days=settings.cache_ttl_days,
        )

    since = datetime.now(UTC) - timedelta(hours=lookback_hours)
    articles = db.get_articles_since(since, status=ArticleStatus.PENDING)

    if not articles:
        logger.info("No pending articles to analyze")
        return AnalysisResult(
            digest=None,
            articles_analyzed=0,
            tokens_used=0,
            cost_estimate_usd=0.0,
            duration_seconds=time.time() - start_time,
            errors=[],
        )

    logger.info(f"Analyzing {len(articles)} articles")

    llm_client = create_client(
        provider=provider,
        api_key=api_key,
        model=model,
        max_retries=settings.llm_retries,
    )
    summarizer = Summarizer(client=llm_client)
    digest_builder = DigestBuilder(client=llm_client)

    summarized_articles: list[Article] = []

    def on_progress(i: int, total: int, article: Article) -> None:
        logger.info(f"[{i + 1}/{total}] {article.title[:40]}...")

    summary_results = summarizer.summarize_batch(
        articles,
        on_progress=on_progress,
        cache=cache,
        model_name=model,
    )

    for article, result in zip(articles, summary_results, strict=False):
        total_tokens += result["tokens_used"]

        if result["success"]:
            article.summary = result["summary"]
            article.key_takeaways = result["key_takeaways"]
            article.action_items = result["action_items"]
            article.status = ArticleStatus.SUMMARIZED

            db.update_article_summary(
                article_id=article.id,
                summary=result["summary"] or "",
                key_takeaways=result["key_takeaways"],
                action_items=result["action_items"],
            )

            summarized_articles.append(article)
        else:
            db.update_article_status(article.id, ArticleStatus.FAILED)
            errors.append(f"Failed to summarize: {article.title[:30]} - {result['error']}")

    if not summarized_articles:
        logger.warning("No articles were successfully summarized")
        return AnalysisResult(
            digest=None,
            articles_analyzed=0,
            tokens_used=total_tokens,
            cost_estimate_usd=_estimate_cost(total_tokens, provider),
            duration_seconds=time.time() - start_time,
            errors=errors,
        )

    logger.info("Building digest...")
    digest = digest_builder.build_digest(summarized_articles)

    synthesis_tokens = 2000 * len(digest.categories)
    total_tokens += synthesis_tokens

    duration = time.time() - start_time
    digest.processing_time_seconds = duration

    logger.info(
        f"Analysis complete: {len(summarized_articles)} articles, "
        f"{total_tokens} tokens, {duration:.1f}s"
    )

    return AnalysisResult(
        digest=digest,
        articles_analyzed=len(summarized_articles),
        tokens_used=total_tokens,
        cost_estimate_usd=_estimate_cost(total_tokens, provider),
        duration_seconds=duration,
        errors=errors,
    )


def _estimate_cost(tokens: int, provider: str = "gemini") -> float:
    """Estimate API cost (rough, assumes 70/30 input/output token split)."""
    pricing = COST_PER_1K_TOKENS.get(provider, COST_PER_1K_TOKENS["gemini"])
    input_tokens = tokens * 0.7
    output_tokens = tokens * 0.3
    return ((input_tokens / 1000) * pricing["input"]) + ((output_tokens / 1000) * pricing["output"])
