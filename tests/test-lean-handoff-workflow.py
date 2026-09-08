#!/usr/bin/env python3
"""Contracts for the lean Claude handoff workflow."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POOL = ROOT / "dot-agents" / "skills"


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


class LeanIssueWorkContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.issue_work = read("dot-agents/skills/issue-work/SKILL.md")
        cls.handoff = read("dot-agents/skills/coding-agent-handoff-supervision/SKILL.md")
        cls.review = read("dot-agents/skills/pr-self-review/SKILL.md")
        cls.code_review = read("dot-agents/skills/code-review/SKILL.md")
        cls.ship = read("dot-agents/skills/ship/SKILL.md")
        cls.lane_reviewer = read("dot-claude/agents/lane-reviewer.md")
        cls.helper_reference = read(
            "dot-agents/skills/coding-agent-handoff-supervision/"
            "references/herdr-claude-handoff.md"
        )

    def test_exploration_is_conditional(self) -> None:
        self.assertIn("zero exploration children", self.issue_work)
        self.assertNotIn("**always** at least one", self.issue_work)

    def test_imperative_work_command_carries_reviewable_pr_authority(self) -> None:
        self.assertIn("imperative `work <issue URL>`", self.issue_work)
        self.assertIn("reviewable PR", self.issue_work)
        self.assertIn("does not authorize merge", self.issue_work)

    def test_auto_routing_right_sizes_single_loop_work(self) -> None:
        self.assertIn("--task-shape", self.issue_work)
        self.assertIn("single-loop", self.issue_work)
        self.assertIn("substantial", self.issue_work)
        self.assertIn("single-loop", self.handoff)

    def test_parent_acceptance_is_the_normal_final_gate(self) -> None:
        self.assertRegex(
            self.issue_work,
            r"(?is)the Sol parent\s+is the independent acceptance\s+context",
        )
        self.assertIn("one integrated review", self.review.lower())
        self.assertNotIn("must launch a fresh visible Claude reviewer", self.issue_work)

    def test_review_runs_in_one_context_with_risk_deepening(self) -> None:
        self.assertIn("one review context", self.code_review.lower())
        self.assertIn("targeted Risk reviewer", self.code_review)
        self.assertNotIn("parallel children", self.code_review)

    def test_correction_bound_is_two_without_terminal_review_only(self) -> None:
        self.assertIn("one normal correction", self.review)
        self.assertIn("one conditional second correction", self.review)
        self.assertIn("never a third correction", self.review)
        self.assertNotIn("final_review_only", self.review)

    def test_one_correction_counter_spans_implementation_and_review(self) -> None:
        self.assertIn("global `correction_passes` counter", self.issue_work)
        self.assertIn("`correction_passes_consumed`", self.issue_work)
        self.assertIn("`correction_passes_consumed`", self.review)
        self.assertIn("must not reset it", self.review)

    def test_blocked_worker_has_validated_read_and_answer_operations(self) -> None:
        helper = read(
            "dot-agents/skills/coding-agent-handoff-supervision/"
            "scripts/herdr_worker.py"
        )
        self.assertIn('subparsers.add_parser("read")', helper)
        self.assertIn('subparsers.add_parser("answer-blocked")', helper)
        self.assertIn('subparsers.add_parser("recover-start")', helper)
        self.assertIn("state_change_seq", helper)
        self.assertIn("agent_not_found", helper)
        self.assertIn("pane_not_found", helper)
        self.assertIn("pre_split_pane_ids", helper)
        self.assertIn('record["closing"] = True', helper)
        self.assertIn("answer-blocked", self.helper_reference)
        self.assertNotIn("--caller-pane", helper)

    def test_cross_repository_reviewer_admits_validated_ticket_state(self) -> None:
        for field in (
            "ticket_trunk_root",
            "state_dir",
            "context_validation_path",
            "context_validator_path",
            "validate_cross_repo_context.py",
        ):
            with self.subTest(field=field):
                self.assertIn(field, self.lane_reviewer)
        self.assertIn("exact validated ticket state directory", self.lane_reviewer)

    def test_ship_has_narrow_issue_work_authority_mode(self) -> None:
        self.assertIn("issue-work-authorized", self.ship)
        self.assertIn("existing same-branch PR", self.ship)
        self.assertIn("skip labels", self.ship.lower())
        self.assertIn("generic mode", self.ship.lower())

    def test_metrics_are_compact_and_required(self) -> None:
        for field in (
            "claude_prompts",
            "correction_passes",
            "review_invocations",
            "elapsed_to_reviewable_pr_seconds",
            "blocking_findings_after_initial_review",
            "provider_capacity_start",
            "provider_capacity_end",
            "quota_interruptions",
            "escaped_critical_major",
        ):
            with self.subTest(field=field):
                self.assertIn(field, self.issue_work)
        self.assertIn("issue-work-efficiency-pilot.json", self.issue_work)
        self.assertIn("record_efficiency.py", self.issue_work)

    def test_herdr_mechanics_have_one_script_owner(self) -> None:
        helper = POOL / "coding-agent-handoff-supervision" / "scripts" / "herdr_worker.py"
        tests = POOL / "coding-agent-handoff-supervision" / "tests" / "test_herdr_worker.py"
        self.assertTrue(helper.is_file())
        self.assertTrue(tests.is_file())
        self.assertIn("herdr_worker.py", self.handoff)
        self.assertIn("herdr_worker.py", read(
            "dot-agents/skills/coding-agent-handoff-supervision/references/herdr-claude-handoff.md"
        ))


if __name__ == "__main__":
    unittest.main()
