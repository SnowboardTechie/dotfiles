#!/usr/bin/env python3
"""Tests for the model-free Studio service watchdog."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "scripts" / "check-studio-services.py"
MANIFEST = HERE / "manifest.json"
EXPECTED_SERVICES = {
    "Hermes Dashboard",
    "Hindsight API",
    "Hindsight Control Plane",
    "Open WebUI",
    "Grafana",
    "Prometheus",
    "Alertmanager",
    "Loki",
    "Grafana Alloy",
    "Ollama",
    "Syncthing",
    "Plex",
    "Jellyfin",
    "Dashy",
}


def load_module():
    spec = importlib.util.spec_from_file_location("check_studio_services", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WatchdogStateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def healthy(self) -> dict[str, str | None]:
        return {probe.name: None for probe in self.module.PROBES}

    def test_declared_probe_set_is_complete(self) -> None:
        self.assertEqual({probe.name for probe in self.module.PROBES}, EXPECTED_SERVICES)
        self.assertEqual(len({probe.name for probe in self.module.PROBES}), len(self.module.PROBES))

    def test_three_failures_alert_once_and_recovery_alerts_once(self) -> None:
        state: dict = {}
        results = self.healthy()
        results["Grafana"] = "HTTP 500"

        state, messages = self.module.evaluate(state, results, failure_threshold=3)
        self.assertEqual(messages, [])
        state, messages = self.module.evaluate(state, results, failure_threshold=3)
        self.assertEqual(messages, [])
        state, messages = self.module.evaluate(state, results, failure_threshold=3)
        self.assertEqual(len(messages), 1)
        self.assertIn("Grafana", messages[0])
        self.assertIn("3 consecutive checks", messages[0])
        self.assertTrue(messages[0].startswith(self.module.MENTION))

        state, messages = self.module.evaluate(state, results, failure_threshold=3)
        self.assertEqual(messages, [])

        state, messages = self.module.evaluate(state, self.healthy(), failure_threshold=3)
        self.assertEqual(len(messages), 1)
        self.assertIn("recovered", messages[0].lower())
        self.assertIn("Grafana", messages[0])

        state, messages = self.module.evaluate(state, self.healthy(), failure_threshold=3)
        self.assertEqual(messages, [])

    def test_multiple_transitions_are_consolidated(self) -> None:
        state: dict = {
            "services": {
                "Plex": {"failures": 2, "alerted": False, "last_error": "timeout"},
                "Loki": {"failures": 3, "alerted": True, "last_error": "HTTP 503"},
            }
        }
        results = self.healthy()
        results["Plex"] = "connection refused"

        state, messages = self.module.evaluate(state, results, failure_threshold=3)

        self.assertEqual(len(messages), 1)
        self.assertIn("Plex", messages[0])
        self.assertIn("Loki", messages[0])
        self.assertIn("unhealthy", messages[0].lower())
        self.assertIn("recovered", messages[0].lower())

    def test_state_round_trip_is_atomic_and_private(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state.json"
            expected = {"services": {"Grafana": {"failures": 1, "alerted": False}}}
            self.module.save_state(path, expected)
            self.assertEqual(self.module.load_state(path), expected)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)


class ManifestContractTest(unittest.TestCase):
    def test_manifest_installs_and_schedules_model_free_watchdog(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        script_name = SCRIPT.name
        self.assertNotEqual(SCRIPT.stat().st_mode & 0o111, 0)
        self.assertIn(script_name, manifest["scripts"])
        self.assertIn(script_name, manifest["copiedScripts"])

        job = next(job for job in manifest["cronJobs"] if job["name"] == "Monitor Studio services")
        self.assertEqual(job["schedule"], "every 5m")
        self.assertEqual(job["deliver"], "matrix")
        self.assertEqual(job["script"], script_name)
        self.assertIs(job["noAgent"], True)
        self.assertIsNone(job["model"])
        self.assertIsNone(job["provider"])
        self.assertEqual(job["enabledToolsets"], [])
        self.assertIs(job["attachToSession"], False)

    def test_script_help_executes_with_the_host_python(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--diagnose", completed.stdout)


if __name__ == "__main__":
    unittest.main()
