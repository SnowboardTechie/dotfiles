"""Name the Rex tab a Hermes CLI/TUI session runs in after the session's title.

Rex's own agent integration asks the agent to rename its session; Hermes has no
such integration, and Bryan runs one Rex session ("Random", ...) with one tab
per Hermes conversation, so the tab is the useful label. Hermes already
generates a short session title; this plugin copies it onto the tab.

The agent runs in the gateway, so ``REX_*`` are not in ``os.environ``: they
arrive in the session's client environment (``terminal.client_env_passthrough``
in config.yaml) and are bound for the turn, which is where ``post_llm_call``
fires. The values are captured there, then a daemon thread waits for the
model-written title (it is generated in the background and can land after the
first turn ends) and renames the tab.

A tab is renamed only while it still has Rex's generated label
(``Window 1a2b3c4d``) or a label this gateway process wrote itself, so a tab
Bryan named by hand is never overwritten.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import subprocess
import threading
import time
from collections.abc import Mapping
from pathlib import Path

logger = logging.getLogger(__name__)

_PLATFORMS = frozenset({"cli", "tui"})
# Titles Bryan set (/title) or the title model wrote. ``derived`` is an instant
# placeholder cut from the opening message and is never copied to a tab.
_ACCEPTED_SOURCES = frozenset({"user", "llm"})
_GENERATED_LABEL = re.compile(r"Window [0-9a-f]{8}")
_FALLBACK_REX = "/Applications/Rex Beta.app/Contents/Helpers/Rex Server.rex/Contents/MacOS/rex"
_MAX_LABEL = 48
_POLL_SECONDS = 2.0
_WAIT_SECONDS = 90.0
_REX_TIMEOUT = 5

_lock = threading.Lock()
# window_id -> label this process last wrote; lets later titles replace our own.
_written: dict[str, str] = {}
# session_id -> label already applied, so steady-state turns cost no Rex calls.
_applied: dict[str, str] = {}
_pending: set[str] = set()


def _rex_env() -> dict[str, str] | None:
    """The session's REX_* values: the bound client env, else the process env."""
    bound = None
    try:
        from agent.session_client_env import bound_client_env

        bound = bound_client_env()
    except Exception:  # older Hermes without per-session client env
        bound = None
    env: Mapping[str, str] = bound if bound is not None else os.environ
    values = {name: env.get(name, "") for name in ("REX_SESSION", "REX_BLOCK", "REX_BIN_DIR", "REX_SERVER")}
    if not values["REX_SESSION"] or not values["REX_BLOCK"]:
        return None
    return values


def _rex_binary(rex: dict[str, str]) -> str:
    candidate = Path(rex["REX_BIN_DIR"]) / "rex" if rex.get("REX_BIN_DIR") else None
    if candidate is not None and candidate.is_file():
        return str(candidate)
    return _FALLBACK_REX


def _state_db() -> Path:
    try:
        from hermes_constants import get_hermes_home

        return Path(get_hermes_home()) / "state.db"
    except Exception:
        return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes") / "state.db"


def _session_title(session_id: str, db: Path | None = None) -> tuple[str | None, str | None]:
    path = db or _state_db()
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2)
    except sqlite3.Error:
        return None, None
    try:
        row = conn.execute("SELECT title, title_source FROM sessions WHERE id = ?", (session_id,)).fetchone()
    except sqlite3.Error:
        return None, None
    finally:
        conn.close()
    if not row or not row[0]:
        return None, None
    return row[0], row[1]


def tab_label(title: str) -> str:
    label = " ".join(title.split())
    if len(label) > _MAX_LABEL:
        label = label[: _MAX_LABEL - 1].rstrip() + "…"
    return label


def _run_rex(binary: str, rex: dict[str, str], *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    if rex.get("REX_SERVER"):
        env["REX_SERVER"] = rex["REX_SERVER"]
    return subprocess.run(
        [binary, *args],
        capture_output=True,
        text=True,
        timeout=_REX_TIMEOUT,
        env=env,
        stdin=subprocess.DEVNULL,
        check=False,
    )


def _block_window(binary: str, rex: dict[str, str]) -> tuple[str, str] | None:
    """(window_id, current window label) for the session's Rex block."""
    done = _run_rex(binary, rex, "block", "inspect", "-s", rex["REX_SESSION"], rex["REX_BLOCK"], "--json")
    if done.returncode != 0:
        return None
    window_id = (json.loads(done.stdout).get("block") or {}).get("window_id")
    if not window_id:
        return None
    done = _run_rex(binary, rex, "window", "inspect", "-s", rex["REX_SESSION"], window_id, "--json")
    if done.returncode != 0:
        return None
    data = json.loads(done.stdout)
    window = data.get("window") if isinstance(data.get("window"), dict) else data
    return window_id, str(window.get("label") or "")


def may_replace(window_id: str, current: str) -> bool:
    """Only Rex's generated label, an empty one, or a label this process wrote."""
    if not current or _GENERATED_LABEL.fullmatch(current):
        return True
    with _lock:
        return _written.get(window_id) == current


def apply_title(session_id: str, rex: dict[str, str], label: str) -> str:
    """Rename the session's tab to ``label`` when allowed. Returns the outcome."""
    binary = _rex_binary(rex)
    located = _block_window(binary, rex)
    if located is None:
        return "no-window"
    window_id, current = located
    if current == label:
        outcome = "current"
    elif not may_replace(window_id, current):
        outcome = "kept-manual"
    else:
        done = _run_rex(binary, rex, "window", "rename", "-s", rex["REX_SESSION"], window_id, label)
        if done.returncode != 0:
            return "rename-failed"
        with _lock:
            _written[window_id] = label
        outcome = "renamed"
    with _lock:
        _applied[session_id] = label
    return outcome


def _follow_title(session_id: str, rex: dict[str, str], deadline: float) -> None:
    try:
        while True:
            title, source = _session_title(session_id)
            if title and source in _ACCEPTED_SOURCES:
                label = tab_label(title)
                with _lock:
                    already = _applied.get(session_id) == label
                if not already:
                    outcome = apply_title(session_id, rex, label)
                    logger.debug("rex-tab-title %s: %s", session_id, outcome)
                return
            if time.monotonic() >= deadline:
                return
            time.sleep(_POLL_SECONDS)
    except Exception as exc:  # never let tab naming disturb a turn
        logger.debug("rex-tab-title failed for %s: %s", session_id, exc)
    finally:
        with _lock:
            _pending.discard(session_id)


def _turn_finished(**kwargs) -> None:
    if kwargs.get("platform") not in _PLATFORMS:
        return
    session_id = kwargs.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return
    rex = _rex_env()
    if rex is None:
        return
    with _lock:
        if session_id in _pending:
            return
        _pending.add(session_id)
    threading.Thread(
        target=_follow_title,
        args=(session_id, rex, time.monotonic() + _WAIT_SECONDS),
        name=f"rex-tab-title-{session_id[:16]}",
        daemon=True,
    ).start()


def register(ctx) -> None:
    ctx.register_hook("post_llm_call", _turn_finished)
