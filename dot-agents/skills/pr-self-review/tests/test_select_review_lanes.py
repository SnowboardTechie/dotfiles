#!/usr/bin/env python3
"""Tests for deterministic review-lane selection.

The contract these lock:

* Standards and Spec always run — no input suppresses them.
* Risk runs on a real signal in the changed paths.
* Risk always runs for CairnOS, whatever the diff touches.
* Ambiguity includes Risk rather than excluding it.
* Selection reports its reasons, so a reviewer can see why a lane ran.

Run: python3 -m unittest dot-agents/skills/pr-self-review/tests/test_select_review_lanes.py
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "select_review_lanes.py"
SPEC = importlib.util.spec_from_file_location("select_review_lanes", MODULE_PATH)
assert SPEC and SPEC.loader
LANES = importlib.util.module_from_spec(SPEC)
# Register before exec: @dataclass resolves annotations through sys.modules.
sys.modules["select_review_lanes"] = LANES
SPEC.loader.exec_module(LANES)

ORDINARY = ["README.md", "src/format_date.ts", "docs/usage.md", "src/format_date.test.ts"]


class AlwaysLanesTest(unittest.TestCase):
    def test_standards_and_spec_run_on_an_ordinary_change(self) -> None:
        selection = LANES.select_lanes("bryan/notes", ORDINARY)
        self.assertEqual(selection.lanes, ["standards", "spec"])

    def test_standards_and_spec_run_on_an_empty_diff(self) -> None:
        selection = LANES.select_lanes("bryan/notes", [])
        self.assertEqual(selection.lanes, ["standards", "spec"])

    def test_standards_and_spec_cannot_be_suppressed_by_any_input(self) -> None:
        for changed in ([], [""], ["   "], ["src/auth.py"], ["../../etc/passwd"]):
            with self.subTest(changed=changed):
                lanes = LANES.select_lanes("bryan/anything", changed).lanes
                self.assertIn("standards", lanes)
                self.assertIn("spec", lanes)

    def test_lane_order_is_stable(self) -> None:
        selection = LANES.select_lanes("bryan/cairn-os", ORDINARY)
        self.assertEqual(selection.lanes, ["standards", "spec", "risk"])


class RiskTriggerTest(unittest.TestCase):
    def assert_risk(self, path: str) -> None:
        selection = LANES.select_lanes("bryan/notes", [path])
        self.assertTrue(
            selection.risk_selected, f"{path} should have selected the Risk lane"
        )
        self.assertTrue(selection.reasons["risk"], "Risk must report why it ran")

    def test_security_and_data_paths_select_risk(self) -> None:
        for path in (
            "src/auth/session.ts",
            "api/oauth_callback.py",
            "lib/permissions.rs",
            "config/secrets.yaml",
            "deploy/credentials.tf",
            "certs/server.pem",
            "src/crypto/signing.go",
        ):
            with self.subTest(path=path):
                self.assert_risk(path)

    def test_operational_paths_select_risk(self) -> None:
        for path in (
            ".github/workflows/release.yml",
            "Dockerfile",
            "docker-compose.yml",
            "db/migrations/0003_add_users.sql",
            "deploy/rollback.sh",
            "src/queue/worker.py",
            "app/webhooks/stripe.ts",
            "scripts/install.sh",
            ".env.production",
            "nix/systemd-units.nix",
        ):
            with self.subTest(path=path):
                self.assert_risk(path)

    def test_agent_and_memory_paths_select_risk(self) -> None:
        for path in (
            "dot-agents/skills/issue-work/SKILL.md",
            "hermes/scripts/check-something.py",
            "src/memory/recall.py",
        ):
            with self.subTest(path=path):
                self.assert_risk(path)

    def test_concurrency_paths_select_risk(self) -> None:
        self.assert_risk("internal/locking/mutex.go")

    def test_an_ordinary_change_does_not_select_risk(self) -> None:
        self.assertFalse(LANES.select_lanes("bryan/notes", ORDINARY).risk_selected)

    def test_windows_separators_are_normalized(self) -> None:
        self.assertTrue(
            LANES.select_lanes("bryan/notes", ["src\\auth\\session.ts"]).risk_selected
        )


class AmbiguityTest(unittest.TestCase):
    def test_an_unrecognized_security_adjacent_path_includes_risk(self) -> None:
        """A false Risk lane costs one child agent; a missed one ships the defect."""
        for path in (
            "src/sanitize_untrusted_payload.ts",
            "lib/privacy_filter.py",
            "internal/audit_policy.go",
            "src/pii_scrubber.rb",
        ):
            with self.subTest(path=path):
                selection = LANES.select_lanes("bryan/notes", [path])
                self.assertTrue(selection.risk_selected)

    def test_the_ambiguous_reason_is_labelled_as_such(self) -> None:
        selection = LANES.select_lanes("bryan/notes", ["src/sanitize_input.ts"])
        self.assertTrue(
            any("ambiguous" in reason for reason in selection.reasons["risk"]),
            "an ambiguous match must say so, so a reviewer can judge it",
        )


class CairnOsTest(unittest.TestCase):
    def test_cairnos_always_selects_risk(self) -> None:
        """A cosmetic-looking change can still alter boot, permissions, or updates."""
        for repo in ("bryan/cairn-os", "cairn-os", "someone/cairn_os", "bryan/cairnos"):
            with self.subTest(repo=repo):
                selection = LANES.select_lanes(repo, ["README.md"])
                self.assertTrue(selection.risk_selected)

    def test_cairnos_risk_reason_names_the_repository_rule(self) -> None:
        selection = LANES.select_lanes("bryan/cairn-os", ["README.md"])
        self.assertTrue(
            any("always runs Risk" in reason for reason in selection.reasons["risk"])
        )

    def test_a_similarly_named_repository_is_not_swept_in(self) -> None:
        self.assertFalse(LANES.select_lanes("bryan/cairn-os-docs-site", ["README.md"]).risk_selected)

    def test_cairnos_risk_survives_alongside_path_reasons(self) -> None:
        selection = LANES.select_lanes("bryan/cairn-os", ["src/auth/session.ts"])
        self.assertGreaterEqual(len(selection.reasons["risk"]), 2)


class ReasonTest(unittest.TestCase):
    def test_reasons_are_deduplicated_by_cause_not_by_file(self) -> None:
        many = [f"src/auth/handler_{i}.ts" for i in range(10)]
        selection = LANES.select_lanes("bryan/notes", many)
        auth = [r for r in selection.reasons["risk"] if "authentication" in r]
        self.assertEqual(len(auth), 1)

    def test_reasons_are_sorted_so_output_is_stable(self) -> None:
        changed = ["src/queue/worker.py", "src/auth/session.ts", "Dockerfile"]
        first = LANES.select_lanes("bryan/notes", changed).reasons["risk"]
        second = LANES.select_lanes("bryan/notes", list(reversed(changed))).reasons["risk"]
        self.assertEqual(first, second)

    def test_always_lanes_state_why_they_ran(self) -> None:
        selection = LANES.select_lanes("bryan/notes", ORDINARY)
        self.assertEqual(selection.reasons["standards"], ["always runs"])
        self.assertEqual(selection.reasons["spec"], ["always runs"])


class ContentSignalTest(unittest.TestCase):
    """Paths alone are not enough — a neutral filename can carry real risk."""

    def diff(self, path: str, *added: str) -> list[str]:
        return [f"--- a/{path}", f"+++ b/{path}"] + [f"+{line}" for line in added]

    def assert_content_risk(self, path: str, line: str, expect: str) -> None:
        selection = LANES.select_lanes("bryan/notes", [], self.diff(path, line))
        self.assertTrue(
            selection.risk_selected,
            f"{line!r} in {path} should have selected Risk",
        )
        joined = " ".join(selection.reasons["risk"])
        self.assertIn(expect, joined)

    def test_a_neutral_filename_that_parses_input_selects_risk(self) -> None:
        """`src/parser.py` is the contract's own example."""
        self.assert_content_risk(
            "src/parser.py", "return json.loads(raw)", "parsing or deserializing"
        )

    def test_each_named_risk_area_has_a_content_signal(self) -> None:
        cases = [
            ("src/util.py", "if authenticate(user, password):", "authentication"),
            ("src/util.py", "body = request.json", "untrusted input"),
            ("src/util.py", "subprocess.run(cmd, shell=True)", "process execution"),
            ("src/ui.tsx", "el.innerHTML = value", "unescaped markup"),
            ("src/util.py", "requests.get(url)", "outbound network call"),
            ("src/util.py", "return redirect(target)", "redirect or cross-origin"),
            ("src/util.py", "os.chmod(path, 0o600)", "filesystem path or permission"),
            ("src/util.py", "cur.execute('ALTER TABLE users ADD COLUMN x')", "persistence or migration"),
            ("src/util.py", "task.retry(backoff=2)", "queue or retry"),
            ("src/util.py", "with Lock():", "concurrency control"),
            ("ops/run.sh", "kubectl apply -f manifest.yaml", "deployment, promotion, or rollback"),
            ("ops/run.sh", "npm publish --access public", "package publication"),
            ("cfg/job.json", '"enabledToolsets": ["terminal"]', "agent permissions"),
            ("src/util.py", "recall(query)", "memory retention"),
            ("ops/run.sh", "git push origin HEAD", "unattended mutation"),
            ("src/util.py", "digest = hashlib.sha256(data)", "cryptography or randomness"),
        ]
        for path, line, expect in cases:
            with self.subTest(area=expect):
                self.assert_content_risk(path, line, expect)

    def test_unknown_security_adjacent_content_fails_closed_to_risk(self) -> None:
        selection = LANES.select_lanes(
            "bryan/notes", [], self.diff("src/util.py", "flag = is_untrusted_origin(x)")
        )
        self.assertTrue(selection.risk_selected)
        self.assertTrue(
            any("unrecognized" in r for r in selection.reasons["risk"]),
            "an unmatched security-adjacent line must be labelled as unknown",
        )

    def test_an_ordinary_diff_does_not_select_risk(self) -> None:
        """An always-on Risk lane carries no signal."""
        selection = LANES.select_lanes(
            "bryan/notes",
            [],
            self.diff(
                "src/format_date.ts",
                "export const fmt = (d: Date) => d.toISOString().slice(0, 10);",
                "const LABEL = 'Updated';",
            ),
        )
        self.assertFalse(selection.risk_selected, selection.reasons.get("risk"))

    def test_comments_and_blank_lines_do_not_trigger(self) -> None:
        for line in ("# TODO: think about security later", "// sanitize this eventually", ""):
            with self.subTest(line=line):
                selection = LANES.select_lanes(
                    "bryan/notes", [], self.diff("src/util.py", line)
                )
                self.assertFalse(selection.risk_selected)

    def test_removed_lines_cannot_introduce_risk(self) -> None:
        diff = ["--- a/src/util.py", "+++ b/src/util.py", "-subprocess.run(cmd, shell=True)"]
        self.assertFalse(LANES.select_lanes("bryan/notes", [], diff).risk_selected)

    def test_the_file_header_is_not_treated_as_content(self) -> None:
        diff = ["--- a/src/auth_notes.md", "+++ b/src/auth_notes.md", "+plain prose"]
        selection = LANES.select_lanes("bryan/notes", [], diff)
        # The *path* is what triggers here, not the `+++` line.
        self.assertTrue(selection.risk_selected)
        self.assertTrue(any("authentication" in r for r in selection.reasons["risk"]))

    def test_a_deleted_risky_path_selects_risk(self) -> None:
        """Removing an auth module is exactly the change that needs Risk.

        `git diff` writes `+++ /dev/null` for a deletion, so a classifier that
        read only the `+++` header saw no paths at all.
        """
        diff = ["--- a/src/auth/session.py", "+++ /dev/null", "-def login(): ..."]
        selection = LANES.select_lanes("bryan/notes", [], diff)
        self.assertEqual(LANES.changed_files_from_diff(diff), ["src/auth/session.py"])
        self.assertTrue(selection.risk_selected)
        self.assertTrue(any("authentication" in r for r in selection.reasons["risk"]))

    def test_a_deleted_neutral_path_does_not_select_risk(self) -> None:
        diff = ["--- a/docs/notes.md", "+++ /dev/null", "-just prose"]
        self.assertFalse(LANES.select_lanes("bryan/notes", [], diff).risk_selected)

    def test_an_added_risky_path_selects_risk(self) -> None:
        diff = ["--- /dev/null", "+++ b/src/auth/session.py", "+def login(): ..."]
        self.assertEqual(LANES.changed_files_from_diff(diff), ["src/auth/session.py"])
        self.assertTrue(LANES.select_lanes("bryan/notes", [], diff).risk_selected)

    def test_a_rename_reports_both_sides(self) -> None:
        """The old location can carry a signal the new one does not."""
        diff = ["--- a/src/auth/session.py", "+++ b/src/util/session.py"]
        self.assertEqual(
            LANES.changed_files_from_diff(diff),
            ["src/auth/session.py", "src/util/session.py"],
        )
        self.assertTrue(LANES.select_lanes("bryan/notes", [], diff).risk_selected)

    def test_a_modified_file_is_not_double_counted(self) -> None:
        diff = ["--- a/src/auth/session.py", "+++ b/src/auth/session.py", "+x = 1"]
        self.assertEqual(LANES.changed_files_from_diff(diff), ["src/auth/session.py"])
        reasons = LANES.select_lanes("bryan/notes", [], diff).reasons["risk"]
        self.assertEqual(len([r for r in reasons if "authentication or authorization" in r]), 1)

    def test_both_dev_null_sides_are_excluded(self) -> None:
        self.assertEqual(
            LANES.changed_files_from_diff(["--- /dev/null", "+++ /dev/null"]), []
        )

    def test_added_lines_attach_to_the_new_path_only(self) -> None:
        """A deletion has no new path, so its removed lines attach to nothing."""
        diff = [
            "--- a/gone.py", "+++ /dev/null", "-secret = load()",
            "--- a/src/parser.py", "+++ b/src/parser.py", "+data = json.loads(raw)",
        ]
        pairs = LANES.added_lines_with_paths(diff)
        self.assertEqual(pairs, [("src/parser.py", "data = json.loads(raw)")])

    def test_a_multi_file_diff_classifies_every_touched_path(self) -> None:
        diff = [
            "--- a/README.md", "+++ b/README.md", "+docs",
            "--- a/src/auth/session.py", "+++ /dev/null",
            "--- /dev/null", "+++ b/db/migrations/001.sql", "+CREATE TABLE t (id int);",
        ]
        paths = LANES.changed_files_from_diff(diff)
        self.assertEqual(
            paths, ["README.md", "src/auth/session.py", "db/migrations/001.sql"]
        )
        reasons = " ".join(LANES.select_lanes("bryan/notes", [], diff).reasons["risk"])
        self.assertIn("authentication", reasons)
        self.assertIn("persistence", reasons)

    def test_paths_are_derived_from_the_diff_when_not_supplied(self) -> None:
        diff = ["--- a/src/auth/session.ts", "+++ b/src/auth/session.ts", "+const x = 1;"]
        self.assertEqual(LANES.changed_files_from_diff(diff), ["src/auth/session.ts"])
        self.assertTrue(LANES.select_lanes("bryan/notes", [], diff).risk_selected)

    def test_content_reasons_are_deduplicated_and_stable(self) -> None:
        diff = self.diff(
            "src/util.py",
            "a = json.loads(one)",
            "b = json.loads(two)",
            "c = json.loads(three)",
        )
        reasons = LANES.select_lanes("bryan/notes", [], diff).reasons["risk"]
        parsing = [r for r in reasons if "parsing" in r]
        self.assertEqual(len(parsing), 1)
        self.assertEqual(
            reasons, LANES.select_lanes("bryan/notes", [], diff).reasons["risk"]
        )

    def test_omitting_the_diff_is_reported_as_a_weaker_selection(self) -> None:
        """Silence about a skipped sweep would read as a clean sweep."""
        selection = LANES.select_lanes("bryan/notes", ["README.md"])
        self.assertTrue(any("content signals were not evaluated" in n for n in selection.notes))
        self.assertIn("note:", selection.render())

    def test_supplying_a_diff_leaves_no_content_sweep_note(self) -> None:
        selection = LANES.select_lanes("bryan/notes", [], self.diff("README.md", "hello"))
        self.assertFalse([n for n in selection.notes if "content signals" in n])

    def test_a_diff_alone_is_still_flagged_as_a_weaker_path_authority(self) -> None:
        """Content is covered; path identity is not. Both facts must be said."""
        selection = LANES.select_lanes("bryan/notes", [], self.diff("README.md", "hello"))
        self.assertTrue([n for n in selection.notes if "unified diff headers" in n])

    def test_name_status_plus_diff_is_the_complete_pair(self) -> None:
        selection = LANES.select_lanes(
            "bryan/notes",
            None,
            self.diff("README.md", "hello"),
            LANES.parse_name_status("M\0README.md\0"),
        )
        self.assertEqual(selection.notes, [])

    def test_a_prose_only_signal_is_marked_as_prose(self) -> None:
        """Discussing authentication and changing it deserve different attention."""
        selection = LANES.select_lanes(
            "bryan/notes",
            [],
            self.diff("docs/design.md", "The service handles authentication by ..."),
        )
        self.assertTrue(selection.risk_selected, "prose still selects the lane")
        self.assertTrue(any(" in prose (" in r for r in selection.reasons["risk"]))
        self.assertTrue(any("came from documentation" in n for n in selection.notes))

    def test_a_code_example_outranks_a_prose_one_for_the_same_reason(self) -> None:
        diff = (
            self.diff("docs/design.md", "we use json.loads on the payload")
            + self.diff("src/parser.py", "data = json.loads(raw)")
        )
        selection = LANES.select_lanes("bryan/notes", [], diff)
        parsing = [r for r in selection.reasons["risk"] if "parsing" in r]
        self.assertEqual(len(parsing), 1)
        self.assertNotIn(" in prose (", parsing[0])
        self.assertIn("src/parser.py", parsing[0])
        self.assertFalse(
            [n for n in selection.notes if "documentation" in n],
            "a code signal is present, so no prose-only note",
        )

    def test_reasons_name_the_file_they_came_from(self) -> None:
        selection = LANES.select_lanes(
            "bryan/notes", [], self.diff("src/parser.py", "data = json.loads(raw)")
        )
        self.assertIn("src/parser.py", " ".join(selection.reasons["risk"]))

    def test_cairnos_still_always_selects_risk_with_a_clean_diff(self) -> None:
        selection = LANES.select_lanes(
            "bryan/cairn-os", [], self.diff("README.md", "just docs")
        )
        self.assertTrue(selection.risk_selected)
        self.assertTrue(any("always runs Risk" in r for r in selection.reasons["risk"]))


class NameStatusTest(unittest.TestCase):
    """Git's name-status inventory is the authority on which paths moved.

    Captured from real `git diff --name-status -z -M` output. Two cases prove
    why unified headers cannot be trusted for path identity:

    * a content-identical rename shows as `--- /dev/null` + `+++ b/new`, so the
      *old* path is absent entirely;
    * a binary delete produces no `---`/`+++` headers at all.
    """

    # Exactly what git emitted for: modify, add, binary delete, 100% rename.
    REAL = (
        "M\0docs/notes.md\0"
        "A\0src/added.py\0"
        "D\0src/auth/blob.bin\0"
        "R100\0src/auth/session.py\0src/util/session.py\0"
    )

    def paths(self, raw: str) -> list[str]:
        return LANES.changed_files_from_name_status(LANES.parse_name_status(raw))

    def test_it_parses_every_status_shape(self) -> None:
        changes = LANES.parse_name_status(self.REAL)
        self.assertEqual(
            [(c.status, c.paths) for c in changes],
            [
                ("M", ("docs/notes.md",)),
                ("A", ("src/added.py",)),
                ("D", ("src/auth/blob.bin",)),
                ("R100", ("src/auth/session.py", "src/util/session.py")),
            ],
        )

    def test_a_content_identical_rename_classifies_both_sides(self) -> None:
        """The source path carries the signal the destination laundered away."""
        raw = "R100\0src/auth/session.py\0src/util/session.py\0"
        self.assertEqual(self.paths(raw), ["src/auth/session.py", "src/util/session.py"])
        selection = LANES.select_lanes(
            "bryan/notes", None, None, LANES.parse_name_status(raw)
        )
        self.assertTrue(selection.risk_selected)
        self.assertTrue(any("authentication" in r for r in selection.reasons["risk"]))

    def test_a_rename_is_invisible_to_unified_headers(self) -> None:
        """The regression, stated against the weaker path."""
        unified = ["--- /dev/null", "+++ b/src/util/session.py", "+def login(): ..."]
        self.assertEqual(LANES.changed_files_from_diff(unified), ["src/util/session.py"])
        self.assertNotIn("src/auth/session.py", LANES.changed_files_from_diff(unified))

    def test_a_binary_deletion_classifies(self) -> None:
        """A binary delete emits no unified headers at all."""
        raw = "D\0src/auth/blob.bin\0"
        self.assertEqual(self.paths(raw), ["src/auth/blob.bin"])
        self.assertTrue(
            LANES.select_lanes("bryan/notes", None, None, LANES.parse_name_status(raw)).risk_selected
        )

    def test_a_copy_classifies_both_sides(self) -> None:
        raw = "C075\0src/auth/session.py\0src/util/copy.py\0"
        self.assertEqual(self.paths(raw), ["src/auth/session.py", "src/util/copy.py"])
        self.assertTrue(
            LANES.select_lanes("bryan/notes", None, None, LANES.parse_name_status(raw)).risk_selected
        )

    def test_ordinary_add_modify_delete(self) -> None:
        raw = "A\0src/a.py\0M\0src/b.py\0D\0src/c.py\0"
        self.assertEqual(self.paths(raw), ["src/a.py", "src/b.py", "src/c.py"])
        self.assertFalse(
            LANES.select_lanes("bryan/notes", None, None, LANES.parse_name_status(raw)).risk_selected
        )

    def test_no_double_count(self) -> None:
        """A path that appears twice yields one path and one reason."""
        raw = (
            "R100\0src/auth/session.py\0src/util/session.py\0"
            "M\0src/auth/session.py\0"
        )
        self.assertEqual(self.paths(raw), ["src/auth/session.py", "src/util/session.py"])
        reasons = LANES.select_lanes(
            "bryan/notes", None, None, LANES.parse_name_status(raw)
        ).reasons["risk"]
        self.assertEqual(len([r for r in reasons if "authentication or authorization" in r]), 1)

    def test_unusual_but_valid_path_bytes_survive(self) -> None:
        """`-z` removes Git's quoting, so odd names arrive verbatim."""
        odd = 'src/weird name;with a "quote".py'
        raw = f"M\0{odd}\0"
        self.assertEqual(self.paths(raw), [odd])

    def test_a_path_with_a_control_character_is_refused(self) -> None:
        for bad in ("src/a\nb.py", "src/a\x01b.py", "src/a\x7f.py"):
            with self.subTest(path=bad), self.assertRaises(ValueError):
                LANES.parse_name_status(f"M\0{bad}\0")

    def test_a_truncated_inventory_is_refused(self) -> None:
        for bad in ("R100\0only-one-path\0", "M\0"):
            with self.subTest(raw=bad), self.assertRaises(ValueError):
                LANES.parse_name_status(bad)

    def test_an_unknown_status_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            LANES.parse_name_status("Z\0src/a.py\0")

    def test_an_empty_path_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            LANES.parse_name_status("M\0\0")

    def test_an_empty_inventory_parses_to_nothing(self) -> None:
        self.assertEqual(LANES.parse_name_status(""), [])
        self.assertEqual(self.paths(""), [])

    def test_name_status_is_the_authority_over_the_diff(self) -> None:
        """Both inputs supplied: paths come from name-status, content from the diff."""
        changes = LANES.parse_name_status(self.REAL)
        diff = ["--- a/src/parser.py", "+++ b/src/parser.py", "+data = json.loads(raw)"]
        selection = LANES.select_lanes("bryan/notes", None, diff, changes)
        reasons = " ".join(selection.reasons["risk"])
        self.assertIn("authentication", reasons, "path authority came from name-status")
        self.assertIn("parsing", reasons, "content signal came from the diff")
        self.assertEqual(selection.notes, [], "a complete pair needs no weakness note")

    def test_a_caller_supplied_path_list_is_marked_weaker(self) -> None:
        selection = LANES.select_lanes("bryan/notes", ["README.md"])
        self.assertTrue(any("not `git diff --name-status`" in n for n in selection.notes))

    def test_header_derived_paths_are_marked_weaker(self) -> None:
        diff = ["--- a/README.md", "+++ b/README.md", "+x"]
        selection = LANES.select_lanes("bryan/notes", None, diff)
        self.assertTrue(any("unified diff headers" in n for n in selection.notes))

    def test_the_cli_accepts_a_name_status_inventory(self) -> None:
        payload = "D\0src/auth/session.py\0"
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            original, sys.stdin = sys.stdin, io.StringIO(payload)
            try:
                code = LANES.main(
                    ["--repo", "bryan/notes", "--name-status-from", "-", "--json"]
                )
            finally:
                sys.stdin = original
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["lanes"], ["standards", "spec", "risk"])

    def test_the_cli_refuses_two_stdin_readers(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            LANES.main(
                ["--repo", "bryan/notes", "--diff-from", "-", "--name-status-from", "-"]
            )

    def test_the_cli_refuses_an_unusable_inventory(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stderr(out), self.assertRaises(SystemExit):
            original, sys.stdin = sys.stdin, io.StringIO("R100\0only-one\0")
            try:
                LANES.main(["--repo", "bryan/notes", "--name-status-from", "-"])
            finally:
                sys.stdin = original
        self.assertIn("unusable name-status inventory", out.getvalue())


class CliTest(unittest.TestCase):
    def run_cli(self, argv: list[str], stdin: str = "") -> str:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            original, sys.stdin = sys.stdin, io.StringIO(stdin)
            try:
                code = LANES.main(argv)
            finally:
                sys.stdin = original
        self.assertEqual(code, 0)
        return out.getvalue()

    def test_reads_changed_files_from_stdin(self) -> None:
        output = self.run_cli(
            ["--repo", "bryan/notes", "--changed-files-from", "-", "--json"],
            stdin="src/auth/session.ts\nREADME.md\n",
        )
        payload = json.loads(output)
        self.assertEqual(payload["lanes"], ["standards", "spec", "risk"])

    def test_accepts_repeated_changed_file_arguments(self) -> None:
        payload = json.loads(
            self.run_cli(
                ["--repo", "bryan/notes", "--changed-file", "README.md", "--json"]
            )
        )
        self.assertEqual(payload["lanes"], ["standards", "spec"])

    def test_text_output_names_the_lanes_and_reasons(self) -> None:
        output = self.run_cli(["--repo", "bryan/cairn-os", "--changed-file", "README.md"])
        self.assertIn("lanes: standards, spec, risk", output)
        self.assertIn("always runs Risk", output)

    def test_reads_a_diff_from_stdin_and_derives_its_paths(self) -> None:
        payload = "--- a/src/parser.py\n+++ b/src/parser.py\n+return json.loads(raw)\n"
        result = json.loads(
            self.run_cli(["--repo", "bryan/notes", "--diff-from", "-", "--json"], stdin=payload)
        )
        self.assertEqual(result["lanes"], ["standards", "spec", "risk"])
        self.assertTrue(any("parsing" in r for r in result["reasons"]["risk"]))

    def test_json_output_carries_the_weaker_selection_note(self) -> None:
        result = json.loads(
            self.run_cli(["--repo", "bryan/notes", "--changed-file", "README.md", "--json"])
        )
        self.assertTrue(result["notes"])

    def test_two_stdin_readers_are_refused(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            LANES.main(
                ["--repo", "bryan/notes", "--changed-files-from", "-", "--diff-from", "-"]
            )

    def test_repo_is_required(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            LANES.main(["--changed-file", "README.md"])


class RealGitInventoryTest(unittest.TestCase):
    """Run the documented authority command against a real Git repository.

    Hand-written fixtures encode what I *believe* Git emits. These run the
    literal command from `NAME_STATUS_COMMAND` in a throwaway repo and classify
    whatever Git actually produces, so a wrong belief fails here rather than in
    a review that quietly skipped its Risk lane.
    """

    def git(self, *args: str) -> str:
        result = subprocess.run(
            ("git", "-C", self.repo, *args),
            capture_output=True,
            check=True,
        )
        return result.stdout.decode("utf-8", "surrogateescape")

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = self._tmp.name
        env = {
            "GIT_CONFIG_GLOBAL": str(Path(self.repo) / "no-global-config"),
            "GIT_CONFIG_SYSTEM": str(Path(self.repo) / "no-system-config"),
        }
        for key, value in env.items():
            os.environ[key] = value
        self._env_keys = tuple(env)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")
        self.git("config", "commit.gpgsign", "false")

    def tearDown(self) -> None:
        for key in self._env_keys:
            os.environ.pop(key, None)
        self._tmp.cleanup()

    def write(self, path: str, content: bytes | str) -> None:
        target = Path(self.repo) / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, str):
            target.write_text(content, encoding="utf-8")
        else:
            target.write_bytes(content)

    def commit(self, message: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def inventory(self) -> list:
        """Exactly the documented authority command, run for real."""
        base = self.git("rev-parse", "main").strip()
        command = LANES.NAME_STATUS_COMMAND.format(base=base)
        self.assertEqual(
            command.split()[:7],
            ["git", "diff", "--name-status", "-z", "-M", "-C", "--find-copies-harder"],
            "the documented authority command changed shape",
        )
        raw = self.git(*command.split()[1:])
        return LANES.parse_name_status(raw)

    def branch(self) -> None:
        self.git("checkout", "-q", "-b", "work")

    # -- the four required shapes ---------------------------------------

    def test_a_content_identical_rename_reports_both_paths(self) -> None:
        """Risky → neutral, byte-identical. The reason name-status exists."""
        self.write("src/auth/session.py", "def login():\n    return True\n")
        self.write("README.md", "docs\n")
        self.commit("seed")
        self.branch()
        (Path(self.repo) / "src" / "util").mkdir(parents=True, exist_ok=True)
        self.git("mv", "src/auth/session.py", "src/util/helper.py")
        self.commit("move it somewhere harmless")

        changes = self.inventory()
        statuses = {c.kind for c in changes}
        self.assertEqual(statuses, {"R"}, f"expected one rename, got {changes}")
        paths = LANES.changed_files_from_name_status(changes)
        self.assertIn("src/auth/session.py", paths, "the risky source vanished")
        self.assertIn("src/util/helper.py", paths)

        selection = LANES.select_lanes("bryan/thing", name_status=changes)
        self.assertIn(LANES.RISK, selection.lanes)
        self.assertTrue(
            any("auth" in reason for reason in selection.reasons[LANES.RISK])
        )

    def test_a_binary_deletion_reports_its_path(self) -> None:
        """A binary delete emits no unified `---`/`+++` headers at all."""
        self.write("src/auth/keystore.p12", bytes(range(256)) * 8)
        self.write("README.md", "docs\n")
        self.commit("seed")
        self.branch()
        (Path(self.repo) / "src/auth/keystore.p12").unlink()
        self.commit("drop the keystore")

        base = self.git("rev-parse", "main").strip()
        unified = self.git(*LANES.UNIFIED_DIFF_COMMAND.format(base=base).split()[1:])
        self.assertNotIn(
            "--- ", unified, "premise broken: this binary delete has path headers"
        )
        self.assertEqual(
            LANES.changed_files_from_diff(unified),
            [],
            "premise broken: the unified diff exposed the deleted path",
        )

        changes = self.inventory()
        self.assertEqual([c.kind for c in changes], ["D"])
        self.assertEqual(
            LANES.changed_files_from_name_status(changes), ["src/auth/keystore.p12"]
        )
        selection = LANES.select_lanes("bryan/thing", name_status=changes)
        self.assertIn(LANES.RISK, selection.lanes)

    def test_a_copy_from_an_untouched_risky_source_emits_C(self) -> None:
        """This is what `--find-copies-harder` buys.

        Plain `-C` only considers files the commit already modified, so copying
        an untouched source reports a bare `A` and the risky source is never
        classified.
        """
        body = "".join(f"def credential_{i}():\n    return {i}\n" for i in range(40))
        self.write("src/auth/credentials.py", body)
        self.commit("seed")
        self.branch()
        self.write("src/util/copy_of_credentials.py", body)
        self.commit("copy it")

        changes = self.inventory()
        kinds = {c.kind for c in changes}
        self.assertEqual(
            kinds, {"C"}, f"--find-copies-harder did not report a copy: {changes}"
        )
        paths = LANES.changed_files_from_name_status(changes)
        self.assertIn("src/auth/credentials.py", paths, "the untouched source vanished")
        self.assertIn("src/util/copy_of_credentials.py", paths)
        self.assertIn(
            LANES.RISK, LANES.select_lanes("bryan/thing", name_status=changes).lanes
        )

    def test_a_plain_copy_flag_would_have_missed_that_source(self) -> None:
        """The negative control for the flag choice, run for real."""
        body = "".join(f"def credential_{i}():\n    return {i}\n" for i in range(40))
        self.write("src/auth/credentials.py", body)
        self.commit("seed")
        self.branch()
        self.write("src/util/copy_of_credentials.py", body)
        self.commit("copy it")

        base = self.git("rev-parse", "main").strip()
        weaker = LANES.parse_name_status(
            self.git("diff", "--name-status", "-z", "-M", "-C", f"{base}...HEAD", "--")
        )
        self.assertEqual(
            [c.kind for c in weaker],
            ["A"],
            "premise broken: plain -C already found this copy",
        )
        self.assertNotIn(
            "src/auth/credentials.py",
            LANES.changed_files_from_name_status(weaker),
            "premise broken: plain -C exposed the source anyway",
        )

    def test_ordinary_add_modify_delete_classify(self) -> None:
        self.write("src/auth/session.py", "x = 1\n")
        self.write("docs/old.md", "gone soon\n")
        self.commit("seed")
        self.branch()
        self.write("src/auth/session.py", "x = 2\n")
        self.write("docs/new.md", "new\n")
        (Path(self.repo) / "docs/old.md").unlink()
        self.commit("add, modify, delete")

        changes = self.inventory()
        by_path = {c.paths[0]: c.kind for c in changes}
        self.assertEqual(by_path["src/auth/session.py"], "M")
        self.assertEqual(by_path["docs/new.md"], "A")
        self.assertEqual(by_path["docs/old.md"], "D")
        paths = LANES.changed_files_from_name_status(changes)
        self.assertEqual(len(paths), len(set(paths)), "a path was double-counted")

    def test_an_unusual_filename_survives_the_nul_stream(self) -> None:
        """`-z` exists so this arrives verbatim instead of quoted."""
        odd = 'src/auth/we"ird na;me file.py'
        self.write("README.md", "docs\n")
        self.commit("seed")
        self.branch()
        self.write(odd, "x = 1\n")
        self.commit("add an awkward name")

        changes = self.inventory()
        self.assertEqual(
            LANES.changed_files_from_name_status(changes),
            [odd],
            "the path was quoted or mangled rather than passed through",
        )


class StrictStatusParsingTest(unittest.TestCase):
    """Every malformation refuses, because the alternative is a guess."""

    def z(self, *fields: str) -> str:
        return "\0".join(fields) + "\0"

    def test_one_path_statuses_are_exactly_one_letter(self) -> None:
        for status in ("A", "D", "M", "T", "U", "X", "B"):
            with self.subTest(status=status):
                changes = LANES.parse_name_status(self.z(status, "a.py"))
                self.assertEqual(changes[0].kind, status)

    def test_a_suffixed_one_path_status_is_refused(self) -> None:
        """`MM` is porcelain-status syntax, not name-status syntax."""
        for bad in ("MM", "AM", "M1", "A100", "DD", "M "):
            with self.subTest(status=bad):
                with self.assertRaises(ValueError):
                    LANES.parse_name_status(self.z(bad, "a.py", "b.py"))

    def test_rename_and_copy_require_a_three_digit_score(self) -> None:
        for good in ("R000", "R100", "R087", "C000", "C100", "C050"):
            with self.subTest(status=good):
                changes = LANES.parse_name_status(self.z(good, "a.py", "b.py"))
                self.assertEqual(changes[0].paths, ("a.py", "b.py"))
        for bad in ("R", "R1", "R12", "R1000", "R101", "R999", "Rxyz", "C", "C1001"):
            with self.subTest(status=bad):
                with self.assertRaises(ValueError):
                    LANES.parse_name_status(self.z(bad, "a.py", "b.py"))

    def test_a_leading_empty_field_is_refused_not_skipped(self) -> None:
        """An empty status field means the stream is misaligned."""
        with self.assertRaises(ValueError) as caught:
            LANES.parse_name_status(self.z("", "M", "a.py"))
        self.assertIn("misaligned", str(caught.exception))

    def test_truncation_is_refused(self) -> None:
        for data in (self.z("M"), self.z("R100", "only-one.py"), self.z("C050")):
            with self.subTest(data=data):
                with self.assertRaises(ValueError) as caught:
                    LANES.parse_name_status(data)
                self.assertIn("truncated", str(caught.exception))

    def test_an_empty_path_is_refused(self) -> None:
        with self.assertRaises(ValueError) as caught:
            LANES.parse_name_status(self.z("M", ""))
        self.assertIn("empty path", str(caught.exception))
        with self.assertRaises(ValueError):
            LANES.parse_name_status(self.z("R100", "a.py", ""))

    def test_a_control_character_in_a_path_is_refused(self) -> None:
        for bad in ("a\npy", "a\rpy", "a\x01py", "a\x7fpy", "a\tpy".replace("\t", "\x0b")):
            with self.subTest(path=bad):
                with self.assertRaises(ValueError) as caught:
                    LANES.parse_name_status(self.z("M", bad))
                self.assertIn("control character", str(caught.exception))

    def test_a_tab_in_a_path_is_refused(self) -> None:
        """Tab is technically a legal filename byte, but a path this classifier
        cannot render unambiguously is a path it must not classify — and a tab
        in a real repository path is overwhelmingly a mangled or adversarial
        stream, not a file."""
        with self.assertRaises(ValueError) as caught:
            LANES.parse_name_status(self.z("M", "src/a\tb.py"))
        self.assertIn("control character", str(caught.exception))

    def test_a_whitespace_mutated_status_is_refused(self) -> None:
        """Exact status bytes, validated before any normalization.

        Stripping first would launder ` M`, `M\n`, or `\tM ` into a valid
        status — a mutated stream classified as if it were the real protocol.
        """
        for bad in (" M", "M ", "M\n", "\tM", "\tM ", " R100", "R100\n"):
            with self.subTest(status=bad):
                with self.assertRaises(ValueError):
                    LANES.parse_name_status(self.z(bad, "a.py", "b.py"))

    def test_undecodable_bytes_are_refused_rather_than_substituted(self) -> None:
        """A path decoded with U+FFFD names a different file than Git meant."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "inventory.z"
            path.write_bytes(b"M\x00src/auth/\xff\xfe.py\x00")
            with self.assertRaises(ValueError) as caught:
                LANES.read_raw(str(path))
            self.assertIn("not valid UTF-8", str(caught.exception))

    def test_the_cli_reports_undecodable_input_as_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "inventory.z"
            path.write_bytes(b"M\x00\xff\xfe\x00")
            with contextlib.redirect_stderr(io.StringIO()) as err, self.assertRaises(
                SystemExit
            ):
                LANES.main(["--repo", "bryan/x", "--name-status-from", str(path)])
        self.assertIn("unusable name-status inventory", err.getvalue())

    def test_documented_commands_preserve_the_load_bearing_flags(self) -> None:
        """Orchestrators pin SHAs, but none may weaken the Git inventory flags."""
        command = LANES.NAME_STATUS_COMMAND
        self.assertEqual(
            command,
            "git diff --name-status -z -M -C --find-copies-harder {base}...HEAD --",
        )
        root = Path(__file__).resolve().parents[3]
        literal = command.replace("{base}", "")
        for skill in (
            root / "skills" / "pr-self-review" / "SKILL.md",
            root / "skills" / "code-review" / "SKILL.md",
        ):
            with self.subTest(skill=skill.name):
                text = skill.read_text(encoding="utf-8")
                self.assertIn(
                    "--name-status -z -M -C --find-copies-harder",
                    text,
                    "the skill's invocation contract does not use the authority command",
                )
                self.assertIn("--find-copies-harder", text)
        help_text = LANES.main.__doc__ or ""
        del help_text, literal  # help is asserted through the parser below
        parser_help = io.StringIO()
        with contextlib.redirect_stdout(parser_help), self.assertRaises(SystemExit):
            LANES.main(["--help"])
        self.assertIn("--find-copies-harder", parser_help.getvalue())


if __name__ == "__main__":
    unittest.main()
