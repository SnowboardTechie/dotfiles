#!/usr/bin/env python3
"""Fixture tests for scripts/retire-agent-memory.py (isolated temp homes only)."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HELPER = REPO_ROOT / "scripts" / "retire-agent-memory.py"
RUNTIME = "/home/peer/.hindsight/coding-agents"

FOREIGN_HOOK = {"type": "command", "command": "node ~/.claude/hooks/gsd-context-monitor.js"}
CLAUDE_SETTINGS = {
    "model": "opus[1m]",
    "hooks": {
        "SessionStart": [
            {"hooks": [{"type": "command", "command": '"/home/peer/.claude/hooks/context-mode-cache-heal.mjs"'}]},
            {"hooks": [{"type": "command", "command": f'node "{RUNTIME}/dist/claude-sessionstart-hook.js"'}]},
            {"matcher": "*", "hooks": [FOREIGN_HOOK]},
        ],
        "UserPromptSubmit": [
            {"hooks": [{"type": "command", "command": f'HINDSIGHT_TOKEN=sekrit node "{RUNTIME}/dist/claude-hook.js"'}]},
        ],
        "Stop": [
            {"hooks": [
                {"type": "command", "command": f'node "{RUNTIME}/dist/claude-stop-hook.js"'},
                {"type": "command", "command": "afplay done.aiff"},
            ]},
        ],
    },
    "enabledPlugins": {
        "context-mode@context-mode": True,
        "claude-mem@thedotmack": False,
        "context7@claude-plugins-official": True,
    },
    "extraKnownMarketplaces": {
        "context-mode": {"source": {"source": "github", "repo": "mksglu/context-mode"}},
        "thedotmack": {"source": {"source": "github", "repo": "someone-else/fork"}},
        "ponytail": {"source": {"source": "github", "repo": "x/ponytail"}},
    },
    "autoMemoryEnabled": True,
}
CLAUDE_STATE = {
    "numStartups": 7,
    "mcpServers": {
        "hindsight": {"type": "http", "url": "https://bryans-mac-studio.tail5ba690.ts.net:9443/mcp/"},
        "context7": {"type": "http", "url": "https://mcp.context7.com/mcp"},
    },
    "projects": {
        "/work": {"mcpServers": {"notes": {"command": "notes-mcp"}}, "history": ["kept"]},
    },
}
PI_SETTINGS = {"defaultModel": "local", "extensions": [f"{RUNTIME}/dist/pi.js", "/opt/pi/other.js"]}
OPENCODE = {"model": "openai/x", "plugin": [RUNTIME, "opencode-foreign"], "mcp": {}}


class RetireAgentMemoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.claude_settings = self.write(".claude/settings.json", CLAUDE_SETTINGS)
        self.claude_state = self.write(".claude.json", CLAUDE_STATE)
        self.pi = self.write(".pi/agent/settings.json", PI_SETTINGS)
        self.opencode = self.write(".config/opencode/opencode.json", OPENCODE)
        self.memory = self.home / ".claude/projects/-work/memory/MEMORY.md"
        self.memory.parent.mkdir(parents=True)
        self.memory.write_text("- native memory\n", encoding="utf-8")
        self.hindsight_data = self.home / ".hindsight/coding-agent.json"
        self.hindsight_data.parent.mkdir()
        self.hindsight_data.write_text("{}", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write(self, relative: str, value: dict) -> Path:
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        return path

    def read(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def run_helper(self, mode: str, expected_status: int = 0) -> str:
        result = subprocess.run(
            [sys.executable, str(HELPER), mode],
            env={**os.environ, "HOME": str(self.home)},
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, expected_status, result.stdout + result.stderr)
        return result.stdout

    def load_helper(self):
        spec = importlib.util.spec_from_file_location("retire_agent_memory", HELPER)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_check_reports_without_writing(self) -> None:
        before = {path: path.read_bytes() for path in (self.claude_settings, self.claude_state, self.pi, self.opencode)}

        output = self.run_helper("--check")

        self.assertIn("would remove", output)
        self.assertIn("summary: 10 retired entries found", output)
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content, path)

    def test_apply_removes_only_retired_entries_and_is_idempotent(self) -> None:
        self.run_helper("--apply")

        settings = self.read(self.claude_settings)
        self.assertEqual(settings["model"], "opus[1m]")
        self.assertIs(settings["autoMemoryEnabled"], True)
        self.assertEqual(settings["hooks"]["SessionStart"], [{"matcher": "*", "hooks": [FOREIGN_HOOK]}])
        self.assertNotIn("UserPromptSubmit", settings["hooks"])
        self.assertEqual(
            settings["hooks"]["Stop"],
            [{"hooks": [{"type": "command", "command": "afplay done.aiff"}]}],
        )
        self.assertEqual(settings["enabledPlugins"], {"context7@claude-plugins-official": True})
        # A same-named marketplace from another repository is foreign.
        self.assertEqual(sorted(settings["extraKnownMarketplaces"]), ["ponytail", "thedotmack"])

        state = self.read(self.claude_state)
        self.assertEqual(sorted(state["mcpServers"]), ["context7"])
        self.assertEqual(state["numStartups"], 7)
        self.assertEqual(state["projects"], CLAUDE_STATE["projects"])

        self.assertEqual(self.read(self.pi)["extensions"], ["/opt/pi/other.js"])
        self.assertEqual(self.read(self.pi)["defaultModel"], "local")
        self.assertEqual(self.read(self.opencode)["plugin"], ["opencode-foreign"])

        self.assertEqual(self.memory.read_text(encoding="utf-8"), "- native memory\n")
        self.assertTrue(self.hindsight_data.exists())

        snapshot = {path: path.read_bytes() for path in (self.claude_settings, self.claude_state, self.pi, self.opencode)}
        second = self.run_helper("--apply")
        self.assertIn("summary: 0 retired entries removed", second)
        for path, content in snapshot.items():
            self.assertEqual(path.read_bytes(), content, path)

    def test_reports_hook_categories_without_commands(self) -> None:
        output = self.run_helper("--check")

        self.assertIn("hook UserPromptSubmit: hindsight", output)
        self.assertIn("hook SessionStart: context-mode-cache-heal", output)
        self.assertNotIn("sekrit", output)
        self.assertNotIn("claude-hook.js", output)

    def test_concurrent_rewrite_between_read_and_replace_is_not_clobbered(self) -> None:
        module = self.load_helper()
        concurrent = json.dumps({**CLAUDE_STATE, "numStartups": 8}, indent=2).encode()
        prune = module.prune_claude_state

        def prune_then_claude_writes(state, removed):
            prune(state, removed)
            self.claude_state.write_bytes(concurrent)

        module.prune_claude_state = prune_then_claude_writes
        total, failures = module.reconcile(self.home, True)

        self.assertEqual(failures, 1)
        self.assertEqual(self.claude_state.read_bytes(), concurrent)
        self.assertEqual(sorted(p.name for p in self.home.glob(".claude.json.*")), [])
        # Other files are still cleaned in the same run.
        self.assertEqual(self.read(self.pi)["extensions"], ["/opt/pi/other.js"])
        self.assertEqual(total, 9)

    def test_malformed_target_fails_nonzero_and_is_untouched(self) -> None:
        self.pi.write_text("{not json", encoding="utf-8")

        output = self.run_helper("--apply", expected_status=1)

        self.assertIn("ERROR: unreadable", output)
        self.assertIn("1 file(s) failed", output)
        self.assertEqual(self.pi.read_text(encoding="utf-8"), "{not json")
        self.assertNotIn("context-mode@context-mode", self.read(self.claude_settings)["enabledPlugins"])

    def test_apply_writes_through_a_stowed_symlink(self) -> None:
        repo_copy = self.home / "dotfiles/dot-claude/settings.json"
        repo_copy.parent.mkdir(parents=True)
        self.claude_settings.rename(repo_copy)
        self.claude_settings.symlink_to(repo_copy)

        self.run_helper("--apply")

        self.assertTrue(self.claude_settings.is_symlink())
        self.assertNotIn("context-mode@context-mode", self.read(repo_copy)["enabledPlugins"])

    def test_missing_configs_are_a_clean_no_op(self) -> None:
        for path in (self.claude_settings, self.claude_state, self.pi, self.opencode):
            path.unlink()

        output = self.run_helper("--apply")

        self.assertIn("summary: 0 retired entries removed", output)


if __name__ == "__main__":
    unittest.main()
