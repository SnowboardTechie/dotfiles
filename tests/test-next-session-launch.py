#!/usr/bin/env python3
"""Tests for dot-agents/skills/next-session/scripts/launch_next_session.py.

A fake `herdr` and a fake `ps` stand in for the real ones, and a temporary
HERMES_HOME holds the TTY records, so nothing here touches a live Herdr session.

Run: python3 -m unittest tests/test-next-session-launch.py
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "dot-agents" / "skills" / "next-session" / "scripts" / "launch_next_session.py"
SESSION = "local-abc123"

FAKE_HERDR = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import json, os, sys
    state = json.load(open(os.environ["FAKE_STATE"]))
    args = sys.argv[1:]
    with open(os.environ["FAKE_LOG"], "a") as log:
        log.write(json.dumps(args) + "\\n")
    def out(result):
        print(json.dumps({"id": "fake", "result": result}))
        sys.exit(0)
    if args[:2] == ["pane", "list"]:
        out({"panes": state["panes"]})
    if args[:2] == ["pane", "process-info"]:
        pane = args[args.index("--pane") + 1]
        out({"process_info": {"pane_id": pane, "foreground_processes": [{"pid": state["pids"][pane]}]}})
    if args[:2] == ["pane", "split"]:
        out({"pane": {"pane_id": "w1:pNEW"}})
    if args[:2] == ["agent", "start"]:
        if state.get("start_fails"):
            print("agent_not_ready", file=sys.stderr)
            sys.exit(3)
        out({"agent": {"agent": "hermes", "pane_id": args[args.index("--pane") + 1]}})
    if args[:2] == ["agent", "get"]:
        out({"agent": {"agent": state.get("started_kind", "hermes"), "pane_id": "w1:pNEW", "agent_status": "working"}})
    sys.exit(9)
    """
)

FAKE_PS = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import json, os, sys
    ttys = json.load(open(os.environ["FAKE_STATE"]))["ttys"]
    print(ttys.get(sys.argv[sys.argv.index("-p") + 1], "??"))
    """
)


class LaunchNextSessionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="next-session-test-"))
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        for name, body in (("herdr", FAKE_HERDR), ("ps", FAKE_PS)):
            path = bin_dir / name
            path.write_text(body)
            path.chmod(0o755)
        self.home = self.tmp / "hermes"
        (self.home / "terminal-sessions").mkdir(parents=True)
        self.record("ttys003", SESSION)
        self.record("ttys004", "local-other")
        self.cwd = self.tmp / "work"
        self.cwd.mkdir()
        self.state = {
            "panes": [
                {"pane_id": "w1:p1", "agent": "hermes", "foreground_cwd": str(self.cwd)},
                {"pane_id": "w1:p2", "agent": "hermes", "foreground_cwd": str(self.cwd)},
                {"pane_id": "w1:p3", "agent": "claude", "foreground_cwd": str(self.cwd)},
            ],
            "pids": {"w1:p1": 101, "w1:p2": 102, "w1:p3": 103},
            "ttys": {"101": "ttys004", "102": "ttys003", "103": "ttys003"},
        }
        self.prompt = self.tmp / "prompt.md"
        self.prompt.write_text("Work the map.\nUse the wayfinder skill.\n")
        self.log = self.tmp / "herdr.log"

    def record(self, tty: str, session: str) -> None:
        (self.home / "terminal-sessions" / f"tty-dev-{tty}").write_text(json.dumps({"session_id": session, "cwd": "/", "ts": 1}))

    def run_script(self, *args: str, session: str = SESSION) -> tuple[int, dict]:
        state = self.tmp / "state.json"
        state.write_text(json.dumps(self.state))
        env = {
            **os.environ,
            "PATH": f"{self.tmp / 'bin'}:{os.environ['PATH']}",
            "HERMES_HOME": str(self.home),
            "HERMES_SESSION_ID": session,
            "FAKE_STATE": str(state),
            "FAKE_LOG": str(self.log),
        }
        env.pop("HERDR_BIN", None)
        done = subprocess.run(["python3", str(SCRIPT), *args], capture_output=True, text=True, env=env, timeout=60)
        return done.returncode, json.loads(done.stdout)

    def calls(self) -> list[list[str]]:
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_whoami_finds_the_hermes_pane_on_this_sessions_tty(self) -> None:
        code, out = self.run_script("whoami")
        self.assertEqual(code, 0, out)
        self.assertEqual((out["pane_id"], out["tty"]), ("w1:p2", "ttys003"))

    def test_a_claude_pane_on_the_same_tty_is_not_the_caller(self) -> None:
        code, out = self.run_script("whoami")
        self.assertEqual(out["pane_id"], "w1:p2")

    def test_refuses_without_a_tty_record(self) -> None:
        code, out = self.run_script("whoami", session="local-missing")
        self.assertEqual(code, 1)
        self.assertIn("TTY", out["reason"])

    def test_refuses_when_two_hermes_panes_share_the_tty(self) -> None:
        self.state["ttys"]["101"] = "ttys003"
        code, out = self.run_script("whoami")
        self.assertEqual(code, 1)
        self.assertEqual(sorted(out["panes"]), ["w1:p1", "w1:p2"])

    def test_refuses_without_a_session_id(self) -> None:
        code, out = self.run_script("whoami", session="")
        self.assertEqual(code, 1)
        self.assertIn("HERMES_SESSION_ID", out["reason"])

    def test_dry_run_splits_nothing(self) -> None:
        code, out = self.run_script("launch", "--prompt-file", str(self.prompt), "--name", "wf-182", "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertFalse(out["launched"])
        self.assertEqual(out["argv"], ["hermes", "chat", "--query-file", str(self.prompt.resolve())])
        self.assertFalse(any(call[:2] in (["pane", "split"], ["agent", "start"]) for call in self.calls()))

    def test_launch_splits_right_without_focus_and_seeds_the_prompt(self) -> None:
        code, out = self.run_script("launch", "--prompt-file", str(self.prompt), "--name", "wf-182", "--skills", "wayfinder")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["pane"], "w1:pNEW")
        calls = self.calls()
        split = next(c for c in calls if c[:2] == ["pane", "split"])
        self.assertEqual(split[2], "w1:p2")
        self.assertEqual(split[split.index("--direction") + 1], "right")
        self.assertIn("--no-focus", split)
        self.assertEqual(split[split.index("--cwd") + 1], str(self.cwd))
        start = next(c for c in calls if c[:2] == ["agent", "start"])
        self.assertEqual(start[start.index("--kind") + 1], "hermes")
        self.assertEqual(start[start.index("--pane") + 1], "w1:pNEW")
        self.assertEqual(start[start.index("--") + 1:], ["chat", "--query-file", str(self.prompt.resolve()), "--skills", "wayfinder"])

    def test_focus_flag_moves_focus(self) -> None:
        self.run_script("launch", "--prompt-file", str(self.prompt), "--name", "wf-182", "--focus")
        split = next(c for c in self.calls() if c[:2] == ["pane", "split"])
        self.assertIn("--focus", split)
        self.assertNotIn("--no-focus", split)

    def test_failed_start_keeps_the_pane_and_prints_the_manual_command(self) -> None:
        self.state["start_fails"] = True
        code, out = self.run_script("launch", "--prompt-file", str(self.prompt), "--name", "wf-182")
        self.assertEqual(code, 1)
        self.assertEqual(out["pane"], "w1:pNEW")
        self.assertIn("--query-file", out["manual"])
        self.assertFalse(any(c[:2] == ["pane", "close"] for c in self.calls()))

    def test_refuses_a_non_hermes_agent_after_start(self) -> None:
        self.state["started_kind"] = "claude"
        code, out = self.run_script("launch", "--prompt-file", str(self.prompt), "--name", "wf-182")
        self.assertEqual(code, 1)
        self.assertIn("not Hermes", out["reason"])

    def test_refuses_bad_inputs_before_touching_herdr(self) -> None:
        empty = self.tmp / "empty.md"
        empty.write_text("  \n")
        for args, reason in (
            (["--prompt-file", str(self.prompt), "--name", "Bad Name"], "agent name"),
            (["--prompt-file", str(self.tmp / "missing.md"), "--name", "ok"], "does not exist"),
            (["--prompt-file", str(empty), "--name", "ok"], "empty"),
        ):
            with self.subTest(reason=reason):
                code, out = self.run_script("launch", *args)
                self.assertEqual(code, 1)
                self.assertIn(reason, out["reason"])
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
