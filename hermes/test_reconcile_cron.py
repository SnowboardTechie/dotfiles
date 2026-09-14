from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("reconcile_cron.py")
SPEC = importlib.util.spec_from_file_location("reconcile_cron", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ValueComparisonTest(unittest.TestCase):
    def test_workdir_symlink_and_resolved_path_match(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            real = root / "real"
            real.mkdir()
            linked = root / "linked"
            linked.symlink_to(real)
            self.assertTrue(MODULE.values_match("workdir", str(linked), str(real)))

    def test_other_values_remain_exact(self) -> None:
        self.assertFalse(MODULE.values_match("deliver", "matrix", "matrix:!room"))


class ContinuationOriginTest(unittest.TestCase):
    def definition(self, **overrides: object) -> dict:
        definition = {
            "name": "Test Brief",
            "deliver": "matrix:!room",
            "attachToSession": True,
            "continuation": {
                "chatName": "Test Room",
                "userEnv": "MATRIX_ALLOWED_USERS",
            },
        }
        definition.update(overrides)
        return definition

    def test_builds_explicit_matrix_origin(self) -> None:
        with patch.dict(os.environ, {"MATRIX_ALLOWED_USERS": "@bryan:example.test"}):
            origin = MODULE.continuation_origin(self.definition())

        self.assertEqual(
            origin,
            {
                "platform": "matrix",
                "chat_id": "!room",
                "chat_name": "Test Room",
                "thread_id": None,
                "user_id": "@bryan:example.test",
            },
        )

    def test_non_continuable_job_has_no_origin(self) -> None:
        definition = self.definition(attachToSession=False)
        definition.pop("continuation")
        self.assertIsNone(MODULE.continuation_origin(definition))

    def test_rejects_metadata_on_non_continuable_job(self) -> None:
        with self.assertRaises(SystemExit):
            MODULE.continuation_origin(self.definition(attachToSession=False))

    def test_rejects_home_channel_fallback(self) -> None:
        with patch.dict(os.environ, {"MATRIX_ALLOWED_USERS": "@bryan:example.test"}):
            with self.assertRaises(SystemExit):
                MODULE.continuation_origin(self.definition(deliver="matrix"))

    def test_requires_exactly_one_user(self) -> None:
        with patch.dict(
            os.environ,
            {"MATRIX_ALLOWED_USERS": "@one:example.test,@two:example.test"},
        ):
            with self.assertRaises(SystemExit):
                MODULE.continuation_origin(self.definition())

    def test_requires_continuation_metadata(self) -> None:
        definition = self.definition()
        definition.pop("continuation")
        with self.assertRaises(SystemExit):
            MODULE.continuation_origin(definition)


class InferenceRouteTest(unittest.TestCase):
    def definition(self, **overrides: object) -> dict:
        definition = {
            "name": "Test Brief",
            "model": "gpt-5.6-terra",
            "provider": "openai-codex",
            "noAgent": False,
        }
        definition.update(overrides)
        return definition

    def test_accepts_codex_subscription_route(self) -> None:
        MODULE.verify_inference_route(self.definition())

    def test_accepts_model_free_no_agent_job(self) -> None:
        MODULE.verify_inference_route(
            self.definition(model=None, provider=None, noAgent=True)
        )

    def test_rejects_non_codex_agent_routes(self) -> None:
        cases = (
            {"provider": "openrouter"},
            {"provider": "custom:local-gemma4", "model": "gemma4:31b-mlx"},
            {"baseUrl": "https://openrouter.ai/api/v1"},
            {"model": None},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides), self.assertRaises(SystemExit):
                MODULE.verify_inference_route(self.definition(**overrides))

    def test_rejects_inference_fields_on_no_agent_job(self) -> None:
        with self.assertRaises(SystemExit):
            MODULE.verify_inference_route(self.definition(noAgent=True))


class MCPRequirementTest(unittest.TestCase):
    def write_config(self, root: Path, servers: dict) -> None:
        import yaml

        root.mkdir(parents=True, exist_ok=True)
        (root / "config.yaml").write_text(
            yaml.safe_dump({"mcp_servers": servers}), encoding="utf-8"
        )

    def requirements(self) -> dict:
        return {
            "mcpRequirements": {
                "granola": {
                    "url": "https://mcp.granola.ai/mcp",
                    "auth": "oauth",
                    "enabled": True,
                    "tools": {
                        "include": ["list_meetings", "get_meetings"],
                        "exclude": [],
                        "resources": False,
                        "prompts": False,
                    },
                }
            }
        }

    def test_accepts_exact_restricted_granola_configuration(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_config(
                root,
                {
                    "granola": {
                        "url": "https://mcp.granola.ai/mcp",
                        "auth": "oauth",
                        "enabled": True,
                        "tools": {
                            "include": ["get_meetings", "list_meetings"],
                            "exclude": [],
                            "resources": False,
                            "prompts": False,
                        },
                    }
                },
            )
            with patch.dict(os.environ, {"HERMES_HOME": str(root)}):
                MODULE.verify_mcp_requirements(self.requirements())

    def test_rejects_missing_or_overbroad_granola_configuration(self) -> None:
        import tempfile

        cases = (
            {},
            {
                "granola": {
                    "url": "https://mcp.granola.ai/mcp",
                    "auth": "oauth",
                    "enabled": True,
                }
            },
        )
        for servers in cases:
            with self.subTest(servers=servers), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.write_config(root, servers)
                with patch.dict(os.environ, {"HERMES_HOME": str(root)}):
                    with self.assertRaises(SystemExit):
                        MODULE.verify_mcp_requirements(self.requirements())

    def test_rejects_filtered_full_interactive_alias(self) -> None:
        import tempfile

        requirements = {
            "mcpRequirements": {
                "granola_full": {
                    "url": "https://mcp.granola.ai/mcp",
                    "auth": "oauth",
                    "enabled": True,
                    "tools": {
                        "include": [],
                        "exclude": [],
                        "resources": True,
                        "prompts": True,
                    },
                }
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_config(
                root,
                {
                    "granola_full": {
                        "url": "https://mcp.granola.ai/mcp",
                        "auth": "oauth",
                        "enabled": True,
                        "tools": {"exclude": ["get_meeting_transcript"]},
                    }
                },
            )
            with patch.dict(os.environ, {"HERMES_HOME": str(root)}):
                with self.assertRaises(SystemExit):
                    MODULE.verify_mcp_requirements(requirements)


class MonitorScriptTest(unittest.TestCase):
    """`monitorScript` reaches the scheduler and is verified on readback.

    The declarative key is validated here rather than at the API boundary
    because a rejection there arrives *after* the reconciler has reported the
    job synchronized.
    """

    def definition(self, **overrides: object) -> dict:
        definition = {
            "name": "Watch Something",
            "schedule": "5 9 * * 1",
            "model": "gpt-5.6-terra",
            "provider": "openai-codex",
            "promptFile": "automations/x/prompt.md",
            "monitorScript": "check-something.py",
            "deliver": "matrix",
            "skills": [],
            "script": None,
            "noAgent": False,
            "enabledToolsets": ["file"],
            "workdir": "/tmp",
            "attachToSession": False,
        }
        definition.update(overrides)
        return definition

    def test_manifest_declares_the_watcher_with_a_bare_filename(self) -> None:
        manifest = json.loads(
            (Path(__file__).with_name("manifest.json")).read_text(encoding="utf-8")
        )
        jobs = [j for j in manifest["cronJobs"] if j.get("monitorScript")]
        self.assertTrue(jobs, "manifest declares no monitor job")
        for job in jobs:
            with self.subTest(job=job["name"]):
                self.assertNotIn("/", job["monitorScript"])
                self.assertIn(job["monitorScript"], manifest["scripts"])
                self.assertFalse(job["noAgent"])
                self.assertTrue(
                    (Path(__file__).with_name("scripts") / job["monitorScript"]).is_file()
                )

    def test_a_monitor_job_ships_its_script(self) -> None:
        """A monitorScript absent from `scripts` never gets installed, so the
        scheduler would run a job whose source does not exist."""
        manifest = json.loads(
            (Path(__file__).with_name("manifest.json")).read_text(encoding="utf-8")
        )
        for job in manifest["cronJobs"]:
            monitor = job.get("monitorScript")
            if monitor:
                self.assertIn(monitor, manifest["scripts"], job["name"])

    def test_accepts_a_bare_filename(self) -> None:
        self.assertEqual(
            MODULE.monitor_script_value(self.definition()), "check-something.py"
        )

    def test_absent_key_means_no_monitor(self) -> None:
        definition = self.definition()
        definition.pop("monitorScript")
        self.assertIsNone(MODULE.monitor_script_value(definition))

    def test_rejects_a_path_shaped_monitor_script(self) -> None:
        for bad in ("scripts/check.py", "./check.py", "../check.py", "/abs/check.py"):
            with self.subTest(value=bad), self.assertRaises(SystemExit):
                MODULE.monitor_script_value(self.definition(monitorScript=bad))

    def test_rejects_an_empty_monitor_script(self) -> None:
        for bad in ("", "   ", 7):
            with self.subTest(value=bad), self.assertRaises(SystemExit):
                MODULE.monitor_script_value(self.definition(monitorScript=bad))

    def test_rejects_a_monitor_combined_with_no_agent(self) -> None:
        """A monitor exists to gate an agent run; with noAgent there is nothing to gate."""
        with self.assertRaises(SystemExit):
            MODULE.monitor_script_value(self.definition(noAgent=True))

    def test_every_job_declares_its_monitor_state_explicitly(self) -> None:
        """A job that dropped `monitorScript` must clear the live field.

        The reconciler sends `monitor_script` on every job — the declared name,
        or an empty string to clear — because omitting it would leave a stale
        monitor running while the reconciler reported the job synchronized.
        """
        manifest = json.loads(
            (Path(__file__).with_name("manifest.json")).read_text(encoding="utf-8")
        )
        for job in manifest["cronJobs"]:
            with self.subTest(job=job["name"]):
                value = MODULE.monitor_script_value(job)
                self.assertEqual(value or "", job.get("monitorScript") or "")

    def test_the_watcher_is_pinned_to_a_proven_research_route(self) -> None:
        """Owned here, not in the morning-brief tests, so each family pins its own."""
        manifest = json.loads(
            (Path(__file__).with_name("manifest.json")).read_text(encoding="utf-8")
        )
        job = next(
            j for j in manifest["cronJobs"] if j["name"] == "Watch Matt Pocock skill updates"
        )
        self.assertEqual(job["model"], "gpt-5.6-terra")
        self.assertEqual(job["provider"], "openai-codex")
        self.assertIsNone(job.get("baseUrl"), "a cloud route needs no base_url override")

    def test_prompt_file_for_every_cron_job_resolves(self) -> None:
        asset_root = Path(__file__).parent
        manifest = json.loads((asset_root / "manifest.json").read_text(encoding="utf-8"))
        for job in manifest["cronJobs"]:
            with self.subTest(job=job["name"]):
                self.assertTrue((asset_root / job["promptFile"]).is_file())

class MergedFeatureIntegrationTest(unittest.TestCase):
    """Where the watcher's `monitorScript` and the brief's continuity meet.

    Both features add fields to the *same* create/update payload and the same
    readback comparison. Each is covered on its own above and in
    `test_morning_brief_split.py`, so what is left — and what a merge can
    silently break — is the interaction: one feature's field surviving the
    other's code path.

    `main()` is driven end to end against fake `cron.jobs` and
    `tools.cronjob_tools` modules, so the payloads asserted here are the exact
    dicts the real scheduler would receive.
    """

    # Static so other contract classes can drive the same end-to-end path
    # without inheriting this class's own tests. It never touched `self`.
    @staticmethod
    def run_reconcile(
        jobs: list[dict],
        definitions: list[dict],
        env: dict[str, str] | None = None,
    ) -> dict:
        """Drive `reconcile_cron.main()` once and capture what it sent."""
        import sys as _sys
        import tempfile
        import types

        captured: dict = {"calls": [], "updates": []}
        # A fresh store per call, keyed by name, so readback sees what a write
        # would actually have stored.
        store = {job["name"]: dict(job) for job in jobs}

        minted = {"n": 0}

        def cronjob(*, action: str, job_id: str | None = None, **fields):
            captured["calls"].append({"action": action, "job_id": job_id, **fields})
            record = store.setdefault(fields["name"], {})
            if not (job_id or record.get("id")):
                # Distinct ids per creation. Reusing one made `update_job`
                # match the wrong record, which is exactly the kind of
                # cross-job bleed this class exists to catch.
                minted["n"] += 1
                record["id"] = f"minted-{minted['n']}"
            record["id"] = job_id or record["id"]
            record["name"] = fields["name"]
            record["schedule_display"] = fields.get(
                "schedule", record.get("schedule_display")
            )
            for key in (
                "model",
                "provider",
                "prompt",
                "deliver",
                "skills",
                "script",
                "no_agent",
                "enabled_toolsets",
                "workdir",
            ):
                if key in fields:
                    record[key] = fields[key]
            if "base_url" in fields:
                # The API stores an empty clear as absent, like the real one.
                record["base_url"] = fields["base_url"] or None
            if "monitor_script" in fields:
                record["monitor_script"] = fields["monitor_script"] or None
            if "attach_to_session" in fields:
                record["attach_to_session"] = fields["attach_to_session"]
            if "continuity" in fields:
                record["context_from"] = ["self"] if fields["continuity"] else []
            if "repeat" in fields:
                record["repeat"] = {"times": fields["repeat"]}
            return json.dumps({"success": True, "jobId": record["id"]})

        def list_jobs(include_disabled: bool = False):
            return [dict(job) for job in store.values()]

        def resolve_job_ref(name: str):
            job = store.get(name)
            return dict(job) if job else None

        def update_job(job_id: str, fields: dict):
            captured["updates"].append({"job_id": job_id, **fields})
            for record in store.values():
                if record["id"] == job_id:
                    record.update(fields)
                    return dict(record)
            return None

        cron_pkg = types.ModuleType("cron")
        cron_pkg.__path__ = []  # type: ignore[attr-defined]
        cron_jobs = types.ModuleType("cron.jobs")
        cron_jobs.list_jobs = list_jobs  # type: ignore[attr-defined]
        cron_jobs.resolve_job_ref = resolve_job_ref  # type: ignore[attr-defined]
        cron_jobs.update_job = update_job  # type: ignore[attr-defined]
        tools_pkg = types.ModuleType("tools")
        tools_pkg.__path__ = []  # type: ignore[attr-defined]
        cronjob_tools = types.ModuleType("tools.cronjob_tools")
        cronjob_tools.cronjob = cronjob  # type: ignore[attr-defined]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # One stand-in prompt per declared promptFile, so a real
            # manifest entry can be driven through this harness unchanged.
            for definition in definitions:
                prompt = root / definition["promptFile"]
                prompt.parent.mkdir(parents=True, exist_ok=True)
                prompt.write_text("Do the thing.\n", encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps({"cronJobs": definitions}), encoding="utf-8"
            )
            (root / "source").mkdir()
            injected = {
                "cron": cron_pkg,
                "cron.jobs": cron_jobs,
                "tools": tools_pkg,
                "tools.cronjob_tools": cronjob_tools,
            }
            saved = {k: _sys.modules.get(k) for k in injected}
            _sys.modules.update(injected)
            try:
                with patch.object(_sys, "argv", ["reconcile_cron.py", str(manifest)]), patch.dict(
                    os.environ,
                    {
                        "HERMES_SOURCE_ROOT": str(root / "source"),
                        "MATRIX_ALLOWED_USERS": "@bryan:example.test",
                        **(env or {}),
                    },
                ):
                    captured["rc"] = MODULE.main()
            finally:
                for key, value in saved.items():
                    if value is None:
                        _sys.modules.pop(key, None)
                    else:
                        _sys.modules[key] = value
        captured["store"] = store
        return captured

    WATCHER = {
        "name": "Watch Something",
        "schedule": "5 9 * * 1",
        "model": "gpt-5.6-terra",
        "provider": "openai-codex",
        "promptFile": "automations/x/prompt.md",
        "monitorScript": "check-something.py",
        "deliver": "matrix",
        "skills": [],
        "script": None,
        "noAgent": False,
        "enabledToolsets": ["web", "no_mcp"],
        "workdir": "/tmp",
        "attachToSession": False,
    }
    BRIEF = {
        "name": "Personal Brief",
        "schedule": "20 7 * * 1-5",
        "model": "gpt-5.6-terra",
        "provider": "openai-codex",
        "promptFile": "automations/x/prompt.md",
        "deliver": "matrix:!room",
        "skills": ["personal-routine-automation"],
        "script": "personal-morning-brief.py",
        "noAgent": False,
        "enabledToolsets": ["file", "terminal"],
        "workdir": "/tmp",
        "attachToSession": True,
        "carryPreviousOutput": True,
        "continuation": {"chatName": "Second Brain", "userEnv": "MATRIX_ALLOWED_USERS"},
    }

    def test_creating_both_families_sends_both_fields(self) -> None:
        result = self.run_reconcile([], [dict(self.WATCHER), dict(self.BRIEF)])
        self.assertEqual(result["rc"], 0)
        calls = {call["name"]: call for call in result["calls"]}
        self.assertEqual(
            calls["Watch Something"]["monitor_script"], "check-something.py"
        )
        self.assertFalse(
            calls["Watch Something"]["continuity"],
            "a watcher must not silently inherit continuity",
        )
        self.assertEqual(
            calls["Personal Brief"]["monitor_script"],
            "",
            "a non-monitor job must actively clear the field, not omit it",
        )
        self.assertTrue(calls["Personal Brief"]["continuity"])

    def test_a_brief_migrating_off_a_local_route_clears_base_url_and_monitor(self) -> None:
        """Both clears travel in the same update payload."""
        existing = {
            "id": "job-1",
            "name": "Personal Brief",
            "base_url": "http://127.0.0.1:11434/v1",
            "monitor_script": "stale-monitor.py",
            "context_from": [],
            "attach_to_session": True,
            "enabled": True,
            "state": "active",
        }
        result = self.run_reconcile([existing], [dict(self.BRIEF)])
        self.assertEqual(result["rc"], 0)
        update = result["calls"][0]
        self.assertEqual(update["action"], "update")
        self.assertEqual(update["base_url"], "")
        self.assertEqual(update["monitor_script"], "")
        self.assertTrue(update["continuity"])
        stored = result["store"]["Personal Brief"]
        self.assertIsNone(stored["base_url"])
        self.assertIsNone(stored["monitor_script"])

    def test_a_watcher_keeps_its_monitor_while_a_brief_gains_continuity(self) -> None:
        watcher = {
            "id": "job-w",
            "name": "Watch Something",
            "monitor_script": "check-something.py",
            "context_from": [],
            "attach_to_session": False,
            "enabled": True,
            "state": "active",
        }
        brief = {
            "id": "job-b",
            "name": "Personal Brief",
            "monitor_script": None,
            "context_from": [],
            "attach_to_session": True,
            "enabled": True,
            "state": "active",
        }
        result = self.run_reconcile(
            [watcher, brief], [dict(self.WATCHER), dict(self.BRIEF)]
        )
        self.assertEqual(result["rc"], 0)
        self.assertEqual(
            result["store"]["Watch Something"]["monitor_script"], "check-something.py"
        )
        self.assertEqual(result["store"]["Watch Something"]["context_from"], [])
        self.assertEqual(result["store"]["Personal Brief"]["context_from"], ["self"])
        self.assertIsNone(result["store"]["Personal Brief"]["monitor_script"])

    def test_a_terminal_job_keeps_its_schedule_while_both_fields_still_sync(self) -> None:
        """The repeat/terminal semantics must survive both features."""
        terminal = {
            "id": "job-t",
            "name": "Personal Brief",
            "schedule_display": "20 7 * * 1-5",
            "monitor_script": "stale-monitor.py",
            "base_url": "http://127.0.0.1:11434/v1",
            "context_from": [],
            "attach_to_session": True,
            "enabled": False,
            "state": "completed",
        }
        result = self.run_reconcile([terminal], [dict(self.BRIEF)])
        self.assertEqual(result["rc"], 0)
        update = result["calls"][0]
        self.assertNotIn(
            "schedule", update, "a completed job must not be rescheduled into life"
        )
        self.assertEqual(update["monitor_script"], "")
        self.assertEqual(update["base_url"], "")
        self.assertTrue(update["continuity"])

    def test_a_repeat_count_applies_only_on_creation(self) -> None:
        definition = dict(self.BRIEF, repeat=3)
        created = self.run_reconcile([], [definition])
        self.assertEqual(created["calls"][0]["repeat"], 3)
        existing = {
            "id": "job-1",
            "name": "Personal Brief",
            "context_from": [],
            "attach_to_session": True,
            "enabled": True,
            "state": "active",
            # Already created with the finite count; two runs are spent.
            "repeat": {"times": 3},
        }
        updated = self.run_reconcile([existing], [definition])
        self.assertNotIn(
            "repeat",
            updated["calls"][0],
            "reconciliation must not reset a finite pilot's remaining runs",
        )
        self.assertEqual(updated["store"]["Personal Brief"]["repeat"], {"times": 3})


class SssfUpstreamWatchTest(unittest.TestCase):
    """The tracked contract for `Watch SSSF upstream updates`.

    This watcher is a plain `script` job, not a `monitorScript` one, and that is
    the whole point: a monitor suppresses the run when its bytes repeat, and
    Bryan asked for a weekly report that *includes* the quiet weeks. A future
    edit promoting it to `monitorScript` would silently delete exactly the
    report it was built to send, so the absence of that key is asserted here
    rather than left to review.
    """

    NAME = "Watch SSSF upstream updates"
    ASSET_ROOT = Path(__file__).parent

    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            (cls.ASSET_ROOT / "manifest.json").read_text(encoding="utf-8")
        )

    def job(self) -> dict:
        for definition in self.manifest["cronJobs"]:
            if definition["name"] == self.NAME:
                return definition
        self.fail(f"manifest does not define {self.NAME!r}")

    # -- declarative contract ------------------------------------------------

    def test_it_is_a_weekly_report_not_a_change_suppressing_monitor(self) -> None:
        job = self.job()
        self.assertNotIn(
            "monitorScript",
            job,
            "a monitor suppresses unchanged runs, which would drop the quiet-week report",
        )
        self.assertEqual(job["script"], "check-sssf-upstream.py")
        self.assertIsNone(MODULE.monitor_script_value(job))

    def test_the_schedule_is_the_planned_weekly_monday_slot(self) -> None:
        self.assertEqual(self.job()["schedule"], "15 9 * * 1")

    def test_the_collector_is_declared_and_installed_as_a_copy(self) -> None:
        """The scheduler rejects a cron script whose symlink resolves outside
        `HERMES_HOME/scripts`, so this one has to be in `copiedScripts` too."""
        job = self.job()
        self.assertNotIn("/", job["script"])
        self.assertIn(job["script"], self.manifest["scripts"])
        self.assertIn(job["script"], self.manifest["copiedScripts"])
        script = self.ASSET_ROOT / "scripts" / job["script"]
        self.assertTrue(script.is_file())
        self.assertTrue(script.stat().st_mode & 0o111, "cron scripts are run directly")

    def test_the_workdir_is_the_sgg_workspace_that_holds_the_ledger(self) -> None:
        """The collector locates `factory/upstream.json` from the cron workdir,
        because as an installed copy it cannot find the repository any other way."""
        self.assertEqual(self.job()["workdir"], "/Users/bryan/code/sgg")

    def test_it_is_pinned_to_the_codex_route(self) -> None:
        job = self.job()
        self.assertEqual(job["model"], "gpt-5.6-terra")
        self.assertEqual(job["provider"], "openai-codex")
        self.assertIsNone(job.get("baseUrl"))
        MODULE.verify_inference_route(job)

    def test_it_delivers_to_the_sgg_room_without_continuation(self) -> None:
        job = self.job()
        self.assertEqual(
            job["deliver"], "matrix:!USHKqGpzKJq-4PQkLs_aDY_PxB_7AvS-xLSQGcdXVGU"
        )
        self.assertFalse(job["attachToSession"])
        self.assertNotIn("continuation", job)
        self.assertIsNone(MODULE.continuation_origin(job))

    def test_its_toolsets_are_read_only(self) -> None:
        job = self.job()
        for forbidden in ("file", "delegation", "development", "default", "skills", "safe"):
            with self.subTest(toolset=forbidden):
                self.assertNotIn(forbidden, job["enabledToolsets"])
        self.assertIn("no_mcp", job["enabledToolsets"])
        self.assertEqual(job["enabledToolsets"], ["no_mcp"])

    def test_its_prompt_resolves_and_always_reports(self) -> None:
        job = self.job()
        prompt = (self.ASSET_ROOT / job["promptFile"]).read_text(encoding="utf-8")
        self.assertIn("@bryan:snowboardtechie.com", prompt)
        self.assertIn("Every run produces a message", prompt)
        self.assertNotIn(
            "[SILENT]",
            prompt.replace("never answer `[SILENT]`", ""),
            "a weekly report has no silent branch",
        )
        for classification in (
            "update now",
            "review for update",
            "skip for now",
            "assessment blocked",
        ):
            with self.subTest(classification=classification):
                self.assertIn(classification, prompt)
        self.assertIn("no update to consider this week", prompt)

    def test_the_prompt_forbids_mutation(self) -> None:
        prompt = (self.ASSET_ROOT / self.job()["promptFile"]).read_text(encoding="utf-8")
        self.assertRegex(prompt, r"(?i)never .*(edit|advance|install|activate)")
        # Whitespace-tolerant: the prompt is wrapped prose, so a literal
        # substring assertion breaks on a reflow that changed nothing.
        self.assertRegex(prompt, r"never\s+advance the pin")
        self.assertRegex(prompt, r"never\s+push")

    def test_it_carries_the_skill_the_plan_assigned(self) -> None:
        self.assertEqual(self.job()["skills"], ["cross-agent-skill-migration"])

    # -- isolated reconciliation --------------------------------------------

    def live_cron_state(self) -> object:
        """A fingerprint of the real cron registry, or None when absent."""
        live = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
        jobs = live / "cron" / "jobs.json"
        return jobs.read_bytes() if jobs.is_file() else None

    def test_reconciling_it_touches_no_production_cron_state(self) -> None:
        """Driven end to end through `main()` against fake cron modules and a
        throwaway HERMES_HOME, then the real registry is compared byte for byte.
        """
        before = self.live_cron_state()
        with tempfile.TemporaryDirectory() as tmp:
            isolated = Path(tmp) / "hermes-home"
            (isolated / "cron").mkdir(parents=True)
            result = MergedFeatureIntegrationTest.run_reconcile(
                [], [self.job()], env={"HERMES_HOME": str(isolated)}
            )
            self.assertEqual(result["rc"], 0)
            self.assertFalse(
                (isolated / "cron" / "jobs.json").exists(),
                "reconciliation must not write a cron registry of its own",
            )
        self.assertEqual(before, self.live_cron_state(), "live cron state changed")

    def test_reconciliation_sends_the_script_and_clears_the_monitor_field(self) -> None:
        """`monitor_script` is sent as an empty string, never omitted: omitting
        it would leave a stale live monitor while reporting the job synced."""
        result = MergedFeatureIntegrationTest.run_reconcile([], [self.job()])
        call = next(c for c in result["calls"] if c["name"] == self.NAME)
        self.assertEqual(call["action"], "create")
        self.assertEqual(call["script"], "check-sssf-upstream.py")
        self.assertEqual(call["monitor_script"], "")
        self.assertFalse(call["continuity"])
        self.assertEqual(call["workdir"], "/Users/bryan/code/sgg")
        self.assertEqual(call["enabled_toolsets"], ["no_mcp"])

    def test_reconciling_it_leaves_an_unrelated_existing_job_alone(self) -> None:
        """It is added to a manifest that already owns live jobs; a new entry
        must not disturb one it does not name."""
        unrelated = {
            "id": "job-unrelated",
            "name": "Monitor Studio services",
            "schedule_display": "every 5m",
            "script": "check-studio-services.py",
            "enabled": True,
            "state": "active",
        }
        result = MergedFeatureIntegrationTest.run_reconcile([unrelated], [self.job()])
        self.assertEqual(result["rc"], 0)
        self.assertEqual(result["store"]["Monitor Studio services"], unrelated)
        self.assertEqual([c["name"] for c in result["calls"]], [self.NAME])


if __name__ == "__main__":
    unittest.main()
