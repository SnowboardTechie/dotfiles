#!/usr/bin/env python3
"""Contract tests for the black-box-verification skill adoption.

Locks the accepted shape from the adoption plan, not the prose: the skill is
discoverable, its two references are reachable from explicit triggers, the
issue workflows route to it conditionally, its pstack provenance is pinned and
licensed, and the reconciler curates it for every runtime without installing
pstack itself.

Run: python3 -m unittest tests/test-black-box-verification.py
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
POOL = REPO_ROOT / "dot-agents" / "skills"
SKILL_DIR = POOL / "black-box-verification"
SKILL = SKILL_DIR / "SKILL.md"
REFERENCES = ("change-impact.md", "project-recipe.md")
UPSTREAMS = REPO_ROOT / "dot-agents" / "upstreams"
LEDGER_PATH = UPSTREAMS / "pstack-claude.json"
PINNED_COMMIT = "963781d11834918bf0951202d721c2e144777a70"
RECONCILER = REPO_ROOT / "scripts" / "reconcile-agent-skills.sh"
CURATED_FOR = ("CLAUDE_SKILLS", "CODEX_SKILLS", "PI_SKILLS", "OPENCODE_SKILLS", "HERMES_SKILLS")

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def frontmatter_fields(path: Path) -> dict[str, str]:
    match = FRONTMATTER.match(read(path))
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if line[:1] not in (" ", "\t") and ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields


def curation_arrays() -> dict[str, list[str]]:
    """Reconciler arrays with `${…[@]}` expanded; the reconciler is the authority."""
    parsed: dict[str, list[str]] = {}
    for match in re.finditer(r"^([A-Z_]+)=\((.*?)\)\s*$", read(RECONCILER), re.DOTALL | re.MULTILINE):
        tokens: list[str] = []
        for token in match.group(2).split():
            token = token.strip().strip('"')
            expand = re.fullmatch(r"\$\{([A-Z_]+)\[@\]\}", token)
            if expand:
                tokens.extend(parsed.get(expand.group(1), []))
            elif token and not token.startswith("#"):
                tokens.append(token)
        parsed[match.group(1)] = tokens
    return parsed


def paragraphs_naming(body: str, needle: str) -> list[str]:
    return [p for p in re.split(r"\n\s*\n", body) if needle in p]


class DiscoveryTest(unittest.TestCase):
    def test_skill_is_in_the_pool_with_frontmatter(self) -> None:
        fields = frontmatter_fields(SKILL)
        self.assertEqual(fields.get("name"), "black-box-verification")
        description = fields.get("description", "")
        self.assertRegex(description, r"\AUse when proving behavior through a public interface")

    def test_skill_stays_model_invocable(self) -> None:
        self.assertNotIn("disable-model-invocation", frontmatter_fields(SKILL))

    def test_separates_black_box_from_change_impact(self) -> None:
        body = read(SKILL)
        self.assertRegex(body, r"(?i)black-box verification")
        self.assertRegex(body, r"(?i)change-impact investigation")
        self.assertRegex(body, r"(?i)test selection")
        self.assertRegex(body, r"(?i)not required to execute")
        self.assertRegex(body, r"(?i)expectations come from the contract")

    def test_planning_keeps_permitted_isolated_probes(self) -> None:
        for path in (SKILL, SKILL_DIR / "references" / "change-impact.md"):
            with self.subTest(source=path.name):
                body = read(path)
                self.assertRegex(body, r"(?i)scratch or in-memory probes?")
                self.assertRegex(body, r"(?i)implementation authority")

    def test_states_honest_result_rules(self) -> None:
        body = read(SKILL)
        self.assertRegex(body, r"(?i)mocks?\b.*not proof")
        self.assertRegex(body, r"(?i)substituted")
        self.assertRegex(body, r"(?i)untested")
        self.assertRegex(body, r"(?i)failing setup[\s\S]*not a reproduced\s+regression")

    def test_grants_no_authority(self) -> None:
        body = read(SKILL)
        self.assertRegex(body, r"(?i)planning is read-only")
        self.assertRegex(body, r"(?i)grants nothing")
        self.assertRegex(body, r"(?i)no dependency or software install")


class ReferenceTest(unittest.TestCase):
    def test_every_relative_link_resolves(self) -> None:
        for source in (SKILL, *(SKILL_DIR / "references" / r for r in REFERENCES)):
            for target in LINK.findall(read(source)):
                if target.startswith(("http://", "https://", "#")):
                    continue
                with self.subTest(source=source.name, target=target):
                    self.assertTrue((source.parent / target.split("#", 1)[0]).resolve().exists())

    def test_each_reference_is_linked_behind_an_explicit_trigger(self) -> None:
        body = read(SKILL)
        for name in REFERENCES:
            with self.subTest(reference=name):
                self.assertTrue((SKILL_DIR / "references" / name).is_file())
                pointers = paragraphs_naming(body, f"](references/{name})")
                self.assertTrue(pointers, f"SKILL.md never links references/{name}")
                self.assertRegex(pointers[0], r"(?i)open when")

    def test_change_impact_is_bounded(self) -> None:
        body = read(SKILL_DIR / "references" / "change-impact.md")
        self.assertRegex(body, r"(?i)one or two")
        self.assertRegex(body, r"(?i)exhaustive caller inventory")
        self.assertRegex(body, r"(?i)fan-out")

    def test_project_recipe_covers_the_required_sections(self) -> None:
        body = read(SKILL_DIR / "references" / "project-recipe.md")
        for pattern in (
            r"(?i)launch, readiness, and ownership",
            r"(?i)\*\*drive",
            r"(?i)independent expected results",
            r"(?i)side-effect readback",
            r"(?i)isolation and cleanup",
            r"(?i)reuse before generating",
            r"(?i)placement is a decision",
        ):
            with self.subTest(pattern=pattern):
                self.assertRegex(body, pattern)


class RoutingTest(unittest.TestCase):
    def test_issue_plan_routes_unproven_cross_boundary_assumptions(self) -> None:
        body = read(POOL / "issue-plan" / "SKILL.md")
        rows = [line for line in body.splitlines() if line.startswith("|") and "black-box-verification" in line]
        self.assertEqual(len(rows), 1, "issue-plan needs exactly one planning-table route")
        self.assertRegex(rows[0], r"(?i)boundary")
        self.assertRegex(rows[0], r"(?i)change-impact")

    def test_issue_work_routes_public_interface_behavior_conditionally(self) -> None:
        body = read(POOL / "issue-work" / "SKILL.md")
        route = paragraphs_naming(body, "`black-box-verification`")
        self.assertEqual(len(route), 1, "issue-work needs one routing paragraph")
        self.assertRegex(route[0], r"(?i)public-interface")
        self.assertRegex(route[0], r"(?i)no gate for internal logic, documentation, or trivial")


class ProvenanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ledger = json.loads(read(LEDGER_PATH))

    def test_pin_and_license(self) -> None:
        self.assertEqual(self.ledger["upstream"], "https://github.com/michael-denyer/pstack-claude")
        self.assertEqual(self.ledger["commit"], PINNED_COMMIT)
        self.assertEqual(self.ledger["license"], "MIT")
        license_text = read(UPSTREAMS / self.ledger["licenseFile"])
        self.assertIn("MIT License", license_text)
        self.assertIn("Lauren Tan", license_text)
        self.assertIn("Michael Denyer", license_text)

    def test_update_policy_is_manual_and_unwatched(self) -> None:
        policy = self.ledger["updatePolicy"]
        self.assertIs(policy["autoApply"], False)
        self.assertIs(policy["humanApprovedPinAdvance"], True)
        self.assertIsNone(policy["monitor"])

    def test_adaptation_maps_both_upstream_skills(self) -> None:
        (entry,) = self.ledger["adaptations"]
        self.assertEqual(entry["skill"], "black-box-verification")
        upstream = " ".join(entry["upstreamPaths"])
        self.assertIn("skills/blast-radius/", upstream)
        self.assertIn("skills/create-verification-skill/", upstream)
        self.assertTrue(set(entry["watchedFiles"]).issubset(entry["upstreamPaths"]))
        for local in entry["localPaths"]:
            with self.subTest(local=local):
                self.assertTrue((REPO_ROOT / local).is_file())
        for key in ("localChanges", "acceptedUpstreamRules", "rejectedUpstreamRules"):
            with self.subTest(key=key):
                self.assertTrue(entry[key])

    def test_rejected_rules_cover_fan_out_autonomy_and_shipping(self) -> None:
        rejected = " ".join(self.ledger["adaptations"][0]["rejectedUpstreamRules"]).lower()
        for term in ("fan-out", "autonomy", "shipping"):
            with self.subTest(term=term):
                self.assertIn(term, rejected)

    def test_skill_points_at_the_ledger(self) -> None:
        self.assertIn("upstreams/pstack-claude.json", read(SKILL))


class CurationTest(unittest.TestCase):
    def test_curated_for_every_runtime(self) -> None:
        arrays = curation_arrays()
        for tool in CURATED_FOR:
            with self.subTest(tool=tool):
                self.assertIn("black-box-verification", arrays.get(tool, []))

    def test_pstack_itself_is_not_installed(self) -> None:
        arrays = curation_arrays()
        for tool in CURATED_FOR:
            with self.subTest(tool=tool):
                self.assertFalse([n for n in arrays.get(tool, []) if "pstack" in n])
        self.assertNotIn("pstack", read(REPO_ROOT / "dot-claude" / "settings.json"))


if __name__ == "__main__":
    unittest.main()
