#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).parent / "scripts" / "check-cloudflared-homebrew-release.py"
SPEC = importlib.util.spec_from_file_location("cloudflared_homebrew_watch", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def formula(version: str) -> str:
    return (
        "class Cloudflared < Formula\n"
        f'  url "https://github.com/cloudflare/cloudflared/archive/refs/tags/{version}.tar.gz"\n'
        "end\n"
    )


class CloudflaredHomebrewWatchTests(unittest.TestCase):
    def run_main(self, root: Path, version: str, installed: str | None) -> list[str]:
        fixture = root / "cloudflared.rb"
        fixture.write_text(formula(version), encoding="utf-8")
        argv = [str(SCRIPT), "--formula-file", str(fixture), "--state-file", str(root / "state.json")]
        printed: list[str] = []
        with (
            patch.object(MODULE, "installed_version", return_value=installed),
            patch("sys.argv", argv),
            patch("builtins.print", side_effect=lambda text, **_: printed.append(text)),
        ):
            self.assertEqual(MODULE.main(), 0)
        return printed

    def test_formula_version_extracts_exact_tag(self) -> None:
        self.assertEqual(MODULE.formula_version(formula("2026.10.4")), "2026.10.4")

    def test_formula_version_rejects_unexpected_source(self) -> None:
        with self.assertRaises(MODULE.WatchError):
            MODULE.formula_version('url "https://example.com/2026.10.4.tar.gz"\n')

    def test_numeric_comparison_not_lexical(self) -> None:
        self.assertGreater(MODULE.parse_version("2026.10.10"), MODULE.parse_version("2026.10.4"))

    def test_silent_while_homebrew_is_behind(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual(self.run_main(root, "2026.10.3", "2026.10.3"), [])
            self.assertFalse((root / "state.json").exists())

    def test_notifies_once_with_mention(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.run_main(root, "2026.10.4", "2026.10.3")
            self.assertEqual(len(first), 1)
            self.assertTrue(first[0].startswith("@bryan:snowboardtechie.com cloudflared 2026.10.4"))
            self.assertEqual(self.run_main(root, "2026.10.4", "2026.10.3"), [])

    def test_silent_when_already_upgraded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual(self.run_main(root, "2026.10.4", "2026.10.4"), [])
            self.assertFalse((root / "state.json").exists())

    def test_source_failure_exits_nonzero(self) -> None:
        with (
            patch.object(MODULE, "fetch_formula", side_effect=MODULE.WatchError("HTTP 503")),
            patch("sys.argv", [str(SCRIPT), "--state-file", "/nonexistent/state.json"]),
        ):
            self.assertEqual(MODULE.main(), 1)


if __name__ == "__main__":
    unittest.main()
