#!/usr/bin/env python3
"""Alert once when long-lived Studio services fail or recover."""

from __future__ import annotations

import argparse
import concurrent.futures
import fcntl
import json
import os
import ssl
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import NamedTuple

MENTION = "@bryan:snowboardtechie.com"
FAILURE_THRESHOLD = 3
REQUEST_TIMEOUT_SECONDS = 8
USER_AGENT = "Bryan-Studio-Service-Watchdog/1.0"
DEFAULT_STATE = Path.home() / ".local/state/hermes/studio-service-watchdog.json"


class Probe(NamedTuple):
    name: str
    url: str
    check: str


PROBES = (
    Probe(
        "Hermes Dashboard",
        "https://bryans-mac-studio.tail5ba690.ts.net/api/status",
        "hermes",
    ),
    Probe("Hindsight API", "http://127.0.0.1:8888/health", "hindsight"),
    Probe(
        "Hindsight Control Plane",
        "https://bryans-mac-studio.tail5ba690.ts.net:9444/",
        "hindsight-ui",
    ),
    Probe("Open WebUI", "https://ai.thompson.codes/health", "open-webui"),
    Probe("Grafana", "http://100.121.238.48:3000/api/health", "grafana"),
    Probe("Prometheus", "http://127.0.0.1:9090/-/ready", "prometheus"),
    Probe("Alertmanager", "http://127.0.0.1:9093/-/ready", "alertmanager"),
    Probe("Loki", "http://127.0.0.1:3100/ready", "loki"),
    Probe("Grafana Alloy", "http://127.0.0.1:12345/-/ready", "alloy"),
    Probe("Ollama", "http://127.0.0.1:11434/api/tags", "ollama"),
    Probe("Syncthing", "http://127.0.0.1:8384/rest/noauth/health", "syncthing"),
    Probe("Plex", "http://100.121.238.48:32400/web/index.html", "plex"),
    Probe("Jellyfin", "http://100.121.238.48:8096/health", "jellyfin"),
)


def _json(body: bytes) -> object:
    return json.loads(body.decode("utf-8"))


def response_is_valid(check: str, body: bytes) -> bool:
    if check == "hermes":
        value = _json(body)
        return isinstance(value, dict) and value.get("auth_required") is True
    if check == "hindsight":
        value = _json(body)
        return isinstance(value, dict) and value.get("status") == "healthy"
    if check == "hindsight-ui":
        return b"Hindsight Control Plane" in body
    if check == "open-webui":
        value = _json(body)
        return isinstance(value, dict) and value.get("status") is True
    if check == "grafana":
        value = _json(body)
        return isinstance(value, dict) and value.get("database") == "ok"
    if check == "prometheus":
        return b"Prometheus Server is Ready" in body
    if check == "alertmanager":
        return body.strip() == b"OK"
    if check == "loki":
        return body.strip() == b"ready"
    if check == "alloy":
        return b"Alloy is ready" in body
    if check == "ollama":
        value = _json(body)
        return isinstance(value, dict) and isinstance(value.get("models"), list)
    if check == "syncthing":
        value = _json(body)
        return isinstance(value, dict) and value.get("status") == "OK"
    if check == "plex":
        return b"Plex" in body or b"plex" in body
    if check == "jellyfin":
        return body.strip() == b"Healthy"
    raise ValueError(f"unknown probe check: {check}")


def run_probe(probe: Probe) -> str | None:
    request = urllib.request.Request(probe.url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(
            request,
            timeout=REQUEST_TIMEOUT_SECONDS,
            context=ssl.create_default_context(),
        ) as response:
            status = response.status
            body = response.read(2_000_000)
    except urllib.error.HTTPError as error:
        return f"HTTP {error.code}"
    except (OSError, urllib.error.URLError, TimeoutError) as error:
        detail = str(error.reason if isinstance(error, urllib.error.URLError) else error)
        return f"{type(error).__name__}: {detail[:160]}"
    except Exception as error:  # noqa: BLE001 - convert probe failures into bounded state
        return f"{type(error).__name__}: {str(error)[:160]}"

    if not 200 <= status < 300:
        return f"HTTP {status}"
    try:
        if not response_is_valid(probe.check, body):
            return "unexpected response content"
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as error:
        return f"invalid response: {type(error).__name__}"
    return None


def probe_all() -> dict[str, str | None]:
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        errors = executor.map(run_probe, PROBES)
    return {probe.name: error for probe, error in zip(PROBES, errors)}


def load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("watchdog state must be a JSON object")
    return value


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def evaluate(
    state: dict,
    results: dict[str, str | None],
    *,
    failure_threshold: int = FAILURE_THRESHOLD,
) -> tuple[dict, list[str]]:
    services = state.setdefault("services", {})
    newly_unhealthy: list[tuple[str, str]] = []
    newly_recovered: list[str] = []

    for name, error in results.items():
        record = services.setdefault(
            name, {"failures": 0, "alerted": False, "last_error": None}
        )
        if error is None:
            if record.get("alerted"):
                newly_recovered.append(name)
            record.update({"failures": 0, "alerted": False, "last_error": None})
            continue

        record["failures"] = int(record.get("failures", 0)) + 1
        record["last_error"] = error
        if record["failures"] >= failure_threshold and not record.get("alerted"):
            record["alerted"] = True
            newly_unhealthy.append((name, error))

    for stale_name in set(services) - set(results):
        services.pop(stale_name, None)

    if not newly_unhealthy and not newly_recovered:
        return state, []

    if newly_unhealthy and newly_recovered:
        heading = f"{MENTION} ⚠️ Studio service watchdog detected changes:"
    elif newly_unhealthy:
        heading = f"{MENTION} 🚨 Studio services are unhealthy after {failure_threshold} consecutive checks:"
    else:
        heading = f"{MENTION} ✅ Studio services recovered:"

    lines = [heading]
    if newly_unhealthy:
        lines.append("Unhealthy:")
        lines.extend(f"- {name}: {error}" for name, error in newly_unhealthy)
    if newly_recovered:
        lines.append("Recovered:")
        lines.extend(f"- {name}" for name in newly_recovered)
    lines.append("Investigate the Studio service logs and Grafana Service Health dashboard.")
    return state, ["\n".join(lines)]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--state",
        type=Path,
        default=Path(os.environ.get("STUDIO_SERVICE_WATCHDOG_STATE", DEFAULT_STATE)),
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="print current probe results as JSON without reading or writing state",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    results = probe_all()
    if args.diagnose:
        print(json.dumps({name: error or "healthy" for name, error in results.items()}, indent=2))
        return 1 if any(results.values()) else 0

    lock_path = args.state.with_suffix(args.state.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = load_state(args.state)
        state, messages = evaluate(state, results)
        save_state(args.state, state)
    if messages:
        print("\n\n".join(messages))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
