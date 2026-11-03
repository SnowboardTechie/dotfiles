from __future__ import annotations

import importlib.util
import json
import os
import stat
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

PLUGIN = Path(__file__).with_name("plugins") / "rex-tab-archive" / "__init__.py"
SPEC = importlib.util.spec_from_file_location("rex_tab_archive", PLUGIN)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

WINDOW = "window:01a1941b-817e-7d88-850b-255bb146b256"
BLOCK = "block:01a1941b-815f-742e-9d22-7262a13d01e5"
SESSION = "session:01a19384-2fca-7b71-8dd9-a60512bf5a33"

# A stand-in rex reproducing the real CLI's answers (measured against Rex Beta):
# `wait` on a closed tab exits 0 with {"window_id": ...}; on a missing target it
# exits 3 with "... not found"; a --for timeout exits 1 with "wait timed out".
# The scenario for each `wait` call is popped from the state file's queue.
FAKE_REX = """#!/usr/bin/env python3
import json, sys
state_path = {state!r}
state = json.load(open(state_path))
args = sys.argv[1:]
state["calls"].append(args[:2])
def save():
    json.dump(state, open(state_path, "w"))
if args[:2] == ["block", "inspect"]:
    save()
    print(json.dumps({{"session_id": state["session"], "block": {{"block_id": args[-2], "window_id": state["window"]}}}}))
elif args[:1] == ["wait"]:
    outcome = state["waits"].pop(0) if state["waits"] else "timeout"
    if outcome == "closed":
        state["open"] = False
    save()
    if outcome in ("closed", "closed-still-open"):
        print(json.dumps({{"window_id": state["window"]}}))
    elif outcome == "session-closed":
        state["open"] = False
        save()
        print(json.dumps({{"session_id": state["session"]}}))
    elif outcome == "missing":
        sys.stderr.write('Error: block or window target "x" not found\\n'); sys.exit(3)
    elif outcome == "disconnect":
        sys.stderr.write("Error: server disconnected\\n"); sys.exit(4)
    else:
        sys.stderr.write("Error: wait timed out after 1h: context deadline exceeded\\n"); sys.exit(1)
elif args[:2] == ["window", "inspect"]:
    save()
    if state["open"]:
        print(json.dumps({{"window_id": state["window"]}}))
    else:
        sys.stderr.write('Error: window target "x" not found\\n'); sys.exit(3)
else:
    save()
    sys.exit(2)
"""


class RexTabArchiveTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(dir=os.environ.get("TMPDIR")))
        self.state = self.tmp / "rex-state.json"
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        rex = bin_dir / "rex"
        rex.write_text(FAKE_REX.format(state=str(self.state)))
        rex.chmod(rex.stat().st_mode | stat.S_IEXEC)
        self.rex = {"REX_SESSION": SESSION, "REX_BLOCK": BLOCK, "REX_BIN_DIR": str(bin_dir), "REX_SERVER": ""}
        self.registry = self.tmp / "rex-tab-archive.json"
        self.archived: list[tuple[str, str]] = []
        MODULE._watching.clear()
        MODULE._located.clear()
        MODULE._rearmed.clear()

    def scenario(self, *waits: str, open_: bool = True) -> None:
        self.state.write_text(json.dumps(
            {"session": SESSION, "window": WINDOW, "open": open_, "waits": list(waits), "calls": []}))

    def calls(self) -> list[list[str]]:
        return json.loads(self.state.read_text())["calls"]

    def watch(self) -> None:
        def fake_archive(session_id: str, db_path: str) -> str:
            self.archived.append((session_id, db_path))
            return "archived"

        with mock.patch.object(MODULE, "archive_session", side_effect=fake_archive), \
                mock.patch.object(MODULE, "_RETRY_SECONDS", 0.0):
            MODULE.watch_window(self.registry, WINDOW)

    def test_closing_the_tab_archives_every_session_it_held(self) -> None:
        self.scenario("timeout", "closed")
        MODULE.remember(self.registry, WINDOW, self.rex, "s1", "/db")
        MODULE.remember(self.registry, WINDOW, self.rex, "s2", "/db")
        self.watch()
        self.assertEqual(self.archived, [("s1", "/db"), ("s2", "/db")])
        self.assertEqual(MODULE._load(self.registry)["windows"], {})

    def test_closing_the_whole_rex_session_counts_as_a_close(self) -> None:
        self.scenario("session-closed")
        MODULE.remember(self.registry, WINDOW, self.rex, "s1", "/db")
        self.watch()
        self.assertEqual(self.archived, [("s1", "/db")])

    def test_window_already_gone_is_forgotten_not_archived(self) -> None:
        self.scenario("missing", open_=False)
        MODULE.remember(self.registry, WINDOW, self.rex, "s1", "/db")
        self.watch()
        self.assertEqual(self.archived, [])
        self.assertEqual(MODULE._load(self.registry)["windows"], {})

    def test_server_disconnect_never_archives_and_retries(self) -> None:
        self.scenario("disconnect", "disconnect", "missing", open_=False)
        MODULE.remember(self.registry, WINDOW, self.rex, "s1", "/db")
        self.watch()
        self.assertEqual(self.archived, [])
        self.assertEqual(sum(1 for c in self.calls() if c[:1] == ["wait"]), 3)

    def test_close_payload_without_confirmed_absence_does_not_archive(self) -> None:
        # Rex reported a close but the window still inspects: keep watching.
        self.scenario("closed-still-open", "missing")
        MODULE.remember(self.registry, WINDOW, self.rex, "s1", "/db")
        self.watch()
        self.assertEqual(self.archived, [])
        self.assertIn(["window", "inspect"], self.calls())

    def test_hook_records_window_once_and_starts_one_watcher(self) -> None:
        self.scenario()
        with mock.patch.object(MODULE, "_hermes_home", return_value=self.tmp), \
                mock.patch.object(MODULE, "_rex_env", return_value=self.rex), \
                mock.patch.object(MODULE.threading, "Thread") as thread:
            MODULE._turn_finished(platform="local", session_id="s1")
            MODULE._turn_finished(platform="cli", session_id="s2")
        windows = MODULE._load(self.registry)["windows"]
        self.assertEqual(set(windows[WINDOW]["sessions"]), {"s1", "s2"})
        self.assertEqual(windows[WINDOW]["sessions"]["s1"], str(self.tmp / "state.db"))
        self.assertEqual(sum(1 for c in self.calls() if c == ["block", "inspect"]), 1)
        thread.assert_called_once()

    def test_hook_ignores_non_rex_and_non_cli_turns(self) -> None:
        self.scenario()
        with mock.patch.object(MODULE, "_hermes_home", return_value=self.tmp), \
                mock.patch.object(MODULE.threading, "Thread") as thread:
            with mock.patch.object(MODULE, "_rex_env", return_value=self.rex):
                MODULE._turn_finished(platform="matrix", session_id="s1")
            with mock.patch.object(MODULE, "_rex_env", return_value=None):
                MODULE._turn_finished(platform="cli", session_id="s1")
            thread.assert_not_called()
        self.assertFalse(self.registry.exists())

    def test_gateway_restart_rearms_recorded_windows(self) -> None:
        MODULE.remember(self.registry, WINDOW, self.rex, "s1", "/db")
        with mock.patch.object(MODULE, "_hermes_home", return_value=self.tmp), \
                mock.patch.object(MODULE, "_in_gateway", return_value=True), \
                mock.patch.object(MODULE.threading, "Thread") as thread:
            MODULE._turn_finished(platform="cron", session_id="c1")
            MODULE._turn_finished(platform="cron", session_id="c2")
        thread.assert_called_once()
        self.assertEqual(thread.call_args.kwargs["args"], (self.registry, WINDOW))

    def test_stale_windows_are_dropped(self) -> None:
        MODULE.remember(self.registry, "window:old", self.rex, "s0", "/db")
        data = MODULE._load(self.registry)
        data["windows"]["window:old"]["seen_at"] = 0
        MODULE._save(self.registry, data)
        MODULE.remember(self.registry, WINDOW, self.rex, "s1", "/db")
        self.assertEqual(list(MODULE._load(self.registry)["windows"]), [WINDOW])

    def test_register_uses_post_llm_call(self) -> None:
        hooks = []
        ctx = type("Ctx", (), {"register_hook": lambda self, name, cb: hooks.append(name)})()
        MODULE.register(ctx)
        self.assertEqual(hooks, ["post_llm_call"])


class ArchiveSessionTest(unittest.TestCase):
    """archive_session against a stub SessionDB with the real method names."""

    class FakeDB:
        def __init__(self, row):
            self.row, self.auto, self.manual = row, [], []

        def get_session(self, session_id):
            return self.row

        def _auto_archive_lineage(self, session_id):
            self.auto.append(session_id)
            return True

        def set_session_archived(self, session_id, archived):
            self.manual.append((session_id, archived))
            return True

    def run_archive(self, row, *, drop_auto: bool = False):
        db = self.FakeDB(row)
        if drop_auto:
            setattr(db, "_auto_archive_lineage", None)
        registry = types.ModuleType("hermes_state_registry")
        setattr(registry, "acquire", lambda path: db)
        setattr(registry, "release_or_close", lambda handle: None)
        with mock.patch.dict(sys.modules, {"hermes_state_registry": registry}):
            return MODULE.archive_session("s1", "/db"), db

    def test_open_session_gets_sweep_archive(self) -> None:
        outcome, db = self.run_archive({"id": "s1", "pinned": 0, "archived": 0})
        self.assertEqual((outcome, db.auto, db.manual), ("archived", ["s1"], []))

    def test_pinned_session_is_kept(self) -> None:
        outcome, db = self.run_archive({"id": "s1", "pinned": 1, "archived": 0})
        self.assertEqual((outcome, db.auto), ("pinned", []))

    def test_already_archived_is_left_alone(self) -> None:
        outcome, db = self.run_archive({"id": "s1", "pinned": 0, "archived": 1})
        self.assertEqual((outcome, db.auto), ("already-archived", []))

    def test_falls_back_to_plain_archive(self) -> None:
        outcome, db = self.run_archive({"id": "s1", "pinned": 0, "archived": 0}, drop_auto=True)
        self.assertEqual((outcome, db.manual), ("archived-manual", [("s1", True)]))


if __name__ == "__main__":
    unittest.main()
