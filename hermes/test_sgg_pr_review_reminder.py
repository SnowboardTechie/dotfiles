from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "scripts" / "sgg-pr-review-reminder.py"
MANIFEST = ROOT / "manifest.json"
PROMPT = ROOT / "automations" / "sgg-pr-review-reminder" / "prompt.md"
SKILL = ROOT / "skills" / "productivity" / "sgg-pr-review-reminder" / "SKILL.md"

SPEC = importlib.util.spec_from_file_location("sgg_pr_review_reminder", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def pull_request(**overrides: object) -> dict:
    value = {
        "number": 42,
        "title": "feat: useful change",
        "url": "https://github.com/HHS/simpler-grants-protocol/pull/42",
        "body": "",
        "isDraft": False,
        "reviewDecision": "REVIEW_REQUIRED",
        "reviewRequests": [{"__typename": "User", "login": "widal001"}],
        "statusCheckRollup": [
            {
                "__typename": "CheckRun",
                "name": "test",
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
            }
        ],
        "mergeStateStatus": "BLOCKED",
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-02T00:00:00Z",
        "headRefOid": "abc123",
        "baseRefName": "main",
        "headRefName": "feature-42",
        "labels": [],
        "closingIssuesReferences": [],
    }
    value.update(overrides)
    return value


class EligibilityTest(unittest.TestCase):
    def normalize(self, **overrides: object) -> dict:
        return MODULE.normalize_pr(
            "HHS/simpler-grants-protocol", pull_request(**overrides)
        )

    def test_non_draft_unapproved_pr_is_eligible(self) -> None:
        result = self.normalize()
        self.assertTrue(result["eligible"])
        self.assertEqual(result["exclusionReasons"], [])
        self.assertEqual(
            result["reviewers"],
            [{"kind": "user", "githubLogin": "widal001", "slackName": "Billy Daly"}],
        )

    def test_re_review_request_can_be_eligible_after_changes_requested(self) -> None:
        self.assertTrue(self.normalize(reviewDecision="CHANGES_REQUESTED")["eligible"])

    def test_only_draft_and_approved_are_excluded(self) -> None:
        cases = {
            "draft": {"isDraft": True},
            "approved": {"reviewDecision": "APPROVED"},
        }
        for reason, overrides in cases.items():
            with self.subTest(reason=reason):
                result = self.normalize(**overrides)
                self.assertFalse(result["eligible"])
                self.assertIn(reason, result["exclusionReasons"])

    def test_missing_github_request_uses_slack_team_route(self) -> None:
        result = self.normalize(reviewRequests=[])
        self.assertTrue(result["eligible"])
        self.assertEqual(result["reviewerSource"], "team-default")
        self.assertEqual(
            [reviewer["slackName"] for reviewer in result["reviewers"]],
            ["Karina Gonzalez", "Billy Daly"],
        )

    def test_checks_and_merge_state_do_not_hide_a_ready_pr(self) -> None:
        result = self.normalize(
            reviewRequests=[],
            mergeStateStatus="DIRTY",
            statusCheckRollup=[
                {
                    "__typename": "CheckRun",
                    "name": "audit",
                    "status": "COMPLETED",
                    "conclusion": "FAILURE",
                }
            ],
        )
        self.assertTrue(result["eligible"])
        self.assertEqual(result["checks"]["state"], "FAILURE")

    def test_slack_names_replace_github_logins_and_use_canonical_order(self) -> None:
        result = self.normalize(
            reviewRequests=[
                {"__typename": "User", "login": "widal001"},
                {"__typename": "User", "login": "karinamzalez"},
            ]
        )
        self.assertEqual(
            [reviewer["slackName"] for reviewer in result["reviewers"]],
            ["Karina Gonzalez", "Billy Daly"],
        )


class PriorityOrderingTest(unittest.TestCase):
    def normalize(self, number: int, **overrides: object) -> dict:
        raw = pull_request(
            number=number,
            url=f"https://github.com/HHS/simpler-grants-protocol/pull/{number}",
            headRefName=f"feature-{number}",
            createdAt=f"2026-01-{number % 28 + 1:02d}T00:00:00Z",
        )
        raw.update(overrides)
        return MODULE.normalize_pr(
            "HHS/simpler-grants-protocol",
            raw,
        )

    def test_security_fix_and_stacked_chain_precede_independent_prs(self) -> None:
        independent_old = self.normalize(1010, createdAt="2025-12-01T00:00:00Z")
        base = self.normalize(1115, headRefName="trusted-publishing")
        dependent = self.normalize(
            1117,
            baseRefName="trusted-publishing",
            body="Stacked on #1115. Either #1151 resolves first, or this gate stays red.",
            reviewRequests=[],
        )
        decision_gate = self.normalize(
            1143,
            createdAt="2026-02-01T00:00:00Z",
            labels=[{"name": "adr"}],
        )
        security = self.normalize(
            1161,
            labels=[{"name": "dependencies"}],
            closingIssuesReferences=[
                {
                    "number": 1151,
                    "title": "Clear audit advisories",
                    "url": "https://github.com/HHS/simpler-grants-protocol/issues/1151",
                }
            ],
        )

        ordered = MODULE.order_candidates(
            [independent_old, dependent, base, decision_gate, security]
        )

        self.assertEqual([pr["number"] for pr in ordered], [1161, 1115, 1117, 1143, 1010])
        self.assertEqual(
            [dependency["number"] for dependency in dependent["dependsOn"]],
            [1115, 1161],
        )
        self.assertEqual([pr["priorityRank"] for pr in ordered], [1, 2, 3, 4, 5])

    def test_recent_activity_breaks_ties_between_ordinary_independent_prs(self) -> None:
        older_activity = self.normalize(300, updatedAt="2026-01-01T00:00:00Z")
        newer_activity = self.normalize(301, updatedAt="2026-02-01T00:00:00Z")

        ordered = MODULE.order_candidates([older_activity, newer_activity])

        self.assertEqual([pr["number"] for pr in ordered], [301, 300])

    def test_explicit_body_dependency_is_detected_without_a_stacked_base(self) -> None:
        prerequisite = self.normalize(200, headRefName="prerequisite")
        dependent = self.normalize(
            201,
            baseRefName="main",
            body="This depends on #200 and should merge after it.",
        )

        ordered = MODULE.order_candidates([dependent, prerequisite])

        self.assertEqual([pr["number"] for pr in ordered], [200, 201])
        self.assertEqual(dependent["dependsOn"][0]["number"], 200)


class ContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.job = next(
            job for job in self.manifest["cronJobs"] if job["name"] == "SGG PR Review Reminder"
        )

    def test_scope_is_exactly_the_four_sgg_repositories(self) -> None:
        self.assertEqual(
            MODULE.REPOSITORIES,
            (
                "HHS/simpler-grants-gov",
                "HHS/simpler-grants-protocol",
                "common-grants/py-cg-grants-gov",
                "common-grants/ts-cg-grants-gov",
            ),
        )
        self.assertEqual(MODULE.AUTHOR, "SnowboardTechie")

    def test_manifest_installs_assets_and_schedules_before_slack_prompt(self) -> None:
        self.assertIn("sgg-pr-review-reminder.py", self.manifest["scripts"])
        self.assertIn("sgg-pr-review-reminder.py", self.manifest["copiedScripts"])
        self.assertIn("productivity/sgg-pr-review-reminder", self.manifest["skills"])
        self.assertEqual(self.job["schedule"], "45 5 * * 2,4")
        self.assertEqual(self.job["model"], "gpt-5.6-terra")
        self.assertEqual(self.job["provider"], "openai-codex")
        self.assertEqual(
            self.job["deliver"],
            "matrix:!USHKqGpzKJq-4PQkLs_aDY_PxB_7AvS-xLSQGcdXVGU",
        )
        self.assertEqual(
            self.job["skills"], ["sgg-pr-review-reminder", "voice-bryan"]
        )
        self.assertEqual(self.job["script"], "sgg-pr-review-reminder.py")
        self.assertEqual(self.job["enabledToolsets"], ["safe"])
        self.assertFalse(self.job["noAgent"])
        self.assertFalse(self.job["attachToSession"])
        self.assertTrue(PROMPT.is_file())
        self.assertTrue(SKILL.is_file())

    def test_prompt_and_skill_preserve_read_only_boundary(self) -> None:
        prompt = PROMPT.read_text(encoding="utf-8")
        skill = SKILL.read_text(encoding="utf-8")
        self.assertIn("read-only", prompt)
        self.assertIn("Never modify repositories", skill)
        self.assertIn("candidateCount", skill)
        self.assertIn("priorityRank", skill)
        self.assertIn("@Karina Gonzalez", skill)
        self.assertIn("@Billy Daly", skill)
        self.assertNotIn("written as `@login`", skill)
        self.assertNotIn("—", skill)


if __name__ == "__main__":
    unittest.main()
