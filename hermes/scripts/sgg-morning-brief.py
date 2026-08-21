#!/usr/bin/env python3
"""Collect bounded, read-only inputs for the SGG weekday morning brief."""

from __future__ import annotations

import asyncio
import json
import os
import stat
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

HOME = Path.home()
HERMES_HOME = Path(os.environ.get("HERMES_HOME", HOME / ".hermes"))
SGG_ROOT = HOME / "code" / "sgg"
VAULT_ROOT = SGG_ROOT / "vault"
HINDSIGHT_CONFIG = HOME / ".hindsight" / "coding-agent.json"
HINDSIGHT_BANK = "coding-agent::sgg"
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

def git_history(
    repo: Path,
    since: datetime,
    pathspec: str | None = None,
    until: datetime | None = None,
) -> tuple[str, str | None]:
    args = [
        "git",
        "log",
        f"--since={since.isoformat()}",
        "--date=iso-local",
        "--format=COMMIT %h|%ad|%s",
        "--name-only",
        "--max-count=50",
    ]
    if until:
        args.insert(3, f"--until={until.isoformat()}")
    if pathspec:
        args.extend(["--", pathspec])
    return command(args, timeout=30, cwd=repo)


def collect_notes(since: datetime) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    previous_workday_end = since + timedelta(days=1)
    sgg_history, error = git_history(
        SGG_ROOT,
        since,
        "vault",
        until=previous_workday_end,
    )
    if error:
        errors.append(f"SGG vault: {error}")

    return {
        "sgg": {
            "instructionsFile": str(VAULT_ROOT / "AGENTS.md"),
            "canonicalFiles": [
                str(VAULT_ROOT / "INDEX.md"),
                str(VAULT_ROOT / "status.md"),
            ],
            "previousWorkdayHistory": sgg_history[:15000],
            "previousWorkdayEnd": previous_workday_end.isoformat(),
        },
    }, errors


async def _recall_sgg_hindsight(query: str, config: dict[str, Any]) -> list[str]:
    from hindsight_client import Hindsight

    client = Hindsight(
        base_url=str(config["apiUrl"]),
        api_key=str(config["apiToken"]),
        timeout=30.0,
    )
    try:
        response = await client.arecall(
            bank_id=HINDSIGHT_BANK,
            query=query,
            budget="low",
            max_tokens=900,
        )
        return [item.text for item in (response.results or []) if item.text]
    finally:
        await client.aclose()


def collect_hindsight(
    since: datetime,
    github: dict[str, Any],
    recent_vault_history: str,
) -> tuple[dict[str, Any], str | None]:
    try:
        mode = stat.S_IMODE(HINDSIGHT_CONFIG.stat().st_mode)
        if mode != 0o600:
            return {}, f"{HINDSIGHT_CONFIG} must be mode 0600 (is {mode:04o})"
        config = json.loads(HINDSIGHT_CONFIG.read_text(encoding="utf-8"))
        if not config.get("apiUrl") or not config.get("apiToken"):
            return {}, f"{HINDSIGHT_CONFIG} is missing apiUrl or apiToken"

        open_items = [
            f"{item.get('repository')}#{item.get('number')} {str(item.get('title') or '')[:100]}"
            for item in github.get("openPRs", [])[:6]
        ]
        recent_commits = [
            line.removeprefix("COMMIT ").strip()[:120]
            for line in recent_vault_history.splitlines()
            if line.startswith("COMMIT ")
        ][:6]
        query = (
            "Retrieve durable SGG work context that could materially change today's "
            f"brief after {since.date().isoformat()}. Focus on Bryan's explicit decisions, "
            "accepted priorities, unresolved commitments, and meaningful completed or "
            "changed work. Exclude generated workday-note refreshes, routine sync or "
            "workspace-migration logs, completed initiatives without new activity, stale "
            "PR status, and personal projects. Do not invent a priority. Current open "
            f"GitHub items: {'; '.join(open_items) or 'none collected'}. Recent SGG vault "
            f"commit records: {'; '.join(recent_commits) or 'none collected'}."
        )[:1800]
        raw_results = asyncio.run(_recall_sgg_hindsight(query, config))
        results = [
            text
            for text in raw_results
            if "sgg(workday)" not in text.lower()
            and "workday component" not in text.lower()
        ][:10]
        return {
            "bank": HINDSIGHT_BANK,
            "authority": "durable context only; live systems and canonical vault artifacts win",
            "querySince": since.isoformat(),
            "results": results,
        }, None
    except Exception as exc:
        return {}, str(exc)


def main() -> int:
    now = datetime.now(PACIFIC)
    since = previous_workday_start(now)
    calendar_rows, calendar_error = collect_calendar()
    apple_mail, apple_mail_error = collect_apple_mail(since)
    github, github_errors = collect_github(since)
    notes, notes_errors = collect_notes(since)
    hindsight, hindsight_error = collect_hindsight(
        since,
        github,
        notes.get("sgg", {}).get("previousWorkdayHistory", ""),
    )

    errors = {
        key: value
        for key, value in {
            "appleCalendar": calendar_error,
            "appleMail": apple_mail_error,
            "notes": notes_errors or None,
            "github": github_errors or None,
            "hindsight": hindsight_error,
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
        "hindsight": hindsight,
        "notes": notes,
    }
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
