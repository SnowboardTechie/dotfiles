#!/usr/bin/env python3
"""Record the bounded five-run issue-work efficiency pilot."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta
import fcntl
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
from typing import Any, Iterator


TARGET_RUNS = 5
REQUIRED_FIELDS = {
    "task_shape",
    "exploration_children",
    "claude_prompts",
    "correction_passes",
    "review_invocations",
    "targeted_risk_reviews",
    "provider_capacity_start",
    "provider_capacity_end",
    "blocking_findings_after_initial_review",
    "elapsed_to_reviewable_pr_seconds",
    "quota_interruptions",
    "completed_at",
}
COUNT_FIELDS = {
    "exploration_children",
    "claude_prompts",
    "correction_passes",
    "review_invocations",
    "targeted_risk_reviews",
    "blocking_findings_after_initial_review",
    "elapsed_to_reviewable_pr_seconds",
    "quota_interruptions",
}


class PilotError(RuntimeError):
    """Raised when the pilot record cannot be admitted safely."""


def _target(path: Path) -> Path:
    expanded = path.expanduser()
    if not expanded.is_absolute():
        raise PilotError("pilot path must be absolute")
    target = expanded.parent.resolve() / expanded.name
    if target.is_symlink():
        raise PilotError(f"pilot path must not be a symlink: {target}")
    if not target.parent.is_dir():
        raise PilotError(f"pilot parent must already exist: {target.parent}")
    return target


def _issue_key(issue_url: str) -> str:
    canonical = issue_url.strip()
    if not canonical:
        raise PilotError("issue URL must not be empty")
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    target = _target(path)
    if not target.exists():
        return {"version": 1, "target_runs": TARGET_RUNS, "records": []}
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PilotError(f"could not read pilot: {exc}") from exc
    if not isinstance(value, dict):
        raise PilotError("pilot must be a JSON object")
    if value.get("version") != 1 or value.get("target_runs") != TARGET_RUNS:
        raise PilotError("unsupported pilot schema")
    records = value.get("records")
    if not isinstance(records, list) or len(records) > TARGET_RUNS:
        raise PilotError("pilot records are malformed")
    sequences = [item.get("sequence") for item in records if isinstance(item, dict)]
    if sequences != list(range(1, len(records) + 1)):
        raise PilotError("pilot sequence is malformed")
    for record in records:
        _validate_persisted_record(record)
    issue_keys = [record["issue_key"] for record in records]
    if len(issue_keys) != len(set(issue_keys)):
        raise PilotError("pilot contains duplicate issue keys")
    return value


def _atomic_write(path: Path, value: dict[str, Any]) -> None:
    target = _target(path)
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    temp_path = Path(temporary)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, target)
    finally:
        if temp_path.exists():
            temp_path.unlink()


@contextmanager
def _locked(path: Path) -> Iterator[None]:
    target = _target(path)
    lock_path = target.with_name(f".{target.name}.lock")
    if lock_path.is_symlink():
        raise PilotError(f"pilot lock must not be a symlink: {lock_path}")
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _validate_record(record: dict[str, Any]) -> dict[str, Any]:
    missing = sorted(REQUIRED_FIELDS - record.keys())
    unknown = sorted(record.keys() - REQUIRED_FIELDS)
    if missing:
        raise PilotError("record missing fields: " + ", ".join(missing))
    if unknown:
        raise PilotError("record has unknown fields: " + ", ".join(unknown))
    if record["task_shape"] not in {"single-loop", "substantial"}:
        raise PilotError("task_shape must be single-loop or substantial")
    for field in COUNT_FIELDS:
        value = record[field]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise PilotError(f"{field} must be a non-negative integer")
    if record["correction_passes"] > 2:
        raise PilotError("correction_passes must not exceed 2")
    for field in ("provider_capacity_start", "provider_capacity_end"):
        value = record[field]
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100
        ):
            raise PilotError(f"{field} must be null or an integer from 0 to 100")
    if not isinstance(record["completed_at"], str) or not record["completed_at"].strip():
        raise PilotError("completed_at must be a non-empty timestamp")
    _parse_timestamp(record["completed_at"], field="completed_at")
    return dict(record)


def _parse_timestamp(value: str, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise PilotError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise PilotError(f"{field} must include a timezone")
    return parsed


def _validate_persisted_record(record: dict[str, Any]) -> None:
    if not isinstance(record, dict):
        raise PilotError("pilot record must be a JSON object")
    persisted_fields = REQUIRED_FIELDS | {
        "issue_key",
        "sequence",
        "escaped_critical_major",
        "escaped_assessed_at",
    }
    unknown = sorted(record.keys() - persisted_fields)
    if unknown:
        raise PilotError("pilot record has unknown fields: " + ", ".join(unknown))
    metrics = {field: record[field] for field in REQUIRED_FIELDS if field in record}
    _validate_record(metrics)
    issue_key = record.get("issue_key")
    if not isinstance(issue_key, str) or len(issue_key) != 64 or any(
        character not in "0123456789abcdef" for character in issue_key
    ):
        raise PilotError("pilot record issue_key is malformed")
    escaped = record.get("escaped_critical_major")
    if not isinstance(escaped, list):
        raise PilotError("escaped_critical_major must be a list")
    for observation in escaped:
        if not isinstance(observation, dict):
            raise PilotError("escaped observation must be an object")
        if set(observation) != {"severity", "reference", "assessed_at"}:
            raise PilotError("escaped observation fields are malformed")
        if observation.get("severity") not in {"Critical", "Major"}:
            raise PilotError("escaped observation severity is malformed")
        if not isinstance(observation.get("reference"), str) or not observation[
            "reference"
        ].strip():
            raise PilotError("escaped observation reference is malformed")
        _parse_timestamp(observation.get("assessed_at", ""), field="assessed_at")
    assessed_at = record.get("escaped_assessed_at")
    if assessed_at is not None:
        if not isinstance(assessed_at, str):
            raise PilotError("escaped_assessed_at is malformed")
        assessed_time = _parse_timestamp(assessed_at, field="escaped_assessed_at")
        completed_time = _parse_timestamp(record["completed_at"], field="completed_at")
        if assessed_time < completed_time + timedelta(days=7):
            raise PilotError("escaped_assessed_at is earlier than the seven-day window")


def record_run(*, pilot_path: Path, issue_url: str, record: dict[str, Any]) -> dict[str, Any]:
    metrics = _validate_record(record)
    issue_key = _issue_key(issue_url)
    with _locked(pilot_path):
        pilot = _load(pilot_path)
        records = pilot["records"]
        existing = next((item for item in records if item.get("issue_key") == issue_key), None)
        if existing is None:
            if len(records) >= TARGET_RUNS:
                raise PilotError("pilot already has five runs")
            existing = {
                "issue_key": issue_key,
                "sequence": len(records) + 1,
                "escaped_critical_major": [],
                "escaped_assessed_at": None,
            }
            records.append(existing)
        escaped = list(existing.get("escaped_critical_major", []))
        assessed_at = existing.get("escaped_assessed_at")
        sequence = existing["sequence"]
        existing.clear()
        existing.update(metrics)
        existing.update(
            {
                "issue_key": issue_key,
                "sequence": sequence,
                "escaped_critical_major": escaped,
                "escaped_assessed_at": assessed_at,
            }
        )
        _atomic_write(pilot_path, pilot)
        return dict(existing)


def _find_record(pilot: dict[str, Any], issue_url: str) -> dict[str, Any]:
    issue_key = _issue_key(issue_url)
    record = next(
        (item for item in pilot["records"] if item.get("issue_key") == issue_key),
        None,
    )
    if record is None:
        raise PilotError("issue is not one of the five pilot runs")
    return record


def record_escape(
    *,
    pilot_path: Path,
    issue_url: str,
    severity: str,
    reference: str,
    assessed_at: str,
) -> dict[str, Any]:
    if severity not in {"Critical", "Major"}:
        raise PilotError("severity must be Critical or Major")
    if not reference.strip() or not assessed_at.strip():
        raise PilotError("reference and assessed_at must not be empty")
    _parse_timestamp(assessed_at, field="assessed_at")
    with _locked(pilot_path):
        pilot = _load(pilot_path)
        record = _find_record(pilot, issue_url)
        observation = {
            "severity": severity,
            "reference": reference.strip(),
            "assessed_at": assessed_at.strip(),
        }
        if observation not in record["escaped_critical_major"]:
            record["escaped_critical_major"].append(observation)
        _atomic_write(pilot_path, pilot)
        return dict(record)


def assess_escape_window(
    *, pilot_path: Path, issue_url: str, assessed_at: str
) -> dict[str, Any]:
    if not assessed_at.strip():
        raise PilotError("assessed_at must not be empty")
    assessed_time = _parse_timestamp(assessed_at, field="assessed_at")
    with _locked(pilot_path):
        pilot = _load(pilot_path)
        record = _find_record(pilot, issue_url)
        completed_time = _parse_timestamp(record["completed_at"], field="completed_at")
        if assessed_time < completed_time + timedelta(days=7):
            raise PilotError("escape assessment must wait seven days after completion")
        record["escaped_assessed_at"] = assessed_at.strip()
        _atomic_write(pilot_path, pilot)
        return dict(record)


def report(pilot_path: Path) -> dict[str, Any]:
    pilot = _load(pilot_path)
    records = pilot["records"]
    elapsed = [item["elapsed_to_reviewable_pr_seconds"] for item in records]
    return {
        "target_runs": TARGET_RUNS,
        "completed_runs": len(records),
        "evaluation_ready": len(records) == TARGET_RUNS
        and all(item.get("escaped_assessed_at") for item in records),
        "claude_prompts": sum(item["claude_prompts"] for item in records),
        "review_invocations": sum(item["review_invocations"] for item in records),
        "quota_interruptions": sum(item["quota_interruptions"] for item in records),
        "escaped_critical_major_count": sum(
            len(item["escaped_critical_major"]) for item in records
        ),
        "median_elapsed_to_reviewable_pr_seconds": (
            statistics.median(elapsed) if elapsed else None
        ),
    }


def _read_record_file(path: Path) -> dict[str, Any]:
    target = path.expanduser().resolve()
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PilotError(f"could not read record file: {exc}") from exc
    if not isinstance(value, dict):
        raise PilotError("record file must contain a JSON object")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    record = subparsers.add_parser("record")
    record.add_argument("--pilot", type=Path, required=True)
    record.add_argument("--issue-url", required=True)
    record.add_argument("--record-file", type=Path, required=True)

    escape = subparsers.add_parser("record-escape")
    escape.add_argument("--pilot", type=Path, required=True)
    escape.add_argument("--issue-url", required=True)
    escape.add_argument("--severity", choices=("Critical", "Major"), required=True)
    escape.add_argument("--reference", required=True)
    escape.add_argument("--assessed-at", required=True)

    assess = subparsers.add_parser("assess")
    assess.add_argument("--pilot", type=Path, required=True)
    assess.add_argument("--issue-url", required=True)
    assess.add_argument("--assessed-at", required=True)

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--pilot", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "record":
            result = record_run(
                pilot_path=args.pilot,
                issue_url=args.issue_url,
                record=_read_record_file(args.record_file),
            )
        elif args.command == "record-escape":
            result = record_escape(
                pilot_path=args.pilot,
                issue_url=args.issue_url,
                severity=args.severity,
                reference=args.reference,
                assessed_at=args.assessed_at,
            )
        elif args.command == "assess":
            result = assess_escape_window(
                pilot_path=args.pilot,
                issue_url=args.issue_url,
                assessed_at=args.assessed_at,
            )
        else:
            result = report(args.pilot)
    except (PilotError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps({"ok": True, **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
