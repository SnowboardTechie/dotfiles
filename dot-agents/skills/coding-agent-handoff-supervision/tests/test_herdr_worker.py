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
        self.split_count = 0
        self.answer_count = 0
        self.wait_after_seq: int | None = None
        self.interrupt_after_split = False
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

    def start_agent(self, *, name: str, kind: str, pane_id: str, title: str) -> None:
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
        self.agents[name]["agent_status"] = "idle"
        return self.get_agent(name)

    def read_agent(self, *, name: str, lines: int) -> str:
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


if __name__ == "__main__":
    unittest.main()
