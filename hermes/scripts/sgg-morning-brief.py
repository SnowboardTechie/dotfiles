#!/usr/bin/env python3
"""Collect bounded, read-only inputs for the SGG weekday morning brief."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

HOME = Path.home()
HERMES_HOME = Path(os.environ.get("HERMES_HOME", HOME / ".hermes"))
SGG_ROOT = HOME / "code" / "sgg"
NOTES_ROOT = HOME / "code" / "notes"
PACIFIC = ZoneInfo("America/Los_Angeles")
WORK_CALENDARS = {"Bryan @ Agile6"}
REPOS = (
    "HHS/simpler-grants-protocol",
    "HHS/simpler-grants-gov",
    "common-grants/py-cg-grants-gov",
    "common-grants/ts-cg-grants-gov",
)


def previous_workday_start(now: datetime) -> datetime:
    candidate = now.date() - timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return datetime.combine(candidate, datetime.min.time(), tzinfo=PACIFIC)


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


def json_command(args: list[str], *, timeout: int = 45, cwd: Path | None = None) -> tuple[Any, str | None]:
    output, error = command(args, timeout=timeout, cwd=cwd)
    if error:
        return None, error
    try:
        return json.loads(output), None
    except json.JSONDecodeError as exc:
        return None, f"Invalid JSON: {exc}: {output[:300]}"


def collect_calendar() -> tuple[list[dict[str, Any]], str | None]:
    binary = HERMES_HOME / "scripts" / "bin" / "sgg-calendar-events"
    data, error = json_command([str(binary)], timeout=30)
    rows = [row for row in (data or []) if str(row.get("calendar", "")).strip() in WORK_CALENDARS]
    return rows, error


def collect_apple_mail(since: datetime) -> tuple[list[dict[str, Any]], str | None]:
    script = HERMES_HOME / "scripts" / "sgg-mail-messages.js"
    data, error = json_command(
        ["/usr/bin/osascript", "-l", "JavaScript", str(script), since.isoformat(), "30"],
        timeout=45,
    )
    return (data or []), error


def collect_github(since: datetime) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    prs: dict[str, dict[str, Any]] = {}
    fields = "number,title,url,updatedAt,reviewDecision,statusCheckRollup,isDraft,author"
    for repo in REPOS:
        for search in ("author:@me", "review-requested:@me"):
            data, error = json_command(
                ["gh", "pr", "list", "--repo", repo, "--state", "open", "--search", search, "--limit", "30", "--json", fields],
                timeout=45,
                cwd=SGG_ROOT,
            )
            if error:
                errors.append(f"{repo} ({search}): {error}")
                continue
            for item in data or []:
                item["repository"] = repo
                prs[item["url"]] = item

    notifications, error = json_command(
        [
            "gh",
            "api",
            "--method",
            "GET",
            "notifications",
            "-f",
            "participating=true",
            "-f",
            f"since={since.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')}",
            "-f",
            "per_page=50",
        ],
        timeout=60,
        cwd=SGG_ROOT,
    )
    if error:
        errors.append(f"notifications: {error}")
        notifications = []
    relevant_notifications = []
    for item in notifications or []:
        repo = (item.get("repository") or {}).get("full_name")
        if repo in REPOS:
            relevant_notifications.append(
                {
                    "repository": repo,
                    "reason": item.get("reason"),
                    "unread": item.get("unread"),
                    "updatedAt": item.get("updated_at"),
                    "subject": item.get("subject"),
                }
            )
    return {"openPRs": list(prs.values()), "notifications": relevant_notifications[:30]}, errors

def git_history(repo: Path, since: datetime, pathspec: str | None = None) -> tuple[str, str | None]:
    args = [
        "git",
        "log",
        f"--since={since.isoformat()}",
        "--date=iso-local",
        "--format=COMMIT %h|%ad|%s",
        "--name-only",
        "--max-count=50",
    ]
    if pathspec:
        args.extend(["--", pathspec])
    return command(args, timeout=30, cwd=repo)


def collect_notes(since: datetime, now: datetime) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    sgg_history, error = git_history(NOTES_ROOT, since, "sgg")
    if error:
        errors.append(f"SGG vault: {error}")

    return {
        "sgg": {
            "instructionsFile": str(NOTES_ROOT / "sgg" / "AGENTS.md"),
            "canonicalFiles": [
                str(NOTES_ROOT / "sgg" / "INDEX.md"),
                str(NOTES_ROOT / "sgg" / "status.md"),
            ],
            "previousWorkdayHistory": sgg_history[:15000],
            "workdayNotes": {
                "todayPath": str(NOTES_ROOT / "sgg" / "workdays" / f"{now.date().isoformat()}.md"),
                "previousWorkdayPath": str(
                    NOTES_ROOT / "sgg" / "workdays" / f"{since.date().isoformat()}.md"
                ),
                "pilotReviewDate": "2026-07-30",
            },
        },
    }, errors


def main() -> int:
    now = datetime.now(PACIFIC)
    since = previous_workday_start(now)
    calendar_rows, calendar_error = collect_calendar()
    apple_mail, apple_mail_error = collect_apple_mail(since)
    github, github_errors = collect_github(since)
    notes, notes_errors = collect_notes(since, now)

    errors = {
        key: value
        for key, value in {
            "appleCalendar": calendar_error,
            "appleMail": apple_mail_error,
            "notes": notes_errors or None,
            "github": github_errors or None,
        }.items()
        if value
    }
    payload = {
        "generatedAt": now.isoformat(),
        "timezone": "America/Los_Angeles",
        "previousWorkdayStart": since.isoformat(),
        "sourceErrors": errors,
        "calendar": calendar_rows,
        "email": apple_mail,
        "emailSourceCounts": {"appleMail": len(apple_mail)},
        "github": github,
        "notes": notes,
    }
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
