"""
RSS feed fetching with error handling and timeout management.
"""

import hashlib
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import NamedTuple

import feedparser
import httpx
from dateutil.parser import parse as parse_date
from dateutil.parser import ParserError

from src.logging_config import get_logger
from src.models import Article

logger = get_logger("feeds")

FEED_AGENT_HEADERS = {
    "User-Agent": "FeedAgent/1.0",
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
}

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "application/rss+xml,application/atom+xml,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

BOT_FILTER_RETRY_STATUS_CODES = {403, 404}


class FeedResult(NamedTuple):
    """Result of fetching a feed."""
    
    feed_url: str
    feed_name: str
    articles: list[Article]
    success: bool
    error: str | None = None
    status_code: int | None = None
    final_url: str | None = None
    content_type: str | None = None
    attempts: int = 1
    response_time_ms: float | None = None
    entry_count: int = 0
    bozo: bool = False
    bozo_exception: str | None = None


def generate_article_id(url: str) -> str:
    """Generate a unique ID for an article based on its URL."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def fetch_feed(
    feed_url: str,
    feed_name: str,
    category: str = "Uncategorized",
    lookback_hours: int = 48,
    max_articles: int = 10,
    timeout: int = 30,
) -> FeedResult:
    """
    Fetch and parse an RSS feed.
    
    Args:
        feed_url: URL of the RSS feed
        feed_name: Human-readable name for the feed
        category: Category to assign to articles
        lookback_hours: Only include articles from this many hours ago
        max_articles: Maximum number of articles to return
        timeout: Request timeout in seconds
    
    Returns:
        FeedResult with articles or error information
    """
    logger.info(f"Fetching feed: {feed_name}")
    attempts = 0
    status_code: int | None = None
    final_url: str | None = None
    content_type: str | None = None
    response_time_ms: float | None = None
    attempt_summaries: list[str] = []

    try:
        response = None
        for profile_name, headers in (
            ("feed-agent", FEED_AGENT_HEADERS),
            ("browser", BROWSER_HEADERS),
        ):
            attempts += 1
            response, response_time_ms = _fetch_response(
                feed_url=feed_url,
                timeout=timeout,
                headers=headers,
            )
            status_code = response.status_code
            final_url = str(response.url)
            content_type = response.headers.get("content-type")
            attempt_summaries.append(f"{status_code} ({profile_name})")

            if status_code < 400:
                break

            # Some feed hosts/CDNs block simple bot user agents with false 404/403.
            if (
                status_code in BOT_FILTER_RETRY_STATUS_CODES
                and headers is FEED_AGENT_HEADERS
            ):
                logger.debug(
                    f"{feed_name}: got {status_code} with FeedAgent headers, retrying "
                    "with browser-like headers"
                )
                continue

            break

        if response is None:
            raise RuntimeError("Feed request did not produce a response")

        if response.status_code >= 400:
            error_msg = _format_http_error(response, attempt_summaries)
            logger.warning(f"Feed HTTP error for {feed_name}: {error_msg}")
            return FeedResult(
                feed_url=feed_url,
                feed_name=feed_name,
                articles=[],
                success=False,
                error=error_msg,
                status_code=response.status_code,
                final_url=str(response.url),
                content_type=response.headers.get("content-type"),
                attempts=attempts,
                response_time_ms=response_time_ms,
            )

        feed = feedparser.parse(response.content)

        # Check for feed-level errors
        bozo_exception = str(feed.bozo_exception) if feed.bozo and feed.bozo_exception else None
        if feed.bozo and feed.bozo_exception:
            error_msg = bozo_exception or "Unknown feed parse error"
            # Some bozo exceptions are recoverable (e.g., CharacterEncodingOverride)
            if not feed.entries:
                logger.warning(f"Feed error for {feed_name}: {error_msg}")
                return FeedResult(
                    feed_url=feed_url,
                    feed_name=feed_name,
                    articles=[],
                    success=False,
                    error=error_msg,
                    status_code=status_code,
                    final_url=final_url,
                    content_type=content_type,
                    attempts=attempts,
                    response_time_ms=response_time_ms,
                    bozo=True,
                    bozo_exception=error_msg,
                )

        # Determine feed title
        actual_feed_name = feed.feed.get("title", feed_name)

        # Calculate cutoff time
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        articles: list[Article] = []

        for entry in feed.entries[:max_articles * 2]:  # Fetch extra, filter by date
            # Parse publication date
            published = _parse_entry_date(entry)
            if published is None:
                logger.debug(f"Skipping entry without date: {entry.get('title', 'Unknown')}")
                continue

            # Skip old articles
            if published < cutoff:
                continue

            # Extract article URL
            url = entry.get("link", "")
            if not url:
                continue

            # Create article
            article = Article(
                id=generate_article_id(url),
                url=url,
                title=entry.get("title", "Untitled"),
                author=_extract_author(entry),
                feed_name=actual_feed_name,
                feed_url=feed_url,
                published=published,
                content="",  # Will be populated by parser
                category=category,
            )

            articles.append(article)

            if len(articles) >= max_articles:
                break

        logger.info(f"Found {len(articles)} new articles from {feed_name}")

        return FeedResult(
            feed_url=feed_url,
            feed_name=actual_feed_name,
            articles=articles,
            success=True,
            status_code=status_code,
            final_url=final_url,
            content_type=content_type,
            attempts=attempts,
            response_time_ms=response_time_ms,
            entry_count=len(feed.entries),
            bozo=bool(feed.bozo),
            bozo_exception=bozo_exception,
        )

    except httpx.TimeoutException as e:
        logger.error(f"Timeout fetching {feed_name}: {e}")
        return FeedResult(
            feed_url=feed_url,
            feed_name=feed_name,
            articles=[],
            success=False,
            error=f"Request timed out after {timeout}s: {e}",
            status_code=status_code,
            final_url=final_url,
            content_type=content_type,
            attempts=max(attempts, 1),
            response_time_ms=response_time_ms,
        )
    except httpx.HTTPError as e:
        logger.error(f"HTTP error fetching {feed_name}: {e}")
        return FeedResult(
            feed_url=feed_url,
            feed_name=feed_name,
            articles=[],
            success=False,
            error=str(e),
            status_code=status_code,
            final_url=final_url,
            content_type=content_type,
            attempts=max(attempts, 1),
            response_time_ms=response_time_ms,
        )
    except Exception as e:
        logger.error(f"Failed to fetch {feed_name}: {e}")
        return FeedResult(
            feed_url=feed_url,
            feed_name=feed_name,
            articles=[],
            success=False,
            error=str(e),
            status_code=status_code,
            final_url=final_url,
            content_type=content_type,
            attempts=max(attempts, 1),
            response_time_ms=response_time_ms,
        )


def _fetch_response(feed_url: str, timeout: int, headers: dict[str, str]) -> tuple[httpx.Response, float]:
    """Fetch a feed URL and return (response, elapsed_ms)."""
    started = perf_counter()
    response = httpx.get(
        feed_url,
        timeout=timeout,
        follow_redirects=True,
        headers=headers,
    )
    elapsed_ms = (perf_counter() - started) * 1000
    return response, elapsed_ms


def _format_http_error(response: httpx.Response, attempt_summaries: list[str]) -> str:
    """Build a compact HTTP error message with diagnostics."""
    parts = [f"HTTP {response.status_code} for {response.url}"]
    if attempt_summaries:
        parts.append(f"attempts: {', '.join(attempt_summaries)}")
    if content_type := response.headers.get("content-type"):
        parts.append(f"content-type: {content_type}")
    return " | ".join(parts)


def _parse_entry_date(entry: dict) -> datetime | None:
    """Parse publication date from feed entry."""
    # Try different date fields
    for field in ["published_parsed", "updated_parsed", "created_parsed"]:
        if parsed := entry.get(field):
            try:
                from time import mktime
                return datetime.fromtimestamp(mktime(parsed), tz=timezone.utc)
            except (ValueError, OverflowError):
                continue
    
    # Try string parsing as fallback
    for field in ["published", "updated", "created"]:
        if date_str := entry.get(field):
            try:
                dt = parse_date(date_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except (ValueError, ParserError):
                continue
    
    return None


def _extract_author(entry: dict) -> str:
    """Extract author name from feed entry."""
    # Try author field
    if author := entry.get("author"):
        return author
    
    # Try author_detail
    if author_detail := entry.get("author_detail"):
        if name := author_detail.get("name"):
            return name
    
    # Try authors list
    if authors := entry.get("authors"):
        if authors and (name := authors[0].get("name")):
            return name
    
    return "Unknown"


def fetch_all_feeds(
    feeds_config: dict[str, dict],
    lookback_hours: int = 48,
    max_articles_per_feed: int = 10,
) -> list[FeedResult]:
    """
    Fetch all configured feeds concurrently.
    
    Args:
        feeds_config: Dictionary of feed configurations
        lookback_hours: Only include articles from this many hours ago
        max_articles_per_feed: Maximum articles per feed
    
    Returns:
        List of FeedResults
    """
    import concurrent.futures
    
    results: list[FeedResult] = []
    
    # Prepare arguments for each feed
    fetch_args = []
    for feed_name, config in feeds_config.items():
        url = config.get("url")
        if not url:
            logger.warning(f"Feed {feed_name} has no URL configured")
            continue
        
        category = config.get("category", "Uncategorized")
        fetch_args.append((url, feed_name, category))
    
    # Execute concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_feed = {
            executor.submit(
                fetch_feed, 
                feed_url=url, 
                feed_name=name, 
                category=cat, 
                lookback_hours=lookback_hours, 
                max_articles=max_articles_per_feed
            ): (name, url) for url, name, cat in fetch_args
        }

        for future in concurrent.futures.as_completed(future_to_feed):
            feed_name, feed_url = future_to_feed[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error(f"Top-level error fetching {feed_name}: {e}")
                results.append(
                    FeedResult(
                        feed_url=feed_url,
                        feed_name=feed_name,
                        articles=[],
                        success=False,
                        error=f"Unhandled fetch error: {e}",
                        attempts=1,
                    )
                )

    return results
