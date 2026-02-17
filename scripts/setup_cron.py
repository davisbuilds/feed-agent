"""Print cron setup instructions for scheduled Feed runs."""

from __future__ import annotations

import argparse
import shlex
from pathlib import Path

from src.scheduler import build_cron_line, build_job_shell_command, build_plan


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Generate a cron entry for running Feed and sending email.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Path to the feed project root",
    )
    parser.add_argument(
        "--day-of-week",
        choices=["sun", "mon", "tue", "wed", "thu", "fri", "sat"],
        default="fri",
        help="Run day for weekly schedules",
    )
    parser.add_argument(
        "--frequency",
        choices=["daily", "weekly"],
        default="weekly",
        help="Schedule frequency",
    )
    parser.add_argument(
        "--hour",
        type=int,
        default=17,
        help="Run hour in 24h time (0-23)",
    )
    parser.add_argument(
        "--minute",
        type=int,
        default=0,
        help="Run minute (0-59)",
    )
    parser.add_argument(
        "--lookback-hours",
        type=int,
        default=None,
        help="LOOKBACK_HOURS override (defaults to 168 weekly, 24 daily)",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path("logs/cron.log"),
        help="Log file path (relative to project root unless absolute)",
    )
    parser.add_argument(
        "--label",
        default="com.user.feed",
        help="Label used in managed cron comments",
    )
    parser.add_argument(
        "--runner",
        default=None,
        help="Custom command to run feed (default: ./feed or 'uv run feed')",
    )
    return parser.parse_args()


def main() -> None:
    """Print a ready-to-copy cron line and setup steps."""
    args = parse_args()
    day_of_week = args.day_of_week if args.frequency == "weekly" else None
    plan = build_plan(
        backend="cron",
        frequency=args.frequency,
        day_of_week=day_of_week,
        time_str=f"{args.hour:02}:{args.minute:02}",
        lookback_hours=args.lookback_hours,
        project_root=args.project_root,
        runner_override=args.runner,
        log_file=args.log_file,
        label=args.label,
        launch_agents_dir=Path.home() / "Library" / "LaunchAgents",
    )
    cron_line = build_cron_line(plan)
    command = f"/bin/zsh -lc {shlex.quote(build_job_shell_command(plan, redirect_to_log=True))}"

    print("=" * 60)
    print("Cron Setup Instructions")
    print("=" * 60)
    print("\n1. Create logs directory:")
    print(f"   mkdir -p {shlex.quote(str(plan.log_file.parent))}")
    print("\n2. Open crontab:")
    print("   crontab -e")
    print("\n3. Add this line:")
    print(f"\n   {cron_line}")
    print("\n4. Verify:")
    print("   crontab -l")
    print(f"   tail -f {shlex.quote(str(plan.log_file))}")
    print("\n5. Test command manually:")
    print(f"   {command}")


if __name__ == "__main__":
    main()
