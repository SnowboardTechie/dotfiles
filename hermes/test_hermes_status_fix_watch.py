"""Offline checks for upstream fix recognition and quiet transition delivery."""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "watch", Path(__file__).parent / "scripts/check-hermes-status-fix.py")
assert spec is not None and spec.loader is not None
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)


def source(key):
    return f'''
class CLI:
    def _show_session_status(self):
        if is_approval_bypass_active_for_session(getattr(self, "{key}", "") or ""):
            approval_label += " (YOLO bypass active)"
    def _toggle_yolo(self):
        session_key = self.session_id or "default"
'''


class WatchTests(unittest.TestCase):
    def test_current_bug_is_pending(self):
        self.assertFalse(watch.fixed(source("session_key")))

    def test_known_fix(self):
        self.assertTrue(watch.fixed(source("session_id")))

    def test_unknown_identity_and_refactor_fail_closed(self):
        for text in (source("unknown"), "", source("session_id").replace("self.session_id or", "self.other_id or")):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    watch.fixed(text)

    def test_pending_silent_and_ready_only_once(self):
        pending, message = watch.transition({}, False, "a" * 40)
        self.assertEqual(message, "")
        ready, message = watch.transition(pending, True, "b" * 40)
        self.assertTrue(message.startswith(watch.MENTION))
        self.assertIn("detached-HEAD", message)
        self.assertIn("No update", message)
        self.assertIn("b" * 40, message)
        self.assertEqual(watch.transition(ready, True, "c" * 40)[1], "")
        reset, message = watch.transition(ready, False, "d" * 40)
        self.assertEqual(message, "")
        self.assertTrue(watch.transition(reset, True, "e" * 40)[1])


if __name__ == "__main__":
    unittest.main()
