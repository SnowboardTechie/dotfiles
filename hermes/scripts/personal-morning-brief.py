#!/usr/bin/env python3
"""Collect bounded, read-only inputs for Bryan's weekday personal morning brief."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from personal_notes import find_note, note_ref, read_markdown  # noqa: E402

HOME = Path.home()
HERMES_HOME = Path(os.environ.get("HERMES_HOME", HOME / ".hermes"))
PACIFIC = ZoneInfo("America/Los_Angeles")
EXCLUDED_CALENDARS = {"Bryan @ Agile6", "Traci"}
PROHIBITED_UNATTENDED_PATTERN = re.compile(
    r"\b(?:alcohol|beer|wine|liquor|whiske?y|cocktail|sobri\w*|abstinen\w*)\b",
    re.IGNORECASE,
)
WEATHER_LOCATION_FILE = Path(
    os.environ.get("PERSONAL_WEATHER_LOCATION_FILE", HOME / ".secrets" / "personal-weather-location")
)


def configured_weather_location() -> str:
    location = os.environ.get("PERSONAL_WEATHER_LOCATION", "").strip()
    if location:
        return location
    try:
        return WEATHER_LOCATION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


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


def contains_prohibited_context(value: Any) -> bool:
    return isinstance(value, str) and bool(PROHIBITED_UNATTENDED_PATTERN.search(value))


def filter_prohibited_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = ("title", "notes", "calendar", "list")
    return [
        row
        for row in rows
        if not any(contains_prohibited_context(row.get(field)) for field in fields)
    ]


def _heading_text(line: str) -> str | None:
    stripped = line.strip()
    if stripped.startswith("#"):
        return stripped.lstrip("#").strip().casefold()
    if stripped.startswith("**") and stripped.endswith("**") and len(stripped) > 4:
        return stripped.strip("*").strip().casefold()
    return None


def extract_active_goals(note: str) -> list[str]:
    """Bullets under the hub's `Active Goals and Projects` heading, as read back
    from Apple Notes (Markdown headings or bold lead-ins) or from a template."""
    in_section = False
    goals: list[str] = []
    for line in note.splitlines():
        heading = _heading_text(line)
        if heading == "active goals and projects":
            in_section = True
            continue
        if in_section and heading is not None:
            break
        if in_section and line.startswith("- "):
            goal = line[2:].strip()
            if goal and not contains_prohibited_context(goal):
                goals.append(goal)
    return goals[:8]


def collect_calendar() -> tuple[list[dict[str, Any]], str | None]:
    binary = HERMES_HOME / "scripts" / "bin" / "sgg-calendar-events"
    data, error = json_command([str(binary), "2"], timeout=30)
    rows = [
        row
        for row in (data or [])
        if str(row.get("calendar", "")).strip() not in EXCLUDED_CALENDARS
    ]
    return filter_prohibited_rows(rows), error


def collect_reminders() -> tuple[list[dict[str, Any]], str | None]:
    data, error = json_command(["remindctl", "today", "--json"], timeout=30)
    rows = [row for row in (data or []) if not row.get("isCompleted", False)]
    return filter_prohibited_rows(rows), error


def collect_weather() -> tuple[dict[str, Any] | None, str | None]:
    location = configured_weather_location()
    if not location:
        return None, f"weather location is not configured in {WEATHER_LOCATION_FILE}"
    try:
        weather_url = f"https://wttr.in/{quote(location)}?format=j1"
        request = Request(weather_url, headers={"User-Agent": "Hermes-personal-morning/1.0"})
        with urlopen(request, timeout=20) as response:
            data = json.load(response)
        area = (data.get("nearest_area") or [{}])[0]
        current = (data.get("current_condition") or [{}])[0]
        today = (data.get("weather") or [{}])[0]
        astronomy = (today.get("astronomy") or [{}])[0]
        return {
            "source": "wttr.in configured location",
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


def _pacific_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=PACIFIC)
    return parsed.astimezone(PACIFIC)


def add_authoritative_local_times(payload: dict[str, Any]) -> None:
    generated = _pacific_timestamp(payload.get("generatedAt"))
    if generated:
        payload["generatedLocalDate"] = generated.date().isoformat()
        payload["generatedLocalWeekday"] = generated.strftime("%A")

    for event in payload.get("calendar") or []:
        start = _pacific_timestamp(event.get("start"))
        end = _pacific_timestamp(event.get("end"))
        if start:
            event["localStart"] = start.isoformat()
            if event.get("allDay"):
                event["localStartDate"] = start.date().isoformat()
        if end:
            event["localEnd"] = end.isoformat()
            if event.get("allDay"):
                event["localEndDateInclusive"] = end.date().isoformat()

    for reminder in payload.get("reminders") or []:
        due = _pacific_timestamp(reminder.get("dueDate"))
        alarm = _pacific_timestamp(reminder.get("alarmDate"))
        if due:
            reminder["localDueDate"] = due.isoformat()
        if alarm:
            reminder["localAlarmDate"] = alarm.isoformat()


def main() -> int:
    now = datetime.now(PACIFIC)
    monday = now.date() - timedelta(days=now.weekday())
    calendar, calendar_error = collect_calendar()
    reminders, reminders_error = collect_reminders()
    weather, weather_error = collect_weather()
    hub_title = f"{monday.isoformat()}-weekly-plan"
    current_week_direction: list[str] = []
    hub, notes_error = find_note(hub_title)
    if hub and not notes_error:
        markdown, notes_error = read_markdown(hub["id"])
        if not notes_error:
            current_week_direction = extract_active_goals(markdown)

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
        "sourceCounts": {
            "calendar": len(calendar),
            "reminders": len(reminders),
            "weeklyDirection": len(current_week_direction),
        },
        "notes": {
            "backend": "apple-notes",
            "currentWeekHub": note_ref(hub_title),
            "currentWeekHubExists": bool(hub),
            "currentWeekDirection": current_week_direction,
        },
    }
    add_authoritative_local_times(payload)
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
