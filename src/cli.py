"""
Feed CLI.

Usage:
    ./feed run                    # Full pipeline, output to terminal (rich)
    ./feed run --format text      # Full pipeline, output as plain text
    ./feed run --format json      # Full pipeline, output as JSON
    ./feed run --send             # Full pipeline, send email instead
    ./feed schedule               # Print default scheduler config (Fri 17:00)
    ./feed schedule --status      # Show installed scheduler status
    ./feed schedule --install     # Install schedule with default backend
    ./feed ingest                 # Only fetch new articles
    ./feed test --all             # Test configured feeds for reachability/parseability
    ./feed analyze                # Only summarize pending articles
    ./feed send                   # Send digest email
    ./feed send --format rich     # Preview digest in terminal (no send)
    ./feed status                 # Show pipeline status
    ./feed config                 # Verify configuration
"""

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import click
import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.rule import Rule
from rich.table import Table

# Imports
from src.config import XDG_CONFIG_PATH, FeedConfig, get_settings
from src.logging_config import setup_logging
from src.models import ArticleStatus, DailyDigest
from src.scheduler import (
    activate_launchd,
    bootstrap_launchd,
    build_cron_line,
    build_plan,
    get_cron_managed_block,
    install_cron,
    launchd_domain_and_service,
    launchd_plist_path,
    write_launchd_plist,
)
from src.storage.db import Database

# Format choices for digest output
FormatChoice = typer.Option(
    "rich",
    "--format",
    "-f",
    help="Output format: rich (terminal), text (plain), or json",
)

__version__ = "0.3.0"

console = Console()
DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCHEDULE_LOG_FILE = Path("logs/scheduler.log")
DEFAULT_LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
ProjectRootOption = typer.Option(
    DEFAULT_PROJECT_ROOT,
    "--project-root",
    help="Feed project root",
)
ScheduleLogFileOption = typer.Option(
    DEFAULT_SCHEDULE_LOG_FILE,
    "--log-file",
    help="Log path for cron output (absolute or project-relative)",
)
LaunchAgentsDirOption = typer.Option(
    DEFAULT_LAUNCH_AGENTS_DIR,
    "--launch-agents-dir",
    help="Directory for launchd plist files",
)

# Global state
state = {"verbose": False}


def _load_settings():
    """Load settings with a user-friendly error on failure."""
    try:
        return get_settings()
    except Exception as e:
        console.print(
            "[red]Configuration error.[/red] "
            "Check your config file or environment variables.\n"
        )
        for error in getattr(e, "errors", lambda: [])():
            loc = ".".join(str(part) for part in error["loc"])
            console.print(f"  [red]✗[/red] {loc}: {error['msg']}")
        if not getattr(e, "errors", None):
            console.print(f"  [red]✗[/red] {e}")
        console.print("\n[dim]Run 'feed init' to set up, or 'feed config' to verify.[/dim]")
        raise typer.Exit(code=1) from None


def _resolve_feeds_config_path() -> Path:
    """
    Resolve feeds.yaml path.

    Prefer configured path when full settings are available; fall back to common
    defaults so feed testing works even before full API/email setup.
    """
    try:
        settings = get_settings()
        return settings.config_dir / "feeds.yaml"
    except Exception:
        xdg_feeds = XDG_CONFIG_PATH / "feeds.yaml"
        if xdg_feeds.exists():
            return xdg_feeds
        return Path("config/feeds.yaml")


def version_callback(value: bool):
    """Print version and exit."""
    if value:
        print(f"Feed CLI v{__version__}")
        raise typer.Exit()


_QUICK_REF_ITEMS = [
    ("run", "[--send] [--format rich|text|json] [--no-cache]"),
    (
        "schedule",
        "[--status] [--backend auto|cron|launchd] "
        "[--frequency daily|weekly] [--install]",
    ),
    ("ingest", ""),
    ("analyze", "[--format rich|text|json] [--no-cache]"),
    ("send", "[--test] [--format rich|text|json]"),
    ("test", "[--url URL | --name NAME | --all] [--strict] [--timeout N]"),
    ("status", "[--json]"),
    ("config", ""),
    ("cache", "[--clear]"),
    ("init", "[--force]"),
]


class _HelpGroup(typer.core.TyperGroup):
    """Custom group that adds a boxed quick-reference section to --help."""

    def format_help(self, ctx, formatter):
        if not typer.core.HAS_RICH or self.rich_markup_mode is None:
            super().format_help(ctx, formatter)
            with formatter.section("Quick Reference"):
                formatter.write_dl(_QUICK_REF_ITEMS)
            return

        from typer import rich_utils

        rich_utils.rich_format_help(
            obj=self,
            ctx=ctx,
            markup_mode=self.rich_markup_mode,
        )

        quick_commands = [
            click.Command(name=command, help=usage, short_help=usage)
            for command, usage in _QUICK_REF_ITEMS
        ]
        rich_utils._print_commands_panel(
            name="Quick Reference",
            commands=quick_commands,
            markup_mode=self.rich_markup_mode,
            console=rich_utils._get_rich_console(),
            cmd_len=max(len(command) for command, _ in _QUICK_REF_ITEMS),
        )


app = typer.Typer(
    name="feed",
    help="Feed - Your newsletter digest CLI",
    no_args_is_help=True,
    add_completion=False,
    cls=_HelpGroup,
    rich_markup_mode="markdown",
)


@app.callback()
def main(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging output."
    ),
    version: bool | None = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit."
    ),
):
    """
    Feed - Your newsletter digest CLI
    """
    state["verbose"] = verbose
    if verbose:
        setup_logging("DEBUG")
    else:
        setup_logging("INFO")


@app.command()
def init(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing config"),
) -> None:
    """Set up Feed with an interactive wizard."""
    config_file = XDG_CONFIG_PATH / "config.env"

    # Check if config already exists
    if config_file.exists() and not force:
        console.print(f"[yellow]Config already exists at {config_file}[/yellow]")
        console.print("Use --force to overwrite.")
        raise typer.Exit(code=1)

    console.print(Panel.fit(
        "[bold]Feed Setup Wizard[/bold]\n"
        "Configure your Feed agent",
        border_style="blue",
    ))

    # LLM Provider
    console.print("\n[bold cyan]LLM Configuration[/bold cyan]")
    provider = typer.prompt(
        "LLM provider",
        default="gemini",
        type=typer.Choice(["gemini", "openai", "anthropic"]),
    )

    api_key = typer.prompt(
        f"API key for {provider}",
        hide_input=True,
    )

    # Validate API key is not empty
    if not api_key.strip():
        console.print("[red]API key cannot be empty[/red]")
        raise typer.Exit(code=1)

    # Email settings
    console.print("\n[bold cyan]Email Configuration[/bold cyan]")
    resend_api_key = typer.prompt(
        "Resend API key",
        hide_input=True,
    )

    if not resend_api_key.strip():
        console.print("[red]Resend API key cannot be empty[/red]")
        raise typer.Exit(code=1)

    email_from = typer.prompt("Sender email (e.g., digest@yourdomain.com)")
    email_to = typer.prompt("Recipient email")

    # Create config directory
    XDG_CONFIG_PATH.mkdir(parents=True, exist_ok=True)

    # Write config file
    config_content = f"""# Feed Configuration
# Generated by 'feed init'

# Paths (point to XDG config directory)
CONFIG_DIR={XDG_CONFIG_PATH}
DATA_DIR={XDG_CONFIG_PATH / "data"}

# LLM Settings
LLM_PROVIDER={provider}
LLM_API_KEY={api_key}

# Email Settings (Resend)
RESEND_API_KEY={resend_api_key}
EMAIL_FROM={email_from}
EMAIL_TO={email_to}

# Optional: Override defaults
# LLM_MODEL=
# DIGEST_HOUR=7
# DIGEST_TIMEZONE=America/New_York
# MAX_ARTICLES_PER_FEED=10
# LOOKBACK_HOURS=24
"""

    config_file.write_text(config_content)
    console.print(f"\n[green]✓[/green] Config written to {config_file}")

    # Offer to copy sample feeds.yaml
    console.print("\n[bold cyan]Feeds Configuration[/bold cyan]")
    feeds_dest = XDG_CONFIG_PATH / "feeds.yaml"
    sample_feeds = Path(__file__).parent.parent / "config" / "feeds.yaml"

    if feeds_dest.exists() and not force:
        console.print(f"[dim]feeds.yaml already exists at {feeds_dest}[/dim]")
    elif sample_feeds.exists():
        copy_feeds = typer.confirm(
            f"Copy sample feeds.yaml to {feeds_dest}?",
            default=True,
        )
        if copy_feeds:
            import shutil
            shutil.copy(sample_feeds, feeds_dest)
            console.print(f"[green]✓[/green] Copied feeds.yaml to {feeds_dest}")
            console.print("[dim]Edit this file to add your RSS feeds[/dim]")
    else:
        console.print("[dim]No sample feeds.yaml found to copy[/dim]")

    # Summary
    console.print(Panel.fit(
        "[bold green]Setup complete![/bold green]\n\n"
        f"Config: {config_file}\n"
        f"Feeds: {feeds_dest if feeds_dest.exists() else 'Not configured'}\n\n"
        "[dim]Run 'feed config' to verify, or 'feed run' to start[/dim]",
        border_style="green",
    ))


def _print_digest(digest: DailyDigest, output_format: str) -> None:
    """Print digest to terminal in specified format."""
    if output_format == "json":
        print(json.dumps(digest.model_dump(mode="json"), indent=2, default=str))
    elif output_format == "text":
        from src.deliver.renderer import EmailRenderer
        renderer = EmailRenderer()
        print(renderer.render_text(digest))
    else:  # rich
        _print_digest_rich(digest)


def _print_digest_rich(digest: DailyDigest) -> None:
    """Print digest with Rich formatting."""
    # Header panel
    header_text = (
        f"[bold]Daily Digest[/bold] - {digest.date.strftime('%B %d, %Y')}\n"
        f"{digest.total_articles} articles from {digest.total_feeds} sources"
    )
    console.print(Panel(header_text, border_style="blue"))

    # Overall themes
    if digest.overall_themes:
        console.print("\n[bold cyan]TODAY'S THEMES[/bold cyan]")
        for theme in digest.overall_themes:
            console.print(f"  • {theme}")

    # Categories
    for category in digest.categories:
        # Category header
        console.print()
        console.print(Rule(
            f"[bold]{category.name}[/bold] ({category.article_count} "
            f"article{'s' if category.article_count != 1 else ''})",
            style="dim",
        ))

        # Synthesis
        if category.synthesis:
            console.print(f"\n[dim italic]{category.synthesis}[/dim italic]")

        # Key takeaways
        if category.top_takeaways:
            console.print("\n[bold]KEY TAKEAWAYS:[/bold]")
            for takeaway in category.top_takeaways[:3]:
                console.print(f"  • {takeaway}")

        # Articles table
        if category.articles:
            table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
            table.add_column("Article", style="white", max_width=45, no_wrap=False)
            table.add_column("Source", style="dim", max_width=15)
            table.add_column("Summary", style="dim", max_width=50, no_wrap=False)

            for article in category.articles:
                title = article.title
                if len(title) > 45:
                    title = title[:42] + "..."
                summary = article.summary or ""
                if len(summary) > 80:
                    summary = summary[:77] + "..."
                table.add_row(title, article.feed_name, summary)

            console.print()
            console.print(table)

    # Must-read section
    if digest.must_read:
        console.print()
        console.print("[bold cyan]MUST READ:[/bold cyan]")
        for url in digest.must_read:
            console.print(f"  • {url}")

    # Footer
    console.print()
    console.print(Panel.fit(
        f"[dim]Generated in {digest.processing_time_seconds:.1f}s[/dim]",
        border_style="dim",
    ))


@app.command()
def run(
    send: bool = typer.Option(False, "--send", help="Send email instead of terminal output"),
    output_format: str = FormatChoice,
    no_cache: bool = typer.Option(False, "--no-cache", help="Skip cache, re-summarize all"),
) -> None:
    """Run the full digest pipeline: ingest → analyze → send."""
    settings = _load_settings()

    console.print(Panel.fit(
        "[bold]📬 Feed CLI[/bold]\n"
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
        for error in ingest_result.errors[:5]:
            console.print(f"    [yellow]• {error}[/yellow]")
        if len(ingest_result.errors) > 5:
            console.print(
                f"    [dim]... and {len(ingest_result.errors) - 5} more feed errors[/dim]"
            )

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
            analysis_result = run_analysis(db=db, no_cache=no_cache)
            progress.remove_task(task)

        console.print(f"  ✓ Analyzed {analysis_result.articles_analyzed} articles")
        console.print(
            f"  ✓ Used {analysis_result.tokens_used:,} tokens "
            f"(${analysis_result.cost_estimate_usd:.4f})"
        )

    # Phase 3: Output or Send
    if analysis_result and analysis_result.digest:
        if send:
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
            console.print("\n[bold cyan]Phase 3: Digest output[/bold cyan]\n")
            _print_digest(analysis_result.digest, output_format)
    else:
        console.print("\n[dim]No digest to output[/dim]")

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

    if result.errors:
        console.print("\n[yellow]Feed failures:[/yellow]")
        for error in result.errors[:10]:
            console.print(f"  • {error}")
        if len(result.errors) > 10:
            console.print(f"  ... and {len(result.errors) - 10} more")
        raise typer.Exit(code=1)


@app.command("test")
def test_feeds(
    url: str | None = typer.Option(
        None,
        "--url",
        help="Test a one-off feed URL (does not require feeds.yaml)",
    ),
    name: str | None = typer.Option(
        None,
        "--name",
        help="Test one configured feed by name",
    ),
    all_feeds: bool = typer.Option(
        False,
        "--all",
        help="Test all configured feeds in feeds.yaml (default when no selector is provided)",
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Fail if parser warning occurs or feed has zero entries",
    ),
    timeout: int = typer.Option(20, "--timeout", min=1, help="HTTP timeout in seconds"),
    lookback_hours: int = typer.Option(
        24,
        "--lookback-hours",
        min=1,
        help="Lookback window used to count recent entries",
    ),
    max_articles: int = typer.Option(
        10,
        "--max-articles",
        min=1,
        help="Maximum recent articles to inspect per feed",
    ),
) -> None:
    """Test feed URLs and parser health before adding/running them."""
    selectors_used = sum([bool(url), bool(name), bool(all_feeds)])
    if selectors_used > 1:
        console.print("[red]Use only one of --url, --name, or --all.[/red]")
        raise typer.Exit(code=1)
    if selectors_used == 0:
        all_feeds = True

    feeds_to_test: list[tuple[str, dict[str, str]]] = []
    if url:
        feeds_to_test = [("ad-hoc", {"url": url, "category": "Ad-hoc"})]
    else:
        feeds_path = _resolve_feeds_config_path()
        try:
            feed_config = FeedConfig(feeds_path)
        except Exception as e:
            console.print(f"[red]Failed to load feeds config ({feeds_path}): {e}[/red]")
            raise typer.Exit(code=1) from None

        feeds = feed_config.feeds
        if not feeds:
            console.print(f"[yellow]No feeds configured in {feeds_path}[/yellow]")
            raise typer.Exit(code=1)

        if name:
            if name not in feeds:
                sample_names = ", ".join(list(feeds.keys())[:8])
                console.print(f"[red]Feed '{name}' not found in {feeds_path}[/red]")
                if sample_names:
                    console.print(f"[dim]Configured feeds: {sample_names}[/dim]")
                raise typer.Exit(code=1)
            feeds_to_test = [(name, feeds[name])]
        else:
            feeds_to_test = list(feeds.items())

    from src.ingest.feeds import fetch_feed

    console.print(f"[bold]Testing {len(feeds_to_test)} feed(s)...[/bold]")
    results = []
    for feed_name, feed_cfg in feeds_to_test:
        feed_url = str(feed_cfg.get("url", "")).strip()
        category = str(feed_cfg.get("category", "Uncategorized"))
        if not feed_url:
            from src.ingest.feeds import FeedResult

            results.append(
                FeedResult(
                    feed_url="",
                    feed_name=feed_name,
                    articles=[],
                    success=False,
                    error="Missing URL",
                    attempts=0,
                )
            )
            continue

        results.append(
            fetch_feed(
                feed_url=feed_url,
                feed_name=feed_name,
                category=category,
                lookback_hours=lookback_hours,
                max_articles=max_articles,
                timeout=timeout,
            )
        )

    table = Table(title="Feed Test Results")
    table.add_column("Feed", style="cyan", no_wrap=True)
    table.add_column("Result", style="bold", no_wrap=True)
    table.add_column("HTTP", style="green", no_wrap=True)
    table.add_column("Entries", style="green", no_wrap=True)
    table.add_column("Details", style="dim", overflow="fold")

    failures: list[str] = []
    for result in results:
        strict_reasons: list[str] = []
        if strict and result.entry_count == 0:
            strict_reasons.append("zero entries")
        if strict and result.bozo:
            strict_reasons.append("parser warning")

        passed = result.success and not strict_reasons
        status_label = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
        http_label = str(result.status_code) if result.status_code is not None else "-"
        details_parts: list[str] = []

        if result.content_type:
            details_parts.append(result.content_type.split(";")[0])
        if result.response_time_ms is not None:
            details_parts.append(f"{result.response_time_ms:.0f} ms")
        if result.attempts > 1:
            details_parts.append(f"{result.attempts} attempts")
        if result.final_url and result.final_url != result.feed_url:
            details_parts.append(f"redirected to {result.final_url}")
        if result.bozo_exception:
            details_parts.append(f"parser: {result.bozo_exception}")

        if strict_reasons:
            details_parts.append("strict: " + ", ".join(strict_reasons))
        if result.error:
            details_parts.append(result.error)

        table.add_row(
            result.feed_name,
            status_label,
            http_label,
            str(result.entry_count),
            " | ".join(details_parts) if details_parts else "-",
        )

        if not passed:
            reason = result.error or ", ".join(strict_reasons) or "unknown failure"
            failures.append(f"{result.feed_name}: {reason}")

    console.print(table)

    if failures:
        console.print("\n[red]Feed test failures:[/red]")
        for failure in failures:
            console.print(f"  • {failure}")
        raise typer.Exit(code=1)

    console.print("\n[green]✓ All feed tests passed[/green]")


@app.command()
def analyze(
    output_format: str | None = typer.Option(
        None,
        "--format",
        "-f",
        help="Show digest after analysis (rich, text, or json)",
    ),
    no_cache: bool = typer.Option(False, "--no-cache", help="Skip cache, re-summarize all"),
) -> None:
    """Summarize pending articles with the configured LLM."""
    settings = _load_settings()

    db = Database(settings.data_dir / "articles.db")
    pending = db.get_pending_articles()

    if not pending:
        console.print("[yellow]No pending articles to analyze[/yellow]")
        return

    console.print(f"[bold]Analyzing {len(pending)} articles...[/bold]")

    from src.analyze import run_analysis

    result = run_analysis(db=db, no_cache=no_cache)

    table = Table(title="Analysis Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Articles analyzed", str(result.articles_analyzed))
    table.add_row("Tokens used", f"{result.tokens_used:,}")
    table.add_row("Estimated cost", f"${result.cost_estimate_usd:.4f}")
    table.add_row("Duration", f"{result.duration_seconds:.1f}s")

    console.print(table)

    if result.digest:
        console.print(
            f"\n[green]Digest ready with {len(result.digest.categories)} categories[/green]"
        )
        if output_format:
            console.print()
            _print_digest(result.digest, output_format)


@app.command()
def send(
    test: bool = typer.Option(False, "--test", help="Send test email instead"),
    output_format: str | None = typer.Option(
        None,
        "--format",
        "-f",
        help="Preview digest in terminal instead of sending (rich, text, or json)",
    ),
) -> None:
    """Send the digest email, or preview with --format."""
    settings = _load_settings()

    # Build digest from recent summarized articles (needed for both preview and send)
    db = Database(settings.data_dir / "articles.db")
    since = datetime.now(UTC) - timedelta(hours=settings.lookback_hours)
    articles = db.get_articles_since(since, status=ArticleStatus.SUMMARIZED)

    if not articles:
        console.print("[yellow]No summarized articles available[/yellow]")
        return

    from src.analyze.digest_builder import DigestBuilder

    builder = DigestBuilder()
    digest = builder.build_digest(articles)

    # Preview mode: output to terminal instead of sending
    if output_format:
        console.print(f"[bold]Preview of digest ({len(articles)} articles):[/bold]\n")
        _print_digest(digest, output_format)
        return

    # Test mode: send test email
    if test:
        from src.deliver import EmailSender
        sender = EmailSender()
        console.print("[bold]Sending test email...[/bold]")
        result = sender.send_test_email()
    else:
        # Normal send
        from src.deliver import EmailSender
        sender = EmailSender()
        console.print(f"[bold]Sending digest ({len(articles)} articles)...[/bold]")
        result = sender.send_digest(digest)

    if result.success:
        console.print("[green]✓ Email sent successfully[/green]")
        console.print(f"  Email ID: {result.email_id}")
    else:
        console.print(f"[red]✗ Send failed: {result.error}[/red]")
        raise typer.Exit(code=1)


@app.command()
def schedule(
    backend: str = typer.Option(
        "auto",
        "--backend",
        help="Scheduler backend: auto, cron, or launchd",
    ),
    frequency: str = typer.Option(
        "weekly",
        "--frequency",
        "-q",
        help="Schedule frequency: daily or weekly",
    ),
    day_of_week: str = typer.Option(
        "fri",
        "--day-of-week",
        "--day",
        help="Day for weekly schedules (sun, mon, tue, wed, thu, fri, sat)",
    ),
    time: str = typer.Option(
        "17:00",
        "--time",
        help="Run time in 24h HH:MM",
    ),
    lookback_hours: int | None = typer.Option(
        None,
        "--lookback-hours",
        min=1,
        help="LOOKBACK_HOURS override (weekly defaults to 168; daily to 24)",
    ),
    status: bool = typer.Option(
        False,
        "--status",
        help="Show installed scheduler status for the selected backend/label",
    ),
    install: bool = typer.Option(
        False,
        "--install",
        help="Install the schedule into the selected scheduler",
    ),
    activate: bool = typer.Option(
        False,
        "--activate",
        help="For launchd, run immediately via kickstart after install",
    ),
    replace: bool = typer.Option(
        True,
        "--replace/--no-replace",
        help="For cron install, replace existing managed block with the same label",
    ),
    label: str = typer.Option(
        "com.user.feed",
        "--label",
        help="Job label (launchd label and cron block marker)",
    ),
    project_root: Path = ProjectRootOption,
    runner: str | None = typer.Option(
        None,
        "--runner",
        help="Command used to invoke feed (default: ./feed or 'uv run feed')",
    ),
    log_file: Path = ScheduleLogFileOption,
    launch_agents_dir: Path = LaunchAgentsDirOption,
) -> None:
    """Generate, inspect, or install a schedule for `feed run --send`."""
    freq = frequency.strip().lower()
    day = day_of_week if freq == "weekly" else None
    try:
        plan = build_plan(
            backend=backend,
            frequency=frequency,
            day_of_week=day,
            time_str=time,
            lookback_hours=lookback_hours,
            project_root=project_root,
            runner_override=runner,
            log_file=log_file,
            label=label,
            launch_agents_dir=launch_agents_dir,
        )
    except ValueError as exc:
        console.print(f"[red]Invalid schedule options:[/red] {exc}")
        raise typer.Exit(code=1) from None

    if plan.backend == "launchd" and sys.platform != "darwin":
        console.print("[red]launchd scheduling is only supported on macOS[/red]")
        raise typer.Exit(code=1)

    if activate and not install:
        console.print("[red]--activate requires --install[/red]")
        raise typer.Exit(code=1)

    if status and (install or activate):
        console.print("[red]--status cannot be combined with --install/--activate[/red]")
        raise typer.Exit(code=1)

    if activate and plan.backend != "launchd":
        console.print("[red]--activate is only valid with launchd[/red]")
        raise typer.Exit(code=1)

    schedule_table = Table(title="Schedule Plan")
    schedule_table.add_column("Setting", style="cyan")
    schedule_table.add_column("Value", style="green")
    schedule_table.add_row("Backend", plan.backend)
    schedule_table.add_row("Frequency", plan.frequency)
    schedule_table.add_row("Day", plan.day_of_week or "-")
    schedule_table.add_row("Time", f"{plan.hour:02}:{plan.minute:02}")
    schedule_table.add_row("Lookback hours", str(plan.lookback_hours))
    schedule_table.add_row("Runner", plan.runner)
    schedule_table.add_row("Project root", str(plan.project_root))
    console.print(schedule_table)

    if status:
        if plan.backend == "cron":
            try:
                block = get_cron_managed_block(plan.label)
            except Exception as exc:
                console.print(f"[red]Failed to read cron status:[/red] {exc}")
                raise typer.Exit(code=1) from None

            if not block:
                console.print("\n[yellow]No managed cron schedule found for this label.[/yellow]")
                console.print("[dim]Install with: feed schedule --backend cron --install[/dim]")
                return

            console.print("\n[green]✓ Managed cron schedule found[/green]")
            console.print(f"[dim]Label: {plan.label}[/dim]")
            console.print("\n[bold]Cron block:[/bold]")
            console.print(block)
            return

        plist_path = launchd_plist_path(plan)
        _, service = launchd_domain_and_service(plan.label)
        plist_exists = plist_path.exists()
        loaded = False
        status_detail = ""
        if plist_exists:
            result = subprocess.run(
                ["launchctl", "print", service],
                capture_output=True,
                text=True,
                check=False,
            )
            loaded = result.returncode == 0
            if not loaded:
                status_detail = (result.stderr or result.stdout).strip()

        status_table = Table(title="Launchd Status")
        status_table.add_column("Check", style="cyan")
        status_table.add_column("Value", style="green")
        status_table.add_row("Plist path", str(plist_path))
        status_table.add_row("Plist exists", "yes" if plist_exists else "no")
        status_table.add_row("Service", service)
        status_table.add_row("Loaded", "yes" if loaded else "no")
        console.print()
        console.print(status_table)

        if status_detail:
            console.print(f"\n[yellow]{status_detail}[/yellow]")
        if not plist_exists:
            console.print("[dim]Install with: feed schedule --backend launchd --install[/dim]")
        return

    if plan.backend == "cron":
        cron_line = build_cron_line(plan)
        if not install:
            console.print("\n[bold]Cron entry:[/bold]")
            console.print(cron_line)
            console.print(
                "\n[dim]Use --install to write this managed block into your user crontab.[/dim]"
            )
            return

        try:
            install_cron(plan, replace_existing=replace)
        except Exception as exc:
            console.print(f"[red]Failed to install cron schedule:[/red] {exc}")
            raise typer.Exit(code=1) from None

        console.print("\n[green]✓ Installed cron schedule[/green]")
        console.print("[dim]Verify with: crontab -l[/dim]")
        console.print(f"[dim]Logs: {plan.log_file}[/dim]")
        return

    plist_path = launchd_plist_path(plan)
    stdout_log = plan.project_root / "logs" / "launchd.stdout.log"
    stderr_log = plan.project_root / "logs" / "launchd.stderr.log"

    if not install:
        console.print("\n[bold]Launchd plist path:[/bold]")
        console.print(str(plist_path))
        console.print(
            "\n[dim]Use --install to write + bootstrap. Add --activate to run immediately.[/dim]"
        )
        return

    try:
        plist_path = write_launchd_plist(plan)
    except Exception as exc:
        console.print(f"[red]Failed to write launchd plist:[/red] {exc}")
        raise typer.Exit(code=1) from None

    console.print("\n[green]✓ Wrote launchd plist[/green]")
    console.print(f"[dim]{plist_path}[/dim]")

    if activate:
        try:
            domain, service = activate_launchd(plan, plist_path)
        except Exception as exc:
            console.print(f"[red]Failed to activate launchd service:[/red] {exc}")
            raise typer.Exit(code=1) from None
        console.print("[green]✓ Activated launchd service[/green]")
    else:
        try:
            domain, service = bootstrap_launchd(plan, plist_path)
        except Exception as exc:
            console.print(f"[red]Failed to bootstrap launchd service:[/red] {exc}")
            raise typer.Exit(code=1) from None
        console.print("[green]✓ Installed launchd service[/green]")

    console.print("\n[dim]Next commands:[/dim]")
    console.print(f"[dim]launchctl print {service}[/dim]")
    console.print(f"[dim]launchctl bootout {service}[/dim]")
    if not activate:
        console.print(f"[dim]launchctl kickstart -k {service}[/dim]")
        console.print(f"[dim]launchctl bootstrap {domain} {plist_path}[/dim]")
    console.print(f"[dim]stdout: {stdout_log}[/dim]")
    console.print(f"[dim]stderr: {stderr_log}[/dim]")


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

    # Show config file locations
    console.print("[dim]Config search paths:[/dim]")
    xdg_config = XDG_CONFIG_PATH / "config.env"
    xdg_status = "[green](exists)[/green]" if xdg_config.exists() else "[dim](not found)[/dim]"
    console.print(f"  1. {xdg_config} {xdg_status}")
    local_env = Path(".env")
    local_status = "[green](exists)[/green]" if local_env.exists() else "[dim](not found)[/dim]"
    console.print(f"  2. {local_env.absolute()} {local_status}")
    console.print()

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
        console.print(
            "[yellow]⚠ Skipping feeds and directory checks (settings not loaded)[/yellow]"
        )

    # Summary
    console.print()
    if errors:
        console.print("[red]Configuration errors:[/red]")
        for error in errors:
            console.print(f"  [red]✗[/red] {error}")
        raise typer.Exit(code=1)
    else:
        console.print("[green]✓ Configuration valid[/green]")


@app.command("cache")
def cache_cmd(
    clear: bool = typer.Option(False, "--clear", help="Clear all cached LLM responses"),
) -> None:
    """Show cache statistics or clear cached responses."""
    settings = _load_settings()

    from src.storage.cache import CacheStore

    cache = CacheStore(
        db_path=settings.data_dir / "articles.db",
        default_ttl_days=settings.cache_ttl_days,
    )

    if clear:
        count = cache.clear()
        console.print(f"[green]Cleared {count} cached entries[/green]")
        return

    stats = cache.stats()
    table = Table(title="Cache Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Total entries", str(stats["total_entries"]))
    table.add_row("Expired entries", str(stats["expired_entries"]))
    console.print(table)


def cli() -> None:
    """Entry point."""
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[dim]Aborted.[/dim]")
        raise SystemExit(130) from None
    except Exception as e:
        console.print(f"\n[red]Unexpected error:[/red] {e}")
        console.print("[dim]Run with --verbose for more details.[/dim]")
        raise SystemExit(1) from e


if __name__ == "__main__":
    cli()
