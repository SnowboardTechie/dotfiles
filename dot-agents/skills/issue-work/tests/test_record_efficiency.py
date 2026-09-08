from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "record_efficiency.py"


def load_module():
    spec = importlib.util.spec_from_file_location("record_efficiency", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load record_efficiency.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EfficiencyPilotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.pilot = self.root / "issue-work-efficiency-pilot.json"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def record(self, issue_number: int, **overrides):
        value = {
            "task_shape": "substantial",
            "exploration_children": 0,
            "claude_prompts": 2,
            "correction_passes": 1,
            "review_invocations": 1,
            "targeted_risk_reviews": 0,
            "provider_capacity_start": 9,
            "provider_capacity_end": 12,
            "blocking_findings_after_initial_review": 3,
            "elapsed_to_reviewable_pr_seconds": 900,
            "quota_interruptions": 0,
            "completed_at": "2026-09-08T18:00:00Z",
        }
        value.update(overrides)
        return self.module.record_run(
            pilot_path=self.pilot,
            issue_url=f"https://private.example/repo/issues/{issue_number}",
            record=value,
        )

    def test_first_five_runs_receive_stable_sequence_without_issue_urls(self) -> None:
        for number in range(1, 6):
            result = self.record(number)
            self.assertEqual(result["sequence"], number)

        pilot = json.loads(self.pilot.read_text(encoding="utf-8"))
        self.assertEqual(pilot["version"], 1)
        self.assertEqual(pilot["target_runs"], 5)
        self.assertEqual([item["sequence"] for item in pilot["records"]], [1, 2, 3, 4, 5])
        self.assertNotIn("private.example", self.pilot.read_text(encoding="utf-8"))
        with self.assertRaisesRegex(self.module.PilotError, "already has five runs"):
            self.record(6)

    def test_rerecord_updates_same_slot_and_preserves_escape_observations(self) -> None:
        first = self.record(1)
        self.module.record_escape(
            pilot_path=self.pilot,
            issue_url="https://private.example/repo/issues/1",
            severity="Major",
            reference="review-comment-7",
            assessed_at="2026-09-09T18:00:00Z",
        )
        updated = self.record(1, claude_prompts=1)

        self.assertEqual(updated["sequence"], first["sequence"])
        self.assertEqual(updated["claude_prompts"], 1)
        self.assertEqual(len(updated["escaped_critical_major"]), 1)
        self.assertEqual(len(json.loads(self.pilot.read_text())["records"]), 1)

    def test_escape_assessment_is_explicit_and_report_waits_for_all_five(self) -> None:
        for number in range(1, 6):
            self.record(number)
        for number in range(1, 6):
            self.module.assess_escape_window(
                pilot_path=self.pilot,
                issue_url=f"https://private.example/repo/issues/{number}",
                assessed_at="2026-09-15T18:00:00Z",
            )
        self.module.record_escape(
            pilot_path=self.pilot,
            issue_url="https://private.example/repo/issues/3",
            severity="Critical",
            reference="post-publication-finding",
            assessed_at="2026-09-15T18:00:00Z",
        )

        report = self.module.report(self.pilot)
        self.assertTrue(report["evaluation_ready"])
        self.assertEqual(report["completed_runs"], 5)
        self.assertEqual(report["escaped_critical_major_count"], 1)
        self.assertEqual(report["quota_interruptions"], 0)

    def test_record_schema_rejects_missing_or_invalid_metrics(self) -> None:
        with self.assertRaisesRegex(self.module.PilotError, "missing fields"):
            self.module.record_run(
                pilot_path=self.pilot,
                issue_url="https://example.test/repo/issues/1",
                record={"task_shape": "substantial"},
            )
        with self.assertRaisesRegex(self.module.PilotError, "provider_capacity_start"):
            self.record(1, provider_capacity_start=101)
        with self.assertRaisesRegex(self.module.PilotError, "severity"):
            self.record(1)
            self.module.record_escape(
                pilot_path=self.pilot,
                issue_url="https://private.example/repo/issues/1",
                severity="Minor",
                reference="not-an-escape",
                assessed_at="2026-09-09T18:00:00Z",
            )

    def test_assessment_cannot_close_before_seven_day_window(self) -> None:
        self.record(1)
        with self.assertRaisesRegex(self.module.PilotError, "seven days"):
            self.module.assess_escape_window(
                pilot_path=self.pilot,
                issue_url="https://private.example/repo/issues/1",
                assessed_at="2026-09-14T17:59:59Z",
            )

    def test_malformed_existing_record_fails_closed(self) -> None:
        self.pilot.write_text(
            json.dumps(
                {
                    "version": 1,
                    "target_runs": 5,
                    "records": [{"sequence": 1, "issue_key": "x" * 64}],
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(self.module.PilotError, "record missing fields"):
            self.module.report(self.pilot)

    def test_concurrent_cli_records_receive_distinct_slots(self) -> None:
        record_paths = []
        for number in (1, 2):
            record_path = self.root / f"record-{number}.json"
            record_path.write_text(
                json.dumps(
                    {
                        "task_shape": "single-loop",
                        "exploration_children": 0,
                        "claude_prompts": 0,
                        "correction_passes": 0,
                        "review_invocations": 1,
                        "targeted_risk_reviews": 0,
                        "provider_capacity_start": None,
                        "provider_capacity_end": None,
                        "blocking_findings_after_initial_review": 0,
                        "elapsed_to_reviewable_pr_seconds": 30,
                        "quota_interruptions": 0,
                        "completed_at": "2026-09-08T18:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            record_paths.append(record_path)

        processes = [
            subprocess.Popen(
                [
                    sys.executable,
                    str(SCRIPT),
                    "record",
                    "--pilot",
                    str(self.pilot),
                    "--issue-url",
                    f"https://example.test/repo/issues/{number}",
                    "--record-file",
                    str(record_path),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for number, record_path in zip((1, 2), record_paths)
        ]
        results = [process.communicate(timeout=10) for process in processes]
        self.assertEqual([process.returncode for process in processes], [0, 0], results)
        pilot = json.loads(self.pilot.read_text(encoding="utf-8"))
        self.assertEqual(sorted(item["sequence"] for item in pilot["records"]), [1, 2])


if __name__ == "__main__":
    unittest.main()
