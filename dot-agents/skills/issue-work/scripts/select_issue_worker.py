#!/usr/bin/env python3
"""Select the issue-work implementation worker from verified repository identity."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any
from urllib.parse import urlparse

SGG_REPOSITORIES = {
    "hhs/simpler-grants-gov",
    "hhs/simpler-grants-protocol",
    "common-grants/py-cg-grants-gov",
    "common-grants/ts-cg-grants-gov",
}
SGG_FORGE_HOST = "github.com"


class RoutingError(RuntimeError):
    """Repository identity or routing policy could not be verified."""


def identity_from_remote(remote_url: str) -> tuple[str, str]:
    """Return forge host and owner/repository from a supported Git remote."""
    remote = remote_url.strip()
    if not remote:
        raise RoutingError("origin remote URL is empty")

    scp_match = re.fullmatch(r"[^/@:]+@([^/:]+):(.+)", remote)
    if scp_match:
        host = scp_match.group(1).lower()
        path = scp_match.group(2)
    else:
        parsed = urlparse(remote)
        if parsed.scheme not in {"http", "https", "ssh", "git"} or not parsed.netloc:
            raise RoutingError("unsupported origin remote URL")
        if not parsed.hostname:
            raise RoutingError("origin remote URL has no forge host")
        host = parsed.hostname.lower()
        path = parsed.path

    parts = [part for part in path.strip("/").split("/") if part]
    if len(parts) != 2:
        raise RoutingError("origin remote must identify exactly owner/repository")
    owner, repository = parts
    if repository.endswith(".git"):
        repository = repository[:-4]
    if not owner or not repository:
        raise RoutingError("origin remote does not identify owner/repository")
    return host, f"{owner}/{repository}"


def repo_from_remote(remote_url: str) -> str:
    return identity_from_remote(remote_url)[1]


def normalize_repo(repo: str) -> str:
    value = repo.strip().strip("/")
    parts = value.split("/")
    if len(parts) != 2 or not all(parts):
        raise RoutingError(f"ticket repository must be owner/repository: {repo}")
    return value.lower()


def select_worker(
    *,
    ticket_repo: str,
    remote_url: str,
    override: str,
) -> dict[str, Any]:
    ticket_key = normalize_repo(ticket_repo)
    remote_host, remote_repo = identity_from_remote(remote_url)
    remote_key = normalize_repo(remote_repo)
    if ticket_key != remote_key:
        raise RoutingError(
            f"ticket repository {ticket_repo} does not match origin repository {remote_repo}"
        )

    is_sgg = remote_host == SGG_FORGE_HOST and ticket_key in SGG_REPOSITORIES
    if override == "auto":
        selected = "claude" if is_sgg else "qwen"
        reason = "verified SGG allowlist" if is_sgg else "default non-SGG issue-work route"
    elif override == "claude":
        if not is_sgg:
            raise RoutingError(
                "Claude is restricted to the verified SGG repository allowlist"
            )
        selected = "claude"
        reason = "explicit Claude selection within SGG allowlist"
    elif override == "qwen":
        selected = "qwen"
        reason = "explicit local Qwen selection"
    elif override == "gpt":
        selected = "gpt"
        reason = "explicit host-native GPT selection"
    else:
        raise RoutingError(f"unsupported worker override: {override}")

    loops = {
        "claude": "codex-claude-implementation-loop",
        "qwen": "codex-qwen-implementation-loop",
        "gpt": None,
    }
    return {
        "ok": True,
        "ticket_repo": ticket_repo,
        "remote_host": remote_host,
        "remote_repo": remote_repo,
        "sgg_allowlisted": is_sgg,
        "selected_worker": selected,
        "implementation_loop": loops[selected],
        "reason": reason,
    }


def git_output(workdir: Path, args: list[str], label: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(workdir),
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise RoutingError(f"could not read {label}: {detail}")
    return completed.stdout.strip()


def repository_identity(workdir: Path) -> tuple[Path, str]:
    common_text = git_output(
        workdir,
        ["rev-parse", "--path-format=absolute", "--git-common-dir"],
        "Git common directory",
    )
    common_dir = Path(common_text).expanduser().resolve()
    if not common_dir.is_dir():
        raise RoutingError(f"Git common directory does not exist: {common_dir}")
    remote = git_output(
        workdir,
        ["remote", "get-url", "origin"],
        "origin remote",
    )
    return common_dir, remote


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", type=Path, default=Path.cwd())
    parser.add_argument("--ticket-repo", required=True)
    parser.add_argument(
        "--override",
        choices=("auto", "gpt", "qwen", "claude"),
        default="auto",
    )
    args = parser.parse_args()

    workdir = args.workdir.expanduser().resolve()
    if not workdir.is_dir():
        print(json.dumps({"ok": False, "error": f"workdir does not exist: {workdir}"}))
        return 1
    try:
        common_dir, remote = repository_identity(workdir)
        result = select_worker(
            ticket_repo=args.ticket_repo,
            remote_url=remote,
            override=args.override,
        )
        result["git_common_dir"] = str(common_dir)
    except (OSError, subprocess.SubprocessError, RoutingError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
