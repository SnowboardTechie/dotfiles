#!/usr/bin/env python3
"""Notify once when Homebrew ships cloudflared at or above a target version."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

FORMULA_URL = "https://raw.githubusercontent.com/Homebrew/homebrew-core/HEAD/Formula/c/cloudflared.rb"
TARGET_VERSION = "2026.10.4"
CLOUDFLARED = "/opt/homebrew/bin/cloudflared"
STATE_FILE = Path.home() / ".hermes" / "state" / "cloudflared-homebrew-release.json"
USER_AGENT = "dotfiles-cloudflared-homebrew-release-watch/1"
TIMEOUT_SECONDS = 30
MAX_FORMULA_BYTES = 256 * 1024


class WatchError(RuntimeError):
    """A source failure that must make the cron run fail."""


def parse_version(text: str) -> tuple[int, ...]:
    if not re.fullmatch(r"\d+(\.\d+)+", text):
        raise WatchError(f"unexpected cloudflared version {text!r}")
    return tuple(int(part) for part in text.split("."))


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


def formula_version(formula: str) -> str:
    match = re.search(
        r'^\s*url\s+"https://github\.com/cloudflare/cloudflared/archive/refs/tags/([^"/]+)\.tar\.gz"\s*$',
        formula,
        flags=re.MULTILINE,
    )
    if not match:
        raise WatchError("Homebrew formula did not contain the expected cloudflared tag URL")
    version = match.group(1)
    parse_version(version)
    return version


def installed_version(binary: str = CLOUDFLARED) -> str | None:
    """Return the locally installed version, or None when it cannot be read."""
    try:
        result = subprocess.run(
            [binary, "--version"], capture_output=True, text=True, check=False, timeout=15
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.search(r"cloudflared version (\d+(?:\.\d+)+)", result.stdout + result.stderr)
    return match.group(1) if match else None


def load_notified_version(path: Path) -> str | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise WatchError(f"cannot read notification state at {path}: {exc}") from None
    value = payload.get("notifiedVersion")
    return value if isinstance(value, str) else None


def write_notification_state(path: Path, *, version: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"formulaUrl": FORMULA_URL, "notifiedVersion": version, "targetVersion": TARGET_VERSION}
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


def notification(version: str) -> str:
    return "\n".join(
        [
            f"@bryan:snowboardtechie.com cloudflared {version} is now in Homebrew.",
            "",
            "Update and restart the tunnel daemon:",
            "brew update && brew upgrade cloudflared",
            "sudo launchctl kickstart -k system/com.cloudflare.cloudflared",
            "",
            "Verify: grep Version /Library/Logs/com.cloudflare.cloudflared.err.log | tail -1",
            f"Release: https://github.com/cloudflare/cloudflared/releases/tag/{version}",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--formula-file", type=Path, help="read a local formula fixture")
    parser.add_argument("--state-file", type=Path, default=STATE_FILE)
    parser.add_argument("--cloudflared", default=CLOUDFLARED)
    args = parser.parse_args()

    try:
        formula = (
            args.formula_file.read_text(encoding="utf-8")
            if args.formula_file is not None
            else fetch_formula()
        )
        version = formula_version(formula)
        target = parse_version(TARGET_VERSION)
        if parse_version(version) < target:
            return 0
        if load_notified_version(args.state_file) == version:
            return 0
        local = installed_version(args.cloudflared)
        if local is not None and parse_version(local) >= target:
            return 0
        write_notification_state(args.state_file, version=version)
        print(notification(version))
        return 0
    except (OSError, WatchError) as exc:
        print(f"cloudflared Homebrew watch failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
