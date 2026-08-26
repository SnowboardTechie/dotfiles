#!/usr/bin/env python3

"""Tests for dot-config/herdr/openrouter-spend.py.

The network is stubbed and the key file and cache live in a temp directory, so
this never touches the real account or the real credential.

The expected glyph is built with chr(), never pasted literally, for the reason
tests/test-herdr-glyph-rail.py spells out: a test carrying the raw Plane-15
character could be stripped by the same pipeline that strips the module, and
would then assert nothing against nothing.

Run: python3 tests/test-herdr-openrouter-spend.py
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import time
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "dot-config/herdr/openrouter-spend.py"

GAUGE = chr(0xF04C5)  # Nerd Font gauge, the spend module's glyph

spec = importlib.util.spec_from_file_location("openrouter_spend", MODULE_PATH)
spend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(spend)

failures: list[str] = []


def check(description: str, ok: bool, detail: str = "") -> None:
    if ok:
        print("ok   %s" % description)
    else:
        print("FAIL: %s" % description, file=sys.stderr)
        if detail:
            print("  %s" % detail, file=sys.stderr)
        failures.append(description)


class FakeResponse:
    def __init__(self, body: dict) -> None:
        self._body = json.dumps(body).encode()

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False


def run(
    *,
    key: str | None,
    response: object = None,
    cache: str | None = None,
    cache_age: float = 0.0,
) -> tuple[str, list[dict]]:
    """Drive main() against a stubbed API. Returns (stdout, captured requests)."""
    with tempfile.TemporaryDirectory() as workspace:
        root = Path(workspace)
        spend.KEY_FILE = root / "management-key"
        spend.CACHE_FILE = root / "cache"
        if key is not None:
            spend.KEY_FILE.write_text(key + "\n")
        if cache is not None:
            spend.CACHE_FILE.write_text(cache + "\n")
            stamp = time.time() - cache_age
            os.utime(spend.CACHE_FILE, (stamp, stamp))

        requests: list[dict] = []

        def fake_urlopen(request, timeout=None):  # noqa: ANN001 - stub signature
            requests.append(
                {
                    "url": request.full_url,
                    "headers": {k.lower(): v for k, v in request.header_items()},
                    "body": json.loads(request.data),
                    "timeout": timeout,
                }
            )
            if isinstance(response, Exception):
                raise response
            return FakeResponse(response)

        original = spend.urllib.request.urlopen
        spend.urllib.request.urlopen = fake_urlopen
        try:
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                spend.main()
        finally:
            spend.urllib.request.urlopen = original

        return stream.getvalue(), requests


def analytics_response(rows: list[dict], truncated: bool = False) -> dict:
    return {
        "data": {
            "data": rows,
            "metadata": {"query_time_ms": 9, "row_count": len(rows), "truncated": truncated},
        }
    }


# 1. The happy path: rows are summed and rendered behind the gauge glyph.
#    total_usage arrives as a string in some rows, per OpenRouter's own docs.
out, calls = run(
    key="test-management-key",
    response=analytics_response([{"total_usage": 3.5}, {"total_usage": "0.45"}]),
)
check(
    "sums total_usage and prints it behind the U+F04C5 gauge",
    out == "%s $3.95\n" % GAUGE,
    "got %r" % out,
)

# 2. The credential goes in a header, is the management key, and never lands in
#    argv where `ps` could read it.
check(
    "authenticates with the management key from ~/.secrets",
    len(calls) == 1
    and calls[0]["headers"].get("Authorization".lower()) == "Bearer test-management-key",
    "got %r" % (calls[0]["headers"] if calls else None),
)

# 3. The window is account-wide (no dimensions) and really rolls 24 hours,
#    rather than snapping to a UTC calendar day.
body = calls[0]["body"] if calls else {}
window = body.get("time_range", {})
try:
    start = datetime.fromisoformat(window["start"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(window["end"].replace("Z", "+00:00"))
    span_hours = (end - start).total_seconds() / 3600
    ends_now = abs((datetime.now(timezone.utc) - end).total_seconds()) < 120
except (KeyError, ValueError, AttributeError):
    span_hours, ends_now = 0.0, False
check(
    # The literal 24, not spend.WINDOW_HOURS: asserting against the module's
    # own constant would move with the bug and pass on any window.
    "queries a trailing 24-hour window ending now",
    span_hours == 24 and ends_now,
    "got %r (span %.2fh)" % (window, span_hours),
)
check(
    "asks for account-wide spend: total_usage, no dimensions",
    body.get("metrics") == ["total_usage"] and not body.get("dimensions"),
    "got %r" % (body,),
)

# 4. No management key means no output and no network call — the rail entry is
#    conditional, so an unconfigured host simply drops the module.
out, calls = run(key=None, response=analytics_response([{"total_usage": 9.0}]))
check("stays silent and offline without a management key", out == "" and calls == [], "got %r" % out)

# 5. Offline with a warm-but-stale cache: hold the last known figure rather
#    than letting the rail flicker.
out, calls = run(
    key="test-management-key",
    response=urllib.error.URLError("offline"),
    cache="1.25",
    cache_age=spend.CACHE_TTL + 60,
)
check("falls back to the cached figure when the API is unreachable", out == "%s $1.25\n" % GAUGE, "got %r" % out)

# 6. A truncated response would understate spend, so it must not be printed.
out, _ = run(
    key="test-management-key",
    response=analytics_response([{"total_usage": 3.5}], truncated=True),
)
check("refuses to print a truncated (partial) total", out == "", "got %r" % out)

# 7. A fresh cache is served without hitting the API.
out, calls = run(
    key="test-management-key",
    response=analytics_response([{"total_usage": 9.0}]),
    cache="2.10",
    cache_age=1,
)
check(
    "serves a fresh cache without calling the API",
    out == "%s $2.10\n" % GAUGE and calls == [],
    "got %r after %d call(s)" % (out, len(calls)),
)

# 8. Zero spend keeps the module conditional: nothing to show, nothing shown.
out, _ = run(key="test-management-key", response=analytics_response([{"total_usage": 0}]))
check("prints nothing when the account spent nothing", out == "", "got %r" % out)

if failures:
    print("\n%d check(s) failed" % len(failures), file=sys.stderr)
    sys.exit(1)
