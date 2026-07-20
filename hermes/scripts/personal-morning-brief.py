#!/usr/bin/env python3
"""Collect bounded, read-only inputs for Bryan's weekday personal morning brief."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

HOME = Path.home()
HERMES_HOME = Path(os.environ.get("HERMES_HOME", HOME / ".hermes"))
SECOND_BRAIN = HOME / "second-brain"
PACIFIC = ZoneInfo("America/Los_Angeles")
WORK_CALENDARS = {"Bryan @ Agile6"}


def command(args: list[str], *, timeout: int = 45, cwd: Path | None = None) -> tuple[str, str | None]:
    try:
        result = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "", str(exc)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or f"exit {result.returncode}").strip()
        return result.stdout.strip(), detail[:1000]
    return result.stdout.strip(), None


def json_command(args: list[str], *, timeout: int = 45) -> tuple[Any, str | None]:
    output, error = command(args, timeout=timeout)
    if error:
        return None, error
    try:
        return json.loads(output), None
    except json.JSONDecodeError as exc:
        return None, f"Invalid JSON: {exc}: {output[:300]}"


def collect_calendar() -> tuple[list[dict[str, Any]], str | None]:
    binary = HERMES_HOME / "scripts" / "bin" / "sgg-calendar-events"
    data, error = json_command([str(binary), "2"], timeout=30)
    rows = [row for row in (data or []) if str(row.get("calendar", "")).strip() not in WORK_CALENDARS]
    return rows, error


def collect_reminders() -> tuple[list[dict[str, Any]], str | None]:
    data, error = json_command(["remindctl", "today", "--json"], timeout=30)
    rows = [row for row in (data or []) if not row.get("isCompleted", False)]
    return rows, error


def collect_weather() -> tuple[dict[str, Any] | None, str | None]:
    try:
        request = Request("https://wttr.in/?format=j1", headers={"User-Agent": "Hermes-personal-morning/1.0"})
        with urlopen(request, timeout=20) as response:
            data = json.load(response)
        area = (data.get("nearest_area") or [{}])[0]
        current = (data.get("current_condition") or [{}])[0]
        today = (data.get("weather") or [{}])[0]
        astronomy = (today.get("astronomy") or [{}])[0]
        return {
            "source": "wttr.in IP geolocation",
            "area": ((area.get("areaName") or [{}])[0].get("value")),
            "region": ((area.get("region") or [{}])[0].get("value")),
            "current": {
                "tempF": current.get("temp_F"),
                "feelsLikeF": current.get("FeelsLikeF"),
                "description": ((current.get("weatherDesc") or [{}])[0].get("value")),
            },
            "today": {
                "minF": today.get("mintempF"),
                "maxF": today.get("maxtempF"),
                "sunrise": astronomy.get("sunrise"),
                "sunset": astronomy.get("sunset"),
                "maxChanceOfRain": max((int(hour.get("chanceofrain") or 0) for hour in today.get("hourly") or []), default=0),
                "maxChanceOfSnow": max((int(hour.get("chanceofsnow") or 0) for hour in today.get("hourly") or []), default=0),
            },
        }, None
    except Exception as exc:  # noqa: BLE001 - source failures are reported, not fatal
        return None, str(exc)[:1000]


def recent_paths(now: datetime) -> tuple[list[str], str | None]:
    output, error = command(
        [
            "git",
            "log",
            f"--since={(now - timedelta(days=21)).isoformat()}",
            "--format=",
            "--name-only",
            "--max-count=80",
        ],
        timeout=30,
        cwd=SECOND_BRAIN,
    )
    paths = sorted({line.strip() for line in output.splitlines() if line.strip()})
    return paths[:100], error


def main() -> int:
    now = datetime.now(PACIFIC)
    monday = now.date() - timedelta(days=now.weekday())
    calendar, calendar_error = collect_calendar()
    reminders, reminders_error = collect_reminders()
    weather, weather_error = collect_weather()
    paths, notes_error = recent_paths(now)

    errors = {
        key: value
        for key, value in {
            "appleCalendar": calendar_error,
            "appleReminders": reminders_error,
            "weather": weather_error,
            "secondBrain": notes_error,
        }.items()
        if value
    }
    payload = {
        "generatedAt": now.isoformat(),
        "timezone": "America/Los_Angeles",
        "sourceErrors": errors,
        "calendar": calendar,
        "reminders": reminders,
        "weather": weather,
        "notes": {
            "root": str(SECOND_BRAIN),
            "instructionsFile": str(SECOND_BRAIN / "AGENTS.md"),
            "currentWeekHubPath": str(SECOND_BRAIN / "Journal" / f"{monday.isoformat()}-weekly-plan.md"),
            "recentSecondBrainPaths": paths,
        },
    }
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
