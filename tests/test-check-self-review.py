#!/usr/bin/env python3
"""Tests for dot-agents/skills/pr-self-review/scripts/check_self_review.py.

The verifier answers one question: does a current, complete `pr-self-review`
exist for this exact candidate, and is it ready? Each test builds a throwaway
Git repository with one candidate commit, writes the review artifacts the skill
would write for it, then breaks one condition.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "dot-agents" / "skills" / "pr-self-review" / "scripts" / "check_self_review.py"


class CheckSelfReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory(prefix="check-self-review-", dir=os.environ.get("TMPDIR"))
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name).resolve()
        self.repo = self.directory / "repo"
        self.state = self.directory / "state"
        self.repo.mkdir()
        self.state.mkdir()
        self.env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        self.git("init", "-b", "main")
        (self.repo / "a.txt").write_text("one\n")
        self.commit("Base")
        self.git("switch", "-c", "feature")
        (self.repo / "a.txt").write_text("one\ntwo\n")
        self.commit("Candidate")
        self.identity = self.recompute()
        self.write_review()

    # -- fixture helpers -------------------------------------------------

    def git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args], cwd=self.repo, env=self.env, capture_output=True, text=True, check=True
        )
        return result.stdout.strip()

    def commit(self, message: str) -> None:
        self.git("add", "-A")
        self.git(
            "-c", "user.name=Review Test", "-c", "user.email=review@example.invalid",
            "-c", "commit.gpgsign=false", "commit", "-q", "-m", message,
        )

    def recompute(self) -> dict:
        import hashlib

        base = self.git("rev-parse", "main^{commit}")
        head = self.git("rev-parse", "HEAD")
        diff = subprocess.run(
            ["git", "diff", "--binary", "-M", "-C", "--find-copies-harder", f"{base}...{head}", "--"],
            cwd=self.repo, env=self.env, capture_output=True, check=True,
        ).stdout
        return {
            "base_sha": base,
            "head_sha": head,
            "merge_base_sha": self.git("merge-base", base, head),
            "diff_sha256": hashlib.sha256(diff).hexdigest(),
            "expected_head_branch": "feature",
        }

    def write_review(self, *, dimensions: str = "[standards, spec]", readiness: str = "Ready to publish",
                     verdict: str = "met") -> None:
        i = self.identity
        (self.state / "summary.md").write_text(
            "---\n"
            "status: reviewed\n"
            "ticket: example\n"
            f"candidate: {i['head_sha']}\n"
            f"expected_head_branch: {i['expected_head_branch']}\n"
            f"base_sha: {i['base_sha']}\n"
            f"merge_base_sha: {i['merge_base_sha']}\n"
            f"diff_sha256: {i['diff_sha256']}\n"
            "review_context: orchestrator\n"
            f"dimensions: {dimensions}\n"
            "quality_gates: [ponytail]\n"
            "---\n\n"
            "## Headline\n\nFine.\n\n"
            "## Ship Readiness\n\n"
            f"{readiness}\n"
        )
        for name in ("standards", "spec", "ponytail"):
            (self.state / f"review-{name}.md").write_text(f"# {name}\n")
        (self.state / "intent-checklist.json").write_text(json.dumps({
            "candidate_identity": {k: i[k] for k in ("base_sha", "head_sha", "merge_base_sha", "diff_sha256")},
            "sources": [{"kind": "plan", "ref": "plan.md", "available": True, "criteria": 1}],
            "criteria": [{"id": "AC-1", "statement": "two is added", "sources": [],
                          "verdict": verdict, "evidence": "a.txt:2"}],
        }))

    def run_verifier(self, base: str = "main") -> tuple[int, dict]:
        result = subprocess.run(
            [sys.executable, "-I", str(VERIFIER), "--state-dir", str(self.state),
             "--worktree", str(self.repo), "--base", base],
            env=self.env, capture_output=True, text=True,
        )
        self.assertEqual(result.stderr, "", "problems belong in the JSON, not a traceback")
        return result.returncode, json.loads(result.stdout)

    def assert_fails(self, phrase: str) -> dict:
        code, report = self.run_verifier()
        self.assertEqual(code, 1, report)
        self.assertFalse(report["ok"])
        self.assertTrue(any(phrase in p for p in report["problems"]), report["problems"])
        return report

    # -- cases -----------------------------------------------------------

    def test_current_complete_ready_review_passes(self) -> None:
        code, report = self.run_verifier()
        self.assertEqual(code, 0, report)
        self.assertTrue(report["ok"])
        self.assertEqual(report["problems"], [])
        self.assertEqual(report["readiness"], "Ready to publish")
        for key, value in self.identity.items():
            self.assertEqual(report["identity"][key], value, key)
        self.assertTrue(report["identity"]["clean"])

    def test_base_given_as_a_sha_passes(self) -> None:
        code, report = self.run_verifier(base=self.identity["base_sha"])
        self.assertEqual(code, 0, report)

    def test_new_commit_after_review_makes_it_stale(self) -> None:
        (self.repo / "a.txt").write_text("one\ntwo\nthree\n")
        self.commit("After review")
        report = self.assert_fails("candidate")
        self.assertNotEqual(report["identity"]["head_sha"], self.identity["head_sha"])
        self.assert_fails("intent-checklist.json")

    def test_dirty_worktree_fails(self) -> None:
        (self.repo / "untracked.txt").write_text("x\n")
        self.assert_fails("worktree is not clean")

    def test_missing_ponytail_artifact_fails(self) -> None:
        (self.state / "review-ponytail.md").unlink()
        self.assert_fails("review-ponytail.md")

    def test_missing_risk_artifact_fails_when_risk_was_selected(self) -> None:
        self.write_review(dimensions="[standards, spec, risk]")
        self.assert_fails("review-risk.md")
        (self.state / "review-risk.md").write_text("# risk\n")
        code, report = self.run_verifier()
        self.assertEqual(code, 0, report)

    def test_unswept_criterion_fails(self) -> None:
        self.write_review(verdict="unswept")
        self.assert_fails("AC-1")

    def test_unmet_criterion_fails(self) -> None:
        self.write_review(verdict="unmet")
        self.assert_fails("AC-1")

    def test_not_ready_readiness_line_fails(self) -> None:
        self.write_review(readiness="Correction bound reached — do not merge")
        report = self.assert_fails("Ready to publish")
        self.assertEqual(report["readiness"], "Correction bound reached — do not merge")

    def test_no_summary_at_all_fails(self) -> None:
        (self.state / "summary.md").unlink()
        report = self.assert_fails("summary.md")
        self.assertIsNone(report["readiness"])

    def test_unreadable_checklist_is_a_problem_not_a_traceback(self) -> None:
        (self.state / "intent-checklist.json").write_text("{not json")
        self.assert_fails("intent-checklist.json")

    def test_missing_state_dir_and_unknown_base_are_problems(self) -> None:
        result = subprocess.run(
            [sys.executable, "-I", str(VERIFIER), "--state-dir", str(self.directory / "nope"),
             "--worktree", str(self.repo), "--base", "no-such-ref"],
            env=self.env, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")
        report = json.loads(result.stdout)
        self.assertFalse(report["ok"])
        self.assertTrue(any("no-such-ref" in p for p in report["problems"]), report["problems"])


if __name__ == "__main__":
    unittest.main()
