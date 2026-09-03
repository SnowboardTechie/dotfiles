#!/usr/bin/env python3
"""Collect Bryan's review-ready, still-waiting SGG pull requests."""

from __future__ import annotations

import json
import re
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
    "number,title,url,body,isDraft,reviewDecision,reviewRequests,latestReviews,"
    "statusCheckRollup,mergeStateStatus,createdAt,updatedAt,headRefOid,"
    "baseRefName,headRefName,labels,closingIssuesReferences"
)
SLACK_REVIEWER_NAMES = {
    "karinamzalez": "Karina Gonzalez",
    "widal001": "Billy Daly",
}
DEFAULT_REVIEWER_LOGINS = ("karinamzalez", "widal001")
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


def reviewer_identity(request: dict[str, Any]) -> dict[str, str | None] | None:
    kind = str(request.get("__typename") or "")
    if kind == "User" and request.get("login"):
        login = str(request["login"])
        return {
            "kind": "user",
            "githubLogin": login,
            "slackName": SLACK_REVIEWER_NAMES.get(login),
        }
    if kind == "Team" and request.get("slug"):
        return {
            "kind": "team",
            "githubSlug": str(request["slug"]),
            "slackName": None,
        }
    return None


def reviewers_for_requests(
    requests: list[dict[str, Any]],
) -> tuple[list[dict[str, str | None]], str]:
    reviewers = [
        identity
        for request in requests
        if (identity := reviewer_identity(request)) is not None
    ]
    if not reviewers:
        return (
            [
                {
                    "kind": "user",
                    "githubLogin": login,
                    "slackName": SLACK_REVIEWER_NAMES[login],
                }
                for login in DEFAULT_REVIEWER_LOGINS
            ],
            "team-default",
        )

    order = {login: index for index, login in enumerate(DEFAULT_REVIEWER_LOGINS)}
    reviewers.sort(
        key=lambda reviewer: (
            order.get(str(reviewer.get("githubLogin")), len(order)),
            str(reviewer.get("githubLogin") or reviewer.get("githubSlug") or ""),
        )
    )
    return reviewers, "github-request"


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


def priority_context(body: str) -> list[str]:
    dependency_keywords = ("before", "block", "depend", "first", "stacked", "until")
    priority_keywords = ("advis", "audit", "release", "security")
    dependency_lines: list[str] = []
    priority_lines: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        folded = line.casefold()
        if not line:
            continue
        if any(keyword in folded for keyword in dependency_keywords):
            dependency_lines.append(line[:300])
        elif any(keyword in folded for keyword in priority_keywords):
            priority_lines.append(line[:300])
    return (dependency_lines + priority_lines)[:8]


def normalize_pr(repository: str, raw: dict[str, Any]) -> dict[str, Any]:
    reviewers, reviewer_source = reviewers_for_requests(raw.get("reviewRequests") or [])
    checks = check_summary(raw.get("statusCheckRollup") or [])
    reasons: list[str] = []
    if raw.get("isDraft"):
        reasons.append("draft")
    if str(raw.get("reviewDecision") or "").upper() == "APPROVED":
        reasons.append("approved")

    labels = [str(label.get("name")) for label in raw.get("labels") or [] if label.get("name")]
    closing_issues = [
        {
            "number": issue.get("number"),
            "title": issue.get("title"),
            "url": issue.get("url"),
        }
        for issue in raw.get("closingIssuesReferences") or []
        if issue.get("number")
    ]

    return {
        "repository": repository,
        "number": raw["number"],
        "title": raw["title"],
        "url": raw["url"],
        "createdAt": raw.get("createdAt"),
        "updatedAt": raw.get("updatedAt"),
        "headRefOid": raw.get("headRefOid"),
        "baseRefName": raw.get("baseRefName"),
        "headRefName": raw.get("headRefName"),
        "reviewDecision": raw.get("reviewDecision") or None,
        "reviewers": reviewers,
        "reviewerSource": reviewer_source,
        "unmappedSlackReviewers": [
            reviewer.get("githubLogin") or reviewer.get("githubSlug")
            for reviewer in reviewers
            if not reviewer.get("slackName")
        ],
        "labels": labels,
        "closingIssues": closing_issues,
        "priorityContext": priority_context(str(raw.get("body") or "")),
        "checks": checks,
        "mergeStateStatus": raw.get("mergeStateStatus"),
        "eligible": not reasons,
        "exclusionReasons": reasons,
    }


def _candidate_id(pr: dict[str, Any]) -> str:
    return f"{pr['repository']}#{pr['number']}"


def add_dependencies(candidates: list[dict[str, Any]]) -> None:
    by_id = {_candidate_id(pr): pr for pr in candidates}
    by_number = {
        (pr["repository"], int(pr["number"])): pr
        for pr in candidates
    }
    head_branches = {
        (pr["repository"], pr.get("headRefName")): pr
        for pr in candidates
        if pr.get("headRefName")
    }
    issue_closers = {
        (pr["repository"], int(issue["number"])): pr
        for pr in candidates
        for issue in pr.get("closingIssues") or []
    }

    for pr in candidates:
        dependencies: dict[str, dict[str, Any]] = {}
        base_match = head_branches.get((pr["repository"], pr.get("baseRefName")))
        if base_match and _candidate_id(base_match) != _candidate_id(pr):
            dependencies[_candidate_id(base_match)] = {
                "repository": base_match["repository"],
                "number": base_match["number"],
                "url": base_match["url"],
                "evidence": f"base branch is {pr.get('baseRefName')}",
            }

        for line in pr.get("priorityContext") or []:
            for pr_number in re.findall(
                r"(?:stacked on|depends on|based on|blocked by|after)\s+(?:PR\s*)?#(\d+)",
                line,
                re.I,
            ):
                dependency_pr = by_number.get((pr["repository"], int(pr_number)))
                if dependency_pr and _candidate_id(dependency_pr) != _candidate_id(pr):
                    dependencies[_candidate_id(dependency_pr)] = {
                        "repository": dependency_pr["repository"],
                        "number": dependency_pr["number"],
                        "url": dependency_pr["url"],
                        "evidence": f"PR body identifies #{pr_number} as a prerequisite",
                    }
            for issue_number in re.findall(r"#(\d+)\s+(?:resolves?|lands?|merges?)\s+first", line, re.I):
                closer = issue_closers.get((pr["repository"], int(issue_number)))
                if closer and _candidate_id(closer) != _candidate_id(pr):
                    dependencies[_candidate_id(closer)] = {
                        "repository": closer["repository"],
                        "number": closer["number"],
                        "url": closer["url"],
                        "evidence": f"closes prerequisite issue #{issue_number}",
                    }

        pr["dependsOn"] = sorted(
            dependencies.values(), key=lambda dependency: dependency["number"]
        )
        pr["prioritySignals"] = []
        if any(label.casefold() in {"dependencies", "security"} for label in pr["labels"]):
            pr["prioritySignals"].append("dependency-or-security-remediation")

    for pr in candidates:
        dependents = [
            other
            for other in candidates
            if any(
                dependency["repository"] == pr["repository"]
                and dependency["number"] == pr["number"]
                for dependency in other["dependsOn"]
            )
        ]
        pr["unblocks"] = [
            {"repository": other["repository"], "number": other["number"], "url": other["url"]}
            for other in dependents
        ]
        if dependents:
            pr["prioritySignals"].append("prerequisite-for-another-candidate")

    unknown_dependencies = {
        _candidate_id(pr): [
            dependency
            for dependency in pr["dependsOn"]
            if f"{dependency['repository']}#{dependency['number']}" not in by_id
        ]
        for pr in candidates
    }
    if any(unknown_dependencies.values()):
        raise ValueError("candidate dependency graph references a missing candidate")


def _is_urgent(pr: dict[str, Any]) -> bool:
    return "dependency-or-security-remediation" in pr.get("prioritySignals", [])


def order_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    add_dependencies(candidates)
    by_id = {_candidate_id(pr): pr for pr in candidates}
    neighbors = {candidate_id: set() for candidate_id in by_id}
    for candidate_id, pr in by_id.items():
        for dependency in pr["dependsOn"]:
            dependency_id = f"{dependency['repository']}#{dependency['number']}"
            neighbors[candidate_id].add(dependency_id)
            neighbors[dependency_id].add(candidate_id)

    components: list[list[str]] = []
    unseen = set(by_id)
    while unseen:
        seed = min(unseen)
        stack = [seed]
        component: list[str] = []
        while stack:
            candidate_id = stack.pop()
            if candidate_id not in unseen:
                continue
            unseen.remove(candidate_id)
            component.append(candidate_id)
            stack.extend(sorted(neighbors[candidate_id], reverse=True))
        components.append(component)

    def component_key(component: list[str]) -> tuple[Any, ...]:
        members = [by_id[candidate_id] for candidate_id in component]
        has_urgent = any(_is_urgent(pr) for pr in members)
        has_dependencies = any(neighbors[candidate_id] for candidate_id in component)
        oldest = min(str(pr.get("createdAt") or "") for pr in members)
        return (0 if has_urgent else 1 if has_dependencies else 2, oldest, min(component))

    ordered: list[dict[str, Any]] = []
    for component in sorted(components, key=component_key):
        pending = set(component)
        while pending:
            ready = [
                candidate_id
                for candidate_id in pending
                if all(
                    f"{dependency['repository']}#{dependency['number']}" not in pending
                    for dependency in by_id[candidate_id]["dependsOn"]
                )
            ]
            if not ready:
                ready = list(pending)
            ready.sort(
                key=lambda candidate_id: (
                    0 if _is_urgent(by_id[candidate_id]) else 1,
                    -len(by_id[candidate_id]["unblocks"]),
                    str(by_id[candidate_id].get("createdAt") or ""),
                    candidate_id,
                )
            )
            selected = ready[0]
            pending.remove(selected)
            ordered.append(by_id[selected])

    for rank, pr in enumerate(ordered, start=1):
        pr["priorityRank"] = rank
    return ordered


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
            {
                "name": repository,
                "status": "ok",
                "openPullRequestCount": len(pull_requests),
                "excludedPullRequests": [
                    {
                        "number": pr["number"],
                        "url": pr["url"],
                        "exclusionReasons": pr["exclusionReasons"],
                    }
                    for pr in pull_requests
                    if not pr["eligible"]
                ],
            }
        )
        payload["candidates"].extend(pr for pr in pull_requests if pr["eligible"])
        for pr in pull_requests:
            if pr["unmappedSlackReviewers"]:
                payload["sourceErrors"].append(
                    {
                        "source": f"{repository}#{pr['number']}",
                        "error": "missing Slack-name mapping for reviewer(s): "
                        + ", ".join(str(value) for value in pr["unmappedSlackReviewers"]),
                    }
                )

    payload["candidates"] = order_candidates(payload["candidates"])
    payload["candidateCount"] = len(payload["candidates"])
    payload["openPullRequestCount"] = sum(
        int(repository.get("openPullRequestCount") or 0)
        for repository in payload["repositories"]
    )
    return payload


def main() -> int:
    print(json.dumps(collect(), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
