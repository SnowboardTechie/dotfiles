#!/usr/bin/env python3
"""Check that a current, complete `pr-self-review` exists for the exact candidate.

Recomputes the candidate identity the way `pr-self-review` §2 does, then reads
the review artifacts in the state directory and checks that they were written
for that identity, that none is missing, that no acceptance criterion is
`unswept` or `unmet`, and that Ship Readiness says `Ready to publish`.

Prints one JSON object: `ok`, the recomputed `identity`, the `readiness` line,
and `problems` (one plain sentence per failed condition). Exits 0 only when
`ok`; 1 otherwise. Missing files and unreadable input are problems, never
tracebacks.

Usage:
    check_self_review.py --state-dir DIR --worktree DIR --base REF
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Sequence

READY = "Ready to publish"
REQUIRED_ARTIFACTS = ("review-standards.md", "review-spec.md", "review-ponytail.md")
SUMMARY_KEYS = {
    "candidate": "head_sha",
    "expected_head_branch": "expected_head_branch",
    "base_sha": "base_sha",
    "merge_base_sha": "merge_base_sha",
    "diff_sha256": "diff_sha256",
}
CHECKLIST_KEYS = ("base_sha", "head_sha", "merge_base_sha", "diff_sha256")
BLOCKING_VERDICTS = ("unswept", "unmet")


def git(worktree: Path, *args: str) -> bytes:
    result = subprocess.run(["git", *args], cwd=worktree, capture_output=True)
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", "replace").strip().splitlines()
        raise RuntimeError(f"`git {' '.join(args)}` failed: {message[-1] if message else 'no output'}")
    return result.stdout


def candidate_identity(worktree: Path, base: str) -> dict:
    """The identity `pr-self-review` §2 records, from direct Git state."""
    text = lambda *a: git(worktree, *a).decode("utf-8").strip()  # noqa: E731
    base_sha = text("rev-parse", "--verify", "--end-of-options", f"{base}^{{commit}}")
    head_sha = text("rev-parse", "HEAD")
    diff = git(worktree, "diff", "--binary", "-M", "-C", "--find-copies-harder", f"{base_sha}...{head_sha}", "--")
    status = git(worktree, "status", "--porcelain", "--untracked-files=all").decode("utf-8", "replace")
    return {
        "base_sha": base_sha,
        "head_sha": head_sha,
        "merge_base_sha": text("merge-base", base_sha, head_sha),
        "diff_sha256": hashlib.sha256(diff).hexdigest(),
        "expected_head_branch": text("branch", "--show-current"),
        "clean": status == "",
    }


def frontmatter(text: str) -> dict[str, str]:
    """Flat `key: value` pairs between the leading `---` fences."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        key, sep, value = line.partition(":")
        if sep and not key.startswith((" ", "\t")):
            fields[key.strip()] = value.strip().strip("'\"")
    return {}  # no closing fence


def listed(value: str) -> list[str]:
    return [item.strip().strip("'\"") for item in value.strip().strip("[]").split(",") if item.strip()]


def readiness_line(text: str) -> str | None:
    """The first non-empty line under `## Ship Readiness`."""
    inside = False
    for line in text.splitlines():
        if line.startswith("#"):
            if inside:
                return None
            inside = line.lstrip("#").strip().lower() == "ship readiness"
            continue
        if inside and line.strip():
            return line.strip().lstrip("-* ").strip("`*_ ")
    return None


def check(state_dir: Path, worktree: Path, base: str) -> dict:
    problems: list[str] = []
    identity: dict | None = None
    readiness: str | None = None

    try:
        identity = candidate_identity(worktree, base)
    except (RuntimeError, OSError) as error:
        problems.append(f"Could not recompute the candidate identity from {worktree} against base {base!r}: {error}.")

    if identity is not None:
        if not identity["expected_head_branch"]:
            problems.append("The worktree is not on a named branch.")
        if not identity["clean"]:
            problems.append("The worktree is not clean: `git status --porcelain --untracked-files=all` is not empty.")

    if not state_dir.is_dir():
        problems.append(f"The state directory {state_dir} does not exist.")

    summary_path = state_dir / "summary.md"
    summary: dict[str, str] = {}
    try:
        summary_text = summary_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        problems.append(f"summary.md is missing or unreadable ({error.__class__.__name__}).")
    else:
        summary = frontmatter(summary_text)
        if not summary:
            problems.append("summary.md has no frontmatter.")
        if identity is not None:
            for field, key in SUMMARY_KEYS.items():
                if summary.get(field) != identity[key]:
                    problems.append(
                        f"summary.md {field} is {summary.get(field)!r}, but the current candidate's is {identity[key]!r}."
                    )
        readiness = readiness_line(summary_text)
        if readiness is None:
            problems.append("summary.md has no line under `## Ship Readiness`.")
        elif not readiness.startswith(READY):
            problems.append(f"Ship Readiness is {readiness!r}, not `{READY}`.")

    artifacts = list(REQUIRED_ARTIFACTS)
    if "risk" in listed(summary.get("dimensions", "")):
        artifacts.append("review-risk.md")
    for name in artifacts:
        if not (state_dir / name).is_file():
            problems.append(f"{name} is missing.")

    checklist_path = state_dir / "intent-checklist.json"
    try:
        checklist = json.loads(checklist_path.read_text(encoding="utf-8"))
        if not isinstance(checklist, dict):
            raise ValueError("not a JSON object")
    except (OSError, UnicodeDecodeError, ValueError) as error:
        problems.append(f"intent-checklist.json is missing or unreadable ({error.__class__.__name__}).")
    else:
        recorded = checklist.get("candidate_identity")
        recorded = recorded if isinstance(recorded, dict) else {}
        if identity is not None:
            for key in CHECKLIST_KEYS:
                if recorded.get(key) != identity[key]:
                    problems.append(
                        f"intent-checklist.json {key} is {recorded.get(key)!r}, but the current candidate's is {identity[key]!r}."
                    )
        criteria = checklist.get("criteria")
        if not isinstance(criteria, list) or not criteria:
            problems.append("intent-checklist.json has no acceptance criteria.")
        else:
            for index, criterion in enumerate(criteria):
                item = criterion if isinstance(criterion, dict) else {}
                verdict = item.get("verdict")
                if verdict in BLOCKING_VERDICTS:
                    problems.append(f"Acceptance criterion {item.get('id', index + 1)} is {verdict}.")

    return {"ok": not problems, "identity": identity, "readiness": readiness, "problems": problems}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--state-dir", required=True, type=Path, help="the review's state directory")
    parser.add_argument("--worktree", required=True, type=Path, help="the candidate's worktree")
    parser.add_argument("--base", required=True, help="the base ref or SHA the candidate is reviewed against")
    args = parser.parse_args(argv)
    report = check(args.state_dir, args.worktree, args.base)
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
