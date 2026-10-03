"""Hermes worker evidence: the intended launcher's runtime command and native ``/status``.

Checked against Hermes 4ed093c: ``hermes --print-runtime-command`` (hermes_cli/_launchers.py
``runtime_command``) prints ``[python, "-I", "-c", <bootstrap>, *args]``; the managed launcher
Herdr actually runs execs the same interpreter with ``_launcher_script``'s ``-I -c`` bootstrap
for the same source root. Only those two exact POSIX bootstraps of ``hermes_cli.main`` count.
``/status`` in the classic CLI (cli_session_mixin._show_session_status) prints a titled block
of ``Label: value`` lines whose approvals label comes from the live approval engine. In unpatched
4ed093c that label queries a nonexistent ``session_key`` attribute, so it never shows a session's
``/yolo``; only source with the session-id repair (``_STATUS_QUERY``) is supported.
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import unicodedata

from .policy import Refusal

STATUS_TITLE = "Hermes CLI Status"
YOLO_SUFFIX = " (YOLO bypass active)"
SESSION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
_ROOT_LITERAL = re.compile(r"sys\.path\.insert\(0, '([^'\\]+)'\)")


def _print_bootstrap(root: str) -> str:
    """``runtime_command(root)`` for ``hermes_cli.main``, verbatim (POSIX)."""
    return ("import os, sys, runpy; "
            "os.environ.pop('PYTHONHOME', None); os.environ.pop('PYTHONPATH', None); "
            "os.environ.pop('VIRTUAL_ENV', None); "
            f"sys.path.insert(0, {root!r}); "
            "os.environ['HERMES_HOME'] = os.environ.get('HERMES_HOME') or "
            "str(__import__('hermes_constants').get_default_hermes_root()); "
            "import hermes_bootstrap; "
            "runpy.run_module('hermes_cli.main', run_name='__main__', alter_sys=True)")


def _launcher_bootstrap(root: str) -> str:
    """``_launcher_script("hermes", root, ...)``, verbatim: the managed launcher's ``-c`` code."""
    return (
        "import os, re, sys\n"
        "os.environ.pop('PYTHONHOME', None)\n"
        "os.environ.pop('PYTHONPATH', None)\n"
        f"sys.path.insert(0, {root!r})\n"
        "if sys.argv[1:2] == ['--print-runtime-command']: sys.dont_write_bytecode = True\n"
        "from hermes_constants import get_default_hermes_root\n"
        "os.environ['HERMES_HOME'] = os.environ.get('HERMES_HOME') or str(get_default_hermes_root())\n"
        "if sys.argv[1:2] == ['--print-runtime-command']:\n"
        "    from pathlib import Path\n"
        "    from hermes_cli._launchers import print_runtime_command\n"
        f"    print_runtime_command(Path({root!r}), sys.argv[2:])\n"
        "    sys.exit(0)\n"
        "import hermes_bootstrap\n"
        "if sys.argv[1:2] == ['--run-module']:\n"
        "    import runpy\n"
        "    if len(sys.argv) < 3: sys.exit('hermes: --run-module needs a module')\n"
        "    module = sys.argv.pop(2)\n"
        "    del sys.argv[1]\n"
        "    runpy.run_module(module, run_name='__main__', alter_sys=True)\n"
        "    sys.exit(0)\n"
        "from hermes_cli.main import main\n"
        "sys.argv[0] = re.sub(r'(-script\\.pyw|\\.exe)?$', '', sys.argv[0])\n"
        "sys.exit(main())\n"
    )


# What the CLI's sanitizers remove before dispatch (input_sanitize, cli_terminal_input): visible
# bracketed-paste markers and caret/bare terminal reports. ESC forms are control characters.
_SANITIZED = re.compile(r"\^\[|\[20[01]~|0[01]~|<\d+;\d+;\d+[Mm]")


def task_text_problem(text: str) -> str | None:
    """Why the classic CLI might not take this submission as a model task, or None.

    It strips a submission and removes leaked paste/terminal artifacts, possibly splicing what
    surrounds them, then runs a leading ``/`` (command) or ``!`` (shell) locally instead of as a
    turn (cli_tui_mixin._tui_handle_enter, cli_tui_runtime_mixin._tui_process_one_input). With no
    control character and no artifact text there is nothing to remove, so the dispatched text is
    exactly ``text.strip()``.
    """
    if any(unicodedata.category(c) == "Cc" and c not in "\n\t" for c in text):
        return "contains terminal control characters"
    if _SANITIZED.search(text):
        return "contains terminal paste or report markers the Hermes CLI would strip"
    if text.strip()[:1] in ("/", "!"):
        return "would run as a native Hermes slash or shell command, not a task"
    return None
_LABELS = {"Session ID": "session", "Path": "path", "Title": "title", "Model": "model",
           "Reasoning": "reasoning", "Approvals": "approvals", "Context": "context",
           "Created": "created", "Last Activity": "last_activity", "Tokens": "tokens",
           "Agent Running": "agent_running"}
_REQUIRED = frozenset({"session", "path", "model", "approvals", "created", "last_activity",
                       "tokens", "agent_running"})


STATUS_SOURCE = os.path.join("hermes_cli", "cli_session_mixin.py")
# /status must ask the approval engine about exactly the session that native /yolo toggles.
_STATUS_QUERY = ["is_approval_bypass_active_for_session(getattr(self, 'session_id', '') or '')"]
_TOGGLE_KEY = ["self.session_id or 'default'"]
_TOGGLE_CALLS = {"is_session_yolo_enabled(session_key)", "disable_session_yolo(session_key)",
                 "enable_session_yolo(session_key)"}


def _only_method(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    found = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name]
    return found[0] if len(found) == 1 else None


def _calls(fn: ast.FunctionDef, names: set[str]) -> list[str]:
    return [ast.unparse(n) for n in ast.walk(fn) if isinstance(n, ast.Call)
            and getattr(n.func, "id", getattr(n.func, "attr", None)) in names]


def status_source_problem(root: str) -> str | None:
    """Why the runtime source at ``root`` cannot show a session's YOLO bypass in ``/status``.

    Read statically, never imported: ``_show_session_status`` must query the approval engine with
    the CLI session id, and ``_toggle_yolo`` must toggle under that same id.
    """
    try:
        with open(os.path.join(root, STATUS_SOURCE), encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
    except (OSError, ValueError, SyntaxError):
        return "its CLI session source is unreadable"
    status, toggle = _only_method(tree, "_show_session_status"), _only_method(tree, "_toggle_yolo")
    if status is None or toggle is None:
        return "it lacks exactly one native /status and one /yolo implementation"
    if _calls(status, {"is_approval_bypass_active_for_session"}) != _STATUS_QUERY:
        return "its /status does not query the approval engine with the CLI session id"
    keys = [ast.unparse(n.value) for n in ast.walk(toggle) if isinstance(n, ast.Assign)
            and [ast.unparse(t) for t in n.targets] == ["session_key"]]
    if keys != _TOGGLE_KEY or set(_calls(toggle, {c.split("(")[0] for c in _TOGGLE_CALLS})) != _TOGGLE_CALLS:
        return "its /yolo does not toggle the CLI session id"
    return None


def launch_args(preset: dict) -> list[str]:
    """The only arguments a Hermes worker is ever launched with: classic CLI, exact route."""
    return ["--cli", "--provider", preset["provider"], "--model", preset["model"],
            "--reasoning", preset["effort"]]


def preflight(preset: dict, env: dict[str, str]) -> dict:
    """Before any layout: the intended home exists and the intended launcher reports its
    canonical runtime command. Returns the evidence the launched process must match."""
    launcher, home, args = preset["launcher"], preset["home"], launch_args(preset)
    if os.path.realpath(home) != home or not os.path.isdir(home):
        raise Refusal("home_unverified", "the preset's Hermes home is not an existing directory "
                      "reached without symlinks")
    if not os.path.isfile(launcher) or not os.access(launcher, os.X_OK):
        raise Refusal("launcher_unverified", "the preset's Hermes launcher is not an executable file")
    try:
        proc = subprocess.run([launcher, "--print-runtime-command", "--", *args], capture_output=True,
                              text=True, env=env, cwd="/", timeout=30, check=False)
        command = json.loads(proc.stdout) if proc.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, ValueError):
        command = None
    if not (isinstance(command, list) and len(command) == 4 + len(args)
            and all(isinstance(v, str) for v in command) and os.path.isabs(command[0])
            and command[1:3] == ["-I", "-c"] and command[4:] == args
            and len(roots := _ROOT_LITERAL.findall(command[3])) == 1 and os.path.isabs(roots[0])
            and command[3] == _print_bootstrap(roots[0])):
        raise Refusal("launcher_unverified", "the preset's Hermes launcher did not report the canonical "
                      "isolated Hermes runtime command for exactly the preset's arguments")
    problem = status_source_problem(roots[0])
    if problem:
        raise Refusal("runtime_unsupported", f"the preset's Hermes source cannot prove a worker's "
                      f"approval mode: {problem}. It needs the /status session-id repair (see the "
                      "herdr-gateway README, Runtime prerequisite)")
    return {"interpreter": command[0], "root": roots[0], "args": args}


def runtime_matches(expected: dict, argv: list[str]) -> bool:
    """Same interpreter, one of the two canonical bootstraps of the same source root, exactly
    the preset's args. Anything else, including another entrypoint, fails closed."""
    root = expected["root"]
    return (len(argv) == 4 + len(expected["args"]) and argv[0] == expected["interpreter"]
            and argv[1:3] == ["-I", "-c"]
            and argv[3] in (_print_bootstrap(root), _launcher_bootstrap(root))
            and argv[4:] == expected["args"])


def display_home(home: str) -> str:
    """Hermes's display_hermes_home: ``~/`` relative to the user's home, else the absolute path."""
    rel = os.path.relpath(home, os.path.expanduser("~"))
    return home if rel == os.pardir or rel.startswith(os.pardir + os.sep) else "~/" + rel


def status_blocks(text: str) -> list[list[str]]:
    """Every block that starts on an exact title line; incidental mentions are not blocks."""
    lines = [line.strip() for line in text.splitlines()]
    starts = [i for i, line in enumerate(lines) if line == STATUS_TITLE]
    blocks = []
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        block = lines[start:end]
        last = next((i for i, line in enumerate(block) if line.startswith("Agent Running:")), None)
        blocks.append(block if last is None else block[:last + 1])
    return blocks


def fenced_status(text: str, query: str) -> list[str] | None:
    """The one complete block after ``query``'s own echo; None while there is none yet.

    The classic CLI echoes a submitted slash command before running it
    (cli_tui_runtime_mixin._tui_run_slash_input: ``"\\n⚙️  " + input``). ``query`` carries a
    never-sent token, so its echo fences off every earlier report, however identical. The echo
    is matched whole, tolerating only how a terminal may store the emoji (variation selector,
    width padding). A repeated echo or more than one report after it is refused.
    """
    lines = [line.strip() for line in text.splitlines()]
    echo = re.compile("⚙️?\\s+" + re.escape(query))
    fences = [i for i, line in enumerate(lines) if echo.fullmatch(line)]
    if len(fences) > 1:
        raise Refusal("hermes_unverified", "the status query's echo appeared more than once")
    blocks = status_blocks("\n".join(lines[fences[0] + 1:])) if fences else []
    if len(blocks) > 1:
        raise Refusal("hermes_unverified", "more than one status report followed the query")
    return blocks[0] if blocks and blocks[0][-1].startswith("Agent Running:") else None


def parse_status(block: list[str]) -> dict | None:
    """Strictly parse one complete block; anything unknown, repeated or missing is None."""
    if len(block) < 3 or block[1] or not block[-1].startswith("Agent Running:"):
        return None
    fields: dict[str, str] = {}
    for line in block[2:]:
        label, sep, value = line.partition(": ")
        key = _LABELS.get(label)
        if not sep or key is None or key in fields or not value:
            return None
        fields[key] = value
    if not _REQUIRED <= set(fields) or not SESSION_RE.fullmatch(fields["session"]):
        return None
    return fields


def approval_mode(approvals: str) -> str | None:
    """``smart`` or ``yolo`` (smart base approvals with a bypass); anything else is None.

    Admission proved its process started without the frozen ``--yolo``/``HERMES_YOLO_MODE``
    bypass, and approvals ``off`` changes the base label, so for an admitted process the suffix
    can only come from that session's native ``/yolo``.
    """
    return {"smart": "smart", "smart" + YOLO_SUFFIX: "yolo"}.get(approvals)


def status_problem(status: dict, record: dict, *, fresh: bool, mode: str | None = "smart") -> str | None:
    """Why native status does not prove this record's runtime policy, or None.

    ``mode`` is the approval mode the status must show; None accepts either recognized mode.
    """
    launch = record["launch"]
    if status["path"] != display_home(launch["home"]):
        return "the worker is not running in the preset's default-profile home"
    if status["model"] != f"{record['model']} ({launch['provider']})":
        return "the worker's model or provider differs from the preset"
    observed = approval_mode(status["approvals"])
    if observed is None:
        return "the worker's effective approvals are not smart"
    if mode is not None and observed != mode:
        return ("the worker has a YOLO approval bypass active that was not authorized"
                if observed == "yolo" else "the worker's authorized YOLO bypass is no longer active")
    reasoning = status.get("reasoning")
    if reasoning is not None and reasoning.split(" (display: ")[0] != record["effort"]:
        return "the worker's reasoning effort differs from the preset"
    if status["agent_running"] != "No":
        return "the worker reports a running agent turn"
    if fresh and status["tokens"] != "0":
        return "the worker's session is not fresh"
    if not fresh and status["session"] != record["runtime_session"]:
        return "the worker's session differs from the bound session"
    return None
