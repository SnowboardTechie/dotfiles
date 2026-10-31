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
        # Herdr inside a Rex pane: inherited REX_* must not divert the launch to Rex.
        self.extra_env = {"REX_SESSION": "session:outer", "REX_BLOCK": "block:outer"}

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
        for key in ("HERDR_BIN", "HERDR_BIN_PATH", "REX_BIN", "REX_BIN_DIR"):
            env.pop(key, None)
        env.update({"HERDR_ENV": "1", "HERDR_PANE_ID": "w1:p2", **self.extra_env})
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


FAKE_REX = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import json, os, sys
    path = os.environ["FAKE_STATE"]
    state = json.load(open(path))
    args = sys.argv[1:]
    with open(os.environ["FAKE_LOG"], "a") as log:
        log.write(json.dumps(args) + "\\n")
    def out(value):
        print(json.dumps(value))
        sys.exit(0)
    if args[:3] == ["block", "call", "-b"] and args[4] == "process":
        block = args[3]
        if block not in state["blocks"]:
            print(f'Error: block target "{block}" not found', file=sys.stderr)
            sys.exit(1)
        polls = state.setdefault("polls", {})
        polls[block] = polls.get(block, 0) + 1
        json.dump(state, open(path, "w"))
        sequence = state["blocks"][block]
        out({"foreground": sequence[min(polls[block], len(sequence)) - 1]})
    if args[:3] == ["api", "call", "session.new_split"]:
        out({"anchor_id": json.loads(args[3])["anchor_id"], "block_ids": ["block:new"],
             "split_ids": ["split:1"], "revision": 7})
    sys.exit(9)
    """
)


class RexLaunchTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="next-session-rex-test-"))
        self.bin_dir = self.tmp / "bin"
        self.bin_dir.mkdir()
        self.rex = self.bin_dir / "rex"
        self.rex.write_text(FAKE_REX)
        self.rex.chmod(0o755)
        self.cwd = self.tmp / "work"
        self.cwd.mkdir()
        hermes_fg = {"pid": 42, "name": "python3.14", "argv0": "/Users/me/.hermes/tools/python/bin/python3", "cwd": str(self.cwd)}
        self.state = {"blocks": {
            "block:me": [{"pid": 7, "name": "python3.14", "argv0": "/Users/me/.hermes/tools/python/bin/python3", "cwd": str(self.cwd)}],
            # The new pane shows its shell first, then Hermes.
            "block:new": [{"pid": 40, "name": "zsh", "argv0": "-zsh", "cwd": str(self.cwd)}, hermes_fg],
        }}
        self.prompt = self.tmp / "prompt's file.md"
        self.prompt.write_text("Work the map.\n")
        self.log = self.tmp / "rex.log"

    def run_script(self, *args: str, env_extra: dict | None = None) -> tuple[int, dict]:
        state = self.tmp / "state.json"
        state.write_text(json.dumps(self.state))
        env = {k: v for k, v in os.environ.items() if not k.startswith(("HERDR_", "REX_"))}
        env.update({
            # Not on PATH: found through REX_BIN_DIR, as the Rex app sets it up.
            "PATH": "/usr/bin:/bin",
            "REX_BIN_DIR": str(self.bin_dir),
            "REX_SESSION": "session:s1",
            "REX_BLOCK": "block:me",
            "HERMES_SESSION_ID": SESSION,
            "HERMES_HOME": str(self.tmp / "hermes"),
            "FAKE_STATE": str(state),
            "FAKE_LOG": str(self.log),
            "NEXT_SESSION_REX_START_TIMEOUT": "3",
            **(env_extra or {}),
        })
        done = subprocess.run(["python3", str(SCRIPT), *args], capture_output=True, text=True, env=env, timeout=60)
        return done.returncode, json.loads(done.stdout)

    def calls(self) -> list[list[str]]:
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def split_request(self) -> dict:
        call = next(c for c in self.calls() if c[:3] == ["api", "call", "session.new_split"])
        return json.loads(call[3])

    def test_whoami_is_this_rex_block(self) -> None:
        code, out = self.run_script("whoami")
        self.assertEqual(code, 0, out)
        self.assertEqual((out["host"], out["pane_id"], out["rex_session"]), ("rex", "block:me", "session:s1"))
        self.assertEqual(out["cwd"], str(self.cwd))

    def test_refuses_a_stale_block(self) -> None:
        code, out = self.run_script("whoami", env_extra={"REX_BLOCK": "block:gone"})
        self.assertEqual(code, 1)
        self.assertIn("not on the connected server", out["reason"])

    def test_refuses_outside_both_hosts(self) -> None:
        code, out = self.run_script("whoami", env_extra={"REX_BLOCK": ""})
        self.assertEqual(code, 1)
        self.assertIn("not running inside Herdr or Rex", out["reason"])

    def test_dry_run_splits_nothing(self) -> None:
        code, out = self.run_script("launch", "--prompt-file", str(self.prompt), "--name", "wf-9", "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertFalse(out["launched"])
        self.assertFalse(any(c[:3] == ["api", "call", "session.new_split"] for c in self.calls()))

    def test_launch_splits_right_unfocused_and_waits_for_hermes(self) -> None:
        code, out = self.run_script("launch", "--prompt-file", str(self.prompt), "--name", "wf-9", "--skills", "wayfinder")
        self.assertEqual(code, 0, out)
        self.assertEqual((out["launched"], out["pane"], out["foreground_pid"]), (True, "block:new", 42))
        req = self.split_request()
        self.assertEqual((req["session_id"], req["anchor_id"]), ("session:s1", "block:me"))
        self.assertEqual((req["direction"], req["side"], req["focus"]), ("horizontal", "after", False))
        block = req["layout"]["block"]
        self.assertEqual((block["flavor"], block["label"]), ("com.superlogical.terminal.shell", "wf-9"))
        self.assertEqual(block["options"]["cwd"], str(self.cwd))
        typed = block["options"]["initial_input"]
        self.assertTrue(typed.endswith("\n"))
        import shlex
        self.assertEqual(shlex.split(typed), ["hermes", "chat", "--query-file", str(self.prompt.resolve()), "--skills", "wayfinder"])

    def test_focus_flag(self) -> None:
        self.run_script("launch", "--prompt-file", str(self.prompt), "--name", "wf-9", "--focus")
        self.assertTrue(self.split_request()["focus"])

    def test_cwd_override(self) -> None:
        other = self.tmp / "other"
        other.mkdir()
        self.run_script("launch", "--prompt-file", str(self.prompt), "--name", "wf-9", "--cwd", str(other))
        self.assertEqual(self.split_request()["layout"]["block"]["options"]["cwd"], str(other.resolve()))

    def test_hermes_never_starting_keeps_the_pane_and_prints_the_manual_command(self) -> None:
        self.state["blocks"]["block:new"] = [{"pid": 40, "name": "zsh", "argv0": "-zsh"}]
        code, out = self.run_script("launch", "--prompt-file", str(self.prompt), "--name", "wf-9")
        self.assertEqual(code, 1)
        self.assertEqual(out["pane"], "block:new")
        self.assertIn("--query-file", out["manual"])
        self.assertFalse(any("close" in c for c in self.calls()))

    def test_refuses_bad_inputs_before_splitting(self) -> None:
        code, out = self.run_script("launch", "--prompt-file", str(self.prompt), "--name", "Bad Name")
        self.assertEqual(code, 1)
        self.assertEqual(self.calls(), [])


class TerminalHostTest(unittest.TestCase):
    def setUp(self) -> None:
        import sys
        sys.path.insert(0, str(REPO_ROOT / "dot-agents" / "lib"))
        import terminal_host
        self.th = terminal_host

    def test_herdr_wins_over_inherited_rex_variables(self) -> None:
        host = self.th.detect({"HERDR_ENV": "1", "HERDR_PANE_ID": "w1:p1", "HERDR_BIN_PATH": "/x/herdr",
                               "REX_SESSION": "session:s", "REX_BLOCK": "block:b"})
        self.assertEqual((host.kind, host.pane, host.binary), ("herdr", "w1:p1", "/x/herdr"))

    def test_rex_needs_both_block_and_session(self) -> None:
        self.assertIsNone(self.th.detect({"REX_BLOCK": "block:b", "PATH": ""}))
        host = self.th.detect({"REX_BLOCK": "block:b", "REX_SESSION": "session:s", "REX_BIN": "/r/rex"})
        self.assertEqual((host.kind, host.pane, host.session, host.binary), ("rex", "block:b", "session:s", "/r/rex"))

    def test_nothing(self) -> None:
        self.assertIsNone(self.th.detect({}))


if __name__ == "__main__":
    unittest.main()
