"""
Feed Agent CLI.

Usage:
    feed run            # Full pipeline: ingest, analyze, send
    feed ingest         # Only fetch new articles
    feed analyze        # Only summarize pending articles
    feed send           # Only send digest for summarized articles
    feed status         # Show pipeline status
    feed config         # Verify configuration
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Imports
from src.config import FeedConfig, get_settings
from src.logging_config import setup_logging
from src.models import ArticleStatus
from src.storage.db import Database

__version__ = "0.1.0"

app = typer.Typer(
    name="feed",
    help="Feed Agent - Your personal newsletter intelligence",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()

# Global state
state = {"verbose": False}


def _load_settings():
    """Load settings with a user-friendly error on failure."""
    try:
        return get_settings()
    except Exception as e:
        console.print(
            "[red]Configuration error.[/red] "
            "Check your .env file or environment variables.\n"
        )
        for error in getattr(e, "errors", lambda: [])():
            loc = ".".join(str(l) for l in error["loc"])
            console.print(f"  [red]✗[/red] {loc}: {error['msg']}")
        if not getattr(e, "errors", None):
            console.print(f"  [red]✗[/red] {e}")
        console.print("\n[dim]Run 'feed config' to verify your setup.[/dim]")
        raise typer.Exit(code=1)


def version_callback(value: bool):
    """Print version and exit."""
    if value:
        print(f"Feed Agent v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    verbose: bool = typer.Option(
        False, 
        "--verbose", 
        "-v", 
        help="Enable verbose logging output."
    ),
    version: Optional[bool] = typer.Option(
        None, 
        "--version", 
        callback=version_callback, 
        is_eager=True,
        help="Show version and exit."
    ),
):
    """
    Feed Agent CLI
    """
    state["verbose"] = verbose
    if verbose:
        setup_logging("DEBUG")
    else:
        setup_logging("INFO")


@app.command()
def run(
    skip_send: bool = typer.Option(False, "--skip-send", help="Skip email delivery"),
) -> None:
    """Run the full digest pipeline: ingest → analyze → send."""
    settings = _load_settings()
    
    console.print(Panel.fit(
        "[bold]📬 Feed Agent[/bold]\n"
        f"Running full pipeline at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        border_style="blue",
    ))
    
    db = Database(settings.data_dir / "articles.db")
    
    # Phase 1: Ingest
    console.print("\n[bold cyan]Phase 1: Ingesting feeds[/bold cyan]")
    from src.ingest import run_ingestion
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Fetching feeds...", total=None)
        ingest_result = run_ingestion(db=db)
        progress.remove_task(task)
    
    console.print(f"  ✓ Checked {ingest_result.feeds_checked} feeds")
    console.print(f"  ✓ Found {ingest_result.articles_new} new articles")
    
    if ingest_result.feeds_failed > 0:
        console.print(f"  [yellow]⚠ {ingest_result.feeds_failed} feeds failed[/yellow]")
    
    # Phase 2: Analyze
    console.print("\n[bold cyan]Phase 2: Analyzing articles[/bold cyan]")
    from src.analyze import run_analysis
    
    pending = db.get_pending_articles()
    if not pending:
        console.print("  [dim]No new articles to analyze[/dim]")
        analysis_result = None
    else:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Summarizing {len(pending)} articles...", total=None)
            analysis_result = run_analysis(db=db)
            progress.remove_task(task)
        
        console.print(f"  ✓ Analyzed {analysis_result.articles_analyzed} articles")
        console.print(f"  ✓ Used {analysis_result.tokens_used:,} tokens (${analysis_result.cost_estimate_usd:.4f})")
    
    # Phase 3: Send
    if skip_send:
        console.print("\n[dim]Skipping email delivery (--skip-send)[/dim]")
    elif analysis_result and analysis_result.digest:
        console.print("\n[bold cyan]Phase 3: Sending digest[/bold cyan]")
        from src.deliver import EmailSender
        
        sender = EmailSender()
        send_result = sender.send_digest(analysis_result.digest)
        
        if send_result.success:
            console.print(f"  ✓ Email sent to {settings.email_to}")
            console.print(f"  ✓ Email ID: {send_result.email_id}")
        else:
            console.print(f"  [red]✗ Send failed: {send_result.error}[/red]")
            raise typer.Exit(code=1)
    else:
        console.print("\n[dim]No digest to send[/dim]")

    # Summary
    total_time = ingest_result.duration_seconds
    if analysis_result:
        total_time += analysis_result.duration_seconds

    console.print(Panel.fit(
        f"[bold green]✓ Complete[/bold green] in {total_time:.1f}s",
        border_style="green",
    ))


@app.command()
def ingest() -> None:
    """Fetch new articles from RSS feeds."""
    settings = _load_settings()
    
    console.print("[bold]Fetching feeds...[/bold]")
    
    from src.ingest import run_ingestion
    
    db = Database(settings.data_dir / "articles.db")
    result = run_ingestion(db=db)
    
    table = Table(title="Ingestion Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Feeds checked", str(result.feeds_checked))
    table.add_row("Feeds successful", str(result.feeds_successful))
    table.add_row("Feeds failed", str(result.feeds_failed))
    table.add_row("Articles found", str(result.articles_found))
    table.add_row("Articles new", str(result.articles_new))
    table.add_row("Duration", f"{result.duration_seconds:.1f}s")
    
    console.print(table)


@app.command()
def analyze() -> None:
    """Summarize pending articles with the configured LLM."""
    settings = _load_settings()
    
    db = Database(settings.data_dir / "articles.db")
    pending = db.get_pending_articles()
    
    if not pending:
        console.print("[yellow]No pending articles to analyze[/yellow]")
        return
    
    console.print(f"[bold]Analyzing {len(pending)} articles...[/bold]")
    
    from src.analyze import run_analysis
    
    result = run_analysis(db=db)
    
    table = Table(title="Analysis Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Articles analyzed", str(result.articles_analyzed))
    table.add_row("Tokens used", f"{result.tokens_used:,}")
    table.add_row("Estimated cost", f"${result.cost_estimate_usd:.4f}")
    table.add_row("Duration", f"{result.duration_seconds:.1f}s")
    
    console.print(table)
    
    if result.digest:
        console.print(f"\n[green]Digest ready with {len(result.digest.categories)} categories[/green]")


@app.command()
def send(
    test: bool = typer.Option(False, "--test", help="Send test email instead"),
) -> None:
    """Send the digest email."""
    settings = _load_settings()
    
    from src.deliver import EmailSender
    
    sender = EmailSender()
    
    if test:
        console.print("[bold]Sending test email...[/bold]")
        result = sender.send_test_email()
    else:
        # Build digest from recent summarized articles
        db = Database(settings.data_dir / "articles.db")
        since = datetime.now(timezone.utc) - timedelta(hours=settings.lookback_hours)
        articles = db.get_articles_since(since, status=ArticleStatus.SUMMARIZED)
        
        if not articles:
            console.print("[yellow]No summarized articles to send[/yellow]")
            return
        
        console.print(f"[bold]Building digest from {len(articles)} articles...[/bold]")
        
        from src.analyze.digest_builder import DigestBuilder
        
        builder = DigestBuilder()
        digest = builder.build_digest(articles)
        
        console.print("[bold]Sending digest...[/bold]")
        result = sender.send_digest(digest)
    
    if result.success:
        console.print(f"[green]✓ Email sent successfully[/green]")
        console.print(f"  Email ID: {result.email_id}")
    else:
        console.print(f"[red]✗ Send failed: {result.error}[/red]")
        raise typer.Exit(code=1)


@app.command()
def status(
    json_format: bool = typer.Option(False, "--json", help="Output status as JSON"),
) -> None:
    """Show pipeline status and statistics."""
    settings = _load_settings()
    
    db_path = settings.data_dir / "articles.db"
    
    if not db_path.exists():
        if json_format:
            print(json.dumps({"error": "Database not found"}))
        else:
            console.print("[yellow]No database found. Run 'feed ingest' first.[/yellow]")
        return
    
    db = Database(db_path)
    
    # Get article counts by status
    with db._connection() as conn:
        status_counts = conn.execute("""
            SELECT status, COUNT(*) as count
            FROM articles
            GROUP BY status
        """).fetchall()
        
        total_articles = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        
        feed_count = conn.execute("SELECT COUNT(DISTINCT feed_url) FROM articles").fetchone()[0]
        
        recent = conn.execute("""
            SELECT title, feed_name, published, status
            FROM articles
            ORDER BY published DESC
            LIMIT 5
        """).fetchall()
    
    data = {
        "status_counts": {row[0]: row[1] for row in status_counts},
        "total_articles": total_articles,
        "feed_count": feed_count,
        "recent_articles": [
            {"title": row[0], "source": row[1], "published": row[2], "status": row[3]}
            for row in recent
        ]
    }
    
    if json_format:
        print(json.dumps(data, indent=2))
        return
    
    # Status table
    status_table = Table(title="Article Status")
    status_table.add_column("Status", style="cyan")
    status_table.add_column("Count", style="green")
    
    for status, count in data["status_counts"].items():
        status_table.add_row(status, str(count))
    
    status_table.add_row("[bold]Total[/bold]", f"[bold]{total_articles}[/bold]")
    
    console.print(status_table)
    console.print(f"\n[dim]From {feed_count} feeds[/dim]")
    
    # Recent articles
    if recent:
        recent_table = Table(title="\nRecent Articles")
        recent_table.add_column("Title", style="white", max_width=40)
        recent_table.add_column("Source", style="dim")
        recent_table.add_column("Status", style="cyan")
        
        for row in recent:
            recent_table.add_row(
                row[0][:40] + "..." if len(row[0]) > 40 else row[0],
                row[1],
                row[3],
            )
        
        console.print(recent_table)


@app.command()
def config() -> None:
    """Verify configuration and show settings."""
    console.print("[bold]Verifying configuration...[/bold]\n")

    errors = []
    settings = None

    # Check settings
    try:
        settings = get_settings()
        console.print("[green]✓[/green] Settings loaded")

        # Check API keys (show partial)
        if settings.llm_api_key:
            key_preview = settings.llm_api_key[:10] + "..."
            console.print(f"  LLM API key: {key_preview}")
        else:
            errors.append("Missing LLM_API_KEY")

        if settings.resend_api_key:
            key_preview = settings.resend_api_key[:10] + "..."
            console.print(f"  Resend API key: {key_preview}")
        else:
            errors.append("Missing RESEND_API_KEY")

        console.print(f"  Email from: {settings.email_from}")
        console.print(f"  Email to: {settings.email_to}")
        console.print(f"  LLM provider: {settings.llm_provider}")
        console.print(f"  LLM model: {settings.llm_model}")

    except Exception as e:
        errors.append(f"Settings error: {e}")

    # Check feeds config (only if settings loaded successfully)
    console.print()
    if settings is not None:
        try:
            feed_config = FeedConfig(settings.config_dir / "feeds.yaml")
            feeds = feed_config.feeds

            if feeds:
                console.print(f"[green]✓[/green] Feeds configured: {len(feeds)}")
                for name, cfg in list(feeds.items())[:5]:
                    console.print(f"  • {name}: {cfg.get('category', 'Uncategorized')}")
                if len(feeds) > 5:
                    console.print(f"  ... and {len(feeds) - 5} more")
            else:
                errors.append("No feeds configured in config/feeds.yaml")
        except Exception as e:
            errors.append(f"Feeds config error: {e}")

        # Check directories
        console.print()
        console.print(f"[green]✓[/green] Config dir: {settings.config_dir}")
        console.print(f"[green]✓[/green] Data dir: {settings.data_dir}")
    else:
        console.print("[yellow]⚠ Skipping feeds and directory checks (settings not loaded)[/yellow]")

    # Summary
    console.print()
    if errors:
        console.print("[red]Configuration errors:[/red]")
        for error in errors:
            console.print(f"  [red]✗[/red] {error}")
        raise typer.Exit(code=1)
    else:
        console.print("[green]✓ Configuration valid[/green]")


def main() -> None:
    """Entry point."""
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[dim]Aborted.[/dim]")
        raise SystemExit(130)
    except Exception as e:
        console.print(f"\n[red]Unexpected error:[/red] {e}")
        console.print("[dim]Run with --verbose for more details.[/dim]")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
