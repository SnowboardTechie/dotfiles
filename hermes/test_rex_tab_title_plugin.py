from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import stat
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

PLUGIN = Path(__file__).with_name("plugins") / "rex-tab-title" / "__init__.py"
SPEC = importlib.util.spec_from_file_location("rex_tab_title", PLUGIN)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

WINDOW = "window:01a1941b-817e-7d88-850b-255bb146b256"
BLOCK = "block:01a1941b-815f-742e-9d22-7262a13d01e5"
SESSION = "session:01a19384-2fca-7b71-8dd9-a60512bf5a33"

# A stand-in rex: answers block/window inspect from a JSON state file and
# records renames into it, so tests observe exactly what the plugin did.
FAKE_REX = """#!/usr/bin/env python3
import json, sys
state_path = {state!r}
state = json.load(open(state_path))
args = sys.argv[1:]
if args[:2] == ["block", "inspect"]:
    print(json.dumps({{"session_id": state["session"], "block": {{"block_id": args[-2], "window_id": state["window"]}}}}))
elif args[:2] == ["window", "inspect"]:
    print(json.dumps({{"session_id": state["session"], "window_id": state["window"], "label": state["label"]}}))
elif args[:2] == ["window", "rename"]:
    state["label"] = args[-1]
    state["renames"].append(args[-1])
    json.dump(state, open(state_path, "w"))
else:
    sys.exit(2)
"""


class RexTabTitleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(dir=os.environ.get("TMPDIR")))
        self.state = self.tmp / "rex-state.json"
        self.write_state(label="Window 4b2c1e9f")
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        rex = bin_dir / "rex"
        rex.write_text(FAKE_REX.format(state=str(self.state)))
        rex.chmod(rex.stat().st_mode | stat.S_IEXEC)
        self.rex = {"REX_SESSION": SESSION, "REX_BLOCK": BLOCK, "REX_BIN_DIR": str(bin_dir), "REX_SERVER": ""}
        self.db = self.tmp / "state.db"
        conn = sqlite3.connect(self.db)
        conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, title TEXT, title_source TEXT)")
        conn.commit()
        conn.close()
        MODULE._written.clear()
        MODULE._applied.clear()
        MODULE._pending.clear()

    def write_state(self, *, label: str) -> None:
        self.state.write_text(json.dumps({"session": SESSION, "window": WINDOW, "label": label, "renames": []}))

    def read_state(self) -> dict:
        return json.loads(self.state.read_text())

    def set_title(self, session_id: str, title: str | None, source: str | None) -> None:
        conn = sqlite3.connect(self.db)
        conn.execute("INSERT OR REPLACE INTO sessions VALUES (?, ?, ?)", (session_id, title, source))
        conn.commit()
        conn.close()

    def follow(self, session_id: str, wait: float = 0.0) -> None:
        with mock.patch.object(MODULE, "_state_db", return_value=self.db), mock.patch.object(MODULE, "_POLL_SECONDS", 0.01):
            MODULE._follow_title(session_id, self.rex, time.monotonic() + wait)

    def test_generated_label_takes_model_title(self) -> None:
        self.set_title("s1", "Enable tab renaming with Rex", "llm")
        self.follow("s1")
        self.assertEqual(self.read_state()["renames"], ["Enable tab renaming with Rex"])

    def test_manual_label_is_never_overwritten(self) -> None:
        self.write_state(label="hermes renaming tabs")
        self.set_title("s1", "Enable tab renaming with Rex", "llm")
        self.follow("s1")
        self.assertEqual(self.read_state()["renames"], [])
        self.assertEqual(self.read_state()["label"], "hermes renaming tabs")

    def test_instant_title_is_used_when_the_model_title_never_lands(self) -> None:
        self.set_title("s1", "What is the boiling point of water at 5000 feet…", "derived")
        self.follow("s1", wait=0.05)
        self.assertEqual(self.read_state()["renames"], ["What is the boiling point of water at 5000 feet…"])

    def test_waits_for_model_title_after_turn(self) -> None:
        self.set_title("s1", "placeholder", "derived")
        import threading

        def upgrade() -> None:
            time.sleep(0.05)
            self.set_title("s1", "Late model title", "llm")

        threading.Thread(target=upgrade).start()
        self.follow("s1", wait=2.0)
        self.assertEqual(self.read_state()["renames"], ["placeholder", "Late model title"])

    def test_new_session_in_same_tab_replaces_our_own_label(self) -> None:
        self.set_title("s1", "First task", "llm")
        self.follow("s1")
        self.set_title("s2", "Second task", "user")
        self.follow("s2")
        self.assertEqual(self.read_state()["renames"], ["First task", "Second task"])

    def test_label_is_bounded_and_single_line(self) -> None:
        label = MODULE.tab_label("A  very\nlong title " + "x" * 80)
        self.assertLessEqual(len(label), MODULE._MAX_LABEL)
        self.assertNotIn("\n", label)
        self.assertTrue(label.endswith("…"))

    def test_hook_ignores_non_rex_and_non_cli_turns(self) -> None:
        with mock.patch.object(MODULE.threading, "Thread") as thread:
            with mock.patch.object(MODULE, "_rex_env", return_value=self.rex):
                MODULE._turn_finished(platform="matrix", session_id="s1")
            with mock.patch.object(MODULE, "_rex_env", return_value=None):
                MODULE._turn_finished(platform="cli", session_id="s1")
            thread.assert_not_called()
            with mock.patch.object(MODULE, "_rex_env", return_value=self.rex):
                MODULE._turn_finished(platform="cli", session_id="s1")
            thread.assert_called_once()

    def test_register_uses_post_llm_call(self) -> None:
        hooks = []
        ctx = type("Ctx", (), {"register_hook": lambda self, name, cb: hooks.append(name)})()
        MODULE.register(ctx)
        self.assertEqual(hooks, ["post_llm_call"])


if __name__ == "__main__":
    unittest.main()
