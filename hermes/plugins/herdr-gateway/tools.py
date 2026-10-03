"""Tool handlers: origin-scoped, request-bound Herdr worker lifecycle."""

from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import time
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path

from .herdr_client import HerdrClient, HerdrError, TransportError
from .hermes_runtime import (
    approval_mode, fenced_status, launch_args, parse_status, preflight, runtime_matches,
    status_blocks, status_problem, task_text_problem,
)
from .ledger import Ledger, LeaseBusy, StateError
from .policy import (
    TASK_RE, Refusal, authorize, clean_text, load_settings, owner_of, permitted_cwd,
    require_not_delegated, require_still_permitted, runtime_origin,
)

PROMPT_MAX_CHARS = 64_000
READ_MAX_CHARS = 40_000
DIALOG_MAX_CHARS = 2_000
# Herdr waits up to 5s for prompt activity before reporting agent_prompt_stalled.
ACTIVITY_FLOOR_MS = 10_000
READY = ("idle", "done")
# Native /status is rendered locally by the CLI; this bounds how long its block may take.
STATUS_WAIT_S = 10
STATUS_READ_LINES = "400"
UNSETTLED = frozenset({"submitting", "submitted", "working", "blocked", "timed_out", "unknown"})
YOLO_USAGE = ("Usage: /herdr-yolo <worker-id> on|off|status. Shows or changes the YOLO approval "
              "bypass of one of this conversation's own idle Hermes workers; workers always start "
              "with smart approvals.")
MODE_TEXT = {"smart": "smart approvals, YOLO bypass OFF",
             "yolo": "YOLO bypass ACTIVE (dangerous commands are auto-approved)",
             "pending:smart": "an unverified change to smart approvals",
             "pending:yolo": "an unverified change to YOLO bypass"}


def _ok(**fields) -> str:
    return json.dumps({"ok": True, **fields})


def _refused(code: str, message: str, **details) -> str:
    return json.dumps({"ok": False, "error_code": code, "error": message, **details})


def _now() -> float:
    return round(time.time(), 3)


def _tool_env(**extra: str) -> dict[str, str]:
    return {"HOME": os.environ.get("HOME", "/"), "PATH": os.environ.get("PATH", os.defpath),
            "LC_ALL": "C", **extra}


def git_identity(cwd: str) -> dict | None:
    """Worktree root, common Git dir and branch for ``cwd``; None outside Git."""
    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True,
                              env=_tool_env(), timeout=30, check=False)

    top = git("rev-parse", "--show-toplevel")
    if top.returncode != 0:
        return None
    common = git("rev-parse", "--path-format=absolute", "--git-common-dir")
    branch = git("branch", "--show-current")
    if common.returncode != 0 or branch.returncode != 0:
        raise Refusal("git_identity_unavailable", "Git identity of cwd could not be read")
    return {"root": os.path.realpath(top.stdout.strip()),
            "common_dir": os.path.realpath(common.stdout.strip()),
            "branch": branch.stdout.strip()}


def _is_folder_trust_prompt(screen: str, cwd: str) -> bool:
    """Claude's ordinary folder-trust dialog, shown for exactly ``cwd``."""
    match = re.search(r"Accessing workspace:\s*(.*?)\s*Quick safety check:", screen, re.S)
    if not match:
        return False
    shown = "".join(line.strip() for line in match.group(1).splitlines())
    normalized = " ".join(screen.split())
    return (bool(shown) and os.path.realpath(os.path.expanduser(shown)) == cwd
            and "Is this a project you created or one you trust?" in normalized
            and "❯ No, exit" in normalized and "Yes, I trust this folder" in normalized)


@dataclass
class Request:
    settings: dict
    origin: dict
    entry: dict
    herdr: HerdrClient
    ledger: Ledger


class Handlers:
    def __init__(self, ctx) -> None:
        self.ctx = ctx

    # ---------- shared ----------

    def _begin(self, session_id) -> Request:
        settings = load_settings(self.ctx)
        require_not_delegated()
        origin = runtime_origin(session_id)
        entry = authorize(settings, origin)
        ledger = Ledger(Path(self.ctx.state.data_dir) / "workers")
        ledger.records()  # validate persisted state before any Herdr contact
        return Request(settings, origin, entry,
                       HerdrClient(settings["herdr_bin"], settings["socket_path"]), ledger)

    def _guard(self, fn, args, session_id) -> str:
        if not isinstance(args, dict):
            return _refused("invalid_argument", "arguments must be an object")
        try:
            return fn(args, session_id)
        except Refusal as exc:
            return _refused(exc.code, str(exc), **exc.details)
        except StateError as exc:
            return _refused("state_unsafe", f"worker state refused: {exc}")
        except LeaseBusy as exc:
            if exc.kind == "worker":
                return _refused("worker_busy", "another request is starting, driving or closing "
                                "this worker; nothing was changed")
            return _refused("turn_in_progress", "another request is driving this worker's turn")
        except HerdrError as exc:
            return _refused("herdr_error", str(exc))

    def _check_endpoint(self, req: Request) -> None:
        try:
            fields = req.herdr.status()
        except TransportError as exc:
            raise Refusal("herdr_unavailable", str(exc)) from None
        if fields.get("status") != "running":
            raise Refusal("herdr_unavailable", "the configured Herdr server is not running")
        if fields.get("endpoint_compatible") != "yes" or fields.get("private_protocol_compatible") != "yes":
            raise Refusal("herdr_incompatible", "Herdr client and server protocols are not compatible")
        if os.path.realpath(fields.get("socket", "")) != os.path.realpath(req.settings["socket_path"]):
            raise Refusal("herdr_endpoint_mismatch", "Herdr answered from a different endpoint")

    def _require_capacity(self, req: Request) -> None:
        command = req.settings["claude_capacity_command"]
        if not command:
            raise Refusal("capacity_unverified", "claude_capacity_command is not configured")
        try:
            proc = subprocess.run([command, "--check-capacity"], capture_output=True, text=True,
                                  env=_tool_env(), timeout=15, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            raise Refusal("capacity_unverified", f"Claude capacity check failed: {exc}") from None
        if proc.returncode != 0:
            raise Refusal("capacity_unavailable", "Claude capacity check refused",
                          detail=(proc.stdout or proc.stderr).strip()[:200])

    @staticmethod
    def _only(args: dict, allowed: set[str]) -> None:
        """Reject any argument the schema does not define (origin, launch flags, model, ...)."""
        unknown = sorted(set(args) - allowed)
        if unknown:
            raise Refusal("invalid_argument", f"unsupported argument(s): {', '.join(unknown)}")

    @staticmethod
    def _prompt(value) -> str:
        if not isinstance(value, str) or not value.strip():
            raise Refusal("invalid_argument", "prompt must be non-empty text")
        if not clean_text(value):
            raise Refusal("invalid_argument", "prompt must be valid Unicode text without NUL characters")
        if len(value) > PROMPT_MAX_CHARS:
            raise Refusal("invalid_argument", f"prompt exceeds {PROMPT_MAX_CHARS} characters")
        if value.startswith("-"):
            raise Refusal("invalid_argument", "prompt must not begin with '-'")
        return value

    @staticmethod
    def _hermes_task(prompt: str) -> None:
        """A Hermes brief or follow-up is a model task, never a native CLI command."""
        problem = task_text_problem(prompt)
        if problem:
            raise Refusal("invalid_argument", f"Hermes prompt refused: it {problem}; nothing was sent")

    @staticmethod
    def _wait_ms(value, settings: dict) -> int:
        if value is None:
            value = 0
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise Refusal("invalid_argument", "wait_seconds must be a non-negative integer")
        if value > settings["max_wait_seconds"]:
            raise Refusal("invalid_argument", f"wait_seconds exceeds {settings['max_wait_seconds']}")
        return value * 1000

    # ---------- identity ----------

    @staticmethod
    def _owned(req: Request, worker_id) -> dict:
        """The record for ``worker_id`` only if this exact room/thread/user owns it."""
        record = req.ledger.records().get(worker_id) if isinstance(worker_id, str) else None
        if record is None or record["owner"] != owner_of(req.origin):
            raise Refusal("worker_not_found", "no worker with that id belongs to this conversation")
        return record

    @staticmethod
    def _view(record: dict) -> dict:
        return {key: record.get(key) for key in (
            "task", "agent", "preset", "phase", "pane_id", "workspace_id", "cwd",
            "runtime_session", "turn", "mode", "error", "closed_result")} | {
            "worker": record["id"], "git_branch": (record["git"] or {}).get("branch")}

    def _result(self, record: dict, **extra) -> str:
        return _ok(**(self._view(record) | extra))

    def _live_agent(self, req: Request, record: dict) -> dict:
        """Return the live agent only if it is exactly the recorded worker."""
        if record["endpoint"] != req.settings["socket_path"]:
            raise Refusal("endpoint_mismatch", "worker belongs to a different Herdr endpoint")
        if record["phase"] == "closed" or not record["pane_id"] or not record["terminal_id"]:
            raise Refusal("worker_unavailable", f"worker is {record['phase']}")
        agent = req.herdr.call("agent", "get", record["agent"], expect="agent")
        expected = {
            "name": record["agent"], "agent": record["kind"], "pane_id": record["pane_id"],
            "workspace_id": record["workspace_id"], "terminal_id": record["terminal_id"],
        }
        for key, value in expected.items():
            if agent.get(key) != value:
                raise Refusal("identity_mismatch", f"live worker {key} differs from the record")
        if os.path.realpath(str(agent.get("cwd", ""))) != record["cwd"]:
            raise Refusal("identity_mismatch", "live worker cwd differs from the record")
        session = (agent.get("agent_session") or {}).get("value")
        bound = record.get("runtime_session")
        # Hermes reports its session to Herdr only at its first conversation. Until then the
        # session bound from native status stands; any report must agree with it.
        if bound and session != bound and not (record["kind"] == "hermes" and session is None):
            raise Refusal("identity_mismatch", "live worker runtime session differs from the record")
        if record["git"] != (git_identity(record["cwd"]) if record["git"] is not None else None):
            raise Refusal("identity_mismatch", "Git identity of the worker directory changed")
        if record["process"] is not None:
            live = self._foreground(req, record)
            if {"pid": live["pid"], "argv": live["argv"]} != record["process"]:
                raise Refusal("identity_mismatch", "worker foreground process differs from the "
                              "admitted runtime")
        return agent

    @staticmethod
    def _foreground(req: Request, record: dict) -> dict:
        """The pane's foreground process-group leader (the agent itself, not a child)."""
        info = req.herdr.call("pane", "process-info", "--pane", record["pane_id"],
                              expect="process_info")
        pgid = info.get("foreground_process_group_id")
        leaders = [p for p in info.get("foreground_processes") or ()
                   if isinstance(p, dict) and p.get("pid") == pgid]
        argv = leaders[0].get("argv") if len(leaders) == 1 else None
        if (info.get("pane_id") != record["pane_id"] or isinstance(pgid, bool)
                or not isinstance(pgid, int) or pgid <= 0 or pgid == info.get("shell_pid")
                or not isinstance(argv, list) or not argv
                or not all(isinstance(v, str) and v and clean_text(v) for v in argv)):
            raise Refusal("identity_unverified", "the worker pane's foreground process could not be "
                          "identified")
        return {"pid": pgid, "argv": argv, "cwd": leaders[0].get("cwd")}

    # ---------- turns ----------

    @staticmethod
    def _classify(agent: dict, seq_before: int) -> str:
        """Turn state relative to the lifecycle sequence captured before submission."""
        if agent.get("state_change_seq", -1) <= seq_before:
            return "submitted"
        return {"working": "working", "blocked": "blocked", "idle": "settled",
                "done": "settled"}.get(str(agent.get("agent_status")), "unknown")

    def _observe(self, req: Request, record: dict, seq_before: int) -> str:
        """Classify after a lost or expired acknowledgement; no observed activity is unknown."""
        try:
            state = self._classify(self._live_agent(req, record), seq_before)
        except (Refusal, HerdrError):
            return "unknown"
        return "unknown" if state == "submitted" else state

    def _record_turn(self, req: Request, record: dict, seq_before: int, state: str) -> dict:
        turn = {"state": state, "seq_before": seq_before, "at": _now()}
        req.ledger.update(record["id"], turn=turn)
        if state == "blocked":
            # Surface the approval/question; the human answers it in the visible pane.
            try:
                self._live_agent(req, record)
                screen = req.herdr.text("agent", "read", record["agent"], "--source", "visible")
                turn = dict(turn, dialog=screen.strip()[-DIALOG_MAX_CHARS:])
            except (Refusal, HerdrError):
                turn = dict(turn, dialog=None)
        return turn

    def _submit(self, req: Request, worker_id: str, prompt: str, wait_ms: int,
                revalidate: bool = False) -> dict:
        """Send one turn. ``revalidate`` marks later input: a Hermes worker's runtime policy is
        then proven again first (the first brief follows its admission under the same lease)."""
        record = req.ledger.records()[worker_id]
        require_still_permitted(req.entry, record["cwd"])
        if record["phase"] != "ready":
            raise Refusal("worker_not_ready", f"worker is {record['phase']}; nothing was sent")
        with req.ledger.lease("turn", record["runtime_session"]):
            record = req.ledger.records()[worker_id]
            if (record.get("turn") or {}).get("state") in UNSETTLED:
                raise Refusal("turn_unsettled", "the previous turn is not settled; use herdr_wait or "
                              "herdr_read. Nothing was sent.", turn=record["turn"])
            if record["kind"] == "claude":
                self._require_capacity(req)
            elif revalidate:
                self._revalidate(req, record)
            agent = self._live_agent(req, record)
            if agent.get("agent_status") not in READY:
                raise Refusal("worker_not_ready", f"worker is {agent.get('agent_status')}; nothing was sent")
            seq = agent["state_change_seq"]
            # Persisted before sending: a lost acknowledgement can never cause a resend.
            req.ledger.update(worker_id, turn={"state": "submitting", "seq_before": seq, "at": _now()})
            timeout_ms = max(wait_ms, ACTIVITY_FLOOR_MS)
            try:
                req.herdr.call("agent", "prompt", record["agent"], prompt, "--wait",
                               "--timeout", str(timeout_ms), timeout_s=timeout_ms / 1000 + 30)
                stalled = False
            except HerdrError as exc:
                if exc.code in ("agent_blocked", "agent_not_found"):  # rejected before any input
                    req.ledger.update(worker_id, turn=None)
                    raise Refusal("worker_not_ready", f"Herdr refused the prompt ({exc.code}); "
                                  "nothing was sent") from None
                stalled = exc.code == "agent_prompt_stalled"
            # Classified from a fresh identity-checked observation, never from the ack alone.
            state = "submitted" if stalled else self._observe(req, record, seq)
            return self._record_turn(req, record, seq, state)

    # ---------- herdr_prompt / herdr_wait ----------

    def prompt(self, args: dict, session_id=None, **_) -> str:
        return self._guard(self._prompt_turn, args, session_id)

    def _prompt_turn(self, args: dict, session_id) -> str:
        req = self._begin(session_id)
        self._only(args, {"worker", "prompt", "wait_seconds"})
        prompt = self._prompt(args.get("prompt"))
        wait_ms = self._wait_ms(args.get("wait_seconds"), req.settings)
        record = self._owned(req, args.get("worker"))
        if record["kind"] == "hermes":
            self._hermes_task(prompt)
        with req.ledger.lease("worker", record["id"]):
            turn = self._submit(req, record["id"], prompt, wait_ms, revalidate=True)
        return self._result(req.ledger.records()[record["id"]], turn=turn)

    def wait(self, args: dict, session_id=None, **_) -> str:
        return self._guard(self._wait_turn, args, session_id)

    def _wait_turn(self, args: dict, session_id) -> str:
        req = self._begin(session_id)
        self._only(args, {"worker", "wait_seconds"})
        wait_ms = self._wait_ms(args.get("wait_seconds", min(600, req.settings["max_wait_seconds"])),
                                req.settings)
        record = self._owned(req, args.get("worker"))
        require_still_permitted(req.entry, record["cwd"])
        with req.ledger.lease("worker", record["id"]):
            record = req.ledger.records()[record["id"]]
            if not record["turn"]:
                return self._result(record)
            with req.ledger.lease("turn", record["runtime_session"]):
                turn = self._await_turn(req, record, wait_ms)
        return self._result(req.ledger.records()[record["id"]], turn=turn)

    def _await_turn(self, req: Request, record: dict, wait_ms: int) -> dict:
        seq = record["turn"]["seq_before"]
        state = self._classify(self._live_agent(req, record), seq)
        if state == "working" and wait_ms:
            try:
                req.herdr.call("agent", "wait", record["agent"], "--timeout", str(wait_ms),
                               timeout_s=wait_ms / 1000 + 30)
                state = self._classify(self._live_agent(req, record), seq)
            except HerdrError as exc:
                state = "timed_out" if exc.code == "timeout" else self._observe(req, record, seq)
        if state == "submitted" and record["turn"]["state"] in ("submitting", "unknown"):
            state = "unknown"
        return self._record_turn(req, record, seq, state)

    # ---------- herdr_start ----------

    def start(self, args: dict, session_id=None, **_) -> str:
        return self._guard(self._start, args, session_id)

    def _start(self, args: dict, session_id) -> str:
        req = self._begin(session_id)
        settings = req.settings
        self._only(args, {"task", "cwd", "prompt", "preset", "wait_seconds"})
        task = args.get("task")
        if not isinstance(task, str) or not TASK_RE.fullmatch(task):
            raise Refusal("invalid_argument", "task must be a short kebab-case slug")
        prompt = self._prompt(args.get("prompt"))
        cwd = permitted_cwd(req.entry, args.get("cwd"))
        preset_name = args.get("preset") or settings["default_preset"]
        preset = settings["presets"].get(preset_name) if isinstance(preset_name, str) else None
        if preset is None:
            raise Refusal("invalid_argument", "preset names no configured operator preset")
        if preset["kind"] == "hermes":
            self._hermes_task(prompt)
        wait_ms = self._wait_ms(args.get("wait_seconds"), settings)
        self._check_endpoint(req)
        expected = None
        if preset["kind"] == "claude":
            self._require_capacity(req)
        else:
            # Intended launch policy only; the actual runtime is admitted after startup.
            expected = preflight(preset, _tool_env(HERMES_HOME=preset["home"]))
        worker_id = secrets.token_hex(8)
        # The lifecycle lease is held from before ownership exists until start returns, so no
        # other request can close (or drive) this worker while its layout, agent start, Hermes
        # admission or first brief is in flight.
        with req.ledger.lease("worker", worker_id):
            return self._start_owned(req, worker_id, task, preset_name, preset, cwd, prompt, wait_ms,
                                     expected)

    def _start_owned(self, req: Request, worker_id: str, task: str, preset_name: str, preset: dict,
                     cwd: str, prompt: str, wait_ms: int, expected: dict | None) -> str:
        record = self._reserve(req, worker_id, task, preset_name, preset, cwd, git_identity(cwd))
        # Hermes only: pin the default home and no-YOLO; nothing else is added to the pane.
        env = ([] if preset["kind"] == "claude" else
               ["--env", f"HERMES_HOME={preset['home']}", "--env", "HERMES_YOLO_MODE=0"])
        try:
            created = req.herdr.call("workspace", "create", "--cwd", cwd, "--label", record["label"],
                                     "--no-focus", *env)
        except TransportError:
            req.ledger.update(worker_id, phase="cleanup_required",
                              error="workspace creation was not acknowledged")
            raise Refusal("start_incomplete", "Herdr did not acknowledge workspace creation, so its "
                          "outcome is unresolved; ownership is kept and no agent was started. "
                          "herdr_close reconciles it once the labelled layout is visible.",
                          worker=worker_id) from None
        except HerdrError as exc:
            req.ledger.update(worker_id, phase="closed", error=f"workspace create: {exc.code}")
            raise Refusal("start_failed", f"Herdr refused workspace creation ({exc.code})",
                          worker=worker_id) from None
        try:
            record = self._adopt_layout(req, worker_id, created)
            blocked = self._launch(req, record, preset)
            if blocked is not None:
                return blocked
            if expected is None:
                self._bind_runtime(req, worker_id)
            else:
                self._admit(req, worker_id, expected)
        except (HerdrError, Refusal) as exc:
            try:
                cleanup = self._close_pane(req, req.ledger.records()[worker_id],
                                           error=f"start failed: {exc.code}")
            except (HerdrError, Refusal):
                req.ledger.update(worker_id, phase="cleanup_required", error=f"start failed: {exc.code}")
                cleanup = "cleanup could not be verified; ownership is kept for herdr_close"
            raise Refusal("start_failed", f"worker start failed ({exc.code}); the brief was not sent; "
                          f"{cleanup}", worker=worker_id, cause=exc.code, detail=str(exc)[:300]) from None
        turn = self._submit(req, worker_id, prompt, wait_ms)
        return self._result(req.ledger.records()[worker_id], turn=turn)

    @staticmethod
    def _reserve(req: Request, worker_id: str, task: str, preset_name: str, preset: dict,
                 cwd: str, git: dict | None) -> dict:
        """Claim ownership in the ledger before any Herdr mutation."""
        owner = owner_of(req.origin)
        with req.ledger.transaction() as records:
            live = [r for r in records.values() if r["phase"] != "closed"]
            for other in live:
                if other["owner"] == owner and other["task"] == task:
                    raise Refusal("task_already_open", "this conversation already has an open worker "
                                  "for that task", worker=other["id"])
            if len(live) >= req.settings["max_workers"]:
                raise Refusal("capacity_exhausted", "the gateway's worker limit is reached; "
                              "close a finished worker first")
            records[worker_id] = {
                "id": worker_id, "owner": owner, "session_key": req.origin["session_key"],
                "task": task, "preset": preset_name, "kind": preset["kind"],
                "model": preset.get("model"), "effort": preset.get("effort"),
                "agent": f"hg-{task[:20]}-{worker_id[:5]}", "label": f"hg:{task}:{worker_id}",
                "cwd": cwd, "git": git, "endpoint": req.settings["socket_path"],
                "phase": "layout_pending", "workspace_id": None, "tab_id": None, "pane_id": None,
                "terminal_id": None, "runtime_session": None, "turn": None, "created_at": _now(),
                "launch": (None if preset["kind"] == "claude" else
                           {"provider": preset["provider"], "home": preset["home"]}),
                "process": None,
                # Fresh Hermes workers are always smart, never YOLO.
                "mode": None if preset["kind"] == "claude" else "smart",
            }
            return dict(records[worker_id])

    @staticmethod
    def _adopt_layout(req: Request, worker_id: str, created: dict) -> dict:
        try:
            ids = {"workspace_id": created["workspace"]["workspace_id"],
                   "tab_id": created["tab"]["tab_id"], "pane_id": created["root_pane"]["pane_id"]}
        except (KeyError, TypeError):
            raise TransportError("workspace create returned no layout identifiers") from None
        req.ledger.update(worker_id, phase="agent_starting", **ids)
        pane = req.herdr.call("pane", "get", ids["pane_id"], expect="pane")
        if pane.get("workspace_id") != ids["workspace_id"] or not pane.get("terminal_id"):
            raise Refusal("identity_mismatch", "new pane does not belong to the new workspace")
        return req.ledger.update(worker_id, terminal_id=pane["terminal_id"])

    def _launch(self, req: Request, record: dict, preset: dict) -> str | None:
        """Start the agent; None when ready, else a blocked-startup result."""
        args = (["--permission-mode", preset["permission_mode"], "--model", preset["model"],
                 "--effort", preset["effort"], "--name", record["task"]]
                if record["kind"] == "claude" else launch_args(preset))
        try:
            req.herdr.call("agent", "start", record["agent"], "--kind", record["kind"], "--pane",
                           record["pane_id"], "--timeout", "300000", "--", *args, timeout_s=330)
        except HerdrError as exc:
            if exc.code != "agent_not_ready":
                raise
        agent = self._live_agent(req, record)
        if agent.get("agent_status") in READY:
            return None
        screen = req.herdr.text("agent", "read", record["agent"], "--source", "visible")
        if (record["kind"] == "claude" and agent.get("agent_status") == "blocked"
                and _is_folder_trust_prompt(screen, record["cwd"])):
            # The authorized, operator-permitted cwd is the inspected folder being trusted.
            req.herdr.call("agent", "send-keys", record["agent"], "down", "enter")
            agent = self._await_change(req, record, agent["state_change_seq"])
            if agent.get("agent_status") in READY:
                return None
            screen = req.herdr.text("agent", "read", record["agent"], "--source", "visible")
        req.ledger.update(record["id"], phase="blocked_startup")
        status = agent.get("agent_status")
        reason = ("the worker reported unknown readiness; this is a startup blocker, not an "
                  "outage" if status == "unknown" else
                  "the worker is waiting on a startup dialog the gateway does not answer")
        return _refused("worker_not_ready", f"{reason}. The brief was not sent. Inspect the "
                        "visible pane, then herdr_close.", worker=record["id"],
                        agent_status=status, dialog=screen.strip()[-DIALOG_MAX_CHARS:])

    def _await_change(self, req: Request, record: dict, seq: int, timeout_s: float = 60) -> dict:
        deadline = time.monotonic() + timeout_s
        while True:
            agent = self._live_agent(req, record)
            if agent.get("state_change_seq", -1) > seq or time.monotonic() >= deadline:
                return agent
            time.sleep(0.2)

    def _bind_runtime(self, req: Request, worker_id: str) -> dict:
        agent = self._live_agent(req, req.ledger.records()[worker_id])
        session = (agent.get("agent_session") or {}).get("value")
        if not isinstance(session, str) or not session:
            raise Refusal("identity_unverified", "Herdr reported no runtime session for the worker")
        return req.ledger.update(worker_id, phase="ready", runtime_session=session)

    # ---------- Hermes admission ----------

    def _admit(self, req: Request, worker_id: str, expected: dict) -> dict:
        """Admit a started Hermes worker from its actual runtime before any brief is sent.

        No model turn is used: native ``/status`` reports the session, home, model route and the
        approval engine's effective mode. Herdr has no session yet, so the status session is
        bound here, and Herdr's later report must agree with it.
        """
        record = req.ledger.records()[worker_id]
        status, process, agent = self._native_status(req, record, expected)
        problem = status_problem(status, record, fresh=True)
        reported = (agent.get("agent_session") or {}).get("value")
        if problem is None and reported is not None and reported != status["session"]:
            problem = "Herdr reports a different session than the worker's own status"
        if problem:
            raise Refusal("hermes_unverified", problem)
        with req.ledger.transaction() as records:
            if any(r["runtime_session"] == status["session"] for r in records.values()):
                raise Refusal("hermes_unverified", "the worker's session is already bound to a worker")
            records[worker_id].update(phase="ready", runtime_session=status["session"],
                                      process={"pid": process["pid"], "argv": process["argv"]})
            return dict(records[worker_id])

    def _revalidate(self, req: Request, record: dict) -> None:
        """Before later task input: the admitted process still runs under the admitted policy,
        with exactly the approval mode the user last authorized and the gateway verified."""
        if record["mode"] not in ("smart", "yolo"):
            raise Refusal("mode_unresolved", f"this worker's YOLO mode change was never verified; "
                          f"/herdr-yolo {record['id']} status resolves it. Nothing was sent.")
        status, _, _ = self._native_status(req, record, None)
        problem = status_problem(status, record, fresh=False, mode=record["mode"])
        if problem:
            raise Refusal("hermes_unverified", f"{problem}; the follow-up was not sent")

    def _screen(self, req: Request, record: dict) -> str:
        return req.herdr.text("agent", "read", record["agent"], "--source", "recent-unwrapped",
                              "--lines", STATUS_READ_LINES)

    def _native_status(self, req: Request, record: dict,
                       expected: dict | None) -> tuple[dict, dict, dict]:
        """One read-only ``/status``, with the exact worker and process verified around it.

        ``expected`` (admission only) is the preflight runtime evidence the process must match,
        and the screen must hold no earlier report. The query never uses the task activity gate
        and is sent at most once: a lost acknowledgement is observed, not resent. Herdr reads
        have no cursor, only the last lines, so neither block counts nor text changes can tell
        identical reports apart. The CLI dispatches ``/status`` on its first word and echoes the
        whole input first, so a never-sent token makes the one block after its echo the answer.
        """
        agent = self._live_agent(req, record)
        if agent.get("agent_status") not in READY:
            raise Refusal("worker_not_ready", f"worker is {agent.get('agent_status')}; nothing was sent")
        process = self._foreground(req, record)
        if expected is not None and (not runtime_matches(expected, process["argv"])
                                     or os.path.realpath(str(process["cwd"])) != record["cwd"]):
            raise Refusal("hermes_unverified", "the worker's foreground process is not the preset "
                          "launcher's runtime in the worker directory")
        if expected is not None and status_blocks(self._screen(req, record)):
            raise Refusal("hermes_unverified", "status output was already on the new worker's screen")
        query = f"/status {secrets.token_hex(16)}"
        try:
            req.herdr.call("agent", "prompt", record["agent"], query)
        except TransportError:
            pass  # outcome unknown: observed below, never resent
        block = self._await_status(req, record, query)
        after = self._live_agent(req, record)
        if self._foreground(req, record) != process:
            raise Refusal("identity_mismatch", "the worker's foreground process changed around its "
                          "status query")
        status = parse_status(block)
        if status is None:
            raise Refusal("hermes_unverified", "the worker's status report is malformed")
        return status, process, after

    def _await_status(self, req: Request, record: dict, query: str) -> list[str]:
        deadline = time.monotonic() + STATUS_WAIT_S
        while True:
            block = fenced_status(self._screen(req, record), query)
            if block is not None:
                return block
            if time.monotonic() >= deadline:
                raise Refusal("hermes_unverified", "no complete status report followed this query's "
                              "own echo")
            time.sleep(0.2)

    @staticmethod
    def _gone(req: Request, kind: str, target: str) -> bool:
        try:
            req.herdr.call(kind, "get", target)
        except HerdrError as exc:
            return exc.code == f"{kind}_not_found"
        return False

    @staticmethod
    def _locators(record: dict) -> dict:
        return {"runtime_session": record["runtime_session"], "kind": record["kind"],
                "cwd": record["cwd"], "git_branch": (record["git"] or {}).get("branch"),
                "last_turn": (record.get("turn") or {}).get("state"), "mode": record["mode"]}

    def _close_pane(self, req: Request, record: dict, error: str | None = None) -> str:
        """Close only the recorded pane, then prove pane and agent absent."""
        pane_id = record["pane_id"]
        if pane_id and not self._gone(req, "pane", pane_id):
            pane = req.herdr.call("pane", "get", pane_id, expect="pane")
            if record["terminal_id"] and pane.get("terminal_id") != record["terminal_id"]:
                raise Refusal("identity_mismatch", "recorded pane now hosts another terminal")
            try:
                req.herdr.call("pane", "close", pane_id)
            except HerdrError:
                pass  # absence below is the only proof that counts
        if pane_id and self._gone(req, "pane", pane_id) and self._gone(req, "agent", record["agent"]):
            req.ledger.update(record["id"], phase="closed", error=error,
                              closed_result=self._locators(record))
            return "its pane was closed and verified absent"
        req.ledger.update(record["id"], phase="cleanup_required", error=error)
        return "cleanup could not be verified; ownership is kept for herdr_close"

    # ---------- herdr_status / herdr_read ----------

    def status(self, args: dict, session_id=None, **_) -> str:
        return self._guard(self._status, args, session_id)

    def _status(self, args: dict, session_id) -> str:
        req = self._begin(session_id)
        self._only(args, {"include_closed"})
        owner = owner_of(req.origin)
        rows = []
        for record in sorted(req.ledger.records().values(), key=lambda r: r["created_at"]):
            if record["owner"] != owner or (record["phase"] == "closed"
                                            and args.get("include_closed") is not True):
                continue
            row = self._view(record)
            if record["phase"] != "closed":
                try:
                    require_still_permitted(req.entry, record["cwd"])
                    row["agent_status"] = self._live_agent(req, record)["agent_status"]
                except Refusal as exc:
                    row["agent_status"] = exc.code
                except HerdrError as exc:
                    row["agent_status"] = "missing" if exc.code == "agent_not_found" else "unknown"
            rows.append(row)
        return _ok(workers=rows)

    def read(self, args: dict, session_id=None, **_) -> str:
        return self._guard(self._read, args, session_id)

    def _read(self, args: dict, session_id) -> str:
        req = self._begin(session_id)
        self._only(args, {"worker", "lines"})
        lines = args.get("lines", 120)
        if isinstance(lines, bool) or not isinstance(lines, int) or not 1 <= lines <= 400:
            raise Refusal("invalid_argument", "lines must be an integer from 1 to 400")
        record = self._owned(req, args.get("worker"))
        require_still_permitted(req.entry, record["cwd"])
        self._live_agent(req, record)
        text = req.herdr.text("agent", "read", record["agent"], "--source", "recent-unwrapped",
                              "--lines", str(lines))
        # The occupant must still be ours after the read, or the text is discarded.
        agent = self._live_agent(req, record)
        return _ok(worker=record["id"], agent_status=agent["agent_status"],
                   text=text[-READ_MAX_CHARS:])

    # ---------- herdr_close ----------

    def close(self, args: dict, session_id=None, **_) -> str:
        return self._guard(self._close, args, session_id)

    def _close(self, args: dict, session_id) -> str:
        req = self._begin(session_id)
        self._only(args, {"worker"})
        record = self._owned(req, args.get("worker"))
        if record["endpoint"] != req.settings["socket_path"]:
            raise Refusal("endpoint_mismatch", "worker belongs to a different Herdr endpoint")
        with req.ledger.lease("worker", record["id"]):
            record = req.ledger.records()[record["id"]]
            if record["phase"] == "closed":
                if record["pane_id"] and not (self._gone(req, "pane", record["pane_id"])
                                              and self._gone(req, "agent", record["agent"])):
                    raise Refusal("identity_mismatch", "a closed worker's pane or name still resolves")
                return self._result(record)
            turn = (req.ledger.lease("turn", record["runtime_session"])
                    if record["runtime_session"] else nullcontext())
            with turn:
                message = self._close_owned(req, record)
        record = req.ledger.records()[record["id"]]
        if record["phase"] != "closed":
            raise Refusal("cleanup_unverified", message, worker=record["id"])
        return self._result(record)

    def _close_owned(self, req: Request, record: dict) -> str:
        if record["pane_id"] is None:
            record = self._recover_layout(req, record)
        if not self._gone(req, "pane", record["pane_id"]):
            if record["terminal_id"] is None or self._gone(req, "agent", record["agent"]):
                record = self._check_pane(req, record)
            else:
                self._live_agent(req, record)
        record = req.ledger.update(record["id"], phase="closing")
        return self._close_pane(req, record)

    @staticmethod
    def _check_pane(req: Request, record: dict) -> dict:
        """No live agent to verify: the pane must still be this worker's terminal and workspace."""
        pane = req.herdr.call("pane", "get", record["pane_id"], expect="pane")
        if (pane.get("workspace_id") != record["workspace_id"] or not pane.get("terminal_id")
                or (record["terminal_id"] and pane["terminal_id"] != record["terminal_id"])):
            raise Refusal("identity_mismatch", "recorded pane now hosts another terminal")
        if record["git"] is not None and git_identity(record["cwd"]) != record["git"]:
            raise Refusal("identity_mismatch", "Git identity of the worker directory changed")
        # An interrupted start may have recorded the acknowledged pane before its terminal.
        return req.ledger.update(record["id"], terminal_id=pane["terminal_id"])

    def _recover_layout(self, req: Request, record: dict) -> dict:
        """Find the layout of an unacknowledged create by its unique label, never by position.

        Absence is not proof: a create whose outcome was never acknowledged may still land,
        so the record stays owned until its labelled layout is found and closed.
        """
        found = [w for w in req.herdr.call("workspace", "list", expect="workspaces")
                 if w.get("label") == record["label"]]
        if not found:
            req.ledger.update(record["id"], phase="cleanup_required")
            raise Refusal("cleanup_unverified", "workspace creation is unresolved and no workspace "
                          "carries this worker's label yet; that does not prove none will appear, "
                          "so ownership is kept and nothing was closed. Retry herdr_close later.",
                          worker=record["id"])
        if len(found) > 1:
            raise Refusal("cleanup_ambiguous", "more than one workspace carries this worker's label")
        panes = req.herdr.call("pane", "list", "--workspace", found[0]["workspace_id"],
                               expect="panes")
        if len(panes) != 1 or os.path.realpath(str(panes[0].get("cwd", ""))) != record["cwd"]:
            raise Refusal("cleanup_ambiguous", "the labeled workspace is not exactly this worker's layout")
        pane = panes[0]
        return req.ledger.update(record["id"], workspace_id=found[0]["workspace_id"],
                                 tab_id=pane.get("tab_id"), pane_id=pane["pane_id"],
                                 terminal_id=pane.get("terminal_id"))

    # ---------- /herdr-yolo: a native command a person types, never a model tool ----------

    def yolo_command(self, raw_args) -> str:
        """``/herdr-yolo <worker-id> on|off|status``, typed in the conversation owning the worker.

        Hermes dispatches plugin commands before any agent turn, with the message's source bound
        to the same ContextVars a tool call sees, so authorization and ownership are exactly the
        tools'. The reply goes straight back to that conversation.
        """
        parts = raw_args.split() if isinstance(raw_args, str) else []
        if len(parts) != 2 or parts[1] not in ("on", "off", "status"):
            return YOLO_USAGE
        try:
            out = json.loads(self._guard(self._yolo, {"worker": parts[0], "action": parts[1]}, None))
        except Exception as exc:  # a raising command would fall through to the model as text
            return (f"herdr-yolo failed unexpectedly ({type(exc).__name__}); "
                    f"`/herdr-yolo {parts[0]} status` shows the observed mode.")
        if out["ok"]:
            return out["message"]
        recorded = f" Recorded mode: {MODE_TEXT[out['mode']]}." if out.get("mode") in MODE_TEXT else ""
        return f"herdr-yolo refused ({out['error_code']}): {out['error']}{recorded}"

    def _yolo(self, args: dict, session_id) -> str:
        req = self._begin(session_id)
        record = self._owned(req, args["worker"])
        if record["kind"] != "hermes":
            raise Refusal("unsupported_kind", "only Hermes workers have a YOLO mode")
        require_still_permitted(req.entry, record["cwd"])
        with req.ledger.lease("worker", record["id"]):
            record = req.ledger.records()[record["id"]]
            state = (record.get("turn") or {}).get("state")
            if record["phase"] != "ready" or state in UNSETTLED:
                raise Refusal("worker_not_ready" if record["phase"] != "ready" else "turn_unsettled",
                              f"the worker is {state if record['phase'] == 'ready' else record['phase']}. "
                              "Only an idle, settled worker's mode can be shown or changed, and "
                              "nothing is typed into a running task or dialog; a person can still "
                              "act in its visible pane. Nothing was sent.", mode=record["mode"])
            with req.ledger.lease("turn", record["runtime_session"]):
                return self._yolo_owned(req, record, args["action"])

    def _yolo_owned(self, req: Request, record: dict, action: str) -> str:
        """Observe, then send native ``/yolo`` at most once, then observe again.

        Only an observed mode is ever claimed or recorded. The intent is persisted as
        ``pending:<mode>`` before sending, so a crash or an unobservable outcome leaves durable
        uncertainty that a later observation resolves, never a blind resend.
        """
        observed = self._observe_mode(req, record)
        if action == "status":
            note = ""
            if record["mode"].startswith("pending:"):
                record = req.ledger.update(record["id"], mode=observed)
                note = " An earlier unverified change is now resolved by this observation."
            elif record["mode"] != observed:
                note = (f" That is NOT the mode this gateway verified ({MODE_TEXT[record['mode']]}), "
                        "so task input stays refused until on/off settles it.")
            return self._yolo_reply(record, f"observed {MODE_TEXT[observed]}.{note}")
        desired = "yolo" if action == "on" else "smart"
        if observed == desired:
            record = req.ledger.update(record["id"], mode=desired)
            return self._yolo_reply(record, f"{MODE_TEXT[desired]} was already in effect; "
                                    "nothing was sent.")
        record = req.ledger.update(record["id"], mode=f"pending:{desired}")
        try:
            req.herdr.call("agent", "prompt", record["agent"], "/yolo")
        except TransportError:
            pass  # outcome unknown: observed below, never resent
        except HerdrError as exc:
            req.ledger.update(record["id"], mode=observed)
            raise Refusal("worker_not_ready", f"Herdr refused the /yolo command ({exc.code}); nothing "
                          "was sent", mode=observed) from None
        try:
            after = self._observe_mode(req, record)
        except (Refusal, HerdrError) as exc:
            raise Refusal("mode_unverified", f"/yolo was sent once, but its effect could not be "
                          f"observed ({exc.code}: {exc}). Nothing more was sent; task input stays "
                          f"refused until /herdr-yolo {record['id']} status observes the worker.",
                          mode=record["mode"]) from None
        record = req.ledger.update(record["id"], mode=after)
        if after != desired:
            raise Refusal("mode_unverified", f"after one /yolo the worker still shows "
                          f"{MODE_TEXT[after]}; nothing more was sent", mode=after)
        return self._yolo_reply(record, f"now {MODE_TEXT[after]}, verified from its own status.")

    def _observe_mode(self, req: Request, record: dict) -> str:
        """The admitted process's approval mode from one identity-checked native ``/status``."""
        status, _, _ = self._native_status(req, record, None)
        problem = status_problem(status, record, fresh=False, mode=None)
        if problem:
            raise Refusal("hermes_unverified", f"{problem}; its mode was not changed")
        return approval_mode(status["approvals"])

    def _yolo_reply(self, record: dict, text: str) -> str:
        scope = (f" It applies only to this worker, until /herdr-yolo {record['id']} off or "
                 "herdr_close." if record["mode"] == "yolo" else "")
        return _ok(message=f"Worker {record['id']} ({record['task']}, session "
                   f"{record['runtime_session']}): {text}{scope}", **self._view(record))
