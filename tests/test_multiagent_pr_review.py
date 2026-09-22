#!/usr/bin/env python3
"""Contract and artifact tests for the multiagent PR review skill."""

from __future__ import annotations

import json
import hashlib
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
POOL = REPO_ROOT / "dot-agents" / "skills"
SKILL_ROOT = POOL / "multiagent-pr-review"
SKILL_PATH = SKILL_ROOT / "SKILL.md"
CLAUDE_AGENT = REPO_ROOT / "dot-claude" / "agents" / "multiagent-pr-lane-reviewer.md"
RECONCILER = REPO_ROOT / "scripts" / "reconcile-agent-skills.sh"
VALIDATOR = SKILL_ROOT / "scripts" / "validate-review-artifacts.py"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if line and not line.startswith((" ", "\t")) and ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    return fields


class MultiagentPrReviewContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = read(SKILL_PATH)
        cls.layout = read(SKILL_ROOT / "references" / "herdr-dual-review-layout.md")
        cls.orchestrator = read(
            SKILL_ROOT / "references" / "reviewer-orchestrator-contract.md"
        )
        cls.artifacts = read(SKILL_ROOT / "references" / "artifact-contract.md")
        cls.model_template = read(SKILL_ROOT / "templates" / "model-review.md")
        cls.adjudication_template = read(SKILL_ROOT / "templates" / "adjudication.md")
        cls.agent = read(CLAUDE_AGENT)

    def assert_matches(self, text: str, pattern: str, message: str) -> None:
        self.assertRegex(text, re.compile(pattern, re.IGNORECASE | re.DOTALL), message)

    def test_frontmatter_and_explicit_invocation(self) -> None:
        self.assertTrue(SKILL_PATH.is_file())
        fields = frontmatter(self.skill)
        self.assertEqual(fields.get("name"), "multiagent-pr-review")
        self.assertTrue(fields.get("description"))
        self.assertIn("GitHub PR", fields.get("description", ""))
        self.assertEqual(fields.get("argument-hint"), "<github-pr-url>")
        self.assertEqual(fields.get("disable-model-invocation"), "true")
        self.assert_matches(
            self.skill,
            r"explicit invocation only.*multiagent-pr-review\s+<github-pr-url>",
            "the body must repeat the explicit-only invocation contract",
        )

    def test_intake_is_github_teammate_only(self) -> None:
        self.assertIn("https://github.com/<owner>/<repo>/pull/<number>", self.skill)
        self.assert_matches(
            self.skill,
            r"self.authored|author.*authenticated.*pr-self-review",
            "self-authored PRs must route to pr-self-review",
        )
        for deferred in ("Forgejo", "local range"):
            with self.subTest(deferred=deferred):
                self.assert_matches(
                    self.skill,
                    rf"{re.escape(deferred)}.*(defer|out of scope|not supported)",
                    f"{deferred} must be explicitly deferred",
                )

    def test_exact_candidate_and_manifest_identity(self) -> None:
        for token in (
            "base_sha",
            "head_sha",
            "merge_base_sha",
            "diff_sha256",
            "expected_pr_head_ref",
            "evidence_manifest_sha256",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.skill)
        self.assertIn("git diff --binary -M -C --find-copies-harder", self.skill)

    def test_dual_model_gate_has_no_fallback_and_one_retry(self) -> None:
        self.assert_matches(
            self.skill,
            r"both.*Claude.*GPT.*reports.*required",
            "both model-family reports must be mandatory",
        )
        self.assert_matches(
            self.skill,
            r"one.*same.model.*retry|retry.*once.*same.model",
            "only one same-model retry may be offered",
        )
        self.assert_matches(
            self.skill,
            r"no model.family fallback|never.*fallback",
            "model-family fallback must be prohibited",
        )
        self.assert_matches(
            self.skill,
            r"missing|stale|model.mismatch.*INCOMPLETE.*no verdict",
            "an invalid report bundle must fail closed",
        )

    def test_both_reviewers_share_all_lanes_and_identity(self) -> None:
        for lane in ("standards", "spec", "correctness", "risk", "ponytail"):
            with self.subTest(lane=lane):
                self.assertIn(lane, self.orchestrator.lower())
        self.assert_matches(
            self.orchestrator,
            r"same.*candidate identity.*evidence manifest",
            "both reviewers must receive the same identity and evidence",
        )
        self.assert_matches(
            self.orchestrator,
            r"Ponytail.*after.*selected primary",
            "Ponytail must remain the final lane",
        )

    def test_reports_are_isolated_and_root_validates_leads(self) -> None:
        self.assert_matches(
            self.skill,
            r"reviewer outputs.*isolated|must not see each other",
            "reviewer outputs must stay isolated until both settle",
        )
        self.assert_matches(
            self.skill,
            r"leads.*independent|independently validat.*every",
            "the root must independently verify model leads",
        )
        self.assert_matches(
            self.skill,
            r"agreement|consensus.*not proof|not corroboration",
            "model agreement must not be treated as proof",
        )

    def test_herdr_layout_is_right_then_down_without_focus(self) -> None:
        self.assertIn("herdr-claude-handoff.md", self.layout)
        self.assert_matches(
            self.layout,
            r"split.*--pane.*HERDR_PANE_ID.*--direction right.*--ratio 0\.5.*--no-focus",
            "the first split must target the caller and preserve focus",
        )
        self.assert_matches(
            self.layout,
            r"split.*--pane.*claude.*pane.*--direction down.*--ratio 0\.5.*--no-focus",
            "the second split must target the returned Claude pane",
        )
        self.assert_matches(self.layout, r"Claude.*upper|top.*Claude", "Claude must be upper-right")
        self.assert_matches(self.layout, r"GPT.*lower|bottom.*GPT", "GPT must be lower-right")
        self.assert_matches(self.layout, r"two.*identity records|identity record.*each", "two identities are required")
        self.assert_matches(
            self.layout,
            r"one.*supervisor.*each|two.*supervisors",
            "two completion supervisors are required",
        )
        self.assert_matches(self.layout, r"no.*background.*substitut|no.*fallback", "background fallback is forbidden")
        self.assert_matches(self.layout, r"leave.*panes.*open|cleanup.*explicit", "panes remain until explicit cleanup")

    def test_watcher_completion_is_silent_report_gated_and_drained(self) -> None:
        self.assert_matches(
            self.layout,
            r"idle.*without.*report\.sidecar\.json.*intermediate|report\.sidecar\.json.*settled",
            "an orchestrator's intermediate idle state must not finish the watcher",
        )
        self.assert_matches(
            self.layout,
            r"notify=false|omit terminal completion notification",
            "same-turn reviewer supervisors must not emit late user notifications",
        )
        self.assert_matches(
            self.layout,
            r"one silent owned process|one.*process.*each|two distinct supervisors",
            "each reviewer must have one owned supervisor rather than one process per stage",
        )
        self.assert_matches(
            self.skill + self.layout,
            r"before present(?:ing|ation).*process.*(?:exited|closed|resolve)|resolve every.*process handle",
            "all owned background processes must be drained before the final review",
        )

    def test_candidate_drift_requires_user_choice(self) -> None:
        self.assert_matches(
            self.skill,
            r"candidate drift|remote.*head.*moved",
            "remote-head drift must be detected",
        )
        self.assert_matches(
            self.skill,
            r"ask.*Bryan|user choice",
            "drift must return to the user",
        )
        self.assert_matches(
            self.skill,
            r"do not restart automatically|never.*automatic.*restart",
            "drift must never trigger an automatic restart",
        )

    def test_pr_and_teammate_branch_are_read_only(self) -> None:
        self.assert_matches(
            self.skill,
            r"PR.*branch.*GitHub.*read.only|read.only.*GitHub",
            "GitHub and the teammate branch must remain read-only",
        )
        for action in ("comment", "approve", "request-changes", "edit", "commit", "push"):
            with self.subTest(action=action):
                self.assert_matches(
                    self.skill,
                    rf"(never|do not|prohibit)[^\n]*{re.escape(action)}",
                    f"the skill must explicitly prohibit {action}",
                )

    def test_artifact_contract_has_two_advisories_and_one_canonical_note(self) -> None:
        self.assertIn("canonical: false", self.model_template)
        self.assertIn("status: advisory", self.model_template)
        self.assertIn("canonical: true", self.adjudication_template)
        for path in (
            "claude.md",
            "gpt.md",
            "adjudication.md",
            "reviews/INDEX.md",
        ):
            with self.subTest(path=path):
                self.assertIn(path, self.artifacts)
        self.assert_matches(
            self.artifacts,
            r"root.*(only|alone).*(write|copy|synchron)",
            "only the root may mutate the vault",
        )
        self.assert_matches(
            self.artifacts,
            r"immutable.*advisory|advisory.*never overwritten",
            "advisory notes must be immutable",
        )

    def test_templates_capture_identity_route_and_dispositions(self) -> None:
        for token in (
            "pr_url",
            "repository",
            "pr_number",
            "author",
            "base_sha",
            "head_sha",
            "merge_base_sha",
            "diff_sha256",
            "evidence_manifest_sha256",
            "reviewer_family",
            "provider",
            "primary_model",
            "models_used",
            "agent_name",
            "pane_id",
            "runtime_session_id",
            "selected_lanes",
            "risk_reason",
            "generated_at",
        ):
            with self.subTest(model_field=token):
                self.assertIn(token, self.model_template)
        for token in (
            "COMPLETE",
            "INCOMPLETE",
            "STALE",
            "UNSTABLE",
            "Confirmed Findings",
            "Rejected Leads",
            "Unresolved Leads",
            "Acceptance-Criteria Sweep",
            "Changed-File and Omission Sweep",
        ):
            with self.subTest(adjudication_field=token):
                self.assertIn(token, self.adjudication_template)

    def test_claude_lane_agent_is_opus_and_confined(self) -> None:
        self.assertTrue(CLAUDE_AGENT.is_file())
        fields = frontmatter(self.agent)
        self.assertEqual(fields.get("model"), "opus")
        self.assertIn("Write", fields.get("tools", ""))
        for lane in ("standards", "spec", "correctness", "risk", "ponytail"):
            self.assertIn(f"`{lane}`", self.agent)
        self.assertIn("code-review", self.agent)
        self.assertIn("evidence_manifest_sha256", self.agent)
        self.assert_matches(self.agent, r"only.*reviewer state root|write only.*state root", "writes must be confined")
        self.assert_matches(self.agent, r"untrusted data", "PR-provided text must be data")
        self.assert_matches(self.agent, r"sidecar", "each lane must emit an identity/hash sidecar")

    def test_expected_linked_files_exist_and_markdown_links_resolve(self) -> None:
        expected = (
            SKILL_ROOT / "references" / "reviewer-orchestrator-contract.md",
            SKILL_ROOT / "references" / "herdr-dual-review-layout.md",
            SKILL_ROOT / "references" / "artifact-contract.md",
            SKILL_ROOT / "templates" / "model-review.md",
            SKILL_ROOT / "templates" / "adjudication.md",
            SKILL_ROOT / "scripts" / "validate-review-artifacts.py",
            CLAUDE_AGENT,
        )
        for path in expected:
            with self.subTest(path=path):
                self.assertTrue(path.is_file(), f"missing {path.relative_to(REPO_ROOT)}")

        # Resolve authored documentation links. Template links are intentionally
        # candidate-relative and do not exist until the vault notes are rendered.
        for source in (SKILL_PATH, *expected[:3]):
            text = read(source)
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
                if target.startswith(("http://", "https://", "#")):
                    continue
                resolved = (source.parent / target.split("#", 1)[0]).resolve()
                with self.subTest(source=source.name, target=target):
                    self.assertTrue(resolved.exists(), f"broken link {source}: {target}")

    def test_root_skill_is_curated_for_hermes_only(self) -> None:
        reconciler = read(RECONCILER)
        arrays = {}
        for name in ("COMMON_SKILLS", "ADAPTED_CORES", "PI_SKILLS", "CLAUDE_SKILLS", "OPENCODE_SKILLS", "HERMES_SKILLS"):
            match = re.search(
                rf"^{name}=\((.*?)\)\s*$", reconciler, re.DOTALL | re.MULTILINE
            )
            arrays[name] = match.group(1) if match else ""
        self.assertIn("multiagent-pr-review", arrays["HERMES_SKILLS"])
        for name in ("COMMON_SKILLS", "ADAPTED_CORES", "PI_SKILLS", "CLAUDE_SKILLS", "OPENCODE_SKILLS"):
            with self.subTest(array=name):
                self.assertNotIn("multiagent-pr-review", arrays[name])


class ReviewArtifactValidatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name) / "state"
        self.root.mkdir()
        self.candidate = {
            "base_sha": "a" * 40,
            "head_sha": "b" * 40,
            "merge_base_sha": "c" * 40,
            "diff_sha256": "d" * 64,
        }
        evidence = self.root / "evidence" / "candidate.diff"
        evidence.parent.mkdir()
        evidence.write_text("diff --git a/a b/a\n", encoding="utf-8")
        self.manifest_path = self.root / "evidence-manifest.json"
        self.manifest = {
            "pr_url": "https://github.com/acme/widget/pull/42",
            "expected_pr_head_ref": "feature/review-me",
            "candidate_identity": self.candidate,
            "lane_selection": {
                "risk_selected": True,
                "risk_reason": "changed authentication path",
            },
            "files": [
                {
                    "path": "evidence/candidate.diff",
                    "sha256": self.sha256(evidence),
                }
            ],
        }
        self.write_json(self.manifest_path, self.manifest)
        self.manifest_sha = self.sha256(self.manifest_path)
        self.sidecars = {
            family: self.create_report_bundle(family) for family in ("claude", "gpt")
        }

    @staticmethod
    def sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def write_json(path: Path, value: object) -> None:
        path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")

    def lane_markdown(self, family: str, lane: str) -> str:
        identity = "\n".join(f"{key}: {value}" for key, value in self.candidate.items())
        return (
            "---\n"
            f"lane: {lane}\n"
            f"reviewer_family: {family}\n"
            f"evidence_manifest_sha256: {self.manifest_sha}\n"
            f"{identity}\n"
            "---\n\n"
            "## Summary\n\nNo findings.\n"
        )

    def report_markdown(self, family: str) -> str:
        identity = "\n".join(f"{key}: {value}" for key, value in self.candidate.items())
        return (
            "---\n"
            "type: multiagent-pr-model-review\n"
            "status: advisory\n"
            "canonical: false\n"
            f"pr_url: {self.manifest['pr_url']}\n"
            f"reviewer_family: {family}\n"
            f"evidence_manifest_sha256: {self.manifest_sha}\n"
            f"{identity}\n"
            "---\n\n"
            "# Model-family advisory review\n\n"
            "Advisory findings are not yet root-confirmed.\n"
        )

    def create_report_bundle(self, family: str) -> Path:
        family_root = self.root / family
        lane_root = family_root / "lanes"
        lane_root.mkdir(parents=True)
        lanes = ["standards", "spec", "correctness", "risk", "ponytail"]
        lane_artifacts = []
        for lane in lanes:
            path = lane_root / f"{lane}.md"
            path.write_text(self.lane_markdown(family, lane), encoding="utf-8")
            lane_artifacts.append(
                {
                    "lane": lane,
                    "path": str(path.relative_to(self.root)),
                    "sha256": self.sha256(path),
                }
            )

        report_path = family_root / "report.md"
        report_path.write_text(self.report_markdown(family), encoding="utf-8")
        model = "claude-opus-4-1" if family == "claude" else "gpt-5.6"
        provider = "anthropic" if family == "claude" else "openai"
        sidecar = {
            "reviewer_family": family,
            "provider": provider,
            "primary_model": model,
            "models_used": [model],
            "candidate_identity": self.candidate,
            "evidence_manifest_sha256": self.manifest_sha,
            "required_lanes": lanes,
            "lane_artifacts": lane_artifacts,
            "report_path": str(report_path.relative_to(self.root)),
            "report_sha256": self.sha256(report_path),
            "route_evidence": {
                "surface": "herdr",
                "agent_name": f"review-{family}",
                "pane_id": f"pane-{family}",
                "runtime_session_id": f"session-{family}",
            },
        }
        sidecar_path = family_root / "report.json"
        self.write_json(sidecar_path, sidecar)
        return sidecar_path

    def load_sidecar(self, family: str) -> dict:
        return json.loads(self.sidecars[family].read_text(encoding="utf-8"))

    def save_sidecar(self, family: str, sidecar: dict) -> None:
        self.write_json(self.sidecars[family], sidecar)

    def run_validator(
        self,
        families: tuple[str, ...] = ("claude", "gpt"),
        sidecar_families: tuple[str, ...] | None = None,
        manifest_sha: str | None = None,
    ) -> tuple[int, dict]:
        if sidecar_families is None:
            sidecar_families = families
        command = [
            sys.executable,
            str(VALIDATOR),
            "--state-root",
            str(self.root),
            "--manifest",
            str(self.manifest_path),
            "--manifest-sha256",
            manifest_sha or self.manifest_sha,
        ]
        for family in sidecar_families:
            command.extend(("--report-sidecar", str(self.sidecars[family])))
        patterns = {
            "claude": r"^claude-opus-",
            "gpt": r"^gpt-",
        }
        for family in families:
            command.extend(("--expected-model", f"{family}={patterns[family]}"))
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError:
            result = {"stdout": completed.stdout, "stderr": completed.stderr}
        return completed.returncode, result

    def assert_error(self, code: str, **kwargs: Any) -> None:
        returncode, result = self.run_validator(**kwargs)
        self.assertNotEqual(returncode, 0)
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("status"), "INCOMPLETE")
        self.assertEqual(result.get("error"), code)

    def test_valid_single_report_is_admitted(self) -> None:
        returncode, result = self.run_validator(
            families=("claude",), sidecar_families=("claude",)
        )
        self.assertEqual(returncode, 0, result)
        self.assertEqual(result.get("status"), "ADMITTED")
        self.assertEqual(result.get("reviewer_family"), "claude")
        self.assertEqual(result.get("report_sha256"), self.load_sidecar("claude")["report_sha256"])

    def test_complete_dual_report_bundle(self) -> None:
        returncode, result = self.run_validator()
        self.assertEqual(returncode, 0, result)
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("status"), "COMPLETE")
        self.assertEqual(
            [report["reviewer_family"] for report in result.get("reports", [])],
            ["claude", "gpt"],
        )

    def test_report_candidate_mismatch_is_rejected(self) -> None:
        report = self.root / self.load_sidecar("claude")["report_path"]
        report.write_text(
            report.read_text(encoding="utf-8").replace("base_sha: " + "a" * 40, "base_sha: " + "e" * 40),
            encoding="utf-8",
        )
        sidecar = self.load_sidecar("claude")
        sidecar["report_sha256"] = self.sha256(report)
        self.save_sidecar("claude", sidecar)
        self.assert_error("CANDIDATE_MISMATCH", families=("claude",), sidecar_families=("claude",))

    def test_lane_candidate_mismatch_is_rejected(self) -> None:
        sidecar = self.load_sidecar("claude")
        lane = self.root / sidecar["lane_artifacts"][0]["path"]
        lane.write_text(
            lane.read_text(encoding="utf-8").replace("head_sha: " + "b" * 40, "head_sha: " + "e" * 40),
            encoding="utf-8",
        )
        sidecar["lane_artifacts"][0]["sha256"] = self.sha256(lane)
        self.save_sidecar("claude", sidecar)
        self.assert_error("CANDIDATE_MISMATCH", families=("claude",), sidecar_families=("claude",))

    def test_evidence_manifest_hash_mismatch_is_rejected(self) -> None:
        self.assert_error("MANIFEST_HASH_MISMATCH", manifest_sha="0" * 64)

    def test_missing_selected_lane_is_rejected(self) -> None:
        sidecar = self.load_sidecar("claude")
        sidecar["lane_artifacts"] = [
            item for item in sidecar["lane_artifacts"] if item["lane"] != "risk"
        ]
        self.save_sidecar("claude", sidecar)
        self.assert_error("MISSING_LANE", families=("claude",), sidecar_families=("claude",))

    def test_unexpected_risk_placeholder_is_rejected(self) -> None:
        self.manifest["lane_selection"]["risk_selected"] = False
        self.manifest["lane_selection"]["risk_reason"] = "no risk signal"
        self.write_json(self.manifest_path, self.manifest)
        self.manifest_sha = self.sha256(self.manifest_path)
        sidecar = self.load_sidecar("claude")
        sidecar["evidence_manifest_sha256"] = self.manifest_sha
        self.save_sidecar("claude", sidecar)
        self.assert_error("UNEXPECTED_LANE", families=("claude",), sidecar_families=("claude",))

    def test_wrong_reviewer_family_is_rejected(self) -> None:
        sidecar = self.load_sidecar("claude")
        sidecar["reviewer_family"] = "gpt"
        self.save_sidecar("claude", sidecar)
        self.assert_error("WRONG_REVIEWER_FAMILY", families=("claude",), sidecar_families=("claude",))

    def test_disallowed_observed_model_is_rejected(self) -> None:
        sidecar = self.load_sidecar("claude")
        sidecar["models_used"].append("claude-sonnet-4")
        self.save_sidecar("claude", sidecar)
        self.assert_error("MODEL_MISMATCH", families=("claude",), sidecar_families=("claude",))

    def test_empty_route_identity_is_rejected(self) -> None:
        sidecar = self.load_sidecar("claude")
        sidecar["route_evidence"]["runtime_session_id"] = ""
        self.save_sidecar("claude", sidecar)
        self.assert_error("ROUTE_INCOMPLETE", families=("claude",), sidecar_families=("claude",))

    def test_report_hash_mismatch_is_rejected(self) -> None:
        sidecar = self.load_sidecar("claude")
        sidecar["report_sha256"] = "0" * 64
        self.save_sidecar("claude", sidecar)
        self.assert_error("REPORT_HASH_MISMATCH", families=("claude",), sidecar_families=("claude",))

    def test_lane_hash_mismatch_is_rejected(self) -> None:
        sidecar = self.load_sidecar("claude")
        sidecar["lane_artifacts"][0]["sha256"] = "0" * 64
        self.save_sidecar("claude", sidecar)
        self.assert_error("LANE_HASH_MISMATCH", families=("claude",), sidecar_families=("claude",))

    def test_non_advisory_frontmatter_is_rejected(self) -> None:
        report = self.root / self.load_sidecar("claude")["report_path"]
        report.write_text(
            report.read_text(encoding="utf-8").replace("canonical: false", "canonical: true"),
            encoding="utf-8",
        )
        sidecar = self.load_sidecar("claude")
        sidecar["report_sha256"] = self.sha256(report)
        self.save_sidecar("claude", sidecar)
        self.assert_error("INVALID_FRONTMATTER", families=("claude",), sidecar_families=("claude",))

    def test_symlink_escape_is_rejected(self) -> None:
        sidecar = self.load_sidecar("claude")
        report = self.root / sidecar["report_path"]
        outside = Path(self.temp_dir.name) / "outside.md"
        outside.write_text(self.report_markdown("claude"), encoding="utf-8")
        report.unlink()
        report.symlink_to(outside)
        sidecar["report_sha256"] = self.sha256(outside)
        self.save_sidecar("claude", sidecar)
        self.assert_error("PATH_ESCAPE", families=("claude",), sidecar_families=("claude",))

    def test_missing_second_report_yields_incomplete_bundle(self) -> None:
        self.assert_error("MISSING_REPORT", sidecar_families=("claude",))


if __name__ == "__main__":
    unittest.main()
