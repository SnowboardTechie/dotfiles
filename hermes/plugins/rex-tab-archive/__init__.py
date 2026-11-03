"""Archive a Hermes CLI/TUI session when the Rex tab it ran in is closed.

Bryan runs one Rex tab (a Rex *window*) per Hermes conversation and is usually
done with a conversation once he closes its tab. This plugin hides those
sessions from the Desktop/dashboard session list as soon as the tab closes.

The agent runs in the gateway, so ``REX_*`` arrive in the session's bound client
environment (``terminal.client_env_passthrough``), which is where
``post_llm_call`` fires. After each CLI/TUI turn the plugin records which Rex
window holds the session's ``REX_BLOCK`` (in ``rex-tab-archive.json`` under the
Hermes home, so watchers survive a gateway restart) and keeps one daemon thread
per window blocked in ``rex wait -s SESSION WINDOW``.

Only a close Rex reports live archives anything: ``rex wait`` must exit 0 with a
payload naming this window (or its Rex session), and a follow-up
``rex window inspect`` must then say the window is not found. A window that is
already gone when a watcher starts (closed while the gateway was down, or a Rex
server restart) is forgotten without archiving; the ``sessions.auto_archive``
idle sweep covers those.

The archive is the idle sweep's own kind (``auto_archived``): the session stays
in ``state.db``, ``session_search`` still finds it, and it stays resumable;
Hermes un-hides it when a message is sent in it after the gateway has ended it.
Pinned sessions are never archived. A session resumed in a new tab keeps the
``REX_*`` frozen at its creation, so that new tab is not tracked.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Mapping
from pathlib import Path

logger = logging.getLogger(__name__)

# Shell clients' sessions; the gateway stores them as ``local`` and may report either.
_PLATFORMS = frozenset({"cli", "tui", "local"})
_FALLBACK_REX = "/Applications/Rex Beta.app/Contents/Helpers/Rex Server.rex/Contents/MacOS/rex"
_REGISTRY_NAME = "rex-tab-archive.json"
# One ``rex wait`` runs at most this long, so a watcher orphaned by a gateway
# restart exits on its own; the thread then starts the next slice.
_WAIT_SLICE_SECONDS = 3600
_REX_TIMEOUT = 10
_RETRY_SECONDS = 60.0
_MAX_RETRY_SECONDS = 900.0
# Windows not seen in a turn for this long are dropped from the registry.
_KEEP_SECONDS = 30 * 86400

_lock = threading.Lock()
# window_id -> registry path, for windows with a live watcher in this process.
_watching: dict[str, Path] = {}
# (rex_session, rex_block) -> window_id, so steady-state turns cost no Rex calls.
_located: dict[tuple[str, str], str] = {}
# Registry files already re-armed by this process.
_rearmed: set[Path] = set()


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


def _rex_binary(rex: Mapping[str, str]) -> str:
    candidate = Path(rex["REX_BIN_DIR"]) / "rex" if rex.get("REX_BIN_DIR") else None
    if candidate is not None and candidate.is_file():
        return str(candidate)
    return _FALLBACK_REX


def _hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home

        return Path(get_hermes_home())
    except Exception:
        return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")


def _run_rex(rex: Mapping[str, str], *args: str, timeout: float = _REX_TIMEOUT) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    if rex.get("REX_SERVER"):
        env["REX_SERVER"] = rex["REX_SERVER"]
    return subprocess.run(
        [_rex_binary(rex), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        stdin=subprocess.DEVNULL,
        check=False,
    )


def _block_window(rex: Mapping[str, str]) -> str | None:
    done = _run_rex(rex, "block", "inspect", "-s", rex["REX_SESSION"], rex["REX_BLOCK"], "--json")
    if done.returncode != 0:
        return None
    return (json.loads(done.stdout).get("block") or {}).get("window_id") or None


# --- registry ---------------------------------------------------------------


def _load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {"windows": {}}
    if not isinstance(data, dict) or not isinstance(data.get("windows"), dict):
        return {"windows": {}}
    return data


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(data, handle, indent=1, sort_keys=True)
        os.replace(temp, path)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise


def remember(path: Path, window_id: str, rex: Mapping[str, str], session_id: str, db_path: str) -> None:
    """Record that ``session_id`` (stored in ``db_path``) ran in Rex window ``window_id``."""
    now = time.time()
    with _lock:
        data = _load(path)
        windows = data["windows"]
        for stale in [w for w, e in windows.items() if now - float(e.get("seen_at", 0)) > _KEEP_SECONDS]:
            del windows[stale]
        entry = windows.setdefault(window_id, {"sessions": {}})
        entry.update({
            "rex_session": rex["REX_SESSION"],
            "rex_server": rex.get("REX_SERVER", ""),
            "rex_bin_dir": rex.get("REX_BIN_DIR", ""),
            "seen_at": now,
        })
        entry.setdefault("sessions", {})[session_id] = db_path
        _save(path, data)


def _forget(path: Path, window_id: str) -> None:
    with _lock:
        data = _load(path)
        if data["windows"].pop(window_id, None) is not None:
            _save(path, data)


# --- archiving ----------------------------------------------------------------


def archive_session(session_id: str, db_path: str) -> str:
    """Hide one session lineage the way the idle sweep does. Returns the outcome."""
    from hermes_state_registry import acquire, release_or_close

    db = acquire(Path(db_path))
    try:
        row = db.get_session(session_id)
        if not row:
            return "missing"
        if row.get("pinned"):
            return "pinned"
        if row.get("archived"):
            return "already-archived"
        auto_archive = getattr(db, "_auto_archive_lineage", None)
        if callable(auto_archive):
            auto_archive(session_id)
            return "archived"
        # A Hermes without sweep provenance: a plain archive (resume no longer un-hides it).
        db.set_session_archived(session_id, True)
        return "archived-manual"
    finally:
        release_or_close(db)


def _closed_payload(stdout: str, window_id: str, rex_session: str) -> bool:
    for line in stdout.splitlines():
        try:
            payload = json.loads(line)
        except ValueError:
            continue
        if isinstance(payload, dict) and (
            payload.get("window_id") == window_id or payload.get("session_id") == rex_session
        ):
            return True
    return False


def _not_found(done: subprocess.CompletedProcess) -> bool:
    return done.returncode == 3 and "not found" in (done.stderr or "")


def watch_window(path: Path, window_id: str) -> None:
    """Block on ``rex wait`` for one window; archive its sessions on an observed close."""
    failures = 0
    try:
        while True:
            entry = _load(path)["windows"].get(window_id)
            if not entry:
                return
            rex = {
                "REX_SESSION": entry.get("rex_session", ""),
                "REX_SERVER": entry.get("rex_server", ""),
                "REX_BIN_DIR": entry.get("rex_bin_dir", ""),
            }
            try:
                done = _run_rex(
                    rex, "wait", "-s", rex["REX_SESSION"], window_id,
                    "--for", f"{_WAIT_SLICE_SECONDS}s", "--json",
                    timeout=_WAIT_SLICE_SECONDS + 60,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                done = subprocess.CompletedProcess([], 255, "", str(exc))
            if done.returncode == 1 and "timed out" in (done.stderr or ""):
                failures = 0
                continue
            if _not_found(done):
                # Gone before this watcher saw it close: not a close we observed.
                logger.debug("rex-tab-archive %s: already gone, forgetting", window_id)
                _forget(path, window_id)
                return
            if done.returncode == 0 and _closed_payload(done.stdout, window_id, rex["REX_SESSION"]):
                check = _run_rex(rex, "window", "inspect", "-s", rex["REX_SESSION"], window_id, "--json")
                if _not_found(check):
                    entry = _load(path)["windows"].get(window_id) or entry
                    for session_id, db_path in (entry.get("sessions") or {}).items():
                        try:
                            outcome = archive_session(session_id, db_path)
                        except Exception as exc:
                            outcome = f"failed: {exc}"
                        logger.info("rex-tab-archive: tab closed, session %s %s", session_id, outcome)
                    _forget(path, window_id)
                    return
            # Server disconnect or an unexpected answer: retry with backoff.
            failures += 1
            time.sleep(min(_RETRY_SECONDS * failures, _MAX_RETRY_SECONDS))
    except Exception as exc:  # never let a watcher disturb the gateway
        logger.debug("rex-tab-archive watcher for %s failed: %s", window_id, exc)
    finally:
        with _lock:
            _watching.pop(window_id, None)


def _ensure_watcher(path: Path, window_id: str) -> None:
    with _lock:
        if window_id in _watching:
            return
        _watching[window_id] = path
    threading.Thread(
        target=watch_window,
        args=(path, window_id),
        name=f"rex-tab-archive-{window_id[-8:]}",
        daemon=True,
    ).start()


def _rearm(path: Path) -> None:
    """Restart watchers recorded by an earlier gateway process (once per registry)."""
    with _lock:
        if path in _rearmed:
            return
        _rearmed.add(path)
    for window_id in list(_load(path)["windows"]):
        _ensure_watcher(path, window_id)


def _in_gateway() -> bool:
    return "gateway.run" in sys.modules


def _turn_finished(**kwargs) -> None:
    try:
        home = _hermes_home()
        path = home / _REGISTRY_NAME
        if _in_gateway():
            _rearm(path)
        if kwargs.get("platform") not in _PLATFORMS:
            return
        session_id = kwargs.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            return
        rex = _rex_env()
        if rex is None:
            return
        key = (rex["REX_SESSION"], rex["REX_BLOCK"])
        with _lock:
            window_id = _located.get(key)
        if window_id is None:
            window_id = _block_window(rex)
            if window_id is None:
                return
            with _lock:
                _located[key] = window_id
        remember(path, window_id, rex, session_id, str(home / "state.db"))
        _ensure_watcher(path, window_id)
    except Exception as exc:  # never let tab tracking disturb a turn
        logger.debug("rex-tab-archive failed: %s", exc)


def register(ctx) -> None:
    ctx.register_hook("post_llm_call", _turn_finished)
