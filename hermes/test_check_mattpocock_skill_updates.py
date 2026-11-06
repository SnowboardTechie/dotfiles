#!/usr/bin/env python3
"""Offline tests for the upstream skill-update monitor.

The scheduler hashes this script's exact stdout bytes and suppresses the whole
agent run when they are unchanged. These properties follow, and all of them are
tested rather than trusted:

* **Identical upstream content produces identical bytes.** Any instability — a
  timestamp, dict ordering, a local path — would make every weekly tick look
  like a change and turn the watcher into noise.
* **An unrelated upstream commit produces identical bytes.** Identity is the
  per-file Git blob sha, so a push touching nothing we watch stays silent.
  Keying on the repository tip was the bug this replaces.
* **A real change moves the output.** A watcher that cannot notice is worse than
  none, because it reports quiet.
* **Local adaptation context alone does not.** The hashed output carries
  upstream identity only; the agent reads the ledger itself for changed paths.
* **The output and its diff fit the scheduler's prompt caps**, and every changed
  diff line names its own path (the 2026-10-12 `tdd/mocking.md` misattribution).

Everything runs against a fixture directory or an injected HTTP stub. No test
reaches the network.

Run: python3 -m unittest hermes/test_check_mattpocock_skill_updates.py
"""

from __future__ import annotations

import difflib
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("scripts") / "check-mattpocock-skill-updates.py"
SPEC = importlib.util.spec_from_file_location("check_mattpocock_skill_updates", SCRIPT)
assert SPEC and SPEC.loader
MON = importlib.util.module_from_spec(SPEC)
sys.modules["check_mattpocock_skill_updates"] = MON
SPEC.loader.exec_module(MON)

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_LEDGER = REPO_ROOT / "dot-agents" / "upstreams" / "mattpocock-skills.json"

# Mirrors of `cron/monitor.py` in the installed Hermes agent. The monitor block
# shows the agent a unified diff capped at MAX_DIFF_CHARS and the current output
# capped at MAX_OUTPUT_CHARS; anything longer is truncated mid-snapshot.
# `HermesLimitsTest` asserts these still equal the installed values.
HERMES_MONITOR = Path.home() / ".hermes" / "hermes-agent" / "cron" / "monitor.py"
HERMES_PYTHON = Path.home() / ".hermes" / "hermes-agent" / "venv" / "bin" / "python"
MAX_DIFF_CHARS = 4000
MAX_OUTPUT_CHARS = 8000
# The prompt builds each fetch URL as this prefix plus the validated sha.
BLOB_URL_PREFIX = "https://api.github.com/repos/mattpocock/skills/git/blobs/"


def monitor_diff(old: str, new: str) -> str:
    """The scheduler's own diff construction (`build_monitor_diff`), uncapped."""
    return "\n".join(
        difflib.unified_diff(
            old.splitlines(), new.splitlines(), fromfile="previous", tofile="current", lineterm=""
        )
    )


def changed_lines(diff: str) -> list[str]:
    return [
        line
        for line in diff.splitlines()
        if line[:1] in "+-" and not line.startswith(("+++", "---"))
    ]

LEDGER = {
    "upstream": "https://github.com/mattpocock/skills",
    "version": "1.2.3",
    "commit": "885e2ca4d842d139e9aef4e48d366c63cb1b8013",
    "adaptations": [
        {
            "skill": "tdd",
            "upstreamPaths": [
                "skills/engineering/tdd/SKILL.md",
                "skills/engineering/tdd/tests.md",
            ],
            "watchedFiles": [
                "skills/engineering/tdd/SKILL.md",
                "skills/engineering/tdd/tests.md",
            ],
            "localPaths": ["dot-agents/skills/tdd/SKILL.md"],
            "localChanges": ["Adds the pre-agreed-seam path."],
            "rejectedUpstreamRules": ["Reading a CONTEXT.md glossary as a required step."],
        },
        {
            "skill": "codebase-architecture",
            "upstreamPaths": ["skills/engineering/codebase-design/SKILL.md"],
            "watchedFiles": ["skills/engineering/codebase-design/SKILL.md"],
            "localPaths": ["dot-agents/skills/codebase-architecture/SKILL.md"],
            "localChanges": ["Merges two upstream skills into one owner."],
            "rejectedUpstreamRules": ["The generated HTML report."],
        },
        {
            # Shares a watched file with codebase-architecture, so an alert can
            # name every adaptation one upstream change would touch.
            "skill": "tdd-vocabulary-consumer",
            "upstreamPaths": ["skills/engineering/codebase-design/SKILL.md"],
            "watchedFiles": ["skills/engineering/codebase-design/SKILL.md"],
            "localPaths": ["dot-agents/skills/tdd/references/mocking.md"],
            "localChanges": ["Prefers a local substitute over a mock."],
            "rejectedUpstreamRules": [],
        },
    ],
}

DEFAULT_FIXTURE = {
    "skills/engineering/tdd/SKILL.md": "# TDD\n\nRed, green, refactor.\n",
    "skills/engineering/tdd/tests.md": "# Tests\n\nGood and bad.\n",
    "skills/engineering/codebase-design/SKILL.md": "# Codebase Design\n\nDeep modules.\n",
}


def write_fixture(root: Path, *, overrides: dict | None = None) -> Path:
    contents = dict(DEFAULT_FIXTURE)
    contents.update(overrides or {})
    root.mkdir(parents=True, exist_ok=True)
    for relative, body in contents.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return root


def snapshot(root: Path) -> str:
    return MON.render(MON.build_snapshot(LEDGER, fetcher=MON.FixtureFetcher(root)))


def tree_response(paths: dict[str, bytes], *, truncated: bool = False) -> bytes:
    """A recursive Git Trees payload for these path -> content pairs."""
    return json.dumps(
        {
            "sha": "0" * 40,
            "truncated": truncated,
            "tree": [
                {"path": path, "type": "blob", "mode": "100644", "sha": MON.git_blob_sha(body)}
                for path, body in sorted(paths.items())
            ]
            + [{"path": "skills", "type": "tree", "mode": "040000", "sha": "1" * 40}],
        }
    ).encode("utf-8")


class BlobIdentityTest(unittest.TestCase):
    def test_blob_sha_matches_gits_own_algorithm(self) -> None:
        data = b"# TDD\n\nRed, green, refactor.\n"
        expected = hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()  # noqa: S324
        self.assertEqual(MON.git_blob_sha(data), expected)

    def test_blob_sha_is_content_addressed(self) -> None:
        self.assertEqual(MON.git_blob_sha(b"same"), MON.git_blob_sha(b"same"))
        self.assertNotEqual(MON.git_blob_sha(b"a"), MON.git_blob_sha(b"b"))

    def test_the_prompt_builds_the_blob_url_the_trees_api_points_at(self) -> None:
        """The snapshot carries no URL; the prompt's prefix must be this repo's."""
        prompt = (REPO_ROOT / "hermes" / "automations" / "mattpocock-skill-update-watch"
                  / "prompt.md").read_text(encoding="utf-8")
        self.assertIn(BLOB_URL_PREFIX + "<blobSha>", prompt)
        self.assertEqual(BLOB_URL_PREFIX, f"{MON.API_BASE}/git/blobs/")


class WatchListTest(unittest.TestCase):
    def test_paths_are_sorted_and_deduplicated(self) -> None:
        """A path two adaptations share appears once."""
        self.assertEqual(
            MON.watched_paths(LEDGER),
            [
                "skills/engineering/codebase-design/SKILL.md",
                "skills/engineering/tdd/SKILL.md",
                "skills/engineering/tdd/tests.md",
            ],
        )

    def test_a_watched_file_with_no_declared_source_is_refused(self) -> None:
        broken = {
            "adaptations": [{"skill": "x", "upstreamPaths": ["a.md"], "watchedFiles": ["b.md"]}]
        }
        with self.assertRaises(MON.MonitorError):
            MON.watched_paths(broken)

    def test_an_empty_watch_list_is_refused(self) -> None:
        with self.assertRaises(MON.MonitorError):
            MON.watched_paths({"adaptations": []})

    def test_the_real_ledger_produces_a_watch_list(self) -> None:
        paths = MON.watched_paths(json.loads(REAL_LEDGER.read_text(encoding="utf-8")))
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue(path.startswith("skills/"))


class StabilityTest(unittest.TestCase):
    def test_identical_content_produces_identical_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_fixture(Path(tmp))
            self.assertEqual(snapshot(root), snapshot(root))

    def test_no_repository_tip_appears_in_the_output(self) -> None:
        """Identity is per file, not per commit — the whole point of the rewrite."""
        with tempfile.TemporaryDirectory() as tmp:
            payload = json.loads(snapshot(write_fixture(Path(tmp))))
        self.assertNotIn("currentCommit", payload)
        self.assertEqual(
            set(payload), {"upstream", "pinnedCommit", "pinnedVersion", "watched"}
        )

    def test_output_carries_no_timestamp_and_no_local_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_fixture(Path(tmp))
            output = snapshot(root)
            payload = json.loads(output)
        self.assertNotIn(tmp, output)
        self.assertNotIn("/Users/", output)
        # Assert on key names, not substrings: ledger prose legitimately
        # contains words like "generated" ("the generated HTML report").
        forbidden = {"checked_at", "checkedAt", "generated", "generatedAt", "timestamp", "at"}

        def walk(node) -> None:
            if isinstance(node, dict):
                overlap = forbidden & set(node)
                self.assertEqual(overlap, set(), f"time-shaped key(s) in output: {overlap}")
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(payload)
        # And no ISO date anywhere in the rendered bytes.
        self.assertNotRegex(output, r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")

    def test_output_keys_are_sorted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = json.loads(snapshot(write_fixture(Path(tmp))))
        self.assertEqual(list(payload), sorted(payload))
        self.assertEqual(list(payload["watched"]), sorted(payload["watched"]))

    def test_the_snapshot_names_the_pin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = json.loads(snapshot(write_fixture(Path(tmp))))
        self.assertEqual(payload["pinnedCommit"], LEDGER["commit"])
        self.assertEqual(payload["pinnedVersion"], "1.2.3")

    def test_every_watched_entry_carries_a_40_hex_blob_sha(self) -> None:
        """The agent validates exactly this shape before building the URL."""
        with tempfile.TemporaryDirectory() as tmp:
            payload = json.loads(snapshot(write_fixture(Path(tmp))))
        for path, entry in payload["watched"].items():
            with self.subTest(path=path):
                self.assertRegex(entry["blobSha"], r"\A[0-9a-f]{40}\Z")

    def test_watched_entries_carry_upstream_identity_only(self) -> None:
        """No local skill paths, divergence, or rejected rules in the hashed bytes."""
        with tempfile.TemporaryDirectory() as tmp:
            output = snapshot(write_fixture(Path(tmp)))
        payload = json.loads(output)
        for path, entry in payload["watched"].items():
            with self.subTest(path=path):
                self.assertEqual(set(entry), {"blobSha"})
        self.assertNotIn("blobUrl", output)
        self.assertNotIn("/git/blobs/", output)
        for local in ("adaptations", "localPaths", "localChanges", "rejectedUpstreamRules"):
            self.assertNotIn(local, output)

    def test_each_watched_path_is_one_line_carrying_its_own_sha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = snapshot(write_fixture(Path(tmp)))
        payload = json.loads(output)
        for path, entry in payload["watched"].items():
            with self.subTest(path=path):
                lines = [line for line in output.splitlines() if json.dumps(path) in line]
                self.assertEqual(len(lines), 1)
                self.assertIn(entry["blobSha"], lines[0])


class ChangeDetectionTest(unittest.TestCase):
    def test_a_changed_watched_file_moves_the_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = snapshot(write_fixture(root))
            write_fixture(
                root,
                overrides={"skills/engineering/tdd/SKILL.md": "# TDD\n\nA new rule.\n"},
            )
            self.assertNotEqual(before, snapshot(root))

    def test_an_unwatched_upstream_file_does_not_move_the_output(self) -> None:
        """This is what an unrelated commit looks like: other files change."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = snapshot(write_fixture(root))
            for name, body in {
                "skills/engineering/wizard/SKILL.md": "# Wizard\n\nNot adapted.\n",
                "README.md": "# Upstream README\n\nRewritten.\n",
                "skills/productivity/handoff/SKILL.md": "# Handoff\n",
            }.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(body, encoding="utf-8")
            self.assertEqual(before, snapshot(root), "an unrelated commit must stay silent")

    def test_rewriting_a_watched_file_to_the_same_bytes_stays_silent(self) -> None:
        """A revert, or a commit that touches and restores a file."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = snapshot(write_fixture(root))
            target = root / "skills/engineering/tdd/SKILL.md"
            target.write_text("# TDD\n\nTemporarily different.\n", encoding="utf-8")
            self.assertNotEqual(before, snapshot(root))
            target.write_text(
                DEFAULT_FIXTURE["skills/engineering/tdd/SKILL.md"], encoding="utf-8"
            )
            self.assertEqual(before, snapshot(root))

    def test_local_adaptation_context_alone_does_not_move_the_output(self) -> None:
        """A local-only ledger edit must not wake the agent (the 2026-10-19 noise)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = write_fixture(Path(tmp))
            before = snapshot(root)
            edited = json.loads(json.dumps(LEDGER))
            for adaptation in edited["adaptations"]:
                adaptation["localChanges"].append("A brand-new local divergence.")
                adaptation["rejectedUpstreamRules"].append("Something newly rejected.")
                adaptation["localPaths"].append("dot-agents/skills/new/SKILL.md")
                adaptation["skill"] += "-renamed"
            edited["adaptations"].append(
                {
                    "skill": "another-consumer",
                    "upstreamPaths": ["skills/engineering/tdd/SKILL.md"],
                    "watchedFiles": ["skills/engineering/tdd/SKILL.md"],
                    "localPaths": ["dot-agents/skills/other/SKILL.md"],
                    "localChanges": ["Other."],
                    "rejectedUpstreamRules": [],
                }
            )
            after = MON.render(MON.build_snapshot(edited, fetcher=MON.FixtureFetcher(root)))
        self.assertEqual(before, after)

    def test_local_context_in_the_real_ledger_does_not_move_the_output(self) -> None:
        real = json.loads(REAL_LEDGER.read_text(encoding="utf-8"))
        fetcher = StubFetcher()
        before = MON.render(MON.build_snapshot(real, fetcher=fetcher))
        for adaptation in real["adaptations"]:
            adaptation["localChanges"] = adaptation.get("localChanges", []) + ["Edited."]
            adaptation["rejectedUpstreamRules"] = []
        self.assertEqual(before, MON.render(MON.build_snapshot(real, fetcher=fetcher)))


class StubFetcher:
    """Deterministic, distinct 40-hex shas per path — the real output width."""

    def __init__(self, overrides: dict[str, str] | None = None) -> None:
        self.overrides = overrides or {}

    def blob_sha(self, path: str) -> str:
        if path in self.overrides:
            return self.overrides[path]
        return hashlib.sha1(path.encode("utf-8")).hexdigest()  # noqa: S324


# Upstream's real opening bytes for the two sibling files the 2026-10-12 run
# confused (verified 2026-11-06 against the pinned blobs 01eadaa… and 71cbfee…).
TDD_SKILL_BYTES = (
    b"---\nname: tdd\ndescription: Test-driven development. Use when the user wants "
    b"to build features or fix bugs test-first.\n---\n\n# Test-Driven Development\n"
)
TDD_MOCKING_BYTES = b"# When to Mock\n\nMock at **system boundaries** only:\n"
TDD_SKILL = "skills/engineering/tdd/SKILL.md"
TDD_MOCKING = "skills/engineering/tdd/mocking.md"
TDD_LEDGER = {
    "commit": "885e2ca4d842d139e9aef4e48d366c63cb1b8013",
    "version": "1.2.3",
    "adaptations": [
        {
            "skill": "tdd",
            "upstreamPaths": [TDD_SKILL, TDD_MOCKING, "skills/engineering/tdd/tests.md"],
            "watchedFiles": [TDD_SKILL, TDD_MOCKING, "skills/engineering/tdd/tests.md"],
            "localPaths": ["dot-agents/skills/tdd/SKILL.md"],
        }
    ],
}


class BlobAttributionTest(unittest.TestCase):
    """Regression for 2026-10-12: `tdd/mocking.md` 'returned the tdd SKILL'.

    The collector had paired each path with its own sha. The scheduler's diff
    showed the changed `tdd/SKILL.md` sha with `"…/tdd/mocking.md": {` as the
    nearest visible key, because each sha sat below its own key at the end of a
    multi-line object. The agent attributed the sha to `mocking.md`, fetched the
    (correct) `SKILL.md` bytes, and called them the wrong blob.
    """

    def tree_fetcher(self, skill: bytes = TDD_SKILL_BYTES) -> object:
        payload = tree_response(
            {
                TDD_SKILL: skill,
                TDD_MOCKING: TDD_MOCKING_BYTES,
                "skills/engineering/tdd/tests.md": b"# Tests\n",
            }
        )
        return MON.TreeFetcher(http=lambda url, timeout=None: payload)

    def test_each_watched_path_carries_its_own_bytes_sha(self) -> None:
        payload = json.loads(
            MON.render(MON.build_snapshot(TDD_LEDGER, fetcher=self.tree_fetcher()))
        )
        mocking = payload["watched"][TDD_MOCKING]
        skill = payload["watched"][TDD_SKILL]
        self.assertEqual(mocking["blobSha"], MON.git_blob_sha(TDD_MOCKING_BYTES))
        self.assertEqual(skill["blobSha"], MON.git_blob_sha(TDD_SKILL_BYTES))
        self.assertNotEqual(mocking["blobSha"], skill["blobSha"])

    def test_a_changed_sha_is_named_by_its_own_diff_line(self) -> None:
        before = MON.render(MON.build_snapshot(TDD_LEDGER, fetcher=self.tree_fetcher()))
        after = MON.render(
            MON.build_snapshot(
                TDD_LEDGER, fetcher=self.tree_fetcher(TDD_SKILL_BYTES + b"\nA new rule.\n")
            )
        )
        lines = changed_lines(monitor_diff(before, after))
        self.assertEqual(len(lines), 2, lines)
        for line in lines:
            with self.subTest(line=line):
                self.assertIn(json.dumps(TDD_SKILL), line)
                self.assertNotIn("mocking.md", line)
        self.assertIn(MON.git_blob_sha(TDD_SKILL_BYTES), lines[0])

    def test_every_changed_line_names_its_path_with_the_real_ledger(self) -> None:
        real = json.loads(REAL_LEDGER.read_text(encoding="utf-8"))
        paths = MON.watched_paths(real)
        before = MON.render(MON.build_snapshot(real, fetcher=StubFetcher()))
        for path in paths:
            with self.subTest(path=path):
                after = MON.render(
                    MON.build_snapshot(real, fetcher=StubFetcher({path: "f" * 40}))
                )
                lines = changed_lines(monitor_diff(before, after))
                self.assertEqual(len(lines), 2)
                for line in lines:
                    self.assertTrue(line[1:].lstrip().startswith(json.dumps(path) + ":"), line)


class HermesLimitsTest(unittest.TestCase):
    """The real 17-path ledger must fit the scheduler's caps without truncation."""

    def test_mirrored_limits_match_the_installed_hermes(self) -> None:
        if not HERMES_MONITOR.is_file():
            self.skipTest(f"{HERMES_MONITOR} not readable on this host")
        body = HERMES_MONITOR.read_text(encoding="utf-8")
        for name, mirrored in (
            ("MAX_DIFF_CHARS", MAX_DIFF_CHARS),
            ("MAX_OUTPUT_CHARS", MAX_OUTPUT_CHARS),
        ):
            with self.subTest(constant=name):
                found = re.search(rf"^{name}\s*=\s*([0-9_]+)", body, re.MULTILINE)
                self.assertIsNotNone(found, f"{name} not found in {HERMES_MONITOR}")
                self.assertEqual(int(found.group(1).replace("_", "")), mirrored)

    def real_output(self, overrides: dict[str, str] | None = None) -> str:
        real = json.loads(REAL_LEDGER.read_text(encoding="utf-8"))
        return MON.render(MON.build_snapshot(real, fetcher=StubFetcher(overrides)))

    def test_the_real_ledger_snapshot_fits_with_room_to_grow(self) -> None:
        output = self.real_output()
        self.assertGreaterEqual(len(json.loads(output)["watched"]), 17)
        # Half the cap: room to roughly double the watch list before truncation.
        self.assertLess(len(output), MAX_OUTPUT_CHARS // 2, len(output))

    def test_a_single_changed_path_diff_is_well_under_the_cap(self) -> None:
        before = self.real_output()
        for path in MON.watched_paths(json.loads(REAL_LEDGER.read_text(encoding="utf-8"))):
            with self.subTest(path=path):
                diff = monitor_diff(before, self.real_output({path: "f" * 40}))
                self.assertLess(len(diff), MAX_DIFF_CHARS // 2, len(diff))

    def test_every_watched_path_changing_at_once_fits_the_diff_cap(self) -> None:
        """The worst case: an upstream release that touches every watched file."""
        paths = MON.watched_paths(json.loads(REAL_LEDGER.read_text(encoding="utf-8")))
        changed = {path: "e" * 40 for path in paths}
        diff = monitor_diff(self.real_output(), self.real_output(changed))
        self.assertEqual(len(changed_lines(diff)), 2 * len(paths))
        self.assertLess(len(diff), MAX_DIFF_CHARS, len(diff))

    def test_several_changed_paths_still_fit_the_diff_cap(self) -> None:
        """A typical upstream release touches a few watched files at once."""
        paths = MON.watched_paths(json.loads(REAL_LEDGER.read_text(encoding="utf-8")))
        changed = {path: "e" * 40 for path in paths[::2][:5]}
        diff = monitor_diff(self.real_output(), self.real_output(changed))
        self.assertLessEqual(len(diff), MAX_DIFF_CHARS, len(diff))


class TreeFetcherTest(unittest.TestCase):
    """One recursive tree request, not one Contents request per watched file.

    GitHub's unauthenticated limit is 60 requests an hour per IP, shared with
    everything else on the host — a live run with 17 watched files exhausted it
    on the second invocation. That is what these tests hold in place.
    """

    def fetcher(self, paths: dict[str, bytes], *, truncated: bool = False, seen=None):
        payload = tree_response(paths, truncated=truncated)

        def http(url, timeout=None):
            if seen is not None:
                seen.append(url)
            return payload

        return MON.TreeFetcher(http=http)

    def test_a_blob_sha_comes_from_the_tree(self) -> None:
        body = b"# TDD\n"
        fetcher = self.fetcher({"skills/engineering/tdd/SKILL.md": body})
        self.assertEqual(
            fetcher.blob_sha("skills/engineering/tdd/SKILL.md"), MON.git_blob_sha(body)
        )

    def test_the_whole_watch_list_costs_one_request(self) -> None:
        seen: list[str] = []
        paths = {name: name.encode() for name in DEFAULT_FIXTURE}
        fetcher = self.fetcher(paths, seen=seen)
        for path in paths:
            fetcher.blob_sha(path)
        self.assertEqual(len(seen), 1, f"expected one tree request, made {len(seen)}")

    def test_the_request_is_pinned_to_the_requested_ref(self) -> None:
        seen: list[str] = []
        self.fetcher({"a.md": b"x"}, seen=seen).blob_sha("a.md")
        self.assertIn("/git/trees/main", seen[0])
        self.assertIn("recursive=1", seen[0])

    def test_a_truncated_tree_is_refused(self) -> None:
        """A missing watched path would otherwise read as unchanged."""
        fetcher = self.fetcher({"a.md": b"x"}, truncated=True)
        with self.assertRaises(MON.MonitorError) as caught:
            fetcher.blob_sha("a.md")
        self.assertIn("truncated", str(caught.exception))

    def test_a_watched_path_missing_from_the_tree_is_refused(self) -> None:
        """A rename upstream means the ledger is stale, not that nothing changed."""
        fetcher = self.fetcher({"other.md": b"x"})
        with self.assertRaises(MON.MonitorError) as caught:
            fetcher.blob_sha("skills/engineering/tdd/SKILL.md")
        self.assertIn("stale", str(caught.exception))

    def test_tree_entries_are_filtered_to_blobs(self) -> None:
        fetcher = self.fetcher({"a.md": b"x"})
        with self.assertRaises(MON.MonitorError):
            fetcher.blob_sha("skills")  # a tree entry, not a blob

    def test_an_empty_tree_is_refused(self) -> None:
        payload = json.dumps({"truncated": False, "tree": []}).encode()
        fetcher = MON.TreeFetcher(http=lambda url, timeout=None: payload)
        with self.assertRaises(MON.MonitorError):
            fetcher.blob_sha("a.md")

    def test_non_json_is_refused(self) -> None:
        fetcher = MON.TreeFetcher(http=lambda url, timeout=None: b"<html>nope</html>")
        with self.assertRaises(MON.MonitorError):
            fetcher.blob_sha("a.md")

    def test_a_rate_limit_response_is_an_error_not_a_quiet_success(self) -> None:
        """GitHub answers 403 when the shared per-IP limit is exhausted."""

        def http(url, timeout=None):
            raise MON.MonitorError(f"GET {url} failed: HTTP 403")

        with self.assertRaises(MON.MonitorError) as caught:
            MON.TreeFetcher(http=http).blob_sha("a.md")
        self.assertIn("403", str(caught.exception))


class LedgerDiscoveryTest(unittest.TestCase):
    """The installed script is a copy, so `__file__` cannot find the ledger."""

    def test_an_explicit_env_override_wins(self) -> None:
        self.assertEqual(
            MON.default_ledger_path({MON.LEDGER_ENV: "/somewhere/ledger.json"}),
            Path("/somewhere/ledger.json"),
        )

    def test_it_otherwise_resolves_from_the_cron_workdir(self) -> None:
        found = MON.default_ledger_path({}, cwd=Path("/Users/bryan/code/dotfiles"))
        self.assertEqual(
            found,
            Path("/Users/bryan/code/dotfiles/dot-agents/upstreams/mattpocock-skills.json"),
        )

    def test_it_never_looks_beside_the_installed_copy(self) -> None:
        found = MON.default_ledger_path({}, cwd=Path("/Users/bryan/code/dotfiles"))
        self.assertNotIn(".hermes", str(found))

    def test_a_missing_ledger_names_both_discovery_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(MON.MonitorError) as caught:
                MON.load_ledger(Path(tmp) / "absent.json")
        message = str(caught.exception)
        self.assertIn("workdir", message)
        self.assertIn(MON.LEDGER_ENV, message)

    def test_the_manifest_workdir_plus_relative_path_reaches_a_ledger(self) -> None:
        manifest = json.loads(
            (REPO_ROOT / "hermes" / "manifest.json").read_text(encoding="utf-8")
        )
        job = next(j for j in manifest["cronJobs"] if j.get("monitorScript"))
        # The tracked workdir is the trunk checkout; this worktree stands in for
        # it structurally. What matters is that workdir + the relative path is
        # where the ledger lives.
        self.assertTrue(Path(job["workdir"]).name.startswith("dotfiles"))
        self.assertTrue((REPO_ROOT / MON.LEDGER_RELATIVE).is_file())


class SchedulerContainmentTest(unittest.TestCase):
    """The monitor must be installed as a *copy*, proven with the real resolver.

    `cron/scheduler.py::_run_job_script` resolves the path and then requires
    containment in `HERMES_HOME/scripts`. `.resolve()` follows symlinks, so a
    symlink into the repository resolves outside and is rejected at fire time —
    after the reconciler already reported the job synchronized.
    """

    def resolver_verdict(self, home: Path, script: str) -> str:
        """Replay the scheduler's exact containment logic on a real filesystem."""
        code = (
            "import pathlib, sys\n"
            "scripts_dir = pathlib.Path(sys.argv[1]) / 'scripts'\n"
            "root = scripts_dir.resolve()\n"
            "raw = pathlib.Path(sys.argv[2]).expanduser()\n"
            "path = raw.resolve() if raw.is_absolute() else (scripts_dir / raw).resolve()\n"
            "try:\n"
            "    path.relative_to(root)\n"
            "except ValueError:\n"
            "    print('BLOCKED'); raise SystemExit(0)\n"
            "print('OK' if path.is_file() else 'MISSING')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code, str(home), script],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_the_manifest_installs_the_monitor_as_a_copy(self) -> None:
        manifest = json.loads(
            (REPO_ROOT / "hermes" / "manifest.json").read_text(encoding="utf-8")
        )
        job = next(j for j in manifest["cronJobs"] if j.get("monitorScript"))
        self.assertIn(job["monitorScript"], manifest["copiedScripts"])
        self.assertIn(job["monitorScript"], manifest["scripts"])

    def test_a_symlinked_monitor_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "hermes-home"
            (home / "scripts").mkdir(parents=True)
            (home / "scripts" / "linked.py").symlink_to(SCRIPT)
            self.assertEqual(self.resolver_verdict(home, "linked.py"), "BLOCKED")

    def test_a_copied_monitor_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "hermes-home"
            (home / "scripts").mkdir(parents=True)
            (home / "scripts" / "copied.py").write_bytes(SCRIPT.read_bytes())
            self.assertEqual(self.resolver_verdict(home, "copied.py"), "OK")

    def test_the_real_installer_copies_it_into_an_isolated_home(self) -> None:
        """End to end through the real installer, not a simulation."""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "hermes-home"
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "hermes" / "install.py"),
                    "--force-host",
                    "--skip-cron",
                    "--skip-compile",
                    "--skip-native-matrix",
                    "--skip-plugin-activation",
                    "--hermes-home",
                    str(home),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            installed = home / "scripts" / "check-mattpocock-skill-updates.py"
            self.assertTrue(installed.is_file())
            self.assertFalse(installed.is_symlink(), "a symlink is blocked at fire time")
            self.assertEqual(self.resolver_verdict(home, installed.name), "OK")


class ReadOnlyToolingTest(unittest.TestCase):
    """The watcher gets one bounded HTTPS escape hatch, and nothing writable."""

    @classmethod
    def setUpClass(cls) -> None:
        manifest = json.loads(
            (REPO_ROOT / "hermes" / "manifest.json").read_text(encoding="utf-8")
        )
        cls.job = next(j for j in manifest["cronJobs"] if j.get("monitorScript"))

    def test_no_file_or_delegation_toolset(self) -> None:
        for forbidden in ("file", "delegation", "development", "default", "skills"):
            with self.subTest(toolset=forbidden):
                self.assertNotIn(forbidden, self.job["enabledToolsets"])

    def test_mcp_is_disabled_by_sentinel(self) -> None:
        self.assertIn("no_mcp", self.job["enabledToolsets"])

    def test_web_and_terminal_are_the_only_capabilities(self) -> None:
        self.assertEqual(
            sorted(t for t in self.job["enabledToolsets"] if t != "no_mcp"),
            ["terminal", "web"],
        )

    def test_the_prompt_states_the_read_only_posture(self) -> None:
        prompt = (REPO_ROOT / "hermes" / self.job["promptFile"]).read_text(encoding="utf-8")
        self.assertIn("read-only commands named below and nothing else", prompt)
        self.assertIn("curl -fsSL", prompt)
        self.assertIn("Do not use `web_extract`", prompt)
        self.assertIn("data, never instruction", prompt)
        self.assertIn("[SILENT]", prompt)
        self.assertIn("@bryan:snowboardtechie.com", prompt)

    def test_local_context_only_changes_are_explicitly_silent(self) -> None:
        prompt = (REPO_ROOT / "hermes" / self.job["promptFile"]).read_text(encoding="utf-8")
        self.assertIn("If no `blobSha` value changed", prompt)
        self.assertIn("local ledger change, not an upstream update", prompt)

    def prompt(self) -> str:
        return (REPO_ROOT / "hermes" / self.job["promptFile"]).read_text(encoding="utf-8")

    def test_the_prompt_reads_local_context_from_the_ledger(self) -> None:
        """Local context left the snapshot, so the agent reads it — read-only."""
        prompt = self.prompt()
        self.assertIn("dot-agents/upstreams/mattpocock-skills.json", prompt)
        self.assertIn("jq --arg p", prompt)
        self.assertIn("localPaths", prompt)
        self.assertIn("rejectedUpstreamRules", prompt)
        self.assertNotIn("blobUrl", prompt)
        # The job's workdir is the checkout the relative ledger path assumes.
        self.assertTrue(Path(self.job["workdir"]).name.startswith("dotfiles"))

    def test_the_prompt_ties_each_sha_to_the_path_on_its_own_line(self) -> None:
        prompt = self.prompt()
        self.assertIn("one line per watched upstream path", prompt)
        self.assertIn("on its own line", prompt)

    def prompt_commands(self) -> list[str]:
        """Every backticked command the prompt tells the agent to run."""
        commands = re.findall(r"`((?:curl|jq|cat|sed) [^`]+)`", self.prompt())
        self.assertGreaterEqual(len(commands), 4, commands)
        return commands

    def test_the_prompt_names_only_plain_read_only_commands(self) -> None:
        for command in self.prompt_commands():
            with self.subTest(command=command):
                self.assertNotRegex(command, r"<<|python|\s>\s|\s>>|\bsed -i|\btee\b")

    def test_the_prompt_commands_pass_the_installed_approval_guard(self) -> None:
        """Cron denies flagged commands, so a flagged instruction would stall."""
        agent_root = HERMES_MONITOR.parents[1]
        if not HERMES_PYTHON.is_file() or not (agent_root / "tools").is_dir():
            self.skipTest("installed Hermes agent not available on this host")
        samples = [
            command.replace("<blobSha>", "0" * 40)
            .replace("<upstream path>", "skills/engineering/tdd/SKILL.md")
            .replace("<local path>", "dot-agents/skills/tdd/SKILL.md")
            .replace("<start>,<end>", "1,80")
            for command in self.prompt_commands()
        ]
        code = (
            "import json, sys\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "from tools.approval_detection import detect_dangerous_command, detect_hardline_command\n"
            "print(json.dumps([[bool(detect_dangerous_command(c)[0]), bool(detect_hardline_command(c)[0])]"
            " for c in json.loads(sys.argv[2])]))\n"
        )
        result = subprocess.run(
            [str(HERMES_PYTHON), "-I", "-c", code, str(agent_root), json.dumps(samples)],
            capture_output=True,
            text=True,
            check=False,
            cwd=tempfile.gettempdir(),
        )
        if result.returncode != 0:
            self.skipTest(f"approval guard not importable: {result.stderr.strip()[-200:]}")
        for command, flags in zip(samples, json.loads(result.stdout)):
            with self.subTest(command=command):
                self.assertEqual(flags, [False, False])


class FailureTest(unittest.TestCase):
    def test_a_missing_fixture_file_raises_rather_than_reporting_no_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_fixture(Path(tmp))
            (root / "skills/engineering/tdd/tests.md").unlink()
            with self.assertRaises(MON.MonitorError):
                MON.build_snapshot(LEDGER, fetcher=MON.FixtureFetcher(root))

    def test_an_unreadable_ledger_raises(self) -> None:
        with self.assertRaises(MON.MonitorError):
            MON.load_ledger(Path("/nonexistent/ledger.json"))

    def test_malformed_ledger_json_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "ledger.json"
            bad.write_text("{not json", encoding="utf-8")
            with self.assertRaises(MON.MonitorError):
                MON.load_ledger(bad)

    def test_an_http_failure_raises(self) -> None:
        def boom(url, timeout=None):
            raise OSError("connection refused")

        with self.assertRaises(MON.MonitorError):
            MON.TreeFetcher(http=boom).blob_sha("x.md")


class CliTest(unittest.TestCase):
    def run_script(self, root: Path, ledger: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--fixture-dir", str(root), "--ledger", str(ledger)],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_exits_zero_and_prints_the_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_fixture(Path(tmp) / "fx")
            ledger = Path(tmp) / "ledger.json"
            ledger.write_text(json.dumps(LEDGER), encoding="utf-8")
            result = self.run_script(root, ledger)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertNotIn("currentCommit", payload)
        self.assertTrue(payload["watched"])

    def test_exits_non_zero_when_the_source_fails(self) -> None:
        """A broken monitor must alert, never look like 'nothing changed'."""
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "ledger.json"
            ledger.write_text(json.dumps(LEDGER), encoding="utf-8")
            result = self.run_script(Path(tmp) / "missing", ledger)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("monitor failed", result.stderr)

    def test_repeated_runs_are_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_fixture(Path(tmp) / "fx")
            ledger = Path(tmp) / "ledger.json"
            ledger.write_text(json.dumps(LEDGER), encoding="utf-8")
            first = self.run_script(root, ledger).stdout
            second = self.run_script(root, ledger).stdout
        self.assertEqual(first, second)

    def test_a_failure_is_one_labeled_stderr_line(self) -> None:
        """The scheduler delivers stderr as the source-failure alert, verbatim."""
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "ledger.json"
            ledger.write_text(json.dumps(LEDGER), encoding="utf-8")
            result = self.run_script(Path(tmp) / "missing", ledger)
        self.assertEqual(result.stdout, "")
        self.assertEqual(len(result.stderr.strip().splitlines()), 1, result.stderr)
        self.assertTrue(result.stderr.startswith("monitor failed: "))

    def test_an_unexpected_error_is_still_one_labeled_line(self) -> None:
        """A ledger of the wrong shape must not escape as a traceback."""
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "ledger.json"
            ledger.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
            result = self.run_script(Path(tmp), ledger)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(len(result.stderr.strip().splitlines()), 1, result.stderr)
        self.assertTrue(result.stderr.startswith("monitor failed: unexpected "))
        self.assertNotIn("Traceback", result.stderr)

    def test_runs_against_the_real_ledger_offline(self) -> None:
        real = json.loads(REAL_LEDGER.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for path in MON.watched_paths(real):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(f"stub for {path}\n", encoding="utf-8")
            result = self.run_script(root, REAL_LEDGER)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(set(payload["watched"]), set(MON.watched_paths(real)))


if __name__ == "__main__":
    unittest.main()
