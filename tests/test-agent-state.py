#!/usr/bin/env python3
"""Skill state lives in .agent-work/ and still resumes legacy .hermes/ state."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LIB = REPO_ROOT / "dot-agents" / "lib"
sys.path.insert(0, str(LIB))
import agent_state  # noqa: E402


class AgentStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.trunk = Path(self._tmp.name).resolve()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_new_item_goes_to_agent_work(self) -> None:
        result = agent_state.resolve(self.trunk, "issue-work", "owner-repo-1")
        self.assertEqual(result["path"], str(self.trunk / ".agent-work/issue-work/owner-repo-1"))
        self.assertFalse(result["legacy"])
        self.assertFalse(result["exists"])

    def test_existing_legacy_item_is_resumed_in_place(self) -> None:
        legacy = self.trunk / ".hermes/issue-work/owner-repo-1"
        legacy.mkdir(parents=True)
        result = agent_state.resolve(self.trunk, "issue-work", "owner-repo-1")
        self.assertEqual(result["path"], str(legacy))
        self.assertTrue(result["legacy"])
        self.assertTrue(legacy.is_dir())
        self.assertFalse((self.trunk / ".agent-work").exists())

    def test_current_item_wins_over_legacy(self) -> None:
        (self.trunk / ".hermes/issue-work/owner-repo-1").mkdir(parents=True)
        current = self.trunk / ".agent-work/issue-work/owner-repo-1"
        current.mkdir(parents=True)
        result = agent_state.resolve(self.trunk, "issue-work", "owner-repo-1")
        self.assertEqual(result["path"], str(current))
        self.assertFalse(result["legacy"])

    def test_other_legacy_items_do_not_pull_new_items_back(self) -> None:
        (self.trunk / ".hermes/issue-work/owner-repo-1").mkdir(parents=True)
        result = agent_state.resolve(self.trunk, "issue-work", "owner-repo-2")
        self.assertEqual(result["path"], str(self.trunk / ".agent-work/issue-work/owner-repo-2"))

    def test_skill_root_without_key_is_always_new_place(self) -> None:
        (self.trunk / ".hermes/issue-create/drafts").mkdir(parents=True)
        result = agent_state.resolve(self.trunk, "issue-create")
        self.assertEqual(result["path"], str(self.trunk / ".agent-work/issue-create"))
        self.assertEqual(
            result["roots"],
            [str(self.trunk / ".agent-work/issue-create"), str(self.trunk / ".hermes/issue-create")],
        )

    def test_names_must_be_single_segments(self) -> None:
        for bad in ("../x", "a/b", "", ".", ".."):
            with self.assertRaises(ValueError):
                agent_state.resolve(self.trunk, "issue-work", bad)
        with self.assertRaises(ValueError):
            agent_state.roots(self.trunk, "../issue-work")

    def test_is_state_path_accepts_children_of_both_roots_only(self) -> None:
        self.assertTrue(agent_state.is_state_path(self.trunk, "issue-work", self.trunk / ".agent-work/issue-work/x"))
        self.assertTrue(agent_state.is_state_path(self.trunk, "issue-work", self.trunk / ".hermes/issue-work/x"))
        self.assertFalse(agent_state.is_state_path(self.trunk, "issue-work", self.trunk / ".agent-work/issue-work"))
        self.assertFalse(agent_state.is_state_path(self.trunk, "issue-work", self.trunk / ".agent-work/other/x"))
        self.assertFalse(agent_state.is_state_path(self.trunk, "issue-work", self.trunk / "x"))
        self.assertFalse(
            agent_state.is_state_path(self.trunk, "issue-work", self.trunk / ".agent-work/issue-work/../../x")
        )

    def run_cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(LIB / "agent_state.py"), *args],
            text=True, capture_output=True, check=False,
        )

    def test_cli_creates_new_item_only_with_create(self) -> None:
        args = ("dir", "--trunk", str(self.trunk), "--skill", "pr-self-review", "--key", "o-r-5")
        out = self.run_cli(*args)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertFalse(Path(json.loads(out.stdout)["path"]).exists())
        out = self.run_cli(*args, "--create")
        path = Path(json.loads(out.stdout)["path"])
        self.assertTrue(path.is_dir())
        self.assertEqual(path, self.trunk / ".agent-work/pr-self-review/o-r-5")

    def test_cli_roots_and_bad_name(self) -> None:
        out = self.run_cli("roots", "--trunk", str(self.trunk), "--skill", "issue-create")
        self.assertEqual(json.loads(out.stdout)[1], str(self.trunk / ".hermes/issue-create"))
        out = self.run_cli("dir", "--trunk", str(self.trunk), "--skill", "issue-work", "--key", "../x")
        self.assertEqual(out.returncode, 2)
        self.assertFalse(json.loads(out.stdout)["ok"])

    def test_agent_work_is_ignored_everywhere(self) -> None:
        global_ignore = (REPO_ROOT / "dot-config/git/ignore").read_text().splitlines()
        repo_ignore = (REPO_ROOT / ".gitignore").read_text().splitlines()
        self.assertIn(".agent-work/", global_ignore)
        self.assertIn(".agent-work/", repo_ignore)


if __name__ == "__main__":
    unittest.main()
