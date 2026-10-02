#!/usr/bin/env python3
"""Reproduce Studio's native Matrix dependencies without changing Hermes core."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from datetime import datetime
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "matrix-native"


class NativeMatrixError(RuntimeError):
    pass


def run(command: list[str], *, environment=None) -> str:
    result = subprocess.run(command, env=environment, text=True, capture_output=True, timeout=600)
    if result.returncode:
        raise NativeMatrixError((result.stderr or result.stdout)[-4000:])
    return result.stdout.strip()


def runtime(launcher: Path) -> tuple[Path, tuple[int, int]]:
    """Ask the installation-bound launcher; never guess a legacy venv."""
    command = json.loads(run([str(launcher), "--print-runtime-command", "--module", "site"]))
    python = Path(command[0])
    version = json.loads(run([str(python), "-I", "-c",
                             "import sys,json;print(json.dumps(list(sys.version_info[:2])))"]))
    if not python.is_file() or version[0] != 3 or version[1] < 11:
        raise NativeMatrixError("Hermes must supply a supported managed Python (3.11+)")
    return python, tuple(version)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_extract(archive: Path, destination: Path) -> Path:
    """Extract regular files/directories only, including on host Python 3.9."""
    with tarfile.open(archive) as source:
        members = source.getmembers()
        for member in members:
            path = Path(member.name)
            if path.is_absolute() or ".." in path.parts or not (member.isfile() or member.isdir()):
                raise NativeMatrixError(f"unsafe source archive entry: {member.name}")
        for member in members:
            path = destination / member.name
            if member.isdir():
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                stream = source.extractfile(member)
                assert stream is not None
                with stream, path.open("wb") as output:
                    shutil.copyfileobj(stream, output)
    return destination / "python-olm-3.2.16"


def patch_source(source: Path, pin: dict) -> None:
    target = source / pin["patchFile"]
    text = target.read_text(encoding="utf-8")
    if text.count(pin["patchBefore"]) != 1:
        raise NativeMatrixError("pinned libolm compiler patch does not match exactly once")
    target.write_text(text.replace(pin["patchBefore"], pin["patchAfter"]), encoding="utf-8")


def render_project(wheel: Path, version: tuple[int, int]) -> str:
    major, minor = version
    text = (ASSETS / "pyproject.toml.in").read_text(encoding="utf-8")
    return text.replace("@PYTHON_RANGE@", f">={major}.{minor},<{major}.{minor + 1}").replace(
        "@WHEEL_PATH@", json.dumps(str(wheel)))


def require_contained(path: Path, home: Path) -> None:
    """Refuse a symlinked parent or target that redirects runtime writes."""
    if home != path.resolve() and home not in path.resolve().parents:
        raise NativeMatrixError(f"runtime path escapes Hermes home: {path}")


def build_wheel(python: Path, state: Path, scratch: Path, pin: dict, version: tuple[int, int]) -> Path:
    wheels = state / "wheels"
    require_contained(wheels, state.resolve())
    wheels.mkdir(parents=True, exist_ok=True)
    tag = f"cp{version[0]}{version[1]}"
    expected = wheels / f"python_olm-{pin['version']}-{tag}-{tag}-macosx_11_0_arm64.whl"
    receipt = wheels / (expected.name + ".json")
    for path in (expected, receipt, state / "python-olm-3.2.16.tar.gz"):
        require_contained(path, state.resolve())
    recipe_hash = hashlib.sha256((ASSETS / "source.json").read_bytes()).hexdigest()
    if expected.is_file() and receipt.is_file():
        recorded = json.loads(receipt.read_text(encoding="utf-8"))
        if recorded == {"recipe": recipe_hash, "wheel": digest(expected)}:
            return expected
    uv = shutil.which("uv")
    if not uv:
        raise NativeMatrixError("uv is required; use the installed Hermes/Homebrew uv")
    archive = state / "python-olm-3.2.16.tar.gz"
    if not archive.exists():
        with urllib.request.urlopen(pin["url"], timeout=60) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != pin["sha256"]:
            raise NativeMatrixError("downloaded python-olm source checksum mismatch")
        archive.write_bytes(data)
    if digest(archive) != pin["sha256"]:
        raise NativeMatrixError("retained python-olm source checksum mismatch")
    with tempfile.TemporaryDirectory(prefix="matrix-native-build-", dir=scratch) as temporary:
        root = Path(temporary)
        source = safe_extract(archive, root)
        patch_source(source, pin)
        env = os.environ.copy()
        env["TMPDIR"] = str(root)
        env["MACOSX_DEPLOYMENT_TARGET"] = "11.0"
        env["CMAKE_POLICY_VERSION_MINIMUM"] = "3.5"
        run([uv, "build", "--wheel", "--python", str(python), "--out-dir", str(root / "wheels"),
             str(source)], environment=env)
        candidate = root / "wheels" / expected.name
        if not candidate.is_file():
            raise NativeMatrixError("native build did not produce the expected Python/macOS arm64 wheel")
        candidate.replace(expected)
        receipt.write_text(json.dumps({"recipe": recipe_hash, "wheel": digest(expected)}) + "\n")
    return expected


def verify(python: Path, source: Path, home: Path) -> None:
    code = (
        "import sys;sys.path.insert(0," + repr(str(source)) + ");import hermes_bootstrap;"
        "import mautrix,olm,asyncpg,aiosqlite,aiohttp_socks;"
        "from pm.extras import available;assert available('matrix');"
        "from olm import OutboundGroupSession,InboundGroupSession;"
        "s=OutboundGroupSession();r=InboundGroupSession(s.session_key);"
        "assert r.decrypt(s.encrypt('native-matrix-probe'))[0]=='native-matrix-probe';"
        "print('Native Matrix imports and encryption/decryption: PASS')"
    )
    env = os.environ.copy()
    env["HERMES_HOME"] = str(home)
    print(run([str(python), "-I", "-c", code], environment=env))


def reconcile(home: Path, source: Path, *, apply: bool) -> int:
    if sys.platform != "darwin" or os.uname().machine != "arm64":
        print("Native Matrix override: skipped (requires macOS arm64)")
        return 0
    home = home.expanduser().resolve()
    source = source.expanduser().resolve()
    launcher = source / ".hermes/bin/hermes"
    if not launcher.is_file():
        raise NativeMatrixError(f"managed Hermes launcher not found: {launcher}")
    python, version = runtime(launcher)
    plugin = home / "plugins/matrix-native-deps"
    state = home / "platforms/matrix/native"
    scratch = home / "cache/scratch"
    for path in (plugin, state, scratch):
        require_contained(path, home)
    if plugin.is_symlink():
        raise NativeMatrixError("refusing to replace a symlinked native dependency plugin")
    if plugin.exists():
        manifest = plugin / "plugin.yaml"
        if not manifest.is_file() or "name: matrix-native-deps\n" not in manifest.read_text():
            raise NativeMatrixError("refusing to replace an unrecognized plugin directory")
    if not apply:
        verify(python, source, home)
        # Check the tracked declaration as well as availability in the selected generation.
        project = plugin / "pyproject.toml"
        if not project.is_file():
            raise NativeMatrixError("native dependency plugin is not installed")
        pin = json.loads((ASSETS / "source.json").read_text())
        tag = f"cp{version[0]}{version[1]}"
        wheel = state / "wheels" / f"python_olm-{pin['version']}-{tag}-{tag}-macosx_11_0_arm64.whl"
        require_contained(wheel, home)
        if not wheel.is_file() or project.read_text() != render_project(wheel, version):
            raise NativeMatrixError("native dependency declaration/build needs reconciliation")
        receipt = wheel.with_name(wheel.name + ".json")
        require_contained(receipt, home)
        expected_receipt = {"recipe": hashlib.sha256((ASSETS / "source.json").read_bytes()).hexdigest(),
                            "wheel": digest(wheel)}
        if not receipt.is_file() or json.loads(receipt.read_text()) != expected_receipt:
            raise NativeMatrixError("native wheel receipt/checksum needs reconciliation")
        for name in ("plugin.yaml", "__init__.py"):
            if (plugin / name).read_bytes() != (ASSETS / name).read_bytes():
                raise NativeMatrixError(f"native plugin differs from tracked source: {name}")
        env = os.environ.copy()
        env["HERMES_HOME"] = str(home)
        plugins = run([str(launcher), "plugins", "list", "--plain", "--no-bundled"], environment=env)
        if not any(line.split()[:1] == ["enabled"] and line.split()[-1:] == ["matrix-native-deps"]
                   for line in plugins.splitlines()):
            raise NativeMatrixError("native dependency plugin is not enabled")
        print("Native Matrix tracked installation: current")
        return 0
    scratch.mkdir(parents=True, exist_ok=True)
    state.mkdir(parents=True, exist_ok=True)
    pin = json.loads((ASSETS / "source.json").read_text())
    wheel = build_wheel(python, state, scratch, pin, version)
    with tempfile.TemporaryDirectory(prefix="matrix-native-plugin-", dir=scratch) as temporary:
        candidate = Path(temporary) / "matrix-native-deps"
        candidate.mkdir()
        for name in ("plugin.yaml", "__init__.py"):
            shutil.copy2(ASSETS / name, candidate / name)
        (candidate / "pyproject.toml").write_text(render_project(wheel, version))
        from install import install_tree_copy
        backup = home / ".dotfiles-adopt-backup" / datetime.now().strftime("%Y%m%dT%H%M%S")
        print("Native Matrix plugin:", install_tree_copy(candidate, plugin, hermes_home=home, backup_root=backup))
    env = os.environ.copy()
    env["HERMES_HOME"] = str(home)
    print(run([str(launcher), "plugins", "enable", "matrix-native-deps", "--no-allow-tool-override"], environment=env))
    print(run([str(launcher), "pm", "install"], environment=env))
    verify(python, source, home)
    print("Native Matrix dependencies installed; no gateway restart or crypto-state changes performed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--hermes-home", type=Path, default=Path.home() / ".hermes")
    parser.add_argument("--source-root", type=Path)
    args = parser.parse_args()
    source = args.source_root or args.hermes_home / "hermes-agent"
    return reconcile(args.hermes_home, source, apply=args.apply)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (NativeMatrixError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
