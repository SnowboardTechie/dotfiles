from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("matrix_native", Path(__file__).with_name("reconcile_matrix_native.py"))
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class NativeMatrixTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.pin = json.loads((MODULE.ASSETS / "source.json").read_text())

    def tearDown(self):
        self.temp.cleanup()

    def archive(self, name, *, kind=tarfile.REGTYPE):
        archive = self.root / "source.tar.gz"
        with tarfile.open(archive, "w:gz") as output:
            member = tarfile.TarInfo(name)
            member.type = kind
            member.linkname = "outside"
            data = b"source"
            member.size = len(data) if kind == tarfile.REGTYPE else 0
            output.addfile(member, io.BytesIO(data) if member.size else None)
        return archive

    def test_extracts_regular_source(self):
        source = MODULE.safe_extract(self.archive("python-olm-3.2.16/file"), self.root / "extract")
        self.assertEqual((source / "file").read_bytes(), b"source")

    def test_rejects_archive_traversal_and_links(self):
        for name, kind in [("../escape", tarfile.REGTYPE), ("/escape", tarfile.REGTYPE),
                           ("python-olm-3.2.16/link", tarfile.SYMTYPE),
                           ("python-olm-3.2.16/link", tarfile.LNKTYPE)]:
            with self.subTest(name=name, kind=kind), self.assertRaises(MODULE.NativeMatrixError):
                MODULE.safe_extract(self.archive(name, kind=kind), self.root / "extract")
        self.assertFalse((self.root / "extract").exists())

    def test_compiler_patch_requires_exactly_one_match(self):
        target = self.root / self.pin["patchFile"]
        target.parent.mkdir(parents=True)
        target.write_text(self.pin["patchBefore"])
        MODULE.patch_source(self.root, self.pin)
        self.assertEqual(target.read_text(), self.pin["patchAfter"])
        for text in ("unrecognized", self.pin["patchBefore"] * 2):
            target.write_text(text)
            with self.assertRaises(MODULE.NativeMatrixError):
                MODULE.patch_source(self.root, self.pin)

    def test_project_uses_host_independent_wheel_source_and_current_abi(self):
        wheel = self.root / 'with "quote"/python_olm.whl'
        text = MODULE.render_project(wheel, (3, 14))
        self.assertIn('requires-python = ">=3.14,<3.15"', text)
        self.assertIn(json.dumps(str(wheel)), text)
        self.assertIn("[tool.uv.sources]", text)
        self.assertNotIn("@WHEEL_PATH@", text)
        self.assertNotIn("/Users/bryan", text)

    def test_rejects_symlinked_runtime_parent(self):
        home = self.root / "home"
        home.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        (home / "platforms").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(MODULE.NativeMatrixError):
            MODULE.require_contained(home / "platforms/matrix/native", home)

    def test_rejects_bad_download_before_build_or_install(self):
        state = self.root / "state"
        state.mkdir()
        (state / "python-olm-3.2.16.tar.gz").write_bytes(b"bad source")
        with patch.object(MODULE.shutil, "which", return_value="uv"), patch.object(
            MODULE, "run", side_effect=AssertionError("must not run build")
        ), self.assertRaisesRegex(MODULE.NativeMatrixError, "checksum mismatch"):
            MODULE.build_wheel(Path("python"), state, self.root, self.pin, (3, 14))

    def test_valid_receipt_reuses_wheel_without_network_or_build(self):
        state = self.root / "state"
        wheels = state / "wheels"
        wheels.mkdir(parents=True)
        wheel = wheels / "python_olm-3.2.16-cp314-cp314-macosx_11_0_arm64.whl"
        wheel.write_bytes(b"test wheel")
        import hashlib
        receipt = {"recipe": hashlib.sha256((MODULE.ASSETS / "source.json").read_bytes()).hexdigest(),
                   "wheel": MODULE.digest(wheel)}
        wheel.with_name(wheel.name + ".json").write_text(json.dumps(receipt))
        with patch.object(MODULE, "run", side_effect=AssertionError("unexpected build")), patch.object(
            MODULE.urllib.request, "urlopen", side_effect=AssertionError("unexpected network")
        ):
            self.assertEqual(MODULE.build_wheel(Path("python"), state, self.root, self.pin, (3, 14)), wheel)

    def test_check_has_no_install_side_effects(self):
        home = self.root / "home"
        source = self.root / "hermes-agent"
        launcher = source / ".hermes/bin/hermes"
        launcher.parent.mkdir(parents=True)
        launcher.write_text("launcher")
        with patch.object(MODULE.sys, "platform", "darwin"), patch.object(
            MODULE.os, "uname", return_value=type("Host", (), {"machine": "arm64"})()
        ), patch.object(MODULE, "runtime", return_value=(Path("python"), (3, 14))), patch.object(
            MODULE, "verify"
        ), patch.object(MODULE, "build_wheel", side_effect=AssertionError("check must not build")), self.assertRaises(
            MODULE.NativeMatrixError
        ):
            MODULE.reconcile(home, source, apply=False)
        self.assertFalse(home.exists())

    def test_build_refuses_symlinked_wheel_directory(self):
        state = self.root / "state"
        state.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        (state / "wheels").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(MODULE.NativeMatrixError):
            MODULE.build_wheel(Path("python"), state, self.root, self.pin, (3, 14))
        self.assertEqual(list(outside.iterdir()), [])

    def test_subprocess_failure_is_not_success(self):
        result = subprocess.CompletedProcess(["false"], 1, "", "failed")
        with patch.object(MODULE.subprocess, "run", return_value=result), self.assertRaisesRegex(
            MODULE.NativeMatrixError, "failed"
        ):
            MODULE.run(["false"])


if __name__ == "__main__":
    unittest.main()
