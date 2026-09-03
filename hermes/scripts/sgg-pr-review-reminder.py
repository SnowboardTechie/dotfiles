#!/usr/bin/env python3
"""Collect Bryan's review-ready, still-waiting SGG pull requests."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from typing import Any

AUTHOR = "SnowboardTechie"
REPOSITORIES = (
    "HHS/simpler-grants-gov",
    "HHS/simpler-grants-protocol",
    "common-grants/py-cg-grants-gov",
    "common-grants/ts-cg-grants-gov",
)
PR_FIELDS = (
    "number,title,url,isDraft,reviewDecision,reviewRequests,latestReviews,"
    "statusCheckRollup,mergeStateStatus,createdAt,updatedAt,headRefOid"
)
PASSING_CONCLUSIONS = {"SUCCESS", "NEUTRAL", "SKIPPED"}
FAILING_CONCLUSIONS = {
    "ACTION_REQUIRED",
    "CANCELLED",
    "FAILURE",
    "STALE",
    "STARTUP_FAILURE",
    "TIMED_OUT",
}


class GitHubError(RuntimeError):
    """A bounded GitHub CLI call failed."""


def run_gh(arguments: list[str]) -> str:
    try:
        completed = subprocess.run(
            ["gh", *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=45,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitHubError(str(exc)) from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "unknown gh error").strip()
        raise GitHubError(detail[:500])
    return completed.stdout


def reviewer_identity(request: dict[str, Any]) -> dict[str, str] | None:
    kind = str(request.get("__typename") or "")
    if kind == "User" and request.get("login"):
        return {"kind": "user", "login": str(request["login"])}
    if kind == "Team" and request.get("slug"):
        identity = {"kind": "team", "slug": str(request["slug"])}
        if request.get("name"):
            identity["name"] = str(request["name"])
        return identity
    return None


def check_summary(checks: list[dict[str, Any]]) -> dict[str, Any]:
    failing: list[str] = []
    pending: list[str] = []
    for check in checks:
        name = str(check.get("name") or check.get("context") or "unnamed check")
        kind = str(check.get("__typename") or "")
        if kind == "CheckRun":
            if str(check.get("status") or "").upper() != "COMPLETED":
                pending.append(name)
                continue
            conclusion = str(check.get("conclusion") or "").upper()
            if conclusion in FAILING_CONCLUSIONS or conclusion not in PASSING_CONCLUSIONS:
                failing.append(name)
        else:
            state = str(check.get("state") or "").upper()
            if state in {"PENDING", "EXPECTED"}:
                pending.append(name)
            elif state not in {"SUCCESS"}:
                failing.append(name)

    if failing:
        state = "FAILURE"
    elif pending:
        state = "PENDING"
    elif checks:
        state = "SUCCESS"
    else:
        state = "NONE"
    return {
        "state": state,
        "total": len(checks),
        "failing": sorted(set(failing)),
        "pending": sorted(set(pending)),
    }


def normalize_pr(repository: str, raw: dict[str, Any]) -> dict[str, Any]:
    reviewers = [
        identity
        for request in raw.get("reviewRequests") or []
        if (identity := reviewer_identity(request)) is not None
    ]
    checks = check_summary(raw.get("statusCheckRollup") or [])
    reasons: list[str] = []
    if raw.get("isDraft"):
        reasons.append("draft")
    if str(raw.get("reviewDecision") or "").upper() == "APPROVED":
        reasons.append("approved")
    if not reviewers:
        reasons.append("no-reviewer-requested")
    if checks["state"] == "FAILURE":
        reasons.append("checks-failing")
    elif checks["state"] == "PENDING":
        reasons.append("checks-pending")
    if str(raw.get("mergeStateStatus") or "").upper() == "DIRTY":
        reasons.append("merge-conflict")

    return {
        "repository": repository,
        "number": raw["number"],
        "title": raw["title"],
        "url": raw["url"],
        "createdAt": raw.get("createdAt"),
        "updatedAt": raw.get("updatedAt"),
        "headRefOid": raw.get("headRefOid"),
        "reviewDecision": raw.get("reviewDecision") or None,
        "requestedReviewers": reviewers,
        "checks": checks,
        "mergeStateStatus": raw.get("mergeStateStatus"),
        "eligible": not reasons,
        "exclusionReasons": reasons,
    }


def collect() -> dict[str, Any]:
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    payload: dict[str, Any] = {
        "generatedAt": generated_at,
        "author": AUTHOR,
        "repositories": [],
        "candidates": [],
        "sourceErrors": [],
    }

    try:
        authenticated_as = run_gh(["api", "user", "--jq", ".login"]).strip()
    except GitHubError as exc:
        payload["sourceErrors"].append({"source": "github-auth", "error": str(exc)})
        return payload
    if authenticated_as.casefold() != AUTHOR.casefold():
        payload["sourceErrors"].append(
            {
                "source": "github-auth",
                "error": f"authenticated as {authenticated_as!r}, expected {AUTHOR!r}",
            }
        )
        return payload

    for repository in REPOSITORIES:
        try:
            raw_text = run_gh(
                [
                    "pr",
                    "list",
                    "--repo",
                    repository,
                    "--author",
                    AUTHOR,
                    "--state",
                    "open",
                    "--limit",
                    "100",
                    "--json",
                    PR_FIELDS,
                ]
            )
            raw_prs = json.loads(raw_text)
            if not isinstance(raw_prs, list):
                raise GitHubError("gh returned a non-list PR payload")
        except (GitHubError, json.JSONDecodeError) as exc:
            payload["sourceErrors"].append({"source": repository, "error": str(exc)[:500]})
            payload["repositories"].append(
                {"name": repository, "status": "error", "openPullRequests": []}
            )
            continue

        if len(raw_prs) == 100:
            payload["sourceErrors"].append(
                {
                    "source": repository,
                    "error": "result reached the 100-PR safety limit; collection may be incomplete",
                }
            )
        pull_requests = [normalize_pr(repository, raw) for raw in raw_prs]
        payload["repositories"].append(
            {"name": repository, "status": "ok", "openPullRequests": pull_requests}
        )
        payload["candidates"].extend(pr for pr in pull_requests if pr["eligible"])

    payload["candidates"].sort(
        key=lambda pr: (pr.get("createdAt") or "", pr["repository"], pr["number"])
    )
    payload["candidateCount"] = len(payload["candidates"])
    payload["openPullRequestCount"] = sum(
        len(repository["openPullRequests"]) for repository in payload["repositories"]
    )
    return payload


def main() -> int:
    print(json.dumps(collect(), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
