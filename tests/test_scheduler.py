"""Tests for scheduler planning and rendering helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.scheduler import (
    build_cron_line,
    build_launchd_plist,
    build_plan,
    get_cron_managed_block,
    parse_time_24h,
    render_cron_managed_block,
)


def test_parse_time_24h_valid() -> None:
    """HH:MM values should parse into hour/minute integers."""
    assert parse_time_24h("17:05") == (17, 5)
    assert parse_time_24h("00:00") == (0, 0)


@pytest.mark.parametrize("value", ["", "1705", "24:00", "10:60", "aa:bb"])
def test_parse_time_24h_invalid(value: str) -> None:
    """Invalid time strings should raise ValueError."""
    with pytest.raises(ValueError):
        parse_time_24h(value)


def test_build_plan_weekly_defaults_to_fri_and_168(tmp_path: Path) -> None:
    """Weekly schedules default to Friday with a 168-hour lookback."""
    (tmp_path / "feed").write_text("#!/usr/bin/env bash\n")

    plan = build_plan(
        backend="cron",
        frequency="weekly",
        day_of_week=None,
        time_str="17:00",
        lookback_hours=None,
        project_root=tmp_path,
        runner_override=None,
        log_file=Path("logs/cron.log"),
        label="com.user.feed",
        launch_agents_dir=Path.home() / "Library" / "LaunchAgents",
    )

    assert plan.day_of_week == "fri"
    assert plan.lookback_hours == 168
    assert plan.runner == "./feed"


def test_build_plan_daily_uses_24_hour_default(tmp_path: Path) -> None:
    """Daily schedule defaults to 24-hour lookback."""
    plan = build_plan(
        backend="cron",
        frequency="daily",
        day_of_week=None,
        time_str="08:30",
        lookback_hours=None,
        project_root=tmp_path,
        runner_override="uv run feed",
        log_file=Path("logs/cron.log"),
        label="com.user.feed",
        launch_agents_dir=Path.home() / "Library" / "LaunchAgents",
    )

    assert plan.day_of_week is None
    assert plan.lookback_hours == 24


def test_build_cron_line_weekly_contains_expected_schedule(tmp_path: Path) -> None:
    """Weekly cron output should include weekday and send command."""
    plan = build_plan(
        backend="cron",
        frequency="weekly",
        day_of_week="fri",
        time_str="17:00",
        lookback_hours=168,
        project_root=tmp_path,
        runner_override="uv run feed",
        log_file=Path("logs/cron.log"),
        label="com.user.feed",
        launch_agents_dir=Path.home() / "Library" / "LaunchAgents",
    )

    cron_line = build_cron_line(plan)
    assert cron_line.startswith("0 17 * * 5 ")
    assert "LOOKBACK_HOURS=168" in cron_line
    assert "run --send" in cron_line


def test_build_launchd_plist_weekly_has_weekday(tmp_path: Path) -> None:
    """Weekly launchd plist should include StartCalendarInterval.Weekday."""
    plan = build_plan(
        backend="launchd",
        frequency="weekly",
        day_of_week="fri",
        time_str="17:00",
        lookback_hours=168,
        project_root=tmp_path,
        runner_override="uv run feed",
        log_file=Path("logs/launchd.log"),
        label="com.user.feed",
        launch_agents_dir=Path.home() / "Library" / "LaunchAgents",
    )

    payload = build_launchd_plist(plan)
    interval = payload["StartCalendarInterval"]
    assert isinstance(interval, dict)
    assert interval["Hour"] == 17
    assert interval["Minute"] == 0
    assert interval["Weekday"] == 5
    env = payload["EnvironmentVariables"]
    assert isinstance(env, dict)
    assert "PATH" in env
    path_entries = str(env["PATH"]).split(":")
    assert str(Path.home() / ".local" / "bin") in path_entries


def test_render_cron_managed_block_contains_label_and_entry(tmp_path: Path) -> None:
    """Managed cron block should be bracketed with unique label markers."""
    plan = build_plan(
        backend="cron",
        frequency="weekly",
        day_of_week="fri",
        time_str="17:00",
        lookback_hours=168,
        project_root=tmp_path,
        runner_override="uv run feed",
        log_file=Path("logs/cron.log"),
        label="com.user.feed",
        launch_agents_dir=Path.home() / "Library" / "LaunchAgents",
    )

    block = render_cron_managed_block(plan)
    assert "# >>> feed schedule (com.user.feed) >>>" in block
    assert "# <<< feed schedule (com.user.feed) <<<" in block
    assert "0 17 * * 5" in block


def test_get_cron_managed_block_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """Managed block lookup should return block text when present."""
    content = (
        "# header\n"
        "# >>> feed schedule (com.user.feed) >>>\n"
        "0 17 * * 5 /bin/zsh -lc 'echo test'\n"
        "# <<< feed schedule (com.user.feed) <<<\n"
    )
    monkeypatch.setattr("src.scheduler._read_crontab", lambda: content)

    block = get_cron_managed_block("com.user.feed")

    assert block is not None
    assert "0 17 * * 5" in block


def test_get_cron_managed_block_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Managed block lookup should return None when absent."""
    monkeypatch.setattr("src.scheduler._read_crontab", lambda: "# no managed block\n")
    assert get_cron_managed_block("com.user.feed") is None
