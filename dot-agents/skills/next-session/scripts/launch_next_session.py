#!/usr/bin/env python3
"""Start the next Hermes session in a Herdr split beside the calling session.

The calling Hermes CLI session is found without trusting UI focus: Hermes
records which TTY each CLI session runs on (``$HERMES_HOME/terminal-sessions``),
and Herdr reports each pane's foreground processes. The one Hermes pane whose
foreground process sits on this session's TTY is the caller. Anything other
than exactly one match is refused.

The new session is ``hermes chat --query-file <prompt>``: on a real TTY the file
seeds the interactive session as its first turn, verbatim, with nothing
shell-interpreted. The pane is split to the right (a vertical divider) and focus
stays where it was unless ``--focus`` is given.

Commands:
  whoami                       print this session's id, TTY and Herdr pane
  launch --prompt-file F --name N [--cwd D] [--skills S] [--focus] [--dry-run]

Environment: HERMES_SESSION_ID (required), HERMES_HOME (default ~/.hermes),
HERDR_BIN (default ``herdr`` on PATH). Exit 0 on success, 1 on a refusal or a
failed step, with one JSON object on stdout either way.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

NAME = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
TTY_RECORD = re.compile(r"^tty-dev-(tty[A-Za-z0-9]+)$")
MAX_PROMPT_BYTES = 64 * 1024
START_TIMEOUT_MS = 90_000


class Refused(Exception):
    """A precondition failed; nothing past the failing step was done."""

    def __init__(self, reason: str, **detail: object) -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def herdr(*args: str) -> dict:
    exe = os.environ.get("HERDR_BIN") or "herdr"
    done = subprocess.run([exe, *args], capture_output=True, text=True, timeout=180)
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start the next Hermes session in a Herdr split.")
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
        result = caller_pane(session, home) if args.command == "whoami" else launch(args, session, home)
    except Refused as exc:
        print(json.dumps({"ok": False, "reason": exc.reason, **exc.detail}, indent=2))
        return 1
    print(json.dumps({"ok": True, **result}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
