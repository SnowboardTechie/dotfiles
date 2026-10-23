"""Shared, read-only collection for the nightly YunoHost update report.

Two cron entry points use this module, and both are installed as copies next to
it in ``HERMES_HOME/scripts`` (the scheduler refuses symlinked cron scripts):

* ``check-yunohost-updates.py`` is the job's **monitor**. It prints a stable
  snapshot of what is pending: no timestamps, no release-note text, sorted keys.
  The scheduler hashes those bytes and skips the whole agent run when they are
  unchanged, so a held upgrade is reported once rather than every night.
* ``collect-yunohost-updates.py`` is the job's **script**. It runs only after
  the monitor wakes the agent, and adds bounded release-note excerpts for each
  pending app so the assessor can work with zero tools.

The only server access is one SSH call as the non-admin ``agent`` account,
running the exact sudo command its sudoers rule allows. Nothing here upgrades,
writes to the server, or holds a credential beyond the SSH key on disk.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tomllib
import urllib.parse
import urllib.request
from typing import Any, Callable

SSH_KEY = os.path.expanduser(os.environ.get("YUNOHOST_AGENT_KEY", "~/.ssh/yunohost-agent"))
SSH_HOST = os.environ.get("YUNOHOST_HOST", "snowboardtechie.com")
SSH_PORT = os.environ.get("YUNOHOST_PORT", "5518")
SSH_HOST_KEY_ALIAS = "[git.snowboardtechie.com]:5518"
# Must match the sudoers rule byte for byte; any other argument list is refused
# and the refusal emails Bryan.
UPDATE_COMMAND = "sudo -n /usr/bin/yunohost tools update --output-as json"

USER_AGENT = "hermes-yunohost-update-report"
EXCERPT_LIMIT = 4000
APP_LIMIT = 12000
ISSUE_LIMIT = 8
PRIORITY = re.compile(
    r"breaking|security|important|attention|deprecat|remov|migrat|upgrad|config|"
    r"warning|⚠|caution|require",
    re.IGNORECASE,
)


class SourceError(RuntimeError):
    """The server itself could not be read; the run must fail, not look quiet."""


def ssh_command(remote: str) -> list[str]:
    return [
        "ssh", "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
        "-o", "ConnectTimeout=20", "-o", f"HostKeyAlias={SSH_HOST_KEY_ALIAS}",
        "-i", SSH_KEY, "-p", SSH_PORT, f"agent@{SSH_HOST}", remote,
    ]


def fetch_pending(run: Callable[..., Any] = subprocess.run) -> dict:
    result = run(ssh_command(UPDATE_COMMAND), capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()[-1:] or ["no output"]
        raise SourceError(f"yunohost tools update failed over SSH: {detail[0][:300]}")
    text = result.stdout
    start = text.find("{")
    if start < 0:
        raise SourceError("yunohost tools update returned no JSON")
    try:
        return json.loads(text[start:])
    except json.JSONDecodeError as exc:
        raise SourceError(f"yunohost tools update returned invalid JSON: {exc}") from exc


def upstream_version(version: str) -> str:
    return (version or "").split("~", 1)[0]


def system_packages(raw: Any) -> list[tuple[str | None, dict]]:
    """Flatten ``tools update``'s ``system`` field into (category, package) pairs.

    With no apt upgrades YunoHost returns ``[]``; with upgrades it returns a dict
    of category -> package list (e.g. ``{"misc utils and libs": [...]}``). Accept
    both, plus a flat list of packages. Any other shape raises SourceError so the
    run fails visibly instead of reporting a quiet night.
    """
    pairs: list[tuple[str | None, dict]]
    if isinstance(raw, dict):
        pairs = [(str(category), package)
                 for category, packages in raw.items()
                 for package in (packages or [])]
    elif isinstance(raw, list) or raw is None:
        pairs = [(None, package) for package in raw or []]
    else:
        raise SourceError(f"unexpected 'system' field type: {type(raw).__name__}")
    for _, package in pairs:
        if not isinstance(package, dict):
            raise SourceError(f"unexpected system package entry: {str(package)[:120]}")
    return pairs


def snapshot(pending: dict) -> dict:
    """Stable identity of what is pending. Excludes every time-varying field."""
    apps = []
    for app in pending.get("apps") or []:
        upgrade = app.get("upgrade") or {}
        apps.append({
            "id": app.get("id"),
            "name": app.get("name"),
            "domainPath": app.get("domain_path"),
            "currentVersion": upgrade.get("current_version") or app.get("version"),
            "newVersion": upgrade.get("new_version"),
            "newRevision": upgrade.get("new_revision"),
            "packageUrl": upgrade.get("url"),
            "notifications": upgrade.get("notifications") or {},
            "requirements": upgrade.get("requirements") or {},
        })
    system = []
    for category, package in system_packages(pending.get("system")):
        entry = {
            "name": package.get("name"),
            "currentVersion": package.get("current_version"),
            "newVersion": package.get("new_version"),
        }
        if category is not None:
            entry["category"] = category
        system.append(entry)
    migrations = []
    for migration in pending.get("pending_migrations") or []:
        migrations.append(migration.get("id") if isinstance(migration, dict) else str(migration))
    return {
        "apps": sorted(apps, key=lambda a: str(a["id"])),
        "system": sorted(system, key=lambda p: str(p["name"])),
        "importantYunohostUpgrade": bool(pending.get("important_yunohost_upgrade")),
        "pendingMigrations": sorted(migrations),
    }


def render(data: dict) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------- versions


def version_key(text: str) -> tuple[int, ...] | None:
    """Numeric key for a release tag or package version, or None if unparseable.

    Handles ``v1.163.0``, ``17.0.0``, ``0.22.1`` and the date styles Phanpy
    uses: package ``20261009`` and tag ``2026.10.09.febb38d``.
    """
    text = (text or "").strip().lstrip("vV")
    if re.fullmatch(r"\d{8}", text):
        return (int(text[:4]), int(text[4:6]), int(text[6:8]))
    parts = []
    for piece in re.split(r"[.\-+_]", text):
        if not piece.isdigit():
            break
        parts.append(int(piece))
    return tuple(parts) or None


def is_prerelease(tag: str, flagged: bool) -> bool:
    return flagged or bool(re.search(r"(rc|alpha|beta|pre|dev)\d*", tag, re.IGNORECASE))


def releases_in_range(releases: list[dict], current: str, new: str) -> list[dict]:
    low, high = version_key(current), version_key(new)
    if low is None or high is None:
        return []
    chosen = []
    for release in releases:
        tag = release.get("tag") or ""
        key = version_key(tag)
        if key is None or is_prerelease(tag, release.get("prerelease", False)):
            continue
        # Date tags carry an extra hash component; compare on the shared prefix.
        width = min(len(key), max(len(low), len(high)))
        key = key[:width]
        if low[:width] < key <= high[:width]:
            chosen.append(release)
    return sorted(chosen, key=lambda r: version_key(r["tag"]) or ())


# ---------------------------------------------------------------- text shaping


def clean(text: str) -> str:
    text = re.sub(r"<!--.*?-->", "", text or "", flags=re.DOTALL)
    text = text.replace("\r", "")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def excerpt(text: str, limit: int = EXCERPT_LIMIT) -> str:
    """Bounded excerpt that keeps the opening banner and priority sections."""
    text = clean(text)
    if len(text) <= limit:
        return text
    sections: list[list[str]] = [[]]
    for line in text.splitlines():
        heading = line.startswith("#") or re.match(r"^- \S", line)
        if heading and sections[-1]:
            sections.append([])
        sections[-1].append(line)
    blocks = ["\n".join(s) for s in sections if s]
    kept = [blocks[0][:800]]
    used = len(kept[0])
    for block in blocks[1:]:
        if PRIORITY.search(block.splitlines()[0]):
            room = limit - used
            if room <= 200:
                break
            kept.append(block[:room])
            used += len(kept[-1])
    kept.append(f"[truncated: {len(text)} chars total; showing opening and "
                "breaking/security/upgrade sections]")
    return "\n\n".join(kept)


# ---------------------------------------------------------------- network


def http_get(url: str, accept: str = "application/json") -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "replace")


def forge_repo(url: str) -> tuple[str, str, str] | None:
    parsed = urllib.parse.urlparse(url or "")
    parts = [p for p in parsed.path.split("/") if p]
    if parsed.scheme != "https" or len(parts) < 2:
        return None
    host = parsed.hostname or ""
    repo = parts[1].removesuffix(".git")
    if host == "github.com":
        return ("github", parts[0], repo)
    if host in {"codeberg.org"}:
        return ("gitea:" + host, parts[0], repo)
    return None


def list_releases(forge: tuple[str, str, str], get: Callable[[str], str] = http_get) -> list[dict]:
    kind, owner, repo = forge
    if kind == "github":
        raw = json.loads(get(f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=60"))
        return [{"tag": r.get("tag_name") or "", "date": (r.get("published_at") or "")[:10],
                 "prerelease": bool(r.get("prerelease")), "body": r.get("body") or "",
                 "url": r.get("html_url") or ""} for r in raw]
    host = kind.split(":", 1)[1]
    raw = json.loads(get(f"https://{host}/api/v1/repos/{owner}/{repo}/releases?limit=50"))
    return [{"tag": r.get("tag_name") or "", "date": (r.get("published_at") or "")[:10],
             "prerelease": bool(r.get("prerelease")), "body": r.get("body") or "",
             "url": r.get("html_url") or ""} for r in raw]


def package_upstream(package_url: str, revision: str, get: Callable[[str], str] = http_get) -> str | None:
    forge = forge_repo(package_url)
    if not forge or forge[0] != "github" or not re.fullmatch(r"[0-9a-f]{7,40}", revision or ""):
        return None
    manifest = tomllib.loads(get(
        f"https://raw.githubusercontent.com/{forge[1]}/{forge[2]}/{revision}/manifest.toml"))
    upstream = manifest.get("upstream") or {}
    return upstream.get("code")


def expand_linked_notes(release: dict, forge: tuple[str, str, str],
                        get: Callable[[str], str] = http_get) -> str:
    """Some projects publish only a link in the release body; follow known shapes."""
    body = release["body"]
    match = re.search(r"release-notes-published/([\w.\-]+)\.md", body)
    if match and forge[0].startswith("gitea:"):
        host = forge[0].split(":", 1)[1]
        notes = get(f"https://{host}/{forge[1]}/{forge[2]}/raw/branch/forgejo/"
                    f"release-notes-published/{match.group(1)}.md")
        return body + "\n\n" + notes
    return body


def synapse_upgrade_sections(tag: str, versions: list[str],
                             get: Callable[[str], str] = http_get) -> str:
    doc = get(f"https://raw.githubusercontent.com/element-hq/synapse/{tag}/docs/upgrade.md")
    wanted = {v.lstrip("v") for v in versions}
    out, keep = [], False
    for line in doc.splitlines():
        match = re.match(r"^# Upgrading to v(\S+)", line)
        if match:
            keep = match.group(1) in wanted
        elif line.startswith("# "):
            keep = False
        if keep:
            out.append(line)
    return "\n".join(out).strip()


def recent_issue_titles(forge: tuple[str, str, str], version: str, since: str,
                        get: Callable[[str], str] = http_get) -> list[str]:
    kind, owner, repo = forge
    if kind.startswith("gitea:"):
        host = kind.split(":", 1)[1]
        # Gitea's `q` is loose and `since` filters on update time, so fetch a
        # page and keep only issues created after the release that name it.
        query = urllib.parse.urlencode({"state": "all", "type": "issues", "q": version,
                                        "limit": 50, "since": f"{since}T00:00:00Z"})
        raw = json.loads(get(f"https://{host}/api/v1/repos/{owner}/{repo}/issues?{query}"))
        hits = [i for i in raw
                if (i.get("created_at") or "")[:10] >= since
                and version in f"{i.get('title') or ''}\n{i.get('body') or ''}"]
        return [f"#{i['number']} [{i['state']}] {i['title'][:140]}" for i in hits[:ISSUE_LIMIT]]
    query = urllib.parse.quote(f'repo:{owner}/{repo} is:issue "{version}" created:>={since}')
    raw = json.loads(get(f"https://api.github.com/search/issues?q={query}&per_page={ISSUE_LIMIT}"))
    return [f"#{i['number']} [{i['state']}] {i['title'][:140]}" for i in raw.get("items", [])[:ISSUE_LIMIT]]


def collect_notes(app: dict, get: Callable[[str], str] = http_get) -> dict:
    """Bounded release-note context for one pending app. Errors are recorded, not raised."""
    current = upstream_version(app["currentVersion"])
    new = upstream_version(app["newVersion"])
    notes: dict[str, Any] = {"id": app["id"], "upstreamRange": f"{current} -> {new}",
                             "releases": [], "knownIssueTitles": [], "errors": []}
    try:
        code = package_upstream(app["packageUrl"], app["newRevision"], get)
    except Exception as exc:  # noqa: BLE001 - surfaced to the assessor
        notes["errors"].append(f"package manifest: {exc}")
        return notes
    notes["upstreamCode"] = code
    forge = forge_repo(code or "")
    if not forge:
        notes["errors"].append(f"no supported release source for upstream {code!r}")
        return notes
    try:
        chosen = releases_in_range(list_releases(forge, get), current, new)
    except Exception as exc:  # noqa: BLE001
        notes["errors"].append(f"releases: {exc}")
        return notes
    if not chosen:
        notes["errors"].append("no matching upstream releases found for this range")
    # Spend the budget newest-first: the target release matters most, and a
    # long run of point releases must not squeeze it out.
    used = 0
    for release in reversed(chosen):
        try:
            body = expand_linked_notes(release, forge, get)
        except Exception as exc:  # noqa: BLE001
            body = release["body"]
            notes["errors"].append(f"linked notes for {release['tag']}: {exc}")
        text = excerpt(body)
        if used + len(text) > APP_LIMIT:
            text = excerpt(body, max(600, APP_LIMIT - used))
        used += len(text)
        notes["releases"].insert(0, {"tag": release["tag"], "date": release["date"],
                                     "url": release["url"], "excerpt": text})
    if forge[1:] == ("element-hq", "synapse") and chosen:
        try:
            notes["upgradeGuide"] = excerpt(synapse_upgrade_sections(
                chosen[-1]["tag"], [r["tag"] for r in chosen], get), 8000)
            notes["upgradeGuideUrl"] = ("https://github.com/element-hq/synapse/blob/"
                                        f"{chosen[-1]['tag']}/docs/upgrade.md")
        except Exception as exc:  # noqa: BLE001
            notes["errors"].append(f"synapse upgrade guide: {exc}")
    if chosen:
        try:
            notes["knownIssueTitles"] = recent_issue_titles(
                forge, chosen[-1]["tag"].lstrip("v"), chosen[-1]["date"] or "2000-01-01", get)
        except Exception as exc:  # noqa: BLE001
            notes["errors"].append(f"issue search: {exc}")
    return notes
