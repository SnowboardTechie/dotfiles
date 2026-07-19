from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("sgg-pr-review-event.py")
SPEC = importlib.util.spec_from_file_location("sgg_pr_review_event", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def pr(author: str = "SnowboardTechie") -> dict:
    return {
        "number": 42,
        "title": "Improve <unsafe> behavior ](https://example.invalid)",
        "html_url": "https://github.com/HHS/simpler-grants-protocol/pull/42",
        "user": {"login": author},
        "state": "open",
        "draft": False,
    }


def payload(kind: str, *, actor: str = "reviewer") -> dict:
    value = {
        "action": "submitted",
        "repository": {"full_name": "HHS/simpler-grants-protocol"},
        "sender": {"login": actor, "type": "User"},
        "pull_request": pr(),
    }
    if kind == "review":
        value["review"] = {
            "state": "approved",
            "body": "Looks good @room [click](https://example.invalid)",
        }
    elif kind == "review_comment":
        value["action"] = "created"
        value["comment"] = {"body": "Please rename <Thing>."}
    elif kind == "review_requested":
        value["action"] = "review_requested"
        value["pull_request"] = pr("teammate")
        value["requested_reviewer"] = {"login": "SnowboardTechie"}
    return value


def fetched() -> dict:
    return {
        **pr(),
        "title": "Verified title",
        "state": "open",
        "draft": False,
        "merged_at": None,
    }


class EventTransformTest(unittest.TestCase):
    def test_accepts_review_on_authored_pr_and_reads_back(self) -> None:
        result = MODULE.transform(payload("review"), lambda _repo, _number: fetched())
        self.assertEqual(result["state"], "open")
        self.assertEqual(result["source_health"], "verified")
        self.assertIn("approved", result["change"])
        self.assertNotIn("@", result["detail"])
        self.assertNotIn("](https://", result["detail"])
        self.assertEqual(
            result["url"],
            "https://github.com/HHS/simpler-grants-protocol/pull/42",
        )

    def test_accepts_review_request_for_owner(self) -> None:
        result = MODULE.transform(payload("review_requested"), lambda _repo, _number: fetched())
        self.assertIn("requested your review", result["change"])

    def test_accepts_review_comment_and_sanitizes_markup(self) -> None:
        result = MODULE.transform(payload("review_comment"), lambda _repo, _number: fetched())
        self.assertEqual(result["detail"], "Please rename ‹Thing›.")

    def test_suppresses_self_and_bot_events(self) -> None:
        self.assertIsNone(MODULE.transform(payload("review", actor="SnowboardTechie")))
        bot = payload("review", actor="dependabot[bot]")
        bot["sender"]["type"] = "Bot"
        self.assertIsNone(MODULE.transform(bot))

    def test_suppresses_other_repository_and_non_actionable_change(self) -> None:
        other = payload("review")
        other["repository"]["full_name"] = "HHS/other"
        self.assertIsNone(MODULE.transform(other))
        changed = payload("review")
        changed["action"] = "edited"
        self.assertIsNone(MODULE.transform(changed))

    def test_marks_failed_readback_without_dropping_event(self) -> None:
        def fail(_repo: str, _number: int) -> dict:
            raise OSError("offline")

        result = MODULE.transform(payload("review"), fail)
        self.assertEqual(result["source_health"], "readback unavailable")
        self.assertEqual(
            result["title"],
            "Improve ‹unsafe› behavior ］（https://example.invalid）",
        )


if __name__ == "__main__":
    unittest.main()
