"""Owner-only, locked, crash-safe worker records.

One JSON ledger guarded by an flock. Writes go to a fresh 0600 temp file that is
fsynced and atomically renamed. A missing ledger is empty; a corrupt, malformed,
foreign or over-permissive one is refused and never overwritten, so ownership is
never silently reset or defaulted.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import re
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path

from .policy import clean_text

PHASES = frozenset({"layout_pending", "agent_starting", "blocked_startup", "ready", "closing",
                    "cleanup_required", "closed"})
TURN_STATES = frozenset({"submitting", "submitted", "working", "blocked", "settled", "timed_out",
                         "unknown"})
# A Hermes worker's authorized, verified approval mode. ``pending:<mode>`` means a native /yolo
# toward <mode> may have been sent but was not yet observed; only observation resolves it.
MODES = frozenset({"smart", "yolo", "pending:smart", "pending:yolo"})
_REQUIRED = frozenset({
    "id", "owner", "session_key", "task", "preset", "kind", "model", "effort", "agent", "label",
    "cwd", "git", "endpoint", "phase", "workspace_id", "tab_id", "pane_id", "terminal_id",
    "runtime_session", "turn", "created_at", "launch", "process", "mode"})
_OPTIONAL = frozenset({"error", "closed_result"})
_OWNER_KEYS = frozenset({"platform", "chat_id", "thread_id", "user_id"})
_ID_RE = re.compile(r"[0-9a-f]{16}")
_TASK_RE = re.compile(r"[a-z][a-z0-9-]{0,23}")
# Phases whose record must already name a live layout, and the fields that requires.
_NEEDS = {"agent_starting": ("workspace_id", "pane_id"),
          "blocked_startup": ("workspace_id", "pane_id", "terminal_id"),
          "closing": ("pane_id",),
          "ready": ("workspace_id", "pane_id", "terminal_id", "runtime_session")}


class StateError(Exception):
    """Local state is unsafe or unreadable; nothing may proceed."""


class LeaseBusy(Exception):
    """Another request currently holds this lease."""

    def __init__(self, kind: str) -> None:
        super().__init__(kind)
        self.kind = kind


def _is_num(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _hermes_problem(r) -> str | None:
    """Hermes records carry their launch policy, approval mode and, once admitted, the bound
    process."""
    launch, process = r["launch"], r["process"]
    if r["kind"] != "hermes":
        return (None if launch is None and process is None and r["mode"] is None
                else "launch identity on a non-Hermes record")
    if not isinstance(r["mode"], str) or r["mode"] not in MODES:
        return "malformed mode"
    if (not isinstance(launch, dict) or set(launch) != {"provider", "home"}
            or not all(isinstance(v, str) and v for v in launch.values())
            or not os.path.isabs(launch["home"])):
        return "malformed launch"
    if process is None:
        return "ready Hermes record lacks its admitted process" if r["phase"] == "ready" else None
    if (not isinstance(process, dict) or set(process) != {"pid", "argv"}
            or isinstance(process["pid"], bool) or not isinstance(process["pid"], int)
            or process["pid"] <= 0 or not isinstance(process["argv"], list) or not process["argv"]
            or not all(isinstance(v, str) and v for v in process["argv"])):
        return "malformed process"
    return None


def _record_problem(key: str, r) -> str | None:
    """Why a persisted record is unusable, or None when it is well formed."""
    if not isinstance(r, dict):
        return "not an object"
    if not _REQUIRED <= set(r) or set(r) - _REQUIRED - _OPTIONAL:
        return "unexpected or missing fields"
    if r["id"] != key or not _ID_RE.fullmatch(key):
        return "id does not match its key"
    texts = [v for v in r.values() if isinstance(v, str)]
    texts += [v for part in (r["owner"], r["git"], r["launch"]) if isinstance(part, dict)
              for v in part.values()]
    if isinstance(r["process"], dict) and isinstance(r["process"].get("argv"), list):
        texts += r["process"]["argv"]
    if not all(clean_text(v) for v in texts if isinstance(v, str)):
        return "text contains NUL or invalid Unicode"
    owner = r["owner"]
    if (not isinstance(owner, dict) or set(owner) != _OWNER_KEYS
            or not all(isinstance(v, str) for v in owner.values())
            or not all(owner[k] for k in ("platform", "chat_id", "user_id"))):
        return "malformed owner"
    if not isinstance(r["task"], str) or not _TASK_RE.fullmatch(r["task"]):
        return "malformed task"
    if (r["agent"] != f"hg-{r['task'][:20]}-{key[:5]}" or r["label"] != f"hg:{r['task']}:{key}"):
        return "agent name or label is not this worker's"
    if not isinstance(r["kind"], str) or r["kind"] not in ("claude", "hermes"):
        return "unsupported kind"
    for field in ("session_key", "preset", "cwd", "endpoint"):
        if not isinstance(r[field], str) or not r[field]:
            return f"malformed {field}"
    if not (os.path.isabs(r["cwd"]) and os.path.isabs(r["endpoint"])):
        return "cwd and endpoint must be absolute"
    for field in ("model", "effort", "error"):
        if r.get(field) is not None and not isinstance(r[field], str):
            return f"malformed {field}"
    for field in ("workspace_id", "tab_id", "pane_id", "terminal_id", "runtime_session"):
        if r[field] is not None and (not isinstance(r[field], str) or not r[field]):
            return f"malformed {field}"
    git = r["git"]
    if git is not None and (not isinstance(git, dict) or set(git) != {"root", "common_dir", "branch"}
                            or not all(isinstance(v, str) for v in git.values())):
        return "malformed git identity"
    if not isinstance(r["phase"], str) or r["phase"] not in PHASES:
        return "unsupported phase"
    if any(r[field] is None for field in _NEEDS.get(r["phase"], ())):
        return f"phase {r['phase']} lacks its layout identity"
    turn = r["turn"]
    if turn is not None and (
            not isinstance(turn, dict) or set(turn) != {"state", "seq_before", "at"}
            or not isinstance(turn["state"], str) or turn["state"] not in TURN_STATES
            or not _is_num(turn["at"])
            or isinstance(turn["seq_before"], bool) or not isinstance(turn["seq_before"], int)
            or turn["seq_before"] < 0):
        return "malformed turn"
    if not _is_num(r["created_at"]):
        return "malformed created_at"
    if r.get("closed_result") is not None and not isinstance(r["closed_result"], dict):
        return "malformed closed_result"
    return _hermes_problem(r)


def _validate(data) -> dict:
    records = data.get("records") if isinstance(data, dict) else None
    if not isinstance(data, dict) or set(data) != {"version", "records"} \
            or type(data["version"]) is not int or data["version"] != 1 or not isinstance(records, dict):
        raise StateError("ledger has an unexpected shape")
    for key, record in records.items():
        problem = _record_problem(key, record)
        if problem:
            raise StateError(f"ledger record {key!r} is malformed: {problem}")
    return data


def _check_private(path: Path, *, directory: bool) -> None:
    info = os.lstat(path)
    kind_ok = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if not kind_ok:
        raise StateError(f"{path} is not a {'directory' if directory else 'regular file'}")
    if info.st_uid != os.getuid():
        raise StateError(f"{path} is not owned by the current user")
    if info.st_mode & 0o077:
        raise StateError(f"{path} is accessible to other users")


def _open_private(path: Path) -> int:
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    except OSError as exc:
        raise StateError(f"{path} cannot be opened safely: {exc.strerror}") from None
    try:
        _check_private(path, directory=False)
    except (StateError, OSError) as exc:
        os.close(fd)
        raise StateError(str(exc)) from None
    return fd


class Ledger:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.path = root / "ledger.json"

    def _prepare(self) -> None:
        try:
            self.root.parent.mkdir(parents=True, exist_ok=True)
            try:
                self.root.mkdir(mode=0o700)
            except FileExistsError:
                pass
            _check_private(self.root, directory=True)
        except OSError as exc:
            raise StateError(f"state directory {self.root} is unusable: {exc}") from None

    def _read(self) -> dict:
        try:
            _check_private(self.path, directory=False)
        except FileNotFoundError:
            return {"version": 1, "records": {}}
        except OSError as exc:
            raise StateError(f"ledger {self.path} is unusable: {exc}") from None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise StateError(f"ledger {self.path} is unreadable: {exc}") from None
        return _validate(data)

    def _write(self, data: dict) -> None:
        _validate(data)  # never persist a record this module would refuse to read back
        tmp = None
        try:
            fd, tmp = tempfile.mkstemp(prefix=".ledger.", dir=self.root)
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, sort_keys=True)
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.path)
            tmp = None
            dir_fd = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError as exc:
            raise StateError(f"ledger {self.path} could not be written: {exc}") from None
        finally:
            if tmp and os.path.exists(tmp):
                os.unlink(tmp)

    @contextmanager
    def transaction(self):
        """Yield the mutable records mapping; it is persisted when the block exits cleanly."""
        self._prepare()
        fd = _open_private(self.root / "ledger.lock")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            data = self._read()
            before = json.dumps(data, sort_keys=True)
            yield data["records"]
            if json.dumps(data, sort_keys=True) != before:
                self._write(data)
        finally:
            os.close(fd)

    def records(self) -> dict:
        with self.transaction() as records:
            return json.loads(json.dumps(records))

    def update(self, worker_id: str, **fields) -> dict:
        with self.transaction() as records:
            records[worker_id].update(fields)
            return dict(records[worker_id])

    @contextmanager
    def lease(self, kind: str, key: str):
        """Non-blocking exclusive lease: ``worker`` covers one worker's whole lifecycle,
        ``turn`` one runtime session's turns. Always taken outside a ledger transaction."""
        self._prepare()
        digest = hashlib.sha256(key.encode()).hexdigest()[:32]
        # ponytail: one small lock file per worker/session is kept forever; unlinking a
        # lock that another process may hold would break mutual exclusion.
        fd = _open_private(self.root / f"{kind}-{digest}.lock")
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise LeaseBusy(kind) from None
            yield
        finally:
            os.close(fd)
