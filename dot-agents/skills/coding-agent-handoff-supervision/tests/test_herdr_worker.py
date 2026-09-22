from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "herdr_worker.py"


def load_module():
    if not SCRIPT.is_file():
        raise AssertionError(f"missing helper: {SCRIPT}")
    spec = importlib.util.spec_from_file_location("herdr_worker", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeHerdr:
    def __init__(self, worktree: Path) -> None:
        self.worktree = worktree.resolve()
        self.panes = {"caller"}
        self.agents: dict[str, dict] = {}
        self.prompt_count = 0
        self.deliver_count = 0
        self.deliver_error: Exception | None = None
        self.split_count = 0
        self.answer_count = 0
        self.wait_after_seq: int | None = None
        self.interrupt_after_split = False
        # Status-only controls: what the waited turn settles to, or how it fails.
        self.prompt_status_after = "idle"
        self.prompt_error: Exception | None = None
        self.vanish_on_prompt = False
        self.read_count = 0
        self.runtime_session = "runtime-session"

    def status(self) -> str:
        return "endpoint_compatible: yes\nprivate_protocol_compatible: yes\n"

    def current_pane(self, pane_id: str) -> None:
        if pane_id not in self.panes:
            raise RuntimeError("missing caller pane")

    def split(self, *, pane_id: str, cwd: Path) -> str:
        if pane_id not in self.panes:
            raise RuntimeError("missing caller pane")
        self.split_count += 1
        self.panes.add("worker-pane")
        if self.interrupt_after_split:
            raise RuntimeError("interrupted after split")
        return "worker-pane"

    def start_agent(
        self,
        *,
        name: str,
        kind: str,
        pane_id: str,
        title: str,
        claude_model: str = "opus",
        claude_effort: str = "xhigh",
    ) -> None:
        self.agents[name] = {
            "agent": kind,
            "agent_session": {"value": self.runtime_session},
            "agent_status": "idle",
            "cwd": str(self.worktree),
            "name": name,
            "pane_id": pane_id,
            "state_change_seq": 1,
        }

    def get_agent(self, name: str) -> dict:
        if name not in self.agents:
            raise RuntimeError("missing agent")
        return {"result": {"agent": dict(self.agents[name])}}

    def list_agents(self) -> dict:
        return {"result": {"agents": [dict(agent) for agent in self.agents.values()]}}

    def prompt(self, *, name: str, text: str, timeout_ms: int) -> dict:
        self.prompt_count += 1
        if self.prompt_error is not None:
            raise self.prompt_error
        if self.vanish_on_prompt:
            del self.agents[name]
            return {}
        self.agents[name]["state_change_seq"] += 2
        self.agents[name]["agent_status"] = self.prompt_status_after
        return self.get_agent(name)

    def deliver(self, *, name: str, text: str) -> dict:
        if self.deliver_error is not None:
            raise self.deliver_error
        self.deliver_count += 1
        self.agents[name]["agent_status"] = "working"
        return self.get_agent(name)

    def read_agent(self, *, name: str, lines: int) -> str:
        self.read_count += 1
        return f"recent output for {name} ({lines})"

    def send_text(self, *, pane_id: str, text: str) -> None:
        if pane_id not in self.panes:
            raise RuntimeError("missing pane")
        self.answer_count += 1

    def send_keys(self, *, name: str, keys: list[str]) -> None:
        if name not in self.agents:
            raise RuntimeError("missing agent")
        self.answer_count += 1

    def wait_agent(self, *, name: str, after_seq: int, timeout_ms: int) -> dict:
        self.wait_after_seq = after_seq
        self.agents[name]["state_change_seq"] = after_seq + 1
        self.agents[name]["agent_status"] = "idle"
        return self.get_agent(name)

    def get_pane(self, pane_id: str) -> dict:
        if pane_id not in self.panes:
            raise RuntimeError("missing pane")
        return {
            "result": {
                "pane": {
                    "cwd": str(self.worktree),
                    "pane_id": pane_id,
                    "tab_id": "test-tab",
                    "terminal_id": f"terminal-{pane_id}",
                    "workspace_id": "test-workspace",
                }
            }
        }

    def list_panes(self) -> dict:
        return {
            "result": {
                "panes": [
                    self.get_pane(pane_id)["result"]["pane"]
                    for pane_id in sorted(self.panes)
                ]
            }
        }

    def close_pane(self, pane_id: str) -> None:
        self.panes.discard(pane_id)
        for name, agent in list(self.agents.items()):
            if agent["pane_id"] == pane_id:
                del self.agents[name]

    def agent_exists(self, name: str) -> bool:
        return name in self.agents

    def pane_exists(self, pane_id: str) -> bool:
        return pane_id in self.panes


class HerdrWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo, check=True)
        (self.repo / "README.md").write_text("test\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "Initial"], cwd=self.repo, check=True)

    def controller(self, capacity_code: int = 0):
        fake = FakeHerdr(self.repo)

        def capacity(required: bool):
            text = "Claude 5-hour capacity available: 12%; reset in 1:00"
            if capacity_code:
                text = "Claude 5-hour capacity exhausted (100%); reset in 1:00"
            return self.module.CapacityProbe(
                ok=capacity_code == 0,
                returncode=capacity_code,
                message=text,
            )

        controller = self.module.HandoffController(
            herdr=fake,
            capacity_probe=capacity,
            lease_path=self.root / "claude-turn.lock",
        )
        return controller, fake

    def test_start_prompt_and_close_preserve_identity(self) -> None:
        controller, fake = self.controller()
        identity_path = self.root / "identity.json"

        started = controller.start(
            caller_pane="caller",
            worktree=self.repo,
            identity_path=identity_path,
            name="worker",
            kind="claude",
            title="Test worker",
        )
        self.assertEqual(started["worker_pane_id"], "worker-pane")
        self.assertEqual(started["worker_runtime_session_id"], "runtime-session")

        result = controller.prompt(
            identity_path=identity_path,
            text="Implement the ticket",
            timeout_ms=60_000,
        )
        self.assertEqual(result["agent_status"], "idle")
        self.assertEqual(result["provider_capacity_start"], 12)
        self.assertEqual(result["provider_capacity_end"], 12)
        self.assertEqual(fake.prompt_count, 1)

        closed = controller.close(identity_path=identity_path)
        self.assertTrue(closed["closed"])
        self.assertNotIn("worker-pane", fake.panes)
        self.assertNotIn("worker", fake.agents)
        self.assertTrue(json.loads(identity_path.read_text(encoding="utf-8"))["closed"])
        self.assertTrue(controller.close(identity_path=identity_path)["closed"])

    def test_exhausted_capacity_prevents_prompt(self) -> None:
        controller, fake = self.controller()
        identity_path = self.root / "identity.json"
        controller.start(
            caller_pane="caller",
            worktree=self.repo,
            identity_path=identity_path,
            name="worker",
            kind="hermes",
            title="Test worker",
        )
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        identity["worker_kind"] = "claude"
        fake.agents["worker"]["agent"] = "claude"
        identity_path.write_text(json.dumps(identity), encoding="utf-8")
        controller.capacity_probe = lambda required: self.module.CapacityProbe(
            ok=False,
            returncode=75,
            message="Claude 5-hour capacity exhausted (100%); reset in 1:00",
        )

        with self.assertRaisesRegex(self.module.HandoffError, "capacity exhausted"):
            controller.prompt(
                identity_path=identity_path,
                text="Do not send this",
                timeout_ms=60_000,
            )
        self.assertEqual(fake.prompt_count, 0)

    def test_read_and_answer_blocked_preserve_identity_and_capacity(self) -> None:
        controller, fake = self.controller()
        identity_path = self.root / "identity.json"
        controller.start(
            caller_pane="caller",
            worktree=self.repo,
            identity_path=identity_path,
            name="worker",
            kind="claude",
            title="Test worker",
        )
        fake.agents["worker"]["agent_status"] = "blocked"
        fake.agents["unrelated"] = {
            "agent": "claude",
            "agent_session": {"value": "unrelated-runtime"},
            "agent_status": "working",
            "name": "unrelated",
        }

        with self.assertRaisesRegex(self.module.HandoffError, "use answer-blocked"):
            controller.prompt(
                identity_path=identity_path,
                text="Wrong input path",
                timeout_ms=60_000,
            )
        self.assertEqual(fake.prompt_count, 0)

        readback = controller.read(identity_path=identity_path, lines=40)
        self.assertIn("recent output for worker", readback["output"])
        self.assertEqual(fake.answer_count, 0)

        answered = controller.answer_blocked(
            identity_path=identity_path,
            text="Approved answer",
            keys=None,
            timeout_ms=60_000,
        )
        self.assertEqual(answered["agent_status"], "idle")
        self.assertEqual(answered["provider_capacity_start"], 12)
        self.assertEqual(fake.answer_count, 2)
        self.assertEqual(fake.wait_after_seq, 1)

    def test_second_start_refuses_existing_identity_without_new_pane(self) -> None:
        controller, fake = self.controller()
        identity_path = self.root / "identity.json"
        first = controller.start(
            caller_pane="caller",
            worktree=self.repo,
            identity_path=identity_path,
            name="worker",
            kind="claude",
            title="Test worker",
        )
        original = identity_path.read_bytes()

        with self.assertRaisesRegex(self.module.HandoffError, "already exists"):
            controller.start(
                caller_pane="caller",
                worktree=self.repo,
                identity_path=identity_path,
                name="second",
                kind="claude",
                title="Second worker",
            )
        self.assertEqual(fake.split_count, 1)
        self.assertEqual(identity_path.read_bytes(), original)
        self.assertIn(first["worker_agent_name"], fake.agents)

    def test_start_refuses_closed_identity_without_new_pane(self) -> None:
        controller, fake = self.controller()
        identity_path = self.root / "identity.json"
        controller.start(
            caller_pane="caller",
            worktree=self.repo,
            identity_path=identity_path,
            name="worker",
            kind="claude",
            title="Test worker",
        )
        controller.close(identity_path=identity_path)

        with self.assertRaisesRegex(self.module.HandoffError, "already exists"):
            controller.start(
                caller_pane="caller",
                worktree=self.repo,
                identity_path=identity_path,
                name="second",
                kind="claude",
                title="Second worker",
            )
        self.assertEqual(fake.split_count, 1)

    def test_answer_refuses_nonblocked_worker_without_input(self) -> None:
        controller, fake = self.controller()
        identity_path = self.root / "identity.json"
        controller.start(
            caller_pane="caller",
            worktree=self.repo,
            identity_path=identity_path,
            name="worker",
            kind="claude",
            title="Test worker",
        )

        with self.assertRaisesRegex(self.module.HandoffError, "not blocked"):
            controller.answer_blocked(
                identity_path=identity_path,
                text=None,
                keys=["enter"],
                timeout_ms=60_000,
            )
        self.assertEqual(fake.answer_count, 0)

    def test_cli_has_no_caller_pane_override(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("--caller-pane", source)

    def test_other_working_claude_does_not_block_turn(self) -> None:
        controller, fake = self.controller()
        identity_path = self.root / "identity.json"
        controller.start(
            caller_pane="caller",
            worktree=self.repo,
            identity_path=identity_path,
            name="worker",
            kind="claude",
            title="Test worker",
        )
        fake.agents["other"] = {
            "agent": "claude",
            "agent_session": {"value": "other-session"},
            "agent_status": "working",
            "cwd": str(self.repo),
            "name": "other",
            "pane_id": "other-pane",
            "state_change_seq": 1,
        }

        result = controller.prompt(
            identity_path=identity_path,
            text="Implement this independent task",
            timeout_ms=60_000,
        )
        self.assertEqual(result["agent_status"], "idle")
        self.assertEqual(fake.prompt_count, 1)

    def test_concurrent_turns_are_scoped_to_runtime_session(self) -> None:
        for same_session in (False, True):
            for second_action in ("prompt", "answer"):
                with self.subTest(same_session=same_session, second_action=second_action):
                    first, first_fake = self.controller()
                    second, second_fake = self.controller()
                    second_fake.runtime_session = (
                        first_fake.runtime_session if same_session else "independent-session"
                    )
                    paths = []
                    for index, controller in enumerate((first, second)):
                        path = self.root / f"{same_session}-{second_action}-{index}.json"
                        controller.start(
                            caller_pane="caller", worktree=self.repo, identity_path=path,
                            name="worker", kind="claude", title="Test worker",
                        )
                        paths.append(path)
                    if second_action == "answer":
                        second_fake.agents["worker"]["agent_status"] = "blocked"

                    def nested_turn(**kwargs):
                        if second_action == "answer":
                            return second.answer_blocked(
                                identity_path=paths[1], text="Approved answer", keys=None,
                                timeout_ms=60_000,
                            )
                        return second.prompt(
                            identity_path=paths[1], text="Second turn", timeout_ms=60_000,
                        )

                    first_fake.prompt = nested_turn
                    if same_session:
                        with self.assertRaisesRegex(self.module.HandoffError, "another Claude turn owns"):
                            first.prompt(identity_path=paths[0], text="First turn", timeout_ms=60_000)
                        self.assertEqual(second_fake.prompt_count + second_fake.answer_count, 0)
                    else:
                        result = first.prompt(
                            identity_path=paths[0], text="First turn", timeout_ms=60_000,
                        )
                        self.assertEqual(result["agent_status"], "idle")
                        self.assertGreater(second_fake.prompt_count + second_fake.answer_count, 0)

    def test_turn_lease_is_nonblocking_and_process_safe(self) -> None:
        lease = self.root / "claude-turn.lock"
        with self.module.TurnLease(lease):
            with self.assertRaisesRegex(self.module.HandoffError, "another Claude turn owns"):
                with self.module.TurnLease(lease):
                    pass

    def test_real_client_starts_claude_with_the_selected_model_and_default_effort(self) -> None:
        module = self.module
        sent = []

        class StartHerdr(module.RealHerdr):
            def _run(inner, args, *, timeout_seconds=60, allow_failure=False):
                sent.append(args)
                return subprocess.CompletedProcess(args, 0, "", "")

        herdr = StartHerdr(SCRIPT, self.repo)
        herdr.start_agent(
            name="worker",
            kind="claude",
            pane_id="worker-pane",
            title="Fable worker",
            claude_model="claude-fable-5-1",
        )

        self.assertEqual(sent[0][:3], ["agent", "start", "worker"])
        self.assertEqual(
            sent[0][sent[0].index("--model") + 1],
            "claude-fable-5-1",
        )
        self.assertEqual(sent[0][sent[0].index("--effort") + 1], "xhigh")
        self.assertNotIn("opus", sent[0])

        herdr.start_agent(
            name="critical-worker",
            kind="claude",
            pane_id="critical-pane",
            title="Critical worker",
            claude_effort="max",
        )
        self.assertEqual(sent[1][sent[1].index("--effort") + 1], "max")

    def test_startup_failure_includes_readable_output_before_cleanup(self) -> None:
        module = self.module

        class StartupHerdr(module.RealHerdr):
            def _run(inner, args, *, timeout_seconds=60, allow_failure=False):
                if args[:2] == ["agent", "start"]:
                    if not allow_failure:
                        raise module.HandoffError("agent_not_ready")
                    return subprocess.CompletedProcess(args, 1, "agent_not_ready", "")
                self.assertEqual(args[:2], ["agent", "read"])
                return subprocess.CompletedProcess(args, 0, "Workspace trust approval required", "")

        herdr = StartupHerdr(SCRIPT, self.repo)
        with self.assertRaisesRegex(module.HandoffError, "Workspace trust approval required"):
            herdr.start_agent(name="worker", kind="claude", pane_id="worker-pane", title="Test")

    def test_start_accepts_only_trust_for_its_authorized_worktree(self) -> None:
        module = self.module
        for requested in (str(self.repo), str(self.repo) + "-other"):
            with self.subTest(requested=requested):
                sent = []

                class TrustHerdr(module.RealHerdr):
                    def _run(inner, args, *, timeout_seconds=60, allow_failure=False):
                        self.assertEqual(args[:2], ["agent", "start"])
                        return subprocess.CompletedProcess(args, 1, "agent_not_ready", "")

                    def read_agent(inner, *, name, lines):
                        return (f"Accessing workspace:\n {requested}\n\n"
                                "Quick safety check: Is this a project you created or one you trust?\n"
                                "❯ No, exit\n  Yes, I trust this folder\n")

                    def get_agent(inner, name):
                        return {"result": {"agent": {
                            "pane_id": "worker-pane", "cwd": str(self.repo),
                            "agent_status": "blocked", "state_change_seq": 1,
                        }}}

                    def send_keys(inner, *, name, keys):
                        sent.append((name, keys))

                    def wait_agent(inner, *, name, after_seq, timeout_ms):
                        self.assertEqual(after_seq, 1)
                        return {"result": {"agent": {
                            "pane_id": "worker-pane", "cwd": str(self.repo),
                            "agent_status": "idle", "state_change_seq": 2,
                        }}}

                herdr = TrustHerdr(SCRIPT, self.repo)
                if requested == str(self.repo):
                    herdr.start_agent(name="worker", kind="claude", pane_id="worker-pane", title="Test")
                    self.assertEqual(sent, [("worker", ["down", "enter"])])
                else:
                    with self.assertRaises(module.HandoffError):
                        herdr.start_agent(name="worker", kind="claude", pane_id="worker-pane", title="Test")
                    self.assertEqual(sent, [])

    def test_compatibility_check_requires_both_protocols(self) -> None:
        self.assertTrue(
            self.module.status_is_compatible(
                "endpoint_compatible: yes\nprivate_protocol_compatible: yes\n"
            )
        )
        self.assertFalse(self.module.status_is_compatible("endpoint_compatible: yes\n"))

    def test_success_without_a_percentage_is_not_verified_capacity(self) -> None:
        controller, fake = self.controller()
        identity_path = self.root / "identity.json"
        controller.capacity_probe = lambda required: self.module.CapacityProbe(
            ok=True,
            returncode=0,
            message="capacity available",
        )

        with self.assertRaisesRegex(self.module.HandoffError, "capacity available"):
            controller.start(
                caller_pane="caller",
                worktree=self.repo,
                identity_path=identity_path,
                name="worker",
                kind="claude",
                title="Test worker",
            )
        self.assertEqual(fake.panes, {"caller"})
        self.assertFalse(identity_path.exists())

    def test_identity_symlink_is_refused(self) -> None:
        target = self.root / "target.json"
        target.write_text("{}", encoding="utf-8")
        identity = self.root / "identity.json"
        identity.symlink_to(target)

        with self.assertRaisesRegex(self.module.HandoffError, "must not be a symlink"):
            self.module._load_identity(identity)

    def test_resource_existence_distinguishes_not_found_from_server_failure(self) -> None:
        not_found = subprocess.CompletedProcess(
            [],
            1,
            stdout='',
            stderr='{"error":{"code":"agent_not_found","message":"missing"}}',
        )
        self.assertFalse(
            self.module.resource_exists_from_result(
                not_found,
                not_found_code="agent_not_found",
                resource_key="agent",
            )
        )
        unavailable = subprocess.CompletedProcess(
            [],
            1,
            stdout='',
            stderr='{"error":{"code":"server_unavailable","message":"down"}}',
        )
        with self.assertRaisesRegex(self.module.HandoffError, "server_unavailable"):
            self.module.resource_exists_from_result(
                unavailable,
                not_found_code="agent_not_found",
                resource_key="agent",
            )
        malformed = subprocess.CompletedProcess([], 1, stdout="", stderr="not json")
        with self.assertRaisesRegex(self.module.HandoffError, "non-JSON"):
            self.module.resource_exists_from_result(
                malformed,
                not_found_code="pane_not_found",
                resource_key="pane",
            )

    def test_recover_start_completes_a_matching_live_worker(self) -> None:
        controller, fake = self.controller()
        identity_path = self.root / "identity.json"
        fake.panes.add("worker-pane")
        fake.start_agent(
            name="worker",
            kind="claude",
            pane_id="worker-pane",
            title="Test worker",
        )
        identity_path.write_text(
            json.dumps(
                self.module.make_start_record(
                    token="recovery-token",
                    name="worker",
                    kind="claude",
                    caller_pane="caller",
                    worktree_identity=self.module.git_worktree_identity(self.repo),
                    worker_pane_id="worker-pane",
                )
            ),
            encoding="utf-8",
        )

        recovered = controller.recover_start(identity_path=identity_path)
        self.assertFalse(recovered["closed"])
        self.assertEqual(recovered["worker_runtime_session_id"], "runtime-session")

    def test_recover_start_closes_an_orphaned_pane_and_terminalizes(self) -> None:
        controller, fake = self.controller()
        identity_path = self.root / "identity.json"
        fake.panes.add("worker-pane")
        identity_path.write_text(
            json.dumps(
                self.module.make_start_record(
                    token="recovery-token",
                    name="worker",
                    kind="claude",
                    caller_pane="caller",
                    worktree_identity=self.module.git_worktree_identity(self.repo),
                    worker_pane_id="worker-pane",
                )
            ),
            encoding="utf-8",
        )

        recovered = controller.recover_start(identity_path=identity_path)
        self.assertTrue(recovered["closed"])
        self.assertFalse(fake.pane_exists("worker-pane"))

    def test_unverified_start_cleanup_preserves_recoverable_identity(self) -> None:
        controller, fake = self.controller()
        identity_path = self.root / "identity.json"

        def fail_start(**kwargs) -> None:
            raise RuntimeError("startup failed")

        fake.start_agent = fail_start
        fake.agent_exists = lambda name: (_ for _ in ()).throw(
            RuntimeError("server unavailable")
        )
        with self.assertRaisesRegex(RuntimeError, "startup failed"):
            controller.start(
                caller_pane="caller",
                worktree=self.repo,
                identity_path=identity_path,
                name="worker",
                kind="claude",
                title="Test worker",
            )

        failed = json.loads(identity_path.read_text(encoding="utf-8"))
        self.assertTrue(failed["cleanup_required"])
        self.assertEqual(failed["worker_pane_id"], "worker-pane")
        self.assertEqual(
            failed["worker_worktree_identity"],
            self.module.git_worktree_identity(self.repo),
        )

        fake.agent_exists = lambda name: name in fake.agents
        fake.pane_exists = lambda pane_id: pane_id in fake.panes
        recovered = controller.recover_start(identity_path=identity_path)
        self.assertTrue(recovered["closed"])

    def test_interruption_after_split_is_recovered_without_pane_leak(self) -> None:
        controller, fake = self.controller()
        identity_path = self.root / "identity.json"
        fake.interrupt_after_split = True

        with self.assertRaisesRegex(RuntimeError, "interrupted after split"):
            controller.start(
                caller_pane="caller",
                worktree=self.repo,
                identity_path=identity_path,
                name="worker",
                kind="claude",
                title="Test worker",
            )
        failed = json.loads(identity_path.read_text(encoding="utf-8"))
        self.assertTrue(failed["split_started"])
        self.assertIsNone(failed["worker_pane_id"])
        self.assertIn("worker-pane", fake.panes)

        fake.interrupt_after_split = False
        recovered = controller.recover_start(identity_path=identity_path)
        self.assertTrue(recovered["closed"])
        self.assertNotIn("worker-pane", fake.panes)

    def test_split_recovery_refuses_ambiguous_new_panes(self) -> None:
        controller, fake = self.controller()
        identity_path = self.root / "identity.json"
        fake.interrupt_after_split = True
        with self.assertRaisesRegex(RuntimeError, "interrupted after split"):
            controller.start(
                caller_pane="caller",
                worktree=self.repo,
                identity_path=identity_path,
                name="worker",
                kind="claude",
                title="Test worker",
            )
        fake.panes.add("other-new-pane")
        with self.assertRaisesRegex(self.module.HandoffError, "multiple possible panes"):
            controller.recover_start(identity_path=identity_path)
        self.assertIn("worker-pane", fake.panes)
        self.assertIn("other-new-pane", fake.panes)

    def test_close_transport_failure_is_recoverable_on_retry(self) -> None:
        controller, fake = self.controller()
        identity_path = self.root / "identity.json"
        controller.start(
            caller_pane="caller",
            worktree=self.repo,
            identity_path=identity_path,
            name="worker",
            kind="claude",
            title="Test worker",
        )
        original_agent_exists = fake.agent_exists
        calls = 0

        def fail_first_agent_readback(name: str) -> bool:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("server unavailable")
            return original_agent_exists(name)

        fake.agent_exists = fail_first_agent_readback
        with self.assertRaisesRegex(RuntimeError, "server unavailable"):
            controller.close(identity_path=identity_path)
        closing = json.loads(identity_path.read_text(encoding="utf-8"))
        self.assertTrue(closing["closing"])
        self.assertTrue(closing["cleanup_required"])

        fake.agent_exists = original_agent_exists
        closed = controller.close(identity_path=identity_path)
        self.assertTrue(closed["closed"])

    def handoff(self, controller, identity_path: Path, **overrides):
        prompt_path = self.root / "handoff-prompt.md"
        prompt_path.write_text("Read the vault note and implement it.\n", encoding="utf-8")
        arguments = dict(
            caller_pane="caller",
            worktree=self.repo,
            identity_path=identity_path,
            prompt_path=prompt_path,
            name="worker",
            kind="claude",
            title="Handed-off worker",
            text=prompt_path.read_text(encoding="utf-8"),
        )
        arguments.update(overrides)
        return controller.handoff(**arguments), prompt_path

    def handoff_status(self, controller, identity_path: Path, **overrides):
        prompt_path = self.root / "handoff-prompt.md"
        prompt_path.write_text("Read the vault note and implement it.\n", encoding="utf-8")
        arguments = dict(
            caller_pane="caller",
            worktree=self.repo,
            identity_path=identity_path,
            prompt_path=prompt_path,
            name="worker",
            kind="claude",
            title="Status-only worker",
            text=prompt_path.read_text(encoding="utf-8"),
            timeout_ms=60_000,
        )
        arguments.update(overrides)
        return controller.handoff_status(**arguments), prompt_path

    # --- status-only handoff -------------------------------------------------

    def test_engagement_modes_are_distinct_and_legacy_records_read_as_fire_and_forget(self) -> None:
        mode = self.module.engagement_mode
        self.assertEqual(mode({"supervised": False}), "fire-and-forget")  # legacy record
        self.assertEqual(mode({}), "supervised")  # supervised records never carried the flag
        self.assertEqual(mode({"engagement_mode": "status-only", "supervised": False}), "status-only")
        controller, _ = self.controller()
        self.handoff_status(controller, self.root / "status.json")
        self.handoff(controller, self.root / "fire.json", name="fire")
        status_record = json.loads((self.root / "status.json").read_text(encoding="utf-8"))
        fire_record = json.loads((self.root / "fire.json").read_text(encoding="utf-8"))
        self.assertEqual(status_record["engagement_mode"], "status-only")
        self.assertEqual(fire_record["engagement_mode"], "fire-and-forget")
        # The compatibility boolean keeps its documented meaning on both.
        self.assertIs(status_record["supervised"], False)
        self.assertIs(fire_record["supervised"], False)

    def test_status_only_submits_exactly_one_prompt_through_the_wait_path(self) -> None:
        controller, fake = self.controller()
        identity_path = self.root / "identity.json"

        result, prompt_path = self.handoff_status(controller, identity_path)

        self.assertTrue(result["ok"])
        self.assertEqual(result["engagement_mode"], "status-only")
        self.assertEqual(result["terminal_status"], "idle")
        self.assertTrue(result["delivered"])
        self.assertEqual(fake.prompt_count, 1)  # the wait-capable send, once
        self.assertEqual(fake.deliver_count, 0)  # never the one-way send
        self.assertEqual(result["identity_file"], str(identity_path.resolve()))
        self.assertEqual(result["prompt_file"], str(prompt_path.resolve()))
        self.assertEqual(result["worker_pane_id"], "worker-pane")
        self.assertEqual(result["worker_branch"], "main")
        # The worker and pane are left intact for a future independent acceptance.
        self.assertIn("worker-pane", fake.panes)
        self.assertIn("worker", fake.agents)
        record = json.loads(identity_path.read_text(encoding="utf-8"))
        self.assertEqual(record["status_phase"], "settled")
        self.assertEqual(record["terminal_status"], "idle")

    def test_status_only_result_carries_no_worker_output(self) -> None:
        controller, fake = self.controller()
        result, _ = self.handoff_status(controller, self.root / "identity.json")
        self.assertEqual(fake.read_count, 0)
        self.assertNotIn("output", result)
        self.assertNotIn("recent output", json.dumps(result))

    def test_status_only_holds_the_turn_lease_and_capacity_gate(self) -> None:
        # Exhausted capacity is refused by the shared start gate: no pane, no
        # identity, no prompt.
        controller, fake = self.controller(capacity_code=75)
        with self.assertRaisesRegex(self.module.HandoffError, "exhausted"):
            self.handoff_status(controller, self.root / "exhausted.json")
        self.assertEqual((fake.split_count, fake.prompt_count), (0, 0))
        self.assertFalse((self.root / "exhausted.json").exists())

        # Capacity is re-checked right before the send (the same gate `prompt`
        # uses). When it fails there, the started worker is kept and the record
        # says honestly that the prompt was never sent.
        controller, fake = self.controller()
        identity_path = self.root / "identity.json"
        probes = iter([True, False])
        real_require = controller._require_capacity

        def flaky_capacity():
            if next(probes):
                return real_require()
            raise self.module.HandoffError("Claude capacity exhausted before the send")

        controller._require_capacity = flaky_capacity
        with self.assertRaisesRegex(self.module.HandoffError, "exhausted"):
            self.handoff_status(controller, identity_path)
        self.assertEqual(fake.prompt_count, 0)
        self.assertIn("worker-pane", fake.panes)
        record = json.loads(identity_path.read_text(encoding="utf-8"))
        self.assertEqual(record["engagement_mode"], "status-only")
        self.assertEqual(record["status_phase"], "prompt-not-sent")

        # A turn already owning this runtime session's lease blocks the send.
        controller, fake = self.controller()
        identity_path = self.root / "leased.json"
        lease = controller._session_lease({"worker_runtime_session_id": fake.runtime_session})
        with lease:
            with self.assertRaisesRegex(self.module.HandoffError, "lease"):
                self.handoff_status(controller, identity_path)
        self.assertEqual(fake.prompt_count, 0)
        # And it releases its own lease once settled.
        controller, fake = self.controller()
        self.handoff_status(controller, self.root / "released.json")
        with controller._session_lease({"worker_runtime_session_id": fake.runtime_session}):
            pass

    def test_status_only_terminal_states_are_distinct(self) -> None:
        cases = {
            "done": dict(prompt_status_after="done"),
            "blocked": dict(prompt_status_after="blocked"),
            "failed": dict(prompt_status_after="error"),
            "timed-out": dict(prompt_error=self.module.HandoffError(
                'Herdr agent prompt failed: {"error":{"code":"timeout"}}')),
            "disappeared": dict(vanish_on_prompt=True),
        }
        for expected, setup in cases.items():
            with self.subTest(terminal=expected):
                controller, fake = self.controller()
                for key, value in setup.items():
                    setattr(fake, key, value)
                result, _ = self.handoff_status(controller, self.root / f"{expected}.json")
                self.assertEqual(result["terminal_status"], expected)
                self.assertEqual(fake.prompt_count, 1)
                self.assertNotIn("recent output", json.dumps(result))

        # Identity mismatch: the recorded pane changes underneath the turn.
        controller, fake = self.controller()
        original = fake.prompt

        def moved(**kwargs):
            payload = original(**kwargs)
            fake.agents["worker"]["pane_id"] = "someone-else"
            return payload

        fake.prompt = moved
        result, _ = self.handoff_status(controller, self.root / "moved.json")
        self.assertEqual(result["terminal_status"], "identity-mismatch")

    def test_status_only_refuses_every_boundary_crossing_operation(self) -> None:
        controller, fake = self.controller()
        identity_path = self.root / "identity.json"
        self.handoff_status(controller, identity_path)

        with self.assertRaisesRegex(self.module.HandoffError, "status-only"):
            controller.read(identity_path=identity_path, lines=10)
        with self.assertRaisesRegex(self.module.HandoffError, "status-only"):
            controller.inspect(identity_path=identity_path)
        with self.assertRaisesRegex(self.module.HandoffError, "status-only"):
            controller.prompt(identity_path=identity_path, text="fix it", timeout_ms=60_000)
        with self.assertRaisesRegex(self.module.HandoffError, "status-only"):
            controller.answer_blocked(identity_path=identity_path, text="yes", keys=None, timeout_ms=60_000)
        with self.assertRaisesRegex(self.module.HandoffError, "status-only"):
            controller.close(identity_path=identity_path)
        self.assertEqual(fake.read_count, 0)
        self.assertEqual(fake.prompt_count, 1)  # only the original submission
        self.assertEqual(fake.answer_count, 0)
        self.assertIn("worker-pane", fake.panes)

    def test_status_wait_recovers_a_lost_acknowledgement_without_resending(self) -> None:
        controller, fake = self.controller()
        identity_path = self.root / "identity.json"
        # Simulate the caller dying mid-wait: the record says the turn is in flight.
        fake.prompt_error = RuntimeError("caller lost the connection")
        result, _ = self.handoff_status(controller, identity_path)
        self.assertEqual(result["terminal_status"], "failed")
        record = json.loads(identity_path.read_text(encoding="utf-8"))
        record["status_phase"] = "turn-in-flight"
        identity_path.write_text(json.dumps(record), encoding="utf-8")
        fake.prompt_error = None

        recovered = controller.status_wait(identity_path=identity_path, timeout_ms=60_000)

        self.assertEqual(recovered["terminal_status"], "idle")
        self.assertEqual(fake.prompt_count, 1)  # no second submission
        self.assertEqual(fake.deliver_count, 0)
        self.assertEqual(fake.wait_after_seq, record["prompt_state_change_seq"])
        self.assertNotIn("recent output", json.dumps(recovered))

        # Interrupted before the send: nothing to wait for, and still no resend.
        record["status_phase"] = "prompt-not-sent"
        identity_path.write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaisesRegex(self.module.HandoffError, "never submitted"):
            controller.status_wait(identity_path=identity_path, timeout_ms=60_000)
        self.assertEqual(fake.prompt_count, 1)

        # Not applicable to other modes.
        self.handoff(controller, self.root / "fire.json", name="fire")
        with self.assertRaisesRegex(self.module.HandoffError, "only to a status-only"):
            controller.status_wait(identity_path=self.root / "fire.json", timeout_ms=60_000)

    def test_fire_and_forget_creates_no_watcher_and_keeps_its_refusals(self) -> None:
        controller, fake = self.controller()
        result, _ = self.handoff(controller, self.root / "identity.json")
        self.assertEqual(result["engagement_mode"], "fire-and-forget")
        self.assertEqual(fake.prompt_count, 0)  # never the waiting path
        self.assertNotIn("terminal_status", result)
        record = json.loads((self.root / "identity.json").read_text(encoding="utf-8"))
        self.assertNotIn("status_phase", record)

    def test_cli_exposes_status_only_handoff_and_recovery_with_exact_model(self) -> None:
        parser = self.module.build_parser()
        arguments = parser.parse_args(
            [
                "handoff-status",
                "--worktree", str(self.repo),
                "--identity-file", str(self.root / "identity.json"),
                "--prompt-file", str(self.root / "handoff-prompt.md"),
                "--name", "worker",
                "--claude-model", "claude-fable-5-1",
            ]
        )
        self.assertEqual(arguments.command, "handoff-status")
        self.assertEqual(arguments.claude_model, "claude-fable-5-1")
        self.assertEqual(arguments.claude_effort, "xhigh")
        self.assertEqual(arguments.timeout_ms, 7_200_000)
        recovery = parser.parse_args(
            ["status-wait", "--identity-file", str(self.root / "identity.json")]
        )
        self.assertEqual(recovery.command, "status-wait")
        with self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "handoff-status",
                    "--worktree", str(self.repo),
                    "--identity-file", str(self.root / "identity.json"),
                    "--name", "worker",
                ]
            )

    def test_handoff_delivers_once_without_waiting_on_the_turn(self) -> None:
        controller, fake = self.controller()
        identity_path = self.root / "identity.json"

        result, prompt_path = self.handoff(controller, identity_path)

        self.assertTrue(result["ok"])
        self.assertTrue(result["delivered"])
        self.assertIs(result["supervised"], False)
        self.assertEqual(result["worker_pane_id"], "worker-pane")
        self.assertEqual(result["identity_file"], str(identity_path.resolve()))
        self.assertEqual(result["prompt_file"], str(prompt_path.resolve()))
        # The one-way send is used exactly once, and the waiting send never is.
        self.assertEqual(fake.deliver_count, 1)
        self.assertEqual(fake.prompt_count, 0)

    def test_handoff_holds_no_turn_lease_after_returning(self) -> None:
        controller, _ = self.controller()
        identity_path = self.root / "identity.json"

        self.handoff(controller, identity_path)

        record = json.loads(identity_path.read_text(encoding="utf-8"))
        lease = controller._session_lease(record)
        self.assertFalse(lease.path.exists(), "handoff created a turn lease file")
        with lease:  # Would raise if the handoff still owned the session.
            pass

    def test_real_client_delivery_omits_the_wait_flag(self) -> None:
        sent: list[list[str]] = []
        client = self.module.RealHerdr.__new__(self.module.RealHerdr)
        client._json = lambda args, **kwargs: sent.append(args) or {}

        client.deliver(name="worker", text="go")

        self.assertEqual(sent, [["agent", "prompt", "worker", "go"]])
        self.assertNotIn("--wait", sent[0])

    def test_failed_delivery_keeps_the_pane_and_reports_both_paths(self) -> None:
        controller, fake = self.controller()
        identity_path = self.root / "identity.json"
        fake.deliver_error = RuntimeError("transport refused the send")

        with self.assertRaises(self.module.HandoffDeliveryError) as raised:
            self.handoff(controller, identity_path)

        details = raised.exception.details
        self.assertEqual(details["identity_file"], str(identity_path.resolve()))
        self.assertEqual(
            details["prompt_file"], str((self.root / "handoff-prompt.md").resolve())
        )
        self.assertFalse(details["delivered"])
        # The started, validated worker survives the cheapest step failing.
        self.assertIn("worker-pane", fake.panes)
        self.assertIn("worker", fake.agents)
        record = json.loads(identity_path.read_text(encoding="utf-8"))
        self.assertIs(record["supervised"], False)
        self.assertIsNot(record.get("closed"), True)

    def test_handoff_record_refuses_supervision_but_allows_inspect_and_close(self) -> None:
        controller, fake = self.controller()
        identity_path = self.root / "identity.json"
        self.handoff(controller, identity_path)

        self.assertIs(
            json.loads(identity_path.read_text(encoding="utf-8"))["supervised"], False
        )

        with self.assertRaisesRegex(self.module.HandoffError, "unsupervised"):
            controller.prompt(
                identity_path=identity_path, text="follow up", timeout_ms=60_000
            )
        with self.assertRaisesRegex(self.module.HandoffError, "unsupervised"):
            controller.answer_blocked(
                identity_path=identity_path,
                text="yes",
                keys=None,
                timeout_ms=60_000,
            )
        # Refused before any input reached the worker.
        self.assertEqual(fake.prompt_count, 0)
        self.assertEqual(fake.answer_count, 0)

        inspected = controller.inspect(identity_path=identity_path)
        self.assertIs(inspected["supervised"], False)
        self.assertEqual(inspected["worker_agent_name"], "worker")

        closed = controller.close(identity_path=identity_path)
        self.assertTrue(closed["closed"])
        self.assertNotIn("worker-pane", fake.panes)

    def test_handoff_refuses_empty_prompt_before_creating_a_pane(self) -> None:
        controller, fake = self.controller()
        identity_path = self.root / "identity.json"

        with self.assertRaisesRegex(self.module.HandoffError, "must not be empty"):
            self.handoff(controller, identity_path, text="   \n")

        self.assertEqual(fake.split_count, 0)
        self.assertEqual(fake.deliver_count, 0)
        self.assertFalse(identity_path.exists())

    def test_cli_exposes_handoff_with_a_required_prompt_file(self) -> None:
        parser = self.module.build_parser()
        arguments = parser.parse_args(
            [
                "handoff",
                "--worktree", str(self.repo),
                "--identity-file", str(self.root / "identity.json"),
                "--prompt-file", str(self.root / "handoff-prompt.md"),
                "--name", "worker",
            ]
        )
        self.assertEqual(arguments.command, "handoff")
        self.assertEqual(arguments.kind, "claude")
        self.assertEqual(arguments.claude_model, "opus")
        self.assertEqual(arguments.claude_effort, "xhigh")
        selected = parser.parse_args(
            [
                "handoff",
                "--worktree", str(self.repo),
                "--identity-file", str(self.root / "fable-identity.json"),
                "--prompt-file", str(self.root / "handoff-prompt.md"),
                "--name", "fable-worker",
                "--claude-model", "claude-fable-5-1",
                "--claude-effort", "max",
            ]
        )
        self.assertEqual(selected.claude_model, "claude-fable-5-1")
        self.assertEqual(selected.claude_effort, "max")
        with self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "handoff",
                    "--worktree", str(self.repo),
                    "--identity-file", str(self.root / "identity.json"),
                    "--name", "worker",
                ]
            )


if __name__ == "__main__":
    unittest.main()
