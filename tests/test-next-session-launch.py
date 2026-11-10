#!/usr/bin/env python3
"""Tests for dot-agents/skills/next-session/scripts/launch_next_session.py.

A fake `rex` and a fake `ps` stand in for the real ones, and a temporary
HERMES_HOME holds the TTY records, so nothing here touches a live Rex session.

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
        env = {k: v for k, v in os.environ.items() if not k.startswith(("REX_", "PI_"))}
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

    def test_refuses_outside_rex(self) -> None:
        code, out = self.run_script("whoami", env_extra={"REX_BLOCK": ""})
        self.assertEqual(code, 1)
        self.assertIn("not running inside Rex", out["reason"])

    def test_refuses_without_a_session_id(self) -> None:
        code, out = self.run_script("whoami", env_extra={"HERMES_SESSION_ID": ""})
        self.assertEqual(code, 1)
        self.assertIn("HERMES_SESSION_ID", out["reason"])
        self.assertEqual(self.calls(), [])

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

    def pi_launch(self, *extra: str) -> tuple[int, dict, list[str]]:
        import shlex
        pi_fg = {"pid": 77, "name": "node", "argv0": "pi", "cwd": str(self.cwd)}
        self.state["blocks"]["block:new"] = [{"pid": 40, "name": "zsh", "argv0": "-zsh"}, pi_fg]
        code, out = self.run_script("launch", "--prompt-file", str(self.prompt), "--name", "wf-9", *extra,
                                    env_extra={"HERMES_SESSION_ID": "", "PI_SESSION_ID": "pi-1"})
        typed = self.split_request()["layout"]["block"]["options"]["initial_input"] if code == 0 else ""
        return code, out, shlex.split(typed)

    def test_a_pi_session_launches_pi_with_the_prompt_as_its_first_message(self) -> None:
        code, out, typed = self.pi_launch("--model", "claude-code/claude-opus-5-5", "--thinking", "medium", "--skills", "wayfinder")
        self.assertEqual(code, 0, out)
        self.assertEqual((out["agent"], out["foreground_pid"]), ("pi", 77))
        self.assertEqual(typed, ["pi", "--name", "wf-9", "--model", "claude-code/claude-opus-5-5", "--thinking", "medium",
                                 f"@{self.prompt.resolve()}"])

    def test_pi_seat_selects_the_subscription(self) -> None:
        _, _, typed = self.pi_launch("--seat", "personal")
        self.assertEqual(typed[:2], ["env", f"PI_CLAUDE_CODE_CONFIG_DIR={Path.home() / '.claude-personal'}"])
        self.log.unlink()
        _, _, typed = self.pi_launch("--seat", "work")
        self.assertEqual(typed[:3], ["env", "-u", "PI_CLAUDE_CODE_CONFIG_DIR"])

    def test_pi_waits_for_pi_not_hermes(self) -> None:
        code, out = self.run_script("launch", "--prompt-file", str(self.prompt), "--name", "wf-9",
                                    env_extra={"HERMES_SESSION_ID": "", "PI_SESSION_ID": "pi-1"})
        self.assertEqual(code, 1)
        self.assertIn("Pi did not start", out["reason"])

    def test_hermes_refuses_pi_only_flags(self) -> None:
        code, out = self.run_script("launch", "--prompt-file", str(self.prompt), "--name", "wf-9", "--seat", "personal")
        self.assertEqual(code, 1)
        self.assertIn("only to a Pi session", out["reason"])

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


FAKE_PS_TTY = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import json, os, sys
    state = json.load(open(os.environ["FAKE_STATE"]))
    if "-t" in sys.argv:
        for line in state["tty_procs"].get(sys.argv[sys.argv.index("-t") + 1], []):
            print(line)
    """
)


class GatewayAdoptionTest(unittest.TestCase):
    """The helper runs under the Hermes gateway, with no host variables of its own.

    A real child process stands in for this session's Hermes chat, so its
    environment is read from the kernel exactly as it would be live, including
    a REX_BIN_DIR with spaces in it, as the Rex app sets it.
    """

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="next-session-gw-test-"))
        self.bin_dir = self.tmp / "bin"
        self.bin_dir.mkdir()
        ps = self.bin_dir / "ps"
        ps.write_text(FAKE_PS_TTY)
        ps.chmod(0o755)
        self.rex_dir = self.tmp / "Application Support" / "Rex Server.app" / "Contents" / "MacOS"
        self.rex_dir.mkdir(parents=True)
        rex = self.rex_dir / "rex"
        rex.write_text(FAKE_REX)
        rex.chmod(0o755)
        self.home = self.tmp / "hermes"
        (self.home / "terminal-sessions").mkdir(parents=True)
        (self.home / "terminal-sessions" / "tty-dev-ttys003").write_text(json.dumps({"session_id": SESSION, "cwd": "/", "ts": 1}))
        self.cwd = self.tmp / "work"
        self.cwd.mkdir()
        self.prompt = self.tmp / "prompt.md"
        self.prompt.write_text("Work the map.\n")
        self.log = self.tmp / "rex.log"
        self.children: list[subprocess.Popen] = []
        hermes_fg = {"pid": 42, "name": "python3.14", "argv0": "/Users/me/.hermes/tools/python/bin/python3", "cwd": str(self.cwd)}
        self.state = {"blocks": {"block:me": [hermes_fg], "block:new": [hermes_fg]}, "tty_procs": {}}

    def tearDown(self) -> None:
        for child in self.children:
            child.kill()
            child.wait()

    def chat_process(self, host_env: dict) -> int:
        env = {k: v for k, v in os.environ.items() if not k.startswith("REX_")}
        env.update(host_env)
        child = subprocess.Popen(["python3", "-c", "import time; time.sleep(60)"], env=env)
        self.children.append(child)
        return child.pid

    def rex_env(self) -> dict:
        return {"REX_SESSION": "session:s1", "REX_BLOCK": "block:me", "REX_BIN_DIR": str(self.rex_dir),
                "REX_SERVER": "unix:///Users/me/Library/Application%20Support/rex/server.sock"}

    def on_tty(self, *lines: str) -> None:
        self.state["tty_procs"]["ttys003"] = list(lines)

    def run_script(self, *args: str, env_extra: dict | None = None) -> tuple[int, dict]:
        state = self.tmp / "state.json"
        state.write_text(json.dumps(self.state))
        env = {k: v for k, v in os.environ.items() if not k.startswith("REX_")}
        env.update({"PATH": f"{self.bin_dir}:/usr/bin:/bin", "HERMES_SESSION_ID": SESSION, "HERMES_HOME": str(self.home),
                    "FAKE_STATE": str(state), "FAKE_LOG": str(self.log), "NEXT_SESSION_REX_START_TIMEOUT": "3",
                    **(env_extra or {})})
        done = subprocess.run(["python3", str(SCRIPT), *args], capture_output=True, text=True, env=env, timeout=60)
        return done.returncode, json.loads(done.stdout)

    def test_adopts_rex_variables_with_spaces_from_the_sessions_hermes_process(self) -> None:
        chat = self.chat_process(self.rex_env())
        self.on_tty("  500     1 -zsh", f"{chat:5d}   500 /Users/me/.hermes/tools/python/bin/python3 -I -c import os",
                    f"  777 {chat:5d} /Users/me/.hermes/tools/python/bin/python3 -m some_mcp_server")
        code, out = self.run_script("launch", "--prompt-file", str(self.prompt), "--name", "wf-9")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["host_env_from"], {"tty": "ttys003", "pid": chat})
        self.assertEqual((out["host"], out["caller_pane"], out["pane"]), ("rex", "block:me", "block:new"))
        split = next(c for c in [json.loads(l) for l in self.log.read_text().splitlines()] if c[:3] == ["api", "call", "session.new_split"])
        self.assertEqual(json.loads(split[3])["session_id"], "session:s1")

    def test_refuses_two_hermes_processes_on_the_tty(self) -> None:
        first, second = self.chat_process(self.rex_env()), self.chat_process(self.rex_env())
        self.on_tty(f"{first} 1 /Users/me/.hermes/tools/python/bin/python3", f"{second} 1 /Users/me/.hermes/tools/python/bin/python3")
        code, out = self.run_script("whoami")
        self.assertEqual(code, 1)
        self.assertIn("not running inside Rex", out["reason"])
        self.assertIn("no single Hermes process", out["lookup"])
        self.assertEqual(out["pids"], sorted([first, second]))

    def test_refuses_when_the_hermes_process_is_outside_rex(self) -> None:
        chat = self.chat_process({})
        self.on_tty(f"{chat} 1 /Users/me/.hermes/tools/python/bin/python3")
        code, out = self.run_script("whoami")
        self.assertEqual(code, 1)
        self.assertIn("not running inside Rex", out["reason"])

    def test_refuses_without_a_tty_record(self) -> None:
        code, out = self.run_script("whoami", env_extra={"HERMES_SESSION_ID": "local-missing"})
        self.assertEqual(code, 1)
        self.assertIn("not running inside Rex", out["reason"])
        self.assertIn("TTY", out["lookup"])

    def test_a_missing_host_binary_is_a_refusal_not_a_traceback(self) -> None:
        code, out = self.run_script("whoami", env_extra={**self.rex_env(), "REX_BIN": str(self.tmp / "no" / "rex")})
        self.assertEqual(code, 1)
        self.assertIn("cannot run", out["reason"])
        self.assertIn("No such file", out["error"])


class TerminalHostTest(unittest.TestCase):
    def setUp(self) -> None:
        import sys
        sys.path.insert(0, str(REPO_ROOT / "dot-agents" / "lib"))
        import terminal_host
        self.th = terminal_host

    def test_only_rex_variables_identify_a_host(self) -> None:
        self.assertEqual(self.th.HOST_PREFIXES, ("REX_",))

    def test_rex_needs_both_block_and_session(self) -> None:
        self.assertIsNone(self.th.detect({"REX_BLOCK": "block:b", "PATH": ""}))
        host = self.th.detect({"REX_BLOCK": "block:b", "REX_SESSION": "session:s", "REX_BIN": "/r/rex"})
        self.assertEqual((host.kind, host.pane, host.session, host.binary), ("rex", "block:b", "session:s", "/r/rex"))

    def test_nothing(self) -> None:
        self.assertIsNone(self.th.detect({}))

    def test_cli_prints_host_variables_exactly_even_with_spaces(self) -> None:
        spaced = "/Users/me/Library/Application Support/x/Rex Server.app/Contents/MacOS"
        env = {k: v for k, v in os.environ.items() if not k.startswith("REX_")}
        env.update({"REX_BIN_DIR": spaced, "REX_BLOCK": "block:b", "UNRELATED": "x y"})
        child = subprocess.Popen(["python3", "-c", "import time; time.sleep(60)"], env=env)
        try:
            done = subprocess.run(["python3", str(REPO_ROOT / "dot-agents" / "lib" / "terminal_host.py"), str(child.pid)],
                                  capture_output=True, text=True, timeout=30)
        finally:
            child.kill()
            child.wait()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), {"REX_BIN_DIR": spaced, "REX_BLOCK": "block:b"})


if __name__ == "__main__":
    unittest.main()
