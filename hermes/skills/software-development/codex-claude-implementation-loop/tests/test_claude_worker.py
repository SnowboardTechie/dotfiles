#!/usr/bin/env python3
"""Focused tests for Claude worker authentication and isolation helpers."""

from __future__ import annotations

import importlib.util
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "claude_worker.py"
SPEC = importlib.util.spec_from_file_location("claude_worker", MODULE_PATH)
assert SPEC and SPEC.loader
claude_worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(claude_worker)


class ClaudeWorkerTests(unittest.TestCase):
    def test_worker_config_directory_uses_isolated_secure_namespace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "worker-config"
            with mock.patch.dict(
                os.environ,
                {"HERMES_CLAUDE_WORKER_CONFIG_DIR": str(config_dir)},
            ):
                resolved = claude_worker.resolve_worker_config_dir()

            self.assertEqual(resolved, config_dir.resolve())
            self.assertEqual(stat.S_IMODE(resolved.stat().st_mode), 0o700)

    def test_worker_lock_is_private_and_does_not_mask_body_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            expected = OSError("worker body failed")
            with self.assertRaisesRegex(OSError, "worker body failed"):
                with claude_worker.serialized_worker(config_dir):
                    raise expected

            lock_path = config_dir / ".worker.lock"
            self.assertEqual(stat.S_IMODE(lock_path.stat().st_mode), 0o600)

    def test_subscription_auth_uses_isolated_environment(self) -> None:
        worker_env = {
            "PATH": os.environ.get("PATH", ""),
            "CLAUDE_CONFIG_DIR": "/tmp/isolated-claude",
        }
        completed = subprocess.CompletedProcess(
            ["claude", "auth", "status", "--text"],
            0,
            stdout="Login method: Claude account\n",
            stderr="",
        )
        with mock.patch.object(claude_worker, "run_command", return_value=completed) as run:
            method = claude_worker.verify_subscription_auth("claude", worker_env)

        self.assertEqual(method, "Claude account")
        self.assertIs(run.call_args.kwargs["env"], worker_env)

    def test_subscription_auth_rejects_api_key_billing(self) -> None:
        with self.assertRaisesRegex(claude_worker.WorkerError, "API billing"):
            claude_worker.verify_subscription_auth(
                "claude",
                {"ANTHROPIC_API_KEY": "present-but-not-logged"},
            )

    def test_plugin_override_disables_every_registered_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            (config_dir / "settings.json").write_text(
                '{"enabledPlugins":{"one":true,"two":false}}',
                encoding="utf-8",
            )

            settings = claude_worker.disabled_user_plugin_settings(config_dir)

        self.assertEqual(settings, {"enabledPlugins": {"one": False, "two": False}})

    def test_authentication_failures_are_not_retried(self) -> None:
        completed = subprocess.CompletedProcess(
            ["claude"],
            1,
            stdout='{"api_error_status":503,"result":"OAuth session expired"}',
            stderr="",
        )
        self.assertFalse(claude_worker.retryable_claude_failure(completed))


if __name__ == "__main__":
    unittest.main()
