#!/usr/bin/env python3
"""Offline tests for the nightly YunoHost update report scripts.

The monitor's stdout is hashed by the scheduler, so it must be byte-stable and
must move when the pending set moves. The collector must keep the target
release visible inside its budget and select exactly the versions in range.
A server failure must exit non-zero rather than look like a quiet night.
No test reaches the network or the server.

Run: python3 -m unittest hermes/test_yunohost_updates.py
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

SCRIPTS = Path(__file__).resolve().parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import yunohost_updates_lib as lib  # noqa: E402


def load_entry(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), SCRIPTS / name)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


PENDING = {
    "apps": [
        {"id": "synapse", "name": "Synapse", "version": "1.157.2~ynh1",
         "upgrade": {"current_version": "1.157.2~ynh1", "new_version": "1.163.0~ynh1",
                     "new_revision": "e14192f", "url": "https://github.com/YunoHost-Apps/synapse_ynh",
                     "notifications": {}, "requirements": {}}},
        {"id": "element", "name": "Chat", "version": "1.12.24~ynh1",
         "upgrade": {"current_version": "1.12.24~ynh1", "new_version": "1.12.32~ynh1",
                     "new_revision": "9886bb3", "url": "https://github.com/YunoHost-Apps/element_ynh"}},
    ],
    "system": [],
    "important_yunohost_upgrade": False,
    "pending_migrations": [],
    "last_apps_catalog_update": 12,
    "last_apt_update": 34,
}


class SnapshotTests(unittest.TestCase):
    def test_stable_and_sorted(self):
        first = lib.render(lib.snapshot(PENDING))
        varied = dict(PENDING, last_apps_catalog_update=99, last_apt_update=1,
                      apps=list(reversed(PENDING["apps"])))
        self.assertEqual(first, lib.render(lib.snapshot(varied)))
        self.assertEqual([a["id"] for a in json.loads(first)["apps"]], ["element", "synapse"])

    def test_new_version_moves_output(self):
        changed = json.loads(json.dumps(PENDING))
        changed["apps"][0]["upgrade"]["new_version"] = "1.164.0~ynh1"
        self.assertNotEqual(lib.render(lib.snapshot(PENDING)), lib.render(lib.snapshot(changed)))

    def test_system_packages_grouped_by_category(self):
        # Real `tools update --output-as json` shape when apt has upgrades:
        # a dict of category -> package list, not a flat list.
        grouped = dict(PENDING, system={
            "misc utils and libs": [
                {"name": "libexpat1-dev", "new_version": "2.5.0-1+deb12u5",
                 "current_version": "2.5.0-1+deb12u4"},
                {"name": "libexpat1", "new_version": "2.5.0-1+deb12u5",
                 "current_version": "2.5.0-1+deb12u4"},
            ],
        })
        system = json.loads(lib.render(lib.snapshot(grouped)))["system"]
        self.assertEqual([p["name"] for p in system], ["libexpat1", "libexpat1-dev"])
        self.assertEqual(system[0]["category"], "misc utils and libs")
        self.assertEqual(system[0]["newVersion"], "2.5.0-1+deb12u5")

    def test_system_packages_flat_list_still_supported(self):
        flat = dict(PENDING, system=[{"name": "curl", "current_version": "1", "new_version": "2"}])
        system = json.loads(lib.render(lib.snapshot(flat)))["system"]
        self.assertEqual([p["name"] for p in system], ["curl"])

    def test_unknown_system_shape_fails_loudly(self):
        for bad in ({"libs": ["libexpat1"]}, ["libexpat1"], "libexpat1"):
            with self.assertRaises(lib.SourceError):
                lib.snapshot(dict(PENDING, system=bad))


class VersionTests(unittest.TestCase):
    def test_keys(self):
        self.assertEqual(lib.version_key("v1.163.0"), (1, 163, 0))
        self.assertEqual(lib.version_key("20261009"), (2026, 10, 9))
        self.assertEqual(lib.version_key("2026.10.09.febb38d"), (2026, 10, 9))
        self.assertIsNone(lib.version_key("latest"))

    def test_range_excludes_current_prereleases_and_later(self):
        releases = [{"tag": t, "prerelease": False} for t in
                    ["v16.0.1", "v16.0.2", "v17.0.0-rc1", "v17.0.0", "v17.0.1"]]
        chosen = lib.releases_in_range(releases, "16.0.1", "17.0.0")
        self.assertEqual([r["tag"] for r in chosen], ["v16.0.2", "v17.0.0"])

    def test_date_tags(self):
        releases = [{"tag": t, "prerelease": False} for t in
                    ["2026.06.23.05dcc55", "2026.08.08.e6a2887", "2026.10.09.febb38d"]]
        chosen = lib.releases_in_range(releases, "20260623", "20261009")
        self.assertEqual([r["tag"] for r in chosen], ["2026.08.08.e6a2887", "2026.10.09.febb38d"])


class ExcerptTests(unittest.TestCase):
    def test_keeps_banner_and_breaking_section(self):
        body = ("Attention: do not upgrade yet.\n\n- UI features\n" + "  - x\n" * 3000
                + "- Breaking features\n  - strict durations\n<!-- hidden -->")
        text = lib.excerpt(body, 2000)
        self.assertIn("Attention", text)
        self.assertIn("strict durations", text)
        self.assertNotIn("hidden", text)
        self.assertLess(len(text), 2300)

    def test_target_release_keeps_budget(self):
        releases = [{"tag": f"v1.0.{n}", "date": "2026-10-01", "prerelease": False,
                     "url": "", "body": "- Security\n" + "s" * 5000} for n in range(1, 8)]
        releases.append({"tag": "v2.0.0", "date": "2026-10-15", "prerelease": False, "url": "",
                         "body": "Attention: advisory against upgrading"})

        def get(url: str) -> str:
            if url.endswith("manifest.toml"):
                return '[upstream]\ncode = "https://codeberg.org/o/r"\n'
            if "/releases" in url:
                return json.dumps([{"tag_name": r["tag"], "published_at": r["date"],
                                    "prerelease": False, "body": r["body"], "html_url": ""}
                                   for r in releases])
            return "[]"

        notes = lib.collect_notes({"id": "r", "currentVersion": "1.0.0~ynh1",
                                   "newVersion": "2.0.0~ynh1", "newRevision": "abcdef1",
                                   "packageUrl": "https://github.com/YunoHost-Apps/r_ynh"}, get)
        self.assertEqual(notes["releases"][-1]["tag"], "v2.0.0")
        self.assertIn("advisory", notes["releases"][-1]["excerpt"])
        self.assertEqual(notes["errors"], [])

    def test_source_errors_are_recorded(self):
        def get(url: str) -> str:
            raise OSError("offline")

        notes = lib.collect_notes({"id": "r", "currentVersion": "1~ynh1", "newVersion": "2~ynh1",
                                   "newRevision": "abcdef1",
                                   "packageUrl": "https://github.com/YunoHost-Apps/r_ynh"}, get)
        self.assertTrue(notes["errors"])


class ServerAccessTests(unittest.TestCase):
    def test_exact_sudo_command(self):
        argv = lib.ssh_command(lib.UPDATE_COMMAND)
        self.assertEqual(argv[-1], "sudo -n /usr/bin/yunohost tools update --output-as json")
        self.assertIn("BatchMode=yes", argv)

    def test_failure_raises(self):
        def run(*_a, **_k):
            return SimpleNamespace(returncode=255, stdout="", stderr="Connection timed out")

        with self.assertRaises(lib.SourceError):
            lib.fetch_pending(run)

    def test_monitor_exits_nonzero_on_failure(self):
        monitor = load_entry("check-yunohost-updates.py")
        original = lib.fetch_pending
        lib.fetch_pending = lambda: (_ for _ in ()).throw(lib.SourceError("down"))
        try:
            self.assertEqual(monitor.main(), 1)
        finally:
            lib.fetch_pending = original

    def test_parses_json_after_preamble(self):
        def run(*_a, **_k):
            return SimpleNamespace(returncode=0, stdout="Info: x\n" + json.dumps(PENDING), stderr="")

        self.assertEqual(lib.fetch_pending(run)["apps"][0]["id"], "synapse")


class ManifestTests(unittest.TestCase):
    def test_job_has_no_tools_and_is_continuable(self):
        manifest = json.loads((Path(__file__).resolve().parent / "manifest.json").read_text())
        job = next(j for j in manifest["cronJobs"] if j["name"] == "YunoHost update report")
        self.assertEqual(job["enabledToolsets"], [])
        self.assertTrue(job["attachToSession"])
        self.assertEqual(job["monitorScript"], "check-yunohost-updates.py")
        for name in ("yunohost_updates_lib.py", "check-yunohost-updates.py",
                     "collect-yunohost-updates.py"):
            self.assertIn(name, manifest["copiedScripts"])


if __name__ == "__main__":
    unittest.main()
