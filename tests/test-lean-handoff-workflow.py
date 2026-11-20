#!/usr/bin/env python3
"""Contracts for the lean Claude handoff workflow."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_POOL = ROOT / "dot-agents" / "skills"


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


class LeanIssueWorkContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.issue_work = read("dot-agents/skills/issue-work/SKILL.md")
        cls.handoff = read("dot-agents/skills/coding-agent-handoff-supervision/SKILL.md")
        cls.review = read("dot-agents/skills/pr-self-review/SKILL.md")
        cls.code_review = read("dot-agents/skills/pr-self-review/references/review-contract.md")
        cls.ship = read("dot-agents/skills/ship/SKILL.md")
        cls.dimension_reviewer = read("dot-claude/agents/dimension-reviewer.md")
        cls.helper_reference = read(
            "dot-agents/skills/coding-agent-handoff-supervision/"
            "references/rex-claude-handoff.md"
        )

    def test_exploration_is_conditional(self) -> None:
        self.assertIn("zero exploration background agents", self.issue_work)
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
            r"(?is)the orchestrator\s+is the independent acceptance\s+context",
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

    def test_blocked_background_agent_is_read_checked_and_answered_only_from_authority(self) -> None:
        ref = " ".join(self.helper_reference.split())
        self.assertIn("A background agent blocked on a permission or question shows it in `capture`", ref)
        self.assertIn("Answer only what the governing plan already settles", ref)
        self.assertIn("anything new goes to Bryan", ref)
        self.assertIn("before every `send`", ref)
        self.assertIn("block inspect", ref)
        self.assertIn("Confirm a new `user` record in the transcript", ref)
        self.assertIn("Never resend a prompt merely to regain a completion signal", ref)
        self.assertIn("close only the recorded pane", ref)
        self.assertIn("expect 0", ref)

    def test_cross_repository_reviewer_admits_validated_ticket_state(self) -> None:
        for field in (
            "ticket_trunk_root",
            "state_dir",
            "context_validation_path",
            "context_validator_path",
            "validate_cross_repo_context.py",
        ):
            with self.subTest(field=field):
                self.assertIn(field, self.dimension_reviewer)
        self.assertIn("exact validated issue state directory", self.dimension_reviewer)

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

    def test_rex_mechanics_have_script_owners(self) -> None:
        skill = SKILL_POOL / "coding-agent-handoff-supervision"
        self.assertEqual(
            sorted(p.name for p in (skill / "scripts").iterdir() if p.suffix in (".py", ".sh")),
            # rex_subagent_slot.py is a fake at the old name, for launchers written before the renames.
            ["claude-usage.sh", "rex_background_agent_pane.py", "rex_subagent_slot.py", "rex_wait.sh"],
        )
        self.assertEqual(
            sorted(p.name for p in (skill / "tests").glob("test_*.py")),
            ["test_rex_background_agent_pane.py", "test_rex_wait.py"],
        )
        self.assertTrue((skill / "scripts" / "rex_wait.sh").stat().st_mode & 0o111)
        self.assertIn("references/rex-claude-handoff.md", self.handoff)
        for script in ("rex_background_agent_pane.py", "rex_wait.sh"):
            with self.subTest(script=script):
                self.assertIn(script, self.handoff)
                self.assertIn(script, self.helper_reference)


class SelfReviewGateContractTests(unittest.TestCase):
    """A draft PR reaches Bryan only after pr-self-review passed on its exact head (Bryan, 2026-11-20)."""

    VERIFIER = "check_self_review.py"

    @classmethod
    def setUpClass(cls) -> None:
        cls.issue_work = read("dot-agents/skills/issue-work/SKILL.md")
        cls.handoff = read("dot-agents/skills/coding-agent-handoff-supervision/SKILL.md")
        cls.review = read("dot-agents/skills/pr-self-review/SKILL.md")
        cls.ship = read("dot-agents/skills/ship/SKILL.md")
        cls.pi_rules = read("dot-pi/agent/AGENTS.md")

    @staticmethod
    def section(text: str, heading: str) -> str:
        """The body under `heading`, up to the next heading of its level or higher, whitespace collapsed."""
        level = len(heading.split(" ")[0])
        lines = text[text.index(heading) + len(heading):].splitlines()
        body, fenced = [], False
        for line in lines:
            if line.startswith("```"):
                fenced = not fenced
            elif not fenced and line.startswith("#") and len(line.split(" ")[0]) <= level:
                break
            body.append(line)
        return " ".join(" ".join(body).split())

    def test_verifier_script_exists_beside_the_classifier(self) -> None:
        script = SKILL_POOL / "pr-self-review" / "scripts" / self.VERIFIER
        self.assertTrue(script.is_file())
        self.assertTrue(script.stat().st_mode & 0o111)

    def test_issue_work_gates_sit_before_the_phases(self) -> None:
        gates = self.section(self.issue_work, "## Gates")
        self.assertLess(self.issue_work.index("## Gates"), self.issue_work.index("## Phase 1"))
        for phrase in ("to the end", "Phases 4 and 5", "validate_cross_repo_context.py",
                       "`pre-pr`", self.VERIFIER, "`ship`", "gh pr create", "final review"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, gates)

    def test_issue_work_names_the_verifier_where_it_runs(self) -> None:
        self.assertIn(self.VERIFIER, self.section(self.issue_work, "### 2. Run bounded self-review"))
        publish = self.section(self.issue_work, "## Phase 5")
        self.assertIn(self.VERIFIER, publish)
        self.assertIn("`pr-url`", publish)
        self.assertRegex(publish, r"(?s)pr-self-review.{0,80}SKILL\.md")
        self.assertIn("own review brief", publish)

    def test_handoff_step_five_loads_the_review_and_ends_on_the_verifier(self) -> None:
        step = self.section(self.handoff, "### 5. Treat completion as a claim")
        self.assertIn("read it in full", step)
        self.assertIn("is not that review", step)
        self.assertIn(self.VERIFIER, step.split("Complete when")[-1])
        checklist = self.section(self.handoff, "## Verification Checklist")
        self.assertIn(self.VERIFIER, checklist)

    def test_ship_runs_the_verifier_and_owns_pr_creation(self) -> None:
        step = self.section(self.ship, "### 2. Verify the branch and exact-candidate review")
        self.assertIn(self.VERIFIER, step)
        self.assertIn("outside this skill", step)

    def test_self_review_exits_through_the_verifier(self) -> None:
        exit_step = self.section(self.review, "## 8. Write summary and exit")
        self.assertIn(self.VERIFIER, exit_step)
        self.assertIn("exits 0", exit_step)
        self.assertIn(self.VERIFIER, self.section(self.review, "## Verification Checklist"))

    def test_pi_rules_hold_the_gate(self) -> None:
        rule = next(line for line in self.pi_rules.splitlines() if self.VERIFIER in line)
        self.assertIn("(Bryan, 2026-11-20)", rule)
        self.assertIn("readiness line", rule)
        self.assertIn("hand-written brief", rule)


if __name__ == "__main__":
    unittest.main()
