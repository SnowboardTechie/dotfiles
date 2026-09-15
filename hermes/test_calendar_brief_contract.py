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

    def test_event_status_resolves_the_scheduled_occurrence_not_the_first_one(self) -> None:
        """event(withIdentifier:) returns a series' FIRST occurrence, so status
        for a recurring meeting must come from a windowed occurrence lookup."""
        source = CALENDAR_SOURCE.read_text(encoding="utf-8")
        status_branch = source.split('arguments[0] == "--event-status"', 1)[1]
        status_branch = status_branch.split("let start = systemCalendar", 1)[0]

        self.assertIn("store.predicateForEvents(", status_branch)
        self.assertIn("$0.eventIdentifier == identifier", status_branch)
        self.assertIn("timeIntervalSince(expectedOccurrence)", status_branch)
        # A moved occurrence is still an active meeting, never a cancellation.
        self.assertIn('status: "active", reason: "calendar event was rescheduled"', status_branch)
        # The identifier lookup may only be a fallback behind the window search.
        self.assertIn("occurrence ?? store.event(withIdentifier: identifier)", status_branch)
        self.assertNotIn("guard let event = store.event(withIdentifier:", status_branch)

    def test_prompt_does_not_infer_presentation_ownership_from_title(self) -> None:
        prompt = BRIEF_PROMPT.read_text(encoding="utf-8")

        self.assertIn(
            "Never infer that Bryan owns presentation or preparation from an event title",
            prompt,
        )
        self.assertIn("organizer.isCurrentUser", prompt)


if __name__ == "__main__":
    unittest.main()
