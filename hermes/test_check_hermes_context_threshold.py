#!/usr/bin/env python3
"""Tests for the model-free Hermes context-threshold watchdog."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "scripts" / "check-hermes-context-threshold.py"
MANIFEST = HERE / "manifest.json"


def load_module():
    spec = importlib.util.spec_from_file_location("check_hermes_context_threshold", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RepairDetectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def config(self, **compression: object) -> dict:
        values = {
            "enabled": True,
            "threshold": 0.75,
            "threshold_tokens": 0,
            "target_ratio": 0.2,
        }
        values.update(compression)
        return {"compression": values}

    def test_exact_configuration_needs_no_repair(self) -> None:
        self.assertEqual(self.module.required_repairs(self.config()), [])

    def test_missing_null_nonzero_and_boolean_caps_are_repaired(self) -> None:
        cases = ({}, {"threshold_tokens": None}, {"threshold_tokens": 256_000}, {"threshold_tokens": False})
        for compression in cases:
            with self.subTest(compression=compression):
                config = self.config(**compression)
                if not compression:
                    config["compression"].pop("threshold_tokens")
                repairs = self.module.required_repairs(config)
                self.assertIn(("compression.threshold_tokens", "0"), repairs)

    def test_ratio_and_enabled_drift_are_repaired(self) -> None:
        repairs = self.module.required_repairs(
            self.config(threshold=0.5, enabled=False)
        )
        self.assertEqual(
            repairs,
            [
                ("compression.threshold", "0.75"),
                ("compression.enabled", "true"),
            ],
        )

    def test_explicit_native_threshold_is_removed(self) -> None:
        repairs = self.module.required_repairs(
            self.config(codex_responses_compact_threshold=256_000)
        )
        self.assertEqual(
            repairs,
            [("compression.codex_responses_compact_threshold", None)],
        )

    def test_repair_uses_supported_config_commands_then_checks(self) -> None:
        calls: list[list[str]] = []
        applied: list[str] = []

        def capture(_python, _source_root, _hermes_home, arguments):
            calls.append(arguments)

        with patch.object(self.module, "run_config_command", side_effect=capture):
            self.module.repair_config(
                [
                    ("compression.threshold_tokens", "0"),
                    ("compression.threshold", "0.75"),
                    ("compression.codex_responses_compact_threshold", None),
                ],
                python=Path("/python"),
                source_root=Path("/source"),
                hermes_home=Path("/home"),
                applied_keys=applied,
            )

        self.assertEqual(
            calls,
            [
                ["set", "compression.threshold_tokens", "0"],
                ["set", "compression.threshold", "0.75"],
                ["unset", "compression.codex_responses_compact_threshold"],
                ["check"],
            ],
        )
        self.assertEqual(
            applied,
            [
                "compression.threshold_tokens",
                "compression.threshold",
                "compression.codex_responses_compact_threshold",
            ],
        )


class EffectiveThresholdTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_accepts_verified_900k_model_thresholds(self) -> None:
        self.module.validate_effective_values(
            context_length=872_000,
            threshold_percent=0.75,
            threshold_tokens_cap=None,
            local_threshold=654_000,
            native_threshold=645_808,
            expected_native_threshold=645_808,
        )

    def test_rejects_restored_absolute_cap(self) -> None:
        with self.assertRaisesRegex(self.module.WatchdogError, "absolute threshold cap"):
            self.module.validate_effective_values(
                context_length=872_000,
                threshold_percent=0.75,
                threshold_tokens_cap=256_000,
                local_threshold=256_000,
                native_threshold=247_808,
                expected_native_threshold=247_808,
            )

    def test_rejects_wrong_effective_local_threshold(self) -> None:
        with self.assertRaisesRegex(self.module.WatchdogError, "effective local threshold"):
            self.module.validate_effective_values(
                context_length=872_000,
                threshold_percent=0.75,
                threshold_tokens_cap=None,
                local_threshold=256_000,
                native_threshold=247_808,
                expected_native_threshold=247_808,
            )

    def test_rejects_explicit_or_implausibly_low_native_thresholds(self) -> None:
        for native in (256_000, 1):
            with self.subTest(native=native), self.assertRaisesRegex(
                self.module.WatchdogError, "native threshold"
            ):
                self.module.validate_effective_values(
                    context_length=872_000,
                    threshold_percent=0.75,
                    threshold_tokens_cap=None,
                    local_threshold=654_000,
                    native_threshold=native,
                    expected_native_threshold=645_808,
                )


class AuditLogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_audit_log_is_append_only_jsonl_and_private(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "audit.jsonl"
            self.module.append_audit(path, {"status": "healthy", "value": 1})
            self.module.append_audit(path, {"status": "repaired", "value": 2})
            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([record["status"] for record in records], ["healthy", "repaired"])
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_malformed_yaml_never_exposes_the_offending_secret_line(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.yaml"
            secret = "sk-test-secret-that-must-not-escape"
            path.write_text(f"model:\n  api_key: [{secret}\n", encoding="utf-8")
            with self.assertRaises(self.module.WatchdogError) as caught:
                self.module.load_config(path)
            self.assertNotIn(secret, str(caught.exception))

    def test_partial_repair_failure_records_before_after_and_applied_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "profile"
            source = root / "source"
            (source / "venv/bin").mkdir(parents=True)
            (source / "venv/bin/python").touch()
            home.mkdir()
            (home / "config.yaml").write_text(
                "compression:\n"
                "  enabled: true\n"
                "  threshold: 0.5\n"
                "  threshold_tokens: 256000\n",
                encoding="utf-8",
            )
            audit = root / "audit.jsonl"
            calls = {"count": 0}

            def fail_second(*_args, **_kwargs):
                calls["count"] += 1
                if calls["count"] == 2:
                    raise self.module.WatchdogError("bounded command failure")

            with patch.object(self.module, "resolve_source_root", return_value=source), patch.object(
                self.module, "run_config_command", side_effect=fail_second
            ):
                with self.assertRaises(self.module.WatchdogError):
                    self.module.run(
                        [
                            "--hermes-home",
                            str(home),
                            "--state-log",
                            str(audit),
                        ]
                    )

            record = json.loads(audit.read_text(encoding="utf-8"))
            self.assertEqual(record["status"], "error")
            self.assertEqual(
                record["attempted_repair_keys"],
                ["compression.threshold_tokens", "compression.threshold"],
            )
            self.assertEqual(
                record["applied_repair_keys"], ["compression.threshold_tokens"]
            )
            self.assertEqual(record["before"], record["after"])
            self.assertIsNone(record["effective"])


class ProfileIsolationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_hermes_home_environment_selects_the_profile_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"HERMES_HOME": temporary}
        ):
            args = self.module.parse_args([])
            self.assertEqual(args.hermes_home, Path(temporary))

    def test_runtime_source_root_is_independent_of_profile_home(self) -> None:
        source = self.module.resolve_source_root(None)
        self.assertTrue((source / "run_agent.py").is_file())
        self.assertTrue((source / "hermes_cli/main.py").is_file())


class ManifestContractTest(unittest.TestCase):
    def test_manifest_installs_and_schedules_model_free_watchdog(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        script_name = SCRIPT.name
        self.assertNotEqual(SCRIPT.stat().st_mode & 0o111, 0)
        self.assertIn(script_name, manifest["scripts"])
        self.assertIn(script_name, manifest["copiedScripts"])

        job = next(
            job
            for job in manifest["cronJobs"]
            if job["name"] == "Hermes context threshold watchdog"
        )
        self.assertEqual(job["schedule"], "17 3 * * *")
        self.assertEqual(
            job["deliver"],
            "matrix:!5hH-Wud0Gd7hS1Z214EwjEMUvqtH8FBVOZhIZj0sqR4",
        )
        self.assertEqual(job["script"], script_name)
        self.assertIs(job["noAgent"], True)
        self.assertIsNone(job["model"])
        self.assertIsNone(job["provider"])
        self.assertEqual(job["enabledToolsets"], [])
        self.assertIs(job["attachToSession"], False)

    def test_script_help_executes_with_host_python(self) -> None:
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
