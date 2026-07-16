#!/usr/bin/env python3
"""Syntax-check every fenced bash block in an offline Markdown runbook.

This never executes the commands. It only passes each block to `bash -n`, so it
is safe for runbooks containing service stops, imports, deletes, or migrations.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("runbook", type=Path)
    args = parser.parse_args()

    text = args.runbook.read_text(encoding="utf-8")
    blocks = re.findall(r"```bash\n(.*?)\n```", text, flags=re.DOTALL)
    if not blocks:
        parser.error("runbook contains no fenced bash blocks")

    failures: list[str] = []
    for index, block in enumerate(blocks, start=1):
        result = subprocess.run(
            ["/bin/bash", "-n"],
            input=block,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            failures.append(f"block {index}: {result.stderr.strip()}")

    if failures:
        print("Runbook shell syntax failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(f"Runbook shell syntax passed: {len(blocks)} bash blocks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
