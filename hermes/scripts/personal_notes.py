"""Bounded, read-only access to Bryan's personal second brain for Hermes collectors.

The personal second brain is the iCloud Apple Notes folder "Second Brain"
(decision 2026-09-16). Collectors never open the frozen ~/second-brain archive;
they call the shared apple-notes-pkm helper, which returns small JSON payloads
and never the whole library. This module is copied next to the cron entry
scripts (see manifest.json copiedScripts), so it must stay dependency-free.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

HOME = Path.home()
HERMES_HOME = Path(os.environ.get("HERMES_HOME", HOME / ".hermes"))
JOURNAL_FOLDER = "Journal"
ROOT_LABEL = "Second Brain"

HELPER_CANDIDATES = (
    HERMES_HOME / "skills" / "personal" / "apple-notes-pkm" / "scripts" / "apple-notes-pkm.py",
    HOME / "code" / "dotfiles" / "dot-agents" / "skills" / "apple-notes-pkm" / "scripts" / "apple-notes-pkm.py",
)


def helper_path() -> Path | None:
    override = os.environ.get("APPLE_NOTES_PKM_HELPER")
    candidates = ([Path(override)] if override else []) + list(HELPER_CANDIDATES)
    return next((path for path in candidates if path.is_file()), None)


def helper(*args: str, timeout: int = 90) -> tuple[dict[str, Any] | None, str | None]:
    path = helper_path()
    if path is None:
        return None, "apple-notes-pkm helper not installed"
    try:
        proc = subprocess.run(
            [sys.executable, str(path), *args],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)[:500]
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return None, f"helper returned no JSON (exit {proc.returncode}): {(proc.stderr or '')[-300:]}"
    if not payload.get("ok"):
        return None, str(payload.get("error") or f"helper exit {proc.returncode}")[:500]
    return payload, None


def note_ref(title: str, folder: str = JOURNAL_FOLDER) -> str:
    """Human-readable location of a note, used in payloads instead of a file path."""
    return f"{ROOT_LABEL}/{folder}/{title}" if folder else f"{ROOT_LABEL}/{title}"


def find_note(title: str, folder: str = JOURNAL_FOLDER) -> tuple[dict[str, Any] | None, str | None]:
    """Exact-title lookup inside one folder; a bounded title search, never a listing."""
    payload, error = helper("search", title, "--mode", "title", "--folder", folder, "--limit", "5")
    if error or payload is None:
        return None, error
    for row in payload.get("results", []):
        if row.get("title") == title and row.get("folder") == folder:
            return row, None
    return None, None


def read_markdown(note_id: str) -> tuple[str, str | None]:
    payload, error = helper("read", note_id)
    if error or payload is None:
        return "", error
    return payload.get("note", {}).get("markdown", ""), None
