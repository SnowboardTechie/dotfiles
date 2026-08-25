#!/usr/bin/env python3
"""Notify once when Homebrew ships the Herdr Atuin key-protocol fix."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

FORMULA_URL = "https://raw.githubusercontent.com/Homebrew/homebrew-core/HEAD/Formula/h/herdr.rb"
REPOSITORY_URL = "https://github.com/herdrdev/herdr.git"
FIX_COMMIT = "1d604329b0ded93d18fd6b27f72c7473d1fee20f"
STATE_FILE = Path.home() / ".hermes" / "state" / "herdr-homebrew-atuin-fix.json"
USER_AGENT = "dotfiles-herdr-homebrew-atuin-fix-watch/1"
TIMEOUT_SECONDS = 30
MAX_FORMULA_BYTES = 256 * 1024


class WatchError(RuntimeError):
    """A source or verification failure that must make the cron run fail."""


def fetch_formula(url: str = FORMULA_URL) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # nosec B310
            body = response.read(MAX_FORMULA_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise WatchError(f"Homebrew formula fetch failed: HTTP {exc.code}") from None
    except (OSError, urllib.error.URLError) as exc:
        raise WatchError(f"Homebrew formula fetch failed: {type(exc).__name__}") from None
    if len(body) > MAX_FORMULA_BYTES:
        raise WatchError(f"Homebrew formula exceeded {MAX_FORMULA_BYTES} bytes")
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        raise WatchError("Homebrew formula was not valid UTF-8") from None


def formula_release(formula: str) -> tuple[str, str]:
    match = re.search(
        r'^\s*url\s+"https://github\.com/herdrdev/herdr/archive/refs/tags/(v[^"/]+)\.tar\.gz"\s*$',
        formula,
        flags=re.MULTILINE,
    )
    if not match:
        raise WatchError("Homebrew formula did not contain the expected Herdr tag URL")
    tag = match.group(1)
    version = tag.removeprefix("v")
    return tag, version


def release_contains_fix(tag: str) -> bool:
    """Verify the formula's exact release tag descends from the target commit."""
    with tempfile.TemporaryDirectory(prefix="hermes-herdr-watch-") as temporary:
        repository = Path(temporary) / "repo.git"
        init = subprocess.run(
            ["git", "init", "--bare", "--quiet", str(repository)],
            capture_output=True,
            text=True,
            check=False,
        )
        if init.returncode != 0:
            raise WatchError((init.stderr or "git init failed").strip())

        fetch = subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "fetch",
                "--quiet",
                "--filter=blob:none",
                REPOSITORY_URL,
                f"refs/tags/{tag}:refs/tags/{tag}",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        if fetch.returncode != 0:
            detail = (fetch.stderr or fetch.stdout or "git fetch failed").strip()
            raise WatchError(f"could not fetch Herdr release tag {tag}: {detail[:500]}")

        target = subprocess.run(
            ["git", "-C", str(repository), "cat-file", "-e", f"{FIX_COMMIT}^{{commit}}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if target.returncode != 0:
            return False

        ancestry = subprocess.run(
            ["git", "-C", str(repository), "merge-base", "--is-ancestor", FIX_COMMIT, tag],
            capture_output=True,
            text=True,
            check=False,
        )
        if ancestry.returncode == 0:
            return True
        if ancestry.returncode == 1:
            return False
        detail = (ancestry.stderr or ancestry.stdout or "git merge-base failed").strip()
        raise WatchError(f"could not verify Herdr release ancestry: {detail[:500]}")


def load_notified_signature(path: Path) -> str | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise WatchError(f"cannot read notification state at {path}: {exc}") from None
    signature = payload.get("notifiedSignature")
    return signature if isinstance(signature, str) else None


def write_notification_state(path: Path, *, tag: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fixCommit": FIX_COMMIT,
        "formulaUrl": FORMULA_URL,
        "notifiedSignature": f"{tag}:{FIX_COMMIT}",
        "releaseTag": tag,
    }
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(path)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise WatchError(f"cannot write notification state at {path}: {exc}") from None


def notification(version: str, tag: str) -> str:
    release_url = f"https://github.com/herdrdev/herdr/releases/tag/{tag}"
    commit_url = f"https://github.com/herdrdev/herdr/commit/{FIX_COMMIT}"
    return "\n".join(
        [
            f"@bryan:snowboardtechie.com Herdr {version} is now available through Homebrew and includes the Atuin Up/Down key fix.",
            "",
            "Update:",
            "brew update",
            "brew upgrade herdr",
            "",
            "Then restart Herdr. If it runs as a Homebrew service:",
            "brew services restart herdr",
            "",
            "Verify with: herdr --version",
            f"Release: {release_url}",
            f"Fix: {commit_url}",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--formula-file", type=Path, help="read a local formula fixture")
    parser.add_argument("--state-file", type=Path, default=STATE_FILE)
    args = parser.parse_args()

    try:
        formula = (
            args.formula_file.read_text(encoding="utf-8")
            if args.formula_file is not None
            else fetch_formula()
        )
        tag, version = formula_release(formula)
        signature = f"{tag}:{FIX_COMMIT}"
        if load_notified_signature(args.state_file) == signature:
            return 0
        if not release_contains_fix(tag):
            return 0
        write_notification_state(args.state_file, tag=tag)
        print(notification(version, tag))
        return 0
    except (OSError, subprocess.TimeoutExpired, WatchError) as exc:
        print(f"Herdr Homebrew watch failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
