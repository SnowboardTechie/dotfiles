from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CALENDAR_SOURCE = ROOT / "scripts" / "sgg-calendar-events.swift"
BRIEF_PROMPT = ROOT / "automations" / "workday-morning-brief" / "prompt.md"


class CalendarBriefContractTest(unittest.TestCase):
    def test_calendar_payload_includes_bounded_participant_metadata(self) -> None:
        source = CALENDAR_SOURCE.read_text(encoding="utf-8")

        self.assertIn("organizer: participantSummary($0.organizer)", source)
        self.assertIn("currentUserAttendee: currentUserAttendee($0.attendees)", source)
        self.assertIn("attendeeCount: $0.attendees?.count ?? 0", source)

    def test_prompt_does_not_infer_presentation_ownership_from_title(self) -> None:
        prompt = BRIEF_PROMPT.read_text(encoding="utf-8")

        self.assertIn(
            "Never infer that Bryan owns presentation or preparation from an event title",
            prompt,
        )
        self.assertIn("organizer.isCurrentUser", prompt)


if __name__ == "__main__":
    unittest.main()
