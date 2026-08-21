#!/usr/bin/env python3
"""Contract tests for the adapted planning/delivery skill topology.

These lock the *accepted target* from the reviewed adoption plan. Ordinary
explanatory prose may be rewritten freely, but workflow phase headings,
canonical output strings, and fail-closed shell shapes asserted below are
load-bearing contract surfaces:
adapted upstream cores under `dot-agents/skills/`, a machine-readable
provenance ledger, deterministic review-lane selection, curation that
matches the intended per-runtime roles, and a timestamp-free upstream
monitor. They deliberately assert structure and authority wording, not
prose style — a skill body may be rewritten freely as long as the
contract below still holds.

Run: python3 -m unittest tests/test-adapted-agent-skills.py
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
POOL = REPO_ROOT / "dot-agents" / "skills"
UPSTREAMS = REPO_ROOT / "dot-agents" / "upstreams"
LEDGER_PATH = UPSTREAMS / "mattpocock-skills.json"
LICENSE_PATH = UPSTREAMS / "mattpocock-skills-LICENSE"
RECONCILER = REPO_ROOT / "scripts" / "reconcile-agent-skills.sh"

# The cores this plan adds. `guided-learning` is deliberately Hermes-only
# until real use earns wider distribution.
ADAPTED_CORES = (
    "grilling",
    "wayfinder",
    "tdd",
    "diagnosing-bugs",
    "code-review",
    "codebase-architecture",
)
HERMES_ONLY_CORES = ("guided-learning",)
ALL_NEW_SKILLS = ADAPTED_CORES + HERMES_ONLY_CORES

# Routes retired by this plan. A name may still appear in prose that
# explicitly marks it as history; see `_HISTORICAL_MARKERS`.
RETIRED_ROUTES = (
    "git-master",
    "agent-workspace",
    "requesting-code-review",
    "test-driven-development",
    "systematic-debugging",
)
# Stems, matched case-insensitively: "replac" covers replace / replaces /
# replaced / replacing, all of which mark a mention as history rather than
# a live route.
_HISTORICAL_MARKERS = (
    "retired",
    "replac",
    "historical",
    "no longer",
    "formerly",
)

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def frontmatter_fields(path: Path) -> dict[str, str]:
    """Parse the flat scalar keys of a SKILL.md frontmatter block.

    Deliberately not a YAML parser: skills use folded (`>`) descriptions
    and quoted strings, and the only thing under test is which top-level
    keys exist and their first-line values.
    """
    match = FRONTMATTER.match(read(path))
    if not match:
        return {}
    fields: dict[str, str] = {}
    key = None
    for line in match.group(1).splitlines():
        if line[:1] not in (" ", "\t") and ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            fields[key] = value.strip()
        elif key is not None and line.strip():
            fields[key] = (fields[key] + " " + line.strip()).strip()
    return fields


def skill_dirs() -> list[Path]:
    return sorted(p for p in POOL.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())


# Arrays in the reconciler that are *not* a per-tool curation list. They are
# inputs to one (a shared set of names) or operational allowlists, so asserting
# curation rules against them is a category error.
_NON_CURATION_ARRAYS = frozenset({"ADAPTED_CORES", "RETIRED_POOL_TARGETS"})


def curation_arrays() -> dict[str, list[str]]:
    """The reconciler's per-tool curation arrays, with `${…[@]}` expanded.

    The reconciler is the single curation authority, so the contract is asserted
    against its literal arrays rather than a mirrored list. Every uppercase array
    is parsed so expansions resolve, but only the curation ones are returned.
    """
    text = read(RECONCILER)
    parsed: dict[str, list[str]] = {}
    for match in re.finditer(r"^([A-Z_]+)=\((.*?)\)\s*$", text, re.DOTALL | re.MULTILINE):
        name, body = match.group(1), match.group(2)
        tokens: list[str] = []
        for token in body.split():
            token = token.strip().strip('"')
            expand = re.fullmatch(r"\$\{([A-Z_]+)\[@\]\}", token)
            if expand:
                tokens.extend(parsed.get(expand.group(1), []))
            elif token and not token.startswith("#"):
                tokens.append(token)
        parsed[name] = tokens
    return {
        name: members
        for name, members in parsed.items()
        if name not in _NON_CURATION_ARRAYS
    }


def outside_code_fences(text: str) -> str:
    """Drop fenced code blocks — links inside them are illustrations."""
    kept, fenced = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            kept.append(line)
    return "\n".join(kept)


def active_markdown() -> list[Path]:
    """Every markdown surface that routes live agent behavior."""
    paths = sorted(POOL.glob("*/SKILL.md"))
    paths += sorted(POOL.glob("*/references/*.md"))
    paths += sorted((REPO_ROOT / "dot-config" / "opencode" / "agents").glob("*.md"))
    paths += sorted((REPO_ROOT / "dot-claude" / "agents").glob("*.md"))
    # The Git-backed Hermes pool routes too, and it is ours to change —
    # including its worker scripts, which select skills by name at launch.
    paths += sorted((REPO_ROOT / "hermes" / "skills").glob("*/*/SKILL.md"))
    paths += sorted((REPO_ROOT / "hermes" / "skills").glob("*/*/scripts/*.py"))
    paths.append(REPO_ROOT / "dot-agents" / "README.md")
    return [p for p in paths if p.is_file()]



class _MatchMixin:
    """assertRegex dumps whole skill bodies on failure; keep failures readable."""

    def assert_matches(self, body: str, pattern: str, message: str) -> None:
        self.assertTrue(re.search(pattern, body), message)

    def assert_not_matches(self, body: str, pattern: str, message: str) -> None:
        self.assertFalse(re.search(pattern, body), message)


class SkillFrontmatterTest(unittest.TestCase):
    """Every pooled skill must be discoverable by every runtime."""

    def test_every_pool_skill_has_name_and_description(self) -> None:
        for skill in skill_dirs():
            with self.subTest(skill=skill.name):
                fields = frontmatter_fields(skill / "SKILL.md")
                self.assertTrue(fields, f"{skill.name}/SKILL.md has no YAML frontmatter")
                self.assertEqual(
                    fields.get("name"),
                    skill.name,
                    f"{skill.name}/SKILL.md frontmatter name must match its directory",
                )
                self.assertTrue(
                    (fields.get("description") or "").strip(),
                    f"{skill.name}/SKILL.md needs a non-empty description",
                )

    def test_new_cores_exist(self) -> None:
        for name in ALL_NEW_SKILLS:
            with self.subTest(skill=name):
                self.assertTrue(
                    (POOL / name / "SKILL.md").is_file(),
                    f"expected adapted skill {name} in the canonical pool",
                )

    def test_orchestration_skills_require_explicit_invocation(self) -> None:
        """`grilling`, `wayfinder`, and `guided-learning` never auto-start.

        Claude reads `disable-model-invocation`; Hermes and OpenCode do
        not, so the *body* must carry the same rule in prose for the
        runtimes that ignore the frontmatter key.
        """
        for name in ("grilling", "wayfinder", "guided-learning"):
            with self.subTest(skill=name):
                path = POOL / name / "SKILL.md"
                fields = frontmatter_fields(path)
                self.assertEqual(
                    fields.get("disable-model-invocation"),
                    "true",
                    f"{name} must set disable-model-invocation: true for Claude",
                )
                body = read(path).lower()
                self.assertIn(
                    "explicit",
                    body,
                    f"{name} must state its explicit-invocation rule in the body "
                    "for runtimes that ignore the frontmatter key",
                )

    def test_model_invoked_primitives_stay_model_invocable(self) -> None:
        """The delivery primitives load when their trigger is genuinely present."""
        for name in ("tdd", "diagnosing-bugs", "code-review", "codebase-architecture"):
            with self.subTest(skill=name):
                fields = frontmatter_fields(POOL / name / "SKILL.md")
                self.assertNotIn(
                    "disable-model-invocation",
                    fields,
                    f"{name} is a primitive and must remain model-invocable",
                )

    def test_relative_links_resolve(self) -> None:
        """A disclosed reference that does not resolve is a dead route.

        Scoped to the skills this plan owns. Legacy skills carry
        illustrative markdown in their examples (`](Note.md)`,
        `](target)`) that is documentation, not a link to follow.
        """
        owned = set(ALL_NEW_SKILLS) | {
            "pr-self-review",
            "worktrunk",
            "issue-work",
            "issue-create",
            "skill-retrospective",
        }
        link = re.compile(r"\]\((?!https?:|mailto:|#)([^)]+)\)")
        for path in sorted(p for p in POOL.glob("*/**/*.md") if p.parts[-2] in owned or p.parent.parent.name in owned):
            for target in link.findall(outside_code_fences(read(path))):
                target = target.split("#", 1)[0].strip()
                if not target:
                    continue
                with self.subTest(source=str(path.relative_to(REPO_ROOT)), target=target):
                    self.assertTrue(
                        (path.parent / target).exists(),
                        f"{path.relative_to(REPO_ROOT)} links to missing {target}",
                    )


class UpstreamLedgerTest(unittest.TestCase):
    """Pinned provenance is what keeps an adaptation from becoming a silent fork."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.ledger = json.loads(read(LEDGER_PATH)) if LEDGER_PATH.is_file() else {}

    def test_license_is_retained_beside_the_ledger(self) -> None:
        self.assertTrue(LICENSE_PATH.is_file(), "upstream MIT license must be stored beside the ledger")
        self.assertIn("MIT License", read(LICENSE_PATH))
        self.assertIn("Matt Pocock", read(LICENSE_PATH))

    def test_ledger_header_is_complete(self) -> None:
        for key in ("upstream", "version", "commit", "license", "licenseFile", "updatePolicy"):
            with self.subTest(key=key):
                self.assertIn(key, self.ledger)
        self.assertRegex(self.ledger.get("commit", ""), r"\A[0-9a-f]{40}\Z")
        self.assertEqual(self.ledger.get("license"), "MIT")
        self.assertTrue((UPSTREAMS / self.ledger["licenseFile"]).is_file())

    def test_update_policy_is_detection_only(self) -> None:
        policy = self.ledger.get("updatePolicy", {})
        self.assertTrue(policy.get("readOnlyDetection") is True)
        self.assertTrue(policy.get("humanApprovedPinAdvance") is True)
        self.assertTrue(policy.get("autoApply") is False)

    def test_every_adaptation_maps_upstream_to_canonical_local_paths(self) -> None:
        adaptations = self.ledger.get("adaptations", [])
        self.assertTrue(adaptations, "ledger must record at least one adaptation")
        for entry in adaptations:
            with self.subTest(skill=entry.get("skill")):
                for key in (
                    "skill",
                    "upstreamPaths",
                    "localPaths",
                    "localChanges",
                    "acceptedUpstreamRules",
                    "rejectedUpstreamRules",
                    "watchedFiles",
                ):
                    self.assertIn(key, entry)
                self.assertTrue(entry["upstreamPaths"], "adaptation needs its upstream sources")
                self.assertTrue(entry["watchedFiles"], "adaptation needs watched upstream files")
                for local in entry["localPaths"]:
                    self.assertTrue(
                        (REPO_ROOT / local).exists(),
                        f"ledger points at missing local path {local}",
                    )

    def test_watched_files_are_a_subset_of_declared_upstream_paths(self) -> None:
        """A watched file with no mapping cannot be assessed for relevance."""
        for entry in self.ledger.get("adaptations", []):
            with self.subTest(skill=entry.get("skill")):
                self.assertTrue(
                    set(entry["watchedFiles"]).issubset(set(entry["upstreamPaths"])),
                    f"{entry.get('skill')} watches upstream files it does not declare as sources",
                )

    def test_every_adapted_skill_carries_ledger_provenance(self) -> None:
        for name in ALL_NEW_SKILLS:
            with self.subTest(skill=name):
                body = read(POOL / name / "SKILL.md")
                self.assertIn(
                    "mattpocock-skills.json",
                    body,
                    f"{name}/SKILL.md must point at the adaptation ledger",
                )

    def test_every_adapted_skill_is_in_the_ledger(self) -> None:
        recorded = {entry.get("skill") for entry in self.ledger.get("adaptations", [])}
        for name in ALL_NEW_SKILLS:
            with self.subTest(skill=name):
                self.assertIn(name, recorded)


class CurationTest(unittest.TestCase):
    """The reconciler arrays are the single curation authority."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.arrays = curation_arrays()

    def test_cores_are_curated_for_claude_opencode_and_hermes(self) -> None:
        for tool in ("CLAUDE_SKILLS", "OPENCODE_SKILLS", "HERMES_SKILLS"):
            for name in ADAPTED_CORES:
                with self.subTest(tool=tool, skill=name):
                    self.assertIn(name, self.arrays.get(tool, []))

    def test_guided_learning_is_hermes_only(self) -> None:
        self.assertIn("guided-learning", self.arrays.get("HERMES_SKILLS", []))
        for tool in ("CLAUDE_SKILLS", "OPENCODE_SKILLS", "PI_SKILLS"):
            with self.subTest(tool=tool):
                self.assertNotIn("guided-learning", self.arrays.get(tool, []))

    def test_pi_receives_only_the_review_dependency_from_new_scope(self) -> None:
        self.assertIn("code-review", self.arrays.get("PI_SKILLS", []))
        for name in set(ALL_NEW_SKILLS) - {"code-review"}:
            with self.subTest(skill=name):
                self.assertNotIn(name, self.arrays.get("PI_SKILLS", []))

    def test_adr_and_spec_coach_survives_as_the_pilot_control(self) -> None:
        for tool in ("CLAUDE_SKILLS", "OPENCODE_SKILLS", "HERMES_SKILLS"):
            with self.subTest(tool=tool):
                self.assertIn("adr-and-spec-coach", self.arrays.get(tool, []))

    def test_retired_pool_skills_are_uncurated(self) -> None:
        for name in ("git-master", "agent-workspace"):
            for tool, members in self.arrays.items():
                with self.subTest(tool=tool, skill=name):
                    self.assertNotIn(name, members)

    def test_every_curated_name_exists_in_the_pool(self) -> None:
        for tool, members in self.arrays.items():
            for name in members:
                with self.subTest(tool=tool, skill=name):
                    self.assertTrue(
                        (POOL / name).is_dir(),
                        f"{tool} curates {name}, which is not in the pool",
                    )


class RetiredRouteTest(unittest.TestCase):
    """Cleanup is proven by the absence of live references, not by intent."""

    def test_retired_pool_directories_are_gone(self) -> None:
        for name in ("git-master", "agent-workspace"):
            with self.subTest(skill=name):
                self.assertFalse((POOL / name).exists(), f"{name} should be deleted from the pool")

    def test_no_active_reference_to_a_retired_route(self) -> None:
        """A retired name may only appear in a passage that marks it as history.

        Scoped to the paragraph, not the line: a sentence wraps, and the
        clause that makes a mention historical ("the workflow it
        replaces") often lands on the following line.
        """
        for path in active_markdown():
            line_no = 0
            for paragraph in read(path).split("\n\n"):
                start = line_no + 1
                line_no += paragraph.count("\n") + 2
                lowered = paragraph.lower()
                if any(marker in lowered for marker in _HISTORICAL_MARKERS):
                    continue
                for route in RETIRED_ROUTES:
                    if route in lowered:
                        self.fail(
                            f"{path.relative_to(REPO_ROOT)}:~{start} still routes to "
                            f"retired '{route}': {paragraph.strip()[:160]}"
                        )

    def test_trunk_resolution_has_a_canonical_owner(self) -> None:
        body = read(POOL / "worktrunk" / "SKILL.md")
        self.assertIn("resolve_trunk_root", body, "worktrunk must own trunk/worktree resolution")
        self.assertIn("--git-common-dir", body)

    def test_consumers_cite_worktrunk_for_trunk_resolution(self) -> None:
        for name in ("issue-work", "pr-self-review"):
            with self.subTest(skill=name):
                body = read(POOL / name / "SKILL.md")
                self.assertIn("worktrunk", body, f"{name} must cite worktrunk for trunk resolution")


class IssueWorkRoutingTest(_MatchMixin, unittest.TestCase):
    """`issue-work` keeps execution authority and selects the new cores."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.body = read(POOL / "issue-work" / "SKILL.md")

    def test_names_the_adapted_delivery_cores(self) -> None:
        for name in ("tdd", "diagnosing-bugs", "pr-self-review"):
            with self.subTest(core=name):
                self.assertIn(name, self.body)

    def test_does_not_promise_a_lens_count(self) -> None:
        """The old skill hardcoded 'four lenses' while review ran six.

        Lane selection is now computed, so no prose count may reappear.
        """
        self.assert_not_matches(self.body, r"(?i)\b(four|six)[- ]lens", f"forbidden wording present: {r"(?i)\b(four|six)[- ]lens"!r}")
        self.assert_not_matches(self.body, r"(?i)\ball (four|six) lenses\b", f"forbidden wording present: {r"(?i)\ball (four|six) lenses\b"!r}")


class ReviewContractTest(_MatchMixin, unittest.TestCase):
    """Three primary lanes plus a mandatory final Ponytail quality gate."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.body = read(POOL / "pr-self-review" / "SKILL.md")
        cls.code_review = read(POOL / "code-review" / "SKILL.md")
        cls.issue_work = read(POOL / "issue-work" / "SKILL.md")
        cls.lane_reviewer = read(REPO_ROOT / "dot-claude" / "agents" / "lane-reviewer.md")
        cls.review_overview = cls.body.split("## Phase 2 — Review pass", 1)[1].split("### 2.1", 1)[0]
        cls.dispatch = cls.body.split("### 2.2 Run the primary lanes, then Ponytail", 1)[1].split("### 2.2.1", 1)[0]
        cls.ponytail_dispatch = cls.dispatch.split("After the primary batch", 1)[1]
        cls.correction = cls.body.split("### 2.5 Correction bound", 1)[1].split("## Phase 3", 1)[0]
        cls.summary = cls.body.split("### 3.1 Write summary.md", 1)[1].split("### 3.2", 1)[0]
        cls.preflight = cls.body.split("### 0.4 Pre-flight", 1)[1].split("## Phase 1", 1)[0]
        cls.ponytail_contract = cls.code_review.split("### Ponytail quality gate", 1)[1].split("## 5. Report", 1)[0]

    def test_lane_selector_and_its_tests_exist(self) -> None:
        self.assertTrue((POOL / "pr-self-review" / "scripts" / "select_review_lanes.py").is_file())
        self.assertTrue((POOL / "pr-self-review" / "tests" / "test_select_review_lanes.py").is_file())

    def test_skill_names_the_three_lanes_and_their_artifacts(self) -> None:
        for token in ("review-standards.md", "review-spec.md", "review-risk.md", "summary.md"):
            with self.subTest(artifact=token):
                self.assertIn(token, self.body)

    def test_ponytail_is_a_mandatory_final_pass_not_a_fourth_primary_lane(self) -> None:
        self.assertIn("classifier-selected primary lanes", self.review_overview)
        self.assertIn("followed by mandatory Ponytail", self.review_overview)
        self.assertIn("not a fourth primary lane", self.review_overview)
        self.assertIn("Ponytail runs on every review candidate", self.review_overview)
        self.assertIn("After the primary batch", self.dispatch)
        self.assertIn("the same diff range", self.dispatch)
        self.assertIn("candidate_identity", self.dispatch)
        self.assertIn("review-ponytail.md", self.dispatch)
        for field in ("base_sha", "head_sha", "merge_base_sha", "diff_sha256"):
            with self.subTest(ponytail_identity=field):
                self.assertIn(field, self.ponytail_dispatch)

    def test_ponytail_contract_is_host_independent_and_narrow(self) -> None:
        for token in (
            "over-engineering only",
            "delete",
            "yagni",
            "stdlib",
            "native",
            "shrink",
            "never invent deletions",
            "Lean already. Ship.",
        ):
            with self.subTest(token=token):
                self.assertIn(token.lower(), self.ponytail_contract.lower())
        self.assertIn("does **not** report correctness, security", self.ponytail_contract)
        for body in (self.body, self.code_review, self.lane_reviewer):
            self.assertNotIn("ponytail:ponytail-review", body)
        self.assertIn("Do not invoke `/ponytail-review`", self.review_overview)
        self.assertIn("depend on a Claude plugin or user-scope", self.review_overview)

    def test_correction_and_terminal_rereviews_require_ponytail(self) -> None:
        self.assertIn("all selected primary lanes", self.correction)
        self.assertIn("Ponytail last", self.correction)
        self.assertNotIn("affected lanes only", self.correction.lower())
        self.assertIn("The `final_review_only` pass", self.correction)
        self.assertIn("review-ponytail.md", self.correction)
        self.assertIn("validated fix", self.correction)
        self.assertIn("candidate must be reviewed again", self.correction)

    def test_summary_and_readiness_make_missing_ponytail_visible(self) -> None:
        for token in ("candidate: {head_sha}", "quality_gates: [ponytail]", "## Ponytail Quality Gate", "review-ponytail.md"):
            with self.subTest(token=token):
                self.assertIn(token, self.summary)
        for field in ("base_sha", "head_sha", "merge_base_sha", "diff_sha256"):
            with self.subTest(field=field):
                self.assertIn(f"{field}: {{{field}}}", self.lane_reviewer)
                self.assertIn(field, self.body)
        self.assert_matches(
            self.body,
            r"(?is)compare.*base_sha.*head_sha.*merge_base_sha.*diff_sha256.*before.*after",
            "every review stage must verify the complete immutable candidate identity",
        )
        self.assertIn("Ponytail review missing — do not merge", self.summary)
        self.assertIn("Ship Readiness also checks `review-ponytail.md`", self.summary)

    def test_state_directory_is_created_confined_and_symlink_safe(self) -> None:
        self.assertIn("standalone", self.preflight.lower())
        self.assertIn("create", self.preflight.lower())
        self.assertIn("pre-pr", self.preflight.lower())
        self.assertIn("canonical", self.preflight.lower())
        self.assertIn("authorized `.hermes/` state root", self.preflight)
        self.assertIn('D="{state-dir}"', self.body)
        self.assertIn('! -d "$D"', self.body)
        self.assertIn("set -euo pipefail", self.body)
        self.assertIn("trap cleanup_candidate_inputs EXIT", self.body)
        for artifact in ("candidate.diff", "name-status", "unified.diff"):
            with self.subTest(artifact=artifact):
                self.assertIn(f'mktemp "$D/{artifact}.XXXXXX"', self.body)
        self.assertIn('$base_sha...$head_sha', self.body)
        self.assertNotIn('{base}...HEAD -- > "$name_status_file"', self.body)

    def test_issue_work_requires_and_presents_the_ponytail_artifact(self) -> None:
        self.assertIn("review-ponytail.md", self.issue_work)
        self.assert_matches(
            self.issue_work,
            r"(?is)review-ponytail\.md.*(missing|absent).*(blocked|do not merge|stop)",
            "issue-work must not accept an incomplete self-review handoff",
        )
        self.assert_matches(
            self.issue_work,
            r"(?is)Ponytail.*(status|selection)",
            "issue-work must present Ponytail selection/status",
        )

    def test_lane_reviewer_can_receive_the_shared_ponytail_contract(self) -> None:
        self.assertIn("`ponytail`", self.lane_reviewer)
        self.assertIn("review-ponytail.md", self.lane_reviewer)
        self.assert_matches(
            self.lane_reviewer,
            r"(?is)git diff --binary -M -C --find-copies-harder.*\{base_sha\}\.\.\.\{head_sha\}.*diff_sha256",
            "every reviewer must recompute the parent's exact canonical binary-diff fingerprint",
        )
        for token in (
            "actual_head_sha",
            "actual_merge_base_sha",
            "{head_sha}",
            "{merge_base_sha}",
            "git status --porcelain --untracked-files=all",
        ):
            with self.subTest(identity_check=token):
                self.assertIn(token, self.lane_reviewer)
        self.assertIn("git status --porcelain --untracked-files=all", self.body)
        self.assert_matches(
            self.lane_reviewer,
            r"(?is)code-review.*canonical.*ponytail",
            "Claude's reviewer must consume the shared contract rather than a plugin",
        )

    def test_standalone_code_review_pins_classifier_and_ponytail_identity(self) -> None:
        self.assertIn('git rev-parse "<fixed-point>^{commit}"', self.code_review)
        self.assertIn("{base_sha}...{head_sha}", self.code_review)
        self.assertIn("git diff --binary -M -C --find-copies-harder", self.code_review)
        self.assertIn("diff_sha256=", self.code_review)
        self.assertNotIn("<fixed-point>...HEAD -- > name-status", self.code_review)
        ponytail_dispatch = self.code_review.split("After every selected primary lane", 1)[1].split("### Standards lane", 1)[0]
        self.assertIn("expected_head_branch", ponytail_dispatch)
        for field in ("base_sha", "head_sha", "merge_base_sha", "diff_sha256"):
            with self.subTest(field=field):
                self.assertIn(field, ponytail_dispatch)

    def test_every_identity_boundary_rejects_same_commit_branch_switches(self) -> None:
        self.assertIn("expected_head_branch", self.body)
        self.assertIn("git branch --show-current", self.body)
        self.assertIn("current branch", self.body.lower())
        self.assertIn("expected_head_branch", self.lane_reviewer)
        self.assertIn("git branch --show-current", self.lane_reviewer)

    def test_skill_documents_the_cairnos_always_risk_rule(self) -> None:
        self.assert_matches(self.body, r"(?i)cairn", f"missing required wording: {r"(?i)cairn"!r}")

    def test_skill_documents_the_no_third_pass_invariant(self) -> None:
        self.assert_matches(self.body, r"(?i)no third correction pass|never a third correction pass", f"missing required wording: {r"(?i)no third correction pass|never a third correction pass"!r}")

    def test_skill_keeps_the_independent_acceptance_criteria_sweep(self) -> None:
        self.assert_matches(
            self.body, r"(?i)acceptance[- ]criteria sweep", "AC sweep section missing"
        )

    def test_ac_sweep_gathers_from_every_authoritative_intent_source(self) -> None:
        """An issue with no task list is not an issue with no criteria."""
        for source in ("plan_path", "source issue", "spec", "PR body"):
            with self.subTest(source=source):
                self.assert_matches(
                    self.body, re.escape(source), f"AC sweep must name {source} as a source"
                )
        self.assert_matches(
            self.body,
            r"(?i)not an issue with no acceptance criteria",
            "AC sweep must reject absence-of-task-list as absence-of-criteria",
        )
        self.assert_matches(
            self.body, r"(?i)normaliz", "AC sweep must normalize into one checklist"
        )
        self.assert_matches(
            self.body,
            r"(?i)compound",
            "AC sweep must split compound criteria; a half-satisfied compound reads as met",
        )

    def test_the_second_correction_is_still_reviewed(self) -> None:
        """Reaching the bound must not ship an unexamined correction.

        The code the second pass produced has never been looked at, so exiting
        on `correction_passes == 2` would make the conditional final pass a way
        to slip an unreviewed change past the gate.
        """
        self.assert_matches(
            self.body, r"final_review_only", "the terminal review-only state must exist"
        )
        self.assert_matches(
            self.body,
            r"(?i)do not exit here",
            "reaching the bound must explicitly not be an exit",
        )
        self.assert_matches(
            self.body,
            r"(?i)apply nothing",
            "the review-only pass must forbid fixes",
        )

    def test_the_loop_state_table_covers_every_terminal_state(self) -> None:
        for state in ("reviewing", "final_review_only", "clean", "bound"):
            with self.subTest(state=state):
                self.assert_matches(
                    self.body, rf"\|\s*`?{state}`?\s*\|", f"loop state {state} missing from the table"
                )

    def test_the_review_only_pass_is_identical_on_both_paths(self) -> None:
        """A delegated run gets no extra pass and skips no review."""
        self.assert_matches(
            self.body,
            r"(?i)identical on the native and delegated paths",
            "the review-only pass must be stated as path-independent",
        )
        self.assert_matches(
            self.body,
            r"(?i)reconciliation\s+is\s+a\s+verification\s+of\s+the\s+worker.s\s+diff,\s+not\s+a\s+review",
            "Codex reconciliation must not be mistaken for the final review",
        )

    def test_the_review_only_pass_reselects_lanes(self) -> None:
        """The second correction moved HEAD, so the Risk decision may have moved."""
        self.assert_matches(
            self.body,
            r"(?i)re-select the lanes against the \*current\* HEAD",
            "the review-only pass must re-select lanes",
        )

    def test_correction_passes_are_counted_per_committed_boundary(self) -> None:
        """A delegated batch must not spend the conditional final pass early."""
        self.assert_matches(
            self.body,
            r"(?i)once per committed correction boundary",
            "the counter's unit must be stated",
        )
        self.assert_matches(
            self.body,
            r"(?i)do not increment `correction_passes` here",
            "the delegated path must be told explicitly not to double-count",
        )
        self.assert_matches(
            self.body,
            r"(?i)conditional final pass\s*\|",
            "the native/delegated discrimination table must be present",
        )

    def test_the_intent_checklist_is_a_persisted_artifact(self) -> None:
        """Rebuilt from memory, the checklist drifts back to the task list."""
        self.assertIn("intent-checklist.json", self.body)
        self.assert_matches(
            self.body,
            r"(?i)summary\.md.*read \*\*that file\*\*|both the sweep and `summary\.md`",
            "the sweep and the summary must consume one artifact",
        )
        for field in ("sources", "statement", "verdict", "evidence"):
            with self.subTest(field=field):
                self.assertIn(f'"{field}"', self.body)

    def test_the_checklist_never_mines_the_truncated_excerpt(self) -> None:
        """The 400-char window truncates exactly where criteria usually sit."""
        self.assert_matches(
            self.body,
            r"(?i)do not try to recover prose criteria from the 400-character",
            "the excerpt must be ruled out as a criteria source",
        )
        self.assert_matches(
            self.body,
            r"(?i)while the full body is in hand",
            "criteria must be extracted at ingest, not reconstructed later",
        )
        for heading in ("acceptance criteria", "definition of done", "done when"):
            with self.subTest(heading=heading):
                self.assertIn(heading, self.body.lower())

    def test_an_unreadable_authority_is_unswept_not_absent(self) -> None:
        self.assertIn("unswept", self.body)
        self.assert_matches(
            self.body,
            r"(?i)different facts",
            "could-not-read and asked-for-nothing must be distinguished",
        )

    def test_untracked_files_block_the_candidate(self) -> None:
        """A nonignored untracked file is invisible to `{base}...HEAD`."""
        self.assert_matches(
            self.body,
            r"untracked-files=all",
            "the untracked inventory command must be named",
        )
        self.assert_matches(
            self.body,
            r"(?i)invisible to",
            "the reason an untracked file is unreviewable must be stated",
        )
        self.assert_matches(
            self.body,
            r"(?i)`?pre-pr`? and standalone",
            "the rule must apply in both modes",
        )
        self.assert_matches(
            self.body,
            r"(?i)ignored paths are outside the candidate",
            "ignored .hermes state must stay out of scope",
        )

    def test_skill_delegates_lane_selection_to_the_classifier(self) -> None:
        self.assertIn("select_review_lanes.py", self.body)


class GuidedLearningTest(_MatchMixin, unittest.TestCase):
    """Learning state is Bryan's; the skill may never write into itself."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.body = read(POOL / "guided-learning" / "SKILL.md")

    def test_requires_an_absolute_workspace_path(self) -> None:
        self.assert_matches(self.body, r"(?i)absolute .*path", f"missing required wording: {r"(?i)absolute .*path"!r}")

    def test_refuses_to_write_into_its_installed_skill_directory(self) -> None:
        self.assert_matches(self.body, r"(?i)refuse", f"missing required wording: {r"(?i)refuse"!r}")
        self.assert_matches(self.body, r"(?i)installed skill directory", f"missing required wording: {r"(?i)installed skill directory"!r}")

    def test_does_not_precreate_learning_machinery(self) -> None:
        for forbidden in ("lessons/", "assets/", "quiz"):
            with self.subTest(item=forbidden):
                self.assertNotIn(
                    f"create {forbidden}",
                    self.body.lower(),
                    "guided learning must stay a minimal lazy zone",
                )

    def test_never_treats_memory_as_proof_of_learning(self) -> None:
        self.assert_matches(self.body, r"(?i)hindsight", f"missing required wording: {r"(?i)hindsight"!r}")
        self.assert_matches(self.body, r"(?i)evidence", f"missing required wording: {r"(?i)evidence"!r}")


class WayfinderContractTest(_MatchMixin, unittest.TestCase):
    """Tracker mechanics are a deterministic helper, not free-form API prose."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.body = read(POOL / "wayfinder" / "SKILL.md")

    def test_adapter_and_references_exist(self) -> None:
        base = POOL / "wayfinder"
        for relative in (
            "scripts/forgejo_wayfinder.py",
            "tests/test_forgejo_wayfinder.py",
            "references/forgejo-tracker.md",
            "references/prototype-routing.md",
        ):
            with self.subTest(path=relative):
                self.assertTrue((base / relative).is_file())

    def test_skill_requires_a_private_tracker(self) -> None:
        self.assert_matches(self.body, r"(?i)private", f"missing required wording: {r"(?i)private"!r}")
        self.assert_matches(self.body, r"(?i)public .*(tracker|repositor)", f"missing required wording: {r"(?i)public .*(tracker|repositor)"!r}")

    def test_skill_requires_preview_before_mutation(self) -> None:
        self.assert_matches(self.body, r"(?i)dry[- ]run|preview", f"missing required wording: {r"(?i)dry[- ]run|preview"!r}")
        self.assertIn("forgejo_wayfinder.py", self.body)

    # Named prototype workflows and where each one actually lives. `spike` and
    # `sketch` are Hermes builtins, not pool members, so pool membership is the
    # wrong test — availability per runtime is the contract.
    PROTOTYPE_ROUTES = {
        "spike": "hermes-builtin",
        "sketch": "hermes-builtin",
        "dx-target": "pool",
        "dx-preview": "pool",
    }

    def test_prototype_routing_names_every_approved_route(self) -> None:
        routing = read(POOL / "wayfinder" / "references" / "prototype-routing.md")
        for workflow in self.PROTOTYPE_ROUTES:
            with self.subTest(workflow=workflow):
                self.assertIn(f"`{workflow}`", routing)

    def test_pool_routes_are_actually_in_the_pool(self) -> None:
        for name, home in self.PROTOTYPE_ROUTES.items():
            if home != "pool":
                continue
            with self.subTest(workflow=name):
                self.assertTrue(
                    (POOL / name / "SKILL.md").is_file(),
                    f"prototype routing selects pooled '{name}', which is not in the pool",
                )

    def test_routing_declares_availability_and_a_fallback_per_route(self) -> None:
        """A named route that is unavailable needs a stated fallback, not silence.

        `spike` and `sketch` are Hermes builtins; Claude and OpenCode do not have
        them. The reference has to say so and say what to do instead, or the
        route is a dead end on two of three runtimes.
        """
        routing = read(POOL / "wayfinder" / "references" / "prototype-routing.md")
        self.assertRegex(routing, r"(?i)runtime availability")
        for name, home in self.PROTOTYPE_ROUTES.items():
            with self.subTest(workflow=name):
                self.assertRegex(
                    routing,
                    rf"\|\s*`{re.escape(name)}`[^|]*\|[^|]+\|[^|]+\|",
                    f"{name} needs a row naming where it lives and what to do elsewhere",
                )
        for shape in ("feasibility spike", "logic walkthrough", "UI variants"):
            with self.subTest(fallback=shape):
                self.assertIn(f"Inline fallback: {shape}", routing)

    def test_questionnaire_is_a_disclosed_reference_not_a_top_level_skill(self) -> None:
        self.assertTrue((POOL / "grilling" / "references" / "questionnaire.md").is_file())
        self.assertFalse((POOL / "to-questionnaire").exists())
        self.assertFalse((POOL / "questionnaire").exists())


class WritingGovernanceTest(_MatchMixin, unittest.TestCase):
    """Two narrow refinements land on their existing canonical owners."""

    def test_readme_prefers_sharpening_the_pointer_over_inlining(self) -> None:
        body = read(REPO_ROOT / "dot-agents" / "README.md")
        self.assert_matches(body, r"(?i)trigger wording", f"missing required wording: {r"(?i)trigger wording"!r}")
        self.assert_matches(body, r"(?i)inlin", f"missing required wording: {r"(?i)inlin"!r}")

    def test_retrospective_treats_repeated_lookups_as_a_stale_cache(self) -> None:
        body = read(POOL / "skill-retrospective" / "SKILL.md")
        self.assert_matches(body, r"(?i)stale cache", f"missing required wording: {r"(?i)stale cache"!r}")
        self.assert_matches(body, r"(?i)--help|manifest", f"missing required wording: {r"(?i)--help|manifest"!r}")


class MonitorOutputTest(_MatchMixin, unittest.TestCase):
    """A monitor that varies run-to-run alerts on nothing but itself."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.script = REPO_ROOT / "hermes" / "scripts" / "check-mattpocock-skill-updates.py"

    def test_monitor_script_exists_and_is_executable(self) -> None:
        self.assertTrue(self.script.is_file())
        self.assertTrue(self.script.stat().st_mode & 0o111, "monitor script must be executable")

    def test_monitor_emits_no_timestamp_or_local_path(self) -> None:
        body = read(self.script)
        self.assert_not_matches(body, r"datetime\.now|time\.time\(\)|utcnow", f"forbidden wording present: {r"datetime\.now|time\.time\(\)|utcnow"!r}")
        self.assertIn("sort_keys=True", body)

    def test_monitor_supports_offline_fixtures(self) -> None:
        body = read(self.script)
        self.assert_matches(body, r"(?i)fixture", f"missing required wording: {r"(?i)fixture"!r}")

    def test_prompt_is_mention_led_and_read_only(self) -> None:
        prompt = REPO_ROOT / "hermes" / "automations" / "mattpocock-skill-update-watch" / "prompt.md"
        self.assertTrue(prompt.is_file())
        body = read(prompt)
        self.assertIn("@bryan:snowboardtechie.com", body)
        self.assertIn("[SILENT]", body)
        self.assert_matches(body, r"(?i)never .*(edit|advance|install|activate)", f"missing required wording: {r"(?i)never .*(edit|advance|install|activate)"!r}")


class ManifestTest(unittest.TestCase):
    """The tracked manifest is the declarative source for the live job."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(read(REPO_ROOT / "hermes" / "manifest.json"))

    def watcher(self) -> dict:
        for job in self.manifest["cronJobs"]:
            if job["name"] == "Watch Matt Pocock skill updates":
                return job
        self.fail("manifest does not define the upstream watcher cron job")

    def test_monitor_script_is_declared_and_shipped(self) -> None:
        job = self.watcher()
        self.assertEqual(job["monitorScript"], "check-mattpocock-skill-updates.py")
        self.assertIn(job["monitorScript"], self.manifest["scripts"])
        self.assertTrue((REPO_ROOT / "hermes" / "scripts" / job["monitorScript"]).is_file())

    def test_watcher_runs_weekly_and_needs_no_continuation(self) -> None:
        job = self.watcher()
        self.assertRegex(job["schedule"], r"\A\d+ \d+ \* \* [0-6]\Z")
        self.assertFalse(job["attachToSession"])
        self.assertNotIn("continuation", job)

    def test_watcher_prompt_file_resolves(self) -> None:
        job = self.watcher()
        self.assertTrue((REPO_ROOT / "hermes" / job["promptFile"]).is_file())

    def test_watcher_carries_the_migration_skill_and_read_only_toolsets(self) -> None:
        job = self.watcher()
        self.assertIn("cross-agent-skill-migration", job["skills"])
        self.assertNotIn("delegation", job["enabledToolsets"])


if __name__ == "__main__":
    unittest.main()
