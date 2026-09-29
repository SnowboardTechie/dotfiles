from __future__ import annotations

import hashlib
import importlib.util
import json
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
        (self.home / "managed").symlink_to(outside, target_is_directory=True)

        with self.assertRaises(MODULE.InstallError):
            MODULE.install_link(
                self.source,
                self.home / "managed" / "config.json",
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
        destination = self.home / "managed" / "config.json"

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
        destination = self.home / "managed" / "config.json"
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


    def test_retired_link_removes_only_its_managed_source_symlink(self) -> None:
        assets = self.root / "assets"
        managed = self.home / "retired" / "config.json"
        managed.parent.mkdir()
        managed.symlink_to(assets / "retired" / "config.json")
        foreign = self.home / "other" / "config.json"
        foreign.parent.mkdir()
        foreign.symlink_to(self.source)

        outcome = MODULE.remove_managed_link(
            Path("retired/config.json"), hermes_home=self.home, asset_root=assets
        )
        with self.assertRaises(MODULE.InstallError):
            MODULE.remove_managed_link(
                Path("other/config.json"), hermes_home=self.home, asset_root=assets
            )

        self.assertEqual(outcome, "removed")
        self.assertFalse(managed.is_symlink())
        self.assertTrue(foreign.is_symlink())
        self.assertEqual(
            MODULE.remove_managed_link(
                Path("retired/config.json"), hermes_home=self.home, asset_root=assets
            ),
            "absent",
        )

    def test_retired_copy_is_removed_only_while_identical_to_what_shipped(self) -> None:
        scripts = self.home / "scripts"
        scripts.mkdir()
        shipped = b"#!/usr/bin/env python3\n"
        digest = hashlib.sha256(shipped).hexdigest()
        (scripts / "retired.py").write_bytes(shipped)
        (scripts / "edited.py").write_bytes(shipped + b"# local edit\n")

        outcome = MODULE.remove_retired_copy("retired.py", digest, hermes_home=self.home)
        with self.assertRaises(MODULE.InstallError):
            MODULE.remove_retired_copy("edited.py", digest, hermes_home=self.home)

        self.assertEqual(outcome, "removed")
        self.assertFalse((scripts / "retired.py").exists())
        self.assertTrue((scripts / "edited.py").exists())
        self.assertEqual(
            MODULE.remove_retired_copy("retired.py", digest, hermes_home=self.home), "absent"
        )


class RetiredHindsightInstallTest(unittest.TestCase):
    """The installer must neither reinstall nor select the retired Hindsight provider."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / "hermes"
        self.manifest = json.loads(MODULE.MANIFEST_PATH.read_text(encoding="utf-8"))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_manifest_carries_no_hindsight_install_surface(self) -> None:
        self.assertNotIn("hindsightConfig", self.manifest)
        self.assertNotIn("memoryProvider", self.manifest)
        self.assertNotIn("hindsight-scoped", self.manifest["plugins"])
        self.assertIn("matrix-key-recovery", self.manifest["plugins"])
        self.assertNotIn("sgg-granola-import.py", self.manifest["scripts"])
        self.assertIn("sgg-granola-import.py", self.manifest["removedCopiedScripts"])
        self.assertIn("hindsight/config.json", self.manifest["removedLinks"])
        self.assertFalse((MODULE.ASSET_ROOT / "hindsight").exists())
        self.assertFalse((MODULE.ASSET_ROOT / "plugins" / "hindsight-scoped").exists())
        self.assertFalse(hasattr(MODULE, "select_memory_provider"))

    def test_install_retires_hindsight_and_keeps_other_plugins_and_memory(self) -> None:
        stale_link = self.home / "hindsight" / "config.json"
        stale_link.parent.mkdir(parents=True)
        stale_link.symlink_to(MODULE.ASSET_ROOT / "hindsight" / "config.json")
        # Native memory and the already-installed plugin tree are not the
        # installer's to delete; the supported Hermes CLI retires the plugin.
        native_memory = self.home / "memories" / "MEMORY.md"
        native_memory.parent.mkdir()
        native_memory.write_text("native memory\n", encoding="utf-8")
        old_plugin = self.home / "plugins" / "hindsight-scoped" / "plugin.yaml"
        old_plugin.parent.mkdir(parents=True)
        old_plugin.write_text("name: hindsight-scoped\n", encoding="utf-8")

        enabled: list[str] = []
        argv = ["install.py", "--hermes-home", str(self.home), "--force-host",
                "--skip-compile", "--skip-cron"]
        with patch.object(MODULE.sys, "argv", argv), patch.object(
            MODULE, "local_hostname", return_value="elsewhere"
        ), patch.object(
            MODULE, "enable_plugin", side_effect=lambda home, name: enabled.append(name) or "ok"
        ), patch.object(
            MODULE.subprocess, "run", side_effect=AssertionError("unexpected subprocess")
        ), patch("builtins.print"):
            self.assertEqual(MODULE.main(), 0)

        self.assertEqual(enabled, self.manifest["plugins"])
        self.assertFalse(stale_link.exists() or stale_link.is_symlink())
        self.assertFalse((self.home / "scripts" / "sgg-granola-import.py").exists())
        self.assertTrue((self.home / "scripts" / "sgg-morning-brief.py").is_file())
        self.assertTrue((self.home / "plugins" / "matrix-key-recovery").is_dir())
        self.assertEqual(native_memory.read_text(encoding="utf-8"), "native memory\n")
        self.assertTrue(old_plugin.exists())


if __name__ == "__main__":
    unittest.main()
