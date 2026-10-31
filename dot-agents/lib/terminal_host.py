"""Which terminal multiplexer, if any, the calling agent runs inside.

Skills that open panes or tabs for other agents (next-session, handoff
supervision) support Herdr and Rex. Both inject identifying variables into
every pane they start, and nothing else is trusted: not UI focus, not a running
server, not a binary merely being on PATH.

Herdr wins when both are present. Herdr can run inside a Rex pane, and then
its panes inherit that Rex pane's REX_* variables, which name the pane hosting
Herdr rather than the caller. The reverse doesn't happen: Rex panes are started
by the Rex server, which is never itself inside Herdr.

Import from a skill script with:

    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
    import terminal_host

``resolve()`` matters: skills are reached through symlinks into this repo.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class Host:
    kind: str  # "herdr" or "rex"
    pane: str  # Herdr pane ID or Rex block ID of the caller
    session: str  # Rex session ID; empty for Herdr
    binary: str  # executable to run for this host


def _rex_binary(env: Mapping[str, str]) -> str:
    found = shutil.which("rex", path=env.get("PATH"))
    if found:
        return found
    # The Rex app doesn't put rex on PATH; it exports the directory instead.
    bin_dir = env.get("REX_BIN_DIR", "")
    candidate = Path(bin_dir) / "rex" if bin_dir else None
    if candidate and candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    return "rex"


def detect(env: Mapping[str, str] | None = None) -> Host | None:
    """The host this process runs in, or None outside both."""
    env = os.environ if env is None else env
    herdr_pane = env.get("HERDR_PANE_ID", "")
    if env.get("HERDR_ENV") == "1" or herdr_pane:
        binary = env.get("HERDR_BIN_PATH") or env.get("HERDR_BIN") or "herdr"
        return Host("herdr", herdr_pane, "", binary)
    block, session = env.get("REX_BLOCK", ""), env.get("REX_SESSION", "")
    if block and session:
        return Host("rex", block, session, env.get("REX_BIN") or _rex_binary(env))
    return None
