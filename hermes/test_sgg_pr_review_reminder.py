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
        "isDraft": False,
        "reviewDecision": "REVIEW_REQUIRED",
        "reviewRequests": [{"__typename": "User", "login": "reviewer"}],
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
    }
    value.update(overrides)
    return value


class EligibilityTest(unittest.TestCase):
    def normalize(self, **overrides: object) -> dict:
        return MODULE.normalize_pr(
            "HHS/simpler-grants-protocol", pull_request(**overrides)
        )

    def test_green_non_draft_with_requested_reviewer_is_eligible(self) -> None:
        result = self.normalize()
        self.assertTrue(result["eligible"])
        self.assertEqual(result["exclusionReasons"], [])
        self.assertEqual(result["requestedReviewers"], [{"kind": "user", "login": "reviewer"}])

    def test_re_review_request_can_be_eligible_after_changes_requested(self) -> None:
        self.assertTrue(self.normalize(reviewDecision="CHANGES_REQUESTED")["eligible"])

    def test_each_not_ready_condition_is_excluded(self) -> None:
        cases = {
            "draft": {"isDraft": True},
            "approved": {"reviewDecision": "APPROVED"},
            "no-reviewer-requested": {"reviewRequests": []},
            "checks-failing": {
                "statusCheckRollup": [
                    {
                        "__typename": "CheckRun",
                        "name": "test",
                        "status": "COMPLETED",
                        "conclusion": "FAILURE",
                    }
                ]
            },
            "checks-pending": {
                "statusCheckRollup": [
                    {
                        "__typename": "CheckRun",
                        "name": "test",
                        "status": "IN_PROGRESS",
                        "conclusion": "",
                    }
                ]
            },
            "merge-conflict": {"mergeStateStatus": "DIRTY"},
        }
        for reason, overrides in cases.items():
            with self.subTest(reason=reason):
                result = self.normalize(**overrides)
                self.assertFalse(result["eligible"])
                self.assertIn(reason, result["exclusionReasons"])

    def test_team_request_preserves_slug_and_name(self) -> None:
        result = self.normalize(
            reviewRequests=[
                {"__typename": "Team", "slug": "maintainers", "name": "Maintainers"}
            ]
        )
        self.assertEqual(
            result["requestedReviewers"],
            [{"kind": "team", "slug": "maintainers", "name": "Maintainers"}],
        )


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
        self.assertNotIn("—", skill)


if __name__ == "__main__":
    unittest.main()
