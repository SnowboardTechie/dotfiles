#!/usr/bin/env python3
"""Create or update Git-backed Hermes cron definitions by exact job name."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    if len(sys.argv) != 2:
        fail("usage: reconcile_cron.py MANIFEST")

    manifest_path = Path(sys.argv[1]).resolve()
    asset_root = manifest_path.parent
    source_root = Path(os.environ["HERMES_SOURCE_ROOT"]).resolve()
    if not source_root.is_dir():
        fail(f"Hermes source root not found: {source_root}")
    sys.path.insert(0, str(source_root))

    from cron.jobs import list_jobs, resolve_job_ref  # pyright: ignore[reportMissingImports]  # noqa: PLC0415
    from tools.cronjob_tools import cronjob  # pyright: ignore[reportMissingImports]  # noqa: PLC0415

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    summaries: list[dict[str, str]] = []
    for definition in manifest["cronJobs"]:
        name = definition["name"]
        matches = [job for job in list_jobs(include_disabled=True) if job.get("name") == name]
        if len(matches) > 1:
            fail(f"refusing to reconcile duplicate cron jobs named {name!r}")

        prompt_path = (asset_root / definition["promptFile"]).resolve()
        if asset_root not in prompt_path.parents:
            fail(f"prompt escapes managed asset root: {prompt_path}")
        prompt = prompt_path.read_text(encoding="utf-8").rstrip("\n")
        common = {
            "prompt": prompt,
            "schedule": definition["schedule"],
            "name": name,
            "deliver": definition["deliver"],
            "skills": definition["skills"],
            "script": definition["script"],
            "no_agent": definition["noAgent"],
            "enabled_toolsets": definition["enabledToolsets"],
            "workdir": definition["workdir"],
            "attach_to_session": definition["attachToSession"],
        }
        # Apply finite repeat counts only on creation. Reconciliation must not
        # reset completed pilot runs.
        if not matches and "repeat" in definition:
            common["repeat"] = definition["repeat"]
        if matches:
            action = "update"
            response = json.loads(cronjob(action=action, job_id=matches[0]["id"], **common))
        else:
            action = "create"
            response = json.loads(cronjob(action=action, **common))
        if not response.get("success"):
            fail(f"{action} failed for {name!r}: {response.get('error', response)}")

        job = resolve_job_ref(name)
        if not job:
            fail(f"cron job {name!r} disappeared after {action}")
        expected = {
            "name": name,
            "schedule_display": definition["schedule"],
            "prompt": prompt,
            "deliver": definition["deliver"],
            "skills": definition["skills"],
            "script": definition["script"],
            "no_agent": definition["noAgent"],
            "enabled_toolsets": definition["enabledToolsets"],
            "workdir": definition["workdir"],
        }
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
