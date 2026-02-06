# Phase 4: Orchestration & CLI

**Goal**: Create a polished CLI interface and scheduling system that ties all components together into a reliable daily pipeline.

**Estimated Time**: 2-3 hours

**Dependencies**: Phases 1-3 completed

---

## Overview

The orchestration layer provides the user interface and automation:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLI & Scheduling                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌──────────────┐                                                  │
│   │   Typer CLI  │                                                  │
│   │              │                                                  │
│   │  • run       │──────────────────────────────────────────┐       │
│   │  • ingest    │                                          │       │
│   │  • analyze   │                                          ▼       │
│   │  • send      │     ┌──────────────────────────────────────┐     │
│   │  • status    │     │          Pipeline                    │     │
│   │  • config    │     │                                      │     │
│   └──────────────┘     │  Ingest ──▶ Analyze ──▶ Deliver     │     │
│                        │                                      │     │
│                        └──────────────────────────────────────┘     │
│                                       │                             │
│   ┌──────────────┐                    │                             │
│   │   Scheduler  │◀───────────────────┘                             │
│   │   (cron)     │                                                  │
│   └──────────────┘                                                  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Single Command**: `./feed run` does everything
2. **Modular**: Each phase runnable independently
3. **Observable**: Clear progress and status reporting
4. **Recoverable**: Can resume from failures

---

## Tasks

### 4.1 Main CLI

Create `scripts/run_digest.py`:

```python
"""
Feed Agent CLI.

Usage:
    digest run          # Full pipeline: ingest, analyze, send
    digest ingest       # Only fetch new articles
    digest analyze      # Only summarize pending articles
    digest send         # Only send digest for summarized articles
    digest status       # Show pipeline status
    digest config       # Verify configuration
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import FeedConfig, get_settings
from src.logging_config import setup_logging
from src.models import ArticleStatus
from src.storage.db import Database

app = typer.Typer(
    name="digest",
    help="Feed Agent - Your personal newsletter intelligence",
    no_args_is_help=True,
)
console = Console()


@app.command()
def run(
    skip_send: bool = typer.Option(False, "--skip-send", help="Skip email delivery"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """Run the full digest pipeline: ingest → analyze → send."""
    setup_logging("DEBUG" if verbose else "INFO")
    settings = get_settings()
    
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
def ingest(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """Fetch new articles from RSS feeds."""
    setup_logging("DEBUG" if verbose else "INFO")
    settings = get_settings()
    
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
def analyze(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """Summarize pending articles with Claude."""
    setup_logging("DEBUG" if verbose else "INFO")
    settings = get_settings()
    
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
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    test: bool = typer.Option(False, "--test", help="Send test email instead"),
) -> None:
    """Send the digest email."""
    setup_logging("DEBUG" if verbose else "INFO")
    settings = get_settings()
    
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


@app.command()
def status() -> None:
    """Show pipeline status and statistics."""
    settings = get_settings()
    
    db_path = settings.data_dir / "articles.db"
    
    if not db_path.exists():
        console.print("[yellow]No database found. Run 'digest ingest' first.[/yellow]")
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
    
    # Status table
    status_table = Table(title="Article Status")
    status_table.add_column("Status", style="cyan")
    status_table.add_column("Count", style="green")
    
    for row in status_counts:
        status_table.add_row(row[0], str(row[1]))
    
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
    
    # Check settings
    try:
        settings = get_settings()
        console.print("[green]✓[/green] Settings loaded")
        
        # Check API keys (show partial)
        if settings.anthropic_api_key:
            key_preview = settings.anthropic_api_key[:10] + "..."
            console.print(f"  Anthropic API key: {key_preview}")
        else:
            errors.append("Missing ANTHROPIC_API_KEY")
        
        if settings.resend_api_key:
            key_preview = settings.resend_api_key[:10] + "..."
            console.print(f"  Resend API key: {key_preview}")
        else:
            errors.append("Missing RESEND_API_KEY")
        
        console.print(f"  Email from: {settings.email_from}")
        console.print(f"  Email to: {settings.email_to}")
        console.print(f"  Claude model: {settings.claude_model}")
        
    except Exception as e:
        errors.append(f"Settings error: {e}")
    
    # Check feeds config
    console.print()
    try:
        feed_config = FeedConfig(settings.config_dir / "feeds.yaml")
        feeds = feed_config.feeds
        
        if feeds:
            console.print(f"[green]✓[/green] Feeds configured: {len(feeds)}")
            for name, config in list(feeds.items())[:5]:
                console.print(f"  • {name}: {config.get('category', 'Uncategorized')}")
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
    
    # Summary
    console.print()
    if errors:
        console.print("[red]Configuration errors:[/red]")
        for error in errors:
            console.print(f"  [red]✗[/red] {error}")
    else:
        console.print("[green]✓ Configuration valid[/green]")


def main() -> None:
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
```

- [ ] Create `scripts/run_digest.py`
- [ ] Test CLI commands: `./feed --help`
- [ ] Test each subcommand: `config`, `status`, `ingest`, etc.

### 4.2 Make CLI Installable

Update `pyproject.toml` to add the CLI entry point:

```toml
[project.scripts]
digest = "scripts.run_digest:main"
```

Then install in development mode:

```bash
uv pip install -e .
```

Now you can run:
```bash
digest run
digest status
digest config
```

- [ ] Update `pyproject.toml` with entry point
- [ ] Install in dev mode
- [ ] Verify `digest` command works

### 4.3 Scheduling with Cron

Create `scripts/setup_cron.py`:

```python
"""Set up cron job for daily digest."""

import os
import sys
from pathlib import Path

def get_cron_command() -> str:
    """Generate the cron command."""
    # Get the Python interpreter path
    python_path = sys.executable
    
    # Get the script path
    script_dir = Path(__file__).parent
    run_script = script_dir / "run_digest.py"
    
    # Get the project root for PYTHONPATH
    project_root = script_dir.parent
    
    # Build the command
    command = (
        f"cd {project_root} && "
        f"PYTHONPATH={project_root} "
        f"{python_path} {run_script} run "
        f">> {project_root}/logs/digest.log 2>&1"
    )
    
    return command


def main() -> None:
    """Print instructions for setting up cron."""
    command = get_cron_command()
    
    print("=" * 60)
    print("Cron Setup Instructions")
    print("=" * 60)
    
    print("\n1. Create logs directory:")
    print("   mkdir -p logs")
    
    print("\n2. Open crontab for editing:")
    print("   crontab -e")
    
    print("\n3. Add this line (runs at 7 AM daily):")
    print(f"\n   0 7 * * * {command}")
    
    print("\n4. Save and exit")
    
    print("\n" + "-" * 60)
    print("Alternative: Run every 6 hours")
    print("-" * 60)
    print(f"\n   0 */6 * * * {command}")
    
    print("\n" + "-" * 60)
    print("To verify cron is set up:")
    print("-" * 60)
    print("   crontab -l")
    
    print("\n" + "-" * 60)
    print("To test the command manually:")
    print("-" * 60)
    print(f"   {command}")


if __name__ == "__main__":
    main()
```

- [ ] Create `scripts/setup_cron.py`
- [ ] Run `uv run python scripts/setup_cron.py` for instructions
- [ ] Set up cron job if desired

### 4.4 Launchd for macOS (Alternative to Cron)

Create `scripts/setup_launchd.py`:

```python
"""Generate launchd plist for macOS scheduling."""

import os
import sys
from pathlib import Path

PLIST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.feed</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>{script_path}</string>
        <string>run</string>
    </array>
    
    <key>WorkingDirectory</key>
    <string>{project_root}</string>
    
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>{project_root}</string>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>{hour}</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    
    <key>StandardOutPath</key>
    <string>{log_path}/digest.stdout.log</string>
    
    <key>StandardErrorPath</key>
    <string>{log_path}/digest.stderr.log</string>
    
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
"""


def main() -> None:
    """Generate and install launchd plist."""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # Configuration
    python_path = sys.executable
    script_path = script_dir / "run_digest.py"
    log_path = project_root / "logs"
    hour = 7  # 7 AM
    
    # Generate plist content
    plist_content = PLIST_TEMPLATE.format(
        python_path=python_path,
        script_path=script_path,
        project_root=project_root,
        log_path=log_path,
        hour=hour,
    )
    
    # Paths
    plist_name = "com.user.feed.plist"
    launch_agents_dir = Path.home() / "Library" / "LaunchAgents"
    plist_path = launch_agents_dir / plist_name
    
    print("=" * 60)
    print("macOS Launchd Setup")
    print("=" * 60)
    
    # Create logs directory
    log_path.mkdir(exist_ok=True)
    print(f"\n✓ Created logs directory: {log_path}")
    
    # Write plist
    launch_agents_dir.mkdir(exist_ok=True)
    with open(plist_path, "w") as f:
        f.write(plist_content)
    print(f"✓ Created plist: {plist_path}")
    
    print("\n" + "-" * 60)
    print("Next steps:")
    print("-" * 60)
    
    print(f"\n1. Load the agent:")
    print(f"   launchctl load {plist_path}")
    
    print(f"\n2. To run immediately (for testing):")
    print(f"   launchctl start com.user.feed")
    
    print(f"\n3. To check status:")
    print(f"   launchctl list | grep substack")
    
    print(f"\n4. To unload (disable):")
    print(f"   launchctl unload {plist_path}")
    
    print(f"\n5. View logs:")
    print(f"   tail -f {log_path}/digest.stdout.log")
    
    print("\n" + "-" * 60)
    print(f"Scheduled to run daily at {hour}:00 AM")
    print("-" * 60)


if __name__ == "__main__":
    main()
```

- [ ] Create `scripts/setup_launchd.py`
- [ ] Run `uv run python scripts/setup_launchd.py` to set up
- [ ] Load the agent and test

### 4.5 Healthcheck Script

Create `scripts/healthcheck.py`:

```python
"""Quick healthcheck for the digest agent."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_settings
from src.storage.db import Database


def main() -> int:
    """Run healthcheck and return exit code."""
    settings = get_settings()
    
    issues = []
    
    # Check database exists
    db_path = settings.data_dir / "articles.db"
    if not db_path.exists():
        issues.append("Database not found")
    else:
        db = Database(db_path)
        
        # Check for recent activity
        with db._connection() as conn:
            last_article = conn.execute("""
                SELECT MAX(created_at) FROM articles
            """).fetchone()[0]
            
            if last_article:
                last_time = datetime.fromisoformat(last_article)
                age_hours = (datetime.now() - last_time).total_seconds() / 3600
                
                if age_hours > 48:
                    issues.append(f"No new articles in {age_hours:.0f} hours")
            else:
                issues.append("No articles in database")
    
    # Check config
    if not settings.anthropic_api_key:
        issues.append("Missing Anthropic API key")
    
    if not settings.resend_api_key:
        issues.append("Missing Resend API key")
    
    # Output
    if issues:
        print("UNHEALTHY")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    else:
        print("HEALTHY")
        return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] Create `scripts/healthcheck.py`
- [ ] Test: `uv run python scripts/healthcheck.py`

---

## CLI Command Reference

| Command | Description |
|---------|-------------|
| `./feed run` | Full pipeline (ingest + analyze + send) |
| `./feed run --skip-send` | Run without sending email |
| `./feed ingest` | Only fetch new articles |
| `./feed analyze` | Only summarize pending articles |
| `./feed send` | Send digest from summarized articles |
| `./feed send --test` | Send test email |
| `./feed status` | Show article counts and recent items |
| `./feed config` | Verify configuration |

---

## Completion Checklist

- [ ] All CLI commands work correctly
- [ ] `./feed run` completes full pipeline
- [ ] `./feed status` shows accurate counts
- [ ] Scheduling is configured (cron or launchd)
- [ ] Healthcheck script works
- [ ] Logs are being written

## Next Phase

Proceed to `06-PHASE-POLISH.md` for error handling, monitoring, and refinements.
