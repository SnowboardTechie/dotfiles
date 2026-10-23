#!/usr/bin/env python3
"""Collector for the nightly YunoHost update report.

Runs only after the monitor detects a change. Prints the pending snapshot plus
bounded release-note excerpts for each pending app, so the assessing agent can
work with zero tools and therefore no path to the server's upgrade commands.
Release-source failures are listed per app; a server failure exits non-zero.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yunohost_updates_lib as lib  # noqa: E402


def main() -> int:
    try:
        snap = lib.snapshot(lib.fetch_pending())
    except (lib.SourceError, OSError, TimeoutError) as exc:
        print(f"YunoHost update check failed: {exc}", file=sys.stderr)
        return 1
    snap["releaseNotes"] = [lib.collect_notes(app) for app in snap["apps"]]
    sys.stdout.write(lib.render(snap))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
