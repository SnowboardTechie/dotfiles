#!/usr/bin/env python3
"""Safely prepare and synchronize one SGG workday note.

This helper never edits note content. It validates repository state before an
agent write and stages only the exact dated workday note afterward.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

NOTES_ROOT = Path.home() / "code" / "notes"
WORKDAYS_ROOT = NOTES_ROOT / "sgg" / "workdays"
BEGIN_MARKER = "<!-- BEGIN GENERATED MORNING BRIEF -->"
END_MARKER = "<!-- END GENERATED MORNING BRIEF -->"
REQUIRED_MANUAL_HEADINGS = ("## Day log", "## End-of-day handoff", "## Canonical context")


class SyncError(RuntimeError):
    pass


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=NOTES_ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or f"git exited {result.returncode}").strip()
        raise SyncError(detail[:1200])
    return result


def target_for(day: str) -> tuple[Path, str]:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        raise SyncError("date must use YYYY-MM-DD")
    try:
        date.fromisoformat(day)
    except ValueError as exc:
        raise SyncError(str(exc)) from exc
    relative = f"sgg/workdays/{day}.md"
    return NOTES_ROOT / relative, relative


def changed_tracked_paths(*, staged: bool) -> set[str]:
    args = ["diff", "--name-only"]
    if staged:
        args.append("--cached")
    result = git(*args)
    return {line for line in result.stdout.splitlines() if line}


def require_branch() -> None:
    branch = git("branch", "--show-current").stdout.strip()
    if branch != "main":
        raise SyncError(f"notes repository is on {branch or 'detached HEAD'}, not main")


def require_no_staged_changes() -> None:
    staged = changed_tracked_paths(staged=True)
    if staged:
        raise SyncError(f"pre-existing staged changes: {', '.join(sorted(staged))}")


def require_no_unrelated_tracked_changes(relative: str) -> None:
    changed = changed_tracked_paths(staged=False)
    unrelated = changed - {relative}
    if unrelated:
        raise SyncError(f"unrelated tracked changes: {', '.join(sorted(unrelated))}")


def divergence() -> tuple[int, int]:
    raw = git("rev-list", "--left-right", "--count", "HEAD...origin/main").stdout.strip()
    ahead_text, behind_text = raw.split()
    return int(ahead_text), int(behind_text)


def fetch() -> None:
    git("fetch", "origin", "main")


def prepare(day: str) -> dict[str, object]:
    target, relative = target_for(day)
    require_branch()
    require_no_staged_changes()
    require_no_unrelated_tracked_changes(relative)
    fetch()
    ahead, behind = divergence()
    if ahead:
        raise SyncError(f"local main is {ahead} commit(s) ahead of origin/main")
    if behind:
        if target.exists() and relative in changed_tracked_paths(staged=False):
            raise SyncError("today's note has local edits while origin/main is ahead")
        git("merge", "--ff-only", "origin/main")
    ahead, behind = divergence()
    if ahead or behind:
        raise SyncError(f"notes repository is not synchronized (ahead={ahead}, behind={behind})")
    return {
        "status": "ready",
        "target": str(target),
        "relativePath": relative,
        "existing": target.exists(),
        "untrackedFilesPreserved": True,
    }


def validate_note(target: Path, day: str) -> None:
    if not target.is_file():
        raise SyncError(f"workday note was not created: {target}")
    text = target.read_text(encoding="utf-8")
    if text.count(BEGIN_MARKER) != 1 or text.count(END_MARKER) != 1:
        raise SyncError("workday note must contain exactly one generated-block marker pair")
    if text.index(BEGIN_MARKER) >= text.index(END_MARKER):
        raise SyncError("generated-block markers are out of order")
    if f"date: {day}" not in text or f"# Workday — {day}" not in text:
        raise SyncError("workday note date metadata or title is incorrect")
    missing = [heading for heading in REQUIRED_MANUAL_HEADINGS if heading not in text]
    if missing:
        raise SyncError(f"workday note is missing manual sections: {', '.join(missing)}")


def commit(day: str) -> dict[str, object]:
    target, relative = target_for(day)
    validate_note(target, day)
    require_branch()
    require_no_staged_changes()
    require_no_unrelated_tracked_changes(relative)
    fetch()
    ahead, behind = divergence()
    if ahead or behind:
        raise SyncError(f"origin/main changed during the run (ahead={ahead}, behind={behind})")

    git("add", "--", relative)
    staged = changed_tracked_paths(staged=True)
    if not staged:
        return {"status": "unchanged", "target": str(target), "synced": True}
    if staged != {relative}:
        raise SyncError(f"refusing to commit unexpected staged paths: {', '.join(sorted(staged))}")
    git("diff", "--cached", "--check")
    tracked_before = git("ls-files", "--error-unmatch", "--", relative, check=False).returncode == 0
    action = "refresh" if tracked_before else "open"
    result = git("commit", "-m", f"sgg(workday): {action} {day}")
    commit_sha = git("rev-parse", "HEAD").stdout.strip()
    push = git("push", "origin", "main", check=False)
    if push.returncode != 0:
        detail = (push.stderr or push.stdout or "push failed").strip()
        raise SyncError(f"note committed locally as {commit_sha[:12]} but push failed: {detail[:800]}")
    fetch()
    local = git("rev-parse", "HEAD").stdout.strip()
    remote = git("rev-parse", "origin/main").stdout.strip()
    if local != remote:
        raise SyncError(f"push could not be verified (local={local[:12]}, remote={remote[:12]})")
    return {
        "status": "committed",
        "target": str(target),
        "commit": commit_sha,
        "synced": True,
        "commitSummary": result.stdout.strip().splitlines()[0] if result.stdout.strip() else "",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "commit"))
    parser.add_argument("day")
    args = parser.parse_args()
    try:
        result = prepare(args.day) if args.action == "prepare" else commit(args.day)
    except (SyncError, OSError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
