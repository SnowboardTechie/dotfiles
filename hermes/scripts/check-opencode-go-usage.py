#!/usr/bin/env python3
"""Estimate OpenCode Go allowance use from Hermes's own records and alert at thresholds.

OpenCode Go has one allowance shared by every paid model (OpenCode support, opencode#54875).
Each request costs the model's token prices, weighted by the model's listed monthly limit:
on the Go plan a $60 model counts at face value and a $15 model four times. The plan's pool
is $60 a month, with a 5-hour window of 20% and a weekly window of 50%.

The console is authoritative and has no API, so this script estimates use from Hermes's
`session_model_usage` rows in every profile's state.db (read-only). It does not see
OpenCode's own app or anything outside Hermes. Prices are Go's published table, read
2026-11-04; update PRICES when OpenCode changes them.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

MENTION = "@bryan:snowboardtechie.com"
HERMES_HOME = Path(os.environ.get("HERMES_ROOT", Path.home() / ".hermes"))
DEFAULT_STATE = Path.home() / ".local/state/hermes/opencode-go-usage.json"
PROVIDER = "opencode-go"
GO_POOL_USD = 60.0  # $10 Go plan: the face value of a $60-limit model's monthly allowance
WINDOWS = {"5-hour": (dt.timedelta(hours=5), 0.20), "weekly": (dt.timedelta(days=7), 0.50)}
THRESHOLDS = (0.5, 0.8, 0.95)
MENTION_AT = 0.8
PACIFIC = dt.timezone(dt.timedelta(hours=-8))

# model: (input, output, cache_read, cache_write or None for input price, Go monthly limit)
# Per 1M tokens. Lower-tier prices (the first context band, DeepSeek off-peak) are used;
# DEEPSEEK_PEAK doubles DeepSeek inside its peak hours.
PRICES: dict[str, tuple[float, float, float, float | None, float]] = {
    "glm-5.3-flash": (0.15, 0.50, 0.03, None, 60),
    "glm-5.3": (1.40, 4.40, 0.26, None, 15),
    "glm-5.2": (1.40, 4.40, 0.26, None, 60),
    "kimi-k3.1-pro": (2.00, 10.00, 0.20, 2.00, 15),
    "kimi-k3": (3.00, 15.00, 0.30, 3.00, 15),
    "kimi-k2.7-code": (0.95, 4.00, 0.19, None, 60),
    "longcat-2.0": (0.30, 1.20, 0.006, None, 60),
    "step-5-preview": (1.00, 2.70, 0.10, None, 15),
    "mimo-v2.6-flash": (0.14, 0.28, 0.0028, None, 60),
    "mimo-v2.6-pro": (0.435, 0.87, 0.003625, None, 15),
    "mimo-v2.5": (0.14, 0.28, 0.0028, None, 60),
    "mimo-v2.5-pro": (0.435, 0.87, 0.003625, None, 15),
    "minimax-m3.1-flash": (0.15, 0.60, 0.015, None, 20),
    "minimax-m3": (0.30, 1.20, 0.06, None, 60),
    "qwen3.8-max": (2.00, 6.00, 0.25, 2.50, 15),
    "qwen3.8-flash": (0.15, 0.47, 0.016, 0.20, 30),
    "qwen3.7-plus": (0.40, 1.60, 0.04, 0.50, 60),
    "deepseek-v4.1-flash": (0.15, 0.60, 0.003, None, 100),
    "deepseek-v4-pro": (0.66, 1.98, 0.022, None, 15),
    "hy4-preview": (0.834, 2.501, 0.042, None, 30),
    "hy3": (0.14, 0.58, 0.035, None, 60),
    "grok-4.7": (2.00, 6.00, 0.50, None, 15),
    "gpt-6-luna": (0.10, 0.50, 0.01, 0.125, 15),
    "gpt-5.6-luna": (0.20, 1.20, 0.02, 0.25, 15),
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125, 15),
    "gemini-4-argon": (2.00, 10.00, 0.10, None, 30),  # 50% off through 2026-11-30
}
UNKNOWN_MODEL = (3.00, 15.00, 0.30, 3.00, 15)  # count an unpriced model like the dearest one
FREE_MODELS = {"beam-free", "iceman-contributor-free"}
DEEPSEEK_PEAK_UTC = ((1, 4), (6, 10))  # Mon-Fri


def model_key(model: str) -> str:
    return model.split("/", 1)[-1].strip().lower()


def deepseek_peak(moment: dt.datetime) -> bool:
    if moment.weekday() >= 5:
        return False
    return any(start <= moment.hour < end for start, end in DEEPSEEK_PEAK_UTC)


def allowance_usd(row: dict) -> float:
    """Pool cost of one usage row at face value of the $60 tier."""
    key = model_key(row["model"])
    if key in FREE_MODELS:
        return 0.0
    price_in, price_out, price_read, price_write, limit = PRICES.get(key, UNKNOWN_MODEL)
    if price_write is None:
        price_write = price_in
    cost = (
        row["input_tokens"] * price_in
        + row["output_tokens"] * price_out
        + row["cache_read_tokens"] * price_read
        + row["cache_write_tokens"] * price_write
    ) / 1_000_000
    if key.startswith("deepseek") and row.get("last_seen"):
        seen = dt.datetime.fromtimestamp(row["last_seen"], dt.timezone.utc)
        if deepseek_peak(seen):
            cost *= 2
    return cost * (60.0 / limit)


def state_dbs(root: Path) -> list[tuple[str, Path]]:
    found = []
    if (root / "state.db").exists():
        found.append(("default", root / "state.db"))
    profiles = root / "profiles"
    if profiles.is_dir():
        for child in sorted(profiles.iterdir()):
            if (child / "state.db").exists():
                found.append((child.name, child / "state.db"))
    return found


def read_rows(root: Path, since: float) -> list[dict]:
    rows: list[dict] = []
    for profile, path in state_dbs(root):
        try:
            connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
        except sqlite3.Error:
            continue
        try:
            connection.row_factory = sqlite3.Row
            cursor = connection.execute(
                "SELECT model, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,"
                " first_seen, last_seen FROM session_model_usage"
                " WHERE billing_provider = ? AND COALESCE(last_seen, 0) >= ?",
                (PROVIDER, since),
            )
            for record in cursor:
                row = dict(record)
                row["profile"] = profile
                rows.append(row)
        except sqlite3.Error:
            pass
        finally:
            connection.close()
    return rows


def share_in_window(row: dict, start: float, end: float) -> float:
    """Spread a row's cost evenly over its active span and keep the part inside the window."""
    first = row.get("first_seen") or row.get("last_seen") or end
    last = row.get("last_seen") or first
    if last <= first:
        return 1.0 if start <= last <= end else 0.0
    overlap = max(0.0, min(last, end) - max(first, start))
    return overlap / (last - first)


def cycle_start(now: dt.datetime, cycle_day: int) -> dt.datetime:
    local = now.astimezone(PACIFIC)
    year, month = local.year, local.month
    if local.day < cycle_day:
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return dt.datetime(year, month, cycle_day, tzinfo=PACIFIC)


def measure(root: Path, now: dt.datetime, pool: float, cycle_day: int) -> dict:
    month_start = cycle_start(now, cycle_day)
    rows = read_rows(root, month_start.timestamp())
    end = now.timestamp()
    spans = {"monthly": (month_start.timestamp(), pool)}
    for name, (length, fraction) in WINDOWS.items():
        spans[name] = ((now - length).timestamp(), pool * fraction)
    result: dict = {"as_of": now.isoformat(timespec="seconds"), "pool_usd": pool, "windows": {}}
    for name, (start, limit) in spans.items():
        used = 0.0
        by_model: dict[str, float] = {}
        by_profile: dict[str, float] = {}
        for row in rows:
            part = allowance_usd(row) * share_in_window(row, start, end)
            if part <= 0:
                continue
            used += part
            by_model[model_key(row["model"])] = by_model.get(model_key(row["model"]), 0.0) + part
            by_profile[row["profile"]] = by_profile.get(row["profile"], 0.0) + part
        result["windows"][name] = {
            "used_usd": round(used, 4),
            "limit_usd": round(limit, 2),
            "share": round(used / limit, 4) if limit else 0.0,
            "by_model": {k: round(v, 4) for k, v in sorted(by_model.items(), key=lambda i: -i[1])},
            "by_profile": {k: round(v, 4) for k, v in sorted(by_profile.items(), key=lambda i: -i[1])},
        }
    result["cycle_started"] = month_start.isoformat(timespec="seconds")
    return result


def evaluate(state: dict, measured: dict) -> tuple[dict, list[str]]:
    alerted = state.setdefault("alerted", {})
    crossed: list[tuple[str, float, dict]] = []
    for name, window in measured["windows"].items():
        share = window["share"]
        level = max((t for t in THRESHOLDS if share >= t), default=0.0)
        if level > float(alerted.get(name, 0.0)):
            crossed.append((name, level, window))
        # Follow the share down as the window rolls, so a later rise alerts again.
        alerted[name] = level
    state["last"] = measured
    if not crossed:
        return state, []
    top = max(level for _, level, _ in crossed)
    heading = "OpenCode Go allowance (estimated from Hermes records):"
    if top >= MENTION_AT:
        heading = f"{MENTION} {heading}"
    lines = [heading]
    for name, _level, window in crossed:
        models = ", ".join(f"{m} ${v:.2f}" for m, v in list(window["by_model"].items())[:3])
        lines.append(
            f"- {name}: {window['share']:.0%} of ${window['limit_usd']:.2f}"
            f" (${window['used_usd']:.2f}; top: {models or 'none'})"
        )
    lines.append("When any window reaches 100%, every paid Go model stops until it resets. Free models keep working.")
    lines.append("The OpenCode console is authoritative: https://opencode.ai/console")
    return state, ["\n".join(lines)]


def load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=Path(os.environ.get("OPENCODE_GO_USAGE_STATE", DEFAULT_STATE)))
    parser.add_argument("--pool-usd", type=float, default=float(os.environ.get("OPENCODE_GO_POOL_USD", GO_POOL_USD)))
    parser.add_argument("--cycle-day", type=int, default=int(os.environ.get("OPENCODE_GO_CYCLE_DAY", 4)))
    parser.add_argument("--report", action="store_true", help="print the current estimate as JSON; no state change")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    now = dt.datetime.now(dt.timezone.utc)
    measured = measure(HERMES_HOME, now, args.pool_usd, args.cycle_day)
    if args.report:
        print(json.dumps(measured, indent=2))
        return 0
    lock_path = args.state.with_suffix(args.state.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state, messages = evaluate(load_state(args.state), measured)
        save_state(args.state, state)
    if messages:
        print("\n\n".join(messages))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
