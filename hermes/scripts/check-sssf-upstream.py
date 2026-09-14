#!/usr/bin/env python3
"""Weekly read-only facts about Super Simple Software Factory upstream drift.

Collects the bounded evidence the weekly SGG report needs to answer one
question: *has `disler/super-simple-software-factory` moved past the commit the
SGG ledger says was reviewed, and should Bryan consider updating?* It answers
nothing itself. It never fetches, clones, writes, advances a pin, or touches a
local checkout — the only local read is the ledger.

Unlike `check-mattpocock-skill-updates.py`, this is a plain cron **`script`**,
not a `monitorScript`. That single difference drives two decisions that would
otherwise look like bugs:

* **No-change is output, not silence.** A `monitorScript` is hashed and the run
  is suppressed when the bytes repeat; Bryan asked for a weekly report that
  *includes* an explicit no-change week, so unchanged upstream is a reported
  state (`"status": "unchanged"`) and the agent always runs.
* **A reachability failure exits zero.** A monitor that fails must exit
  non-zero, because its silence would otherwise read as "nothing changed".
  Here nothing is suppressed, so a GitHub outage or rate limit is reported —
  `"status": "unreachable"` plus an entry in `incomplete` — and the weekly
  report says `assessment blocked` instead of vanishing. A *ledger* fault is
  different: there is then no coherent document to report at all, so that still
  exits non-zero and the scheduler records an error.

Identity is per-commit here, not the Pocock watcher's per-file blob sha. The
question is whether upstream advanced past the reviewed SHA, so the compare
range between them *is* the subject. GitHub's compare `status` distinguishes
the four cases that matter — `identical`, `ahead`, `behind`, and `diverged` —
and `diverged` is the force-push / non-descendant condition that must block an
assessment rather than look like ordinary progress.

Request budget is eight per run, all `GET`:

    upstream: repo metadata, default-branch head, compare range, tags,
              one recursive tree at the current head
    fork:     repo metadata, default-branch head
    relation: one cross-repo compare (upstream base ... fork head)

The recursive tree is one request for every changed path's blob sha, not one
`Contents` request per file — GitHub's unauthenticated limit is 60 per hour per
IP shared with everything else on the host, and a per-file loop over a wide
upstream commit would exhaust it. A path missing from that tree is a deletion,
which is how removed and renamed files are reported honestly rather than as a
dangling blob URL.

Output is deterministic: every key and list sorted, no timestamp, no hostname,
no credential, no environment dump, and no raw private file content. The only
local strings that appear are the SGG adaptation paths the ledger itself
publishes, which the assessor needs in order to name affected surfaces and
cannot read for itself (the job runs without file tools).

**Ledger discovery.** This installs as a *copy* — the scheduler refuses a cron
script whose symlink resolves outside `HERMES_HOME/scripts` — so `__file__`
says nothing about where the SGG workspace is. The ledger is located from, in
order: `--ledger`, `$SSSF_UPSTREAM_LEDGER`, then the cron job's **workdir**,
which the scheduler sets as the process cwd and the tracked manifest pins to
`/Users/bryan/code/sgg`.

Offline use:
    check-sssf-upstream.py --ledger L.json --fixture responses.json
where `responses.json` maps each request URL to its JSON body, or to
`{"__error__": "HTTP 403"}` to replay a failure.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable

API_ROOT = "https://api.github.com"
GITHUB_HOST = "github.com"
USER_AGENT = "dotfiles-sssf-upstream-watch/1"
TIMEOUT_SECONDS = 30
MAX_BYTES = 4_194_304  # 4 MiB; a recursive tree of this repository is far smaller.

LEDGER_ENV = "SSSF_UPSTREAM_LEDGER"
LEDGER_RELATIVE = Path("factory") / "upstream.json"

# Bounds. This is a Matrix alert, not a changelog: an unbounded commit list
# would blow past what is readable and past what the assessor should weigh.
MAX_COMMITS = 20
MAX_PATHS = 40
MAX_TAGS = 10
MAX_DIVERGENCES = 20


# GitHub's own caps on a compare response. Hitting either means the range is
# wider than the API will describe, which is an incompleteness, not a change.
COMPARE_FILE_CAP = 300

SHA_RE = re.compile(r"\A[0-9a-f]{40}\Z")
REPO_RE = re.compile(r"\A[A-Za-z0-9._-]+/[A-Za-z0-9._-]+\Z")
BRANCH_RE = re.compile(r"\A[A-Za-z0-9._/-]{1,100}\Z")


class LedgerError(RuntimeError):
    """A fault in local tracked state. Exits non-zero: nothing to report."""


class FetchError(RuntimeError):
    """A remote fault. Reported in the document; never fails the run."""


# --------------------------------------------------------------------------
# Ledger
# --------------------------------------------------------------------------


def default_ledger_path(
    environ: dict[str, str] | None = None, cwd: Path | None = None
) -> Path:
    """Locate the SGG ledger without relying on `__file__`.

    The installed script is a copy living in `HERMES_HOME/scripts`, so its own
    location says nothing about the SGG workspace. The cron workdir does.
    """
    env = environ if environ is not None else dict(os.environ)
    override = (env.get(LEDGER_ENV) or "").strip()
    if override:
        return Path(override).expanduser()
    return (cwd if cwd is not None else Path.cwd()) / LEDGER_RELATIVE


def load_ledger(path: Path) -> dict:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise LedgerError(
            f"SGG factory ledger not found at {path}. This script runs as an installed "
            f"copy, so it locates the ledger from the cron job's workdir or from "
            f"${LEDGER_ENV} — check that the job's workdir is the SGG workspace."
        ) from None
    except OSError as exc:
        raise LedgerError(f"cannot read the SGG factory ledger at {path}: {exc}") from None
    try:
        ledger = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LedgerError(f"SGG factory ledger is not valid JSON: {exc}") from None
    if not isinstance(ledger, dict):
        raise LedgerError("SGG factory ledger must be a JSON object")
    return ledger


def repo_slug(url: object, *, field: str) -> str:
    """`https://github.com/owner/name` -> `owner/name`, host-validated.

    A ledger that names some other host would otherwise send credentials-free
    but still unwanted requests wherever it pointed.
    """
    if not isinstance(url, str) or not url.strip():
        raise LedgerError(f"ledger {field} is missing")
    text = url.strip().removesuffix(".git").rstrip("/")
    prefix = f"https://{GITHUB_HOST}/"
    if not text.startswith(prefix):
        raise LedgerError(f"ledger {field} must be an https://{GITHUB_HOST}/ URL, got {url!r}")
    slug = text[len(prefix) :]
    if not REPO_RE.fullmatch(slug):
        raise LedgerError(f"ledger {field} is not an owner/repository pair: {url!r}")
    return slug


def _sha(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value.strip()):
        raise LedgerError(f"ledger {field} must be a 40-character lowercase hex sha")
    return value.strip()


def _branch(value: object, *, field: str, default: str = "main") -> str:
    if value is None:
        return default
    if not isinstance(value, str) or not BRANCH_RE.fullmatch(value.strip()):
        raise LedgerError(f"ledger {field} is not a valid branch name")
    return value.strip()


def _trimmed(values: object, limit: int) -> list[str]:
    """Sorted, bounded, with an honest tail marker rather than a quiet cut."""
    if not isinstance(values, list):
        return []
    items = sorted(str(value) for value in values)
    if len(items) <= limit:
        return items
    return items[:limit] + [f"… and {len(items) - limit} more (see the ledger in Git)"]


def read_ledger_facts(ledger: dict) -> dict:
    """The validated subset the collector and the assessor both depend on."""
    upstream = ledger.get("upstream")
    engine = ledger.get("engine")
    if not isinstance(upstream, dict) or not isinstance(engine, dict):
        raise LedgerError("SGG factory ledger needs both 'upstream' and 'engine' objects")
    policy = ledger.get("update_policy")
    paths = ledger.get("sgg_local_paths")
    divergences = ledger.get("divergences")
    if not isinstance(policy, dict):
        raise LedgerError("SGG factory ledger needs an 'update_policy' object")
    if not isinstance(paths, dict) or not paths:
        raise LedgerError("SGG factory ledger needs a non-empty 'sgg_local_paths' object")
    if not isinstance(divergences, list):
        raise LedgerError("SGG factory ledger needs a 'divergences' list")
    if not isinstance(policy.get("detect"), str) or not policy["detect"].strip():
        raise LedgerError("ledger update_policy.detect must be a non-empty string")
    if not isinstance(policy.get("apply"), str) or not policy["apply"].strip():
        raise LedgerError("ledger update_policy.apply must be a non-empty string")
    if not isinstance(policy.get("autoApply"), bool):
        raise LedgerError("ledger update_policy.autoApply must be a boolean")
    if any(not isinstance(value, str) or not value.strip()
           for value in divergences):
        raise LedgerError("ledger divergences entries must be non-empty strings")
    if any(not isinstance(key, str) or not key.strip()
           or not isinstance(value, str) or not value.strip()
           or Path(value).is_absolute() or ".." in Path(value).parts
           for key, value in paths.items()):
        raise LedgerError("ledger sgg_local_paths must contain relative, non-empty paths")
    return {
        "upstreamRepo": repo_slug(upstream.get("repository"), field="upstream.repository"),
        "upstreamBranch": _branch(
            upstream.get("default_branch"), field="upstream.default_branch"
        ),
        "reviewedSha": _sha(upstream.get("reviewed_sha"), field="upstream.reviewed_sha"),
        "forkRepo": repo_slug(engine.get("repository"), field="engine.repository"),
        "forkBranch": _branch(engine.get("default_branch"), field="engine.default_branch"),
        "pinnedSha": _sha(engine.get("pinned_sha"), field="engine.pinned_sha"),
        "divergences": _trimmed(divergences, MAX_DIVERGENCES),
        "sggLocalPaths": {
            str(key): str(value) for key, value in sorted(paths.items())
        },
        "updatePolicy": {
            "detect": policy["detect"].strip(),
            "apply": policy["apply"].strip(),
            "autoApply": policy["autoApply"],
        },
    }


# --------------------------------------------------------------------------
# Transport
# --------------------------------------------------------------------------


class HttpClient:
    """Bounded read-only GitHub JSON reads. Never authenticates."""

    def __init__(self, *, timeout: int = TIMEOUT_SECONDS) -> None:
        self.timeout = timeout

    def get(self, url: str) -> object:
        if not url.startswith(f"{API_ROOT}/"):
            raise FetchError(f"refusing a request outside {API_ROOT}")
        request = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # nosec B310 — literal https base
                body = response.read(MAX_BYTES + 1)
        except urllib.error.HTTPError as exc:
            raise FetchError(f"HTTP {exc.code}") from None
        except (OSError, urllib.error.URLError, http.client.HTTPException) as exc:
            raise FetchError(type(exc).__name__) from None
        if len(body) > MAX_BYTES:
            raise FetchError(f"response exceeded {MAX_BYTES} bytes")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            raise FetchError("response was not JSON") from None


class FixtureClient:
    """Replays a recorded URL -> body map, for tests and offline dry runs.

    A body of `{"__error__": "HTTP 403"}` replays that failure, which is how the
    rate-limit and outage paths are exercised without a network.
    """

    def __init__(self, responses: dict[str, object]) -> None:
        self.responses = responses
        self.requested: list[str] = []

    def get(self, url: str) -> object:
        self.requested.append(url)
        if url not in self.responses:
            raise FetchError("HTTP 404")
        payload = self.responses[url]
        if isinstance(payload, dict) and "__error__" in payload:
            raise FetchError(str(payload["__error__"]))
        return payload


def load_fixture(path: Path) -> FixtureClient:
    try:
        responses = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LedgerError(f"cannot read the response fixture at {path}: {exc}") from None
    if not isinstance(responses, dict):
        raise LedgerError("a response fixture must be a JSON object of url -> body")
    return FixtureClient(responses)


# --------------------------------------------------------------------------
# Collection
# --------------------------------------------------------------------------


def commit_url(repo: str, sha: str) -> str:
    """A content-pinned commit URL — the exact commit, not a moving branch."""
    return f"https://{GITHUB_HOST}/{repo}/commit/{sha}"


def blob_url(repo: str, sha: str, path: str) -> str:
    """A content-pinned blob URL for exactly the bytes whose sha is reported."""
    return f"https://{GITHUB_HOST}/{repo}/blob/{sha}/{path}"


def head_sha(client, repo: str, branch: str) -> str:
    payload = client.get(f"{API_ROOT}/repos/{repo}/commits/{branch}")
    if not isinstance(payload, dict):
        raise FetchError("commit response was not an object")
    sha = payload.get("sha")
    if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
        raise FetchError("commit response carried no usable sha")
    return sha


def repo_metadata(client, repo: str) -> dict:
    payload = client.get(f"{API_ROOT}/repos/{repo}")
    if not isinstance(payload, dict) or not isinstance(payload.get("full_name"), str):
        raise FetchError("repository response was not an object")
    if payload["full_name"].lower() != repo.lower():
        # A rename or a redirect to some other repository. Reading it as the
        # expected one would silently assess the wrong source.
        raise FetchError(
            f"repository identity mismatch: asked for {repo}, got {payload['full_name']}"
        )
    return {
        "defaultBranch": str(payload.get("default_branch") or ""),
        "archived": bool(payload.get("archived", False)),
        "fork": bool(payload.get("fork", False)),
        "parent": str((payload.get("parent") or {}).get("full_name") or ""),
    }


def tree_blobs(client, repo: str, sha: str) -> tuple[dict[str, str], bool]:
    """Every blob sha at one commit from one recursive request.

    Truncation is reported rather than refused: a missing entry would otherwise
    read as a deleted file, and the difference matters to the assessor.
    """
    payload = client.get(f"{API_ROOT}/repos/{repo}/git/trees/{sha}?recursive=1")
    if not isinstance(payload, dict):
        raise FetchError("tree response was not an object")
    entries = payload.get("tree")
    if not isinstance(entries, list):
        raise FetchError("tree response carried no entries")
    blobs = {
        entry["path"]: entry["sha"]
        for entry in entries
        if isinstance(entry, dict)
        and entry.get("type") == "blob"
        and isinstance(entry.get("path"), str)
        and isinstance(entry.get("sha"), str)
        and SHA_RE.fullmatch(entry["sha"])
    }
    return blobs, bool(payload.get("truncated"))


def compare(client, repo: str, base: str, head: str) -> dict:
    payload = client.get(f"{API_ROOT}/repos/{repo}/compare/{base}...{head}")
    if not isinstance(payload, dict):
        raise FetchError("compare response was not an object")
    status = payload.get("status")
    if status not in {"identical", "ahead", "behind", "diverged"}:
        raise FetchError(f"compare response carried no usable status: {status!r}")
    return payload


def tag_names(client, repo: str) -> tuple[list[str], dict[str, list[str]]]:
    """Tag names, plus a sha -> tags index for the two shas that matter."""
    payload = client.get(f"{API_ROOT}/repos/{repo}/tags")
    if not isinstance(payload, list):
        raise FetchError("tags response was not a list")
    by_sha: dict[str, list[str]] = {}
    names: list[str] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        sha = (entry.get("commit") or {}).get("sha")
        if isinstance(name, str):
            names.append(name)
            if isinstance(sha, str) and SHA_RE.fullmatch(sha):
                by_sha.setdefault(sha, []).append(name)
    return sorted(names), {sha: sorted(tags) for sha, tags in by_sha.items()}


UPSTREAM_STATUS = {
    "identical": "unchanged",
    "ahead": "advanced",
    "behind": "rewound",
    "diverged": "diverged",
}


def collect_upstream(client, facts: dict, incomplete: list[str]) -> dict:
    """Upstream facts, degrading every remote fault into a reported state."""
    repo = facts["upstreamRepo"]
    result: dict = {
        "repository": repo,
        "defaultBranch": facts["upstreamBranch"],
        "reviewedSha": facts["reviewedSha"],
        "reviewedShaUrl": commit_url(repo, facts["reviewedSha"]),
        "currentSha": None,
        "status": "unreachable",
        "aheadBy": None,
        "behindBy": None,
        "commits": [],
        "commitsTruncated": False,
        "totalCommits": None,
        "changedPaths": [],
        "changedPathsTruncated": False,
        "tags": [],
        "reviewedShaTags": [],
        "currentShaTags": [],
        "archived": None,
    }

    try:
        metadata = repo_metadata(client, repo)
    except FetchError as exc:
        reason = str(exc)
        result["status"] = "missing" if reason == "HTTP 404" else "unreachable"
        incomplete.append(f"upstream repository metadata unavailable: {reason}")
        return result
    result["archived"] = metadata["archived"]
    if metadata["defaultBranch"] and metadata["defaultBranch"] != facts["upstreamBranch"]:
        # Not fatal, but the ledger is then describing a branch upstream no
        # longer treats as canonical, and that changes what "current" means.
        incomplete.append(
            f"upstream default branch is {metadata['defaultBranch']!r}, "
            f"ledger records {facts['upstreamBranch']!r}"
        )

    try:
        current = head_sha(client, repo, facts["upstreamBranch"])
    except FetchError as exc:
        incomplete.append(f"upstream head unavailable: {exc}")
        return result
    result["currentSha"] = current
    result["currentShaUrl"] = commit_url(repo, current)

    try:
        comparison = compare(client, repo, facts["reviewedSha"], current)
    except FetchError as exc:
        incomplete.append(f"upstream compare unavailable: {exc}")
        return result

    result["status"] = UPSTREAM_STATUS[comparison["status"]]
    result["aheadBy"] = comparison.get("ahead_by")
    result["behindBy"] = comparison.get("behind_by")

    commits = [entry for entry in (comparison.get("commits") or []) if isinstance(entry, dict)]
    total = comparison.get("total_commits")
    result["totalCommits"] = total if isinstance(total, int) else len(commits)
    if isinstance(total, int) and total > len(commits):
        result["commitsTruncated"] = True
        incomplete.append(
            f"GitHub returned {len(commits)} of {total} commits in the compare range"
        )
    listed = commits[:MAX_COMMITS]
    if len(commits) > MAX_COMMITS:
        result["commitsTruncated"] = True
        incomplete.append(
            f"commit list bounded to {MAX_COMMITS} of {len(commits)} returned commits"
        )
    result["commits"] = [
        {
            "sha": entry.get("sha", ""),
            "url": commit_url(repo, str(entry.get("sha", ""))),
        }
        for entry in listed
        if isinstance(entry.get("sha"), str) and SHA_RE.fullmatch(entry["sha"])
    ]

    files = [entry for entry in (comparison.get("files") or []) if isinstance(entry, dict)]
    if len(files) >= COMPARE_FILE_CAP:
        result["changedPathsTruncated"] = True
        incomplete.append(
            f"GitHub caps a compare at {COMPARE_FILE_CAP} files; the changed-path "
            "inventory is incomplete"
        )

    blobs: dict[str, str] = {}
    if files:
        try:
            blobs, truncated = tree_blobs(client, repo, current)
            if truncated:
                result["changedPathsTruncated"] = True
                incomplete.append(
                    "the upstream tree came back truncated; a changed path may be "
                    "reported as deleted when it still exists"
                )
        except FetchError as exc:
            result["changedPathsTruncated"] = True
            incomplete.append(f"upstream tree unavailable, no blob pins: {exc}")

    entries = []
    for entry in files[:MAX_PATHS]:
        path = entry.get("filename")
        if not isinstance(path, str) or not path:
            continue
        blob = blobs.get(path)
        entries.append(
            {
                "path": path,
                "status": str(entry.get("status") or "unknown"),
                "previousPath": entry.get("previous_filename") or None,
                "blobSha": blob,
                # No pin for a path that is gone at head; saying so beats a URL
                # that 404s when the assessor tries to read it.
                "blobUrl": blob_url(repo, current, path) if blob else None,
            }
        )
    if len(files) > MAX_PATHS:
        result["changedPathsTruncated"] = True
        incomplete.append(
            f"changed-path inventory bounded to {MAX_PATHS} of {len(files)} paths"
        )
    result["changedPaths"] = sorted(entries, key=lambda item: item["path"])

    try:
        names, by_sha = tag_names(client, repo)
        result["tags"] = names[:MAX_TAGS]
        if len(names) > MAX_TAGS:
            incomplete.append(f"tag list bounded to {MAX_TAGS} of {len(names)} tags")
        result["reviewedShaTags"] = by_sha.get(facts["reviewedSha"], [])
        result["currentShaTags"] = by_sha.get(current, [])
    except FetchError as exc:
        incomplete.append(f"upstream tags unavailable: {exc}")

    return result


def collect_fork(client, facts: dict, upstream: dict, incomplete: list[str]) -> dict:
    """Fork facts plus its relation to upstream, both degrading on fault."""
    repo = facts["forkRepo"]
    result: dict = {
        "repository": repo,
        "defaultBranch": facts["forkBranch"],
        "pinnedSha": facts["pinnedSha"],
        "pinnedShaUrl": commit_url(repo, facts["pinnedSha"]),
        "currentSha": None,
        "status": "unreachable",
        "isFork": None,
        "parent": None,
        "pinnedShaIsForkHead": None,
        "comparedToUpstream": {"status": "unavailable", "aheadBy": None, "behindBy": None},
    }

    try:
        metadata = repo_metadata(client, repo)
    except FetchError as exc:
        reason = str(exc)
        result["status"] = "missing" if reason == "HTTP 404" else "unreachable"
        incomplete.append(f"fork repository metadata unavailable: {reason}")
        return result
    result["isFork"] = metadata["fork"]
    result["parent"] = metadata["parent"] or None
    if metadata["parent"] and metadata["parent"] != facts["upstreamRepo"]:
        incomplete.append(
            f"fork parent is {metadata['parent']}, ledger records upstream "
            f"{facts['upstreamRepo']}"
        )

    try:
        current = head_sha(client, repo, facts["forkBranch"])
    except FetchError as exc:
        incomplete.append(f"fork head unavailable: {exc}")
        return result
    result["currentSha"] = current
    result["currentShaUrl"] = commit_url(repo, current)
    result["status"] = "present"
    result["pinnedShaIsForkHead"] = current == facts["pinnedSha"]
    # A pin may intentionally name a reviewed feature-branch commit while the
    # fork's default branch stays at upstream. Keep the difference explicit,
    # but do not call it incomplete: it does not prevent an upstream assessment.

    # One cross-repo compare, from the upstream side of the fork network.
    upstream_owner = facts["upstreamRepo"].split("/")[0]
    fork_owner = facts["forkRepo"].split("/")[0]
    try:
        comparison = compare(
            client,
            facts["upstreamRepo"],
            f"{upstream_owner}:{facts['upstreamBranch']}",
            f"{fork_owner}:{facts['forkBranch']}",
        )
        result["comparedToUpstream"] = {
            "status": comparison["status"],
            "aheadBy": comparison.get("ahead_by"),
            "behindBy": comparison.get("behind_by"),
        }
    except FetchError as exc:
        incomplete.append(f"fork-to-upstream comparison unavailable: {exc}")

    if upstream["status"] == "unreachable":
        incomplete.append("fork position relative to upstream could not be established")
    return result


def collect(ledger: dict, *, client) -> dict:
    """The deterministic document the weekly assessment reads."""
    facts = read_ledger_facts(ledger)
    incomplete: list[str] = []
    upstream = collect_upstream(client, facts, incomplete)
    fork = collect_fork(client, facts, upstream, incomplete)
    return {
        "collector": "sssf-upstream-watch",
        "schemaVersion": 1,
        "ledger": {
            "divergences": facts["divergences"],
            "sggLocalPaths": facts["sggLocalPaths"],
            "updatePolicy": facts["updatePolicy"],
        },
        "upstream": upstream,
        "fork": fork,
        "incomplete": sorted(set(incomplete)),
    }


def render(snapshot: dict) -> str:
    """Sorted, indented JSON with a trailing newline. No timestamp, ever."""
    return json.dumps(snapshot, indent=2, sort_keys=True) + "\n"


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bounded read-only upstream facts for the weekly SSSF report."
    )
    parser.add_argument("--ledger", type=Path, help="path to factory/upstream.json")
    parser.add_argument(
        "--fixture",
        type=Path,
        help="replay recorded GitHub responses from this url->body JSON file",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        ledger = load_ledger(args.ledger or default_ledger_path())
        client = load_fixture(args.fixture) if args.fixture else HttpClient()
        sys.stdout.write(render(collect(ledger, client=client)))
    except LedgerError as error:
        # Non-zero: local tracked state is broken, so there is no honest weekly
        # document to emit at all. A *remote* fault never reaches here — it is
        # reported inside the document so the weekly report still arrives.
        print(f"collector failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
