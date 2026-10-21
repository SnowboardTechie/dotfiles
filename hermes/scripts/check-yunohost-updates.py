#!/usr/bin/env python3
"""Monitor for the nightly YunoHost update report.

Prints a stable snapshot of pending YunoHost system and app upgrades. The
scheduler hashes these bytes; unchanged output suppresses the agent run, so a
held upgrade is reported once, not nightly. A server failure exits non-zero so
the scheduler records an error instead of a quiet night. Read-only.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yunohost_updates_lib as lib  # noqa: E402


def main() -> int:
    try:
        pending = lib.fetch_pending()
    except (lib.SourceError, OSError, TimeoutError) as exc:
        print(f"YunoHost update check failed: {exc}", file=sys.stderr)
        return 1
    sys.stdout.write(lib.render(lib.snapshot(pending)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
