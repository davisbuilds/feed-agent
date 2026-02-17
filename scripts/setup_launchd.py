"""Generate launchd plist for scheduled Feed runs on macOS."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.scheduler import (
    build_plan,
    launchd_domain_and_service,
    write_launchd_plist,
)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Generate and install a launchd agent for Feed email runs.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Path to the feed project root",
    )
    parser.add_argument(
        "--label",
        default="com.user.feed",
        help="launchd label",
    )
    parser.add_argument(
        "--frequency",
        choices=["daily", "weekly"],
        default="weekly",
        help="Schedule frequency",
    )
    parser.add_argument(
        "--day-of-week",
        choices=["sun", "mon", "tue", "wed", "thu", "fri", "sat"],
        default="fri",
        help="Run day for weekly schedules",
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
        "--launch-agents-dir",
        type=Path,
        default=Path.home() / "Library" / "LaunchAgents",
        help="LaunchAgents directory",
    )
    parser.add_argument(
        "--runner",
        default=None,
        help="Custom command to run feed (default: ./feed or 'uv run feed')",
    )
    return parser.parse_args()


def main() -> None:
    """Generate and install a launchd plist file."""
    args = parse_args()
    day_of_week = args.day_of_week if args.frequency == "weekly" else None
    plan = build_plan(
        backend="launchd",
        frequency=args.frequency,
        day_of_week=day_of_week,
        time_str=f"{args.hour:02}:{args.minute:02}",
        lookback_hours=args.lookback_hours,
        project_root=args.project_root,
        runner_override=args.runner,
        log_file=Path("logs/launchd.log"),
        label=args.label,
        launch_agents_dir=args.launch_agents_dir,
    )
    plist_path = write_launchd_plist(plan)
    domain, service = launchd_domain_and_service(plan.label)
    stdout_log = plan.project_root / "logs" / "launchd.stdout.log"
    stderr_log = plan.project_root / "logs" / "launchd.stderr.log"

    print("=" * 60)
    print("macOS Launchd Setup")
    print("=" * 60)
    print(f"\nCreated plist: {plist_path}")
    print(f"stdout log: {stdout_log}")
    print(f"stderr log: {stderr_log}")
    print("\nNext steps:")
    print(f"1. launchctl bootstrap {domain} {plist_path}")
    print(f"2. launchctl kickstart -k {service}")
    print(f"3. launchctl print {service}")
    print(f"4. launchctl bootout {service}")
    print(f"5. tail -f {stdout_log}")


if __name__ == "__main__":
    main()
