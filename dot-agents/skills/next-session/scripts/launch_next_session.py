#!/usr/bin/env python3
"""Start the next Hermes session in a split beside the calling session.

Works inside Herdr or Rex; ``dot-agents/lib/terminal_host.py`` decides which.
Herdr is checked first because it can run inside a Rex pane.

Herdr: the calling Hermes CLI session is found without trusting UI focus.
Hermes records which TTY each CLI session runs on
(``$HERMES_HOME/terminal-sessions``), and Herdr reports each pane's foreground
processes. The one Hermes pane whose foreground process sits on this session's
TTY is the caller. Anything other than exactly one match is refused.

Rex: every pane exports its own ``REX_BLOCK``, so the caller is that block. It
must still exist on the server. The new pane is a shell with the hermes command
typed into it, as Herdr's agent start does, so a shell remains when Hermes exits.
The launch is confirmed only once a Hermes process is the new pane's foreground.

The new session is ``hermes chat --query-file <prompt>``: on a real TTY the file
seeds the interactive session as its first turn, verbatim. Only the file's path
reaches a shell, quoted. The pane is split to the right (a vertical divider) and
focus stays where it was unless ``--focus`` is given.

Commands:
  whoami                       print this session's id, TTY and Herdr pane
  launch --prompt-file F --name N [--cwd D] [--skills S] [--focus] [--dry-run]

Gateway: when this process has no HERDR_* or REX_* variables (the agent's
commands run under the Hermes gateway, not in the pane), they are adopted from
the one Hermes process on this session's recorded TTY, read exactly from the
kernel. ``host_env_from`` in the output names that TTY and pid.

Environment: HERMES_SESSION_ID (required), HERMES_HOME (default ~/.hermes),
HERDR_BIN (default ``herdr`` on PATH), REX_BIN (default ``rex`` on PATH, then
``$REX_BIN_DIR/rex``). Exit 0 on success, 1 on a refusal or a
failed step, with one JSON object on stdout either way.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import terminal_host  # noqa: E402

NAME = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
TTY_RECORD = re.compile(r"^tty-dev-(tty[A-Za-z0-9]+)$")
MAX_PROMPT_BYTES = 64 * 1024
START_TIMEOUT_MS = 90_000
REX_START_TIMEOUT_S = float(os.environ.get("NEXT_SESSION_REX_START_TIMEOUT", "60"))
SHELL_FLAVOR = "com.superlogical.terminal.shell"


class Refused(Exception):
    """A precondition failed; nothing past the failing step was done."""

    def __init__(self, reason: str, **detail: object) -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


class CannotRun(Refused):
    """The host's binary couldn't be started at all: nothing about panes is known."""


def run_host(exe: str, args: tuple[str, ...], timeout: int) -> subprocess.CompletedProcess:
    try:
        return subprocess.run([exe, *args], capture_output=True, text=True, timeout=timeout)
    except OSError as exc:
        raise CannotRun(f"cannot run {exe}", error=str(exc)) from exc


def herdr(*args: str) -> dict:
    exe = os.environ.get("HERDR_BIN_PATH") or os.environ.get("HERDR_BIN") or "herdr"
    done = run_host(exe, args, 180)
    if done.returncode != 0:
        raise Refused(f"herdr {args[0]} {args[1] if len(args) > 1 else ''} failed".strip(),
                      exit_code=done.returncode, stderr=done.stderr.strip()[-800:], stdout=done.stdout.strip()[-800:])
    try:
        return json.loads(done.stdout)["result"]
    except (ValueError, KeyError) as exc:
        raise Refused(f"herdr {args[0]} returned no JSON result", stdout=done.stdout.strip()[-800:]) from exc


def tty_of(pid: int) -> str:
    done = subprocess.run(["ps", "-o", "tty=", "-p", str(pid)], capture_output=True, text=True, timeout=10)
    return done.stdout.strip() if done.returncode == 0 else ""


def session_tty(session: str, home: Path) -> str:
    """The TTY Hermes recorded for this CLI session. Exactly one record must name it."""
    records = home / "terminal-sessions"
    ttys = []
    for path in sorted(records.glob("tty-dev-*")) if records.is_dir() else []:
        match = TTY_RECORD.match(path.name)
        if not match:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if data.get("session_id") == session:
            ttys.append(match.group(1))
    if len(ttys) != 1:
        raise Refused("this session's TTY is not recorded exactly once", session=session, ttys=ttys, records=str(records))
    return ttys[0]


def tty_processes(tty: str) -> list[tuple[int, int, str]]:
    """(pid, ppid, command) of every process on the TTY."""
    done = subprocess.run(["ps", "-t", tty, "-o", "pid=,ppid=,command="], capture_output=True, text=True, timeout=10)
    procs = []
    for line in done.stdout.splitlines():
        fields = line.split(None, 2)
        if len(fields) >= 2 and fields[0].isdigit() and fields[1].isdigit():
            procs.append((int(fields[0]), int(fields[1]), fields[2] if len(fields) > 2 else ""))
    return procs


def adopt_session_host(session: str, home: Path) -> dict:
    """Take the host variables from this session's own Hermes process.

    The agent's commands may run under the Hermes gateway, whose environment has
    no Herdr or Rex variables even though the chat runs in a pane. Hermes
    records the chat's TTY; the one Hermes process on it (its children aside)
    holds the pane's variables. Only HERDR_* and REX_* are adopted, read exactly
    from the kernel (terminal_host.process_environment), never from ``ps eww``.
    """
    tty = session_tty(session, home)
    hermes = [p for p in tty_processes(tty) if "/.hermes/" in p[2] or Path(p[2].split(" ", 1)[0]).name == "hermes"]
    pids = {pid for pid, _, _ in hermes}
    roots = [pid for pid, ppid, _ in hermes if ppid not in pids]
    if len(roots) != 1:
        raise Refused("no single Hermes process runs on this session's TTY", tty=tty, pids=sorted(roots))
    try:
        env = terminal_host.process_environment(roots[0])
    except OSError as exc:
        raise Refused("cannot read this session's Hermes process environment", tty=tty, pid=roots[0], error=str(exc)) from exc
    adopted = {k: v for k, v in env.items() if k.startswith(terminal_host.HOST_PREFIXES)}
    if terminal_host.detect(adopted) is None:
        raise Refused("not running inside Herdr or Rex: no pane to split", tty=tty, pid=roots[0])
    os.environ.update(adopted)
    return {"tty": tty, "pid": roots[0]}


def caller_pane(session: str, home: Path) -> dict:
    tty = session_tty(session, home)
    matches = []
    for pane in herdr("pane", "list")["panes"]:
        if pane.get("agent") != "hermes":
            continue
        info = herdr("pane", "process-info", "--pane", pane["pane_id"])["process_info"]
        pids = [p["pid"] for p in info.get("foreground_processes", []) if isinstance(p.get("pid"), int)]
        if any(tty_of(pid) == tty for pid in pids):
            matches.append(pane)
    if len(matches) != 1:
        raise Refused("no single Hermes pane runs on this session's TTY", tty=tty, panes=[p["pane_id"] for p in matches])
    pane = matches[0]
    return {"session_id": session, "tty": tty, "pane_id": pane["pane_id"],
            "cwd": pane.get("foreground_cwd") or pane.get("cwd"), "tab_id": pane.get("tab_id")}


def read_prompt(path: str) -> Path:
    prompt = Path(path).expanduser().resolve()
    if not prompt.is_file():
        raise Refused("prompt file does not exist", prompt_file=str(prompt))
    data = prompt.read_bytes()
    if not data.strip():
        raise Refused("prompt file is empty", prompt_file=str(prompt))
    if len(data) > MAX_PROMPT_BYTES:
        raise Refused("prompt file is too large for a pointer prompt", prompt_file=str(prompt), bytes=len(data))
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Refused("prompt file is not UTF-8", prompt_file=str(prompt)) from exc
    return prompt


def launch(args: argparse.Namespace, session: str, home: Path) -> dict:
    if not NAME.match(args.name):
        raise Refused("agent name must match [a-z][a-z0-9_-]{0,31}", name=args.name)
    prompt = read_prompt(args.prompt_file)
    me = caller_pane(session, home)
    cwd = str(Path(args.cwd).expanduser().resolve()) if args.cwd else me["cwd"]
    if not cwd or not Path(cwd).is_dir():
        raise Refused("working directory does not exist", cwd=cwd)
    agent_args = ["chat", "--query-file", str(prompt)]
    if args.skills:
        agent_args += ["--skills", args.skills]
    plan = {"caller_pane": me["pane_id"], "cwd": cwd, "name": args.name, "prompt_file": str(prompt),
            "argv": ["hermes", *agent_args]}
    if args.dry_run:
        return {"launched": False, "dry_run": True, **plan}

    split = herdr("pane", "split", me["pane_id"], "--direction", "right", "--cwd", cwd,
                  "--focus" if args.focus else "--no-focus")
    pane = split["pane"]["pane_id"]
    try:
        herdr("agent", "start", args.name, "--kind", "hermes", "--pane", pane,
              "--timeout", str(START_TIMEOUT_MS), "--", *agent_args)
        agent = herdr("agent", "get", args.name)["agent"]
    except Refused as exc:
        # The split pane is left open: it is visible and the start is the retryable step.
        exc.detail.update(pane=pane, manual=f"hermes chat --query-file {prompt}")
        raise
    if agent.get("agent") != "hermes" or agent.get("pane_id") != pane:
        raise Refused("the started agent is not Hermes in the new pane", pane=pane, agent=agent)
    return {"launched": True, **plan, "pane": pane, "agent_status": agent.get("agent_status")}


def rex(host: terminal_host.Host, *args: str) -> dict:
    done = run_host(host.binary, args, 60)
    if done.returncode != 0:
        raise Refused(f"rex {' '.join(args[:2])} failed", exit_code=done.returncode,
                      stderr=done.stderr.strip()[-800:], stdout=done.stdout.strip()[-800:])
    try:
        value = json.loads(done.stdout)
    except ValueError as exc:
        raise Refused(f"rex {' '.join(args[:2])} returned no JSON", stdout=done.stdout.strip()[-800:]) from exc
    if not isinstance(value, dict):
        raise Refused(f"rex {' '.join(args[:2])} returned no JSON object")
    return value


def rex_process(host: terminal_host.Host, block: str) -> dict:
    return rex(host, "block", "call", "-b", block, "process")


def is_hermes(process: dict | None) -> bool:
    """A Hermes CLI runs as Python out of the Hermes install; its argv0 shows that path."""
    if not process:
        return False
    names = (process.get("name", ""), process.get("argv0", ""), process.get("path", ""))
    return any(Path(n).name == "hermes" or "/.hermes/" in n for n in names if n)


def rex_caller(session: str, host: terminal_host.Host) -> dict:
    try:
        info = rex_process(host, host.pane)
    except CannotRun:
        raise
    except Refused as exc:
        raise Refused("this session's Rex block is not on the connected server", block=host.pane,
                      rex_session=host.session, **exc.detail) from exc
    foreground = info.get("foreground") or {}
    return {"session_id": session, "host": "rex", "pane_id": host.pane, "rex_session": host.session,
            "cwd": foreground.get("cwd") or os.getcwd()}


def rex_launch(args: argparse.Namespace, session: str, host: terminal_host.Host) -> dict:
    if not NAME.match(args.name):
        raise Refused("agent name must match [a-z][a-z0-9_-]{0,31}", name=args.name)
    prompt = read_prompt(args.prompt_file)
    me = rex_caller(session, host)
    cwd = str(Path(args.cwd).expanduser().resolve()) if args.cwd else me["cwd"]
    if not cwd or not Path(cwd).is_dir():
        raise Refused("working directory does not exist", cwd=cwd)
    argv = ["hermes", "chat", "--query-file", str(prompt)]
    if args.skills:
        argv += ["--skills", args.skills]
    plan = {"host": "rex", "caller_pane": me["pane_id"], "cwd": cwd, "name": args.name,
            "prompt_file": str(prompt), "argv": argv}
    if args.dry_run:
        return {"launched": False, "dry_run": True, **plan}

    request = {
        "session_id": host.session,
        "anchor_id": host.pane,
        "direction": "horizontal",
        "side": "after",
        "focus": bool(args.focus),
        "layout": {"block": {"flavor": SHELL_FLAVOR, "label": args.name,
                             "options": {"cwd": cwd, "initial_input": shlex.join(argv) + "\n"}}},
    }
    split = rex(host, "api", "call", "session.new_split", json.dumps(request))
    blocks = [b for b in split.get("block_ids") or [] if b]
    if len(blocks) != 1:
        raise Refused("rex split did not return exactly one new block", result=split)
    pane = blocks[0]
    deadline = time.monotonic() + REX_START_TIMEOUT_S
    foreground: dict = {}
    while True:
        try:
            foreground = rex_process(host, pane).get("foreground") or {}
        except Refused:
            foreground = {}
        if is_hermes(foreground):
            break
        if time.monotonic() >= deadline:
            # The split pane is left open: it is visible and the start is the retryable step.
            raise Refused("Hermes did not start in the new pane", pane=pane, foreground=foreground,
                          manual=shlex.join(argv))
        time.sleep(0.5)
    return {"launched": True, **plan, "pane": pane, "foreground_pid": foreground.get("pid")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start the next Hermes session in a Herdr or Rex split.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("whoami")
    start = sub.add_parser("launch")
    start.add_argument("--prompt-file", required=True)
    start.add_argument("--name", required=True)
    start.add_argument("--cwd")
    start.add_argument("--skills")
    start.add_argument("--focus", action="store_true")
    start.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    session = os.environ.get("HERMES_SESSION_ID", "")
    home = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")
    try:
        if not session:
            raise Refused("HERMES_SESSION_ID is not set: not running inside a Hermes session")
        host = terminal_host.detect()
        adopted = None
        if host is None:
            try:
                adopted = adopt_session_host(session, home)
            except Refused as exc:
                raise Refused("not running inside Herdr or Rex: no pane to split", lookup=exc.reason, **exc.detail) from exc
            host = terminal_host.detect()
        if host is None:
            raise Refused("not running inside Herdr or Rex: no pane to split")
        if host.kind == "rex":
            result = rex_caller(session, host) if args.command == "whoami" else rex_launch(args, session, host)
        else:
            result = caller_pane(session, home) if args.command == "whoami" else launch(args, session, home)
        if adopted is not None:
            result = {**result, "host_env_from": adopted}
    except Refused as exc:
        print(json.dumps({"ok": False, "reason": exc.reason, **exc.detail}, indent=2))
        return 1
    print(json.dumps({"ok": True, **result}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
