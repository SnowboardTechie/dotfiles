#!/usr/bin/env python3
"""Read-only structural audit for Bryan's project vaults.

Reports missing entry points, stale verification dates, unresolved internal
wikilinks, zero-inbound canonical notes, and canonical files newer than the
index/status surface. Findings are triage candidates; the script never edits.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
from collections import defaultdict
from pathlib import Path

EXCLUDED_PARTS = {".agents", ".obsidian", "drafts", "templates"}
EXCLUDED_NAMES = {"AGENTS.md", "CLAUDE.md"}
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
FENCE_RE = re.compile(r"```.*?```|~~~.*?~~~", re.S)
DATE_RE = re.compile(r"^(updated|created|index-last-verified):\s*(\d{4}-\d{2}-\d{2})\s*$", re.M)
ALLOW_RE = re.compile(r"<!--\s*vault-audit:\s*allow-link\s+(.+?)\s*-->")


def canonical_files(vault: Path) -> list[Path]:
    return sorted(
        path
        for path in vault.rglob("*.md")
        if not any(part in EXCLUDED_PARTS for part in path.relative_to(vault).parts)
        and path.name not in EXCLUDED_NAMES
    )


def normalized_target(raw: str) -> str:
    target = raw.split("|", 1)[0].split("#", 1)[0].split("^", 1)[0].strip()
    return target.removesuffix(".md").strip("/")


def note_keys(path: Path, vault: Path) -> set[str]:
    rel = path.relative_to(vault).with_suffix("").as_posix()
    return {rel.casefold(), path.stem.casefold()}


def git_date(repo: Path, path: Path) -> dt.date | None:
    result = subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%cs", "--", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    value = result.stdout.strip()
    try:
        return dt.date.fromisoformat(value) if value else None
    except ValueError:
        return None


def metadata_dates(path: Path) -> dict[str, dt.date]:
    text = path.read_text(errors="replace")
    dates: dict[str, dt.date] = {}
    for key, value in DATE_RE.findall(text):
        try:
            dates[key] = dt.date.fromisoformat(value)
        except ValueError:
            pass
    return dates


def audit_vault(repo: Path, vault: Path, stale_days: int) -> int:
    findings = 0
    print(f"\n## {vault.name}")
    files = canonical_files(vault)
    index = vault / "INDEX.md"
    status = vault / "status.md"

    if not index.exists():
        print("MISSING_INDEX INDEX.md")
        findings += 1
        return findings

    verified = metadata_dates(index).get("index-last-verified")
    if verified is None:
        print("INDEX_FRESHNESS missing index-last-verified")
        findings += 1
    else:
        age = (dt.date.today() - verified).days
        if age > stale_days:
            print(f"INDEX_FRESHNESS {verified.isoformat()} ({age} days old)")
            findings += 1

    key_to_path: dict[str, Path] = {}
    for path in files:
        for key in note_keys(path, vault):
            key_to_path.setdefault(key, path)

    inbound: dict[Path, set[Path]] = defaultdict(set)
    for source in files:
        text = FENCE_RE.sub("", source.read_text(errors="replace"))
        allowed = {normalized_target(item).casefold() for item in ALLOW_RE.findall(text)}
        for raw in WIKILINK_RE.findall(text):
            target = normalized_target(raw)
            if not target or target.startswith(("~", "/", "http://", "https://")):
                continue
            if target.casefold() in allowed:
                continue
            if (vault / target).is_dir():
                continue
            destination = key_to_path.get(target.casefold())
            if destination is None and (target.startswith(".") or "/" in target):
                candidate = (source.parent / f"{target}.md").resolve()
                try:
                    candidate.relative_to(vault.resolve())
                except ValueError:
                    candidate = Path()
                if candidate in files:
                    destination = candidate
            if destination is None:
                print(f"BROKEN_LINK {source.relative_to(vault)} -> [[{raw}]]")
                findings += 1
            else:
                inbound[destination].add(source)

    for path in files:
        if path == index:
            continue
        if not inbound[path]:
            print(f"ZERO_INBOUND {path.relative_to(vault)}")
            findings += 1

    source_dates = [
        (git_date(repo, path), path)
        for path in files
        if path not in {index, status}
    ]
    source_dates = [(date, path) for date, path in source_dates if date]
    if source_dates:
        newest_date, newest_path = max(source_dates, key=lambda item: item[0])
        for surface in (index, status):
            if not surface.exists():
                continue
            surface_date = git_date(repo, surface)
            if surface_date and newest_date > surface_date:
                print(
                    "SURFACE_OLDER "
                    f"{surface.relative_to(vault)}@{surface_date} < "
                    f"{newest_path.relative_to(vault)}@{newest_date}"
                )
                findings += 1

    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, help="project-vault repository root")
    parser.add_argument("vaults", nargs="*", help="vault directory names (default: all)")
    parser.add_argument("--stale-days", type=int, default=30)
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    names = args.vaults or [
        path.name
        for path in sorted(root.iterdir())
        if path.is_dir()
        and not path.name.startswith(".")
        and any(path.rglob("*.md"))
    ]
    findings = sum(audit_vault(root, root / name, args.stale_days) for name in names)
    print(f"\n{findings} finding(s); read-only audit, no files changed.")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
