#!/usr/bin/env python3

"""Conditional Herdr status entry for rolling 24-hour OpenRouter spend.

Account-wide, not per-host: the number comes from OpenRouter's analytics API,
so every machine on the rail reports the same figure. It used to be summed out
of the local OpenCode database, which silently scoped it to one host's OpenCode
traffic and ignored every other client and machine.

`POST /analytics/query` reports the trailing 24 hours rather than a UTC calendar
day, but only when asked for hourly buckets — see the comment on `granularity`
in fetch_spend_usd, which is the one detail that makes this honest. It needs a
*management*
key (openrouter.ai/settings/management-keys); an `sk-or-v1` inference key is
answered with `403 Only management keys can access analytics`. Management keys
cannot make model requests, so this stays read-only. The key is read from a file
rather than passed on a command line, where `ps` would expose it.

Setup, once per account (the rail simply stays quiet until then):

    mkdir -p ~/.secrets/openrouter
    pbpaste > ~/.secrets/openrouter/management-key   # or your editor of choice
    chmod 600 ~/.secrets/openrouter/management-key
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

WINDOW_HOURS = 24
ENDPOINT = "https://openrouter.ai/api/v1/analytics/query"
KEY_FILE = Path.home() / ".secrets/openrouter/management-key"
CACHE_FILE = (
    Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "herdr-openrouter-spend-cache"
)
# Herdr re-runs this every 60s on every host. The rail does not need
# minute-fresh money, and the cache doubles as the offline fallback below.
# ponytail: the figure can lag 5 minutes; shorten the TTL if the rail is ever
# used to watch a run's spend live rather than to keep an eye on the day.
CACHE_TTL = 300
HTTP_TIMEOUT = 4


def cached_spend_usd() -> float | None:
    try:
        return float(CACHE_FILE.read_text().strip())
    except (OSError, ValueError):
        return None


def store_spend_usd(total: float) -> None:
    temporary = CACHE_FILE.with_suffix(".tmp")
    try:
        temporary.write_text("%.6f\n" % total)
        temporary.replace(CACHE_FILE)
    except OSError:
        pass


def fetch_spend_usd(key: str) -> float:
    """Total USD spent across the account in the trailing WINDOW_HOURS."""
    now = datetime.now(timezone.utc).replace(microsecond=0)
    payload = json.dumps(
        {
            "metrics": ["total_usage"],
            # granularity is load-bearing, not cosmetic. Without it the API
            # snaps time_range out to whole UTC days: asking for one minute of
            # 2026-08-25 returns all of 2026-08-25, so a trailing-24h request
            # silently becomes "yesterday in full plus today so far" — 24 to 48
            # hours wide depending on the clock, measured at 42.4 hours and
            # 2.04x the true figure when this was written. Hourly buckets are
            # clipped to the requested range instead, and they are exactly
            # additive: summing every hour of a day reproduces that day's total
            # to the last decimal. tests/test-herdr-openrouter-spend.py pins it.
            "granularity": "hour",
            # Well above the 25 buckets a 24h window can span, so a smaller
            # server-side default can never clip the sum.
            "limit": 100,
            "time_range": {
                "start": (now - timedelta(hours=WINDOW_HOURS))
                .isoformat()
                .replace("+00:00", "Z"),
                "end": now.isoformat().replace("+00:00", "Z"),
            },
        }
    ).encode()

    request = urllib.request.Request(
        ENDPOINT,
        data=payload,
        method="POST",
        headers={
            "Authorization": "Bearer %s" % key,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
        body = json.loads(response.read())

    data = body["data"]
    if data.get("metadata", {}).get("truncated"):
        # A partial sum would understate spend; a stale figure is the honest
        # fallback. Unreachable while this query groups by nothing, but the
        # cost of noticing later is a wrong number on the rail.
        raise ValueError("analytics response truncated")

    # One row per hour that saw traffic; quiet hours are omitted rather than
    # returned as zero, so no-rows legitimately means nothing was spent.
    # total_usage arrives as a string on some rows, hence float().
    return sum(float(row.get("total_usage") or 0) for row in data["data"])


def spend_usd() -> float | None:
    try:
        key = KEY_FILE.read_text().strip()
    except OSError:
        return None
    if not key:
        return None

    cached = cached_spend_usd()
    try:
        age = time.time() - CACHE_FILE.stat().st_mtime
    except OSError:
        age = None
    if cached is not None and age is not None and age < CACHE_TTL:
        return cached

    try:
        total = fetch_spend_usd(key)
    except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError):
        # Offline, throttled, or a schema change: hold the last known figure
        # so the rail keeps its width instead of flickering.
        return cached

    store_spend_usd(total)
    return total


def main() -> int:
    total_cost = spend_usd()

    if total_cost is not None and total_cost > 0:
        # Glyph Rail module: the 󰓅 (U+F04C5) gauge carries the WINDOW_HOURS
        # framing, so the rail only prints the amount.
        sys.stdout.write("󰓅 $%.2f\n" % total_cost)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
