#!/usr/bin/env python3

"""Integration tests for the Herdr Codex usage module."""

from __future__ import annotations

import contextlib
import io
import json
import os
import runpy
import tempfile
import unittest.mock
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
TRACKER = REPO_ROOT / "dot-config/herdr/codex-usage.py"


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


now = 1_800_000_000
payload = {
    "rate_limit": {
        "primary_window": {
            "used_percent": 21,
            "limit_window_seconds": 18_000,
            "reset_at": now + 3_661,
        },
        "secondary_window": {
            "used_percent": 4,
            "limit_window_seconds": 604_800,
            "reset_at": now + 176_400,
        },
    }
}

with tempfile.TemporaryDirectory(prefix="herdr-codex-usage-test-") as tmp:
    root = Path(tmp)
    home = root / "home"
    runtime = root / "runtime"
    hermes = home / ".hermes"
    hermes.mkdir(parents=True)
    runtime.mkdir()
    (hermes / "auth.json").write_text(
        json.dumps(
            {
                "credential_pool": {
                    "openai-codex": [
                        {
                            "access_token": "test-access-token",
                            "base_url": "https://chatgpt.com/backend-api/codex",
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    requests = []

    def open_request(request, timeout):
        requests.append((request, timeout))
        return FakeResponse(payload)

    stdout = io.StringIO()
    with (
        unittest.mock.patch.dict(
            os.environ,
            {"HOME": str(home), "XDG_RUNTIME_DIR": str(runtime)},
        ),
        unittest.mock.patch("urllib.request.urlopen", side_effect=open_request),
        unittest.mock.patch("time.time", return_value=now),
        contextlib.redirect_stdout(stdout),
    ):
        runpy.run_path(str(TRACKER), run_name="__main__")

    output = stdout.getvalue().strip()
    expected = " 21%"
    if output != expected:
        raise AssertionError(f"expected {expected!r}, got {output!r}")
    if len(requests) != 1:
        raise AssertionError(f"expected one usage request, got {len(requests)}")
    request, timeout = requests[0]
    if request.full_url != "https://chatgpt.com/backend-api/wham/usage":
        raise AssertionError(f"unexpected usage URL: {request.full_url}")
    if request.get_header("Authorization") != "Bearer test-access-token":
        raise AssertionError("tracker did not use the Hermes Codex credential")
    if timeout > 4:
        raise AssertionError(f"request timeout must fit Herdr's 5s timeout, got {timeout}")

    cache = runtime / "herdr-codex-usage-cache"
    os.utime(cache, (now, now))
    failed_requests = []

    def fail_request(*args: object, **kwargs: object) -> None:
        failed_requests.append((args, kwargs))
        raise OSError("offline")

    for age, expected_requests, description in (
        (60, 0, "fresh cache avoids a network request"),
        (600, 1, "stale cache survives a network failure"),
    ):
        stdout = io.StringIO()
        with (
            unittest.mock.patch.dict(
                os.environ,
                {"HOME": str(home), "XDG_RUNTIME_DIR": str(runtime)},
            ),
            unittest.mock.patch("urllib.request.urlopen", side_effect=fail_request),
            unittest.mock.patch("time.time", return_value=now + age),
            contextlib.redirect_stdout(stdout),
        ):
            runpy.run_path(str(TRACKER), run_name="__main__")
        if stdout.getvalue().strip() != expected:
            raise AssertionError(f"{description} did not preserve the last usage value")
        if len(failed_requests) != expected_requests:
            raise AssertionError(
                f"{description}: expected {expected_requests} network attempts, "
                f"got {len(failed_requests)}"
            )
        print(f"ok   {description}")

print("ok   Hermes Codex OAuth renders the highest-used window compactly")
