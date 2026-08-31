#!/usr/bin/env python3
"""Validate exact-candidate multiagent PR review artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, NoReturn


CANDIDATE_FIELDS = ("base_sha", "head_sha", "merge_base_sha", "diff_sha256")
ROUTE_FIELDS = ("surface", "agent_name", "pane_id", "runtime_session_id")
PRIMARY_LANES = ("standards", "spec", "correctness")
FINAL_LANE = "ponytail"


class ValidationError(Exception):
    """A deterministic validation failure safe to expose by error code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise ValidationError("INVALID_ARGUMENTS")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def confined_path(root: Path, value: str | Path) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as error:
        raise ValidationError("PATH_MISSING") from error
    try:
        common = Path(os.path.commonpath((str(root), str(resolved))))
    except ValueError as error:
        raise ValidationError("PATH_ESCAPE") from error
    if common != root:
        raise ValidationError("PATH_ESCAPE")
    return resolved


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValidationError("INVALID_JSON") from error
    if not isinstance(value, dict):
        raise ValidationError("INVALID_JSON")
    return value


def parse_frontmatter(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ValidationError("INVALID_FRONTMATTER") from error
    match = re.match(r"\A---\n(.*?)\n---(?:\n|\Z)", text, re.DOTALL)
    if not match:
        raise ValidationError("INVALID_FRONTMATTER")
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line or line.startswith((" ", "\t")) or ":" not in line:
            raise ValidationError("INVALID_FRONTMATTER")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value or key in fields:
            raise ValidationError("INVALID_FRONTMATTER")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        fields[key] = value
    return fields


def candidate_identity(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValidationError("CANDIDATE_MISMATCH")
    identity: dict[str, str] = {}
    for field in CANDIDATE_FIELDS:
        item = value.get(field)
        if not isinstance(item, str) or not item:
            raise ValidationError("CANDIDATE_MISMATCH")
        identity[field] = item
    return identity


def require_candidate_fields(fields: dict[str, str], expected: dict[str, str]) -> None:
    if any(fields.get(field) != expected[field] for field in CANDIDATE_FIELDS):
        raise ValidationError("CANDIDATE_MISMATCH")


def expected_models(values: list[str]) -> dict[str, re.Pattern[str]]:
    predicates: dict[str, re.Pattern[str]] = {}
    for value in values:
        family, separator, pattern = value.partition("=")
        if not separator or not family or not pattern or family in predicates:
            raise ValidationError("INVALID_ARGUMENTS")
        try:
            predicates[family] = re.compile(pattern)
        except re.error as error:
            raise ValidationError("INVALID_MODEL_PREDICATE") from error
    if not predicates:
        raise ValidationError("INVALID_ARGUMENTS")
    return predicates


def derived_lanes(manifest: dict[str, Any]) -> list[str]:
    selection = manifest.get("lane_selection")
    if not isinstance(selection, dict) or not isinstance(selection.get("risk_selected"), bool):
        raise ValidationError("INVALID_MANIFEST")
    lanes: list[str] = list(PRIMARY_LANES)
    if selection["risk_selected"]:
        lanes.append("risk")
    lanes.append(FINAL_LANE)
    return lanes


def verify_manifest_files(root: Path, manifest: dict[str, Any]) -> None:
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ValidationError("INVALID_MANIFEST")
    seen: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            raise ValidationError("INVALID_MANIFEST")
        relative = item.get("path")
        expected_hash = item.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected_hash, str) or relative in seen:
            raise ValidationError("INVALID_MANIFEST")
        seen.add(relative)
        path = confined_path(root, relative)
        if sha256(path) != expected_hash:
            raise ValidationError("EVIDENCE_HASH_MISMATCH")


def verify_route(sidecar: dict[str, Any]) -> None:
    route = sidecar.get("route_evidence")
    if not isinstance(route, dict):
        raise ValidationError("ROUTE_INCOMPLETE")
    for field in ROUTE_FIELDS:
        if not isinstance(route.get(field), str) or not route[field].strip():
            raise ValidationError("ROUTE_INCOMPLETE")
    if route["surface"] != "herdr":
        raise ValidationError("ROUTE_INCOMPLETE")


def verify_models(
    sidecar: dict[str, Any], predicate: re.Pattern[str]
) -> None:
    primary = sidecar.get("primary_model")
    observed = sidecar.get("models_used")
    if not isinstance(primary, str) or not isinstance(observed, list) or not observed:
        raise ValidationError("MODEL_MISMATCH")
    models = [primary, *observed]
    if any(not isinstance(model, str) or not predicate.search(model) for model in models):
        raise ValidationError("MODEL_MISMATCH")


def verify_lanes(
    root: Path,
    sidecar: dict[str, Any],
    family: str,
    expected_candidate: dict[str, str],
    manifest_sha: str,
    required_lanes: list[str],
) -> None:
    artifacts = sidecar.get("lane_artifacts")
    if not isinstance(artifacts, list):
        raise ValidationError("MISSING_LANE")
    by_lane: dict[str, dict[str, Any]] = {}
    for item in artifacts:
        if not isinstance(item, dict) or not isinstance(item.get("lane"), str):
            raise ValidationError("INVALID_LANE_ARTIFACT")
        lane = item["lane"]
        if lane in by_lane:
            raise ValidationError("DUPLICATE_LANE")
        by_lane[lane] = item

    expected_set = set(required_lanes)
    actual_set = set(by_lane)
    if "risk" in actual_set and "risk" not in expected_set:
        raise ValidationError("UNEXPECTED_LANE")
    if expected_set - actual_set:
        raise ValidationError("MISSING_LANE")
    if actual_set - expected_set:
        raise ValidationError("UNEXPECTED_LANE")

    declared = sidecar.get("required_lanes")
    if declared != required_lanes:
        raise ValidationError("REQUIRED_LANES_MISMATCH")

    for lane in required_lanes:
        item = by_lane[lane]
        relative = item.get("path")
        expected_hash = item.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected_hash, str):
            raise ValidationError("INVALID_LANE_ARTIFACT")
        path = confined_path(root, relative)
        if sha256(path) != expected_hash:
            raise ValidationError("LANE_HASH_MISMATCH")
        fields = parse_frontmatter(path)
        if (
            fields.get("lane") != lane
            or fields.get("reviewer_family") != family
            or fields.get("evidence_manifest_sha256") != manifest_sha
        ):
            raise ValidationError("LANE_IDENTITY_MISMATCH")
        require_candidate_fields(fields, expected_candidate)


def verify_report(
    root: Path,
    sidecar: dict[str, Any],
    family: str,
    pr_url: str,
    expected_candidate: dict[str, str],
    manifest_sha: str,
) -> str:
    relative = sidecar.get("report_path")
    expected_hash = sidecar.get("report_sha256")
    if not isinstance(relative, str) or not isinstance(expected_hash, str):
        raise ValidationError("INVALID_REPORT")
    path = confined_path(root, relative)
    actual_hash = sha256(path)
    if actual_hash != expected_hash:
        raise ValidationError("REPORT_HASH_MISMATCH")
    fields = parse_frontmatter(path)
    if (
        fields.get("type") != "multiagent-pr-model-review"
        or fields.get("status") != "advisory"
        or fields.get("canonical") != "false"
        or fields.get("pr_url") != pr_url
        or fields.get("reviewer_family") != family
        or fields.get("evidence_manifest_sha256") != manifest_sha
    ):
        raise ValidationError("INVALID_FRONTMATTER")
    require_candidate_fields(fields, expected_candidate)
    return actual_hash


def validate_sidecar(
    root: Path,
    path: Path,
    family: str,
    predicate: re.Pattern[str],
    manifest: dict[str, Any],
    manifest_sha: str,
    required_lanes: list[str],
) -> dict[str, str]:
    sidecar = load_json(path)
    if sidecar.get("reviewer_family") != family:
        raise ValidationError("WRONG_REVIEWER_FAMILY")
    if candidate_identity(sidecar.get("candidate_identity")) != candidate_identity(
        manifest.get("candidate_identity")
    ):
        raise ValidationError("CANDIDATE_MISMATCH")
    if sidecar.get("evidence_manifest_sha256") != manifest_sha:
        raise ValidationError("MANIFEST_HASH_MISMATCH")
    verify_route(sidecar)
    verify_models(sidecar, predicate)
    expected_candidate = candidate_identity(manifest.get("candidate_identity"))
    verify_lanes(
        root,
        sidecar,
        family,
        expected_candidate,
        manifest_sha,
        required_lanes,
    )
    report_hash = verify_report(
        root,
        sidecar,
        family,
        str(manifest.get("pr_url", "")),
        expected_candidate,
        manifest_sha,
    )
    return {"reviewer_family": family, "report_sha256": report_hash}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = JsonArgumentParser(description=__doc__)
    parser.add_argument("--state-root", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--report-sidecar", action="append", default=[])
    parser.add_argument("--expected-model", action="append", default=[])
    return parser.parse_args(argv)


def run(argv: list[str]) -> dict[str, Any]:
    args = parse_args(argv)
    try:
        root = Path(args.state_root).resolve(strict=True)
    except OSError as error:
        raise ValidationError("PATH_MISSING") from error
    if not root.is_dir():
        raise ValidationError("PATH_MISSING")

    manifest_path = confined_path(root, args.manifest)
    if sha256(manifest_path) != args.manifest_sha256:
        raise ValidationError("MANIFEST_HASH_MISMATCH")
    manifest = load_json(manifest_path)
    if not isinstance(manifest.get("pr_url"), str) or not manifest["pr_url"]:
        raise ValidationError("INVALID_MANIFEST")
    candidate_identity(manifest.get("candidate_identity"))
    verify_manifest_files(root, manifest)
    required_lanes = derived_lanes(manifest)
    predicates = expected_models(args.expected_model)

    sidecars: dict[str, Path] = {}
    unknown_sidecars: list[Path] = []
    for value in args.report_sidecar:
        path = confined_path(root, value)
        sidecar = load_json(path)
        family = sidecar.get("reviewer_family")
        if not isinstance(family, str) or family not in predicates:
            unknown_sidecars.append(path)
            continue
        if family in sidecars:
            raise ValidationError("DUPLICATE_REPORT")
        sidecars[family] = path
    if unknown_sidecars:
        raise ValidationError("WRONG_REVIEWER_FAMILY")
    if set(sidecars) != set(predicates):
        raise ValidationError("MISSING_REPORT")

    reports = [
        validate_sidecar(
            root,
            sidecars[family],
            family,
            predicate,
            manifest,
            args.manifest_sha256,
            required_lanes,
        )
        for family, predicate in predicates.items()
    ]
    if len(reports) == 1:
        return {"ok": True, "status": "ADMITTED", **reports[0]}
    return {"ok": True, "status": "COMPLETE", "reports": reports}


def main(argv: list[str] | None = None) -> int:
    try:
        result = run(sys.argv[1:] if argv is None else argv)
    except ValidationError as error:
        result = {"ok": False, "status": "INCOMPLETE", "error": error.code}
        print(json.dumps(result, sort_keys=True))
        return 1
    except Exception:
        result = {"ok": False, "status": "INCOMPLETE", "error": "INTERNAL_ERROR"}
        print(json.dumps(result, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
