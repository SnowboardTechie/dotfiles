"""Retirement coverage for the Granola-to-Hindsight import pipeline.

The morning brief still reviews Granola directly (see
test_morning_brief_split.py); what is retired is the post-meeting copy into
Hindsight and the one-shot cron jobs that performed it.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
COLLECTOR = ROOT / "scripts" / "sgg-morning-brief.py"
IMPORTER = ROOT / "scripts" / "sgg-granola-import.py"
CALENDAR_COLLECTOR = ROOT / "scripts" / "sgg-calendar-events.swift"
MANIFEST = ROOT / "manifest.json"
AUTOMATIONS = ROOT / "automations"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tripwire_module(name: str, attribute: str) -> types.ModuleType:
    module = types.ModuleType(name)

    def refuse(*args, **kwargs):
        raise AssertionError(f"retired integration was contacted: {name}.{attribute}")

    setattr(module, attribute, refuse)
    return module


class GranolaImportRetirementTest(unittest.TestCase):
    def test_importer_is_neither_shipped_nor_scheduled(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

        self.assertFalse(IMPORTER.exists())
        self.assertNotIn("sgg-granola-import.py", manifest["scripts"])
        self.assertNotIn("sgg-granola-import.py", manifest["copiedScripts"])
        self.assertIn("sgg-granola-import.py", manifest["removedCopiedScripts"])
        for job in manifest["cronJobs"]:
            self.assertNotEqual(job.get("script"), "sgg-granola-import.py")
        for prompt in AUTOMATIONS.rglob("*.md"):
            with self.subTest(prompt=prompt.relative_to(ROOT)):
                text = prompt.read_text(encoding="utf-8")
                self.assertNotIn("sgg-granola-import.py", text)
                self.assertNotRegex(text, r"(?i)hindsight")

    def test_collector_contacts_no_hindsight_and_schedules_no_imports(self) -> None:
        collector = load_module(COLLECTOR, "sgg_morning_brief_for_retirement_test")
        commands: list[list[str]] = []

        def fake_command(args, *, timeout=45, cwd=None):
            commands.append(list(args))
            return "[]", None

        tripwires = {
            "hindsight_client": tripwire_module("hindsight_client", "Hindsight"),
            "tools": types.ModuleType("tools"),
            "tools.cronjob_tools": tripwire_module("tools.cronjob_tools", "cronjob"),
        }
        output = io.StringIO()
        with patch.dict(sys.modules, tripwires), patch.object(
            collector, "command", side_effect=fake_command
        ), redirect_stdout(output):
            exit_code = collector.main()

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(
            set(payload),
            {
                "generatedAt",
                "timezone",
                "previousWorkdayStart",
                "sourceErrors",
                "calendar",
                "email",
                "emailSourceCounts",
                "github",
                "notes",
            },
        )
        self.assertNotIn("hindsight", payload["sourceErrors"])
        self.assertNotIn("meetingNoteImports", payload["sourceErrors"])
        flattened = [" ".join(args).lower() for args in commands]
        self.assertFalse([args for args in flattened if "hindsight" in args])
        # Normal live sources are still collected.
        self.assertTrue(any(args.startswith("gws calendar") for args in flattened))
        self.assertTrue(any("osascript" in args for args in flattened))
        self.assertTrue(any(args.startswith("gh pr list") for args in flattened))
        self.assertTrue(any(args.startswith("git log") for args in flattened))

    def test_collector_has_no_meeting_status_subcommand(self) -> None:
        collector = load_module(COLLECTOR, "sgg_morning_brief_for_cli_test")

        for name in (
            "schedule_meeting_note_imports",
            "calendar_event_status",
            "calendar_event_status_for_job",
            "collect_hindsight",
            "cli",
        ):
            self.assertFalse(hasattr(collector, name), name)


class CalendarIdentityTest(unittest.TestCase):
    def test_google_calendar_row_preserves_recurring_occurrence_identity(self) -> None:
        collector = load_module(COLLECTOR, "sgg_morning_brief_for_google_calendar_test")
        event = {
            "id": "series_20260901T180000Z",
            "summary": "P&D Huddle",
            "status": "confirmed",
            "start": {"dateTime": "2026-09-01T11:00:00-07:00"},
            "end": {"dateTime": "2026-09-01T12:00:00-07:00"},
            "originalStartTime": {"dateTime": "2026-09-01T11:00:00-07:00"},
            "organizer": {"email": "laura@agile6.com", "displayName": "Laura"},
            "attendees": [
                {
                    "email": "bryan.thompson@agile6.com",
                    "displayName": "Bryan",
                    "self": True,
                    "responseStatus": "accepted",
                }
            ],
            "htmlLink": "https://calendar.google.com/calendar/event?eid=example",
        }

        row = collector._google_event_row(event)

        self.assertEqual(row["eventIdentifier"], event["id"])
        self.assertEqual(row["occurrenceDate"], "2026-09-01T11:00:00-07:00")
        self.assertEqual(row["calendar"], "Bryan @ Agile6")
        self.assertEqual(row["source"], "google_calendar")
        self.assertEqual(row["currentUserAttendee"]["status"], "accepted")

    def test_calendar_collector_exports_event_identity(self) -> None:
        source = CALENDAR_COLLECTOR.read_text(encoding="utf-8")

        self.assertIn("let eventIdentifier: String", source)
        self.assertIn("eventIdentifier: $0.eventIdentifier", source)
        self.assertIn("let occurrenceDate: Date?", source)
        self.assertIn("occurrenceDate: $0.occurrenceDate", source)


if __name__ == "__main__":
    unittest.main()
