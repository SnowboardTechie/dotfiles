#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).parent / "scripts" / "check-herdr-homebrew-atuin-fix.py"
SPEC = importlib.util.spec_from_file_location("herdr_homebrew_watch", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class HerdrHomebrewWatchTests(unittest.TestCase):
    def test_formula_release_extracts_exact_upstream_tag(self) -> None:
        tag, version = MODULE.formula_release(
            'class Herdr < Formula\n  url "https://github.com/herdrdev/herdr/archive/refs/tags/v0.8.3.tar.gz"\nend\n'
        )
        self.assertEqual((tag, version), ("v0.8.3", "0.8.3"))

    def test_formula_release_rejects_unexpected_source(self) -> None:
        with self.assertRaises(MODULE.WatchError):
            MODULE.formula_release('url "https://example.com/v0.8.3.tar.gz"\n')

    def test_state_round_trip_uses_release_and_fix_signature(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / "state.json"
            MODULE.write_notification_state(state, tag="v0.8.3")
            self.assertEqual(
                MODULE.load_notified_signature(state),
                f"v0.8.3:{MODULE.FIX_COMMIT}",
            )
            payload = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(payload["fixCommit"], MODULE.FIX_COMMIT)

    def test_main_stays_silent_when_release_lacks_fix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            formula = root / "herdr.rb"
            state = root / "state.json"
            formula.write_text(
                'url "https://github.com/herdrdev/herdr/archive/refs/tags/v0.8.2.tar.gz"\n',
                encoding="utf-8",
            )
            with (
                patch.object(MODULE, "release_contains_fix", return_value=False),
                patch("sys.argv", [str(SCRIPT), "--formula-file", str(formula), "--state-file", str(state)]),
                patch("builtins.print") as output,
            ):
                self.assertEqual(MODULE.main(), 0)
            output.assert_not_called()
            self.assertFalse(state.exists())

    def test_main_notifies_once_when_release_contains_fix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            formula = root / "herdr.rb"
            state = root / "state.json"
            formula.write_text(
                'url "https://github.com/herdrdev/herdr/archive/refs/tags/v0.8.3.tar.gz"\n',
                encoding="utf-8",
            )
            argv = [str(SCRIPT), "--formula-file", str(formula), "--state-file", str(state)]
            with (
                patch.object(MODULE, "release_contains_fix", return_value=True),
                patch("sys.argv", argv),
                patch("builtins.print") as first_output,
            ):
                self.assertEqual(MODULE.main(), 0)
            first_output.assert_called_once()
            self.assertIn("brew upgrade herdr", first_output.call_args.args[0])

            with (
                patch.object(MODULE, "release_contains_fix") as ancestry,
                patch("sys.argv", argv),
                patch("builtins.print") as second_output,
            ):
                self.assertEqual(MODULE.main(), 0)
            ancestry.assert_not_called()
            second_output.assert_not_called()


if __name__ == "__main__":
    unittest.main()
