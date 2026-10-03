"""Behavioral regression for the classic Hermes CLI's native ``/status`` approval label, and for
the repository-owned runtime patch that repairs it (``runtime-patches/cli-status-session.*``).

The REAL ``_show_session_status`` is read statically from the installed Hermes source (pinned by
the patch manifest), extracted with ``ast`` and compiled on its own. Nothing from Hermes is
imported: its printing, translation, status-field and approval-engine dependencies are injected.
The patch is applied only to temporary copies. This is a synthetic source-method regression, not
live runtime, gateway or Matrix evidence.
"""

from __future__ import annotations

import ast
import builtins
import contextlib
import hashlib
import importlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

# The gateway's own status parser, loaded without running the package's registration code.
PLUGIN_DIR = Path(__file__).with_name("plugins") / "herdr-gateway"
_PKG = "herdr_gateway_status_check"
sys.modules[_PKG] = importlib.util.module_from_spec(importlib.util.spec_from_file_location(
    _PKG, PLUGIN_DIR / "__init__.py", submodule_search_locations=[str(PLUGIN_DIR)]))
RUNTIME = importlib.import_module(f"{_PKG}.hermes_runtime")

PATCHES = Path(__file__).with_name("runtime-patches")
MANIFEST = json.loads((PATCHES / "cli-status-session.json").read_text(encoding="utf-8"))
PATCH = PATCHES / MANIFEST["patch"]
HERMES_ROOT = Path(os.path.expanduser("~/.hermes/hermes-agent"))
SOURCE_PATH = MANIFEST["path"]
SESSION = "20261003_101500_abc123"

# English catalog entries the method renders (locales/en.yaml in Hermes 4ed093c).
CATALOG = {
    "cli.session.status_title": "Hermes CLI Status",
    "cli.session.label_reasoning": "Reasoning",
    "cli.session.label_approvals": "Approvals",
    "cli.session.label_context": "Context",
    "cli.session.yolo_bypass_suffix": " (YOLO bypass active)",
    "cli.shared.label_value": "{label}: {value}",
}


def translate(key: str, **values) -> str:
    return CATALOG.get(key, key).format(**values)


class ApprovalEngine:
    """``tools.approval`` as the status method sees it: a frozen process bypass plus the
    per-session ``/yolo`` set, queried by session key."""

    def __init__(self, session_yolo=(), frozen=False) -> None:
        self.session_yolo, self.frozen, self.queried = set(session_yolo), frozen, []

    def is_approval_bypass_active_for_session(self, session_key: str) -> bool:
        self.queried.append(session_key)
        return self.frozen or (bool(session_key) and session_key in self.session_yolo)


class CLI:
    """The attributes the method reads from the classic CLI. Like the real CLI, it has a
    ``session_id`` and no ``session_key`` attribute."""

    session_id = SESSION
    session_start = "2026-10-03 10:15"
    _session_db = None
    agent = None
    model = "example-model"
    provider = "example-provider"
    reasoning_config = {"effort": "high"}
    show_reasoning = False
    _agent_running = False

    def __init__(self) -> None:
        self.printed: list[str] = []

    def _get_status_bar_snapshot(self) -> dict:
        return {}

    def _console_print(self, text: str, **_) -> None:
        self.printed.append(text)


def build_status_fields(session_id, _agent, _meta, *, model=None, provider=None, created_fallback=None,
                        agent_running=False, **_):
    return {"session_id": session_id, "path": "~/.hermes", "title": None, "model": model,
            "provider": provider, "created": created_fallback, "last_activity": created_fallback,
            "tokens": 0, "agent_running": agent_running}


def status_lines(fields: dict, *keys: str) -> list[str]:
    labels = {"session_id": "Session ID", "path": "Path", "model": "Model", "created": "Created",
              "last_activity": "Last Activity", "tokens": "Tokens", "agent_running": "Agent Running"}
    lines = []
    for key in keys:
        value = fields[key]
        if key == "title" and not value:
            continue
        if key == "model":
            value = f"{value} ({fields['provider']})"
        elif key == "agent_running":
            value = "Yes" if value else "No"
        lines.append(f"{labels[key]}: {value}")
    return lines


def status_method(source: str):
    """Compile exactly the source's ``_show_session_status`` with injected dependencies."""
    [node] = [n for n in ast.walk(ast.parse(source))
              if isinstance(n, ast.FunctionDef) and n.name == "_show_session_status"]
    unexpected: list[str] = []
    engine = ApprovalEngine()
    modules = {
        "hermes_cli.status_report": types.SimpleNamespace(build_status_fields=build_status_fields,
                                                          status_lines=status_lines),
        "tools.approval": types.SimpleNamespace(
            is_approval_bypass_active_for_session=lambda key: engine.is_approval_bypass_active_for_session(key)),
        "tools.approval_context": types.SimpleNamespace(_get_approval_mode=lambda: "smart"),
        "hermes_cli.anon_auth": types.SimpleNamespace(free_tier_route=lambda: False),
    }

    def fake_import(name, *_):
        if name not in modules:
            unexpected.append(name)  # the method swallows import errors, so record them
            raise ImportError(name)
        return modules[name]

    namespace = {"__builtins__": dict(vars(builtins), __import__=fake_import),
                 "contextlib": contextlib, "t": translate}
    exec(compile(ast.Module(body=[node], type_ignores=[]), SOURCE_PATH, "exec"), namespace)
    return namespace["_show_session_status"], engine, unexpected


def render(source: str, session_yolo=(), frozen=False) -> tuple[dict, list[str]]:
    """Run the method once; return its ``Label: value`` lines and the sessions it queried."""
    method, engine, unexpected = status_method(source)
    engine.session_yolo, engine.frozen = set(session_yolo), frozen
    cli = CLI()
    method(cli)
    assert not unexpected, unexpected
    [text] = cli.printed
    lines = text.splitlines()
    assert lines[:2] == ["Hermes CLI Status", ""], lines
    return dict(line.split(": ", 1) for line in lines[2:]), engine.queried


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_apply(source: bytes, *flags: str) -> bytes:
    """Apply the repository patch (exact context, no fuzz) to a temporary copy of ``source``."""
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp, SOURCE_PATH)
        target.parent.mkdir(parents=True)
        target.write_bytes(source)
        env = dict(os.environ, GIT_CEILING_DIRECTORIES=os.path.dirname(tmp))
        subprocess.run(["git", "apply", *flags, str(PATCH)], cwd=tmp, env=env, check=True,
                       capture_output=True)
        return target.read_bytes()


@unittest.skipUnless((HERMES_ROOT / SOURCE_PATH).is_file(), "installed Hermes source not present")
class StatusSessionPatchTests(unittest.TestCase):
    """The installed source must be the pinned preimage or the pinned postimage."""

    @classmethod
    def setUpClass(cls) -> None:
        installed = (HERMES_ROOT / SOURCE_PATH).read_bytes()
        digest = sha256(installed)
        if digest == MANIFEST["original_sha256"]:
            cls.original, cls.patched = installed, git_apply(installed)
        elif digest == MANIFEST["patched_sha256"]:
            cls.original, cls.patched = git_apply(installed, "-R"), installed
        else:
            raise AssertionError(f"installed {SOURCE_PATH} ({digest}) is neither the pinned "
                                 "preimage nor the pinned postimage")

    def test_patch_is_exactly_the_pinned_one_line_change(self) -> None:
        self.assertEqual(sha256(PATCH.read_bytes()), MANIFEST["patch_sha256"])
        self.assertEqual(sha256(self.original), MANIFEST["original_sha256"])
        self.assertEqual(sha256(self.patched), MANIFEST["patched_sha256"])
        self.assertEqual(git_apply(self.patched, "-R"), self.original)
        changed = [(a, b) for a, b in zip(self.original.splitlines(), self.patched.splitlines())
                   if a != b]
        self.assertEqual(len(self.original.splitlines()), len(self.patched.splitlines()))
        self.assertEqual([(a.strip(), b.strip()) for a, b in changed], [(
            b'if is_approval_bypass_active_for_session(getattr(self, "session_key", "") or ""):',
            b'if is_approval_bypass_active_for_session(getattr(self, "session_id", "") or ""):')])

    def test_preimage_is_upstream_content_at_the_pinned_base(self) -> None:
        blob = subprocess.run(["git", "-C", str(HERMES_ROOT), "show",
                               f"{MANIFEST['base_commit']}:{SOURCE_PATH}"],
                              capture_output=True, check=True).stdout
        self.assertEqual(sha256(blob), MANIFEST["original_sha256"])
        object_id = subprocess.run(["git", "-C", str(HERMES_ROOT), "rev-parse",
                                    f"{MANIFEST['base_commit']}:{SOURCE_PATH}"],
                                   capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(object_id, MANIFEST["base_blob"])

    def test_repaired_status_reports_the_cli_sessions_own_yolo_toggle(self) -> None:
        source = self.patched.decode("utf-8")
        cases = {
            "smart": ((), False, "smart"),
            "session YOLO on": ({SESSION}, False, "smart (YOLO bypass active)"),
            "another session's YOLO": ({"20261003_090000_ffffff"}, False, "smart"),
            "frozen process bypass": ((), True, "smart (YOLO bypass active)"),
            "frozen with session YOLO": ({SESSION}, True, "smart (YOLO bypass active)"),
        }
        for name, (session_yolo, frozen, approvals) in cases.items():
            with self.subTest(name):
                fields, queried = render(source, session_yolo, frozen)
                self.assertEqual(fields["Session ID"], SESSION)
                self.assertEqual(fields["Approvals"], approvals)
                self.assertEqual(queried, [SESSION], "the approval query names the CLI session")

    def test_unrepaired_status_cannot_see_a_session_toggle(self) -> None:
        source = self.original.decode("utf-8")
        fields, queried = render(source, {SESSION})
        self.assertEqual((fields["Approvals"], queried), ("smart", [""]))


DISPATCH_SOURCES = ("cli.py", os.path.join("hermes_cli", "cli_tui_runtime_mixin.py"))


def slash_dispatch(printed: list[str], hooks: list[dict]) -> dict:
    """Compile exactly the REAL idle-CLI path from a submitted slash line to its handler: the
    slash detector, the echo-then-dispatch input step, ``process_command`` and its table."""
    trees = [ast.parse((HERMES_ROOT / path).read_text(encoding="utf-8")) for path in DISPATCH_SOURCES]

    def only(name: str) -> ast.stmt:
        [node] = [n for tree in trees for n in ast.walk(tree)
                  if (isinstance(n, ast.FunctionDef) and n.name == name)
                  or (isinstance(n, ast.AnnAssign) and ast.unparse(n.target) == name)]
        return node

    modules = {
        "cli": types.SimpleNamespace(_cprint=printed.append),
        "hermes_cli.commands": types.SimpleNamespace(
            resolve_command=lambda word: types.SimpleNamespace(name=word) if word == "status" else None),
        "hermes_cli.observability.shared_metrics_events": types.SimpleNamespace(
            record_slash_command=lambda **_: None),
        "hermes_cli.plugins": types.SimpleNamespace(fire_pre_command_hook=lambda **kw: hooks.append(kw)),
    }
    namespace = {"__builtins__": dict(vars(builtins), __import__=lambda name, *_: modules[name]),
                 "t": translate}
    body = [only(name) for name in ("_looks_like_slash_command", "_slash_args", "_SLASH_DISPATCH",
                                    "_slash_handler", "process_command", "_tui_run_slash_input")]
    exec(compile(ast.Module(body=body, type_ignores=[]), "cli", "exec"), namespace)
    return namespace


@unittest.skipUnless(all((HERMES_ROOT / p).is_file() for p in DISPATCH_SOURCES),
                     "installed Hermes source not present")
class TokenedStatusDispatchTests(unittest.TestCase):
    """The gateway sends ``/status <token>`` and accepts only the report after that input's echo."""

    def test_tokened_status_is_native_status_echoed_before_its_report(self) -> None:
        printed: list[str] = []
        hooks: list[dict] = []
        real = slash_dispatch(printed, hooks)
        report = ["Hermes CLI Status", "", f"Session ID: {SESSION}", "Approvals: smart",
                  "Agent Running: No"]

        class IdleCLI:
            _SLASH_DISPATCH = real["_SLASH_DISPATCH"]
            _slash_handler = real["_slash_handler"]
            process_command = real["process_command"]
            _tui_run_slash_input = real["_tui_run_slash_input"]
            _slash_metrics_surface = "cli"
            _pending_agent_seed = None
            session_id = SESSION

            def __init__(self) -> None:
                self.status_calls: list[tuple] = []

            def _show_session_status(self, *args) -> None:
                self.status_calls.append(args)
                printed.extend(report)  # ChatConsole paints each rendered line via _cprint

        query = "/status " + "5e" * 16
        self.assertTrue(real["_looks_like_slash_command"](query))
        cli = IdleCLI()
        self.assertIsNone(cli._tui_run_slash_input(query), "no agent seed, so no model turn")
        self.assertEqual(cli.status_calls, [()], "native status ran once, without the token")
        self.assertEqual(hooks[0]["command"], "status")
        self.assertEqual(printed[0], "\n⚙️  " + query, "the whole input is echoed first")
        screen = "".join(line + "\n" for line in printed)
        self.assertEqual(RUNTIME.fenced_status(screen, query), report)
        self.assertIsNone(RUNTIME.fenced_status(screen, "/status " + "6f" * 16))


if __name__ == "__main__":
    unittest.main(verbosity=2)
