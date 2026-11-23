#!/usr/bin/env python3
"""Contract tests for the adapted planning/delivery skill topology.

These lock the *accepted target* from the reviewed adoption plan. Ordinary
explanatory prose may be rewritten freely, but workflow phase headings,
canonical output strings, and fail-closed shell shapes asserted below are
load-bearing contract surfaces:
the retired adapted cores staying out of `dot-agents/skills/` (Matt Pocock's
own skills replace them), a machine-readable source record, the Forgejo
adapter beside its tracker doc, deterministic review-dimension selection, curation that
matches the intended per-harness roles, and a timestamp-free upstream
monitor. They deliberately assert structure and authority wording, not
prose style — a skill body may be rewritten freely as long as the
contract below still holds.

Run: python3 -m unittest tests/test-adapted-agent-skills.py
"""

from __future__ import annotations

import json
import os
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_POOL = REPO_ROOT / "dot-agents" / "skills"
SKILL_SOURCES = REPO_ROOT / "dot-agents" / "skill-sources"
SOURCE_RECORD_PATH = SKILL_SOURCES / "mattpocock-skills.json"
LICENSE_PATH = SKILL_SOURCES / "mattpocock-skills-LICENSE"
RECONCILER = REPO_ROOT / "scripts" / "reconcile-agent-skills.sh"
REVIEW_CONTRACT = SKILL_POOL / "pr-self-review" / "references" / "review-contract.md"

FORGEJO_TRACKER = REPO_ROOT / "dot-agents" / "forgejo-tracker"

# The skills once adapted from Matt Pocock's suite. All retired on 2026-11-16 in
# favour of his own, which every harness loads from one checkout through
# scripts/reconcile-mattpocock-skills.sh: `codebase-architecture` for his
# `codebase-design` and `improve-codebase-architecture`, `guided-learning` for
# his `teach`, the other four for his skills of the same name. The local
# `code-review` retired the same day: its review contract moved into
# `pr-self-review` (`REVIEW_CONTRACT`), and `teammate-pr-review` reviews other
# people's PRs on top of his `code-review`.
RETIRED_ADAPTED_SKILLS = (
    "grilling",
    "wayfinder",
    "tdd",
    "diagnosing-bugs",
    "codebase-architecture",
    "guided-learning",
    "code-review",
)
# Names his promoted skills hold that the skill pool once also held. A skill pool copy of
# one of them would shadow his in Pi from `~` and collide in Claude Code and
# OpenCode, where his are linked under the same names.
HIS_NAMES_ONCE_LOCAL = ("code-review", "grilling", "tdd", "wayfinder", "diagnosing-bugs")

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
    return sorted(p for p in SKILL_POOL.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())


# Arrays in the reconciler that are *not* a per-harness curation list. They are
# inputs to one (a shared set of names) or operational allowlists, so asserting
# curation rules against them is a category error.
_NON_CURATION_ARRAYS = frozenset({"RETIRED_SKILL_POOL_TARGETS"})


def curation_arrays() -> dict[str, list[str]]:
    """The reconciler's per-harness curation arrays, with `${…[@]}` expanded.

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
    paths = sorted(SKILL_POOL.glob("*/SKILL.md"))
    paths += sorted(SKILL_POOL.glob("*/references/*.md"))
    paths += sorted((REPO_ROOT / "dot-config" / "opencode" / "agents").glob("*.md"))
    paths += sorted((REPO_ROOT / "dot-claude" / "agents").glob("*.md"))
    # The Git-backed Hermes skills route too, and they are ours to change —
    # including their background agent scripts, which select skills by name at launch.
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
    """Every skill in the skill pool must be discoverable by every harness."""

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

    def test_retired_adapted_copies_are_gone(self) -> None:
        for name in RETIRED_ADAPTED_SKILLS:
            with self.subTest(skill=name):
                self.assertFalse((SKILL_POOL / name).exists(), f"{name} retired; his copy replaces it")

    def test_no_pool_skill_takes_one_of_his_names(self) -> None:
        for name in HIS_NAMES_ONCE_LOCAL:
            with self.subTest(skill=name):
                self.assertFalse((SKILL_POOL / name).exists())

    def test_model_invoked_primitives_stay_model_invocable(self) -> None:
        """The delivery primitives load when their trigger is genuinely present."""
        for name in ("teammate-pr-review",):
            with self.subTest(skill=name):
                fields = frontmatter_fields(SKILL_POOL / name / "SKILL.md")
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
        owned = {
            "issue-plan",
            "session-handoff",
            "pr-self-review",
            "teammate-pr-review",
            "worktrunk",
            "issue-work",
            "issue-create",
            "skill-retrospective",
        }
        link = re.compile(r"\]\((?!https?:|mailto:|#)([^)]+)\)")
        for path in sorted(p for p in SKILL_POOL.glob("*/**/*.md") if p.parts[-2] in owned or p.parent.parent.name in owned):
            for target in link.findall(outside_code_fences(read(path))):
                target = target.split("#", 1)[0].strip()
                if not target:
                    continue
                with self.subTest(source=str(path.relative_to(REPO_ROOT)), target=target):
                    self.assertTrue(
                        (path.parent / target).exists(),
                        f"{path.relative_to(REPO_ROOT)} links to missing {target}",
                    )


class SessionHandoffPortabilityContractTest(unittest.TestCase):
    """A handoff must carry every required vault artifact across machines."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.handoff = read(REPO_ROOT / "dot-agents/skills/session-handoff/SKILL.md")
        cls.shared_commit_discipline = read(
            REPO_ROOT / "dot-agents/skills/vault-pkm/references/commit-discipline.md"
        )
        cls.hermes_vault = read(REPO_ROOT / "hermes/skills/note-taking/vault-pkm/SKILL.md")

    def test_handoff_dependencies_must_be_reachable_from_the_pushed_commit(self) -> None:
        normalized = " ".join(self.handoff.split())
        for phrase in (
            "handoff dependency set",
            "reachable from the pushed commit",
            "same dirty working tree does not count",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, normalized)

    def test_required_drafts_are_versioned_without_becoming_canonical(self) -> None:
        for body in (self.handoff, self.shared_commit_discipline, self.hermes_vault):
            with self.subTest(surface=body[:40]):
                normalized = " ".join(body.split())
                self.assertIn("authority label, not a Git transport rule", normalized)
                self.assertIn("explicit authorization", normalized)


class SessionHandoffEngagementContractTest(unittest.TestCase):
    """Default launches are status-tracked; fire-and-forget is explicit; the
    watch never becomes review."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.handoff = " ".join(read(REPO_ROOT / "dot-agents/skills/session-handoff/SKILL.md").split())
        cls.reference = " ".join(read(
            REPO_ROOT / "dot-agents/skills/coding-agent-handoff-supervision/references/rex-claude-handoff.md"
        ).split())

    def test_default_launch_is_status_only_and_fire_and_forget_is_explicit(self) -> None:
        for phrase in (
            "sitting in a Rex pane",
            "rex-claude-handoff.md",
            "`engagement_mode: status-only`",
            "Explicit fire-and-forget",
            "`engagement_mode: fire-and-forget`, and start no wait",
            "coding-agent-handoff-supervision",
            "never mix",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.handoff)

    def test_tripwire_forbids_review_but_permits_the_tracked_wait(self) -> None:
        for phrase in ("cannot send the background agent another turn", "read its pane, answer it, or close it",
                       "Retain only the status watch", "rex_wait.sh", "Do not poll",
                       "do **not** start the background agent again"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.handoff)

    def test_completion_distinguishes_delivered_settled_and_accepted(self) -> None:
        for phrase in ("Handoff delivered", "Background agent's turn settled",
                       "Candidate independently accepted", "the qualifier is mandatory"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.handoff)
        self.assertIn("never add a fallback model", self.handoff)

    def test_reference_documents_start_watch_and_close(self) -> None:
        for phrase in ("## Start", "## Watch and settle", "## Close", "rex_wait.sh",
                       "Never resend a prompt merely to regain a completion signal"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.reference)


class SourceRecordTest(unittest.TestCase):
    """Pinned provenance is what keeps an adaptation from becoming a silent fork."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source_record = json.loads(read(SOURCE_RECORD_PATH)) if SOURCE_RECORD_PATH.is_file() else {}

    def test_license_is_retained_beside_the_source_record(self) -> None:
        self.assertTrue(LICENSE_PATH.is_file(), "the skill source's MIT license must be stored beside the source record")
        self.assertIn("MIT License", read(LICENSE_PATH))
        self.assertIn("Matt Pocock", read(LICENSE_PATH))

    def test_source_record_header_is_complete(self) -> None:
        for key in ("upstream", "version", "commit", "license", "licenseFile", "updatePolicy"):
            with self.subTest(key=key):
                self.assertIn(key, self.source_record)
        self.assertRegex(self.source_record.get("commit", ""), r"\A[0-9a-f]{40}\Z")
        self.assertEqual(self.source_record.get("license"), "MIT")
        self.assertTrue((SKILL_SOURCES / self.source_record["licenseFile"]).is_file())

    def test_update_policy_is_automatic_pin_advance(self) -> None:
        # Bryan chose automatic advance on 2026-11-16: the pi-bots job moves the
        # pin, checks the load, commits the source record alone and announces it.
        policy = self.source_record.get("updatePolicy", {})
        self.assertTrue(policy.get("autoApply") is True)
        self.assertTrue(policy.get("humanApprovedPinAdvance") is False)
        self.assertTrue(policy.get("readOnlyDetection") is False)
        self.assertIn("mattpocock-skill-watch", policy.get("monitor", ""))

    def test_the_pin_fields_are_one_per_line_for_the_job_that_rewrites_them(self) -> None:
        # The job rewrites exactly these three lines and refuses any other shape.
        text = (SKILL_SOURCES / "mattpocock-skills.json").read_text(encoding="utf-8")
        for key in ("commit", "version", "verifiedOn"):
            self.assertRegex(text, rf'(?m)^  "{key}": "[^"]*",?$')

    def test_no_adaptation_remains(self) -> None:
        # Every adapted copy retired on 2026-11-16; his skills load as written.
        self.assertNotIn("adaptations", self.source_record)

    def test_notes_record_what_sits_on_top_of_his_skills(self) -> None:
        notes = " ".join(self.source_record.get("notes", []))
        for phrase in (
            "~/.local/share/mattpocock-skills",
            "dot-agents/forgejo-tracker/scripts/forgejo_wayfinder.py",
            "forgejo-map",
            "dot-agents/forgejo-tracker/issue-tracker-forgejo.md",
            "teammate-pr-review",
            "references/review-contract.md",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, notes)

    def test_every_local_path_the_notes_name_exists(self) -> None:
        notes = " ".join(self.source_record.get("notes", []))
        for path in re.findall(r"`((?:dot-agents|scripts)/[^`\s]+)`", notes):
            with self.subTest(path=path):
                self.assertTrue((REPO_ROOT / path).exists(), f"source record notes name missing {path}")


class AdaptedSourceRecordTest(unittest.TestCase):
    """Every source other than Matt Pocock's is adapted, and its pin is a reviewed change."""

    MONITOR = "pi-bots job adapted-skill-watch"

    @classmethod
    def setUpClass(cls) -> None:
        cls.records = {
            path.stem: json.loads(read(path))
            for path in sorted(SKILL_SOURCES.glob("*.json"))
            if path.name != SOURCE_RECORD_PATH.name
        }

    def test_ponytail_and_pstack_are_recorded(self) -> None:
        self.assertEqual(sorted(self.records), ["ponytail", "pstack-claude"])
        self.assertEqual(self.records["ponytail"]["upstream"], "https://github.com/DietrichGebert/ponytail")

    def test_each_record_has_an_exact_pin_and_its_licence(self) -> None:
        for name, record in self.records.items():
            with self.subTest(record=name):
                self.assertRegex(record.get("commit", ""), r"\A[0-9a-f]{40}\Z")
                self.assertRegex(record.get("verifiedOn", ""), r"\A\d{4}-\d{2}-\d{2}\Z")
                self.assertEqual(record.get("license"), "MIT")
                self.assertIn("MIT License", read(SKILL_SOURCES / record["licenseFile"]))

    def test_each_reviewed_pin_is_watched_by_the_adapted_skill_watch(self) -> None:
        # The pi-bots scheduled job reads every record whose pin is a reviewed
        # change and refuses one that names any other monitor.
        for name, record in self.records.items():
            with self.subTest(record=name):
                policy = record["updatePolicy"]
                self.assertIs(policy["autoApply"], False)
                self.assertIs(policy["humanApprovedPinAdvance"], True)
                self.assertEqual(policy["monitor"], self.MONITOR)
                self.assertTrue(any(a.get("watchedFiles") for a in record["adaptations"]))

    def test_every_named_monitor_exists_where_pi_bots_is_checked_out(self) -> None:
        # PI_BOTS_DIR names another pi-bots checkout, such as a worktree.
        pi_bots = Path(os.environ.get("PI_BOTS_DIR") or Path.home() / "code" / "pi-bots") / "jobs"
        if not pi_bots.is_dir():
            self.skipTest(f"no pi-bots checkout at {pi_bots.parent}")
        for record in [*self.records.values(), json.loads(read(SOURCE_RECORD_PATH))]:
            monitor = record["updatePolicy"]["monitor"]
            with self.subTest(monitor=monitor):
                self.assertRegex(monitor, r"\Api-bots job [a-z0-9-]+\Z")
                job = monitor.removeprefix("pi-bots job ")
                if job == "adapted-skill-watch" and not (pi_bots / f"{job}.json").is_file():
                    self.skipTest(f"{pi_bots.parent} does not have the adapted skill watch yet")
                self.assertTrue((pi_bots / f"{job}.json").is_file(), f"{monitor} has no job file")

    def test_each_local_path_exists(self) -> None:
        for name, record in self.records.items():
            for adaptation in record["adaptations"]:
                for path in adaptation["localPaths"]:
                    with self.subTest(record=name, path=path):
                        self.assertTrue((REPO_ROOT / path).is_file())

    def test_every_refresh_decides_each_change_with_a_reason(self) -> None:
        for name, record in self.records.items():
            refreshes = record.get("refreshes", [])
            if refreshes:
                # The refreshes chain, oldest first, and the last one ends at the pin.
                self.assertEqual(refreshes[-1]["to"], record["commit"])
                for earlier, later in zip(refreshes, refreshes[1:]):
                    self.assertEqual(later["from"], earlier["to"])
            for refresh in refreshes:
                for change in refresh["changes"]:
                    with self.subTest(record=name, change=change["change"][:40]):
                        self.assertIn(change["decision"], ("accepted", "rejected", "none"))
                        self.assertTrue(change["reason"].strip())

    def test_ponytail_is_defined_and_called_a_simplicity_review_where_it_runs(self) -> None:
        for skill in ("pr-self-review", "teammate-pr-review"):
            with self.subTest(skill=skill):
                path = SKILL_POOL / skill / "SKILL.md"
                body = read(path)
                self.assertIn("simplicity review", frontmatter_fields(path)["description"])
                self.assertRegex(body, r"(?m)^##+ .*Ponytail, the simplicity review")
                self.assertIn("Ponytail checks the", body)
                self.assertIn("named after the Ponytail plugin", " ".join(body.split()))
                self.assertIn("skill-sources/ponytail.json", body)
                self.assertTrue((path.parent / "../../skill-sources/ponytail.json").resolve().is_file())


class CurationTest(unittest.TestCase):
    """The reconciler arrays are the single curation authority."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.arrays = curation_arrays()

    def test_retired_adapted_skills_are_uncurated_everywhere(self) -> None:
        for name in RETIRED_ADAPTED_SKILLS:
            for tool, members in self.arrays.items():
                with self.subTest(tool=tool, skill=name):
                    self.assertNotIn(name, members)

    def test_existing_links_to_retired_adapted_skills_are_pruned(self) -> None:
        # Their skill pool directories are gone, so only the raw-target allowlist
        # recognises a dangling link to one as the skill pool's.
        match = re.search(r"^RETIRED_SKILL_POOL_TARGETS=\((.*?)\)", read(RECONCILER), re.DOTALL | re.MULTILINE)
        self.assertIsNotNone(match)
        retired = match.group(1).split()
        for name in RETIRED_ADAPTED_SKILLS:
            with self.subTest(skill=name):
                self.assertIn(name, retired)

    def test_local_code_review_is_retired_everywhere(self) -> None:
        self.assertFalse((SKILL_POOL / "code-review").exists())
        for tool, members in self.arrays.items():
            with self.subTest(tool=tool):
                self.assertNotIn("code-review", members)

    def test_teammate_pr_review_goes_wherever_pr_self_review_does(self) -> None:
        for tool, members in self.arrays.items():
            if "pr-self-review" in members:
                with self.subTest(tool=tool):
                    self.assertIn("teammate-pr-review", members)

    def test_adr_and_spec_coach_stays_available_on_request(self) -> None:
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
                        (SKILL_POOL / name).is_dir(),
                        f"{tool} curates {name}, which is not in the skill pool",
                    )


class RetiredRouteTest(unittest.TestCase):
    """Cleanup is proven by the absence of live references, not by intent."""

    def test_retired_pool_directories_are_gone(self) -> None:
        for name in ("git-master", "agent-workspace"):
            with self.subTest(skill=name):
                self.assertFalse((SKILL_POOL / name).exists(), f"{name} should be deleted from the pool")

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

    def test_primary_checkout_resolution_has_one_owner(self) -> None:
        body = read(SKILL_POOL / "worktrunk" / "SKILL.md")
        self.assertIn("resolve_primary_checkout", body, "worktrunk must own primary checkout/worktree resolution")
        self.assertIn("--git-common-dir", body)

    def test_consumers_cite_worktrunk_for_primary_checkout_resolution(self) -> None:
        for name in ("issue-work", "pr-self-review"):
            with self.subTest(skill=name):
                body = read(SKILL_POOL / name / "SKILL.md")
                self.assertIn("worktrunk", body, f"{name} must cite worktrunk for primary checkout resolution")


class IssueWorkRoutingTest(_MatchMixin, unittest.TestCase):
    """`issue-work` right-sizes execution and carries explicit authority."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.body = read(SKILL_POOL / "issue-work" / "SKILL.md")
        cls.handoff = read(SKILL_POOL / "issue-plan" / "references" / "handoff-contract.md")
        cls.repo_resolution = read(SKILL_POOL / "issue-work" / "references" / "repo-resolution.md")
        cls.router = read(SKILL_POOL / "issue-work" / "scripts" / "select_issue_agent.py")
        cls.handoff_supervision = read(
            SKILL_POOL / "coding-agent-handoff-supervision" / "SKILL.md"
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
            "issue-xrepo-{issue_digest}",
            "publication-summary.md",
            "each distinct issue and",
            "source_issue_mode: github_shorthand",
            "wrong forge",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.body)
        self.assertIn("{ISSUE_PRIMARY_CHECKOUT}/repos/{repo}", self.repo_resolution)
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
        self.assertIn("Use zero exploration background agents", self.body)
        self.assertIn("concrete unresolved repository question", self.body)
        self.assertNotIn("**always** at least one", self.body)

    def test_router_right_sizes_auto_work(self) -> None:
        for token in ("--task-shape", "single-loop", "substantial"):
            with self.subTest(token=token):
                self.assertIn(token, self.body)
                self.assertIn(token.replace("--", ""), self.router)
        # Since d426970 (2026-10-19) task shape right-sizes the handoff, not the
                # implementer: a Pi background agent implements both shapes unless Bryan selects
        # otherwise (Claude until 2026-11-10).
        self.assert_matches(
            self.body,
            r"(?is)Bryan's standing\s+selection is Pi for both shapes",
            "a Pi background agent must implement both task shapes by default",
        )
        self.assert_matches(
            self.body,
            r"(?is)legacy `auto` single-loop route does not supersede that instruction",
            "the router's legacy auto route must not override the standing selection",
        )
        self.assert_matches(
            self.body,
            r"(?is)another implementation route only when Bryan explicitly selects it",
            "only Bryan's explicit selection changes the route",
        )
        self.assert_matches(self.body, r"Qwen is\s+never an automatic route", "Qwen is never automatic")

    def test_visible_background_agent_uses_the_rex_procedure_and_complete_identity(self) -> None:
        self.assertIn("references/rex-claude-handoff.md", self.body)
        for field in (
            "background_agent_surface",
            "background_agent_name",
            "background_agent_pane_id",
            "background_agent_kind",
            "background_agent_session_id",
            "background_agent_worktree_identity",
        ):
            with self.subTest(field=field):
                self.assertIn(field, self.body)
                self.assertIn(field, self.handoff_supervision)
        self.assertIn("serializes provider turns within each background agent's session", self.body)
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
        cls.body = read(SKILL_POOL / "coding-agent-handoff-supervision" / "SKILL.md")
        cls.rex = read(
            SKILL_POOL
            / "coding-agent-handoff-supervision"
            / "references"
            / "rex-claude-handoff.md"
        )
        cls.scripts = SKILL_POOL / "coding-agent-handoff-supervision" / "scripts"
        cls.tests = (
            SKILL_POOL
            / "coding-agent-handoff-supervision"
            / "tests"
            / "test_rex_background_agent_pane.py"
        )

    def test_preparation_reuses_or_creates_one_ticket(self) -> None:
        for token in ("Reuse the issue", "issue-create", "duplicate", "read it back"):
            with self.subTest(token=token):
                self.assertIn(token, self.body)

    def test_artifact_not_prompt_carries_context(self) -> None:
        self.assertIn("artifact, not the prompt", self.body)
        self.assert_matches(
            self.body,
            r"(?is)issue or plan URL/path.*implementation repository.*worktree.*authority boundaries.*permissions",
            "the prompt must contain locators and authority only",
        )
        self.assert_matches(
            self.body,
            r"(?is)Do not restate steps, files, tests, requirements, or safeguards",
            "reachable requirements must not be copied into the prompt",
        )

    def test_sol_claude_boundary_is_explicit(self) -> None:
                # The Sol pairing was replaced by the orchestrator/Claude-background-agent split in
        # d426970 (2026-10-19); the orchestrator is Pi or Hermes since 4ea4140, and
        # the background agent is Pi since 2026-11-10.
        # Authorship and acceptance must still stay distinct.
        for token in ("decision-complete", "single-loop", "independent acceptance"):
            with self.subTest(token=token):
                self.assertIn(token.lower(), self.body.lower())
        self.assert_matches(
            self.body,
            r"(?is)The orchestrator \(a Pi or Hermes session\) leads; a Pi background agent implements",
            "the orchestrator/background agent roles must be explicit",
        )
        self.assert_matches(
            self.body,
            r"(?is)a background agent produces\s+changes,\s+not an accepted deliverable",
            "background agent authorship and orchestrator acceptance must stay distinct",
        )

    def test_rex_scripts_and_tests_exist(self) -> None:
        self.assertTrue((self.scripts / "rex_background_agent_pane.py").is_file())
        self.assertTrue((self.scripts / "rex_wait.sh").stat().st_mode & 0o111)
        self.assertTrue(self.tests.is_file())
        for script in ("rex_background_agent_pane.py", "rex_wait.sh"):
            with self.subTest(script=script):
                self.assertIn(script, self.body)
                self.assertIn(script, self.rex)

    def test_capacity_and_session_turn_serialization_are_hard_gates(self) -> None:
        for token in (
            "within each background agent's session",
            "Independent sessions may run concurrently",
            "Any nonzero\ncapacity result stops",
            "never switch providers",
            "75% consumed",
            "An empty capacity reading is a stop, never a pass",
            "One turn at a time per session",
        ):
            with self.subTest(token=token):
                self.assertIn(token.lower(), (self.body + self.rex).lower())
        self.assertIn("*weekly*) threshold=90 ;; *) threshold=75 ;;", self.rex)
        self.assertIn('[ -n "$cap" ] && [ "$cap" -lt "$threshold" ]', self.rex)

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
        self.assertIn("mark the identity closed/non-resumable", self.body)


class ReviewContractTest(_MatchMixin, unittest.TestCase):
    """Review keeps dimensions and quality while reducing invocations."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.body = read(SKILL_POOL / "pr-self-review" / "SKILL.md")
        cls.code_review = read(REVIEW_CONTRACT)
        cls.teammate = read(SKILL_POOL / "teammate-pr-review" / "SKILL.md")
        cls.issue_work = read(SKILL_POOL / "issue-work" / "SKILL.md")
        cls.ship = read(SKILL_POOL / "ship" / "SKILL.md")
        cls.reviewer = read(REPO_ROOT / "dot-claude" / "agents" / "dimension-reviewer.md")

    def test_dimension_selector_and_tests_exist(self) -> None:
        self.assertTrue(
            (SKILL_POOL / "pr-self-review" / "scripts" / "select_review_dimensions.py").is_file()
        )
        self.assertTrue(
            (SKILL_POOL / "pr-self-review" / "tests" / "test_select_review_dimensions.py").is_file()
        )
        self.assertIn("select_review_dimensions.py", self.body)
        self.assertIn("select_review_dimensions.py", self.code_review)

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
        self.assertIn("model: claude-opus-5-5", self.reviewer)
        self.assertIn("Do not spend another background agent", self.reviewer)

    def test_orchestrator_is_independent_for_background_agent_authored_candidate(self) -> None:
        self.assertIn("The orchestrator is the independent acceptance context", self.issue_work)
        self.assertNotRegex(self.issue_work, r"\bSol\b")
        self.assertIn("systematic orchestrator review", self.ship)
        self.assertIn("the orchestrator is the independent acceptance context", self.body)
        self.assertIn("orchestrator-authored candidate\nrequires an independent review context", self.ship)
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
            "issue URL/host/repository",
            "implementation\nhost/repository",
            "state directory",
            "worktree",
        ):
            with self.subTest(identity=identity):
                self.assertIn(identity, self.body)

    def test_ship_accepts_integrated_independent_evidence(self) -> None:
        self.assertIn("integrated review contract in `pr-self-review`", self.ship)
        self.assertIn("references/review-contract.md", self.ship)
        self.assertIn("Missing or stale Ponytail evidence blocks\npublication", self.ship)
        self.assertIn("Exact-candidate Standards, Spec, conditional Risk, and Ponytail", self.ship)

    def test_pr_self_review_points_at_its_review_contract(self) -> None:
        self.assertIn("references/review-contract.md", self.body)
        self.assertNotIn("Load `code-review`", self.body)
        self.assertIn("For someone else's PR use `teammate-pr-review`", self.body)

    def test_teammate_review_stacks_on_his_code_review(self) -> None:
        normalized = " ".join(self.teammate.split())
        self.assertIn("Matt Pocock's `code-review` skill supplies only the Standards and Spec passes", normalized)
        self.assertIn("../pr-self-review/references/review-contract.md", self.teammate)
        for heading in ("## Human-facing review draft", "## Finding bar"):
            with self.subTest(heading=heading):
                self.assertIn(heading, self.teammate)
        description = frontmatter_fields(SKILL_POOL / "teammate-pr-review" / "SKILL.md")["description"]
        self.assertIn("someone else's pull request", description)

    def test_teammate_review_carries_the_drafting_and_gate_rules_whole(self) -> None:
        for phrase in (
            "Choose the proposed review event from the evidence",
            "propose `APPROVE` with an empty body",
            "Never put chat drafts in fenced blocks",
            "Zero findings is a valid successful review",
            "a surviving mutation establishes a coverage gap",
            "Never preserve the original conclusion by changing qualifiers",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, " ".join(self.teammate.split()))


class ForgejoAdapterTest(_MatchMixin, unittest.TestCase):
    """The Forgejo adapter is a command under his `wayfinder`, not a skill."""

    def test_adapter_tests_and_reference_live_beside_the_tracker_doc(self) -> None:
        for relative in (
            "scripts/forgejo_wayfinder.py",
            "tests/test_forgejo_wayfinder.py",
            "references/forgejo-tracker.md",
            "issue-tracker-forgejo.md",
        ):
            with self.subTest(path=relative):
                self.assertTrue((FORGEJO_TRACKER / relative).is_file())

    def test_the_tracker_directory_is_not_a_skill(self) -> None:
        self.assertFalse((FORGEJO_TRACKER / "SKILL.md").exists())

    def test_launcher_runs_the_moved_adapter(self) -> None:
        launcher = read(REPO_ROOT / "dot-agents" / "bin" / "forgejo-map")
        self.assertIn('"$bin_dir/../forgejo-tracker/scripts"', launcher)
        self.assertNotIn("skills/wayfinder", launcher)

    def test_reference_runs_the_adapter_from_its_new_path(self) -> None:
        body = read(FORGEJO_TRACKER / "references" / "forgejo-tracker.md")
        self.assertIn("dot-agents/forgejo-tracker/scripts/forgejo_wayfinder.py", body)
        self.assertNotIn("skills/wayfinder", body)

    def test_adapter_still_refuses_a_public_tracker(self) -> None:
        body = read(FORGEJO_TRACKER / "scripts" / "forgejo_wayfinder.py")
        self.assert_matches(body, r"(?i)private only", "missing required wording: private only")


class WritingGovernanceTest(_MatchMixin, unittest.TestCase):
    """Two narrow refinements land on their existing canonical owners."""

    def test_readme_prefers_sharpening_the_pointer_over_inlining(self) -> None:
        body = read(REPO_ROOT / "dot-agents" / "README.md")
        self.assert_matches(
            body, r"(?i)trigger wording", "missing required wording: trigger wording"
        )
        self.assert_matches(body, r"(?i)inlin", "missing required wording: inline")

    def test_retrospective_treats_repeated_lookups_as_a_stale_cache(self) -> None:
        body = read(SKILL_POOL / "skill-retrospective" / "SKILL.md")
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
