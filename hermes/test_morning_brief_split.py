from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "manifest.json"
WORK_PROMPT = ROOT / "automations" / "workday-morning-brief" / "prompt.md"
WORK_COLLECTOR = ROOT / "scripts" / "sgg-morning-brief.py"


class MorningBriefSplitContractTest(unittest.TestCase):
    # Scoped to the brief jobs this module owns. An exhaustive manifest
    # census here made every unrelated cron addition fail a morning-brief
    # test, which is test sensitivity, not coverage — each job family pins
    # its own models in its own tests.
    OWNED_JOBS = {
        "Workday Morning Brief": ("gpt-6.1-sol", "openai-codex", None),
        "Workday Dependency Triage": ("gpt-6.1-sol", "openai-codex", None),
    }

    def test_manifest_pins_each_owned_job_to_its_intended_model(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        jobs = {job["name"]: job for job in manifest["cronJobs"]}
        missing = sorted(set(self.OWNED_JOBS) - set(jobs))
        self.assertEqual(missing, [], f"manifest lost owned job(s): {missing}")
        for name, (model, provider, base_url) in self.OWNED_JOBS.items():
            with self.subTest(job=name):
                self.assertEqual(jobs[name]["model"], model)
                self.assertEqual(jobs[name]["provider"], provider)
                self.assertEqual(jobs[name].get("baseUrl"), base_url)

    def test_every_human_briefing_is_threaded_and_continuable(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for job in manifest["cronJobs"]:
            with self.subTest(job=job["name"]):
                self.assertIn(job["deliveryIntent"], {"briefing", "alert"})
                if job["deliveryIntent"] == "briefing":
                    self.assertTrue(job["attachToSession"])
                    self.assertEqual(
                        job["continuation"]["userEnv"], "MATRIX_ALLOWED_USERS"
                    )
                else:
                    self.assertFalse(job["attachToSession"])
                    self.assertNotIn("continuation", job)

    def test_every_agent_job_uses_the_codex_subscription(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for job in manifest["cronJobs"]:
            with self.subTest(job=job["name"]):
                if job["noAgent"]:
                    self.assertIsNone(job["model"])
                    self.assertIsNone(job["provider"])
                else:
                    self.assertTrue(job["model"].startswith("gpt-"))
                    self.assertEqual(job["provider"], "openai-codex")
                self.assertIsNone(job.get("baseUrl"))

    def test_retired_personal_routines_are_removed_from_the_studio(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

        self.assertFalse([job["name"] for job in manifest["cronJobs"] if job["name"].startswith("Personal ")])
        self.assertNotIn("productivity/personal-routine-automation", manifest["skills"])
        self.assertIn("skills/productivity/personal-routine-automation", manifest["removedLinks"])
        self.assertIn("personal-mail-messages.js", manifest["removedScripts"])
        for name in (
            "personal_notes.py",
            "personal-morning-brief.py",
            "personal-weekly-orientation.py",
            "personal-alignment-brief.py",
        ):
            with self.subTest(script=name):
                self.assertNotIn(name, manifest["scripts"])
                self.assertRegex(manifest["removedCopiedScripts"][name], r"^[0-9a-f]{64}$")

    def test_work_brief_excludes_personal_sources_and_sections(self) -> None:
        prompt = WORK_PROMPT.read_text(encoding="utf-8")
        collector = WORK_COLLECTOR.read_text(encoding="utf-8")

        self.assertIn("Personal projects, personal reminders, and personal calendar events do not belong in this brief", prompt)
        self.assertNotIn("**Other recent projects**", prompt)
        self.assertNotIn("**Today's reminders**", prompt)
        self.assertNotIn("SECOND_BRAIN", collector)
        self.assertNotIn("collect_reminders", collector)
        self.assertIn('WORK_CALENDARS = {"Bryan @ Agile6"}', collector)
        self.assertIn("collect_google_calendar", collector)
        self.assertIn('"gws",', collector)

    def test_work_brief_uses_project_owned_sgg_vault_read_only(self) -> None:
        prompt = WORK_PROMPT.read_text(encoding="utf-8")
        collector = WORK_COLLECTOR.read_text(encoding="utf-8")

        self.assertIn("/Users/bryan/code/sgg/vault/AGENTS.md", prompt)
        self.assertIn("The workday-note pilot is concluded", prompt)
        self.assertNotIn("sgg-sync-workday-note.py", prompt)
        self.assertNotIn("Workday note: synced.", prompt)
        self.assertNotIn("/Users/bryan/code/notes/sgg", prompt)
        self.assertIn('VAULT_ROOT = SGG_ROOT / "vault"', collector)
        self.assertIn('"previousWorkdayHistory": sgg_history[:15000]', collector)
        self.assertIn('        "vault",', collector)
        self.assertNotIn("NOTES_ROOT", collector)

    def test_work_brief_reviews_granola_directly_without_hindsight(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        job = next(job for job in manifest["cronJobs"] if job["name"] == "Workday Morning Brief")
        prompt = WORK_PROMPT.read_text(encoding="utf-8")
        collector = WORK_COLLECTOR.read_text(encoding="utf-8")

        self.assertEqual(job["enabledToolsets"], ["file", "terminal", "granola", "no_mcp"])
        self.assertNotIn("memory", job["enabledToolsets"])
        self.assertNotIn("sgg-sync-workday-note.py", manifest["scripts"])
        self.assertIn("sgg-sync-workday-note.py", manifest["removedScripts"])
        self.assertEqual(job["schedule"], "0 8 * * 1-5")
        self.assertEqual(job["script"], "sgg-morning-brief.py")
        self.assertTrue(job["deliver"].startswith("matrix:"))
        for text in (prompt, collector):
            self.assertNotRegex(text, r"(?i)hindsight")
            self.assertNotIn("sgg-granola-import.py", text)
            self.assertNotIn("meetingNoteImports", text)
            self.assertNotIn("Import Granola meeting", text)
        self.assertEqual(
            manifest["mcpRequirements"]["granola"]["tools"]["include"],
            ["list_meetings", "get_meetings"],
        )
        self.assertIs(
            manifest["mcpRequirements"]["granola"]["tools"]["resources"], False
        )
        self.assertIs(
            manifest["mcpRequirements"]["granola"]["tools"]["prompts"], False
        )
        self.assertEqual(
            manifest["mcpRequirements"]["granola_full"]["tools"]["exclude"], []
        )
        self.assertIn("Review completed Granola meetings", prompt)
        self.assertIn("not demonstrably about SGG", prompt)
        self.assertIn("never fetch their details to decide relevance", prompt)
        self.assertIn("call `get_meetings` once", prompt)
        self.assertNotIn("query_granola_meetings", prompt)
        self.assertIn("meeting title, date, and meeting ID", prompt)
        self.assertIn("Do not invent a link", prompt)
        self.assertIn("Do not retrieve transcripts", prompt)
        self.assertIn("Never retain, archive, copy, or mirror Granola meeting content", prompt)
        self.assertIn("Do not create, update, or remove any scheduled job", prompt)
        self.assertNotIn("sgg-granola-import.py", manifest["scripts"])
        self.assertIn("A successful empty result", prompt)
        self.assertIn("Report every nonempty `sourceErrors` entry", prompt)

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
