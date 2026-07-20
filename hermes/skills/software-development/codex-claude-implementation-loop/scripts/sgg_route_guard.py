#!/usr/bin/env python3
"""Fail-closed Simpler Grants repository guard for the Claude worker."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

ALLOWED_HOST = "github.com"
ALLOWED_REPOSITORIES = {
    "hhs/simpler-grants-gov",
    "hhs/simpler-grants-protocol",
    "common-grants/py-cg-grants-gov",
    "common-grants/ts-cg-grants-gov",
}


class GuardError(RuntimeError):
    """The worktree identity is not authorized for Claude."""


def run_git(workdir: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(workdir), *args],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise GuardError(f"git {' '.join(args)} failed: {detail}")
    return completed.stdout.strip()


def remote_identity(remote_url: str) -> tuple[str, str]:
    remote = remote_url.strip()
    scp_match = re.fullmatch(r"[^/@:]+@([^/:]+):(.+)", remote)
    if scp_match:
        host = scp_match.group(1).lower()
        path = scp_match.group(2)
    else:
        parsed = urlparse(remote)
        if parsed.scheme not in {"http", "https", "ssh", "git"} or not parsed.hostname:
            raise GuardError("unsupported origin remote URL")
        host = parsed.hostname.lower()
        path = parsed.path

    parts = [part for part in path.strip("/").split("/") if part]
    if len(parts) != 2:
        raise GuardError("origin remote must identify exactly owner/repository")
    owner, repository = parts
    if repository.endswith(".git"):
        repository = repository[:-4]
    identity = f"{owner}/{repository}".lower()
    if not owner or not repository:
        raise GuardError("origin remote does not identify owner/repository")
    return host, identity


def validate_sgg_worktree(workdir_text: str) -> dict[str, str | bool]:
    requested = Path(workdir_text).expanduser().resolve()
    if not requested.is_dir():
        raise GuardError(f"workdir is not a directory: {requested}")
    root = Path(run_git(requested, "rev-parse", "--show-toplevel")).resolve()
    common_dir = Path(
        run_git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    ).resolve()
    if not common_dir.is_dir():
        raise GuardError(f"Git common directory is invalid: {common_dir}")
    remote_url = run_git(root, "remote", "get-url", "origin")
    host, repository = remote_identity(remote_url)
    if host != ALLOWED_HOST or repository not in ALLOWED_REPOSITORIES:
        raise GuardError(
            "Claude worker is restricted to verified SGG repositories on github.com; "
            f"resolved {host}/{repository}"
        )
    return {
        "ok": True,
        "root": str(root),
        "git_common_dir": str(common_dir),
        "origin_host": host,
        "origin_repository": repository,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", required=True)
    args = parser.parse_args()
    try:
        payload = validate_sgg_worktree(args.workdir)
    except GuardError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
