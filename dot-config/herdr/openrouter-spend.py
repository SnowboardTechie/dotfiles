#!/usr/bin/env python3

"""Conditional Herdr status entry for rolling 24-hour OpenRouter spend."""

from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

WINDOW_HOURS = 24
DB_PATH = Path.home() / ".local/share/opencode/opencode.db"


def recent_spend_usd() -> float:
    if not DB_PATH.exists():
        return 0.0

    cutoff_ms = int((time.time() - WINDOW_HOURS * 60 * 60) * 1000)
    query = """
        SELECT COALESCE(SUM(CAST(json_extract(data, '$.cost') AS REAL)), 0)
        FROM message
        WHERE json_extract(data, '$.role') = 'assistant'
          AND json_extract(data, '$.providerID') = 'openrouter'
          AND time_created >= ?
    """

    connection = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        (total,) = connection.execute(query, (cutoff_ms,)).fetchone()
    finally:
        connection.close()

    return float(total or 0.0)


def main() -> int:
    try:
        total_cost = recent_spend_usd()
    except Exception:
        return 0

    if total_cost > 0:
        # Glyph Rail module: the 󰓅 (U+F04C5) gauge carries the WINDOW_HOURS
        # framing, so the rail only prints the amount.
        sys.stdout.write(f"󰓅 ${total_cost:.2f}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
