"""Regression for the repository-owned runtime patch ``runtime-patches/rex-program-status.*``: the
classic Hermes CLI reports its turn state to Rex with OSC 7501 (Rex's Program Status Protocol).

The installed Hermes source must be the pinned preimage or postimage. The patched
``terminal_notify.py`` is loaded on its own (it has no Hermes imports at module level) and driven with
stub CLI objects; the turn wiring in ``cli_chat_turn_mixin.py`` is checked statically with ``ast``.
The patch is applied only to temporary copies. Live Rex behaviour was verified separately by watching
``rex events`` while a real session ran (working -> blocked/question -> working -> done).
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PATCHES = Path(__file__).with_name("runtime-patches")
MANIFEST = json.loads((PATCHES / "rex-program-status.json").read_text(encoding="utf-8"))
PATCH = PATCHES / MANIFEST["patch"]
HERMES_ROOT = Path(os.path.expanduser("~/.hermes/hermes-agent"))
FILES = {entry["path"]: entry for entry in MANIFEST["files"]}
NOTIFY, TURN = "hermes_cli/terminal_notify.py", "hermes_cli/cli_chat_turn_mixin.py"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_apply(sources: dict[str, bytes], *flags: str) -> dict[str, bytes]:
    """Apply the repository patch (exact context, no fuzz) to temporary copies of ``sources``."""
    with tempfile.TemporaryDirectory() as tmp:
        for path, data in sources.items():
            target = Path(tmp, path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        env = dict(os.environ, GIT_CEILING_DIRECTORIES=os.path.dirname(tmp))
        subprocess.run(["git", "apply", *flags, str(PATCH)], cwd=tmp, env=env, check=True,
                       capture_output=True)
        return {path: Path(tmp, path).read_bytes() for path in sources}


def load_notify(source: bytes):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp, "terminal_notify.py")
        path.write_bytes(source)
        spec = importlib.util.spec_from_file_location("rex_patch_terminal_notify", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


class CLI:
    """Only the attributes the reporter reads; no running app, so it writes to the tty."""

    _app = None
    _terminal_io_broken = False
    _approval_state = _clarify_state = _sudo_state = _connection_state = None
    _last_turn_failed = False


@unittest.skipUnless(all((HERMES_ROOT / p).is_file() for p in FILES), "installed Hermes source not present")
class RexProgramStatusPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        installed = {path: (HERMES_ROOT / path).read_bytes() for path in FILES}
        digests = {path: sha256(data) for path, data in installed.items()}
        if all(digests[p] == FILES[p]["original_sha256"] for p in FILES):
            cls.original, cls.patched = installed, git_apply(installed)
        elif all(digests[p] == FILES[p]["patched_sha256"] for p in FILES):
            cls.original, cls.patched = git_apply(installed, "-R"), installed
        else:
            raise AssertionError(f"installed sources {digests} are neither the pinned preimage nor postimage")
        cls.notify = load_notify(cls.patched[NOTIFY])

    def report(self, cli, *steps, term_program="rex"):
        written: list[str] = []
        env = dict(os.environ, TERM_PROGRAM=term_program)
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(self.notify, "write_tty", written.append):
            for step in steps:
                step(cli)
        return written

    def test_patch_digests_and_preimage_are_pinned(self) -> None:
        self.assertEqual(sha256(PATCH.read_bytes()), MANIFEST["patch_sha256"])
        for path, entry in FILES.items():
            self.assertEqual(sha256(self.original[path]), entry["original_sha256"])
            self.assertEqual(sha256(self.patched[path]), entry["patched_sha256"])
            blob = subprocess.run(["git", "-C", str(HERMES_ROOT), "show", f"{MANIFEST['base_commit']}:{path}"],
                                  capture_output=True, check=True).stdout
            self.assertEqual(sha256(blob), entry["original_sha256"], path)
        self.assertEqual(git_apply(self.patched, "-R"), self.original)

    def test_sequences_follow_the_program_status_protocol(self) -> None:
        n = self.notify
        self.assertEqual(n.rex_status("working"), "\x1b]7501;state=working:app=hermes\x1b\\")
        self.assertEqual(n.rex_status("blocked", "question"),
                         "\x1b]7501;state=blocked:app=hermes:kind=question\x1b\\")
        self.assertEqual(n.rex_status("blocked", "bogus"), "\x1b]7501;state=blocked:app=hermes\x1b\\")
        self.assertEqual(n.rex_status("sleeping"), "")
        self.assertTrue(n.rex_supported({"TERM_PROGRAM": "rex"}))
        self.assertFalse(n.rex_supported({"TERM_PROGRAM": "ghostty", "REX_BLOCK": "block:x"}))

    def test_a_turn_reports_working_blocked_working_done_once_each(self) -> None:
        n, cli = self.notify, CLI()

        def ask(c):
            c._clarify_state = {"q": 1}

        def answer(c):
            c._clarify_state = None

        steps = [lambda c: n.rex_report(c, "working"), n.rex_sync, ask, n.rex_sync, n.rex_sync,
                 answer, n.rex_sync, n.rex_turn_end, n.rex_turn_end]
        self.assertEqual(self.report(cli, *steps), [
            n.rex_status("working"), n.rex_status("blocked", "question"), n.rex_status("working"),
            n.rex_status("done")])

    def test_each_prompt_maps_to_its_kind(self) -> None:
        n = self.notify
        for attr, kind in (("_approval_state", "permission"), ("_clarify_state", "question"),
                           ("_sudo_state", "auth"), ("_connection_state", "auth")):
            with self.subTest(attr):
                cli = CLI()
                setattr(cli, attr, {"open": True})
                self.assertEqual(self.report(cli, n.rex_sync), [n.rex_status("blocked", kind)])

    def test_a_failed_turn_ends_as_error_and_an_idle_session_reports_nothing(self) -> None:
        n = self.notify
        failed = CLI()
        failed._last_turn_failed = True
        self.assertEqual(self.report(failed, lambda c: n.rex_report(c, "working"), n.rex_turn_end),
                         [n.rex_status("working"), n.rex_status("error")])
        self.assertEqual(self.report(CLI(), n.rex_turn_end), [], "no turn reported, nothing to end")

    def test_outside_rex_or_with_a_broken_tty_nothing_is_written(self) -> None:
        n = self.notify
        self.assertEqual(self.report(CLI(), n.rex_sync, n.rex_turn_end, term_program="ghostty"), [])
        broken = CLI()
        broken._terminal_io_broken = True
        self.assertEqual(self.report(broken, n.rex_sync), [])

    def test_chat_reports_at_turn_start_while_waiting_and_in_its_finally(self) -> None:
        tree = ast.parse(self.patched[TURN].decode("utf-8"))
        funcs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        chat = ast.unparse(funcs["chat"])
        self.assertLess(chat.index("rex_report(self, 'working')"), chat.index("agent_thread.start()"))
        [turn_try] = [n for n in ast.walk(funcs["chat"]) if isinstance(n, ast.Try)
                      and "agent_thread.start()" in ast.unparse(n.body[0] if len(n.body) == 1 else n)
                      and any("_chat_release_turn_audio" in ast.unparse(s) for s in n.finalbody)]
        self.assertIn("rex_turn_end(self)", [ast.unparse(s) for s in turn_try.finalbody])
        [handler] = [h for h in ast.walk(funcs["_chat_monitor_agent_thread"])
                     if isinstance(h, ast.ExceptHandler) and h.type is not None
                     and ast.unparse(h.type) == "queue.Empty"]
        self.assertEqual(ast.unparse(handler.body[0]), "rex_sync(self)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
