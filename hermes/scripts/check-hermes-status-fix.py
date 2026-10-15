#!/usr/bin/env python3
"""Read-only upstream fix watch; never updates Hermes or re-enables launchd."""
from __future__ import annotations

import ast
import fcntl
import json
import os
import re
import tempfile
import urllib.request
from pathlib import Path

REPO = "NousResearch/hermes-agent"
SOURCE = "hermes_cli/cli_session_mixin.py"
MENTION = "@bryan:snowboardtechie.com"


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "hermes-status-fix-watch/1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read(2_000_001)
    if len(body) > 2_000_000:
        raise ValueError("upstream response exceeded size limit")
    return body


def fixed(source: str) -> bool:
    """Recognize the known fix, failing closed if upstream refactors the seam."""
    tree = ast.parse(source)
    methods = {}
    for name in ("_show_session_status", "_toggle_yolo"):
        matches = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name]
        if len(matches) != 1:
            raise ValueError("upstream status/toggle method shape changed; manual review needed")
        methods[name] = matches[0]
    queries = [n for n in ast.walk(methods["_show_session_status"])
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id == "is_approval_bypass_active_for_session"]
    if len(queries) != 1 or len(queries[0].args) != 1 or queries[0].keywords:
        raise ValueError("upstream approval query shape changed; manual review needed")
    query = ast.unparse(queries[0].args[0])
    if query not in ("getattr(self, 'session_id', '') or ''", "getattr(self, 'session_key', '') or ''"):
        raise ValueError("upstream approval identity changed; manual review needed")
    keys = [n for n in ast.walk(methods["_toggle_yolo"]) if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "session_key" for t in n.targets)]
    if len(keys) != 1 or ast.unparse(keys[0].value) != "self.session_id or 'default'":
        raise ValueError("upstream YOLO identity changed; manual review needed")
    return query == "getattr(self, 'session_id', '') or ''"


def transition(state: dict, is_fixed: bool, sha: str) -> tuple[dict, str]:
    """One alert per pending-to-fixed transition; not an automatic adoption verdict."""
    if not is_fixed:
        return {"fixed": False, "candidate_sha": sha}, ""
    if state.get("fixed"):
        return state, ""
    message = (
        f"{MENTION} Hermes upstream now contains the session_id /status fix. "
        "Bryan's nightly updater remains disabled. Review this exact candidate, verify Herdr "
        "compatibility and resolve the nightly wrapper's detached-HEAD/main requirement before "
        "removing the local patch and re-enabling ai.hermes.update. No update, patch removal, "
        "restart or re-enabling was performed. "
        f"https://github.com/{REPO}/blob/{sha}/{SOURCE}"
    )
    return {"fixed": True, "candidate_sha": sha}, message


def main() -> int:
    home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    directory = home / "state"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "hermes-status-fix-watch.json"
    with (directory / "hermes-status-fix-watch.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            state = json.loads(path.read_text()) if path.exists() else {}
            if not isinstance(state, dict):
                raise ValueError("invalid watcher state")
            sha = json.loads(fetch(f"https://api.github.com/repos/{REPO}/commits/main"))["sha"]
            if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
                raise ValueError("invalid upstream revision")
            source = fetch(f"https://raw.githubusercontent.com/{REPO}/{sha}/{SOURCE}").decode("utf-8")
            updated, message = transition(state, fixed(source), sha)
            # A state commit precedes notification preparation. Cron history records delivery
            # separately; if delivery fails, recover the saved output rather than regenerate it.
            fd, temporary = tempfile.mkstemp(prefix=".hermes-status-watch-", dir=directory)
            try:
                with os.fdopen(fd, "w") as output:
                    json.dump(updated, output, sort_keys=True)
                    output.write("\n")
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            if message:
                print(message)
            return 0
        except Exception as exc:
            # Never echo external content or raw exception text into cron delivery.
            print(f"{MENTION} Hermes upstream fix watcher could not verify the candidate "
                  f"({type(exc).__name__}). Nightly updates remain disabled; inspect cron history.")
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
