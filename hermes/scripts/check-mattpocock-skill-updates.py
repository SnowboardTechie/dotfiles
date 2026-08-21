#!/usr/bin/env python3
"""Monitor source for the adapted upstream skills.

Emits a **stable** snapshot of the upstream files this repository actually
adapted. The Hermes scheduler hashes these exact bytes and suppresses the agent
run entirely when they are unchanged, so the output must be byte-identical
across runs that observe the same upstream *content*.

Two design decisions follow from that, and each one was a bug first:

* **Identity is per-file, not per-commit.** The snapshot carries each watched
  file's Git **blob sha** and no repository tip. An upstream commit that touches
  nothing we watch therefore produces identical output and stays silent. Keying
  on `main` made every unrelated push look like a change.
* **The assessment gets what it needs *here*.** The watcher runs with read-only
  tools, so it cannot open the local ledger. The bounded context it needs —
  which local skills each watched file feeds, what diverged locally, and which
  upstream rules were explicitly rejected — travels in this output. A blob URL
  pinned to the sha lets the agent fetch the exact bytes that were hashed.

Shas come from **one** recursive Git Trees request, not one Contents request per
watched file. That is not premature optimization: GitHub's unauthenticated limit
is 60 requests an hour *per IP*, shared with everything else on the host, and a
live run with 17 watched files exhausted it on the second invocation.

Everything else is in service of stability: every key and list is sorted, and
there is **no timestamp, no local path, no hostname, and no credential**
anywhere in the output.

Read-only. It fetches upstream content and prints. It never writes a file,
advances the pin, or touches the local checkout.

**Ledger discovery.** This script is installed as a *copy* (the scheduler
refuses a cron script whose symlink resolves outside `HERMES_HOME/scripts`), so
`__file__` says nothing about where the repository is. The ledger is located
from, in order: `--ledger`, the `MATTPOCOCK_SKILLS_LEDGER` environment variable,
then the cron job's **workdir** — which the scheduler sets as the process cwd
and which the tracked manifest pins to the dotfiles checkout.

Offline use:
    check-mattpocock-skill-updates.py --fixture-dir tests/fixtures/upstream
where the directory holds each watched file at its upstream-relative path. Blob
shas are computed from the fixture bytes exactly as Git would.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Iterable

UPSTREAM_REPO = "mattpocock/skills"
UPSTREAM_URL = f"https://github.com/{UPSTREAM_REPO}"
API_BASE = f"https://api.github.com/repos/{UPSTREAM_REPO}"
USER_AGENT = "dotfiles-mattpocock-skill-watch/2"
TIMEOUT_SECONDS = 30
MAX_BYTES = 1_048_576  # 1 MiB per file; upstream skills are a few KiB.

LEDGER_ENV = "MATTPOCOCK_SKILLS_LEDGER"
LEDGER_RELATIVE = Path("dot-agents") / "upstreams" / "mattpocock-skills.json"

# Kept short on purpose: an alert has to stay readable, and the agent can fetch
# the full ledger entry from Git if it needs more than the gist.
MAX_CONTEXT_ITEMS = 6


class MonitorError(RuntimeError):
    """Any condition that must exit non-zero rather than report no change."""


# --------------------------------------------------------------------------
# Ledger
# --------------------------------------------------------------------------


def default_ledger_path(
    environ: dict[str, str] | None = None, cwd: Path | None = None
) -> Path:
    """Locate the adaptation ledger without relying on `__file__`.

    The installed script is a copy, so its own location is inside
    `HERMES_HOME/scripts` and tells us nothing. The cron workdir does.
    """
    env = environ if environ is not None else dict(os.environ)
    override = (env.get(LEDGER_ENV) or "").strip()
    if override:
        return Path(override).expanduser()
    return (cwd if cwd is not None else Path.cwd()) / LEDGER_RELATIVE


def load_ledger(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise MonitorError(
            f"adaptation ledger not found at {path}. This script runs as an installed "
            f"copy, so it locates the ledger from the cron job's workdir or from "
            f"${LEDGER_ENV} — check that the job's workdir is the dotfiles checkout."
        ) from None
    except OSError as exc:
        raise MonitorError(f"cannot read the adaptation ledger at {path}: {exc}") from None
    except json.JSONDecodeError as exc:
        raise MonitorError(f"adaptation ledger is not valid JSON: {exc}") from None


def _trimmed(values: Iterable[str]) -> list[str]:
    """At most `MAX_CONTEXT_ITEMS` entries, sorted, with an honest tail marker."""
    items = sorted(str(value) for value in values)
    if len(items) <= MAX_CONTEXT_ITEMS:
        return items
    remaining = len(items) - MAX_CONTEXT_ITEMS
    return items[:MAX_CONTEXT_ITEMS] + [f"… and {remaining} more (see the ledger in Git)"]


def watched_context(ledger: dict) -> dict[str, list[dict]]:
    """Upstream path -> the adaptations it feeds, with their local divergence.

    This is the bounded context the assessment needs and cannot read for itself:
    which local skills a change would affect, what already diverges locally, and
    which upstream rules were rejected on purpose — because upstream restating a
    rejected rule is the same disagreement, not news.
    """
    context: dict[str, list[dict]] = {}
    for adaptation in ledger.get("adaptations", []):
        skill = adaptation.get("skill")
        declared = set(adaptation.get("upstreamPaths", []))
        entry = {
            "skill": skill,
            "localPaths": sorted(adaptation.get("localPaths", [])),
            "localChanges": _trimmed(adaptation.get("localChanges", [])),
            "rejectedUpstreamRules": _trimmed(adaptation.get("rejectedUpstreamRules", [])),
        }
        for path in adaptation.get("watchedFiles", []):
            if path not in declared:
                raise MonitorError(
                    f"{skill}: watched file {path!r} is not one of its declared "
                    "upstreamPaths; a watched file with no mapping cannot be assessed "
                    "for relevance"
                )
            context.setdefault(path, []).append(entry)
    if not context:
        raise MonitorError("adaptation ledger declares no watched files")
    return {
        path: sorted(entries, key=lambda item: item["skill"] or "")
        for path, entries in sorted(context.items())
    }


# --------------------------------------------------------------------------
# Upstream content
# --------------------------------------------------------------------------


def git_blob_sha(data: bytes) -> str:
    """The Git blob id of these exact bytes — content-addressed, commit-free."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()  # noqa: S324


def http_get(url: str, *, timeout: int = TIMEOUT_SECONDS) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310 — literal https base
            body = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise MonitorError(f"GET {url} failed: HTTP {exc.code}") from None
    except (OSError, urllib.error.URLError) as exc:
        raise MonitorError(f"GET {url} failed: {type(exc).__name__}") from None
    if len(body) > MAX_BYTES:
        raise MonitorError(f"GET {url} exceeded {MAX_BYTES} bytes")
    return body


class TreeFetcher:
    """Reads every watched file's blob sha from **one** Git Trees request.

    A per-file Contents call is the obvious implementation and the wrong one:
    it costs one request per watched path, and GitHub's unauthenticated limit is
    60 per hour *per IP* shared with everything else on the host. A live run
    with 17 watched files exhausted it on the second invocation. The recursive
    tree returns every path's blob sha in a single request, which is both the
    authoritative source for those shas and ~17× cheaper.

    A **truncated** tree is refused rather than used: GitHub truncates large
    trees, and a missing watched path would silently read as "unchanged".
    """

    def __init__(self, http: Callable[..., bytes] = http_get, ref: str = "main") -> None:
        self._http = http
        self.ref = ref
        self._blobs: dict[str, str] | None = None

    def _load(self) -> dict[str, str]:
        if self._blobs is not None:
            return self._blobs
        url = f"{API_BASE}/git/trees/{self.ref}?recursive=1"
        try:
            raw = self._http(url)
        except MonitorError:
            raise
        except (OSError, urllib.error.URLError) as exc:
            # Keep the error contract even if the transport raises directly: a
            # raw OSError would escape as a traceback instead of a clean
            # "monitor failed" line, and the scheduler needs the latter.
            raise MonitorError(f"tree fetch failed: {type(exc).__name__}") from None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise MonitorError(f"Trees API returned non-JSON: {exc}") from None
        if payload.get("truncated"):
            raise MonitorError(
                "the upstream tree came back truncated; a watched path could be "
                "missing and would read as unchanged"
            )
        entries = payload.get("tree")
        if not isinstance(entries, list) or not entries:
            raise MonitorError("Trees API returned no tree entries")
        blobs: dict[str, str] = {}
        for entry in entries:
            if entry.get("type") != "blob":
                continue
            path, sha = entry.get("path"), entry.get("sha")
            if isinstance(path, str) and isinstance(sha, str) and len(sha) == 40:
                blobs[path] = sha
        if not blobs:
            raise MonitorError("Trees API returned no blob entries")
        self._blobs = blobs
        return blobs

    def blob_sha(self, path: str) -> str:
        blobs = self._load()
        sha = blobs.get(path)
        if sha is None:
            raise MonitorError(
                f"watched path {path!r} is not in the upstream tree at {self.ref}; "
                "it was renamed or removed, so the adaptation ledger is stale"
            )
        return sha


class FixtureFetcher:
    """Offline fetcher backed by a directory, for tests and dry checks."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def blob_sha(self, path: str) -> str:
        candidate = self.root / path
        if not candidate.is_file():
            raise MonitorError(f"fixture missing for watched path: {path}")
        return git_blob_sha(candidate.read_bytes())


def blob_url(sha: str) -> str:
    """A content-pinned URL for exactly the bytes that were hashed."""
    return f"{API_BASE}/git/blobs/{sha}"


# --------------------------------------------------------------------------
# Snapshot
# --------------------------------------------------------------------------


def build_snapshot(ledger: dict, *, fetcher) -> dict:
    """The deterministic document the scheduler hashes."""
    watched = watched_context(ledger)
    files: dict[str, dict] = {}
    for path, adaptations in watched.items():
        sha = fetcher.blob_sha(path)
        files[path] = {
            "blobSha": sha,
            "blobUrl": blob_url(sha),
            "adaptations": adaptations,
        }
    return {
        "upstream": UPSTREAM_URL,
        "pinnedCommit": ledger.get("commit", ""),
        "pinnedVersion": ledger.get("version", ""),
        "watched": files,
    }


def render(snapshot: dict) -> str:
    """Sorted, indented JSON with a trailing newline. No timestamp, ever."""
    return json.dumps(snapshot, indent=2, sort_keys=True) + "\n"


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stable upstream snapshot for monitor mode.")
    parser.add_argument("--ledger", type=Path, help="path to the adaptation ledger")
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        help="serve upstream content from this directory instead of the network",
    )
    parser.add_argument(
        "--ref", default="main", help="upstream ref to read watched files at (default: main)"
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        ledger = load_ledger(args.ledger or default_ledger_path())
        fetcher = (
            FixtureFetcher(args.fixture_dir)
            if args.fixture_dir
            else TreeFetcher(ref=args.ref)
        )
        sys.stdout.write(render(build_snapshot(ledger, fetcher=fetcher)))
    except MonitorError as error:
        # Non-zero so the scheduler records an ERROR. A broken monitor must
        # alert, never quietly look like "nothing changed".
        print(f"monitor failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
