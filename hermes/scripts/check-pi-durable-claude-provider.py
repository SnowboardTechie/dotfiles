#!/usr/bin/env python3
"""Monitor source for an official Claude provider usable from Pi Durable.

Bryan's Durable Pi planner is built on Pi's application libraries (`pi-ai`,
`chord`, `pi-durable`), not the `pi-coding-agent` terminal app. The third-party
Claude packages on pi.dev are coding-agent extensions, so they do not count.
What we are waiting for is the Pi equivalent of Nous's official Hermes plugin:
an Earendil-shipped way to drive Claude Opus on a Claude subscription through
the official `claude` binary, from `pi-ai`.

This script emits a **stable** snapshot of official Earendil signals only. The
Hermes scheduler hashes the exact stdout and skips the agent run when it is
unchanged, so the output carries no versions, timestamps, hosts or paths:

* the published `@earendil-works/*` npm package names;
* the provider module names in `packages/ai/src/providers` of earendil-works/pi;
* every repository path under `packages/` whose name mentions Claude;
* changelog lines in the `ai`, `durable` and `chord` packages that mention
  Claude Code, the `claude` CLI or the Agent SDK.

The repository tree is one GitHub Trees request (unauthenticated limit: 60/hour
per IP); changelogs come from raw.githubusercontent.com. Any source failure
exits non-zero so the scheduler records an error instead of "no change".

Read-only. It fetches and prints; it never writes anything.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Iterable

REPO = "earendil-works/pi"
TREE_URL = f"https://api.github.com/repos/{REPO}/git/trees/main?recursive=1"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO}/main"
NPM_SEARCH_URL = "https://registry.npmjs.org/-/v1/search?" + urllib.parse.urlencode(
    {"text": "scope:earendil-works", "size": 250}
)
NPM_SCOPE = "@earendil-works/"
CHANGELOG_PACKAGES = ("ai", "chord", "durable")
USER_AGENT = "dotfiles-pi-durable-claude-provider-watch/1"
TIMEOUT_SECONDS = 30
MAX_BYTES = 8_388_608

PROVIDER_FILE = re.compile(r"packages/ai/src/providers/([^/]+)\.ts")
PROVIDER_HELPER = re.compile(r"\.(models|lazy|test)$|\.d$")
CLAUDE_PATH = re.compile(r"claude", re.IGNORECASE)
CHANGELOG_SIGNAL = re.compile(
    r"claude[ -]code|claude cli|`claude`|agent sdk|claude-agent-sdk", re.IGNORECASE
)


class MonitorError(RuntimeError):
    """Any condition that must exit non-zero rather than report no change."""


def http_get(url: str) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, text/plain"}
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # nosec B310 — literal https bases
            body = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise MonitorError(f"GET {url} failed: HTTP {exc.code}") from None
    except (OSError, urllib.error.URLError) as exc:
        raise MonitorError(f"GET {url} failed: {type(exc).__name__}") from None
    if len(body) > MAX_BYTES:
        raise MonitorError(f"GET {url} exceeded {MAX_BYTES} bytes")
    return body


def _json(raw: bytes, source: str) -> dict:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MonitorError(f"{source} returned non-JSON: {exc}") from None
    if not isinstance(payload, dict):
        raise MonitorError(f"{source} returned an unexpected document")
    return payload


def repository_paths(get: Callable[[str], bytes]) -> list[str]:
    payload = _json(get(TREE_URL), "GitHub Trees API")
    if payload.get("truncated"):
        raise MonitorError("the earendil-works/pi tree came back truncated; a new path could be missed")
    entries = payload.get("tree")
    if not isinstance(entries, list) or not entries:
        raise MonitorError("GitHub Trees API returned no entries")
    paths = [entry["path"] for entry in entries if isinstance(entry, dict) and isinstance(entry.get("path"), str)]
    if not any(path.startswith("packages/ai/") for path in paths):
        raise MonitorError("earendil-works/pi no longer has packages/ai; the watch needs review")
    return paths


def provider_modules(paths: Iterable[str]) -> list[str]:
    names = set()
    for path in paths:
        match = PROVIDER_FILE.fullmatch(path)
        if match and not PROVIDER_HELPER.search(match.group(1)):
            names.add(match.group(1))
    if "anthropic" not in names:
        raise MonitorError("pi-ai has no anthropic provider module; the watch needs review")
    return sorted(names)


def claude_paths(paths: Iterable[str]) -> list[str]:
    return sorted(
        path
        for path in paths
        if path.startswith("packages/") and CLAUDE_PATH.search(path.rsplit("/", 1)[-1])
    )


def changelog_mentions(get: Callable[[str], bytes]) -> dict[str, list[str]]:
    mentions: dict[str, list[str]] = {}
    for package in CHANGELOG_PACKAGES:
        text = get(f"{RAW_BASE}/packages/{package}/CHANGELOG.md").decode("utf-8", "replace")
        if "##" not in text:
            raise MonitorError(f"packages/{package}/CHANGELOG.md does not look like a changelog")
        lines = {line.strip() for line in text.splitlines() if CHANGELOG_SIGNAL.search(line)}
        mentions[package] = sorted(lines)
    return mentions


def earendil_packages(get: Callable[[str], bytes]) -> list[str]:
    payload = _json(get(NPM_SEARCH_URL), "npm search")
    objects = payload.get("objects")
    if not isinstance(objects, list):
        raise MonitorError("npm search returned no result list")
    names = sorted(
        {
            item["package"]["name"]
            for item in objects
            if isinstance(item, dict)
            and isinstance(item.get("package"), dict)
            and str(item["package"].get("name", "")).startswith(NPM_SCOPE)
        }
    )
    if f"{NPM_SCOPE}pi-ai" not in names or f"{NPM_SCOPE}pi-durable" not in names:
        raise MonitorError("npm search did not return the core @earendil-works packages")
    return names


def build_snapshot(get: Callable[[str], bytes] = http_get) -> dict:
    paths = repository_paths(get)
    return {
        "source": f"https://github.com/{REPO}",
        "earendilNpmPackages": earendil_packages(get),
        "piAiProviderModules": provider_modules(paths),
        "claudeNamedPaths": claude_paths(paths),
        "changelogMentions": changelog_mentions(get),
    }


def render(snapshot: dict) -> str:
    """Sorted, indented JSON with a trailing newline. No timestamp, ever."""
    return json.dumps(snapshot, indent=2, sort_keys=True) + "\n"


def main() -> int:
    try:
        sys.stdout.write(render(build_snapshot()))
    except MonitorError as error:
        print(f"monitor failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
