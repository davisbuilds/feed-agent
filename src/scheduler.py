"""Scheduler helpers for cron and launchd Feed jobs."""

from __future__ import annotations

import os
import plistlib
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Backend = Literal["cron", "launchd"]
Frequency = Literal["daily", "weekly"]

WEEKDAY_NAMES = ("sun", "mon", "tue", "wed", "thu", "fri", "sat")

CRON_WEEKDAY_BY_NAME = {
    "sun": "0",
    "mon": "1",
    "tue": "2",
    "wed": "3",
    "thu": "4",
    "fri": "5",
    "sat": "6",
}

LAUNCHD_WEEKDAY_BY_NAME = {
    "sun": 0,
    "mon": 1,
    "tue": 2,
    "wed": 3,
    "thu": 4,
    "fri": 5,
    "sat": 6,
}


@dataclass(frozen=True)
class SchedulePlan:
    """Resolved scheduler plan."""

    backend: Backend
    frequency: Frequency
    day_of_week: str | None
    hour: int
    minute: int
    lookback_hours: int
    project_root: Path
    runner: str
    log_file: Path
    label: str
    launch_agents_dir: Path


def parse_time_24h(value: str) -> tuple[int, int]:
    """Parse HH:MM (24h) and return hour, minute."""
    parts = value.strip().split(":")
    if len(parts) != 2:
        raise ValueError("Time must be in HH:MM format")
    hour_str, minute_str = parts
    if not hour_str.isdigit() or not minute_str.isdigit():
        raise ValueError("Time must be numeric HH:MM")
    hour = int(hour_str)
    minute = int(minute_str)
    if not 0 <= hour <= 23:
        raise ValueError("Hour must be between 0 and 23")
    if not 0 <= minute <= 59:
        raise ValueError("Minute must be between 0 and 59")
    return hour, minute


def normalize_day_of_week(value: str) -> str:
    """Normalize day names to short lowercase forms."""
    normalized = value.strip().lower()[:3]
    if normalized not in WEEKDAY_NAMES:
        raise ValueError(f"Invalid day '{value}'. Use: {', '.join(WEEKDAY_NAMES)}")
    return normalized


def resolve_backend(value: str) -> Backend:
    """Resolve backend name, allowing `auto`."""
    normalized = value.strip().lower()
    if normalized in {"cron", "launchd"}:
        return normalized  # type: ignore[return-value]
    if normalized != "auto":
        raise ValueError("Backend must be one of: auto, cron, launchd")
    return "launchd" if sys.platform == "darwin" else "cron"


def default_day_of_week(frequency: Frequency) -> str | None:
    """Default day by frequency."""
    if frequency == "daily":
        return None
    return "fri"


def default_lookback_hours(frequency: Frequency) -> int:
    """Lookback defaults tuned for schedule frequency."""
    return 24 if frequency == "daily" else 168


def resolve_runner(project_root: Path, runner_override: str | None) -> str:
    """Pick the command that invokes the feed CLI."""
    if runner_override:
        return _shell_quote_command(runner_override)
    wrapper = project_root / "feed"
    if wrapper.exists():
        return "./feed"
    return "uv run feed"


def resolve_log_path(project_root: Path, log_file: Path) -> Path:
    """Resolve log path relative to project root when needed."""
    return log_file if log_file.is_absolute() else project_root / log_file


def build_plan(
    *,
    backend: str,
    frequency: str,
    day_of_week: str | None,
    time_str: str,
    lookback_hours: int | None,
    project_root: Path,
    runner_override: str | None,
    log_file: Path,
    label: str,
    launch_agents_dir: Path,
) -> SchedulePlan:
    """Build a validated schedule plan from CLI-like inputs."""
    resolved_backend = resolve_backend(backend)
    normalized_frequency = frequency.strip().lower()
    if normalized_frequency not in {"daily", "weekly"}:
        raise ValueError("Frequency must be one of: daily, weekly")
    freq: Frequency = normalized_frequency  # type: ignore[assignment]

    hour, minute = parse_time_24h(time_str)
    resolved_day = None
    if freq == "weekly":
        if day_of_week is None:
            resolved_day = default_day_of_week(freq)
        else:
            resolved_day = normalize_day_of_week(day_of_week)
    elif day_of_week is not None:
        raise ValueError("--day-of-week is only valid with --frequency weekly")

    if lookback_hours is not None and lookback_hours < 1:
        raise ValueError("lookback-hours must be >= 1")

    normalized_label = label.strip()
    if not normalized_label:
        raise ValueError("label cannot be empty")

    resolved_root = project_root.resolve()
    resolved_runner = resolve_runner(resolved_root, runner_override)
    resolved_log = resolve_log_path(resolved_root, log_file)
    resolved_lookback = lookback_hours or default_lookback_hours(freq)

    return SchedulePlan(
        backend=resolved_backend,
        frequency=freq,
        day_of_week=resolved_day,
        hour=hour,
        minute=minute,
        lookback_hours=resolved_lookback,
        project_root=resolved_root,
        runner=resolved_runner,
        log_file=resolved_log,
        label=normalized_label,
        launch_agents_dir=launch_agents_dir.expanduser(),
    )


def build_job_shell_command(plan: SchedulePlan, *, redirect_to_log: bool) -> str:
    """Build shell command that runs feed and sends email."""
    command = (
        f"cd {shlex.quote(str(plan.project_root))} && "
        f"LOOKBACK_HOURS={plan.lookback_hours} {plan.runner} run --send"
    )
    if redirect_to_log:
        command += f" >> {shlex.quote(str(plan.log_file))} 2>&1"
    return command


def build_cron_schedule(plan: SchedulePlan) -> str:
    """Build cron schedule expression."""
    if plan.frequency == "daily":
        return f"{plan.minute} {plan.hour} * * *"
    if plan.day_of_week is None:
        raise ValueError("Weekly schedule requires day_of_week")
    cron_day = CRON_WEEKDAY_BY_NAME[plan.day_of_week]
    return f"{plan.minute} {plan.hour} * * {cron_day}"


def build_cron_line(plan: SchedulePlan) -> str:
    """Build complete cron entry."""
    shell_command = build_job_shell_command(plan, redirect_to_log=True)
    schedule = build_cron_schedule(plan)
    return f"{schedule} /bin/zsh -lc {shlex.quote(shell_command)}"


def build_launchd_plist(plan: SchedulePlan) -> dict[str, object]:
    """Build launchd plist payload."""
    start_calendar: dict[str, int] = {"Hour": plan.hour, "Minute": plan.minute}
    if plan.frequency == "weekly":
        if plan.day_of_week is None:
            raise ValueError("Weekly launchd schedule requires day_of_week")
        start_calendar["Weekday"] = LAUNCHD_WEEKDAY_BY_NAME[plan.day_of_week]

    command = build_job_shell_command(plan, redirect_to_log=False)
    return {
        "Label": plan.label,
        "ProgramArguments": ["/bin/zsh", "-lc", command],
        "WorkingDirectory": str(plan.project_root),
        "EnvironmentVariables": {
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
        },
        "StartCalendarInterval": start_calendar,
        "StandardOutPath": str(plan.project_root / "logs" / "launchd.stdout.log"),
        "StandardErrorPath": str(plan.project_root / "logs" / "launchd.stderr.log"),
        "RunAtLoad": False,
    }


def launchd_plist_path(plan: SchedulePlan) -> Path:
    """Return launchd plist path for plan."""
    return plan.launch_agents_dir / f"{plan.label}.plist"


def cron_marker_start(label: str) -> str:
    """Managed cron block start marker."""
    return f"# >>> feed schedule ({label}) >>>"


def cron_marker_end(label: str) -> str:
    """Managed cron block end marker."""
    return f"# <<< feed schedule ({label}) <<<"


def render_cron_managed_block(plan: SchedulePlan) -> str:
    """Render managed cron block text."""
    start = cron_marker_start(plan.label)
    end = cron_marker_end(plan.label)
    line = build_cron_line(plan)
    return f"{start}\n{line}\n{end}"


def get_cron_managed_block(label: str) -> str | None:
    """Return managed cron block for label, if present."""
    existing = _read_crontab()
    lines = existing.splitlines() if existing else []
    start = cron_marker_start(label)
    end = cron_marker_end(label)
    if start not in lines or end not in lines:
        return None

    start_idx = lines.index(start)
    end_idx = lines.index(end)
    if end_idx < start_idx:
        raise RuntimeError(
            "Malformed cron managed block; end marker appears before start marker."
        )
    return "\n".join(lines[start_idx : end_idx + 1])


def write_launchd_plist(plan: SchedulePlan) -> Path:
    """Write launchd plist and return its path."""
    plist_path = launchd_plist_path(plan)
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    (plan.project_root / "logs").mkdir(parents=True, exist_ok=True)
    with plist_path.open("wb") as file_handle:
        plistlib.dump(build_launchd_plist(plan), file_handle, sort_keys=False)
    return plist_path


def _read_crontab() -> str:
    """Read current crontab content."""
    result = subprocess.run(
        ["crontab", "-l"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return result.stdout.rstrip("\n")

    message = (result.stderr or result.stdout or "").strip().lower()
    if "no crontab" in message:
        return ""
    raise RuntimeError(f"Unable to read crontab: {result.stderr.strip() or result.stdout.strip()}")


def _write_crontab(content: str) -> None:
    """Write full crontab content."""
    subprocess.run(
        ["crontab", "-"],
        input=content.rstrip("\n") + "\n",
        text=True,
        check=True,
    )


def install_cron(plan: SchedulePlan, *, replace_existing: bool = True) -> None:
    """Install schedule as a managed block in crontab."""
    block = render_cron_managed_block(plan)
    existing = _read_crontab()
    start = cron_marker_start(plan.label)
    end = cron_marker_end(plan.label)

    lines = existing.splitlines() if existing else []
    if start in lines and end in lines:
        if not replace_existing:
            raise RuntimeError(
                f"Managed cron block for label '{plan.label}' already exists; "
                "use --replace to update it."
            )
        start_idx = lines.index(start)
        end_idx = lines.index(end)
        if end_idx < start_idx:
            raise RuntimeError(
                "Malformed cron managed block; end marker appears before start marker."
            )
        new_lines = lines[:start_idx] + block.splitlines() + lines[end_idx + 1 :]
    else:
        new_lines = lines + ([""] if lines else []) + block.splitlines()

    _write_crontab("\n".join(new_lines))


def launchd_domain_and_service(label: str) -> tuple[str, str]:
    """Return launchd domain and fully-qualified service name."""
    domain = f"gui/{os.getuid()}"
    return domain, f"{domain}/{label}"


def bootstrap_launchd(plan: SchedulePlan, plist_path: Path) -> tuple[str, str]:
    """Load or reload launchd service from a plist."""
    domain, service = launchd_domain_and_service(plan.label)
    subprocess.run(
        ["launchctl", "bootout", service],
        capture_output=True,
        text=True,
        check=False,
    )
    subprocess.run(
        ["launchctl", "bootstrap", domain, str(plist_path)],
        check=True,
    )
    return domain, service


def activate_launchd(plan: SchedulePlan, plist_path: Path) -> tuple[str, str]:
    """Load launchd service and trigger an immediate run."""
    domain, service = bootstrap_launchd(plan, plist_path)
    subprocess.run(
        ["launchctl", "kickstart", "-k", service],
        check=True,
    )
    return domain, service


def _shell_quote_command(command: str) -> str:
    """Normalize free-form shell command to a safely quoted command string."""
    return " ".join(shlex.quote(part) for part in shlex.split(command))
