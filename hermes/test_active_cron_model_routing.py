"""Pin the approved active-job model routing without activating dormant jobs."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODEL = "gpt-6.1-sol"
PROVIDER = "openai-codex"
ACTIVE_NAMES = {
    "Workday Morning Brief",
    "Watch Inkling-Small release",
    "Watch Colibri GLM-5.2 Studio readiness",
    "Workday Dependency Triage",
    "Watch Matt Pocock skill updates",
    "SGG PR Review Reminder",
    "SGG Friday Recap",
}
STANDALONE = (
    "inkling-small-release-watch",
    "colibri-glm52-readiness-watch",
    "sgg-friday-recap",
)


class ActiveCronModelRoutingTest(unittest.TestCase):
    def test_all_seven_active_jobs_have_the_approved_route(self):
        manifest = json.loads((ROOT / "manifest.json").read_text())
        jobs = {j["name"]: j for j in manifest["cronJobs"] if j["name"] in ACTIVE_NAMES}
        for name in STANDALONE:
            directory = ROOT / "automations" / name
            job = json.loads((directory / "job.json").read_text())
            self.assertNotIn(job["name"], jobs)
            self.assertTrue((directory / job["promptFile"]).is_file())
            jobs[job["name"]] = job
        self.assertEqual(set(jobs), ACTIVE_NAMES)
        for name, job in jobs.items():
            with self.subTest(job=name):
                self.assertEqual(job["model"], MODEL)
                self.assertEqual(job["provider"], PROVIDER)
                self.assertIsNone(job.get("baseUrl"))
                self.assertIsNone(job.get("base_url"))
                self.assertNotIn("reasoning_effort", job)

    def test_script_jobs_are_not_migrated(self):
        manifest = json.loads((ROOT / "manifest.json").read_text())
        for job in manifest["cronJobs"]:
            if job["noAgent"]:
                self.assertIsNone(job["model"])
                self.assertIsNone(job["provider"])


if __name__ == "__main__":
    unittest.main()
