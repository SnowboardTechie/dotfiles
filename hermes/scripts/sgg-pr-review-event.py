#!/usr/bin/env python3
"""Filter SGG GitHub review events and add read-only PR state."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Callable
from typing import Any

OWNER = "SnowboardTechie"
REPOSITORIES = {
    "HHS/simpler-grants-protocol",
    "common-grants/py-cg-grants-gov",
    "common-grants/ts-cg-grants-gov",
}
MAX_DETAIL_LENGTH = 400
SAFE_TEXT_TRANSLATION = str.maketrans(
    {
        "@": "＠",
        "<": "‹",
        ">": "›",
        "[": "［",
        "]": "］",
        "(": "（",
        ")": "）",
        "`": "｀",
    }
)


def clean(value: Any, limit: int = MAX_DETAIL_LENGTH) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = text.translate(SAFE_TEXT_TRANSLATION)
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def event_kind(payload: dict[str, Any]) -> str | None:
    if "review" in payload and "pull_request" in payload:
        return "review"
    if "comment" in payload and "pull_request" in payload:
        return "review_comment"
    if "comment" in payload and payload.get("issue", {}).get("pull_request"):
        return "conversation_comment"
    if "pull_request" in payload:
        return "pull_request"
    return None


def relevant(payload: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    repository = payload.get("repository") or {}
    repo = repository.get("full_name")
    if repo not in REPOSITORIES:
        return None

    actor = payload.get("sender") or {}
    if actor.get("login") == OWNER or actor.get("type") == "Bot":
        return None

    kind = event_kind(payload)
    action = payload.get("action")
    pull_request = payload.get("pull_request") or payload.get("issue") or {}
    author = (pull_request.get("user") or {}).get("login")

    if kind == "review" and action in {"submitted", "dismissed"} and author == OWNER:
        return kind, pull_request
    if kind in {"review_comment", "conversation_comment"} and action == "created" and author == OWNER:
        return kind, pull_request
    if kind == "pull_request" and action == "review_requested":
        requested = (payload.get("requested_reviewer") or {}).get("login")
        if requested == OWNER:
            return kind, pull_request
    return None


def fetch_pr(repo: str, number: int) -> dict[str, Any]:
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/pulls/{number}"],
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    return json.loads(result.stdout)


def transform(
    payload: dict[str, Any],
    pr_fetcher: Callable[[str, int], dict[str, Any]] = fetch_pr,
) -> dict[str, Any] | None:
    match = relevant(payload)
    if match is None:
        return None

    kind, event_pr = match
    repo = payload["repository"]["full_name"]
    number = int(event_pr["number"])
    actor = clean((payload.get("sender") or {}).get("login"), 80)
    action = str(payload.get("action") or "updated")

    detail = ""
    review_state = ""
    if kind == "review":
        review = payload.get("review") or {}
        review_state = clean(review.get("state"), 40).lower()
        detail = clean(review.get("body"))
    elif kind in {"review_comment", "conversation_comment"}:
        detail = clean((payload.get("comment") or {}).get("body"))
    elif kind == "pull_request":
        detail = f"{OWNER} was requested as a reviewer."

    source_health = "verified"
    try:
        current = pr_fetcher(repo, number)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        current = event_pr
        source_health = "readback unavailable"

    state = clean(current.get("state"), 20).lower() or "unknown"
    if current.get("merged_at"):
        state = "merged"
    elif current.get("draft"):
        state = "draft"

    title = clean(current.get("title") or event_pr.get("title"), 180)
    url = f"https://github.com/{repo}/pull/{number}"
    if not title:
        return None

    if kind == "review":
        change = f"{actor} {action} a {review_state or 'review'} review."
    elif kind == "pull_request":
        change = f"{actor} requested your review."
    else:
        change = f"{actor} added a {'review' if kind == 'review_comment' else 'conversation'} comment."

    return {
        "repo": repo,
        "number": number,
        "title": title,
        "url": url,
        "change": change,
        "detail": detail or "No written detail was included.",
        "state": state,
        "source_health": source_health,
    }


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError):
        return 1
    if not isinstance(payload, dict):
        return 1

    output = transform(payload)
    if output is None:
        return 0
    json.dump(output, sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
