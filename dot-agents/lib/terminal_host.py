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

import ctypes
import ctypes.util
import os
import shutil
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

# The variable families that identify a host. Only these are ever adopted from
# another process's environment.
HOST_PREFIXES = ("HERDR_", "REX_")


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


def process_environment(pid: int) -> dict[str, str]:
    """Another process's environment, read exactly as the kernel holds it.

    Never parse ``ps eww`` for this: it joins variables with spaces, so a value
    containing one (Rex's ``REX_BIN_DIR`` lives under "Application Support" and
    "Rex Server.app") can't be split back reliably. The kernel keeps each
    variable NUL-terminated. Raises OSError when the process can't be read.
    """
    if sys.platform.startswith("linux"):
        raw = Path(f"/proc/{pid}/environ").read_bytes()
        entries = raw.split(b"\0")
    elif sys.platform == "darwin":
        entries = _darwin_environment(pid)
    else:
        raise OSError(f"reading another process's environment is not supported on {sys.platform}")
    env: dict[str, str] = {}
    for entry in entries:
        name, sep, value = entry.decode("utf-8", "surrogateescape").partition("=")
        if sep and name:
            env.setdefault(name, value)
    return env


def _darwin_environment(pid: int) -> list[bytes]:
    # KERN_PROCARGS2: int argc, exec path, NUL padding, argc args, then the
    # environment, each NUL-terminated, ended by an empty string.
    libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
    mib = (ctypes.c_int * 3)(1, 49, pid)  # CTL_KERN, KERN_PROCARGS2
    size = ctypes.c_size_t(0)
    if libc.sysctl(mib, 3, None, ctypes.byref(size), None, 0) != 0:
        raise OSError(ctypes.get_errno(), f"sysctl KERN_PROCARGS2 size for pid {pid}")
    buf = ctypes.create_string_buffer(size.value)
    if libc.sysctl(mib, 3, buf, ctypes.byref(size), None, 0) != 0:
        raise OSError(ctypes.get_errno(), f"sysctl KERN_PROCARGS2 for pid {pid}")
    raw = buf.raw[: size.value]
    if len(raw) < 4:
        raise OSError(f"pid {pid}: truncated process arguments")
    argc = struct.unpack_from("i", raw)[0]
    rest = raw[4:]
    start = rest.find(b"\0")
    if start < 0:
        raise OSError(f"pid {pid}: no exec path in process arguments")
    while start < len(rest) and rest[start] == 0:
        start += 1
    parts = rest[start:].split(b"\0")
    entries = []
    for part in parts[argc:]:
        if not part:
            break
        entries.append(part)
    return entries


if __name__ == "__main__":
    # python3 terminal_host.py <pid>: that process's HERDR_* and REX_* values as
    # JSON, exact even when a value contains spaces. Use it instead of `ps eww`.
    import json

    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        sys.exit("usage: terminal_host.py <pid>")
    found = process_environment(int(sys.argv[1]))
    print(json.dumps({k: v for k, v in sorted(found.items()) if k.startswith(HOST_PREFIXES)}, indent=2))
