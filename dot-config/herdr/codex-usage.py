#!/usr/bin/env python3

"""OpenAI Codex subscription usage for Herdr's Glyph Rail.

This is read-only: Hermes or the Codex CLI owns OAuth refresh and rotation.
"""

from __future__ import annotations

import json
import math
import os
import time
import urllib.request
from pathlib import Path
from typing import Any, Optional, Tuple

CACHE_TTL = 300
REQUEST_TIMEOUT = 4
OPENAI_GLYPH = ""  # U+EC81, Nerd Fonts cod-openai


def cache_path() -> Path:
    return Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "herdr-codex-usage-cache"


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def row_credentials(row: Any) -> Optional[Tuple[str, str]]:
    if not isinstance(row, dict):
        return None
    token = str(row.get("access_token") or "").strip()
    base_url = str(row.get("base_url") or "").strip()
    if token:
        return token, base_url
    tokens = row.get("tokens")
    if isinstance(tokens, dict):
        token = str(tokens.get("access_token") or "").strip()
        if token:
            return token, base_url
    return None


def load_credentials() -> Optional[Tuple[str, str]]:
    home = Path.home()
    hermes_home = Path(os.environ.get("HERMES_HOME", home / ".hermes"))
    hermes_auth = read_json(hermes_home / "auth.json")

    pool = (hermes_auth.get("credential_pool") or {}).get("openai-codex")
    if isinstance(pool, list):
        for row in pool:
            credentials = row_credentials(row)
            if credentials:
                return credentials

    providers = hermes_auth.get("providers") or {}
    if isinstance(providers, dict):
        credentials = row_credentials(providers.get("openai-codex"))
        if credentials:
            return credentials

    codex_auth = read_json(home / ".codex" / "auth.json")
    credentials = row_credentials(codex_auth)
    if credentials:
        return credentials
    return row_credentials(codex_auth.get("tokens"))


def usage_url(base_url: str) -> str:
    normalized = (base_url or "https://chatgpt.com/backend-api/codex").rstrip("/")
    if normalized.endswith("/codex"):
        normalized = normalized[: -len("/codex")]
    suffix = "/wham/usage" if "/backend-api" in normalized else "/api/codex/usage"
    return normalized + suffix


def window_label(seconds: Any, fallback: str) -> str:
    if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or seconds <= 0:
        return fallback
    value = int(seconds)
    if value % 86_400 == 0:
        return f"{value // 86_400}d"
    if value % 3_600 == 0:
        return f"{value // 3_600}h"
    return f"{max(1, value // 60)}m"


def reset_countdown(reset_at: Any, now: int) -> str:
    if not isinstance(reset_at, (int, float)) or isinstance(reset_at, bool):
        return ""
    remaining = max(0, int(reset_at) - now)
    if remaining >= 86_400:
        days, remainder = divmod(remaining, 86_400)
        return f"{days}d{remainder // 3_600}h"
    hours, remainder = divmod(remaining, 3_600)
    return f"{hours}:{remainder // 60:02d}"


def render_usage(payload: Any, now: int) -> str:
    if not isinstance(payload, dict):
        return ""
    rate_limit = payload.get("rate_limit")
    if not isinstance(rate_limit, dict):
        return ""

    parts = []
    for key, fallback in (("primary_window", "5h"), ("secondary_window", "7d")):
        window = rate_limit.get(key)
        if not isinstance(window, dict):
            continue
        used = window.get("used_percent")
        if (
            not isinstance(used, (int, float))
            or isinstance(used, bool)
            or not math.isfinite(used)
        ):
            continue
        percent = max(0, min(100, math.floor(float(used) + 0.5)))
        label = window_label(window.get("limit_window_seconds"), fallback)
        part = f"{label} {percent}%"
        countdown = reset_countdown(window.get("reset_at"), now)
        if countdown:
            part += f" ↻{countdown}"
        parts.append(part)

    if not parts:
        return ""
    return f"{OPENAI_GLYPH} " + " · ".join(parts)


def read_cache(*, fresh_only: bool) -> str:
    path = cache_path()
    try:
        if fresh_only and time.time() - path.stat().st_mtime >= CACHE_TTL:
            return ""
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def write_cache(output: str) -> None:
    path = cache_path()
    temporary = path.with_name(path.name + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(output + "\n", encoding="utf-8")
        temporary.replace(path)
    except OSError:
        try:
            temporary.unlink()
        except OSError:
            pass


def fetch_usage(token: str, base_url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        usage_url(base_url),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "codex-cli",
        },
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        payload = json.loads(response.read())
    return payload if isinstance(payload, dict) else {}


def main() -> None:
    cached = read_cache(fresh_only=True)
    if cached:
        print(cached)
        return

    credentials = load_credentials()
    if credentials:
        try:
            output = render_usage(fetch_usage(*credentials), int(time.time()))
        except Exception:
            output = ""
        if output:
            write_cache(output)
            print(output)
            return

    stale = read_cache(fresh_only=False)
    if stale:
        print(stale)


if __name__ == "__main__":
    main()
