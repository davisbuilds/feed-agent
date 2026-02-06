# Phase 5: Polish & Production Readiness

**Goal**: Harden the system for reliable daily operation with proper error handling, monitoring, and refinements based on real usage.

**Estimated Time**: 3-4 hours

**Dependencies**: Phases 0-4 completed and working

---

## Overview

This phase transforms a working prototype into a reliable system you can trust to run unattended. Focus areas:

1. **Error Handling**: Graceful failures, retries, notifications
2. **Monitoring**: Know when things break
3. **Performance**: Optimize for daily use
4. **Maintenance**: Easy updates and debugging

---

## Tasks

### 5.1 Robust Error Handling

Create `src/utils/retry.py`:

```python
"""
Retry utilities for resilient operations.
"""

import time
from functools import wraps
from typing import Callable, TypeVar, Any

from src.logging_config import get_logger

logger = get_logger("retry")

T = TypeVar("T")


class RetryError(Exception):
    """Raised when all retries are exhausted."""
    
    def __init__(self, message: str, last_error: Exception):
        super().__init__(message)
        self.last_error = last_error


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    on_retry: Callable[[int, Exception], None] | None = None,
) -> Callable:
    """
    Decorator for retrying functions with exponential backoff.
    
    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay between retries (seconds)
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch
        on_retry: Optional callback(attempt, exception) on each retry
    
    Usage:
        @retry(max_attempts=3, delay=1.0)
        def flaky_function():
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            current_delay = delay
            last_exception: Exception | None = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts:
                        logger.error(f"{func.__name__} failed after {max_attempts} attempts: {e}")
                        raise RetryError(
                            f"{func.__name__} failed after {max_attempts} attempts",
                            last_exception,
                        )
                    
                    logger.warning(
                        f"{func.__name__} attempt {attempt}/{max_attempts} failed: {e}. "
                        f"Retrying in {current_delay:.1f}s..."
                    )
                    
                    if on_retry:
                        on_retry(attempt, e)
                    
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            # Should never reach here
            raise RetryError(f"{func.__name__} failed", last_exception)  # type: ignore
        
        return wrapper
    return decorator


def retry_async(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Callable:
    """Async version of retry decorator."""
    import asyncio
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            current_delay = delay
            last_exception: Exception | None = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts:
                        raise RetryError(
                            f"{func.__name__} failed after {max_attempts} attempts",
                            last_exception,
                        )
                    
                    logger.warning(
                        f"{func.__name__} attempt {attempt}/{max_attempts} failed: {e}. "
                        f"Retrying in {current_delay:.1f}s..."
                    )
                    
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
            
            raise RetryError(f"{func.__name__} failed", last_exception)  # type: ignore
        
        return wrapper
    return decorator
```

- [ ] Create `src/utils/retry.py`

### 5.2 Error Notifications

Create `src/utils/notifications.py`:

```python
"""
Error notification utilities.

Sends alerts when the digest pipeline fails.
"""

from datetime import datetime

import resend

from src.config import get_settings
from src.logging_config import get_logger

logger = get_logger("notifications")


def send_error_notification(
    error: str,
    context: str = "",
    to: str | None = None,
) -> bool:
    """
    Send an error notification email.
    
    Args:
        error: Error message
        context: Additional context about what failed
        to: Recipient (defaults to settings.email_to)
    
    Returns:
        True if sent successfully
    """
    settings = get_settings()
    recipient = to or settings.email_to
    
    try:
        resend.api_key = settings.resend_api_key
        
        html = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #dc2626;">⚠️ Digest Agent Error</h1>
            <p style="color: #3f3f46;">
                The Feed Agent encountered an error:
            </p>
            <div style="background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 16px; margin: 16px 0;">
                <code style="color: #991b1b; white-space: pre-wrap;">{error}</code>
            </div>
            {f'<p style="color: #71717a;"><strong>Context:</strong> {context}</p>' if context else ''}
            <p style="color: #71717a; font-size: 14px;">
                Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            </p>
        </div>
        """
        
        resend.Emails.send({
            "from": settings.email_from,
            "to": [recipient],
            "subject": "⚠️ Digest Agent Error",
            "html": html,
            "tags": [{"name": "type", "value": "error_notification"}],
        })
        
        logger.info(f"Error notification sent to {recipient}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send error notification: {e}")
        return False


def send_success_notification(
    stats: dict,
    to: str | None = None,
) -> bool:
    """
    Send a success summary (optional, for debugging).
    
    Args:
        stats: Dictionary of statistics
        to: Recipient
    
    Returns:
        True if sent successfully
    """
    settings = get_settings()
    recipient = to or settings.email_to
    
    try:
        resend.api_key = settings.resend_api_key
        
        stats_html = "\n".join([
            f"<li><strong>{k}:</strong> {v}</li>"
            for k, v in stats.items()
        ])
        
        html = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #16a34a;">✓ Digest Agent Success</h1>
            <ul style="color: #3f3f46;">
                {stats_html}
            </ul>
            <p style="color: #71717a; font-size: 14px;">
                Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            </p>
        </div>
        """
        
        resend.Emails.send({
            "from": settings.email_from,
            "to": [recipient],
            "subject": "✓ Digest Agent Success",
            "html": html,
            "tags": [{"name": "type", "value": "success_notification"}],
        })
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to send success notification: {e}")
        return False
```

- [ ] Create `src/utils/notifications.py`

### 5.3 Enhanced Pipeline with Error Handling

Create `src/pipeline.py`:

```python
"""
Main pipeline orchestration with error handling.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from src.analyze import run_analysis, AnalysisResult
from src.config import get_settings
from src.deliver import EmailSender, SendResult
from src.ingest import run_ingestion, IngestResult
from src.logging_config import get_logger
from src.models import ArticleStatus, DailyDigest
from src.storage.db import Database
from src.utils.notifications import send_error_notification

logger = get_logger("pipeline")


@dataclass
class PipelineResult:
    """Complete result of a pipeline run."""
    
    success: bool
    ingest_result: IngestResult | None = None
    analysis_result: AnalysisResult | None = None
    send_result: SendResult | None = None
    digest: DailyDigest | None = None
    
    total_duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/notifications."""
        return {
            "success": self.success,
            "articles_ingested": self.ingest_result.articles_new if self.ingest_result else 0,
            "articles_analyzed": self.analysis_result.articles_analyzed if self.analysis_result else 0,
            "email_sent": self.send_result.success if self.send_result else False,
            "duration_seconds": f"{self.total_duration_seconds:.1f}",
            "errors": len(self.errors),
            "warnings": len(self.warnings),
        }


class Pipeline:
    """
    Main pipeline for the digest agent.
    
    Handles the full ingest → analyze → deliver flow with
    proper error handling and recovery.
    """
    
    def __init__(
        self,
        db: Database | None = None,
        notify_on_error: bool = True,
    ):
        self.settings = get_settings()
        self.db = db or Database(self.settings.data_dir / "articles.db")
        self.notify_on_error = notify_on_error
    
    def run(
        self,
        skip_ingest: bool = False,
        skip_analyze: bool = False,
        skip_send: bool = False,
    ) -> PipelineResult:
        """
        Run the full pipeline.
        
        Args:
            skip_ingest: Skip feed fetching
            skip_analyze: Skip Claude summarization
            skip_send: Skip email delivery
        
        Returns:
            PipelineResult with all outcomes
        """
        import time
        start_time = time.time()
        
        result = PipelineResult(success=True)
        
        try:
            # Phase 1: Ingest
            if not skip_ingest:
                logger.info("Starting ingestion phase")
                try:
                    result.ingest_result = run_ingestion(db=self.db)
                    
                    if result.ingest_result.feeds_failed > 0:
                        result.warnings.append(
                            f"{result.ingest_result.feeds_failed} feeds failed to fetch"
                        )
                except Exception as e:
                    logger.error(f"Ingestion failed: {e}")
                    result.errors.append(f"Ingestion: {e}")
                    # Continue to analyze any existing pending articles
            
            # Phase 2: Analyze
            if not skip_analyze:
                logger.info("Starting analysis phase")
                try:
                    result.analysis_result = run_analysis(db=self.db)
                    result.digest = result.analysis_result.digest
                    
                    if result.analysis_result.errors:
                        result.warnings.extend(result.analysis_result.errors)
                except Exception as e:
                    logger.error(f"Analysis failed: {e}")
                    result.errors.append(f"Analysis: {e}")
            
            # Phase 3: Send
            if not skip_send and result.digest:
                logger.info("Starting delivery phase")
                try:
                    sender = EmailSender()
                    result.send_result = sender.send_digest(result.digest)
                    
                    if not result.send_result.success:
                        result.errors.append(f"Email delivery: {result.send_result.error}")
                except Exception as e:
                    logger.error(f"Delivery failed: {e}")
                    result.errors.append(f"Delivery: {e}")
            elif not skip_send and not result.digest:
                logger.info("No digest to send")
                result.warnings.append("No content for digest")
            
            # Determine overall success
            result.success = len(result.errors) == 0
            
        except Exception as e:
            logger.exception(f"Pipeline failed: {e}")
            result.success = False
            result.errors.append(f"Pipeline: {e}")
        
        finally:
            result.total_duration_seconds = time.time() - start_time
            
            # Send error notification if needed
            if not result.success and self.notify_on_error:
                error_msg = "\n".join(result.errors)
                send_error_notification(
                    error=error_msg,
                    context=f"Pipeline run at {datetime.now()}",
                )
        
        logger.info(f"Pipeline complete: {'SUCCESS' if result.success else 'FAILED'}")
        return result
    
    def run_safe(self, **kwargs) -> PipelineResult:
        """
        Run pipeline with guaranteed no exceptions raised.
        
        Always returns a PipelineResult, even on catastrophic failure.
        """
        try:
            return self.run(**kwargs)
        except Exception as e:
            logger.exception(f"Catastrophic pipeline failure: {e}")
            return PipelineResult(
                success=False,
                errors=[f"Catastrophic failure: {e}"],
            )
```

- [ ] Create `src/pipeline.py`

### 5.4 Logging Improvements

Update `src/logging_config.py` to add file logging:

```python
"""
Logging configuration with file output.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal

from rich.console import Console
from rich.logging import RichHandler

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def setup_logging(
    level: LogLevel = "INFO",
    log_dir: Path | None = None,
    log_to_file: bool = True,
) -> logging.Logger:
    """
    Configure logging with rich console and optional file output.
    
    Args:
        level: Logging level
        log_dir: Directory for log files
        log_to_file: Whether to write to file
    
    Returns:
        Configured root logger
    """
    # Determine log directory
    if log_dir is None:
        log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create handlers
    handlers: list[logging.Handler] = []
    
    # Rich console handler
    console = Console(stderr=True)
    console_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=False,
        rich_tracebacks=True,
        tracebacks_show_locals=True,
    )
    console_handler.setLevel(level)
    handlers.append(console_handler)
    
    # File handler
    if log_to_file:
        log_file = log_dir / f"digest_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)  # Always capture debug to file
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(message)s",
        datefmt="[%X]",
        handlers=handlers,
    )
    
    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    logging.getLogger("feedparser").setLevel(logging.WARNING)
    
    return logging.getLogger("substack_agent")


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a specific module."""
    return logging.getLogger(f"substack_agent.{name}")
```

- [ ] Update `src/logging_config.py` with file logging

### 5.5 Database Maintenance

Create `src/storage/maintenance.py`:

```python
"""
Database maintenance utilities.
"""

from datetime import datetime, timedelta
from pathlib import Path

from src.logging_config import get_logger
from src.storage.db import Database

logger = get_logger("maintenance")


def cleanup_old_articles(
    db: Database,
    days_to_keep: int = 30,
    dry_run: bool = True,
) -> int:
    """
    Remove articles older than specified days.
    
    Args:
        db: Database instance
        days_to_keep: Number of days of articles to retain
        dry_run: If True, only report what would be deleted
    
    Returns:
        Number of articles deleted (or would be deleted)
    """
    cutoff = datetime.now() - timedelta(days=days_to_keep)
    cutoff_str = cutoff.isoformat()
    
    with db._connection() as conn:
        # Count articles to delete
        count = conn.execute("""
            SELECT COUNT(*) FROM articles
            WHERE published < ?
        """, (cutoff_str,)).fetchone()[0]
        
        if dry_run:
            logger.info(f"Would delete {count} articles older than {days_to_keep} days")
        else:
            conn.execute("""
                DELETE FROM articles
                WHERE published < ?
            """, (cutoff_str,))
            logger.info(f"Deleted {count} articles older than {days_to_keep} days")
    
    return count


def vacuum_database(db: Database) -> None:
    """
    Vacuum the database to reclaim space.
    """
    logger.info("Vacuuming database...")
    
    with db._connection() as conn:
        conn.execute("VACUUM")
    
    logger.info("Vacuum complete")


def get_database_stats(db: Database) -> dict:
    """
    Get database statistics.
    
    Returns:
        Dictionary of statistics
    """
    stats = {}
    
    with db._connection() as conn:
        # Total articles
        stats["total_articles"] = conn.execute(
            "SELECT COUNT(*) FROM articles"
        ).fetchone()[0]
        
        # Articles by status
        status_counts = conn.execute("""
            SELECT status, COUNT(*) FROM articles GROUP BY status
        """).fetchall()
        stats["by_status"] = {row[0]: row[1] for row in status_counts}
        
        # Articles by category
        category_counts = conn.execute("""
            SELECT category, COUNT(*) FROM articles GROUP BY category
        """).fetchall()
        stats["by_category"] = {row[0]: row[1] for row in category_counts}
        
        # Unique feeds
        stats["unique_feeds"] = conn.execute(
            "SELECT COUNT(DISTINCT feed_url) FROM articles"
        ).fetchone()[0]
        
        # Date range
        date_range = conn.execute("""
            SELECT MIN(published), MAX(published) FROM articles
        """).fetchone()
        stats["oldest_article"] = date_range[0]
        stats["newest_article"] = date_range[1]
        
        # Database file size
        db_size = Path(db.db_path).stat().st_size if Path(db.db_path).exists() else 0
        stats["db_size_mb"] = db_size / (1024 * 1024)
    
    return stats


def backup_database(db: Database, backup_dir: Path) -> Path:
    """
    Create a backup of the database.
    
    Args:
        db: Database instance
        backup_dir: Directory for backups
    
    Returns:
        Path to backup file
    """
    import shutil
    
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"articles_backup_{timestamp}.db"
    
    shutil.copy2(db.db_path, backup_path)
    
    logger.info(f"Database backed up to {backup_path}")
    return backup_path
```

- [ ] Create `src/storage/maintenance.py`

### 5.6 Maintenance CLI Commands

Add maintenance commands to `scripts/run_digest.py`:

```python
# Add these commands to the existing CLI

@app.command()
def cleanup(
    days: int = typer.Option(30, "--days", "-d", help="Days of articles to keep"),
    dry_run: bool = typer.Option(True, "--dry-run/--execute", help="Preview vs execute"),
) -> None:
    """Clean up old articles from the database."""
    settings = get_settings()
    db = Database(settings.data_dir / "articles.db")
    
    from src.storage.maintenance import cleanup_old_articles
    
    count = cleanup_old_articles(db, days_to_keep=days, dry_run=dry_run)
    
    if dry_run:
        console.print(f"[yellow]Would delete {count} articles[/yellow]")
        console.print("Run with --execute to actually delete")
    else:
        console.print(f"[green]Deleted {count} articles[/green]")


@app.command()
def stats() -> None:
    """Show detailed database statistics."""
    settings = get_settings()
    db = Database(settings.data_dir / "articles.db")
    
    from src.storage.maintenance import get_database_stats
    
    stats = get_database_stats(db)
    
    console.print("\n[bold]Database Statistics[/bold]\n")
    console.print(f"Total articles: {stats['total_articles']}")
    console.print(f"Unique feeds: {stats['unique_feeds']}")
    console.print(f"Database size: {stats['db_size_mb']:.2f} MB")
    
    if stats['oldest_article']:
        console.print(f"\nDate range: {stats['oldest_article'][:10]} to {stats['newest_article'][:10]}")
    
    console.print("\n[bold]By Status:[/bold]")
    for status, count in stats['by_status'].items():
        console.print(f"  {status}: {count}")
    
    console.print("\n[bold]By Category:[/bold]")
    for category, count in sorted(stats['by_category'].items(), key=lambda x: -x[1]):
        console.print(f"  {category}: {count}")


@app.command()
def backup() -> None:
    """Create a database backup."""
    settings = get_settings()
    db = Database(settings.data_dir / "articles.db")
    
    from src.storage.maintenance import backup_database
    
    backup_dir = settings.data_dir / "backups"
    backup_path = backup_database(db, backup_dir)
    
    console.print(f"[green]✓ Backup created: {backup_path}[/green]")
```

- [ ] Add maintenance commands to CLI

### 5.7 Configuration Validation

Create `src/utils/validators.py`:

```python
"""
Configuration and runtime validators.
"""

import httpx
import anthropic
import resend

from src.config import get_settings, FeedConfig
from src.logging_config import get_logger

logger = get_logger("validators")


class ValidationResult:
    """Result of a validation check."""
    
    def __init__(self, name: str):
        self.name = name
        self.success = False
        self.message = ""
        self.details: dict = {}
    
    def __str__(self) -> str:
        status = "✓" if self.success else "✗"
        return f"{status} {self.name}: {self.message}"


def validate_anthropic_api() -> ValidationResult:
    """Validate Anthropic API key and connectivity."""
    result = ValidationResult("Anthropic API")
    settings = get_settings()
    
    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        
        # Make a minimal API call
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}],
        )
        
        result.success = True
        result.message = "Connected successfully"
        result.details["model"] = settings.claude_model
        
    except anthropic.AuthenticationError:
        result.message = "Invalid API key"
    except anthropic.APIError as e:
        result.message = f"API error: {e}"
    except Exception as e:
        result.message = f"Connection error: {e}"
    
    return result


def validate_resend_api() -> ValidationResult:
    """Validate Resend API key."""
    result = ValidationResult("Resend API")
    settings = get_settings()
    
    try:
        resend.api_key = settings.resend_api_key
        
        # Check API key by listing domains (doesn't send anything)
        domains = resend.Domains.list()
        
        result.success = True
        result.message = "Connected successfully"
        result.details["domains"] = len(domains.get("data", []))
        
    except Exception as e:
        result.message = f"Error: {e}"
    
    return result


def validate_feeds() -> ValidationResult:
    """Validate feed configuration and accessibility."""
    result = ValidationResult("RSS Feeds")
    settings = get_settings()
    
    try:
        feed_config = FeedConfig(settings.config_dir / "feeds.yaml")
        feeds = feed_config.feeds
        
        if not feeds:
            result.message = "No feeds configured"
            return result
        
        # Test a few feeds
        accessible = 0
        failed = []
        
        for name, config in list(feeds.items())[:3]:  # Test first 3
            url = config.get("url")
            if not url:
                continue
            
            try:
                response = httpx.head(url, timeout=10, follow_redirects=True)
                if response.status_code < 400:
                    accessible += 1
                else:
                    failed.append(f"{name}: HTTP {response.status_code}")
            except Exception as e:
                failed.append(f"{name}: {e}")
        
        result.success = accessible > 0
        result.message = f"{len(feeds)} configured, {accessible}/3 tested accessible"
        result.details["total"] = len(feeds)
        result.details["failed"] = failed
        
    except Exception as e:
        result.message = f"Error: {e}"
    
    return result


def run_all_validations() -> list[ValidationResult]:
    """Run all validation checks."""
    return [
        validate_anthropic_api(),
        validate_resend_api(),
        validate_feeds(),
    ]
```

- [ ] Create `src/utils/validators.py`

### 5.8 Add Validation to CLI

Add validation command to `scripts/run_digest.py`:

```python
@app.command()
def validate(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show details"),
) -> None:
    """Run all validation checks."""
    from src.utils.validators import run_all_validations
    
    console.print("[bold]Running validation checks...[/bold]\n")
    
    results = run_all_validations()
    
    all_passed = True
    for result in results:
        if result.success:
            console.print(f"[green]{result}[/green]")
        else:
            console.print(f"[red]{result}[/red]")
            all_passed = False
        
        if verbose and result.details:
            for key, value in result.details.items():
                console.print(f"    {key}: {value}")
    
    console.print()
    if all_passed:
        console.print("[green]✓ All checks passed[/green]")
    else:
        console.print("[red]✗ Some checks failed[/red]")
        raise typer.Exit(1)
```

- [ ] Add validation command to CLI
- [ ] Test: `./feed validate`

---

## Production Checklist

### Before Going Live

- [ ] All validation checks pass (`./feed validate`)
- [ ] Test email delivery works (`./feed send --test`)
- [ ] Full pipeline runs successfully (`./feed run`)
- [ ] Scheduling is configured and tested
- [ ] Error notifications are working
- [ ] Logs are being written to files
- [ ] Database backup is working

### Monitoring

Set up periodic checks:

```bash
# Add to cron (runs every 6 hours)
0 */6 * * * /path/to/digest healthcheck || /path/to/notify_error.sh
```

### Maintenance Schedule

- **Daily**: Pipeline runs automatically
- **Weekly**: Review logs for warnings
- **Monthly**: Run `./feed cleanup --execute` and `./feed backup`
- **Quarterly**: Review and update feed list

---

## Troubleshooting Guide

### Common Issues

**Pipeline runs but no email received**
1. Check `./feed validate` for Resend issues
2. Verify email is not in spam folder
3. Check Resend dashboard for delivery status

**Summaries are poor quality**
1. Check article content is being extracted properly
2. Review prompts in `src/analyze/prompts.py`
3. Consider using Claude Opus for better quality

**Feed fetch failures**
1. Check if feed URL is still valid
2. Some sites block automated requests - try different User-Agent
3. Run `./feed ingest -v` for detailed errors

**High API costs**
1. Reduce `max_articles_per_feed` in settings
2. Increase `lookback_hours` to skip more duplicates
3. Filter low-value feeds

---

## Completion Checklist

- [ ] Retry utilities implemented
- [ ] Error notifications working
- [ ] Pipeline handles failures gracefully
- [ ] File logging configured
- [ ] Database maintenance tools ready
- [ ] Validation checks pass
- [ ] Production checklist reviewed

## Next Steps

Congratulations! You now have a production-ready Feed agent. Consider these enhancements:

1. **Web Dashboard**: Add a simple Flask/FastAPI dashboard
2. **Feed Discovery**: Auto-suggest feeds based on reading history
3. **Personalization**: Learn which topics you engage with
4. **Multi-user**: Support multiple recipients with different preferences
5. **Mobile App**: Push notifications for must-read articles
