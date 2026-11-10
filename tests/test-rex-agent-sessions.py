#!/usr/bin/env python3
"""Black-box tests for scripts/rex-agent-sessions.py against a fake rex CLI and fake agent state."""
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOOL = REPO / "scripts/rex-agent-sessions.py"

FAKE_REX = textwrap.dedent('''\
    #!/usr/bin/env python3
    import json, os, sys
    state_path = os.environ["FAKE_REX_STATE"]
    state = json.load(open(state_path))
    args = [a for a in sys.argv[1:] if a != "--autostart=false"]
    def opt(name):
        return args[args.index(name) + 1]
    if not state.get("up", True):
        sys.exit(1)
    if args[0] == "whoami":
        print(json.dumps({"instance_id": state["instance"]}))
    elif args[0] == "ls":
        print(json.dumps({"sessions": [{"session_id": s, "label": s} for s in state["sessions"]]}))
    elif args[:2] == ["block", "ls"]:
        sid = opt("-s")
        print(json.dumps({"blocks": [{"block_id": b, "flavor": "com.superlogical.terminal.shell"}
                                     for b in state["sessions"][sid]]}))
    elif args[:2] == ["block", "call"]:
        block = opt("-b")
        if block not in state["processes"]:
            sys.exit(1)
        print(json.dumps(state["processes"][block]))
    elif args[0] in ("send", "send-key"):
        state.setdefault("sent", []).append([args[0], opt("-b"), args[-1]])
        json.dump(state, open(state_path, "w"))
    else:
        sys.exit(2)
''')


def shell(cwd="/work"):
    return {"foreground": {"pid": 500, "name": "zsh", "cwd": cwd},
            "ancestors": [{"pid": 400, "name": "login"}]}


def agent(pid, name, cwd="/work"):
    return {"foreground": {"pid": pid, "name": name, "cwd": cwd},
            "ancestors": [{"pid": 500, "name": "zsh"}, {"pid": 400, "name": "login"}]}


class RexAgentSessionsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.rex = self.tmp / "rex"
        self.rex.write_text(FAKE_REX)
        self.rex.chmod(0o755)
        self.state = self.tmp / "rex-state.json"
        # Agent registries, keyed by PID, exactly where each agent writes them.
        sessions = self.home / ".claude-personal/sessions"
        sessions.mkdir(parents=True)
        (sessions / "101.json").write_text(json.dumps({"pid": 101, "sessionId": "claude-abc", "cwd": "/repo/a"}))
        hermes = self.home / ".hermes/profiles/sgg/runtime"
        hermes.mkdir(parents=True)
        (hermes / "active_sessions.json").write_text(json.dumps(
            {"entries": [{"pid": 102, "session_id": "local-hermes-1"}]}))
        pi = self.home / ".pi/agent/runtime/rex-agent-sessions"
        pi.mkdir(parents=True)
        (pi / "103.json").write_text(json.dumps({"pid": 103, "sessionFile": "/s/pi one.jsonl", "cwd": "/repo/c"}))
        self.set_rex(instance="old", sessions={"S": ["b1", "b2", "b3", "b4"]}, processes={
            "b1": agent(101, "claude"), "b2": agent(102, "python3.14", "/repo/b"),
            "b3": agent(103, "node"), "b4": shell()})

    def set_rex(self, **state):
        self.state.write_text(json.dumps(state))

    def rex_state(self):
        return json.loads(self.state.read_text())

    def run_tool(self, command):
        env = dict(os.environ, REX_AGENT_SESSIONS_HOME=str(self.home), REX_AGENT_SESSIONS_REX=str(self.rex),
                   FAKE_REX_STATE=str(self.state))
        return subprocess.run([sys.executable, str(TOOL), command], env=env, capture_output=True,
                              text=True, check=True)

    def snapshot(self):
        return json.loads((self.home / ".local/state/rex-agent-sessions/snapshot.json").read_text())

    def restart(self, processes):
        self.set_rex(instance="new", sessions={"S": ["b1", "b2", "b3", "b4"]}, processes=processes)

    def test_snapshot_finds_each_agent_session_by_pid(self):
        self.run_tool("snapshot")
        found = {p["block_id"]: (p["agent"], p["session"]) for p in self.snapshot()["panes"]}
        self.assertEqual(found, {"b1": ("claude", "claude-abc"), "b2": ("hermes", "local-hermes-1"),
                                 "b3": ("pi", "/s/pi one.jsonl")})

    def test_restart_resumes_each_agent_in_its_own_pane(self):
        self.run_tool("snapshot")
        self.restart({b: shell() for b in ["b1", "b2", "b3", "b4"]})
        self.run_tool("restore")
        typed = {b: text for kind, b, text in self.rex_state()["sent"] if kind == "send"}
        self.assertEqual(typed, {
            "b1": "cd -- /repo/a && CLAUDE_CONFIG_DIR=" + str(self.home / ".claude-personal")
                  + " command claude --resume claude-abc",
            "b2": "cd -- /repo/b && command hermes -p sgg --resume local-hermes-1",
            "b3": "cd -- /repo/c && command pi --session '/s/pi one.jsonl'",
        })
        self.assertEqual(sum(1 for kind, *_ in self.rex_state()["sent"] if kind == "send-key"), 3)

    def test_no_restart_types_nothing(self):
        self.run_tool("snapshot")
        self.run_tool("restore")
        self.assertNotIn("sent", self.rex_state())

    def test_busy_pane_is_left_alone_and_retried_once_idle(self):
        self.run_tool("snapshot")
        busy = agent(999, "vim")  # user already started something else in b1
        self.restart({"b1": busy, "b2": shell(), "b3": shell(), "b4": shell()})
        self.run_tool("restore")
        self.assertNotIn("b1", [b for _, b, _ in self.rex_state()["sent"]])
        # The pane later returns to an idle shell: it is resumed then, without repeating others.
        state = self.rex_state()
        state["processes"]["b1"] = shell()
        state["sent"] = []
        self.set_rex(**state)
        self.run_tool("restore")
        self.assertEqual([b for kind, b, _ in self.rex_state()["sent"] if kind == "send"], ["b1"])

    def test_already_resumed_agent_is_not_resumed_twice(self):
        self.run_tool("snapshot")
        self.restart({"b1": agent(101, "claude"), "b2": shell(), "b3": shell(), "b4": shell()})
        self.run_tool("restore")
        self.assertNotIn("b1", [b for _, b, _ in self.rex_state()["sent"]])

    def test_server_down_changes_nothing(self):
        self.run_tool("snapshot")
        before = self.snapshot()
        self.set_rex(up=False)
        self.run_tool("restore")
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
