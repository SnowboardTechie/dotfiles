"""rex_wait.sh settles Pi and Claude worker turns the same way."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "rex_wait.sh"
HANDBACK = "Changes: done.\n\nDivergence: None\n"


def pi(role, stop=None):
    message = {"role": role}
    if stop:
        message["stopReason"] = stop
    return {"type": "message", "message": message}


def claude(kind, stop=None):
    return {"type": kind, "message": {"stop_reason": stop} if stop else {}}


class RexWaitTest(unittest.TestCase):
    def run_wait(self, records, handback=None, cap=3, **env):
        with tempfile.TemporaryDirectory() as tmp:
            transcript = Path(tmp, "t.jsonl")
            transcript.write_text("".join(json.dumps(r) + "\n" for r in records))
            hb = Path(tmp, "h.md")
            if handback is not None:
                hb.write_text(handback)
            full_env = {**os.environ, "REX_WAIT_POLL_SECONDS": "0.1", "REX_WAIT_ENDED_POLLS": "3", **env}
            return subprocess.run(
                ["sh", str(SCRIPT), str(transcript), str(hb), str(cap)],
                env=full_env, capture_output=True, text=True, timeout=30,
            )

    def test_pi_turn_that_stopped_with_handback_settles(self):
        got = self.run_wait([pi("user"), pi("assistant", "toolUse"), pi("toolResult"), pi("assistant", "stop")], HANDBACK)
        self.assertEqual(got.returncode, 0, got.stdout)
        self.assertIn("SETTLED", got.stdout)

    def test_pi_turn_still_calling_tools_does_not_settle(self):
        got = self.run_wait([pi("user"), pi("assistant", "toolUse")], HANDBACK, cap=1)
        self.assertEqual(got.returncode, 1, got.stdout)

    def test_pi_turn_ended_without_handback_exits_2(self):
        got = self.run_wait([pi("user"), pi("assistant", "stop")])
        self.assertEqual(got.returncode, 2, got.stdout)

    def test_pi_errored_turn_counts_as_ended(self):
        got = self.run_wait([pi("user"), pi("assistant", "error")], HANDBACK)
        self.assertEqual(got.returncode, 0, got.stdout)

    def test_pi_unanswered_tool_result_stalls(self):
        got = self.run_wait([pi("user"), pi("assistant", "toolUse"), pi("toolResult")], REX_WAIT_STALL_SECONDS="0")
        self.assertEqual(got.returncode, 3, got.stdout)

    def test_claude_transcript_still_settles(self):
        got = self.run_wait([claude("user"), claude("assistant", "end_turn")], HANDBACK)
        self.assertEqual(got.returncode, 0, got.stdout)

    def test_claude_unanswered_user_record_stalls(self):
        got = self.run_wait([claude("assistant", "end_turn"), claude("user")], REX_WAIT_STALL_SECONDS="0")
        self.assertEqual(got.returncode, 3, got.stdout)


if __name__ == "__main__":
    unittest.main()
