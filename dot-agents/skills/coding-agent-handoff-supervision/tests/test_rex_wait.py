"""rex_wait.sh settles Pi and Claude background agent turns the same way."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "rex_wait.sh"
COMPLETION_REPORT = "Changes: done.\n\nDivergence: None\n"


def pi(role, stop=None):
    message = {"role": role}
    if stop:
        message["stopReason"] = stop
    return {"type": "message", "message": message}


def claude(kind, stop=None):
    return {"type": kind, "message": {"stop_reason": stop} if stop else {}}


class RexWaitTest(unittest.TestCase):
    def run_wait(self, records, completion_report=None, cap=3, marker=None, **env):
        with tempfile.TemporaryDirectory() as tmp:
            transcript = Path(tmp, "t.jsonl")
            transcript.write_text("".join(json.dumps(r) + "\n" for r in records))
            report = Path(tmp, "h.md")
            if completion_report is not None:
                report.write_text(completion_report)
            full_env = {**os.environ, "REX_WAIT_POLL_SECONDS": "0.1", "REX_WAIT_ENDED_POLLS": "3", **env}
            return subprocess.run(
                ["sh", str(SCRIPT), str(transcript), str(report), str(cap), *([marker] if marker else [])],
                env=full_env, capture_output=True, text=True, timeout=30,
            )

    def test_pi_turn_that_stopped_with_completion_report_settles(self):
        got = self.run_wait([pi("user"), pi("assistant", "toolUse"), pi("toolResult"), pi("assistant", "stop")], COMPLETION_REPORT)
        self.assertEqual(got.returncode, 0, got.stdout)
        self.assertIn("SETTLED", got.stdout)

    def test_pi_turn_still_calling_tools_does_not_settle(self):
        got = self.run_wait([pi("user"), pi("assistant", "toolUse")], COMPLETION_REPORT, cap=1)
        self.assertEqual(got.returncode, 1, got.stdout)

    def test_pi_turn_ended_without_completion_report_exits_2(self):
        got = self.run_wait([pi("user"), pi("assistant", "stop")])
        self.assertEqual(got.returncode, 2, got.stdout)

    def test_pi_errored_turn_counts_as_ended(self):
        got = self.run_wait([pi("user"), pi("assistant", "error")], COMPLETION_REPORT)
        self.assertEqual(got.returncode, 0, got.stdout)

    def test_pi_unanswered_tool_result_stalls(self):
        got = self.run_wait([pi("user"), pi("assistant", "toolUse"), pi("toolResult")], REX_WAIT_STALL_SECONDS="0")
        self.assertEqual(got.returncode, 3, got.stdout)

    def test_claude_transcript_still_settles(self):
        got = self.run_wait([claude("user"), claude("assistant", "end_turn")], COMPLETION_REPORT)
        self.assertEqual(got.returncode, 0, got.stdout)

    def test_claude_unanswered_user_record_stalls(self):
        got = self.run_wait([claude("assistant", "end_turn"), claude("user")], REX_WAIT_STALL_SECONDS="0")
        self.assertEqual(got.returncode, 3, got.stdout)

    def test_divergence_heading_followed_by_a_list_settles(self):
        # A background agent wrote this shape on 2026-11-24 and the watch never settled.
        report = "Changes: done.\n\nDivergence:\n\n- Ran CI through `pnpm run ci`.\n- Used `nix run` for actionlint.\n"
        got = self.run_wait([pi("user"), pi("assistant", "stop")], report)
        self.assertEqual(got.returncode, 0, got.stdout)

    def test_divergence_followed_by_a_bold_wrapped_line_settles(self):
        report = "Changes: done.\n\n**Divergence:** none.\n"
        got = self.run_wait([pi("user"), pi("assistant", "stop")], report)
        self.assertEqual(got.returncode, 0, got.stdout)

    def test_divergence_above_a_later_section_does_not_settle(self):
        # A correction turn appends a new section after the earlier Divergence line; the new section isn't done yet.
        report = "Changes: done.\n\nDivergence: None\n\n## Rereview 1\n\nRun the rereview.\n"
        got = self.run_wait([pi("user"), pi("assistant", "stop")], report)
        self.assertEqual(got.returncode, 2, got.stdout)

    def test_marker_section_settles_on_its_own_divergence_list(self):
        report = (
            "Changes: done.\n\nDivergence: None\n\n## Rereview 1\n\nRun it.\n\n"
            "## Rereview 1 result\n\nReady.\n\nDivergence:\n\n- Skipped the probe.\n"
        )
        got = self.run_wait([pi("user"), pi("assistant", "stop")], report, marker="Rereview 1 result")
        self.assertEqual(got.returncode, 0, got.stdout)


if __name__ == "__main__":
    unittest.main()
