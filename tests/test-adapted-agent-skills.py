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
    """`issue-work` right-sizes execution and carries explicit authority."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.body = read(POOL / "issue-work" / "SKILL.md")
        cls.handoff = read(POOL / "issue-plan" / "references" / "handoff-contract.md")
        cls.repo_resolution = read(POOL / "issue-work" / "references" / "repo-resolution.md")
        cls.router = read(POOL / "issue-work" / "scripts" / "select_issue_worker.py")
        cls.handoff_supervision = read(
            POOL / "coding-agent-handoff-supervision" / "SKILL.md"
        )

    def test_supports_explicit_cross_repository_handoffs(self) -> None:
        for field in (
            "Ticket repository",
            "Implementation forge",
            "Implementation repository",
            "Implementation base",
            "Implementation revision",
        ):
            with self.subTest(field=field):
                self.assertIn(field, self.handoff)
        for token in (
            "issue-xrepo-{ticket_digest}",
            "publication-summary.md",
            "each distinct ticket and",
            "source_issue_mode: github_shorthand",
            "wrong forge",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.body)
        self.assertIn("{TICKET_TRUNK_ROOT}/repos/{repo}", self.repo_resolution)
        self.assertIn("Do not rescue an identity mismatch", self.repo_resolution)

    def test_imperative_work_authorizes_reviewable_pr_not_merge(self) -> None:
        self.assert_matches(
            self.body,
            r"(?is)imperative `work <issue URL>`.*implementation.*local commits.*push.*reviewable PR",
            "work command must carry implementation and PR delivery authority",
        )
        for excluded in (
            "does not authorize merge",
            "issue comments",
            "issue-body edits",
            "label changes",
            "deployment",
        ):
            with self.subTest(excluded=excluded):
                self.assertIn(excluded, self.body)
        self.assert_matches(
            self.body,
            r"(?is)do not ask again.*push or create the reviewable PR",
            "issue-work must not add a redundant ship approval",
        )

    def test_exploration_is_question_driven_and_may_be_zero(self) -> None:
        self.assertIn("Use zero exploration children", self.body)
        self.assertIn("concrete unresolved repository question", self.body)
        self.assertNotIn("**always** at least one", self.body)

    def test_router_right_sizes_auto_work(self) -> None:
        for token in ("--task-shape", "single-loop", "substantial"):
            with self.subTest(token=token):
                self.assertIn(token, self.body)
                self.assertIn(token.replace("--", ""), self.router)
        self.assert_matches(
            self.body,
            r"(?is)`auto` keeps a\s+single-loop task with the parent.*substantial work to visible Claude",
            "auto routing must be proportional to task shape",
        )
        self.assertIn("explicit same-run", self.body.lower())
        self.assertIn("Qwen is\nnever an automatic route", self.body)

    def test_visible_worker_uses_one_helper_and_complete_identity(self) -> None:
        self.assertIn("herdr_worker.py", self.body)
        for field in (
            "worker_surface",
            "worker_agent_name",
            "worker_pane_id",
            "worker_kind",
            "worker_runtime_session_id",
            "worker_worktree_identity",
        ):
            with self.subTest(field=field):
                self.assertIn(field, self.body)
                self.assertIn(field, self.handoff_supervision)
        self.assertIn("atomically\nserializes provider turns", self.body)
        self.assertIn("never authorizes an automatic\nprovider switch", self.body)

    def test_destructive_git_remains_absolutely_prohibited(self) -> None:
        region = self.body.split(
            "Destructive and history-rewriting Git operations", 1
        )[1].split("For an explicit Qwen route", 1)[0]
        self.assertIn("absolute and\nnot approval-eligible", region)
        for operation in (
            "git reset",
            "git clean",
            "checkout-discard",
            "rebase",
            "amend",
            "history rewrite",
            "force-push",
            "local-ref/branch deletion",
        ):
            with self.subTest(operation=operation):
                self.assertIn(operation, region)

    def test_compact_efficiency_record_is_complete(self) -> None:
        for field in (
            "task_shape",
            "exploration_children",
            "claude_prompts",
            "correction_passes",
            "review_invocations",
            "targeted_risk_reviews",
            "provider_capacity_start",
            "provider_capacity_end",
            "blocking_findings_after_initial_review",
            "elapsed_to_reviewable_pr_seconds",
        ):
            with self.subTest(field=field):
                self.assertIn(field, self.body)


class CodingAgentHandoffContractTest(_MatchMixin, unittest.TestCase):
    """Visible handoffs are short, deterministic, and globally serialized."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.body = read(POOL / "coding-agent-handoff-supervision" / "SKILL.md")
        cls.herdr = read(
            POOL
            / "coding-agent-handoff-supervision"
            / "references"
            / "herdr-claude-handoff.md"
        )
        cls.script = (
            POOL
            / "coding-agent-handoff-supervision"
            / "scripts"
            / "herdr_worker.py"
        )
        cls.tests = (
            POOL
            / "coding-agent-handoff-supervision"
            / "tests"
            / "test_herdr_worker.py"
        )

    def test_preparation_reuses_or_creates_one_ticket(self) -> None:
        for token in ("Reuse the ticket", "issue-create", "duplicate", "read it back"):
            with self.subTest(token=token):
                self.assertIn(token, self.body)

    def test_artifact_not_prompt_carries_context(self) -> None:
        self.assertIn("artifact, not the prompt", self.body)
        self.assert_matches(
            self.body,
            r"(?is)ticket or plan URL/path.*implementation repository.*worktree.*authority boundaries.*permissions",
            "brief must contain locators and authority only",
        )
        self.assert_matches(
            self.body,
            r"(?is)Do not restate steps, files, tests, requirements, or safeguards",
            "reachable requirements must not be copied into the prompt",
        )

    def test_sol_claude_boundary_is_explicit(self) -> None:
        for token in ("decision-complete", "Sol remains the pairing", "single-loop"):
            with self.subTest(token=token):
                self.assertIn(token.lower(), self.body.lower())
        self.assert_matches(
            self.body,
            r"(?is)the worker produces a\s+candidate; Sol independently accepts",
            "worker authorship and Sol acceptance must stay distinct",
        )

    def test_helper_and_tests_exist(self) -> None:
        self.assertTrue(self.script.is_file())
        self.assertTrue(self.tests.is_file())
        self.assertTrue(self.script.stat().st_mode & 0o111)
        self.assertIn("herdr_worker.py", self.body)
        self.assertIn("herdr_worker.py", self.herdr)

    def test_capacity_and_global_turn_lease_are_hard_gates(self) -> None:
        for token in (
            "global Claude-turn lease",
            "At most one Claude prompt",
            "Any nonzero\ncapacity result stops",
            "never switch providers",
        ):
            with self.subTest(token=token):
                self.assertIn(token.lower(), (self.body + self.herdr).lower())
        script = read(self.script)
        self.assertIn("fcntl.LOCK_EX | fcntl.LOCK_NB", script)
        self.assertIn('"--check-capacity"', script)
        self.assertIn('"--wait"', script)

    def test_visible_authority_and_identity_remain_fail_closed(self) -> None:
        for token in (
            "--permission-mode auto",
            "approvals.mode: smart",
            "HERMES_YOLO_MODE",
            "not sandbox-confined",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.body)
        for permission in ("local commit", "push", "PR/issue permissions"):
            with self.subTest(permission=permission):
                self.assertIn(permission, self.body)
        self.assertIn("Do not hand-edit or reconstruct an\nidentity record", self.body)

    def test_pane_is_released_when_no_turn_remains(self) -> None:
        self.assertIn("Release the pane promptly", self.body)
        self.assertIn("Pending publication, merge, or live\nverification", self.body)
        self.assertIn("marks the identity closed/non-resumable", self.body)


class ReviewContractTest(_MatchMixin, unittest.TestCase):
    """Review keeps dimensions and quality while reducing invocations."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.body = read(POOL / "pr-self-review" / "SKILL.md")
        cls.code_review = read(POOL / "code-review" / "SKILL.md")
        cls.issue_work = read(POOL / "issue-work" / "SKILL.md")
        cls.ship = read(POOL / "ship" / "SKILL.md")
        cls.reviewer = read(REPO_ROOT / "dot-claude" / "agents" / "lane-reviewer.md")

    def test_lane_selector_and_tests_exist(self) -> None:
        self.assertTrue(
            (POOL / "pr-self-review" / "scripts" / "select_review_lanes.py").is_file()
        )
        self.assertTrue(
            (POOL / "pr-self-review" / "tests" / "test_select_review_lanes.py").is_file()
        )
        self.assertIn("select_review_lanes.py", self.body)
        self.assertIn("select_review_lanes.py", self.code_review)

    def test_review_is_integrated_but_artifacts_stay_separate(self) -> None:
        for token in (
            "one integrated review",
            "One review context reads the diff and authorities once",
            "review-standards.md",
            "review-spec.md",
            "review-risk.md",
            "review-ponytail.md",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.body + self.code_review)
        self.assertNotIn("parallel children", self.code_review)
        self.assertIn("model: opus", self.reviewer)
        self.assertIn("Do not spend another subagent", self.reviewer)

    def test_parent_is_independent_for_worker_authored_candidate(self) -> None:
        self.assertIn("Sol parent is the independent acceptance", self.issue_work)
        self.assertIn("systematic Sol-parent review", self.ship)
        self.assertIn("parent-authored candidate\nrequires an independent review context", self.ship)
        self.assertNotIn("must launch a fresh visible Claude reviewer", self.issue_work)

    def test_targeted_risk_deepening_is_conditional_and_late(self) -> None:
        for body in (self.body, self.code_review, self.issue_work):
            with self.subTest(skill=body[:40]):
                self.assertIn("targeted Risk reviewer", body)
                self.assertIn("stabil", body.lower())
        self.assertIn("not another generic pass", self.body)

    def test_ponytail_contract_stays_host_independent_and_narrow(self) -> None:
        for token in (
            "over-engineering only",
            "delete",
            "yagni",
            "stdlib",
            "native",
            "shrink",
            "Never invent deletions",
            "Lean already. Ship.",
        ):
            with self.subTest(token=token):
                self.assertIn(token.lower(), self.code_review.lower())
        self.assertIn("does not report correctness, security", self.code_review)
        self.assertNotIn("ponytail:ponytail-review", self.body + self.code_review)

    def test_correction_bound_is_one_plus_one(self) -> None:
        for token in (
            "one normal correction",
            "one conditional second correction",
            "never a third correction",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.body.lower())
                self.assertIn(token, self.issue_work.lower())
        self.assertNotIn("final_review_only", self.body)
        self.assertNotIn("third correction pass", self.body)

    def test_exact_candidate_and_untracked_guard_remain(self) -> None:
        for token in (
            "base_sha",
            "head_sha",
            "merge_base_sha",
            "diff_sha256",
            "expected_head_branch",
            "git status --porcelain --untracked-files=all",
            "invisible to `{base}...HEAD`",
            "Ignored paths are outside the candidate",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.body)
        for token in (
            "base_sha",
            "head_sha",
            "merge_base_sha",
            "diff_sha256",
            "expected_head_branch",
        ):
            with self.subTest(reviewer_identity=token):
                self.assertIn(token, self.reviewer)

    def test_acceptance_sweep_keeps_all_authorities(self) -> None:
        for token in (
            "plan_path",
            "source issue",
            "governing spec",
            "PR body",
            "intent-checklist.json",
            "An issue with no task list is not an issue with no acceptance criteria",
            "split every compound criterion",
            "unswept",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.body)

    def test_cross_repository_context_validator_remains_required(self) -> None:
        self.assertIn("validate_cross_repo_context.py", self.body)
        self.assertIn("validate_cross_repo_context.py", self.issue_work)
        for identity in (
            "ticket URL/host/repository",
            "implementation\nhost/repository",
            "state root",
            "worktree",
        ):
            with self.subTest(identity=identity):
                self.assertIn(identity, self.body)

    def test_ship_accepts_integrated_independent_evidence(self) -> None:
        self.assertIn("integrated `code-review` contract", self.ship)
        self.assertIn("Missing or stale Ponytail evidence blocks\npublication", self.ship)
        self.assertIn("Exact-candidate Standards, Spec, conditional Risk, and Ponytail", self.ship)


class GuidedLearningTest(_MatchMixin, unittest.TestCase):
    """Learning state is Bryan's; the skill may never write into itself."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.body = read(POOL / "guided-learning" / "SKILL.md")

    def test_requires_an_absolute_workspace_path(self) -> None:
        self.assert_matches(
            self.body, r"(?i)absolute .*path", "missing required wording: absolute path"
        )

    def test_refuses_to_write_into_its_installed_skill_directory(self) -> None:
        self.assert_matches(self.body, r"(?i)refuse", "missing required wording: refuse")
        self.assert_matches(
            self.body,
            r"(?i)installed skill directory",
            "missing required wording: installed skill directory",
        )

    def test_does_not_precreate_learning_machinery(self) -> None:
        for forbidden in ("lessons/", "assets/", "quiz"):
            with self.subTest(item=forbidden):
                self.assertNotIn(
                    f"create {forbidden}",
                    self.body.lower(),
                    "guided learning must stay a minimal lazy zone",
                )

    def test_never_treats_memory_as_proof_of_learning(self) -> None:
        self.assert_matches(self.body, r"(?i)hindsight", "missing required wording: hindsight")
        self.assert_matches(self.body, r"(?i)evidence", "missing required wording: evidence")


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
        self.assert_matches(self.body, r"(?i)private", "missing required wording: private")
        self.assert_matches(
            self.body,
            r"(?i)public .*(tracker|repositor)",
            "missing required wording: public tracker or repository",
        )

    def test_skill_requires_preview_before_mutation(self) -> None:
        self.assert_matches(
            self.body,
            r"(?i)dry[- ]run|preview",
            "missing required wording: dry run or preview",
        )
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
        self.assert_matches(
            body, r"(?i)trigger wording", "missing required wording: trigger wording"
        )
        self.assert_matches(body, r"(?i)inlin", "missing required wording: inline")

    def test_retrospective_treats_repeated_lookups_as_a_stale_cache(self) -> None:
        body = read(POOL / "skill-retrospective" / "SKILL.md")
        self.assert_matches(body, r"(?i)stale cache", "missing required wording: stale cache")
        self.assert_matches(
            body, r"(?i)--help|manifest", "missing required wording: help or manifest"
        )


class PRDescriptionAuthorizationTest(_MatchMixin, unittest.TestCase):
    """Approved PR work includes an accurate synchronized description."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.body = read(REPO_ROOT / "dot-agents" / "skills" / "update-pr-description" / "SKILL.md")

    def test_standing_authorization_avoids_a_duplicate_approval_gate(self) -> None:
        self.assert_matches(
            self.body,
            r"(?i)approval of work for an existing PR satisfies this gate",
            "approved PR work must authorize description synchronization",
        )
        self.assert_matches(
            self.body,
            r"(?i)do not ask again",
            "the workflow must not request duplicate approval",
        )

    def test_standing_authorization_remains_narrow(self) -> None:
        for excluded_action in ("comments", "issue edits", "review requests", "merges"):
            with self.subTest(excluded_action=excluded_action):
                self.assertIn(excluded_action, self.body)


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
        self.assert_not_matches(
            body,
            r"datetime\.now|time\.time\(\)|utcnow",
            "forbidden wording present: nondeterministic timestamp",
        )
        self.assertIn("sort_keys=True", body)

    def test_monitor_supports_offline_fixtures(self) -> None:
        body = read(self.script)
        self.assert_matches(body, r"(?i)fixture", "missing required wording: fixture")

    def test_prompt_is_mention_led_and_read_only(self) -> None:
        prompt = REPO_ROOT / "hermes" / "automations" / "mattpocock-skill-update-watch" / "prompt.md"
        self.assertTrue(prompt.is_file())
        body = read(prompt)
        self.assertIn("@bryan:snowboardtechie.com", body)
        self.assertIn("[SILENT]", body)
        self.assert_matches(
            body,
            r"(?i)never .*(edit|advance|install|activate)",
            "missing required wording: never mutate upstream state",
        )


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
