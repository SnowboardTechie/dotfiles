"""Authorization policy: trusted runtime origin and operator configuration."""

from __future__ import annotations

import contextvars
import os
import re

TASK_RE = re.compile(r"[a-z][a-z0-9-]{0,23}")
MODEL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:\[\]-]{0,127}")
PROVIDER_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
CLAUDE_EFFORTS = frozenset({"low", "medium", "high", "xhigh", "max"})
# Hermes's VALID_REASONING_EFFORTS (hermes_constants); "none" (thinking off) is not offered.
HERMES_EFFORTS = frozenset({"minimal", "low", "medium", "high", "xhigh", "max", "ultra"})
# Permission-respecting Claude modes only: bypassPermissions/dontAsk are absent by design.
CLAUDE_PERMISSION_MODES = frozenset({"default", "acceptEdits", "plan", "auto"})
PRESET_KEYS = {
    "claude": {"kind", "model", "effort", "permission_mode"},
    # Classic CLI, default profile only. No launch arguments, profiles or fallback providers.
    "hermes": {"kind", "launcher", "home", "provider", "model", "effort", "approvals"},
}

# Names Hermes gives its per-turn ContextVars (gateway/session_context.py).
_ORIGIN_VARS = {
    "HERMES_SESSION_PLATFORM": "platform",
    "HERMES_SESSION_CHAT_ID": "chat_id",
    "HERMES_SESSION_THREAD_ID": "thread_id",
    "HERMES_SESSION_USER_ID": "user_id",
    "HERMES_SESSION_KEY": "session_key",
    "HERMES_SESSION_ID": "session_id",
    "HERMES_CRON_SESSION": "cron",
}


class Refusal(Exception):
    """A request the gateway declines; ``code`` is stable for callers."""

    def __init__(self, code: str, message: str, **details) -> None:
        super().__init__(message)
        self.code = code
        self.details = details


def require_not_delegated() -> None:
    """Refuse delegate_task children and their spawned descendants.

    Uses Hermes's own delegation boundary (``agent.delegation_context``): the
    in-process child ContextVar and the descendant environment marker. A runtime
    that does not expose it cannot rule children out, so the gateway refuses.
    """
    try:
        from agent.delegation_context import is_delegated_child_process_context
    except Exception:
        raise Refusal("runtime_unsupported", "herdr-gateway requires a Hermes runtime that exposes "
                      "agent.delegation_context to rule out delegated children") from None
    if is_delegated_child_process_context():
        raise Refusal("delegated_child_refused", "delegated subagents cannot drive Herdr workers")


def runtime_origin(dispatch_session_id: str | None) -> dict:
    """Origin bound by Hermes for this turn, read only from ContextVars.

    Deliberately not ``get_session_env``: that falls back to ``os.environ`` when
    a var was never bound in this task, and process environment must not grant
    an otherwise unbound request authority.
    """
    bound: dict[str, object] = {}
    for var, value in contextvars.copy_context().items():
        field = _ORIGIN_VARS.get(var.name)
        if field is None:
            continue
        if field in bound:
            raise Refusal("origin_ambiguous", f"more than one runtime binding named {var.name}")
        bound[field] = value
    values = {field: value if isinstance(value, str) else "" for field, value in bound.items()}
    if values.get("cron"):
        raise Refusal("origin_unsupported", "scheduled runs cannot drive Herdr workers")
    missing = [f for f in ("platform", "chat_id", "user_id", "session_key") if not values.get(f)]
    if missing:
        raise Refusal("origin_unbound", "no trusted conversation origin is bound to this request",
                      missing=missing)
    bound_session = values.get("session_id", "")
    if bound_session and dispatch_session_id and bound_session != dispatch_session_id:
        raise Refusal("origin_stale", "bound conversation context belongs to another session")
    return {
        "platform": values["platform"],
        "chat_id": values["chat_id"],
        "thread_id": values.get("thread_id", ""),
        "user_id": values["user_id"],
        "session_key": values["session_key"],
    }


def owner_of(origin: dict) -> dict:
    """The exact scope that owns a worker: room, thread and requesting user."""
    return {k: origin[k] for k in ("platform", "chat_id", "thread_id", "user_id")}


def clean_text(value) -> bool:
    """A string the OS and argv can carry unchanged: no NUL, strictly UTF-8 encodable."""
    if not isinstance(value, str) or "\x00" in value:
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _abs_path(value, label: str) -> str:
    if not clean_text(value) or not os.path.isabs(value):
        raise Refusal("config_invalid", f"{label} must be an absolute path")
    return value


def _str_list(value, label: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(v, str) and v for v in value):
        raise Refusal("config_invalid", f"{label} must be a non-empty list of strings")
    return value


def load_settings(ctx) -> dict:
    """Validate the operator configuration on every call; any defect disables the gateway."""
    herdr_bin = ctx.get_config("herdr_bin", "")
    origins = ctx.get_config("origins", [])
    if not herdr_bin or not origins:
        raise Refusal("gateway_disabled", "herdr-gateway is not configured")
    herdr_bin = _abs_path(herdr_bin, "herdr_bin")
    if not os.path.isfile(herdr_bin) or not os.access(herdr_bin, os.X_OK):
        raise Refusal("config_invalid", "herdr_bin is not an executable file")
    socket_path = _abs_path(ctx.get_config("socket_path", ""), "socket_path")
    if not isinstance(origins, list):
        raise Refusal("config_invalid", "origins must be a list")
    checked = []
    for i, entry in enumerate(origins):
        if not isinstance(entry, dict) or set(entry) - {"platform", "chat_id", "user_ids", "projects"}:
            raise Refusal("config_invalid", f"origins[{i}] has an unsupported shape")
        if not all(isinstance(entry.get(k), str) and entry[k] for k in ("platform", "chat_id")):
            raise Refusal("config_invalid", f"origins[{i}] needs platform and chat_id")
        projects = [_abs_path(p, f"origins[{i}].projects") for p in
                    _str_list(entry.get("projects"), f"origins[{i}].projects")]
        checked.append({
            "platform": entry["platform"],
            "chat_id": entry["chat_id"],
            "user_ids": _str_list(entry.get("user_ids"), f"origins[{i}].user_ids"),
            "projects": [os.path.realpath(p) for p in projects],
        })
    presets = ctx.get_config("presets", {})
    if not isinstance(presets, dict) or not presets:
        raise Refusal("config_invalid", "presets must be a non-empty mapping")
    for name, preset in presets.items():
        _check_preset(name, preset)
    default_preset = ctx.get_config("default_preset", "")
    if not isinstance(default_preset, str) or (default_preset and default_preset not in presets):
        raise Refusal("config_invalid", "default_preset must name a configured preset")
    capacity = ctx.get_config("claude_capacity_command", "")
    if not isinstance(capacity, str):
        raise Refusal("config_invalid", "claude_capacity_command must be a path string")
    if capacity:
        _abs_path(capacity, "claude_capacity_command")
    max_workers = ctx.get_config("max_workers", 4)
    max_wait = ctx.get_config("max_wait_seconds", 1800)
    for label, value in (("max_workers", max_workers), ("max_wait_seconds", max_wait)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise Refusal("config_invalid", f"{label} must be a positive integer")
    return {
        "herdr_bin": herdr_bin,
        "socket_path": socket_path,
        "origins": checked,
        "presets": presets,
        "default_preset": default_preset,
        "claude_capacity_command": capacity,
        "max_workers": max_workers,
        "max_wait_seconds": max_wait,
    }


def _check_preset(name, preset) -> None:
    if not isinstance(name, str) or not TASK_RE.fullmatch(name) or not isinstance(preset, dict):
        raise Refusal("config_invalid", f"preset {name!r} has an unsupported shape")
    kind = preset.get("kind")
    if not isinstance(kind, str) or kind not in PRESET_KEYS:
        raise Refusal("config_invalid", f"preset {name!r} kind must be one of {sorted(PRESET_KEYS)}")
    if set(preset) != PRESET_KEYS[kind]:
        raise Refusal("config_invalid", f"preset {name!r} must define exactly {sorted(PRESET_KEYS[kind])}")
    if not isinstance(preset["model"], str) or not MODEL_RE.fullmatch(preset["model"]):
        raise Refusal("config_invalid", f"preset {name!r} model is not an exact model name")
    efforts = CLAUDE_EFFORTS if kind == "claude" else HERMES_EFFORTS
    if not isinstance(preset["effort"], str) or preset["effort"] not in efforts:
        raise Refusal("config_invalid", f"preset {name!r} effort is unsupported")
    if kind == "claude":
        if (not isinstance(preset["permission_mode"], str)
                or preset["permission_mode"] not in CLAUDE_PERMISSION_MODES):
            raise Refusal("config_invalid", f"preset {name!r} permission_mode is not permission-respecting")
        return
    if not isinstance(preset["provider"], str) or not PROVIDER_RE.fullmatch(preset["provider"]):
        raise Refusal("config_invalid", f"preset {name!r} provider is not an exact provider name")
    if preset["approvals"] != "smart":
        raise Refusal("config_invalid", f"preset {name!r} approvals must be smart")
    _abs_path(preset["launcher"], f"preset {name!r} launcher")
    home = _abs_path(preset["home"], f"preset {name!r} home")
    # The default profile is a Hermes root, never <root>/profiles/<name>.
    if os.path.normpath(home) != home or os.path.basename(os.path.dirname(home)) == "profiles":
        raise Refusal("config_invalid", f"preset {name!r} home must be a default-profile Hermes home")


def authorize(settings: dict, origin: dict) -> dict:
    """The configured entry admitting this exact platform, room and user."""
    for entry in settings["origins"]:
        if (entry["platform"] == origin["platform"] and entry["chat_id"] == origin["chat_id"]
                and origin["user_id"] in entry["user_ids"]):
            return entry
    raise Refusal("origin_not_authorized", "this conversation is not authorized for Herdr workers")


def permitted_cwd(entry: dict, cwd) -> str:
    if not clean_text(cwd) or not os.path.isabs(cwd):
        raise Refusal("invalid_argument", "cwd must be an absolute path without NUL characters")
    real = os.path.realpath(cwd)
    if not os.path.isdir(real):
        raise Refusal("invalid_argument", "cwd is not an existing directory")
    if not _within_projects(entry, real):
        raise Refusal("cwd_not_permitted", "cwd is outside this conversation's permitted projects")
    return real


def _within_projects(entry: dict, real: str) -> bool:
    return any(os.path.commonpath([real, project]) == project for project in entry["projects"])


def require_still_permitted(entry: dict, worker_cwd: str) -> None:
    """Re-derive authority to drive or read a worker from the current configuration.

    The recorded cwd must still resolve to itself (no symlink drift) and still lie
    inside a currently permitted project. Cleanup does not call this: closing an
    exact owned pane only reduces authority and returns no worker output.
    """
    if os.path.realpath(worker_cwd) != worker_cwd or not _within_projects(entry, worker_cwd):
        raise Refusal("cwd_not_permitted", "this worker's directory is no longer permitted for this "
                      "conversation; only herdr_close remains available")
