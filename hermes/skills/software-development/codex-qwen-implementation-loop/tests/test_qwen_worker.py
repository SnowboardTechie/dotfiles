from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "qwen_worker.py"
SPEC = importlib.util.spec_from_file_location("qwen_worker", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
qwen_worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(qwen_worker)


class QwenWorkerTests(unittest.TestCase):
    def test_worker_config_pins_loopback_provider_without_fallbacks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)

            config_path = qwen_worker.ensure_worker_config(home)

            config = config_path.read_text(encoding="utf-8")
            self.assertIn("provider: custom:local-qwen", config)
            self.assertIn("base_url: http://127.0.0.1:11434/v1", config)
            self.assertIn(
                "default: qwen3.6:35b-a3b-coding-nvfp4",
                config,
            )
            self.assertIn("compression:\n  enabled: false", config)
            self.assertIn("provider: custom\n    model: qwen3.6:35b-a3b-coding-nvfp4", config)
            self.assertIn("fallback_chain: []", config)
            self.assertEqual(config_path.stat().st_mode & 0o777, 0o600)

    def test_worker_home_rejects_persistent_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            (home / ".env").write_text("TOKEN=secret\n", encoding="utf-8")

            with self.assertRaisesRegex(qwen_worker.WorkerError, "credential"):
                qwen_worker.validate_worker_home_credentials(home)

    def test_worker_environment_isolates_home_and_scrubs_cloud_credentials(self) -> None:
        source = {
            "PATH": os.environ.get("PATH", ""),
            "OPENAI_API_KEY": "openai-secret",
            "ANTHROPIC_API_KEY": "anthropic-secret",
            "OPENROUTER_API_KEY": "router-secret",
            "NOTION_API_KEY": "notion-secret",
            "SGG_API_KEY": "sgg-secret",
            "AWS_SECRET_ACCESS_KEY": "aws-secret",
            "MATRIX_ACCESS_TOKEN": "matrix-secret",
            "CC": "/usr/bin/clang",
            "CFLAGS": "-O2",
            "PKG_CONFIG_PATH": "/opt/homebrew/lib/pkgconfig",
            "BUNDLE_GEMFILE": "/repo/Gemfile",
            "PYENV_ROOT": "/opt/pyenv",
            "HERMES_HOME": "/wrong/home",
            "TERMINAL_CWD": "/wrong/worktree",
            "_HERMES_GATEWAY": "1",
        }
        home = Path("/tmp/local-qwen-worker")

        worker_env = qwen_worker.build_worker_env(home, source)

        self.assertEqual(worker_env["HERMES_HOME"], str(home))
        self.assertEqual(worker_env["HERMES_YOLO_MODE"], "1")
        self.assertNotIn("OPENAI_API_KEY", worker_env)
        self.assertNotIn("ANTHROPIC_API_KEY", worker_env)
        self.assertNotIn("OPENROUTER_API_KEY", worker_env)
        self.assertNotIn("NOTION_API_KEY", worker_env)
        self.assertNotIn("SGG_API_KEY", worker_env)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", worker_env)
        self.assertNotIn("MATRIX_ACCESS_TOKEN", worker_env)
        self.assertEqual(worker_env["CC"], "/usr/bin/clang")
        self.assertEqual(worker_env["CFLAGS"], "-O2")
        self.assertEqual(worker_env["PKG_CONFIG_PATH"], "/opt/homebrew/lib/pkgconfig")
        self.assertEqual(worker_env["BUNDLE_GEMFILE"], "/repo/Gemfile")
        self.assertEqual(worker_env["PYENV_ROOT"], "/opt/pyenv")
        self.assertNotIn("TERMINAL_CWD", worker_env)
        self.assertNotIn("_HERMES_GATEWAY", worker_env)

    def test_command_pins_provider_model_tools_and_session_source(self) -> None:
        command = qwen_worker.build_hermes_command(
            hermes_bin="/usr/local/bin/hermes",
            prompt="implement this plan",
            max_turns=40,
            session_id=None,
        )

        self.assertEqual(command[0], "/usr/local/bin/hermes")
        self.assertIn("custom:local-qwen", command)
        self.assertIn("qwen3.6:35b-a3b-coding-nvfp4", command)
        self.assertIn("terminal,file", command)
        self.assertIn("tool", command)
        self.assertNotIn("--resume", command)

        resumed = qwen_worker.build_hermes_command(
            hermes_bin="hermes",
            prompt="fix review findings",
            max_turns=20,
            session_id="session-123",
        )
        resume_index = resumed.index("--resume")
        self.assertEqual(resumed[resume_index + 1], "session-123")
        self.assertIn("--no-restore-cwd", resumed)

    def test_parse_output_accepts_fenced_json_and_requires_contract(self) -> None:
        result = {
            "status": "completed",
            "summary": "implemented",
            "files_changed": ["src/example.py"],
            "tests": [
                {
                    "command": "pytest",
                    "status": "passed",
                    "summary": "1 passed",
                }
            ],
            "plan_deviations": [],
            "blockers": [],
            "notes": [],
        }
        stdout = f"Implementation complete.\n```json\n{json.dumps(result)}\n```\n"

        parsed = qwen_worker.parse_worker_output(stdout, mode="implement")

        self.assertEqual(parsed, result)

        result.pop("summary")
        with self.assertRaisesRegex(qwen_worker.WorkerError, "missing required fields"):
            qwen_worker.parse_worker_output(json.dumps(result), mode="implement")

    def test_revision_contract_requires_finding_fields(self) -> None:
        result = {
            "status": "completed",
            "summary": "revised",
            "files_changed": [],
            "tests": [],
            "findings_addressed": ["finding-1"],
            "unresolved_findings": [],
            "blockers": [],
            "notes": [],
        }

        parsed = qwen_worker.parse_worker_output(json.dumps(result), mode="revise")

        self.assertEqual(parsed["findings_addressed"], ["finding-1"])

    def test_implementation_requires_a_clean_initial_worktree(self) -> None:
        qwen_worker.validate_initial_status(mode="implement", baseline="")
        qwen_worker.validate_initial_status(mode="revise", baseline=" M greeting.py")
        with self.assertRaisesRegex(qwen_worker.WorkerError, "clean worktree"):
            qwen_worker.validate_initial_status(
                mode="implement",
                baseline=" M unrelated.py",
            )

    def test_extract_session_id_uses_hermes_stderr_contract(self) -> None:
        stderr = "provider log\n\nsession_id: 20260720_120000_abcd1234\n"

        self.assertEqual(
            qwen_worker.extract_session_id(stderr),
            "20260720_120000_abcd1234",
        )
        with self.assertRaisesRegex(qwen_worker.WorkerError, "session_id"):
            qwen_worker.extract_session_id("no session here")

    def test_revision_must_continue_the_requested_session(self) -> None:
        qwen_worker.validate_resumed_session_id("session-123", "session-123")
        with self.assertRaisesRegex(qwen_worker.WorkerError, "different session"):
            qwen_worker.validate_resumed_session_id("session-123", "session-456")

    def test_session_metadata_attests_local_provider_and_endpoint(self) -> None:
        metadata = {
            "session_id": "session-123",
            "model": qwen_worker.MODEL,
            "billing_provider": "custom",
            "billing_base_url": qwen_worker.BASE_URL,
            "source": "tool",
        }

        verified = qwen_worker.validate_session_metadata(metadata, "session-123")

        self.assertEqual(verified["billing_provider"], "custom")
        for field, value in (
            ("billing_provider", "openrouter"),
            ("billing_base_url", "https://example.com/v1"),
            ("source", "cli"),
        ):
            invalid = dict(metadata)
            invalid[field] = value
            with self.assertRaises(qwen_worker.WorkerError):
                qwen_worker.validate_session_metadata(invalid, "session-123")

    def test_session_record_binds_resume_to_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir) / "worker"
            root = Path(temp_dir) / "repo"
            common = root / ".git"
            root.mkdir()
            common.mkdir()

            qwen_worker.write_session_record(home, "session-123", root, common)
            qwen_worker.validate_session_record(home, "session-123", root, common)

            other = Path(temp_dir) / "other"
            other.mkdir()
            with self.assertRaisesRegex(qwen_worker.WorkerError, "repository"):
                qwen_worker.validate_session_record(home, "session-123", other, common)

    def test_sandbox_blocks_external_network_and_non_repository_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            common = root / ".git"
            home = Path(temp_dir) / "worker"
            root.mkdir()
            common.mkdir()
            home.mkdir()

            profile = qwen_worker.build_sandbox_profile(
                root=root,
                common_dir=common,
                worker_home=home,
                temp_dir=Path(temp_dir),
            )
            command = qwen_worker.wrap_sandbox_command(["hermes", "chat"], profile)

            self.assertEqual(command[:2], ["/usr/bin/sandbox-exec", "-p"])
            self.assertIn("(deny network*)", profile)
            self.assertIn('(remote ip "localhost:11434")', profile)
            self.assertIn(str(root), profile)
            self.assertIn(str(common), profile)
            self.assertIn(str(Path.home() / ".netrc"), profile)
            self.assertIn(str(Path.home() / ".claude"), profile)

    def test_reported_paths_must_cover_same_path_revision_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            changed = root / "changed.py"
            changed.write_text("value = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "changed.py"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "baseline"], cwd=root, check=True)
            changed.write_text("value = 2\n", encoding="utf-8")
            initial_status = qwen_worker.repository_status(root)
            initial_paths = qwen_worker.status_paths(initial_status)
            initial_fingerprints = qwen_worker.fingerprint_paths(root, initial_paths)

            changed.write_text("value = 3\n", encoding="utf-8")
            final_status = qwen_worker.repository_status(root)
            final_paths = qwen_worker.status_paths(final_status)
            changed_paths = qwen_worker.changed_paths_since_baseline(
                root,
                initial_paths,
                initial_fingerprints,
                final_paths,
            )

            qwen_worker.validate_reported_paths(
                root,
                ["changed.py"],
                final_paths,
                changed_paths,
            )
            self.assertEqual(changed_paths, {"changed.py"})

            with self.assertRaisesRegex(qwen_worker.WorkerError, "outside"):
                qwen_worker.validate_reported_paths(
                    root,
                    ["../escaped.py"],
                    final_paths,
                    changed_paths,
                )
            with self.assertRaisesRegex(qwen_worker.WorkerError, "not present"):
                qwen_worker.validate_reported_paths(
                    root,
                    ["missing.py"],
                    final_paths,
                    changed_paths,
                )
            with self.assertRaisesRegex(qwen_worker.WorkerError, "did not report"):
                qwen_worker.validate_reported_paths(
                    root,
                    [],
                    final_paths,
                    changed_paths,
                )


if __name__ == "__main__":
    unittest.main()
