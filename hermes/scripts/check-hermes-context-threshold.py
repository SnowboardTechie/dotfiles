#!/usr/bin/env python3
"""Repair and verify Bryan's Hermes compression threshold configuration."""

from __future__ import annotations

import argparse
import fcntl
import json
import math
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

MENTION = "@bryan:snowboardtechie.com"
DESIRED_THRESHOLD = 0.75
DESIRED_THRESHOLD_TOKENS = 0


class WatchdogError(RuntimeError):
    """An expected failure whose message is safe to record and deliver."""


def default_hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hermes-home", type=Path, default=default_hermes_home())
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--state-log", type=Path)
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="verify without repairing or appending to the nightly audit log",
    )
    return parser.parse_args(argv)


def load_config(path: Path) -> dict[str, Any]:
    import yaml

    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError):
        # PyYAML parser errors quote the offending source line. Never propagate
        # one because config.yaml can contain inline credentials.
        raise WatchdogError("Hermes config could not be read and parsed safely") from None
    if not isinstance(value, dict):
        raise WatchdogError("Hermes config root is not a mapping")
    return value


def compression_snapshot(config: dict[str, Any]) -> dict[str, Any]:
    section = config.get("compression")
    if not isinstance(section, dict):
        section = {}
    return {
        "enabled": section.get("enabled"),
        "threshold": section.get("threshold"),
        "threshold_tokens": section.get("threshold_tokens"),
        "codex_responses_compact_threshold": section.get(
            "codex_responses_compact_threshold"
        ),
        "target_ratio": section.get("target_ratio"),
    }


def required_repairs(config: dict[str, Any]) -> list[tuple[str, str | None]]:
    current = compression_snapshot(config)
    repairs: list[tuple[str, str | None]] = []
    cap = current["threshold_tokens"]
    if type(cap) is not int or cap != DESIRED_THRESHOLD_TOKENS:
        repairs.append(("compression.threshold_tokens", "0"))
    threshold = current["threshold"]
    if (
        isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or not math.isfinite(float(threshold))
        or not math.isclose(float(threshold), DESIRED_THRESHOLD, abs_tol=1e-12)
    ):
        repairs.append(("compression.threshold", "0.75"))
    if current["enabled"] is not True:
        repairs.append(("compression.enabled", "true"))
    if current["codex_responses_compact_threshold"] is not None:
        repairs.append(("compression.codex_responses_compact_threshold", None))
    return repairs


def run_config_command(
    python: Path,
    source_root: Path,
    hermes_home: Path,
    arguments: list[str],
) -> None:
    environment = os.environ.copy()
    environment["HERMES_HOME"] = str(hermes_home)
    existing_pythonpath = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = str(source_root) + (
        os.pathsep + existing_pythonpath if existing_pythonpath else ""
    )
    completed = subprocess.run(
        [str(python), "-m", "hermes_cli.main", "config", *arguments],
        cwd=source_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if completed.returncode != 0:
        operation = " ".join(arguments[:2])
        raise WatchdogError(
            f"Hermes config {operation} failed with exit code {completed.returncode}"
        )


def repair_config(
    repairs: list[tuple[str, str | None]],
    *,
    python: Path,
    source_root: Path,
    hermes_home: Path,
    applied_keys: list[str] | None = None,
) -> None:
    for key, value in repairs:
        arguments = ["unset", key] if value is None else ["set", key, value]
        run_config_command(
            python,
            source_root,
            hermes_home,
            arguments,
        )
        if applied_keys is not None:
            applied_keys.append(key)
    run_config_command(python, source_root, hermes_home, ["check"])


def resolve_source_root(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.expanduser().resolve()
    configured = os.environ.get("HERMES_SOURCE_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()

    # Cron uses the gateway's Python interpreter. Walk up from that executable
    # instead of assuming a profile home contains its own Hermes checkout.
    executable = Path(sys.executable).resolve()
    for candidate in executable.parents:
        if (candidate / "run_agent.py").is_file() and (
            candidate / "hermes_cli/main.py"
        ).is_file():
            return candidate

    primary_checkout = Path.home() / ".hermes/hermes-agent"
    if primary_checkout.is_dir():
        return primary_checkout.resolve()
    raise WatchdogError("Hermes source root could not be resolved")


def verify_effective_threshold(
    config: dict[str, Any],
    *,
    source_root: Path,
    hermes_home: Path,
) -> dict[str, Any]:
    os.environ["HERMES_HOME"] = str(hermes_home)
    source_text = str(source_root)
    if source_text not in sys.path:
        sys.path.insert(0, source_text)

    from agent.native_compaction import resolve_compact_threshold  # pyright: ignore[reportMissingImports]
    from hermes_cli.config import split_model_config_default  # pyright: ignore[reportMissingImports]
    from run_agent import AIAgent  # pyright: ignore[reportMissingImports]

    model_config = config.get("model")
    if not isinstance(model_config, dict):
        model_config = {}
    model, nested_provider = split_model_config_default(
        model_config.get("model") or model_config.get("default")
    )
    provider = nested_provider or str(model_config.get("provider") or "").strip()
    if not model:
        raise ValueError("active Hermes model is not configured")

    agent = AIAgent(
        model=model,
        provider=provider,
        quiet_mode=True,
        enabled_toolsets=[],
        skip_context_files=True,
        skip_memory=True,
        skip_background_review=True,
        load_soul_identity=False,
    )
    try:
        compressor = agent.context_compressor
        context_length = int(compressor.context_length)
        threshold_percent = float(compressor.threshold_percent)
        threshold_tokens_cap = compressor.threshold_tokens_cap
        local_threshold = int(compressor.threshold_tokens)
        native_threshold = int(
            resolve_compact_threshold(
                getattr(agent, "codex_responses_compact_threshold", None),
                local_threshold,
            )
        )
        expected_native_threshold = int(
            resolve_compact_threshold(None, local_threshold)
        )
    finally:
        close = getattr(agent, "close", None)
        if callable(close):
            close()

    validate_effective_values(
        context_length=context_length,
        threshold_percent=threshold_percent,
        threshold_tokens_cap=threshold_tokens_cap,
        local_threshold=local_threshold,
        native_threshold=native_threshold,
        expected_native_threshold=expected_native_threshold,
    )

    return {
        "model": model,
        "provider": provider,
        "context_length": context_length,
        "threshold_percent": threshold_percent,
        "threshold_tokens_cap": threshold_tokens_cap,
        "local_threshold_tokens": local_threshold,
        "local_threshold_ratio": round(local_threshold / context_length, 6),
        "native_threshold_tokens": native_threshold,
        "native_threshold_ratio": round(native_threshold / context_length, 6),
        "expected_native_threshold_tokens": expected_native_threshold,
    }


def validate_effective_values(
    *,
    context_length: int,
    threshold_percent: float,
    threshold_tokens_cap: int | None,
    local_threshold: int,
    native_threshold: int,
    expected_native_threshold: int,
) -> None:
    if context_length <= 0:
        raise WatchdogError("effective context length is not positive")
    if not math.isclose(threshold_percent, DESIRED_THRESHOLD, abs_tol=1e-12):
        raise WatchdogError(
            f"effective threshold ratio is {threshold_percent}, expected {DESIRED_THRESHOLD}"
        )
    if threshold_tokens_cap is not None:
        raise WatchdogError(
            f"effective absolute threshold cap is {threshold_tokens_cap}, expected no cap"
        )

    expected_local = int(context_length * DESIRED_THRESHOLD)
    if local_threshold != expected_local:
        raise WatchdogError(
            f"effective local threshold is {local_threshold}, expected {expected_local}"
        )
    if context_length > 400_000 and local_threshold <= 256_000:
        raise WatchdogError("effective threshold regressed to the 256000-token default cap")
    if native_threshold != expected_native_threshold:
        raise WatchdogError(
            f"native threshold is {native_threshold}, expected automatic value "
            f"{expected_native_threshold}"
        )

def append_audit(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def safe_error_message(error: Exception) -> str:
    if isinstance(error, WatchdogError):
        return str(error)[:500]
    return f"unexpected {type(error).__name__}"


def run(argv: list[str]) -> int:
    args = parse_args(argv)
    hermes_home = args.hermes_home.expanduser().resolve()
    source_root = resolve_source_root(args.source_root)
    state_log = (
        args.state_log.expanduser()
        if args.state_log is not None
        else hermes_home / "logs/context-threshold-watchdog.jsonl"
    )
    config_path = hermes_home / "config.yaml"
    python = source_root / "venv/bin/python"
    record: dict[str, Any] = {
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "error",
        "attempted_repair_keys": [],
        "applied_repair_keys": [],
        "before": None,
        "after": None,
        "effective": None,
        "error": None,
    }

    lock_path = state_log.with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            if not source_root.is_dir():
                raise WatchdogError("Hermes source root is unavailable")
            if not python.is_file():
                raise WatchdogError("Hermes Python is unavailable")

            before_config = load_config(config_path)
            record["before"] = compression_snapshot(before_config)
            repairs = required_repairs(before_config)
            record["attempted_repair_keys"] = [key for key, _ in repairs]
            if args.diagnose and repairs:
                keys = ", ".join(key for key, _ in repairs)
                raise WatchdogError(f"configuration needs repair: {keys}")
            if repairs:
                repair_config(
                    repairs,
                    python=python,
                    source_root=source_root,
                    hermes_home=hermes_home,
                    applied_keys=record["applied_repair_keys"],
                )
            else:
                run_config_command(
                    python,
                    source_root,
                    hermes_home,
                    ["check"],
                )

            after_config = load_config(config_path)
            record["after"] = compression_snapshot(after_config)
            remaining = required_repairs(after_config)
            if remaining:
                keys = ", ".join(key for key, _ in remaining)
                raise WatchdogError(
                    f"configuration remains incorrect after repair: {keys}"
                )
            record["effective"] = verify_effective_threshold(
                after_config,
                source_root=source_root,
                hermes_home=hermes_home,
            )
            record["status"] = "repaired" if repairs else "healthy"
        except Exception as error:  # noqa: BLE001 - turn failures into a safe audit record
            record["error"] = safe_error_message(error)
            if record["before"] is not None:
                try:
                    record["after"] = compression_snapshot(load_config(config_path))
                except Exception:
                    pass
            if not args.diagnose:
                append_audit(state_log, record)
            raise WatchdogError(str(record["error"])) from None

        if not args.diagnose:
            append_audit(state_log, record)

    effective = record["effective"]
    if args.diagnose:
        print(json.dumps(record, indent=2, sort_keys=True))
    elif record["applied_repair_keys"]:
        keys = ", ".join(record["applied_repair_keys"])
        print(
            f"{MENTION} Hermes context-threshold watchdog repaired {keys} and verified "
            f"the effective trigger: {effective['local_threshold_tokens']:,} / "
            f"{effective['context_length']:,} tokens "
            f"({effective['local_threshold_ratio']:.1%}; native "
            f"{effective['native_threshold_tokens']:,}). Existing sessions keep their "
            "already-loaded settings; new sessions use the repaired configuration."
        )
    return 0


def main() -> int:
    try:
        return run(sys.argv[1:])
    except Exception as error:  # noqa: BLE001 - never expose arbitrary exception details
        print(
            f"{MENTION} Hermes context-threshold watchdog failed: "
            f"{safe_error_message(error)}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
