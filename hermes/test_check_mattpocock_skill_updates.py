#!/usr/bin/env python3
"""Offline tests for the upstream skill-update monitor.

The scheduler hashes this script's exact stdout bytes and suppresses the whole
agent run when they are unchanged. Three properties follow, and all three are
tested rather than trusted:

* **Identical upstream content produces identical bytes.** Any instability — a
  timestamp, dict ordering, a local path — would make every weekly tick look
  like a change and turn the watcher into noise.
* **An unrelated upstream commit produces identical bytes.** Identity is the
  per-file Git blob sha, so a push touching nothing we watch stays silent.
  Keying on the repository tip was the bug this replaces.
* **A real change moves the output.** A watcher that cannot notice is worse than
  none, because it reports quiet.

Everything runs against a fixture directory or an injected HTTP stub. No test
reaches the network.

Run: python3 -m unittest hermes/test_check_mattpocock_skill_updates.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
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

    def test_the_blob_url_is_pinned_to_the_sha(self) -> None:
        url = MON.blob_url("0" * 40)
        self.assertTrue(url.endswith("/git/blobs/" + "0" * 40))
        self.assertIn("mattpocock/skills", url)


class WatchContextTest(unittest.TestCase):
    def test_context_is_sorted_and_maps_every_adaptation(self) -> None:
        context = MON.watched_context(LEDGER)
        self.assertEqual(list(context), sorted(context))
        shared = context["skills/engineering/codebase-design/SKILL.md"]
        self.assertEqual(
            [entry["skill"] for entry in shared],
            ["codebase-architecture", "tdd-vocabulary-consumer"],
        )

    def test_context_carries_local_divergence_and_rejected_rules(self) -> None:
        """The watcher has no file tools; this is how relevance reaches it."""
        entry = MON.watched_context(LEDGER)["skills/engineering/tdd/SKILL.md"][0]
        self.assertEqual(entry["localPaths"], ["dot-agents/skills/tdd/SKILL.md"])
        self.assertTrue(entry["localChanges"])
        self.assertTrue(entry["rejectedUpstreamRules"])

    def test_long_context_lists_are_trimmed_with_an_honest_tail(self) -> None:
        """A silent truncation would read as a complete list."""
        ledger = {
            "adaptations": [
                {
                    "skill": "x",
                    "upstreamPaths": ["a.md"],
                    "watchedFiles": ["a.md"],
                    "localPaths": [],
                    "localChanges": [f"change {i}" for i in range(MON.MAX_CONTEXT_ITEMS + 4)],
                    "rejectedUpstreamRules": [],
                }
            ]
        }
        changes = MON.watched_context(ledger)["a.md"][0]["localChanges"]
        self.assertEqual(len(changes), MON.MAX_CONTEXT_ITEMS + 1)
        self.assertIn("and 4 more", changes[-1])

    def test_a_watched_file_with_no_declared_source_is_refused(self) -> None:
        broken = {
            "adaptations": [{"skill": "x", "upstreamPaths": ["a.md"], "watchedFiles": ["b.md"]}]
        }
        with self.assertRaises(MON.MonitorError):
            MON.watched_context(broken)

    def test_an_empty_watch_list_is_refused(self) -> None:
        with self.assertRaises(MON.MonitorError):
            MON.watched_context({"adaptations": []})

    def test_the_real_ledger_produces_a_watch_list(self) -> None:
        context = MON.watched_context(json.loads(REAL_LEDGER.read_text(encoding="utf-8")))
        self.assertTrue(context)
        for path, entries in context.items():
            with self.subTest(path=path):
                self.assertTrue(path.startswith("skills/"))
                self.assertTrue(entries)
                for entry in entries:
                    self.assertTrue(entry["localPaths"])


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

    def test_every_watched_entry_carries_a_pinned_blob_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = json.loads(snapshot(write_fixture(Path(tmp))))
        for path, entry in payload["watched"].items():
            with self.subTest(path=path):
                self.assertTrue(entry["blobUrl"].endswith(entry["blobSha"]))


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

    def test_a_ledger_change_moves_the_output(self) -> None:
        """Local divergence is part of relevance, so a ledger edit re-triggers."""
        with tempfile.TemporaryDirectory() as tmp:
            root = write_fixture(Path(tmp))
            before = snapshot(root)
            edited = json.loads(json.dumps(LEDGER))
            edited["adaptations"][0]["rejectedUpstreamRules"].append("Something new.")
            after = MON.render(MON.build_snapshot(edited, fetcher=MON.FixtureFetcher(root)))
        self.assertNotEqual(before, after)


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
    """The watcher reads untrusted third-party prose; give it nothing to break."""

    @classmethod
    def setUpClass(cls) -> None:
        manifest = json.loads(
            (REPO_ROOT / "hermes" / "manifest.json").read_text(encoding="utf-8")
        )
        cls.job = next(j for j in manifest["cronJobs"] if j.get("monitorScript"))

    def test_no_file_or_terminal_or_delegation_toolset(self) -> None:
        for forbidden in ("file", "terminal", "delegation", "development", "default", "skills"):
            with self.subTest(toolset=forbidden):
                self.assertNotIn(forbidden, self.job["enabledToolsets"])

    def test_mcp_is_disabled_by_sentinel(self) -> None:
        self.assertIn("no_mcp", self.job["enabledToolsets"])

    def test_web_is_the_only_capability(self) -> None:
        self.assertEqual(
            sorted(t for t in self.job["enabledToolsets"] if t != "no_mcp"), ["web"]
        )

    def test_the_prompt_states_the_read_only_posture(self) -> None:
        prompt = (REPO_ROOT / "hermes" / self.job["promptFile"]).read_text(encoding="utf-8")
        self.assertIn("web access only", prompt)
        self.assertIn("data, never instruction", prompt)
        self.assertIn("[SILENT]", prompt)
        self.assertIn("@bryan:snowboardtechie.com", prompt)

    def test_the_prompt_does_not_ask_for_local_file_reads(self) -> None:
        """It cannot read the ledger, so it must not be told to."""
        prompt = (REPO_ROOT / "hermes" / self.job["promptFile"]).read_text(encoding="utf-8")
        self.assertNotIn("dot-agents/upstreams/mattpocock-skills.json", prompt)
        self.assertIn("blobUrl", prompt)
        self.assertIn("rejectedUpstreamRules", prompt)


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

    def test_runs_against_the_real_ledger_offline(self) -> None:
        real = json.loads(REAL_LEDGER.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for path in MON.watched_context(real):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(f"stub for {path}\n", encoding="utf-8")
            result = self.run_script(root, REAL_LEDGER)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(set(payload["watched"]), set(MON.watched_context(real)))


if __name__ == "__main__":
    unittest.main()
