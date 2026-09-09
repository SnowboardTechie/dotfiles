from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("install.py")
SPEC = importlib.util.spec_from_file_location("hermes_install", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ManagedDestinationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.source = self.root / "source.json"
        self.source.write_text('{"ok": true}\n', encoding="utf-8")
        self.backup = self.root / "backup"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_link_rejects_symlinked_parent_escape(self) -> None:
        outside = self.root / "outside"
        outside.mkdir()
        (self.home / "hindsight").symlink_to(outside, target_is_directory=True)

        with self.assertRaises(MODULE.InstallError):
            MODULE.install_link(
                self.source,
                self.home / "hindsight" / "config.json",
                hermes_home=self.home,
                adopt_identical=False,
                backup_root=self.backup,
            )

        self.assertFalse((outside / "config.json").exists())

    def test_copy_rejects_symlinked_parent_escape(self) -> None:
        outside = self.root / "outside"
        outside.mkdir()
        (self.home / "scripts").symlink_to(outside, target_is_directory=True)

        with self.assertRaises(MODULE.InstallError):
            MODULE.install_copy(
                self.source,
                self.home / "scripts" / "collector.py",
                hermes_home=self.home,
                backup_root=self.backup,
            )

        self.assertFalse((outside / "collector.py").exists())

    def test_link_is_idempotent_inside_managed_home(self) -> None:
        destination = self.home / "hindsight" / "config.json"

        first = MODULE.install_link(
            self.source,
            destination,
            hermes_home=self.home,
            adopt_identical=False,
            backup_root=self.backup,
        )
        second = MODULE.install_link(
            self.source,
            destination,
            hermes_home=self.home,
            adopt_identical=False,
            backup_root=self.backup,
        )

        self.assertEqual(first, "linked")
        self.assertEqual(second, "current")
        self.assertEqual(destination.resolve(), self.source.resolve())

    def test_identical_file_can_be_adopted_safely(self) -> None:
        destination = self.home / "hindsight" / "config.json"
        destination.parent.mkdir(parents=True)
        destination.write_bytes(self.source.read_bytes())

        outcome = MODULE.install_link(
            self.source,
            destination,
            hermes_home=self.home,
            adopt_identical=True,
            backup_root=self.backup,
        )

        self.assertTrue(outcome.startswith("adopted"))
        self.assertTrue(destination.is_symlink())
        self.assertEqual(destination.resolve(), self.source.resolve())

    def test_identical_copy_reconciles_executable_mode(self) -> None:
        destination = self.home / "scripts" / "collector.py"
        destination.parent.mkdir(parents=True)
        self.source.chmod(0o755)
        destination.write_bytes(self.source.read_bytes())
        destination.chmod(0o644)

        outcome = MODULE.install_copy(
            self.source,
            destination,
            hermes_home=self.home,
            backup_root=self.backup,
        )

        self.assertEqual(outcome, "updated mode")
        self.assertEqual(destination.stat().st_mode & 0o777, 0o755)

    def test_retired_script_rejects_symlinked_parent_escape(self) -> None:
        outside = self.root / "outside"
        outside.mkdir()
        (self.home / "scripts").symlink_to(outside, target_is_directory=True)
        expected = self.root / "assets" / "scripts" / "retired.py"
        (outside / "retired.py").symlink_to(expected)

        with self.assertRaises(MODULE.InstallError):
            MODULE.remove_managed_script(
                "retired.py",
                hermes_home=self.home,
                asset_root=self.root / "assets",
            )

        self.assertTrue((outside / "retired.py").is_symlink())

    def test_retired_script_removes_only_managed_symlink(self) -> None:
        destination = self.home / "scripts" / "retired.py"
        destination.parent.mkdir()
        expected = self.root / "assets" / "scripts" / "retired.py"
        destination.symlink_to(expected)

        outcome = MODULE.remove_managed_script(
            "retired.py",
            hermes_home=self.home,
            asset_root=self.root / "assets",
        )

        self.assertEqual(outcome, "removed")
        self.assertFalse(destination.exists() or destination.is_symlink())

    def test_plugin_activation_is_noninteractive_and_cannot_override_tools(self) -> None:
        interpreter = self.root / "python"
        interpreter.touch()
        completed = MODULE.subprocess.CompletedProcess(
            args=[], returncode=0, stdout="enabled\n", stderr=""
        )

        with patch.dict(MODULE.os.environ, {"HERMES_PYTHON": str(interpreter)}), patch.object(
            MODULE.subprocess, "run", return_value=completed
        ) as run:
            outcome = MODULE.enable_plugin(self.home, "matrix-key-recovery")

        self.assertEqual(outcome, "enabled")
        command = run.call_args.args[0]
        self.assertEqual(
            command,
            [
                str(interpreter),
                "-m",
                "hermes_cli.main",
                "plugins",
                "enable",
                "matrix-key-recovery",
                "--no-allow-tool-override",
            ],
        )
        self.assertEqual(run.call_args.kwargs["env"]["HERMES_HOME"], str(self.home))

    def test_plugin_tree_copy_replaces_only_its_managed_source_symlink(self) -> None:
        source = self.root / "plugin"
        source.mkdir()
        (source / "plugin.yaml").write_text("name: reviewed\n", encoding="utf-8")
        destination = self.home / "plugins" / "reviewed"
        destination.parent.mkdir()
        destination.symlink_to(source, target_is_directory=True)

        outcome = MODULE.install_tree_copy(
            source,
            destination,
            hermes_home=self.home,
            backup_root=self.backup,
        )
        (source / "plugin.yaml").write_text("name: changed\n", encoding="utf-8")

        self.assertEqual(outcome, "copied (replaced managed source symlink)")
        self.assertTrue(destination.is_dir())
        self.assertFalse(destination.is_symlink())
        self.assertEqual(
            (destination / "plugin.yaml").read_text(encoding="utf-8"), "name: reviewed\n"
        )

    def test_memory_provider_selection_uses_profile_scoped_config_cli(self) -> None:
        interpreter = self.root / "python"
        interpreter.touch()
        completed = MODULE.subprocess.CompletedProcess([], 0, "selected\n", "")
        with patch.dict(MODULE.os.environ, {"HERMES_PYTHON": str(interpreter)}), patch.object(
            MODULE.subprocess, "run", return_value=completed
        ) as run:
            result = MODULE.select_memory_provider(self.home, "hindsight-scoped")
        self.assertEqual(result, "selected")
        self.assertEqual(run.call_args.args[0], [
            str(interpreter), "-m", "hermes_cli.main", "config", "set",
            "memory.provider", "hindsight-scoped",
        ])
        self.assertEqual(run.call_args.kwargs["env"]["HERMES_HOME"], str(self.home))

    def test_memory_provider_selection_failure_is_not_reported_as_success(self) -> None:
        completed = MODULE.subprocess.CompletedProcess([], 1, "", "selection failed")
        with patch.object(MODULE.subprocess, "run", return_value=completed):
            with self.assertRaisesRegex(MODULE.InstallError, "selection failed"):
                MODULE.select_memory_provider(self.home, "hindsight-scoped")

    def test_plugin_tree_copy_rejects_a_foreign_symlink(self) -> None:
        source = self.root / "plugin"
        source.mkdir()
        (source / "plugin.yaml").write_text("name: reviewed\n", encoding="utf-8")
        foreign = self.root / "foreign"
        foreign.mkdir()
        destination = self.home / "plugins" / "reviewed"
        destination.parent.mkdir()
        destination.symlink_to(foreign, target_is_directory=True)

        with self.assertRaises(MODULE.InstallError):
            MODULE.install_tree_copy(
                source,
                destination,
                hermes_home=self.home,
                backup_root=self.backup,
            )

    def test_plugin_tree_copy_rejects_symlinks_inside_source(self) -> None:
        source = self.root / "plugin"
        source.mkdir()
        outside = self.root / "outside.py"
        outside.write_text("secret\n", encoding="utf-8")
        (source / "payload.py").symlink_to(outside)
        destination = self.home / "plugins" / "reviewed"

        with self.assertRaises(MODULE.InstallError):
            MODULE.install_tree_copy(
                source,
                destination,
                hermes_home=self.home,
                backup_root=self.backup,
            )

        self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
