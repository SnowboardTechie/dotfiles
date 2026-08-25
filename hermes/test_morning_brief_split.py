from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "manifest.json"
WORK_PROMPT = ROOT / "automations" / "workday-morning-brief" / "prompt.md"
HINDSIGHT_CONFIG = ROOT / "hindsight" / "config.json"
PERSONAL_PROMPT = ROOT / "automations" / "personal-morning-brief" / "prompt.md"
WEEKLY_ORIENTATION_PROMPT = ROOT / "automations" / "personal-weekly-orientation" / "prompt.md"
WORK_COLLECTOR = ROOT / "scripts" / "sgg-morning-brief.py"
PERSONAL_COLLECTOR = ROOT / "scripts" / "personal-morning-brief.py"
WEEKLY_ORIENTATION_COLLECTOR = ROOT / "scripts" / "personal-weekly-orientation.py"
ALIGNMENT_COLLECTOR = ROOT / "scripts" / "personal-alignment-brief.py"


def load_personal_collector():
    spec = importlib.util.spec_from_file_location("personal_morning_brief", PERSONAL_COLLECTOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MorningBriefSplitContractTest(unittest.TestCase):
    # Scoped to the brief/alignment jobs this module owns. An exhaustive
    # manifest census here made every unrelated cron addition fail a
    # morning-brief test, which is test sensitivity, not coverage — each job
    # family pins its own models in its own tests.
    OWNED_JOBS = {
        "Workday Morning Brief": ("gpt-5.6-terra", "openai-codex", None),
        "Personal Morning Brief": ("gpt-5.6-terra", "openai-codex", None),
        "Personal Weekly Orientation": ("gpt-5.6-terra", "openai-codex", None),
        "Personal Weekday Close": ("gpt-5.6-terra", "openai-codex", None),
        "Personal Saturday Orientation": ("gpt-5.6-terra", "openai-codex", None),
        "Personal Sunday Reset": ("gpt-5.6-terra", "openai-codex", None),
        "Workday Dependency Triage": ("gpt-5.6-sol", "openai-codex", None),
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

    def test_manifest_routes_personal_morning_brief_to_second_brain(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        job = next(job for job in manifest["cronJobs"] if job["name"] == "Personal Morning Brief")

        self.assertEqual(job["schedule"], "20 7 * * 1-5")
        self.assertEqual(job["model"], "gpt-5.6-terra")
        self.assertEqual(job["provider"], "openai-codex")
        self.assertNotIn("baseUrl", job)
        self.assertEqual(job["deliver"], "matrix:!5hH-Wud0Gd7hS1Z214EwjEMUvqtH8FBVOZhIZj0sqR4")
        self.assertEqual(job["script"], "personal-morning-brief.py")
        self.assertEqual(job["workdir"], "/Users/bryan/second-brain")
        self.assertTrue(job["attachToSession"])
        self.assertTrue(job["carryPreviousOutput"])
        self.assertEqual(job["continuation"]["chatName"], "Second Brain")

    def test_manifest_adds_one_recurring_weekly_capture_prompt(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        job = next(job for job in manifest["cronJobs"] if job["name"] == "Personal Weekly Orientation")

        self.assertEqual(job["schedule"], "0 11 * * 0")
        self.assertEqual(job["script"], "personal-weekly-orientation.py")
        self.assertNotIn("repeat", job)
        self.assertTrue(job["attachToSession"])
        self.assertEqual(job["continuation"]["chatName"], "Second Brain")

    def test_completed_finite_pilots_are_not_recreated(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        jobs = {job["name"]: job for job in manifest["cronJobs"]}

        for name in (
            "Personal Weekday Close",
            "Personal Saturday Orientation",
            "Personal Sunday Reset",
        ):
            self.assertGreater(jobs[name]["repeat"], 0)
            self.assertIs(jobs[name]["createIfMissing"], False)

    def test_work_brief_excludes_personal_sources_and_sections(self) -> None:
        prompt = WORK_PROMPT.read_text(encoding="utf-8")
        collector = WORK_COLLECTOR.read_text(encoding="utf-8")

        self.assertIn("Personal projects, personal reminders, and personal calendar events belong in the Second Brain morning brief", prompt)
        self.assertNotIn("**Other recent projects**", prompt)
        self.assertNotIn("**Today's reminders**", prompt)
        self.assertNotIn("SECOND_BRAIN", collector)
        self.assertNotIn("collect_reminders", collector)
        self.assertIn('WORK_CALENDARS = {"Bryan @ Agile6"}', collector)

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

    def test_work_brief_reviews_only_granola_mcp_and_does_not_retain(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        job = next(job for job in manifest["cronJobs"] if job["name"] == "Workday Morning Brief")
        prompt = WORK_PROMPT.read_text(encoding="utf-8")
        hindsight = json.loads(HINDSIGHT_CONFIG.read_text(encoding="utf-8"))

        self.assertEqual(job["enabledToolsets"], ["file", "terminal", "granola", "no_mcp"])
        self.assertNotIn("memory", job["enabledToolsets"])
        self.assertNotIn("sgg-sync-workday-note.py", manifest["scripts"])
        self.assertIn("sgg-sync-workday-note.py", manifest["removedScripts"])
        self.assertEqual(manifest["hindsightConfig"], "hindsight/config.json")
        self.assertEqual(hindsight["memory_mode"], "tools")
        self.assertIs(hindsight["auto_recall"], False)
        self.assertIs(hindsight["auto_retain"], False)
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
        self.assertIn("Do not retain meeting content to Hindsight", prompt)
        self.assertIn("A successful empty result", prompt)
        self.assertIn("Report every nonempty `sourceErrors` entry", prompt)

    def test_personal_brief_excludes_sgg_work_details(self) -> None:
        prompt = PERSONAL_PROMPT.read_text(encoding="utf-8")
        collector = PERSONAL_COLLECTOR.read_text(encoding="utf-8")

        self.assertIn("Detailed SGG work state belongs only in the SGG morning brief", prompt)
        self.assertNotIn("SGG_NOTES", collector)
        self.assertIn('EXCLUDED_CALENDARS = {"Bryan @ Agile6", "Traci"}', collector)
        self.assertIn("Never use or mention events from Traci's calendar", prompt)
        self.assertNotIn("recentSecondBrainPaths", collector)
        self.assertIn("currentWeekDirection", collector)

    def test_personal_brief_is_delta_only_and_silent_when_unchanged(self) -> None:
        prompt = PERSONAL_PROMPT.read_text(encoding="utf-8")

        self.assertIn("previous completed delivery", prompt)
        self.assertIn("Do not repeat unchanged", prompt)
        self.assertIn('respond with exactly `[SILENT]`', prompt)
        self.assertIn("Never expose analysis, scratch work, or a drafting preamble", prompt)
        self.assertNotIn("**Today's reminders**: up to 5", prompt)

    def test_personal_collector_filters_prohibited_unattended_context(self) -> None:
        collector = load_personal_collector()
        rows = [
            {"title": "Put the bins out", "calendar": "Home"},
            {"title": "Buy wine", "calendar": "Home"},
        ]

        filtered = collector.filter_prohibited_rows(rows)

        self.assertEqual(filtered, [{"title": "Put the bins out", "calendar": "Home"}])

    def test_personal_collector_extracts_only_safe_active_weekly_direction(self) -> None:
        collector = load_personal_collector()
        note = """# Week

## Active Goals and Projects
- **Body:** Keep the gym as a workday reset.
- **Alcohol:** A prohibited unattended topic.

## Explicitly Parked
- Leave this out.
"""

        self.assertEqual(
            collector.extract_active_goals(note),
            ["**Body:** Keep the gym as a workday reset."],
        )

    def test_weekly_orientation_collector_is_minimal(self) -> None:
        collector = WEEKLY_ORIENTATION_COLLECTOR.read_text(encoding="utf-8")
        prompt = WEEKLY_ORIENTATION_PROMPT.read_text(encoding="utf-8")

        self.assertIn("nextWeekHubPath", collector)
        self.assertNotIn("collect_calendar", collector)
        self.assertNotIn("collect_reminders", collector)
        self.assertNotIn("collect_mail", collector)
        self.assertNotIn("collect_weather", collector)
        self.assertIn("exactly one concrete question", prompt)
        self.assertIn("Do not preview an agenda", prompt)

    def test_personal_collector_adds_authoritative_pacific_timestamps(self) -> None:
        collector = load_personal_collector()
        payload = {
            "generatedAt": "2026-08-18T08:22:32-07:00",
            "calendar": [
                {
                    "title": "Farmers Market",
                    "allDay": False,
                    "start": "2026-08-19T18:00:00Z",
                    "end": "2026-08-19T22:00:00Z",
                }
            ],
            "reminders": [
                {
                    "title": "Put trash and recycle bin out",
                    "dueDate": "2026-08-19T01:00:00Z",
                }
            ],
        }

        collector.add_authoritative_local_times(payload)

        self.assertEqual(payload["generatedLocalDate"], "2026-08-18")
        self.assertEqual(payload["generatedLocalWeekday"], "Tuesday")
        self.assertEqual(payload["calendar"][0]["localStart"], "2026-08-19T11:00:00-07:00")
        self.assertEqual(payload["calendar"][0]["localEnd"], "2026-08-19T15:00:00-07:00")
        self.assertEqual(payload["reminders"][0]["localDueDate"], "2026-08-18T18:00:00-07:00")

    def test_personal_prompt_requires_authoritative_local_timestamp_fields(self) -> None:
        prompt = PERSONAL_PROMPT.read_text(encoding="utf-8")

        self.assertIn("`generatedLocalDate` and `generatedLocalWeekday` are authoritative", prompt)
        self.assertIn("`localStart`, `localEnd`, `localDueDate`, and `localAlarmDate`", prompt)
        self.assertIn("Do not reinterpret the raw UTC timestamp fields", prompt)

    def test_personal_routines_do_not_resurface_alcohol_by_default(self) -> None:
        prompt_paths = [
            PERSONAL_PROMPT,
            WEEKLY_ORIENTATION_PROMPT,
            ROOT / "automations" / "personal-weekday-close" / "prompt.md",
            ROOT / "automations" / "personal-saturday-orientation" / "prompt.md",
            ROOT / "automations" / "personal-sunday-reset" / "prompt.md",
        ]
        for path in prompt_paths:
            prompt = path.read_text(encoding="utf-8").lower()
            self.assertIn("never", prompt, path)
            self.assertIn("sobriety", prompt, path)
            if path != PERSONAL_PROMPT:
                self.assertIn("unless bryan explicitly raises", prompt, path)

        skill = (ROOT / "skills" / "productivity" / "personal-routine-automation" / "SKILL.md").read_text(encoding="utf-8")
        contract = (ROOT / "skills" / "productivity" / "personal-routine-automation" / "references" / "bryan-personal-routine-contract.md").read_text(encoding="utf-8")
        self.assertNotIn("Bryan's alcohol direction is near-abstinence", skill)
        self.assertNotIn("Alcohol direction: as close to abstinence", contract)
        self.assertIn("unless Bryan explicitly raises that topic in the current conversation", skill)
        self.assertIn("unless Bryan explicitly raises that topic in the current conversation", contract)

    def test_personal_weather_uses_private_configuration(self) -> None:
        for path in (PERSONAL_COLLECTOR, ALIGNMENT_COLLECTOR):
            collector = path.read_text(encoding="utf-8")

            self.assertIn('os.environ.get("PERSONAL_WEATHER_LOCATION", "")', collector)
            self.assertIn('HOME / ".secrets" / "personal-weather-location"', collector)
            self.assertIn('f"https://wttr.in/{quote(location)}?format=j1"', collector)
            self.assertNotIn("wttr.in IP geolocation", collector)

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
