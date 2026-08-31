#!/usr/bin/env python3
"""Upsert one Granola meeting source snapshot into the SGG Hindsight bank."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import tempfile
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

CONFIG_PATH = Path.home() / ".hindsight" / "coding-agent.json"
STAGING_ROOT = Path.home() / ".hermes" / "private" / "sgg-granola-imports"
BANK = "coding-agent::sgg"
MARKER = "GRANOLA MEETING SOURCE v1"
TEMP_NAME = re.compile(r"sgg-granola-import-([0-9a-fA-F-]{36})-[A-Za-z0-9_-]+\.json")
ApiFn = Callable[[str, str, Optional[dict[str, Any]]], dict[str, Any]]


def load_connection() -> tuple[str, str]:
    mode = stat.S_IMODE(CONFIG_PATH.stat().st_mode)
    if mode != 0o600:
        raise RuntimeError(f"{CONFIG_PATH} must be mode 0600 (is {mode:04o})")
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    api_url = str(config.get("apiUrl") or "").rstrip("/")
    token = str(config.get("apiToken") or "")
    if not api_url or not token:
        raise RuntimeError(f"{CONFIG_PATH} is missing apiUrl or apiToken")
    return api_url, token


def api(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    api_url, token = load_connection()
    request = urllib.request.Request(
        api_url + path,
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        raw = response.read()
    return json.loads(raw) if raw else {}


def _secure_staging_root(root: Path, *, create: bool) -> Path:
    expanded = root.expanduser()
    nearest_existing = expanded
    while not nearest_existing.exists() and nearest_existing != nearest_existing.parent:
        nearest_existing = nearest_existing.parent
    if nearest_existing.is_symlink():
        raise ValueError("staging root or its nearest existing parent must not be a symlink")
    existed = expanded.exists()
    if create:
        expanded.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not existed:
            expanded.chmod(0o700)
    if not expanded.is_dir():
        raise ValueError("staging root is missing or is not a directory")
    info = expanded.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError("staging root must be owned by the current user with mode 0700")
    return expanded.resolve()


def prepare_input(meeting_id: str, *, root: Path = STAGING_ROOT) -> Path:
    canonical_id = str(uuid.UUID(meeting_id))
    staging_root = _secure_staging_root(root, create=True)
    descriptor, raw_path = tempfile.mkstemp(
        prefix=f"sgg-granola-import-{canonical_id}-",
        suffix=".json",
        dir=staging_root,
        text=True,
    )
    os.close(descriptor)
    path = Path(raw_path)
    path.chmod(0o600)
    return path


def _validated_input_path(path: Path, *, root: Path = STAGING_ROOT) -> Path:
    resolved = path.expanduser().resolve()
    staging_root = _secure_staging_root(root, create=False)
    if resolved.parent != staging_root or not TEMP_NAME.fullmatch(resolved.name):
        raise ValueError("input must be a helper-created Granola staging file")
    if path.is_symlink() or not resolved.is_file():
        raise ValueError("input must be a regular file, not a symlink")
    info = resolved.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
        raise ValueError("input must be owned by the current user with mode 0600")
    return resolved


def load_payload(path: Path) -> dict[str, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("input JSON must be an object")
    payload = {
        key: str(raw.get(key) or "").strip()
        for key in ("meeting_id", "title", "date", "source_url")
    }
    source_text = raw.get("source_text")
    if not isinstance(source_text, str):
        raise ValueError("source_text must be a string")
    payload["source_text"] = source_text
    if any(not payload[key] for key in ("meeting_id", "title", "date")) or not source_text.strip():
        raise ValueError("meeting_id, title, date, and source_text are required")
    meeting_id = str(uuid.UUID(payload["meeting_id"]))
    match = TEMP_NAME.fullmatch(path.name)
    if not match or str(uuid.UUID(match.group(1))) != meeting_id:
        raise ValueError("input filename UUID must match meeting_id")
    try:
        parsed_date = datetime.fromisoformat(payload["date"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("date must be an ISO-8601 datetime") from exc
    if parsed_date.tzinfo is None:
        raise ValueError("date must include a timezone")
    if len(payload["title"]) > 500:
        raise ValueError("title exceeds 500 characters")
    if len(payload["source_text"]) > 100_000:
        raise ValueError("source_text exceeds 100000 characters")
    payload["meeting_id"] = meeting_id
    payload["date"] = parsed_date.isoformat()
    return payload


def source_document(payload: dict[str, str]) -> str:
    source_url = payload.get("source_url") or "not provided by Granola"
    return "\n".join(
        [
            MARKER,
            f"Meeting ID: {payload['meeting_id']}",
            f"Title: {payload['title']}",
            f"Date: {payload['date']}",
            f"Source URL: {source_url}",
            "Epistemic status: Exact Granola private notes and AI-generated summary; evidence of what the meeting artifact recorded, not canonical current state.",
            "Reconcile actions, proposals, decisions, and reported status against live project sources before acting.",
            "",
            payload["source_text"],
        ]
    )


def _document_text(document: dict[str, Any]) -> str:
    for key in ("text", "original_text", "content"):
        value = document.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def import_meeting(
    path: Path,
    *,
    api_fn: ApiFn = api,
    staging_root: Path = STAGING_ROOT,
) -> dict[str, Any]:
    input_path = _validated_input_path(path, root=staging_root)
    try:
        payload = load_payload(input_path)
        document_id = f"granola-meeting::{payload['meeting_id']}"
        content = source_document(payload)
        metadata = {
            "meeting_id": payload["meeting_id"],
            "title": payload["title"],
            "date": payload["date"],
            "source_url": payload.get("source_url") or "",
            "epistemic_status": "granola-source-artifact",
        }
        item = {
            "content": content,
            "document_id": document_id,
            "update_mode": "replace",
            "timestamp": payload["date"],
            "metadata": metadata,
            "tags": ["granola-meeting", "source:granola", "area:sgg"],
        }
        encoded_bank = urllib.parse.quote(BANK, safe="")
        api_fn("PUT", f"/v1/default/banks/{encoded_bank}", {"name": BANK})
        retain_response = api_fn(
            "POST",
            f"/v1/default/banks/{encoded_bank}/memories",
            {"items": [item], "async": False},
        )
        if retain_response.get("success") is not True or retain_response.get("items_count") != 1:
            raise RuntimeError("Hindsight retain response did not confirm exactly one imported item")
        encoded_document = urllib.parse.quote(document_id, safe="")
        stored = api_fn(
            "GET",
            f"/v1/default/banks/{encoded_bank}/documents/{encoded_document}",
            None,
        )
        stored_text = _document_text(stored)
        if document_id != str(stored.get("id") or ""):
            raise RuntimeError("Hindsight read-back returned a different document ID")
        if stored_text != content:
            raise RuntimeError("Hindsight read-back does not exactly match the imported source document")
        return {
            "status": "imported",
            "bank": BANK,
            "documentId": document_id,
            "verified": True,
        }
    finally:
        input_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--meeting-id", required=True)
    import_parser = subparsers.add_parser("import")
    import_parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = {"inputPath": str(prepare_input(args.meeting_id))}
        else:
            result = import_meeting(args.input)
    except Exception as exc:
        print(f"Granola Hindsight import failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
