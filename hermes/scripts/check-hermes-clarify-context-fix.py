#!/usr/bin/env python3
"""Read-only watch for the Hermes fix to context hidden before clarify cards.

Upstream issue NousResearch/hermes-agent#133320: Claude 5.x writes the text meant
for the user into a thinking block before a clarify call, so the card arrives
without context. The proposed fix (PR #134690) steers the model through the
clarify tool description. Bryan's workaround is to ask decision questions in the
final message instead of on cards. This watch alerts once per transition so the
workaround can be revisited; it never edits skills, memory or Hermes.
"""
from __future__ import annotations

import ast
import fcntl
import json
import os
import re
import subprocess
import tempfile
import urllib.request
from pathlib import Path

REPO = "NousResearch/hermes-agent"
ISSUE = 133320
PR = 134690
SOURCE = "tools/clarify_tool.py"
MENTION = "@bryan:snowboardtechie.com"
ISSUE_URL = f"https://github.com/{REPO}/issues/{ISSUE}"
PR_URL = f"https://github.com/{REPO}/pull/{PR}"
STEER = re.compile(r"\b(reasoning|thinking)\b", re.IGNORECASE)
WORKAROUNDS = (
    "Workarounds to revisit: (1) the grilling skill's rule 'Ask in the final message, not on a "
    "clarify card' (dotfiles dot-agents/skills/grilling/SKILL.md, commits fbb406c and 53423f4); "
    "(2) the Hermes user-profile entry that starts 'Bryan sees only final messages and clarify "
    "cards ... put decision questions in the final message'."
)


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "hermes-clarify-fix-watch/1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read(2_000_001)
    if len(body) > 2_000_000:
        raise ValueError("upstream response exceeded size limit")
    return body


def _strings(node: ast.AST) -> str:
    """Flatten the literal text of a string, f-string or concatenation."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(_strings(part) for part in node.values)
    if isinstance(node, ast.FormattedValue):
        return "{}"
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _strings(node.left) + _strings(node.right)
    raise ValueError("clarify description is not literal text; manual review needed")


def steered(source: str) -> bool:
    """True when the clarify tool description tells the model about hidden reasoning.

    Fails closed if the schema is refactored beyond recognition.
    """
    tree = ast.parse(source)
    schemas = [n.value for n in ast.walk(tree) if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == "CLARIFY_SCHEMA" for t in n.targets)]
    if len(schemas) != 1 or not isinstance(schemas[0], ast.Dict):
        raise ValueError("CLARIFY_SCHEMA shape changed; manual review needed")
    descriptions = [v for k, v in zip(schemas[0].keys, schemas[0].values)
                    if isinstance(k, ast.Constant) and k.value == "description"]
    if len(descriptions) != 1:
        raise ValueError("clarify description missing; manual review needed")
    text = _strings(descriptions[0])
    if "clarification" not in text:
        raise ValueError("clarify description unrecognized; manual review needed")
    return bool(STEER.search(text))


def transition(state: dict, *, runtime: bool, upstream: bool, issue_state: str,
               pr_state: str, runtime_rev: str, upstream_sha: str) -> tuple[dict, str]:
    """Return the new state and at most one alert; each alert fires once."""
    state = dict(state)
    if runtime:
        if state.get("runtime_alerted"):
            return state, ""
        state["runtime_alerted"] = True
        state["runtime_rev"] = runtime_rev
        return state, (
            f"{MENTION} The Hermes fix for missing context before question cards is now in the "
            f"Hermes checkout you run ({runtime_rev[:12]}). Restart the desktop app and gateway if "
            "they haven't restarted since that update. The fix is a prompt steer, so test it before "
            "dropping workarounds: ask for a short visible summary followed by a question card a few "
            f"times and check the summary shows. {WORKAROUNDS} Nothing was changed automatically. "
            f"Retire this watcher once that's done. {ISSUE_URL}"
        )
    if upstream:
        if state.get("upstream_alerted"):
            return state, ""
        state["upstream_alerted"] = True
        state["upstream_sha"] = upstream_sha
        return state, (
            f"{MENTION} The Hermes fix for missing context before question cards landed upstream "
            f"(main {upstream_sha[:12]}), but your Hermes ({runtime_rev[:12]}) doesn't have it yet. "
            "No action needed; I'll alert again once your Hermes includes it. "
            f"https://github.com/{REPO}/blob/{upstream_sha}/{SOURCE}"
        )
    if issue_state.startswith("closed") or pr_state == "closed":
        if state.get("stalled_alerted"):
            return state, ""
        state["stalled_alerted"] = True
        return state, (
            f"{MENTION} The tracked Hermes fix for missing context before question cards stalled: "
            f"issue is {issue_state}, PR is {pr_state}, and upstream's clarify description still has "
            "no steer about hidden reasoning. Keep the workarounds; review whether it was fixed "
            f"another way. {ISSUE_URL} {PR_URL}"
        )
    return state, ""


def github_state(kind: str, number: int) -> dict:
    data = json.loads(fetch(f"https://api.github.com/repos/{REPO}/{kind}/{number}"))
    if not isinstance(data, dict) or data.get("number") != number:
        raise ValueError(f"unexpected {kind} payload")
    return data


def main() -> int:
    home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    directory = home / "state"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "hermes-clarify-context-fix-watch.json"
    with (directory / "hermes-clarify-context-fix-watch.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            state = json.loads(path.read_text()) if path.exists() else {}
            if not isinstance(state, dict):
                raise ValueError("invalid watcher state")
            checkout = home / "hermes-agent"
            runtime = steered((checkout / SOURCE).read_text(encoding="utf-8"))
            runtime_rev = subprocess.run(
                ["git", "-C", str(checkout), "rev-parse", "HEAD"],
                capture_output=True, text=True, check=True, timeout=30).stdout.strip()
            if not re.fullmatch(r"[0-9a-f]{40}", runtime_rev):
                raise ValueError("invalid runtime revision")
            sha = json.loads(fetch(f"https://api.github.com/repos/{REPO}/commits/main"))["sha"]
            if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
                raise ValueError("invalid upstream revision")
            upstream = steered(fetch(
                f"https://raw.githubusercontent.com/{REPO}/{sha}/{SOURCE}").decode("utf-8"))
            issue = github_state("issues", ISSUE)
            pr = github_state("pulls", PR)
            issue_state = issue["state"] + (f" ({issue['state_reason']})" if issue.get("state_reason") else "")
            pr_state = "merged" if pr.get("merged_at") else pr["state"]
            if pr_state == "merged":
                upstream = True
            updated, message = transition(
                state, runtime=runtime, upstream=upstream, issue_state=issue_state,
                pr_state=pr_state, runtime_rev=runtime_rev, upstream_sha=sha)
            # State commits before the alert prints; cron history records delivery.
            # If delivery fails, recover the saved output rather than regenerate it.
            fd, temporary = tempfile.mkstemp(prefix=".hermes-clarify-watch-", dir=directory)
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
            print(f"{MENTION} The Hermes question-card fix watcher couldn't check upstream or your "
                  f"Hermes ({type(exc).__name__}). Inspect its cron history. {ISSUE_URL}")
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
