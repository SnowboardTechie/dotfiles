#!/usr/bin/env python3
"""Create or update Git-backed Hermes cron definitions by exact job name."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import NoReturn


def fail(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def _env_value(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value

    hermes_home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    env_path = hermes_home / ".env"
    if not env_path.is_file():
        return ""
    try:
        from dotenv import dotenv_values  # pyright: ignore[reportMissingImports]

        return str(dotenv_values(env_path).get(name) or "").strip()
    except ImportError:
        return ""


def continuation_origin(definition: dict) -> dict | None:
    continuation = definition.get("continuation")
    if not definition["attachToSession"]:
        if continuation is not None:
            fail(f"{definition['name']!r} defines continuation while attachToSession is false")
        return None
    if not isinstance(continuation, dict):
        fail(f"{definition['name']!r} requires continuation metadata")

    match = re.fullmatch(r"matrix:(!\S+)", definition["deliver"])
    if not match:
        fail(f"{definition['name']!r} continuable delivery must target one explicit Matrix room")

    user_env = continuation.get("userEnv")
    if not isinstance(user_env, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", user_env):
        fail(f"{definition['name']!r} has invalid continuation userEnv")
    users = [value.strip() for value in _env_value(user_env).split(",") if value.strip()]
    if len(users) != 1:
        fail(f"{definition['name']!r} requires exactly one continuation user")

    chat_name = continuation.get("chatName")
    if not isinstance(chat_name, str) or not chat_name.strip():
        fail(f"{definition['name']!r} requires a continuation chatName")
    return {
        "platform": "matrix",
        "chat_id": match.group(1),
        "chat_name": chat_name.strip(),
        "thread_id": None,
        "user_id": users[0],
    }


def monitor_script_value(definition: dict) -> str | None:
    """Validate the declarative `monitorScript` key before it reaches the API.

    The scheduler enforces the same containment rule, but it rejects *after*
    this reconciler would otherwise have reported the job synchronized. Failing
    here keeps a bad definition from looking applied.
    """
    monitor_script = definition.get("monitorScript")
    if monitor_script is None:
        return None
    name = definition["name"]
    if not isinstance(monitor_script, str) or not monitor_script.strip():
        fail(f"{name!r} has an empty monitorScript")
    if "/" in monitor_script or "\\" in monitor_script or monitor_script.startswith("."):
        fail(
            f"{name!r} monitorScript must be a bare filename under HERMES_HOME/scripts, "
            f"got {monitor_script!r}"
        )
    if definition.get("noAgent"):
        fail(f"{name!r} cannot combine monitorScript with noAgent; a monitor gates an agent run")
    return monitor_script


def main() -> int:
    if len(sys.argv) != 2:
        fail("usage: reconcile_cron.py MANIFEST")

    manifest_path = Path(sys.argv[1]).resolve()
    asset_root = manifest_path.parent
    source_root = Path(os.environ["HERMES_SOURCE_ROOT"]).resolve()
    if not source_root.is_dir():
        fail(f"Hermes source root not found: {source_root}")
    sys.path.insert(0, str(source_root))

    from cron.jobs import list_jobs, resolve_job_ref, update_job  # pyright: ignore[reportMissingImports]  # noqa: PLC0415
    from tools.cronjob_tools import cronjob  # pyright: ignore[reportMissingImports]  # noqa: PLC0415

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    summaries: list[dict[str, str]] = []
    for definition in manifest["cronJobs"]:
        name = definition["name"]
        expected_origin = continuation_origin(definition)
        matches = [job for job in list_jobs(include_disabled=True) if job.get("name") == name]
        if len(matches) > 1:
            fail(f"refusing to reconcile duplicate cron jobs named {name!r}")
        if not matches and definition.get("createIfMissing", True) is False:
            summaries.append({"name": name, "action": "preserve-absent", "jobId": ""})
            continue

        monitor_script = monitor_script_value(definition)

        prompt_path = (asset_root / definition["promptFile"]).resolve()
        if asset_root not in prompt_path.parents:
            fail(f"prompt escapes managed asset root: {prompt_path}")
        prompt = prompt_path.read_text(encoding="utf-8").rstrip("\n")
        common = {
            "prompt": prompt,
            "schedule": definition["schedule"],
            "name": name,
            "model": definition["model"],
            "provider": definition["provider"],
            "base_url": definition.get("baseUrl"),
            "deliver": definition["deliver"],
            "skills": definition["skills"],
            "script": definition["script"],
            "no_agent": definition["noAgent"],
            "enabled_toolsets": definition["enabledToolsets"],
            "workdir": definition["workdir"],
            "attach_to_session": definition["attachToSession"],
            "continuity": bool(definition.get("carryPreviousOutput", False)),
        }
        # Always send the field. Omitting it on a job whose manifest entry
        # dropped `monitorScript` would leave the live monitor in place, and
        # the reconciler would report the job synchronized anyway. An empty
        # string is how the cron API clears it.
        common["monitor_script"] = monitor_script or ""
        # Apply finite repeat counts only on creation. Reconciliation must not
        # reset completed pilot runs.
        if not matches and "repeat" in definition:
            common["repeat"] = definition["repeat"]
        if matches:
            action = "update"
            current = matches[0]
            update_fields = dict(common)
            if current.get("base_url") and not definition.get("baseUrl"):
                # The cron update API treats None as "not supplied". Use the
                # documented empty-string clear so a local/custom route does
                # not survive an atomic migration to a named provider.
                update_fields["base_url"] = ""
            if current.get("state") in {"completed", "error"} and not current.get("enabled", True):
                if current.get("schedule_display") != definition["schedule"]:
                    fail(
                        f"refusing to change schedule for terminal cron job {name!r}; "
                        "resume or replace it explicitly"
                    )
                # Hermes's cron update tool treats any supplied schedule as an
                # instruction to enable and reschedule a non-paused job. Omit
                # the unchanged schedule so completed/error records remain
                # terminal while their prompt and other durable fields sync.
                update_fields.pop("schedule", None)
            response = json.loads(
                cronjob(action=action, job_id=current["id"], **update_fields)
            )
        else:
            action = "create"
            response = json.loads(cronjob(action=action, **common))
        if not response.get("success"):
            fail(f"{action} failed for {name!r}: {response.get('error', response)}")

        job = resolve_job_ref(name)
        if not job:
            fail(f"cron job {name!r} disappeared after {action}")
        if job.get("origin") != expected_origin:
            job = update_job(job["id"], {"origin": expected_origin})
            if not job:
                fail(f"cron job {name!r} disappeared while setting continuation origin")
        expected = {
            "name": name,
            "schedule_display": definition["schedule"],
            "model": definition["model"],
            "provider": definition["provider"],
            "base_url": definition.get("baseUrl"),
            "prompt": prompt,
            "deliver": definition["deliver"],
            "skills": definition["skills"],
            "script": definition["script"],
            "no_agent": definition["noAgent"],
            "enabled_toolsets": definition["enabledToolsets"],
            "workdir": definition["workdir"],
        }
        expected["monitor_script"] = monitor_script or None
        mismatches = {
            key: {"expected": value, "actual": job.get(key)}
            for key, value in expected.items()
            if job.get(key) != value
        }
        actual_attach = bool(job.get("attach_to_session", False))
        if actual_attach != definition["attachToSession"]:
            mismatches["attach_to_session"] = {
                "expected": definition["attachToSession"],
                "actual": actual_attach,
            }
        stored_refs = job.get("context_from") or []
        if isinstance(stored_refs, str):
            stored_refs = [stored_refs]
        actual_continuity = any(
            str(ref).strip().lower() == "self" or ref == job.get("id")
            for ref in stored_refs
        )
        expected_continuity = bool(definition.get("carryPreviousOutput", False))
        if actual_continuity != expected_continuity:
            mismatches["continuity"] = {
                "expected": expected_continuity,
                "actual": actual_continuity,
            }
        if job.get("origin") != expected_origin:
            mismatches["origin"] = {
                "expected": "configured" if expected_origin else None,
                "actual": "configured" if job.get("origin") else None,
            }
        if "repeat" in definition:
            actual_repeat = (job.get("repeat") or {}).get("times")
            if actual_repeat != definition["repeat"]:
                mismatches["repeat"] = {
                    "expected": definition["repeat"],
                    "actual": actual_repeat,
                }
        if mismatches:
            fail(f"cron verification failed for {name!r}: {json.dumps(mismatches, sort_keys=True)}")
        summaries.append({"name": name, "action": action, "jobId": job["id"]})

    print(json.dumps({"status": "synchronized", "jobs": summaries}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
