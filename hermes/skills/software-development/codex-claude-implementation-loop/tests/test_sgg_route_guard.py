#!/usr/bin/env python3
"""Tests for the Claude worker's independent SGG repository guard."""

from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "sgg_route_guard.py"
SPEC = importlib.util.spec_from_file_location("sgg_route_guard", MODULE_PATH)
assert SPEC and SPEC.loader
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)


class SggRouteGuardTests(unittest.TestCase):
    def make_repo(self, remote: str) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
        subprocess.run(["git", "remote", "add", "origin", remote], cwd=root, check=True)
        return root

    def test_accepts_exact_sgg_repository_on_github(self) -> None:
        root = self.make_repo("git@github.com:HHS/simpler-grants-protocol.git")
        result = GUARD.validate_sgg_worktree(str(root))
        self.assertTrue(result["ok"])
        self.assertEqual(result["origin_host"], "github.com")
        self.assertEqual(result["origin_repository"], "hhs/simpler-grants-protocol")

    def test_rejects_non_sgg_repository(self) -> None:
        root = self.make_repo("git@github.com:bryan/dotfiles.git")
        with self.assertRaises(GUARD.GuardError):
            GUARD.validate_sgg_worktree(str(root))

    def test_rejects_allowlisted_suffix_on_another_forge(self) -> None:
        root = self.make_repo("https://evil.example/HHS/simpler-grants-protocol.git")
        with self.assertRaises(GUARD.GuardError):
            GUARD.validate_sgg_worktree(str(root))


if __name__ == "__main__":
    unittest.main()
