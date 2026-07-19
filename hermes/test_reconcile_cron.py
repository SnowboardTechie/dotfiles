from __future__ import annotations

import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("reconcile_cron.py")
SPEC = importlib.util.spec_from_file_location("reconcile_cron", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ContinuationOriginTest(unittest.TestCase):
    def definition(self, **overrides: object) -> dict:
        definition = {
            "name": "Test Brief",
            "deliver": "matrix:!room",
            "attachToSession": True,
            "continuation": {
                "chatName": "Test Room",
                "userEnv": "MATRIX_ALLOWED_USERS",
            },
        }
        definition.update(overrides)
        return definition

    def test_builds_explicit_matrix_origin(self) -> None:
        with patch.dict(os.environ, {"MATRIX_ALLOWED_USERS": "@bryan:example.test"}):
            origin = MODULE.continuation_origin(self.definition())

        self.assertEqual(
            origin,
            {
                "platform": "matrix",
                "chat_id": "!room",
                "chat_name": "Test Room",
                "thread_id": None,
                "user_id": "@bryan:example.test",
            },
        )

    def test_non_continuable_job_has_no_origin(self) -> None:
        definition = self.definition(attachToSession=False)
        definition.pop("continuation")
        self.assertIsNone(MODULE.continuation_origin(definition))

    def test_rejects_metadata_on_non_continuable_job(self) -> None:
        with self.assertRaises(SystemExit):
            MODULE.continuation_origin(self.definition(attachToSession=False))

    def test_rejects_home_channel_fallback(self) -> None:
        with patch.dict(os.environ, {"MATRIX_ALLOWED_USERS": "@bryan:example.test"}):
            with self.assertRaises(SystemExit):
                MODULE.continuation_origin(self.definition(deliver="matrix"))

    def test_requires_exactly_one_user(self) -> None:
        with patch.dict(
            os.environ,
            {"MATRIX_ALLOWED_USERS": "@one:example.test,@two:example.test"},
        ):
            with self.assertRaises(SystemExit):
                MODULE.continuation_origin(self.definition())

    def test_requires_continuation_metadata(self) -> None:
        definition = self.definition()
        definition.pop("continuation")
        with self.assertRaises(SystemExit):
            MODULE.continuation_origin(definition)


if __name__ == "__main__":
    unittest.main()
