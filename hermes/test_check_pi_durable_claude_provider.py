"""Contract tests for the official Pi Durable Claude provider monitor.

Run: python3 -m unittest hermes.test_check_pi_durable_claude_provider
"""
import importlib.util
import json
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("scripts") / "check-pi-durable-claude-provider.py"
SPEC = importlib.util.spec_from_file_location("check_pi_durable_claude_provider", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MON = importlib.util.module_from_spec(SPEC)
sys.modules["check_pi_durable_claude_provider"] = MON
SPEC.loader.exec_module(MON)

TREE = [
    "packages/ai/src/providers/anthropic.ts",
    "packages/ai/src/providers/anthropic.models.ts",
    "packages/ai/src/providers/openai.ts",
    "packages/ai/src/providers/data-json.d.ts",
    "packages/coding-agent/examples/extensions/claude-rules.ts",
    "docs/claude-notes.md",
]
CHANGELOG = "# Changelog\n\n## 1.3.0\n- Fixed Claude Code tool name normalization.\n- Added a new model.\n"
NPM = {"objects": [{"package": {"name": n}} for n in ("@earendil-works/pi-ai", "@earendil-works/pi-durable", "unrelated")]}


def fake(tree=TREE, changelog=CHANGELOG, npm=NPM, truncated=False):
    def get(url: str) -> bytes:
        if url == MON.TREE_URL:
            return json.dumps({"truncated": truncated, "tree": [{"path": p} for p in tree]}).encode()
        if url == MON.NPM_SEARCH_URL:
            return json.dumps(npm).encode()
        if url.startswith(MON.RAW_BASE) and url.endswith("CHANGELOG.md"):
            return changelog.encode()
        raise AssertionError(f"unexpected URL {url}")

    return get


class SnapshotTest(unittest.TestCase):
    def test_snapshot_keeps_only_official_signals_and_is_stable(self):
        first = MON.render(MON.build_snapshot(fake()))
        self.assertEqual(first, MON.render(MON.build_snapshot(fake())))
        snapshot = json.loads(first)
        self.assertEqual(snapshot["piAiProviderModules"], ["anthropic", "openai"])
        self.assertEqual(snapshot["claudeNamedPaths"], ["packages/coding-agent/examples/extensions/claude-rules.ts"])
        self.assertEqual(snapshot["earendilNpmPackages"], ["@earendil-works/pi-ai", "@earendil-works/pi-durable"])
        self.assertEqual(snapshot["changelogMentions"]["ai"], ["- Fixed Claude Code tool name normalization."])
        self.assertNotIn("1.3.0", first)

    def test_a_new_official_provider_changes_the_snapshot(self):
        before = MON.render(MON.build_snapshot(fake()))
        after = MON.render(MON.build_snapshot(fake(tree=TREE + ["packages/ai/src/providers/claude-code.ts"])))
        self.assertNotEqual(before, after)
        self.assertIn("claude-code", json.loads(after)["piAiProviderModules"])

    def test_unrelated_changelog_entries_do_not_change_the_snapshot(self):
        before = MON.render(MON.build_snapshot(fake()))
        after = MON.render(MON.build_snapshot(fake(changelog=CHANGELOG + "- Added another unrelated model.\n")))
        self.assertEqual(before, after)

    def test_source_failures_are_errors_not_silence(self):
        for get in (
            fake(truncated=True),
            fake(tree=["packages/ai/src/providers/openai.ts"]),
            fake(npm={"objects": []}),
            fake(changelog="not a changelog"),
        ):
            with self.subTest(), self.assertRaises(MON.MonitorError):
                MON.build_snapshot(get)


class ManifestTest(unittest.TestCase):
    def test_job_is_a_copied_monitor_alert(self):
        manifest = json.loads(Path(__file__).with_name("manifest.json").read_text())
        job = next(j for j in manifest["cronJobs"] if j["name"] == "Watch for official Pi Durable Claude provider")
        self.assertEqual(job["monitorScript"], SCRIPT.name)
        self.assertIn(SCRIPT.name, manifest["copiedScripts"])
        self.assertEqual(job["deliveryIntent"], "alert")
        self.assertFalse(job["noAgent"])
        self.assertTrue((Path(__file__).parent / job["promptFile"]).is_file())


if __name__ == "__main__":
    unittest.main()
