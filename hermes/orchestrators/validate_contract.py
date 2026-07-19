#!/usr/bin/env python3
"""Validate the persistent block in a Hermes orchestrator contract."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import NoReturn

FIELD_ORDER = ("outcome", "verification", "constraints", "boundaries", "stop when")
FIELD_PATTERN = re.compile(r"^(outcome|verification|constraints|boundaries|stop when):\s+\S", re.IGNORECASE)
GOAL_PATTERN = re.compile(r"^[!/]goal\s+\S", re.IGNORECASE)
PLACEHOLDER_PATTERN = re.compile(r"<[^>\n]+>")
TEXT_BLOCK_PATTERN = re.compile(r"```text\s*\n(.*?)\n```", re.DOTALL | re.IGNORECASE)
PROHIBITION_PATTERN = re.compile(r"\b(never|must not|do not|prohibited)\b", re.IGNORECASE)
PERMISSION_PATTERN = re.compile(r"\b(may|allowed|authorized|permit(?:ted)?)\b", re.IGNORECASE)


def fail(message: str) -> NoReturn:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def goal_block(markdown: str) -> list[str]:
    candidates = []
    for block in TEXT_BLOCK_PATTERN.findall(markdown):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if lines and GOAL_PATTERN.match(lines[0]):
            candidates.append(lines)
    if len(candidates) != 1:
        fail(f"expected exactly one text block beginning with /goal or !goal; found {len(candidates)}")
    return candidates[0]


def validate(path: Path, allow_placeholders: bool) -> None:
    markdown = path.read_text(encoding="utf-8")
    lines = goal_block(markdown)
    if sum(bool(GOAL_PATTERN.match(line)) for line in lines) != 1:
        fail("goal block must contain exactly one goal headline")

    fields: dict[str, list[str]] = {field: [] for field in FIELD_ORDER}
    positions: dict[str, int] = {}
    for position, line in enumerate(lines[1:], start=1):
        match = FIELD_PATTERN.match(line)
        if not match:
            fail(f"unrecognized or empty contract line: {line!r}")
        field = match.group(1).lower()
        fields[field].append(line)
        positions.setdefault(field, position)

    missing = [field for field in FIELD_ORDER if not fields[field]]
    if missing:
        fail(f"missing required field(s): {', '.join(missing)}")
    if [positions[field] for field in FIELD_ORDER] != sorted(positions.values()):
        fail(f"fields must first appear in this order: {', '.join(FIELD_ORDER)}")

    boundaries = "\n".join(fields["boundaries"])
    if not PERMISSION_PATTERN.search(boundaries):
        fail("boundaries must state at least one explicit permission")
    if not PROHIBITION_PATTERN.search(boundaries):
        fail("boundaries must state at least one explicit prohibition")

    if not allow_placeholders:
        placeholders = sorted(set(PLACEHOLDER_PATTERN.findall("\n".join(lines))))
        if placeholders:
            fail(f"active contract contains unresolved placeholder(s): {', '.join(placeholders)}")

    print(
        f"valid orchestrator contract: {path} "
        f"({len(lines) - 1} contract clauses; placeholders={'allowed' if allow_placeholders else 'rejected'})"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path)
    parser.add_argument(
        "--allow-placeholders",
        action="store_true",
        help="permit <placeholder> tokens in an uninstantiated template",
    )
    args = parser.parse_args()
    if not args.contract.is_file():
        fail(f"contract not found: {args.contract}")
    validate(args.contract, args.allow_placeholders)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
