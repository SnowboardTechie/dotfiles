"""Offline checks for the clarify-context fix watcher's detector and one-time alerts."""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "watch", Path(__file__).parent / "scripts/check-hermes-clarify-context-fix.py")
assert spec is not None and spec.loader is not None
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)

CURRENT = '''
MAX_QUESTIONS = 5
CLARIFY_SCHEMA = {
    "name": "clarify",
    "description": (
        "Ask the user one or more questions when you need a decision, "
        "clarification, or feedback before proceeding. Pass every question "
        f"in `questions` (1-{MAX_QUESTIONS} entries)."
    ),
}
'''
FIXED = CURRENT.replace(
    "before proceeding. ",
    "before proceeding. The user sees only your normal reply text and the question, "
    "never your reasoning. ")
ARGS = dict(issue_state="open", pr_state="open", runtime_rev="a" * 40, upstream_sha="b" * 40)


class DetectorTests(unittest.TestCase):
    def test_current_description_is_not_steered(self):
        self.assertFalse(watch.steered(CURRENT))

    def test_pr_wording_is_steered(self):
        self.assertTrue(watch.steered(FIXED))

    def test_reworded_upstream_description_is_recognized(self):
        reworded = CURRENT.replace("a decision, \"\n        \"clarification, or feedback before proceeding.",
                                   "a decision or feedback.\"\n        \"")
        self.assertNotIn("clarification", reworded)
        self.assertFalse(watch.steered(reworded))

    def test_refactor_fails_closed(self):
        for text in ("", "CLARIFY_SCHEMA = build()", CURRENT.replace('"description"', '"summary"'),
                     CURRENT.replace("Ask the user", "Collect")):
            with self.subTest(text=text[:40]), self.assertRaises(ValueError):
                watch.steered(text)


class TransitionTests(unittest.TestCase):
    def test_pending_is_silent(self):
        state, message = watch.transition({}, runtime=False, upstream=False, **ARGS)
        self.assertEqual(message, "")
        self.assertEqual(state, {})

    def test_upstream_then_runtime_each_alert_once(self):
        state, message = watch.transition({}, runtime=False, upstream=True, **ARGS)
        self.assertTrue(message.startswith(watch.MENTION))
        self.assertIn("doesn't have it yet", message)
        self.assertEqual(watch.transition(state, runtime=False, upstream=True, **ARGS)[1], "")
        state, message = watch.transition(state, runtime=True, upstream=True, **ARGS)
        self.assertIn("grilling", message)
        self.assertIn("Nothing was changed automatically", message)
        self.assertEqual(watch.transition(state, runtime=True, upstream=True, **ARGS)[1], "")

    def test_runtime_first_skips_upstream_alert(self):
        state, message = watch.transition({}, runtime=True, upstream=True, **ARGS)
        self.assertIn("Workarounds to revisit", message)
        self.assertEqual(watch.transition(state, runtime=True, upstream=True, **ARGS)[1], "")

    def test_stalled_alerts_once(self):
        args = dict(ARGS, pr_state="closed")
        state, message = watch.transition({}, runtime=False, upstream=False, **args)
        self.assertIn("stalled", message)
        self.assertEqual(watch.transition(state, runtime=False, upstream=False, **args)[1], "")
        args = dict(ARGS, issue_state="closed (not_planned)")
        self.assertIn("stalled", watch.transition({}, runtime=False, upstream=False, **args)[1])


if __name__ == "__main__":
    unittest.main()
