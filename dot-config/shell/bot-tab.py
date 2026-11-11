#!/usr/bin/env python3
"""`bot <name>`: show a bot's tab in the `bots` Rex session.

Backs the `bot` shell function in aliases.sh. The bots are the directories under
$PI_BOTS_DIR (default ~/code/pi-bots/bots) holding an AGENTS.md, read on every
call, so a bot made with `pi-bots bot create` works at once and a retired one
(moved to bots/.retired/) is gone.

`bot` alone lists them. `bot <name>`:
  1. makes the bot's tab the active tab of the `bots` session (the server side,
     which every Rex app sees when it opens that session), then
  2. asks one Rex app to show that tab: the app that owns the calling pane
     (Rex's block owner: the app that claimed it, usually the one that opened
     it, which need not be the machine you are typing on), else the only
     connected app. With no owner and several apps, no app is switched. That
     step needs the app's Remote Control setting; if it refuses, the tab is
     still active.

Never opens, closes or restarts a tab: the bot service owns them.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SESSION_LABEL = "bots"
NAME = re.compile(r"^[a-z0-9]+$")
APP_BUNDLES = (
    "/Applications/Rex.app/Contents/Helpers/Rex Server.rex/Contents/MacOS/rex",
    "/Applications/Rex Beta.app/Contents/Helpers/Rex Server.rex/Contents/MacOS/rex",
)


class Failure(Exception):
    pass


def bots_dir(env) -> Path:
    return Path(env.get("PI_BOTS_DIR") or Path(env.get("HOME", "~")).expanduser() / "code" / "pi-bots" / "bots")


def list_bots(directory: Path) -> list[str]:
    if not directory.is_dir():
        return []
    return sorted(
        entry.name
        for entry in directory.iterdir()
        if NAME.match(entry.name) and entry.is_dir() and (entry / "AGENTS.md").is_file()
    )


def rex_program(env) -> str:
    """$PI_BOTS_REX, then the pane's own $REX_BIN_DIR, then PATH, then the app bundle."""
    if env.get("PI_BOTS_REX"):
        return env["PI_BOTS_REX"]
    bin_dir = env.get("REX_BIN_DIR")
    if bin_dir and os.access(Path(bin_dir) / "rex", os.X_OK):
        return str(Path(bin_dir) / "rex")
    found = shutil.which("rex", path=env.get("PATH"))
    if found:
        return found
    for candidate in APP_BUNDLES:
        if os.access(candidate, os.X_OK):
            return candidate
    raise Failure("can't find the rex command (not in $REX_BIN_DIR, on PATH or in the Rex app)")


def rex(program: str, *args: str) -> str:
    try:
        done = subprocess.run(
            [program, "--autostart=false", *args], capture_output=True, text=True, timeout=30
        )
    except subprocess.TimeoutExpired:
        raise Failure(f"rex {' '.join(args[:2])} timed out") from None
    if done.returncode != 0:
        raise Failure(f"rex {' '.join(args[:2])} failed: {done.stderr.strip() or done.returncode}")
    return done.stdout


def rex_json(program: str, *args: str):
    out = rex(program, *args)
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        raise Failure(f"rex {' '.join(args[:2])} printed no JSON") from None


def bots_session(program: str) -> str:
    sessions = rex_json(program, "ls", "--json").get("sessions") or []
    for session in sessions:
        if session.get("label") == SESSION_LABEL:
            return session["session_id"]
    raise Failure(f"there is no {SESSION_LABEL!r} Rex session: is the bot service running?")


def bot_window(program: str, session_id: str, name: str) -> str:
    windows = rex_json(program, "window", "ls", "-s", session_id, "--json").get("windows") or []
    for window in windows:
        if window.get("label") == name:
            return window["window_id"]
    raise Failure(
        f"{name} has no tab in the {SESSION_LABEL!r} session yet; the bot service opens it within a minute"
    )


def viewing_client(program: str, env) -> str | None:
    """The Rex app to switch: the calling pane's owner, else the only connected app, else none."""
    block, session = env.get("REX_BLOCK"), env.get("REX_SESSION")
    if block and session:
        try:
            view = rex_json(program, "api", "call", "session.view", "-s", session)
        except Failure:
            view = {}
        for window in view.get("windows") or []:
            for layer in window.get("layers") or []:
                for entry in layer.get("blocks") or []:
                    if entry.get("block_id") == block and entry.get("owner"):
                        return entry["owner"]
    clients = rex_json(program, "client", "ls", "--json").get("clients") or []
    apps = [
        c["client_id"]
        for c in clients
        if (c.get("info") or {}).get("kind") == "app" and c.get("connection_state", "connected") == "connected"
    ]
    return apps[0] if len(apps) == 1 else None


def main(argv: list[str], env=os.environ) -> int:
    directory = bots_dir(env)
    names = list_bots(directory)
    if len(argv) == 0:
        print("\n".join(names) if names else f"no bots in {directory}")
        return 0 if names else 1
    if len(argv) != 1 or argv[0].startswith("-"):
        print("usage: bot [<name>]", file=sys.stderr)
        return 2
    name = argv[0]
    if name not in names:
        known = ", ".join(names) or "none"
        print(f"bot: no bot {name!r} in {directory} (bots: {known})", file=sys.stderr)
        return 2
    try:
        program = rex_program(env)
        session_id = bots_session(program)
        window_id = bot_window(program, session_id, name)
        rex(program, "window", "focus", "-s", session_id, window_id)
        client = viewing_client(program, env)
        if client is None:
            print(
                f"bot: {name}'s tab is now the active tab of the {SESSION_LABEL!r} session; "
                "open that session in Rex to see it (no single Rex app to switch)",
                file=sys.stderr,
            )
            return 0
        try:
            rex(
                program, "--timeout", "5s", "-C", client, "do", "session.select",
                f"session_id={session_id}", f"window_id={window_id}",
            )
        except Failure as error:
            # The tab is active either way; only the app's view didn't follow (Remote Control off, app hidden).
            print(
                f"bot: {name}'s tab is the active tab of the {SESSION_LABEL!r} session, "
                f"but the Rex app didn't switch to it ({error}). Remote Control in Rex's settings lets it.",
                file=sys.stderr,
            )
    except Failure as error:
        print(f"bot: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
