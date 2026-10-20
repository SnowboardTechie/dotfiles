"""Pin the approved active-job model routing without activating dormant jobs."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROVIDER = "claude-subscription-directsdk-experimental"
ROUTES = {
    "Workday Morning Brief": "claude-sonnet-5-5",
    "SGG PR Review Reminder": "claude-sonnet-5-5",
    "Workday Dependency Triage": "claude-sonnet-5-5",
    "Watch Matt Pocock skill updates": "claude-opus-5-5",
    "Watch Inkling-Small release": "claude-sonnet-5-5",
    "Watch Colibri GLM-5.2 Studio readiness": "claude-sonnet-5-5",
    "SGG Friday Recap": "claude-opus-5-5"
}
ACTIVE_NAMES = set(ROUTES)
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
                self.assertEqual(job["model"], ROUTES[name])
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
