#!/usr/bin/env python3
"""Deterministic Herdr lifecycle for visible coding workers."""

from __future__ import annotations

import argparse
from contextlib import nullcontext
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable


class HandoffError(RuntimeError):
    """The visible-worker contract could not be verified."""


class CapacityProbe:
    def __init__(self, *, ok: bool, returncode: int, message: str) -> None:
        self.ok = ok
        self.returncode = returncode
        self.message = message.strip()

    @property
    def percentage(self) -> int | None:
        match = re.search(r"\b([0-9]{1,3})%", self.message)
        return int(match.group(1)) if match else None


class TurnLease:
    """One process-wide Claude prompt at a time across Hermes sessions."""

    def __init__(self, path: Path) -> None:
        expanded = path.expanduser()
        if not expanded.is_absolute():
            raise HandoffError("Claude turn lease path must be absolute")
        self.path = expanded.parent.resolve() / expanded.name
        self.fd: int | None = None

    def __enter__(self) -> "TurnLease":
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        flags = os.O_CREAT | os.O_RDWR
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        self.fd = os.open(self.path, flags, 0o600)
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            os.close(self.fd)
            self.fd = None
            raise HandoffError(
                f"another Claude turn owns the global lease: {self.path}"
            ) from exc
        os.ftruncate(self.fd, 0)
        os.write(self.fd, f"pid={os.getpid()}\n".encode())
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self.fd is None:
            return
        fcntl.flock(self.fd, fcntl.LOCK_UN)
        os.close(self.fd)
        self.fd = None


class StartLease:
    """Exclusive ownership of one identity start or recovery transaction."""

    def __init__(self, identity_path: Path) -> None:
        target = _identity_target(identity_path)
        self.path = target.with_name(f".{target.name}.start.lock")
        self.fd: int | None = None

    def __enter__(self) -> "StartLease":
        if self.path.is_symlink():
            raise HandoffError(f"start lock must not be a symlink: {self.path}")
        flags = os.O_CREAT | os.O_RDWR
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        self.fd = os.open(self.path, flags, 0o600)
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            os.close(self.fd)
            self.fd = None
            raise HandoffError("identity start or recovery is already active") from exc
        os.ftruncate(self.fd, 0)
        os.write(self.fd, f"pid={os.getpid()}\n".encode())
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self.fd is None:
            return
        fcntl.flock(self.fd, fcntl.LOCK_UN)
        os.close(self.fd)
        self.fd = None


def status_is_compatible(text: str) -> bool:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        key, separator, value = line.strip().partition(":")
        if separator:
            fields[key.strip()] = value.strip().lower()
    return (
        fields.get("endpoint_compatible") == "yes"
        and fields.get("private_protocol_compatible") == "yes"
    )


def _run_git(worktree: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(worktree),
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise HandoffError(f"Git identity check failed: {detail}")
    return result.stdout.strip()


def git_worktree_identity(worktree: Path) -> dict[str, str]:
    requested = worktree.expanduser().resolve()
    if not requested.is_dir():
        raise HandoffError(f"worktree does not exist: {requested}")
    root = Path(_run_git(requested, "rev-parse", "--show-toplevel")).resolve()
    common = Path(
        _run_git(requested, "rev-parse", "--path-format=absolute", "--git-common-dir")
    ).resolve()
    branch = _run_git(requested, "branch", "--show-current")
    if not branch:
        raise HandoffError("visible workers require a named Git branch")
    return {"root": str(root), "git_common_dir": str(common), "branch": branch}


def _extract_agent(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        agent = payload["result"]["agent"]
    except (KeyError, TypeError) as exc:
        raise HandoffError("Herdr response omitted result.agent") from exc
    if not isinstance(agent, dict):
        raise HandoffError("Herdr result.agent is not an object")
    return agent


def _extract_agents(payload: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        agents = payload["result"]["agents"]
    except (KeyError, TypeError) as exc:
        raise HandoffError("Herdr response omitted result.agents") from exc
    if not isinstance(agents, list) or not all(isinstance(item, dict) for item in agents):
        raise HandoffError("Herdr result.agents is not a list of objects")
    return agents


def _extract_pane(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        pane = payload["result"]["pane"]
    except (KeyError, TypeError) as exc:
        raise HandoffError("Herdr response omitted result.pane") from exc
    if not isinstance(pane, dict):
        raise HandoffError("Herdr result.pane is not an object")
    return pane


def _extract_panes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        panes = payload["result"]["panes"]
    except (KeyError, TypeError) as exc:
        raise HandoffError("Herdr response omitted result.panes") from exc
    if not isinstance(panes, list) or not all(isinstance(item, dict) for item in panes):
        raise HandoffError("Herdr result.panes is not a list of objects")
    return panes


def _runtime_session_id(agent: dict[str, Any]) -> str:
    session = agent.get("agent_session")
    if not isinstance(session, dict) or not isinstance(session.get("value"), str):
        raise HandoffError("Herdr agent omitted agent_session.value")
    if not session["value"]:
        raise HandoffError("Herdr agent returned an empty runtime session ID")
    return session["value"]


def _state_change_seq(agent: dict[str, Any]) -> int:
    value = agent.get("state_change_seq")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise HandoffError("Herdr agent omitted a valid state_change_seq")
    return value


def make_identity(
    *, agent: dict[str, Any], worktree_identity: dict[str, str]
) -> dict[str, Any]:
    required = ("name", "pane_id", "agent", "cwd")
    missing = [field for field in required if not isinstance(agent.get(field), str) or not agent[field]]
    if missing:
        raise HandoffError(f"Herdr agent omitted identity fields: {', '.join(missing)}")
    if Path(agent["cwd"]).expanduser().resolve() != Path(worktree_identity["root"]):
        raise HandoffError("Herdr agent cwd does not resolve to the Git worktree root")
    return {
        "worker_surface": "herdr",
        "worker_agent_name": agent["name"],
        "worker_pane_id": agent["pane_id"],
        "worker_kind": agent["agent"],
        "worker_runtime_session_id": _runtime_session_id(agent),
        "worker_worktree_identity": worktree_identity,
        "closed": False,
    }


def make_start_record(
    *,
    token: str,
    name: str,
    kind: str,
    caller_pane: str,
    worktree_identity: dict[str, str],
    worker_pane_id: str | None,
) -> dict[str, Any]:
    return {
        "worker_surface": "herdr",
        "worker_agent_name": name,
        "worker_pane_id": worker_pane_id,
        "worker_kind": kind,
        "worker_runtime_session_id": None,
        "worker_worktree_identity": worktree_identity,
        "caller_pane_id": caller_pane,
        "caller_workspace_id": None,
        "caller_tab_id": None,
        "pre_split_pane_ids": [],
        "split_started": False,
        "starting": True,
        "cleanup_required": False,
        "reservation_token": token,
        "closed": False,
    }


def _identity_target(path: Path) -> Path:
    expanded = path.expanduser()
    if not expanded.is_absolute():
        raise HandoffError("identity path must be absolute")
    target = expanded.parent.resolve() / expanded.name
    if target.is_symlink():
        raise HandoffError(f"identity path must not be a symlink: {target}")
    if not target.parent.is_dir():
        raise HandoffError(f"identity parent must already exist: {target.parent}")
    return target


def _reserve_identity(path: Path, value: dict[str, Any]) -> Path:
    target = _identity_target(path)
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.start.", dir=target.parent)
    temporary_path = Path(temporary)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_path, target, follow_symlinks=False)
        except FileExistsError as exc:
            raise HandoffError(f"identity path already exists: {target}") from exc
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return target


def _release_identity_reservation(path: Path, token: str) -> None:
    target = _identity_target(path)
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HandoffError(f"could not verify identity reservation: {exc}") from exc
    if value.get("reservation_token") != token:
        raise HandoffError("identity reservation ownership changed")
    target.unlink()


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    target = _identity_target(path)
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    temporary_path = Path(temporary)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, target)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _load_identity(path: Path) -> dict[str, Any]:
    target = _identity_target(path)
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HandoffError(f"could not read identity record {target}: {exc}") from exc
    if not isinstance(value, dict):
        raise HandoffError("identity record is not an object")
    return value


def validate_identity(
    record: dict[str, Any], agent_payload: dict[str, Any]
) -> dict[str, Any]:
    if record.get("closed") is True:
        raise HandoffError("worker identity is closed and non-resumable")
    worktree = record.get("worker_worktree_identity")
    if not isinstance(worktree, dict) or not isinstance(worktree.get("root"), str):
        raise HandoffError("worker identity omitted structured worktree identity")
    live_worktree = git_worktree_identity(Path(worktree["root"]))
    if live_worktree != worktree:
        raise HandoffError("Git worktree identity changed")
    agent = _extract_agent(agent_payload)
    expected = make_identity(agent=agent, worktree_identity=live_worktree)
    for field in (
        "worker_surface",
        "worker_agent_name",
        "worker_pane_id",
        "worker_kind",
        "worker_runtime_session_id",
        "worker_worktree_identity",
    ):
        if record.get(field) != expected[field]:
            raise HandoffError(f"worker identity mismatch: {field}")
    return agent


def working_claude_names(payload: dict[str, Any], *, excluding: str) -> list[str]:
    names = []
    for agent in _extract_agents(payload):
        if (
            agent.get("agent") == "claude"
            and agent.get("agent_status") == "working"
            and agent.get("name") != excluding
        ):
            names.append(str(agent.get("name")))
    return sorted(names)


def resource_exists_from_result(
    result: subprocess.CompletedProcess[str],
    *,
    not_found_code: str,
    resource_key: str,
) -> bool:
    raw = (result.stdout or result.stderr).strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HandoffError("Herdr resource check returned non-JSON output") from exc
    if not isinstance(payload, dict):
        raise HandoffError("Herdr resource check response is not an object")
    if result.returncode == 0:
        try:
            resource = payload["result"][resource_key]
        except (KeyError, TypeError) as exc:
            raise HandoffError(
                f"Herdr resource check omitted result.{resource_key}"
            ) from exc
        if not isinstance(resource, dict):
            raise HandoffError(f"Herdr result.{resource_key} is not an object")
        return True
    error = payload.get("error")
    code = error.get("code") if isinstance(error, dict) else None
    if code == not_found_code:
        return False
    raise HandoffError(f"Herdr resource check failed with {code or 'unknown_error'}")


class RealHerdr:
    def __init__(self, binary: Path, worktree: Path) -> None:
        self.binary = binary.expanduser().resolve()
        self.worktree = worktree.expanduser().resolve()
        if not self.binary.is_file() or not os.access(self.binary, os.X_OK):
            raise HandoffError(f"HERDR_BIN_PATH is not executable: {self.binary}")

    def _run(
        self,
        args: list[str],
        *,
        timeout_seconds: int = 60,
        allow_failure: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [str(self.binary), *args],
            cwd=str(self.worktree),
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
        if result.returncode != 0 and not allow_failure:
            detail = (result.stderr or result.stdout).strip()
            raise HandoffError(f"Herdr {' '.join(args[:2])} failed: {detail}")
        return result

    def _json(self, args: list[str], *, timeout_seconds: int = 60) -> dict[str, Any]:
        result = self._run(args, timeout_seconds=timeout_seconds)
        try:
            value = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise HandoffError(f"Herdr returned non-JSON output for {' '.join(args[:2])}") from exc
        if not isinstance(value, dict):
            raise HandoffError("Herdr JSON response is not an object")
        return value

    def status(self) -> str:
        return self._run(["status"]).stdout

    def current_pane(self, pane_id: str) -> None:
        self._run(["pane", "current", "--pane", pane_id])

    def split(self, *, pane_id: str, cwd: Path) -> str:
        payload = self._json(
            [
                "pane",
                "split",
                "--pane",
                pane_id,
                "--direction",
                "right",
                "--ratio",
                "0.5",
                "--cwd",
                str(cwd),
                "--no-focus",
            ]
        )
        try:
            pane = payload["result"]["pane"]["pane_id"]
        except (KeyError, TypeError) as exc:
            raise HandoffError("Herdr split response omitted result.pane.pane_id") from exc
        if not isinstance(pane, str) or not pane:
            raise HandoffError("Herdr split returned an empty pane ID")
        return pane

    def start_agent(self, *, name: str, kind: str, pane_id: str, title: str) -> None:
        command = [
            "agent",
            "start",
            name,
            "--kind",
            kind,
            "--pane",
            pane_id,
            "--timeout",
            "300000",
        ]
        if kind == "claude":
            command += [
                "--",
                "--permission-mode",
                "auto",
                "--model",
                "opus",
                "--effort",
                "high",
                "--name",
                title,
            ]
        self._run(command, timeout_seconds=330)

    def get_agent(self, name: str) -> dict[str, Any]:
        return self._json(["agent", "get", name])

    def list_agents(self) -> dict[str, Any]:
        return self._json(["agent", "list"])

    def prompt(self, *, name: str, text: str, timeout_ms: int) -> dict[str, Any]:
        return self._json(
            ["agent", "prompt", name, text, "--wait", "--timeout", str(timeout_ms)],
            timeout_seconds=max(60, timeout_ms // 1000 + 30),
        )

    def read_agent(self, *, name: str, lines: int) -> str:
        return self._run(
            [
                "agent",
                "read",
                name,
                "--source",
                "recent-unwrapped",
                "--lines",
                str(lines),
            ]
        ).stdout

    def send_text(self, *, pane_id: str, text: str) -> None:
        self._run(["pane", "send-text", pane_id, text])

    def send_keys(self, *, name: str, keys: list[str]) -> None:
        self._run(["agent", "send-keys", name, *keys])

    def wait_agent(
        self, *, name: str, after_seq: int, timeout_ms: int
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_ms / 1000
        while True:
            payload = self.get_agent(name)
            agent = _extract_agent(payload)
            if _state_change_seq(agent) > after_seq:
                status = agent.get("agent_status")
                if status in {"idle", "done", "blocked"}:
                    return payload
                if status == "working":
                    remaining_ms = max(1, int((deadline - time.monotonic()) * 1000))
                    self._json(
                        [
                            "agent",
                            "wait",
                            name,
                            "--until",
                            "idle",
                            "--until",
                            "done",
                            "--until",
                            "blocked",
                            "--timeout",
                            str(remaining_ms),
                        ],
                        timeout_seconds=max(60, remaining_ms // 1000 + 30),
                    )
                    final_payload = self.get_agent(name)
                    final = _extract_agent(final_payload)
                    if (
                        _state_change_seq(final) > after_seq
                        and final.get("agent_status") in {"idle", "done", "blocked"}
                    ):
                        return final_payload
            if time.monotonic() >= deadline:
                raise HandoffError("blocked answer produced no newer settled state")
            time.sleep(0.1)

    def get_pane(self, pane_id: str) -> dict[str, Any]:
        return self._json(["pane", "get", pane_id])

    def list_panes(self) -> dict[str, Any]:
        return self._json(["pane", "list"])

    def close_pane(self, pane_id: str) -> None:
        self._run(["pane", "close", pane_id])

    def agent_exists(self, name: str) -> bool:
        return resource_exists_from_result(
            self._run(["agent", "get", name], allow_failure=True),
            not_found_code="agent_not_found",
            resource_key="agent",
        )

    def pane_exists(self, pane_id: str) -> bool:
        return resource_exists_from_result(
            self._run(["pane", "get", pane_id], allow_failure=True),
            not_found_code="pane_not_found",
            resource_key="pane",
        )


class HandoffController:
    def __init__(
        self,
        *,
        herdr: Any,
        capacity_probe: Callable[[bool], CapacityProbe],
        lease_path: Path,
    ) -> None:
        self.herdr = herdr
        self.capacity_probe = capacity_probe
        self.lease_path = lease_path

    def _require_capacity(self) -> CapacityProbe:
        probe = self.capacity_probe(True)
        if not probe.ok or probe.percentage is None:
            raise HandoffError(probe.message or "Claude capacity exhausted or unavailable")
        return probe

    def start(
        self,
        *,
        caller_pane: str,
        worktree: Path,
        identity_path: Path,
        name: str,
        kind: str,
        title: str,
    ) -> dict[str, Any]:
        if kind not in {"claude", "hermes"}:
            raise HandoffError(f"unsupported visible worker kind: {kind}")
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", name):
            raise HandoffError("agent name must match [a-z][a-z0-9_-]{0,31}")
        worktree_identity = git_worktree_identity(worktree)
        reservation_token = secrets.token_hex(16)
        start_record = make_start_record(
            token=reservation_token,
            name=name,
            kind=kind,
            caller_pane=caller_pane,
            worktree_identity=worktree_identity,
            worker_pane_id=None,
        )
        pane_id: str | None = None
        with StartLease(identity_path):
            _reserve_identity(identity_path, start_record)
            try:
                if not status_is_compatible(self.herdr.status()):
                    raise HandoffError("Herdr client/server protocols are not compatible")
                self.herdr.current_pane(caller_pane)
                capacity = self._require_capacity() if kind == "claude" else None
                existing = {
                    agent.get("name")
                    for agent in _extract_agents(self.herdr.list_agents())
                }
                if name in existing:
                    raise HandoffError(f"Herdr agent name already exists: {name}")
                caller = _extract_pane(self.herdr.get_pane(caller_pane))
                if caller.get("pane_id") != caller_pane:
                    raise HandoffError("injected caller pane identity changed")
                caller_workspace = caller.get("workspace_id")
                caller_tab = caller.get("tab_id")
                if not isinstance(caller_workspace, str) or not isinstance(
                    caller_tab, str
                ):
                    raise HandoffError("caller pane omitted workspace or tab identity")
                pre_split_panes = _extract_panes(self.herdr.list_panes())
                pre_split_ids: list[str] = []
                for pane in pre_split_panes:
                    value = pane.get("pane_id")
                    if not isinstance(value, str) or not value:
                        raise HandoffError("pane inventory contains an invalid pane ID")
                    pre_split_ids.append(value)
                if caller_pane not in pre_split_ids:
                    raise HandoffError("caller pane is absent from the pane inventory")
                start_record.update(
                    {
                        "caller_workspace_id": caller_workspace,
                        "caller_tab_id": caller_tab,
                        "pre_split_pane_ids": sorted(pre_split_ids),
                        "split_started": True,
                    }
                )
                _atomic_write_json(identity_path, start_record)
                pane_id = self.herdr.split(
                    pane_id=caller_pane,
                    cwd=Path(worktree_identity["root"]),
                )
                start_record["worker_pane_id"] = pane_id
                start_record["split_started"] = False
                _atomic_write_json(identity_path, start_record)
                self.herdr.start_agent(
                    name=name,
                    kind=kind,
                    pane_id=pane_id,
                    title=title,
                )
                record = make_identity(
                    agent=_extract_agent(self.herdr.get_agent(name)),
                    worktree_identity=worktree_identity,
                )
                if record["worker_pane_id"] != pane_id or record["worker_kind"] != kind:
                    raise HandoffError("started worker does not match requested pane or kind")
                _atomic_write_json(identity_path, record)
            except Exception as exc:
                cleanup_ok = True
                cleanup_errors: list[str] = []
                if pane_id is None and start_record.get("split_started"):
                    cleanup_ok = False
                    cleanup_errors.append("split outcome requires inventory recovery")
                if pane_id is not None:
                    try:
                        self.herdr.close_pane(pane_id)
                    except Exception as cleanup_exc:
                        cleanup_ok = False
                        cleanup_errors.append(str(cleanup_exc))
                    try:
                        agent_exists = self.herdr.agent_exists(name)
                        pane_exists = self.herdr.pane_exists(pane_id)
                        cleanup_ok = cleanup_ok and not agent_exists and not pane_exists
                    except Exception as verify_exc:
                        cleanup_ok = False
                        cleanup_errors.append(str(verify_exc))
                if cleanup_ok:
                    _release_identity_reservation(identity_path, reservation_token)
                else:
                    failed_record = dict(start_record)
                    failed_record.update(
                        {
                            "starting": False,
                            "cleanup_required": True,
                            "error": str(exc),
                            "cleanup_error": "; ".join(cleanup_errors) or None,
                        }
                    )
                    _atomic_write_json(identity_path, failed_record)
                raise
        result = dict(record)
        result["provider_capacity_start"] = capacity.percentage if capacity else None
        return result

    def recover_start(self, *, identity_path: Path) -> dict[str, Any]:
        with StartLease(identity_path):
            record = _load_identity(identity_path)
            if record.get("closed") is True:
                return record
            if record.get("closing"):
                raise HandoffError("closing identity must be resumed with close")
            if not (record.get("starting") or record.get("cleanup_required")):
                raise HandoffError("identity is active and has no start recovery state")
            name = record.get("worker_agent_name")
            kind = record.get("worker_kind")
            pane_value = record.get("worker_pane_id")
            worktree_identity = record.get("worker_worktree_identity")
            if (
                not isinstance(name, str)
                or not name
                or kind not in {"claude", "hermes"}
                or not isinstance(worktree_identity, dict)
                or not isinstance(worktree_identity.get("root"), str)
            ):
                raise HandoffError("start recovery record is incomplete")
            if pane_value is not None and (
                not isinstance(pane_value, str) or not pane_value
            ):
                raise HandoffError("start recovery pane identity is malformed")
            live_worktree = git_worktree_identity(Path(worktree_identity["root"]))
            if live_worktree != worktree_identity:
                raise HandoffError("start recovery Git worktree identity changed")
            if not status_is_compatible(self.herdr.status()):
                raise HandoffError("Herdr client/server protocols are not compatible")

            if pane_value is None and record.get("split_started"):
                pre_split_ids = record.get("pre_split_pane_ids")
                caller_workspace = record.get("caller_workspace_id")
                caller_tab = record.get("caller_tab_id")
                if (
                    not isinstance(pre_split_ids, list)
                    or not all(isinstance(value, str) for value in pre_split_ids)
                    or not isinstance(caller_workspace, str)
                    or not isinstance(caller_tab, str)
                ):
                    raise HandoffError("split recovery inventory is incomplete")
                candidates: list[str] = []
                for pane in _extract_panes(self.herdr.list_panes()):
                    candidate_id = pane.get("pane_id")
                    candidate_cwd = pane.get("cwd")
                    if (
                        isinstance(candidate_id, str)
                        and candidate_id not in pre_split_ids
                        and pane.get("workspace_id") == caller_workspace
                        and pane.get("tab_id") == caller_tab
                        and isinstance(candidate_cwd, str)
                        and Path(candidate_cwd).expanduser().resolve()
                        == Path(worktree_identity["root"])
                    ):
                        candidates.append(candidate_id)
                if len(candidates) > 1:
                    raise HandoffError("split recovery found multiple possible panes")
                if candidates:
                    pane_value = candidates[0]
                    record["worker_pane_id"] = pane_value
                    record["split_started"] = False
                    _atomic_write_json(identity_path, record)

            agent_exists = self.herdr.agent_exists(name)
            pane_exists = (
                self.herdr.pane_exists(pane_value) if pane_value is not None else False
            )
            if agent_exists:
                agent_payload = self.herdr.get_agent(name)
                agent = _extract_agent(agent_payload)
                if (
                    not pane_exists
                    or agent.get("name") != name
                    or agent.get("agent") != kind
                    or agent.get("pane_id") != pane_value
                    or Path(str(agent.get("cwd", ""))).expanduser().resolve()
                    != Path(worktree_identity["root"])
                ):
                    raise HandoffError("live worker does not match start recovery record")
                recovered = make_identity(
                    agent=agent,
                    worktree_identity=worktree_identity,
                )
                _atomic_write_json(identity_path, recovered)
                return recovered

            if pane_exists and pane_value is not None:
                self.herdr.close_pane(pane_value)
            if self.herdr.agent_exists(name) or (
                pane_value is not None and self.herdr.pane_exists(pane_value)
            ):
                raise HandoffError("start recovery could not prove resources absent")
            terminal = dict(record)
            terminal.update(
                {
                    "starting": False,
                    "cleanup_required": False,
                    "closed": True,
                    "recovery": "partial start resources absent",
                }
            )
            _atomic_write_json(identity_path, terminal)
            return terminal

    def inspect(self, *, identity_path: Path) -> dict[str, Any]:
        record = _load_identity(identity_path)
        agent = validate_identity(
            record,
            self.herdr.get_agent(str(record.get("worker_agent_name", ""))),
        )
        result = dict(record)
        result["agent_status"] = agent.get("agent_status")
        return result

    def read(self, *, identity_path: Path, lines: int) -> dict[str, Any]:
        if not 1 <= lines <= 1000:
            raise HandoffError("read lines must be between 1 and 1000")
        record = _load_identity(identity_path)
        name = str(record.get("worker_agent_name", ""))
        validate_identity(record, self.herdr.get_agent(name))
        output = self.herdr.read_agent(name=name, lines=lines)
        agent = validate_identity(record, self.herdr.get_agent(name))
        return {
            "ok": True,
            "worker_agent_name": name,
            "agent_status": agent.get("agent_status"),
            "output": output,
        }

    def prompt(
        self,
        *,
        identity_path: Path,
        text: str,
        timeout_ms: int,
    ) -> dict[str, Any]:
        if not text.strip():
            raise HandoffError("prompt text must not be empty")
        record = _load_identity(identity_path)
        name = str(record.get("worker_agent_name", ""))
        kind = record.get("worker_kind")
        lease = TurnLease(self.lease_path) if kind == "claude" else nullcontext()
        with lease:
            capacity_start = self._require_capacity() if kind == "claude" else None
            others = working_claude_names(self.herdr.list_agents(), excluding=name)
            if kind == "claude" and others:
                raise HandoffError(
                    "another Claude turn is active: " + ", ".join(others)
                )
            before = validate_identity(record, self.herdr.get_agent(name))
            status = before.get("agent_status")
            if status == "working":
                raise HandoffError("recorded worker already has an active turn")
            if status == "blocked":
                raise HandoffError("recorded worker is blocked; use answer-blocked")
            if status != "idle":
                raise HandoffError(f"recorded worker cannot accept a prompt from {status}")
            self.herdr.prompt(name=name, text=text, timeout_ms=timeout_ms)
            after = validate_identity(record, self.herdr.get_agent(name))
            capacity_end = self.capacity_probe(False) if kind == "claude" else None
        return {
            "ok": True,
            "worker_agent_name": name,
            "agent_status": after.get("agent_status"),
            "provider_capacity_start": (
                capacity_start.percentage if capacity_start else None
            ),
            "provider_capacity_end": (
                capacity_end.percentage if capacity_end else None
            ),
            "provider_capacity_end_verified": (
                capacity_end.ok and capacity_end.percentage is not None
                if capacity_end
                else None
            ),
        }

    def answer_blocked(
        self,
        *,
        identity_path: Path,
        text: str | None,
        keys: list[str] | None,
        timeout_ms: int,
    ) -> dict[str, Any]:
        if (text is None) == (keys is None):
            raise HandoffError("answer requires exactly one of text or keys")
        if text is not None and not text.strip():
            raise HandoffError("answer text must not be empty")
        if keys is not None and not keys:
            raise HandoffError("answer keys must not be empty")
        record = _load_identity(identity_path)
        name = str(record.get("worker_agent_name", ""))
        pane_id = str(record.get("worker_pane_id", ""))
        kind = record.get("worker_kind")
        lease = TurnLease(self.lease_path) if kind == "claude" else nullcontext()
        with lease:
            capacity_start = self._require_capacity() if kind == "claude" else None
            others = working_claude_names(self.herdr.list_agents(), excluding=name)
            if kind == "claude" and others:
                raise HandoffError(
                    "another Claude turn is active: " + ", ".join(others)
                )
            before = validate_identity(record, self.herdr.get_agent(name))
            if before.get("agent_status") != "blocked":
                raise HandoffError("recorded worker is not blocked")
            before_seq = _state_change_seq(before)
            if text is not None:
                self.herdr.send_text(pane_id=pane_id, text=text)
                self.herdr.send_keys(name=name, keys=["enter"])
            else:
                self.herdr.send_keys(name=name, keys=keys or [])
            self.herdr.wait_agent(
                name=name,
                after_seq=before_seq,
                timeout_ms=timeout_ms,
            )
            after = validate_identity(record, self.herdr.get_agent(name))
            if _state_change_seq(after) <= before_seq:
                raise HandoffError("blocked answer produced no newer lifecycle state")
            capacity_end = self.capacity_probe(False) if kind == "claude" else None
        return {
            "ok": True,
            "worker_agent_name": name,
            "agent_status": after.get("agent_status"),
            "provider_capacity_start": (
                capacity_start.percentage if capacity_start else None
            ),
            "provider_capacity_end": (
                capacity_end.percentage if capacity_end else None
            ),
            "provider_capacity_end_verified": (
                capacity_end.ok and capacity_end.percentage is not None
                if capacity_end
                else None
            ),
        }

    def close(self, *, identity_path: Path) -> dict[str, Any]:
        with StartLease(identity_path):
            record = _load_identity(identity_path)
            if record.get("starting") or (
                record.get("cleanup_required") and not record.get("closing")
            ):
                raise HandoffError("incomplete start requires recover-start")
            name = record.get("worker_agent_name")
            pane_value = record.get("worker_pane_id")
            if not isinstance(name, str) or not name:
                raise HandoffError("worker identity omitted agent name")
            if not isinstance(pane_value, str) or not pane_value:
                raise HandoffError("worker identity omitted pane ID")
            if record.get("closed") is True:
                if self.herdr.agent_exists(name) or self.herdr.pane_exists(pane_value):
                    raise HandoffError("closed identity still resolves to a Herdr resource")
                return record

            if not record.get("closing"):
                validate_identity(record, self.herdr.get_agent(name))
                self.herdr.get_pane(pane_value)
                record["closing"] = True
                record["cleanup_required"] = True
                _atomic_write_json(identity_path, record)
                agent_exists = True
                pane_exists = True
            else:
                agent_exists = self.herdr.agent_exists(name)
                pane_exists = self.herdr.pane_exists(pane_value)
                if agent_exists:
                    validate_identity(record, self.herdr.get_agent(name))
                if agent_exists and not pane_exists:
                    raise HandoffError("closing worker exists without its recorded pane")

            if pane_exists:
                self.herdr.close_pane(pane_value)
            if self.herdr.agent_exists(name) or self.herdr.pane_exists(pane_value):
                raise HandoffError("Herdr worker or pane still exists after close")
            record.update(
                {
                    "closing": False,
                    "cleanup_required": False,
                    "closed": True,
                }
            )
            _atomic_write_json(identity_path, record)
            return record


def real_capacity_probe(script: Path) -> Callable[[bool], CapacityProbe]:
    resolved = script.expanduser().resolve()

    def probe(required: bool) -> CapacityProbe:
        if not resolved.is_file() or not os.access(resolved, os.X_OK):
            return CapacityProbe(
                ok=False,
                returncode=69,
                message=f"Claude capacity could not be verified: {resolved}",
            )
        try:
            result = subprocess.run(
                [str(resolved), "--check-capacity"],
                text=True,
                capture_output=True,
                check=False,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return CapacityProbe(
                ok=False,
                returncode=69,
                message=f"Claude capacity could not be verified: {exc}",
            )
        message = (result.stdout or result.stderr).strip()
        return CapacityProbe(
            ok=result.returncode == 0,
            returncode=result.returncode,
            message=message,
        )

    return probe


def _require_real_herdr_environment() -> tuple[Path, str]:
    if os.environ.get("HERDR_ENV") != "1":
        raise HandoffError("visible handoff requires HERDR_ENV=1")
    binary = os.environ.get("HERDR_BIN_PATH", "")
    pane = os.environ.get("HERDR_PANE_ID", "")
    if not binary or not pane:
        raise HandoffError("visible handoff requires HERDR_BIN_PATH and HERDR_PANE_ID")
    return Path(binary), pane


def _default_lease_path() -> Path:
    state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return state_home / "herdr" / "claude-turn.lock"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--capacity-script",
        type=Path,
        default=Path.home() / ".config" / "herdr" / "claude-usage.sh",
    )
    parser.add_argument("--lease-path", type=Path, default=_default_lease_path())
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start")
    start.add_argument("--worktree", type=Path, required=True)
    start.add_argument("--identity-file", type=Path, required=True)
    start.add_argument("--name", required=True)
    start.add_argument("--kind", choices=("claude", "hermes"), default="claude")
    start.add_argument("--title")

    prompt = subparsers.add_parser("prompt")
    prompt.add_argument("--identity-file", type=Path, required=True)
    prompt_input = prompt.add_mutually_exclusive_group(required=True)
    prompt_input.add_argument("--text")
    prompt_input.add_argument("--prompt-file", type=Path)
    prompt.add_argument("--timeout-ms", type=int, default=7_200_000)

    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("--identity-file", type=Path, required=True)

    read = subparsers.add_parser("read")
    read.add_argument("--identity-file", type=Path, required=True)
    read.add_argument("--lines", type=int, default=120)

    answer = subparsers.add_parser("answer-blocked")
    answer.add_argument("--identity-file", type=Path, required=True)
    answer_input = answer.add_mutually_exclusive_group(required=True)
    answer_input.add_argument("--text")
    answer_input.add_argument("--keys", nargs="+")
    answer.add_argument("--timeout-ms", type=int, default=7_200_000)

    recover = subparsers.add_parser("recover-start")
    recover.add_argument("--identity-file", type=Path, required=True)

    close = subparsers.add_parser("close")
    close.add_argument("--identity-file", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        binary, injected_pane = _require_real_herdr_environment()
        if args.command == "start":
            worktree = args.worktree.expanduser().resolve()
            identity_path = args.identity_file
        else:
            record = _load_identity(args.identity_file)
            worktree_data = record.get("worker_worktree_identity")
            if not isinstance(worktree_data, dict) or not isinstance(worktree_data.get("root"), str):
                raise HandoffError("identity record omitted worktree root")
            worktree = Path(worktree_data["root"])
            identity_path = args.identity_file
        controller = HandoffController(
            herdr=RealHerdr(binary, worktree),
            capacity_probe=real_capacity_probe(args.capacity_script),
            lease_path=args.lease_path,
        )
        if args.command == "start":
            result = controller.start(
                caller_pane=injected_pane,
                worktree=worktree,
                identity_path=identity_path,
                name=args.name,
                kind=args.kind,
                title=args.title or args.name,
            )
        elif args.command == "prompt":
            text = args.text
            if args.prompt_file is not None:
                prompt_path = args.prompt_file.expanduser().resolve()
                state_root = args.identity_file.expanduser().resolve().parent
                if not prompt_path.is_relative_to(state_root):
                    raise HandoffError("prompt file must stay inside the identity state directory")
                text = prompt_path.read_text(encoding="utf-8")
            result = controller.prompt(
                identity_path=identity_path,
                text=text or "",
                timeout_ms=args.timeout_ms,
            )
        elif args.command == "inspect":
            result = controller.inspect(identity_path=identity_path)
        elif args.command == "read":
            result = controller.read(identity_path=identity_path, lines=args.lines)
        elif args.command == "answer-blocked":
            result = controller.answer_blocked(
                identity_path=identity_path,
                text=args.text,
                keys=args.keys,
                timeout_ms=args.timeout_ms,
            )
        elif args.command == "recover-start":
            result = controller.recover_start(identity_path=identity_path)
        else:
            result = controller.close(identity_path=identity_path)
    except (HandoffError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
