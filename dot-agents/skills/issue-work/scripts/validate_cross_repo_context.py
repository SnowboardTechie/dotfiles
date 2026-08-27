#!/usr/bin/env python3
"""Validate ticket-state and implementation-worktree authority for issue-work."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Dict, NoReturn, TypedDict
from urllib.parse import urlparse


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from select_issue_worker import identity_from_remote, normalize_repo  # noqa: E402


class ContextError(RuntimeError):
    """Cross-repository context is missing, inconsistent, or unsafe."""


class GitContext(TypedDict):
    top: Path
    trunk: Path
    host: str
    repo: str
    branch: str


def fail(message: str) -> NoReturn:
    raise ContextError(message)


def git_output(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(path),
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        fail(f"git {' '.join(args)} failed for {path}: {detail}")
    return result.stdout.strip()


def resolve_git_context(path: Path) -> GitContext:
    candidate = path.expanduser().resolve()
    if not candidate.is_dir():
        fail(f"Git path does not exist: {candidate}")
    top = Path(git_output(candidate, "rev-parse", "--show-toplevel")).resolve()
    common = Path(
        git_output(candidate, "rev-parse", "--path-format=absolute", "--git-common-dir")
    ).resolve()
    if not common.is_dir():
        fail(f"Git common directory does not exist: {common}")
    remote = git_output(candidate, "remote", "get-url", "origin")
    host, repo = identity_from_remote(remote)
    return {
        "top": top,
        "trunk": common.parent,
        "host": host,
        "repo": repo,
        "branch": git_output(candidate, "branch", "--show-current"),
    }


def read_frontmatter(path: Path) -> Dict[str, str]:
    if not path.is_file():
        fail(f"progress file does not exist: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        fail(f"progress file has no frontmatter: {path}")
    values: Dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return values
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            fail(f"invalid progress frontmatter line: {line}")
        key, value = line.split(":", 1)
        key = key.strip()
        if key in values:
            fail(f"duplicate progress frontmatter key: {key}")
        values[key] = value.strip().strip('"').strip("'")
    fail(f"progress frontmatter is not closed: {path}")


def require_equal(progress: Dict[str, str], key: str, expected: str) -> None:
    actual = progress.get(key)
    if actual != expected:
        fail(f"progress {key}={actual!r}; expected {expected!r}")


def require_path_equal(progress: Dict[str, str], key: str, expected: Path) -> None:
    actual = progress.get(key)
    if not actual or Path(actual).expanduser().resolve() != expected.resolve():
        fail(f"progress {key}={actual!r}; expected canonical path {str(expected)!r}")


def validate_context(
    *,
    ticket_trunk: Path,
    state_dir: Path,
    worktree: Path,
    ticket_url: str,
    ticket_host: str,
    ticket_repo: str,
    implementation_host: str,
    implementation_repo: str,
) -> Dict[str, object]:
    ticket = resolve_git_context(ticket_trunk)
    implementation = resolve_git_context(worktree)

    ticket_root = ticket["trunk"].resolve()
    requested_ticket_root = ticket_trunk.expanduser().resolve()
    if requested_ticket_root != ticket_root:
        fail(f"ticket_trunk is not the canonical Git trunk: {requested_ticket_root}")

    parsed_url = urlparse(ticket_url)
    if (
        parsed_url.scheme not in {"http", "https"}
        or not parsed_url.hostname
        or parsed_url.username
        or parsed_url.password
        or parsed_url.query
        or parsed_url.fragment
    ):
        fail(f"ticket URL is not canonical: {ticket_url}")
    if parsed_url.hostname.lower() != ticket_host.strip().lower():
        fail("ticket URL hostname does not match ticket_host")
    url_parts = [part for part in parsed_url.path.strip("/").split("/") if part]
    if (
        len(url_parts) != 4
        or url_parts[2] not in {"issues", "pull", "pulls"}
        or not url_parts[3].isdigit()
        or not all(re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in url_parts[:2])
    ):
        fail(f"ticket URL has an unsupported repository/ticket path: {ticket_url}")
    if normalize_repo("/".join(url_parts[:2])) != normalize_repo(ticket_repo):
        fail("ticket URL repository does not match ticket_repo")

    if str(ticket["host"]).lower() != ticket_host.strip().lower():
        fail("ticket origin hostname does not match ticket_host")
    if normalize_repo(str(ticket["repo"])) != normalize_repo(ticket_repo):
        fail("ticket origin repository does not match ticket_repo")
    if str(implementation["host"]).lower() != implementation_host.strip().lower():
        fail("implementation origin hostname does not match implementation_host")
    if normalize_repo(str(implementation["repo"])) != normalize_repo(implementation_repo):
        fail("implementation origin repository does not match implementation_repo")

    state = state_dir.expanduser().resolve()
    authorized_state_root = (ticket_root / ".hermes" / "issue-work").resolve()
    if not state.is_dir():
        fail(f"state directory does not exist: {state}")
    try:
        relative_state = state.relative_to(authorized_state_root)
    except ValueError:
        fail(f"state directory escapes ticket state root: {state}")
    if not relative_state.parts:
        fail("state directory must be a per-ticket child of the ticket state root")

    progress = read_frontmatter(state / "progress.md")
    worktree_root = implementation["top"].resolve()
    implementation_trunk = implementation["trunk"].resolve()
    require_equal(progress, "ticket", ticket_url)
    require_path_equal(progress, "worktree", worktree_root)
    require_equal(progress, "branch", str(implementation["branch"]))
    require_equal(progress, "ticket_repository", ticket_repo)
    require_equal(progress, "implementation_forge", implementation_host)
    require_equal(progress, "implementation_repository", implementation_repo)
    require_path_equal(progress, "implementation_trunk", implementation_trunk)

    cross_repository = (
        ticket_host.strip().lower() != implementation_host.strip().lower()
        or normalize_repo(ticket_repo) != normalize_repo(implementation_repo)
    )
    source_issue_mode = (
        "github_shorthand"
        if not cross_repository and ticket_host.strip().lower() == "github.com"
        else "plan_only"
    )
    return {
        "ok": True,
        "ticket_url": ticket_url,
        "ticket_host": ticket_host.strip().lower(),
        "ticket_repo": ticket_repo,
        "ticket_trunk": str(ticket_root),
        "state_dir": str(state),
        "implementation_host": implementation_host.strip().lower(),
        "implementation_repo": implementation_repo,
        "implementation_root": str(worktree_root),
        "implementation_trunk": str(implementation_trunk),
        "branch": str(implementation["branch"]),
        "cross_repository": cross_repository,
        "source_issue_mode": source_issue_mode,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticket-trunk", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--worktree", type=Path, required=True)
    parser.add_argument("--ticket-url", required=True)
    parser.add_argument("--ticket-host", required=True)
    parser.add_argument("--ticket-repo", required=True)
    parser.add_argument("--implementation-host", required=True)
    parser.add_argument("--implementation-repo", required=True)
    args = parser.parse_args()
    try:
        result = validate_context(
            ticket_trunk=args.ticket_trunk,
            state_dir=args.state_dir,
            worktree=args.worktree,
            ticket_url=args.ticket_url,
            ticket_host=args.ticket_host,
            ticket_repo=args.ticket_repo,
            implementation_host=args.implementation_host,
            implementation_repo=args.implementation_repo,
        )
    except (ContextError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
