#!/usr/bin/env python3
"""Exercise shared-context hooks in disposable Git/Worktrunk worktrees (Python 3.11+)."""

import os
from pathlib import Path
import subprocess
import tempfile
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "dot-config/worktrunk/config.toml"
HELPER = ROOT / "dot-agents/skills/worktrunk/scripts/link-shared-context.sh"


class WorktrunkContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="worktrunk-context-", dir=os.environ.get("TMPDIR"))
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name).resolve()
        self.trunk = self.directory / "repo"
        self.trunk.mkdir()
        self.env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        self.run_command("git", "init", "-b", "main", cwd=self.trunk)
        self.run_command("git", "-c", "user.name=Context Test", "-c",
                         "user.email=context@example.invalid", "-c", "commit.gpgsign=false",
                         "commit", "--allow-empty", "-m", "Fixture", cwd=self.trunk)
        self.empty_config = self.directory / "config.toml"
        self.empty_config.write_text("")
        self.run_command("wt", "--config", str(self.empty_config), "-y", "switch",
                         "--create", "context-test", "--base", "main", "--no-cd", cwd=self.trunk)
        self.worktree = self.directory / "repo.context-test"
        self.assertTrue((self.worktree / ".git").is_file())
        self.addCleanup(self.remove_worktree)

    def run_command(self, *args, cwd):
        result = subprocess.run(args, cwd=cwd, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def remove_worktree(self):
        # Ignored context fixtures are disposable, not user work.
        self.run_command("wt", "--config", str(self.empty_config), "-y", "remove",
                         "context-test", "--force", "--foreground", cwd=self.trunk)

    def run_context_hook(self):
        config = tomllib.loads(CONFIG.read_text())
        command = next(step["link-agent-context"] for step in config["pre-start"]
                       if "link-agent-context" in step)
        self.run_command("sh", "-c", command, cwd=self.worktree)

    def test_global_hook_links_agents_without_creating_claude_bridge(self):
        (self.trunk / "AGENTS.md").write_text("Shared instructions\n")
        self.run_context_hook()
        self.assertTrue((self.worktree / "AGENTS.md").is_symlink())
        self.assertEqual((self.worktree / "AGENTS.md").resolve(), self.trunk / "AGENTS.md")
        self.assertFalse((self.worktree / "CLAUDE.md").exists())
        self.assertFalse((self.worktree / "CLAUDE.md").is_symlink())
        (self.trunk / "AGENTS.md").write_text("Updated instructions\n")
        self.assertEqual((self.worktree / "AGENTS.md").read_text(), "Updated instructions\n")

    def test_helper_skips_retired_bridges_and_preserves_real_claude_files(self):
        (self.trunk / "AGENTS.md").write_text("Shared instructions\n")
        (self.trunk / "CLAUDE.md").symlink_to("AGENTS.md")
        nested = self.trunk / "nested"
        nested.mkdir()
        (nested / "AGENTS.md").write_text("Nested instructions\n")
        (nested / "CLAUDE.md").symlink_to(nested / "AGENTS.md")
        (self.worktree / "nested").mkdir()
        (self.trunk / "vault").mkdir()
        self.run_command("bash", str(HELPER), str(self.worktree), cwd=self.trunk)
        for relative in (Path("."), Path("nested")):
            self.assertTrue((self.worktree / relative / "AGENTS.md").is_symlink())
            self.assertFalse((self.worktree / relative / "CLAUDE.md").is_symlink())
            self.assertFalse((self.worktree / relative / "CLAUDE.md").exists())
        self.assertTrue((self.worktree / "vault").is_symlink())
        # Real Claude-specific instructions may still be shared; existing files stay intact.
        (self.trunk / "CLAUDE.md").unlink()
        (self.trunk / "CLAUDE.md").write_text("Claude-specific instructions\n")
        (self.worktree / "nested/CLAUDE.md").write_text("Local instructions\n")
        self.run_command("bash", str(HELPER), str(self.worktree), cwd=self.trunk)
        self.assertEqual((self.worktree / "CLAUDE.md").read_text(), "Claude-specific instructions\n")
        self.assertEqual((self.worktree / "nested/CLAUDE.md").read_text(), "Local instructions\n")

    def test_global_hook_preserves_real_claude_and_foreign_symlinks(self):
        (self.trunk / "AGENTS.md").write_text("Shared instructions\n")
        claude = self.worktree / "CLAUDE.md"
        claude.write_text("Local Claude instructions\n")
        self.run_context_hook()
        self.assertFalse(claude.is_symlink())
        self.assertEqual(claude.read_text(), "Local Claude instructions\n")
        claude.unlink()
        claude.symlink_to("missing-foreign-instructions.md")
        self.run_context_hook()
        self.assertEqual(str(claude.readlink()), "missing-foreign-instructions.md")

    def test_global_hook_without_agents_creates_no_context(self):
        self.run_context_hook()
        self.assertFalse((self.worktree / "AGENTS.md").is_symlink())
        self.assertFalse((self.worktree / "CLAUDE.md").is_symlink())


if __name__ == "__main__":
    unittest.main()
