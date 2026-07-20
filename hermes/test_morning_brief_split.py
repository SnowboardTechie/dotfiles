from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "manifest.json"
WORK_PROMPT = ROOT / "automations" / "workday-morning-brief" / "prompt.md"
PERSONAL_PROMPT = ROOT / "automations" / "personal-morning-brief" / "prompt.md"
WORK_COLLECTOR = ROOT / "scripts" / "sgg-morning-brief.py"
PERSONAL_COLLECTOR = ROOT / "scripts" / "personal-morning-brief.py"


class MorningBriefSplitContractTest(unittest.TestCase):
    def test_manifest_routes_personal_morning_brief_to_second_brain(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        job = next(job for job in manifest["cronJobs"] if job["name"] == "Personal Morning Brief")

        self.assertEqual(job["schedule"], "20 7 * * 1-5")
        self.assertEqual(job["deliver"], "matrix:!5hH-Wud0Gd7hS1Z214EwjEMUvqtH8FBVOZhIZj0sqR4")
        self.assertEqual(job["script"], "personal-morning-brief.py")
        self.assertEqual(job["workdir"], "/Users/bryan/second-brain")
        self.assertTrue(job["attachToSession"])
        self.assertEqual(job["continuation"]["chatName"], "Second Brain")

    def test_work_brief_excludes_personal_sources_and_sections(self) -> None:
        prompt = WORK_PROMPT.read_text(encoding="utf-8")
        collector = WORK_COLLECTOR.read_text(encoding="utf-8")

        self.assertIn("Personal projects, personal reminders, and personal calendar events belong in the Second Brain morning brief", prompt)
        self.assertNotIn("**Other recent projects**", prompt)
        self.assertNotIn("**Today's reminders**", prompt)
        self.assertNotIn("SECOND_BRAIN", collector)
        self.assertNotIn("collect_reminders", collector)
        self.assertIn('WORK_CALENDARS = {"Bryan @ Agile6"}', collector)

    def test_personal_brief_excludes_sgg_work_details(self) -> None:
        prompt = PERSONAL_PROMPT.read_text(encoding="utf-8")
        collector = PERSONAL_COLLECTOR.read_text(encoding="utf-8")

        self.assertIn("Detailed SGG work state belongs only in the SGG morning brief", prompt)
        self.assertNotIn("SGG_NOTES", collector)
        self.assertIn('WORK_CALENDARS = {"Bryan @ Agile6"}', collector)
        self.assertIn("recentSecondBrainPaths", collector)

    def test_work_brief_does_not_promote_proposals_or_other_peoples_actions(self) -> None:
        prompt = WORK_PROMPT.read_text(encoding="utf-8")

        self.assertIn(
            "A proposal, deadline, meeting discussion, or action assigned to someone else is not Bryan's priority",
            prompt,
        )
        self.assertIn("Prefer an explicit current resting point", prompt)
        self.assertIn("Preserve assignees exactly", prompt)
        self.assertIn(
            "If no source explicitly establishes Bryan's primary outcome, say so rather than inventing one",
            prompt,
        )


if __name__ == "__main__":
    unittest.main()
