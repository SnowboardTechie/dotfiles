#!/usr/bin/env python3
"""Collect bounded, read-only context for Bryan's personal alignment pilot."""
from __future__ import annotations

import argparse
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
SGG_NOTES = HOME / "code" / "notes" / "sgg"
PACIFIC = ZoneInfo("America/Los_Angeles")
PILOT_REVIEW_DATE = "2026-08-09"


def command(args: list[str], timeout: int = 45, cwd: Path | None = None) -> tuple[str, str | None]:
    try:
        result = subprocess.run(args, cwd=str(cwd) if cwd else None, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "", str(exc)
    if result.returncode:
        return result.stdout.strip(), (result.stderr or result.stdout or f"exit {result.returncode}").strip()[:1000]
    return result.stdout.strip(), None


def json_command(args: list[str], timeout: int = 45) -> tuple[Any, str | None]:
    output, error = command(args, timeout=timeout)
    if error:
        return None, error
    try:
        return json.loads(output), None
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}: {output[:300]}"


def monday(day):
    return day - timedelta(days=day.weekday())


def mode_for(now: datetime) -> str:
    return "saturday" if now.weekday() == 5 else "sunday" if now.weekday() == 6 else "weekday"


def collect_calendar(days: int) -> tuple[list[dict[str, Any]], str | None]:
    binary = HERMES_HOME / "scripts" / "bin" / "sgg-calendar-events"
    data, error = json_command([str(binary), str(days)], timeout=30)
    return (data or []), error


def collect_reminders(mode: str) -> tuple[list[dict[str, Any]], str | None]:
    period = "today" if mode == "weekday" else "week"
    data, error = json_command(["remindctl", period, "--json"], timeout=30)
    return [row for row in (data or []) if not row.get("isCompleted", False)], error


def collect_mail(now: datetime, mode: str) -> tuple[list[dict[str, Any]], str | None]:
    if mode != "sunday":
        return [], None
    script = HERMES_HOME / "scripts" / "personal-mail-messages.js"
    since = (now - timedelta(days=7)).isoformat()
    data, error = json_command(["/usr/bin/osascript", "-l", "JavaScript", str(script), since, "40"], timeout=60)
    return (data or []), error


def collect_weather() -> tuple[dict[str, Any] | None, str | None]:
    try:
        request = Request("https://wttr.in/?format=j1", headers={"User-Agent": "Hermes-personal-alignment/1.0"})
        with urlopen(request, timeout=20) as response:
            data = json.load(response)
        area = (data.get("nearest_area") or [{}])[0]
        current = (data.get("current_condition") or [{}])[0]
        forecasts = []
        for day in (data.get("weather") or [])[:3]:
            astronomy = (day.get("astronomy") or [{}])[0]
            forecasts.append({
                "date": day.get("date"),
                "minF": day.get("mintempF"),
                "maxF": day.get("maxtempF"),
                "sunrise": astronomy.get("sunrise"),
                "sunset": astronomy.get("sunset"),
                "hourly": [
                    {
                        "time": hour.get("time"),
                        "tempF": hour.get("tempF"),
                        "chanceOfRain": hour.get("chanceofrain"),
                        "chanceOfSnow": hour.get("chanceofsnow"),
                        "description": ((hour.get("weatherDesc") or [{}])[0].get("value")),
                    }
                    for hour in (day.get("hourly") or [])[::2]
                ],
            })
        compact = {
            "source": "wttr.in IP geolocation",
            "area": ((area.get("areaName") or [{}])[0].get("value")),
            "region": ((area.get("region") or [{}])[0].get("value")),
            "current": {
                "tempF": current.get("temp_F"),
                "feelsLikeF": current.get("FeelsLikeF"),
                "humidity": current.get("humidity"),
                "description": ((current.get("weatherDesc") or [{}])[0].get("value")),
            },
            "forecast": forecasts,
        }
        return compact, None
    except Exception as exc:  # noqa: BLE001 - source failures are reported, not fatal
        return None, str(exc)[:1000]


def git_history(repo: Path, since: datetime, max_count: int = 60) -> tuple[str, str | None]:
    return command([
        "git", "log", f"--since={since.isoformat()}", "--date=iso-local",
        "--format=COMMIT %h|%ad|%s", "--name-only", f"--max-count={max_count}",
    ], timeout=30, cwd=repo)


def changed_paths(history: str) -> list[str]:
    return sorted({line.strip() for line in history.splitlines() if line.strip() and not line.startswith("COMMIT ")})


def note_context(now: datetime, mode: str) -> dict[str, Any]:
    today = now.date()
    current_start = monday(today)
    next_start = current_start + timedelta(days=7)
    if mode == "sunday":
        next_start = today + timedelta(days=1)
    daily_path = SECOND_BRAIN / "Journal" / f"{today.isoformat()}-daily-check-in.md"
    current_hub = SECOND_BRAIN / "Journal" / f"{current_start.isoformat()}-weekly-plan.md"
    next_hub = SECOND_BRAIN / "Journal" / f"{next_start.isoformat()}-weekly-plan.md"
    week_days = [current_start + timedelta(days=index) for index in range(7)]
    daily_spokes = [
        str(SECOND_BRAIN / "Journal" / f"{day.isoformat()}-daily-check-in.md")
        for day in week_days
        if (SECOND_BRAIN / "Journal" / f"{day.isoformat()}-daily-check-in.md").exists()
    ]
    completion_path = next_hub if mode == "sunday" else daily_path
    return {
        "dailyPath": str(daily_path),
        "currentWeekStart": current_start.isoformat(),
        "currentWeekHubPath": str(current_hub),
        "currentWeekHubExists": current_hub.exists(),
        "nextWeekStart": next_start.isoformat(),
        "nextWeekHubPath": str(next_hub),
        "nextWeekHubExists": next_hub.exists(),
        "currentWeekDailySpokes": daily_spokes,
        "completionPath": str(completion_path),
        "alreadyCompleted": completion_path.exists(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("weekday", "saturday", "sunday"))
    parser.add_argument("--now", help="ISO timestamp for deterministic testing")
    parser.add_argument("--no-network", action="store_true")
    args = parser.parse_args()
    now = datetime.fromisoformat(args.now).astimezone(PACIFIC) if args.now else datetime.now(PACIFIC)
    mode = args.mode or mode_for(now)
    days = 8 if mode == "sunday" else 2

    calendar, calendar_error = collect_calendar(days)
    reminders, reminders_error = collect_reminders(mode)
    mail, mail_error = collect_mail(now, mode)
    weather, weather_error = (None, "disabled for test") if args.no_network else collect_weather()
    second_history, second_error = git_history(SECOND_BRAIN, now - timedelta(days=21))
    sgg_history, sgg_error = git_history(SGG_NOTES.parent, now - timedelta(days=7))

    errors = {key: value for key, value in {
        "appleCalendar": calendar_error,
        "appleReminders": reminders_error,
        "appleMail": mail_error,
        "weather": weather_error,
        "secondBrain": second_error,
        "sggVault": sgg_error,
    }.items() if value}
    payload = {
        "generatedAt": now.isoformat(),
        "timezone": "America/Los_Angeles",
        "mode": mode,
        "pilot": {"reviewDate": PILOT_REVIEW_DATE, "isReviewDate": now.date().isoformat() >= PILOT_REVIEW_DATE},
        "sourceErrors": errors,
        "checkIn": note_context(now, mode),
        "calendar": calendar,
        "reminders": reminders,
        "email": mail,
        "weather": weather,
        "notes": {
            "secondBrainRoot": str(SECOND_BRAIN),
            "secondBrainInstructions": str(SECOND_BRAIN / "AGENTS.md"),
            "alignmentDesign": str(SECOND_BRAIN / "Explorations" / "2026-07-19-hermes-personal-alignment-routines.md"),
            "recentSecondBrainPaths": changed_paths(second_history)[:100],
            "sggRoot": str(SGG_NOTES),
            "sggInstructions": str(SGG_NOTES / "AGENTS.md"),
            "sggCanonical": [str(SGG_NOTES / "INDEX.md"), str(SGG_NOTES / "status.md")],
            "recentSggPaths": [path for path in changed_paths(sgg_history) if path.startswith("sgg/")][:60],
        },
    }
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
