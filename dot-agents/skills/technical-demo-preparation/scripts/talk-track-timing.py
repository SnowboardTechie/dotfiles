#!/usr/bin/env python3
"""Count spoken words in a demo runbook's talk track and estimate delivery time.

Spoken lines are Markdown blockquote lines ("> ...") inside the talk-track
section. Subsections ("### ...") are reported separately.

Usage:
  python3 talk-track-timing.py RUNBOOK.md [--section "Full talk track"] [--wpm 120 140]
"""
import argparse
import re
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--section", default="Full talk track")
    ap.add_argument("--wpm", nargs=2, type=int, default=[120, 140])
    args = ap.parse_args()

    text = Path(args.path).read_text()
    m = re.search(rf"^##\s+{re.escape(args.section)}\s*$", text, re.M)
    if not m:
        print(f"section '## {args.section}' not found", file=sys.stderr)
        return 1
    body = text[m.end():]
    nxt = re.search(r"^##\s", body, re.M)
    if nxt:
        body = body[: nxt.start()]

    parts = re.split(r"^###\s+(.*)$", body, flags=re.M)
    sections = [("(intro)", parts[0])] + list(zip(parts[1::2], parts[2::2]))
    total = 0
    dashes = 0
    for name, chunk in sections:
        spoken = " ".join(l[1:].strip() for l in chunk.splitlines() if l.startswith(">"))
        n = len(spoken.split())
        dashes += spoken.count("\u2014")
        if n:
            print(f"{name}: {n} words")
        total += n

    slow, fast = sorted(args.wpm)
    lo, hi = total / fast * 60, total / slow * 60
    fmt = lambda s: f"{int(s // 60)}:{int(round(s % 60)):02d}"
    print(f"total: {total} words, {fmt(lo)}-{fmt(hi)} at {fast}-{slow} wpm")
    print(f"em-dashes in spoken lines: {dashes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
