#!/usr/bin/env python3
"""Collect minimal state for Bryan's recurring weekly orientation invitation."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from personal_notes import find_note, note_ref  # noqa: E402

PACIFIC = ZoneInfo("America/Los_Angeles")


def next_monday(day):
    current_monday = day - timedelta(days=day.weekday())
    return current_monday + timedelta(days=7)


def main() -> int:
    now = datetime.now(PACIFIC)
    week_start = next_monday(now.date())
    hub_title = f"{week_start.isoformat()}-weekly-plan"
    hub, error = find_note(hub_title)
    payload = {
        "generatedAt": now.isoformat(),
        "timezone": "America/Los_Angeles",
        "sourceErrors": {"secondBrain": error} if error else {},
        "checkIn": {
            "backend": "apple-notes",
            "nextWeekStart": week_start.isoformat(),
            "nextWeekHubTitle": hub_title,
            "nextWeekHubPath": note_ref(hub_title),
            "nextWeekHubId": hub["id"] if hub else None,
            "nextWeekHubExists": bool(hub),
            # An unreadable backend is unknown, not "not yet written": stay silent
            # rather than inviting a reset that may already have happened.
            "alreadyCompleted": bool(hub) or bool(error),
        },
    }
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
