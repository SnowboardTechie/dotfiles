#!/usr/bin/env python3
"""Install Git-backed Hermes assets without touching mutable runtime state."""

from __future__ import annotations

import argparse
import filecmp
import json
import os
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ASSET_ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ASSET_ROOT / "manifest.json"
IGNORED_NAMES = {".DS_Store", "__pycache__"}
IGNORED_SUFFIXES = {".pyc"}


class InstallError(RuntimeError):
    pass


def local_hostname() -> str:
    if sys.platform == "darwin":
        result = subprocess.run(
            ["scutil", "--get", "LocalHostName"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    return socket.gethostname().split(".", 1)[0]


def included_files(root: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part in IGNORED_NAMES for part in relative.parts):
            continue
        if path.suffix in IGNORED_SUFFIXES or not path.is_file():
            continue
        files[str(relative)] = path
    return files


def identical(source: Path, destination: Path) -> bool:
    if source.is_file() and destination.is_file():
        return filecmp.cmp(source, destination, shallow=False)
    if source.is_dir() and destination.is_dir():
        source_files = included_files(source)
        destination_files = included_files(destination)
        if source_files.keys() != destination_files.keys():
            return False
        return all(
            filecmp.cmp(source_files[name], destination_files[name], shallow=False)
            for name in source_files
        )
    return False


def resolved(path: Path) -> Path:
    return path.resolve(strict=True)


def require_managed_destination(destination: Path, hermes_home: Path) -> None:
    """Refuse writes whose resolved parent escapes HERMES_HOME."""
    managed_root = hermes_home.expanduser().resolve(strict=False)
    resolved_parent = destination.expanduser().parent.resolve(strict=False)
    if resolved_parent != managed_root and managed_root not in resolved_parent.parents:
        raise InstallError(f"destination parent escapes Hermes home: {destination}")


def install_link(
    source: Path,
    destination: Path,
    *,
    hermes_home: Path,
    adopt_identical: bool,
    backup_root: Path,
) -> str:
    if not source.exists():
        raise InstallError(f"managed source does not exist: {source}")

    require_managed_destination(destination, hermes_home)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        try:
            if resolved(destination) == resolved(source):
                return "current"
        except FileNotFoundError:
            pass
        raise InstallError(f"refusing to replace foreign or broken symlink: {destination}")

    if destination.exists():
        if not adopt_identical:
            raise InstallError(
                f"destination already exists: {destination}; rerun with --adopt-identical "
                "only after confirming it matches the Git-backed source"
            )
        if not identical(source, destination):
            raise InstallError(f"refusing to adopt non-identical destination: {destination}")
        relative = destination.relative_to(hermes_home)
        backup = backup_root / relative
        backup.parent.mkdir(parents=True, exist_ok=True)
        destination.rename(backup)
        destination.symlink_to(source, target_is_directory=source.is_dir())
        return f"adopted (backup: {backup})"

    destination.symlink_to(source, target_is_directory=source.is_dir())
    return "linked"


def install_copy(
    source: Path,
    destination: Path,
    *,
    hermes_home: Path,
    backup_root: Path,
) -> str:
    """Install a regular-file copy for Hermes paths that reject external symlinks."""
    if not source.is_file():
        raise InstallError(f"managed copy source is not a file: {source}")
    require_managed_destination(destination, hermes_home)
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.is_symlink():
        try:
            if resolved(destination) != resolved(source):
                raise InstallError(f"refusing to replace foreign symlink: {destination}")
        except FileNotFoundError as exc:
            raise InstallError(f"refusing to replace broken symlink: {destination}") from exc
        destination.unlink()
        shutil.copy2(source, destination)
        return "copied (replaced managed source symlink)"

    if destination.exists():
        if not destination.is_file():
            raise InstallError(f"copy destination is not a regular file: {destination}")
        if identical(source, destination):
            source_mode = stat.S_IMODE(source.stat().st_mode)
            destination_mode = stat.S_IMODE(destination.stat().st_mode)
            if destination_mode != source_mode:
                destination.chmod(source_mode)
                return "updated mode"
            return "current"
        backup = backup_root / destination.name
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(destination, backup)
        shutil.copy2(source, destination)
        return f"updated (backup: {backup})"

    shutil.copy2(source, destination)
    return "copied"


def remove_managed_script(
    name: str,
    *,
    hermes_home: Path,
    asset_root: Path,
) -> str:
    """Remove only a managed script symlink inside HERMES_HOME."""
    if Path(name).name != name:
        raise InstallError(f"unsafe removed script name in manifest: {name}")
    destination = hermes_home / "scripts" / name
    require_managed_destination(destination, hermes_home)
    expected_source = (asset_root / "scripts" / name).resolve(strict=False)
    if destination.is_symlink():
        link_target = Path(os.readlink(destination))
        if not link_target.is_absolute():
            link_target = destination.parent / link_target
        if link_target.resolve(strict=False) != expected_source:
            raise InstallError(f"refusing to remove foreign script symlink: {destination}")
        destination.unlink()
        return "removed"
    if destination.exists():
        raise InstallError(f"refusing to remove non-symlink script: {destination}")
    return "absent"


def compile_calendar(hermes_home: Path) -> str:
    if sys.platform != "darwin":
        return "skipped (not macOS)"
    compiler = shutil.which("swiftc")
    if not compiler:
        raise InstallError("swiftc is required to compile the Calendar collector")

    source = hermes_home / "scripts" / "sgg-calendar-events.swift"
    output = hermes_home / "scripts" / "bin" / "sgg-calendar-events"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and output.stat().st_mtime >= source.stat().st_mtime:
        return "current"

    with tempfile.TemporaryDirectory(dir=output.parent) as temp_dir:
        temporary = Path(temp_dir) / output.name
        environment = os.environ.copy()
        environment["TMPDIR"] = temp_dir
        result = subprocess.run(
            [compiler, str(source), "-framework", "EventKit", "-o", str(temporary)],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "swiftc failed").strip()
            raise InstallError(detail[:2000])
        temporary.replace(output)
    return "compiled"


def reconcile_cron(hermes_home: Path) -> str:
    source_root = Path(os.environ.get("HERMES_SOURCE_ROOT", hermes_home / "hermes-agent"))
    candidates = [
        os.environ.get("HERMES_PYTHON"),
        str(hermes_home / "hermes-agent" / "venv" / "bin" / "python"),
        sys.executable,
    ]
    interpreter = next((Path(item) for item in candidates if item and Path(item).is_file()), None)
    if interpreter is None:
        raise InstallError("could not find a Python interpreter for Hermes cron reconciliation")
    if not source_root.is_dir():
        raise InstallError(f"Hermes source root not found: {source_root}")

    environment = os.environ.copy()
    environment["HERMES_HOME"] = str(hermes_home)
    environment["HERMES_SOURCE_ROOT"] = str(source_root)
    result = subprocess.run(
        [str(interpreter), str(ASSET_ROOT / "reconcile_cron.py"), str(MANIFEST_PATH)],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "cron reconciliation failed").strip()
        raise InstallError(detail[:3000])
    return result.stdout.strip()


def enable_plugin(hermes_home: Path, name: str) -> str:
    """Enable one managed plugin without granting tool-override privileges."""
    candidates = [
        os.environ.get("HERMES_PYTHON"),
        str(hermes_home / "hermes-agent" / "venv" / "bin" / "python"),
        sys.executable,
    ]
    interpreter = next((Path(item) for item in candidates if item and Path(item).is_file()), None)
    if interpreter is None:
        raise InstallError("could not find a Python interpreter for Hermes plugin reconciliation")
    environment = os.environ.copy()
    environment["HERMES_HOME"] = str(hermes_home)
    result = subprocess.run(
        [
            str(interpreter),
            "-m",
            "hermes_cli.main",
            "plugins",
            "enable",
            name,
            "--no-allow-tool-override",
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "plugin enable failed").strip()
        raise InstallError(detail[:2000])
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hermes-home", type=Path, default=Path.home() / ".hermes")
    parser.add_argument("--adopt-identical", action="store_true")
    parser.add_argument("--force-host", action="store_true", help="install even when this is not Studio")
    parser.add_argument("--skip-compile", action="store_true")
    parser.add_argument("--skip-cron", action="store_true")
    args = parser.parse_args()

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    current_host = local_hostname()
    expected_host = manifest["studioLocalHostName"]
    if current_host != expected_host and not args.force_host:
        print(f"Hermes managed assets: skipped on {current_host} (Studio is {expected_host})")
        return 0

    hermes_home = args.hermes_home.expanduser().resolve()
    hermes_home.mkdir(parents=True, exist_ok=True)
    backup_root = hermes_home / ".dotfiles-adopt-backup" / datetime.now().strftime("%Y%m%dT%H%M%S")

    results: list[str] = []
    copied_scripts = set(manifest.get("copiedScripts", []))
    if not copied_scripts.issubset(manifest["scripts"]):
        raise InstallError("copiedScripts must be a subset of scripts")
    for name in manifest["scripts"]:
        source = ASSET_ROOT / "scripts" / name
        destination = hermes_home / "scripts" / name
        if name in copied_scripts:
            outcome = install_copy(
                source,
                destination,
                hermes_home=hermes_home,
                backup_root=backup_root / "scripts",
            )
        else:
            outcome = install_link(
                source,
                destination,
                hermes_home=hermes_home,
                adopt_identical=args.adopt_identical,
                backup_root=backup_root,
            )
        results.append(f"script {name}: {outcome}")

    for name in manifest.get("removedScripts", []):
        outcome = remove_managed_script(
            name,
            hermes_home=hermes_home,
            asset_root=ASSET_ROOT,
        )
        results.append(f"retired script {name}: {outcome}")

    hindsight_relative = Path(manifest["hindsightConfig"])
    if hindsight_relative.is_absolute() or ".." in hindsight_relative.parts:
        raise InstallError(f"unsafe Hindsight config path in manifest: {hindsight_relative}")
    hindsight_source = ASSET_ROOT / hindsight_relative
    resolved_asset_root = ASSET_ROOT.resolve(strict=True)
    resolved_hindsight_source = hindsight_source.resolve(strict=True)
    if resolved_asset_root not in resolved_hindsight_source.parents:
        raise InstallError(f"Hindsight config source escapes managed asset root: {hindsight_source}")
    outcome = install_link(
        hindsight_source,
        hermes_home / "hindsight" / "config.json",
        hermes_home=hermes_home,
        adopt_identical=args.adopt_identical,
        backup_root=backup_root,
    )
    results.append(f"Hindsight config: {outcome}")

    managed_plugins = manifest.get("plugins", [])
    for name in managed_plugins:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or len(relative.parts) != 1:
            raise InstallError(f"unsafe plugin path in manifest: {name}")
        outcome = install_link(
            ASSET_ROOT / "plugins" / relative,
            hermes_home / "plugins" / relative,
            hermes_home=hermes_home,
            adopt_identical=args.adopt_identical,
            backup_root=backup_root,
        )
        results.append(f"plugin {name}: {outcome}")
        results.append(f"plugin {name} activation: {enable_plugin(hermes_home, name)}")

    for relative_text in manifest["skills"]:
        relative = Path(relative_text)
        if relative.is_absolute() or ".." in relative.parts or len(relative.parts) != 2:
            raise InstallError(f"unsafe skill path in manifest: {relative_text}")
        outcome = install_link(
            ASSET_ROOT / "skills" / relative,
            hermes_home / "skills" / relative,
            hermes_home=hermes_home,
            adopt_identical=args.adopt_identical,
            backup_root=backup_root,
        )
        results.append(f"skill {relative_text}: {outcome}")

    if not args.skip_compile:
        results.append(f"Calendar collector: {compile_calendar(hermes_home)}")
    if not args.skip_cron:
        results.append(f"cron: {reconcile_cron(hermes_home)}")

    print("\n".join(results))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (InstallError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
