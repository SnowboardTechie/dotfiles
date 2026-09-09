#!/usr/bin/env python3
"""Contract tests; network responses below are simulated, not release evidence."""
import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).parent / "scripts/check-typespec-fix-release.py"
SPEC = importlib.util.spec_from_file_location("typespec_watch", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def response(value):
    return io.BytesIO(json.dumps(value).encode())


class WatchTests(unittest.TestCase):
    def sources(self, request, **kwargs):
        url = request.full_url
        for name in ("compiler", "openapi3"):
            if "registry.npmjs.org" in url and name in url:
                return response({"name": "@typespec/" + name, "version": "1.16.0",
                    "repository": {"url": "git+https://github.com/microsoft/typespec.git"},
                    "dist": {"tarball": f"https://registry.npmjs.org/@typespec/{name}/-/{name}-1.16.0.tgz"}})
        if "/releases/tags/" in url:
            return response({"tag_name": "typespec-stable@1.16.0", "draft": False,
                "prerelease": False, "published_at": "2026-09-10T00:00:00Z"})
        if "/compare/" in url:
            self.assertIn("e0f67bdf3c5a0875dfa98b475648af37caac71a6...typespec-stable%401.16.0", url)
            return response({"status": "ahead"})
        raise AssertionError(url)

    def invoke(self, state):
        out, err = io.StringIO(), io.StringIO()
        with patch("sys.argv", [str(SCRIPT)]), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = MODULE.main()
        return code, out.getvalue(), err.getvalue()

    def test_ready_release_reports_on_every_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state.json"
            with patch("urllib.request.urlopen", side_effect=self.sources):
                code, out, err = self.invoke(state)
            self.assertEqual(code, 0, err)
            self.assertIn("@bryan:snowboardtechie.com", out)
            self.assertIn("1.16.0", out)
            self.assertIn("https://github.com/HHS/simpler-grants-protocol/pull/1093", out)
            self.assertFalse(state.exists())
            with patch("urllib.request.urlopen", side_effect=self.sources):
                self.assertEqual(self.invoke(state), (0, out, ""))


    def test_readiness_and_source_failures(self):
        cases = [
            ("/compare/", {"status": "behind"}, 0),
            ("/compare/", {"status": "diverged"}, 0),
            ("/compare/", {"status": "unexpected"}, 1),
            ("/releases/tags/", {"prerelease": True}, 0),
            ("/releases/tags/", {"draft": True}, 0),
            ("compiler/latest", {"version": "1.16.0-dev.1"}, 0),
            ("compiler/latest", {"name": "unexpected"}, 1),
            ("compiler/latest", {"repository": {"url": "https://example.com/repo"}}, 1),
            ("compiler/latest", {"dist": {"tarball": "https://example.com/file.tgz"}}, 1),
            ("openapi3/latest", {"version": "1.15.0", "dist": {
                "tarball": "https://registry.npmjs.org/@typespec/openapi3/-/openapi3-1.15.0.tgz"}}, 0),
        ]
        for fragment, changes, expected in cases:
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as tmp:
                state = Path(tmp) / "state.json"
                def source(request, **kwargs):
                    data = json.load(self.sources(request, **kwargs))
                    if fragment in request.full_url:
                        data.update(changes)
                    return response(data)
                with patch("urllib.request.urlopen", side_effect=source):
                    code, out, err = self.invoke(state)
                self.assertEqual(code, expected, err)
                if expected == 0:
                    self.assertIn("@bryan:snowboardtechie.com", out)
                    self.assertIn("PR #1093", out)
                    self.assertIn("No qualifying stable TypeSpec fix release verified yet", out)
                    self.assertIn("https://github.com/HHS/simpler-grants-protocol/pull/1093", out)
                else:
                    self.assertEqual(out, "")
                self.assertFalse(state.exists())

    def test_network_failure_is_not_silent_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state.json"
            with patch("urllib.request.urlopen", side_effect=OSError("source unavailable")):
                code, out, err = self.invoke(state)
            self.assertEqual(code, 1)
            self.assertEqual(out, "")
            self.assertIn("source unavailable", err)
            self.assertFalse(state.exists())


if __name__ == "__main__":
    unittest.main()
