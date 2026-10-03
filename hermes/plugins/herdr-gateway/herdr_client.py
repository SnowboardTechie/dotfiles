"""Herdr CLI transport bound to one explicitly configured local endpoint.

No listener, bridge, daemon or install path: every call is one ``herdr``
subprocess against ``socket_path`` with a minimal environment, so no inherited
``HERDR_PANE_ID``/``HERDR_ENV`` caller identity can leak into targeting.
"""

from __future__ import annotations

import json
import os
import subprocess


class HerdrError(Exception):
    """Herdr answered with a structured error; the request was rejected."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class TransportError(HerdrError):
    """No structured answer arrived; the call's outcome is unknown."""

    def __init__(self, message: str) -> None:
        super().__init__("transport_unknown", message)


class HerdrClient:
    def __init__(self, binary: str, socket_path: str, timeout_s: float = 60.0) -> None:
        self.binary = binary
        self.socket_path = socket_path
        self.timeout_s = timeout_s

    def _run(self, args: tuple[str, ...], timeout_s: float | None) -> subprocess.CompletedProcess:
        env = {
            "HERDR_SOCKET_PATH": self.socket_path,
            "HOME": os.environ.get("HOME", "/"),
            "PATH": os.defpath,
            "LC_ALL": "C",
        }
        try:
            return subprocess.run(
                [self.binary, *args], capture_output=True, text=True, env=env, cwd="/",
                timeout=timeout_s or self.timeout_s, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise TransportError(f"herdr {' '.join(args[:2])} did not answer in time") from exc
        except OSError as exc:
            raise TransportError(f"herdr could not be executed: {exc.strerror}") from exc

    @staticmethod
    def _raise_for(proc: subprocess.CompletedProcess, args: tuple[str, ...]) -> None:
        try:
            error = json.loads(proc.stderr.strip() or proc.stdout.strip())["error"]
            code, message = str(error["code"]), str(error.get("message", ""))
        except (ValueError, KeyError, TypeError):
            raise TransportError(f"herdr {' '.join(args[:2])} exited {proc.returncode} "
                                 "without a structured error") from None
        raise HerdrError(code, message[:300])

    def call(self, *args: str, expect: str | None = None, timeout_s: float | None = None):
        """Run a JSON command; return ``result`` or, with ``expect``, the validated
        ``result[expect]`` object or list of objects."""
        proc = self._run(args, timeout_s)
        if proc.returncode != 0:
            self._raise_for(proc, args)
        try:
            result = json.loads(proc.stdout)["result"]
            value = result if expect is None else result[expect]
        except (ValueError, KeyError, TypeError):
            raise TransportError(f"herdr {' '.join(args[:2])} returned an unexpected shape") from None
        if not (isinstance(value, dict) or (isinstance(value, list)
                                            and all(isinstance(v, dict) for v in value))):
            raise TransportError(f"herdr {' '.join(args[:2])} returned an unexpected shape")
        return value

    def text(self, *args: str) -> str:
        """Run a plain-text command (agent read)."""
        proc = self._run(args, None)
        if proc.returncode != 0:
            self._raise_for(proc, args)
        return proc.stdout

    def status(self) -> dict[str, str]:
        proc = self._run(("status",), 15)
        if proc.returncode != 0:
            raise TransportError("herdr status failed")
        fields: dict[str, str] = {}
        section = ""
        for line in proc.stdout.splitlines():
            if line and not line.startswith(" "):
                section = line.rstrip(":").strip()
                continue
            key, sep, value = line.strip().partition(":")
            if sep and section == "server":
                fields[key.strip()] = value.strip()
        return fields
