from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "select_issue_worker.py"
SPEC = importlib.util.spec_from_file_location("select_issue_worker", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
select_issue_worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(select_issue_worker)


class SelectIssueWorkerTests(unittest.TestCase):
    def test_top_level_routing_error_has_two_blank_lines(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("from urllib.parse import urlparse\n\n\nclass RoutingError", source)

    def test_auto_routes_sgg_to_claude(self) -> None:
        result = select_issue_worker.select_worker(
            ticket_repo="HHS/simpler-grants-protocol",
            remote_url="git@github.com:HHS/simpler-grants-protocol.git",
            override="auto",
        )

        self.assertEqual(result["selected_worker"], "claude")
        self.assertEqual(
            result["implementation_loop"],
            "coding-agent-handoff-supervision",
        )

    def test_cross_repo_routing_uses_implementation_identity(self) -> None:
        result = select_issue_worker.select_worker(
            ticket_repo="HHS/private-planning-workspace",
            implementation_repo="HHS/simpler-grants-protocol",
            implementation_host="github.com",
            remote_url="git@github.com:HHS/simpler-grants-protocol.git",
            override="auto",
        )

        self.assertEqual(result["selected_worker"], "claude")
        self.assertNotIn("sgg_allowlisted", result)

    def test_auto_route_has_no_obsolete_sgg_policy_fields(self) -> None:
        result = select_issue_worker.select_worker(
            ticket_repo="HHS/simpler-grants-gov",
            remote_url="git@evil.example:HHS/simpler-grants-gov.git",
            override="auto",
        )

        self.assertEqual(result["selected_worker"], "claude")
        self.assertNotIn("sgg_allowlisted", result)
        self.assertEqual(result["remote_host"], "evil.example")

    def test_auto_routes_forgejo_repository_to_visible_claude_handoff(self) -> None:
        result = select_issue_worker.select_worker(
            ticket_repo="bryan/cairn-os",
            remote_url="ssh://forgejo@git.snowboardtechie.com/bryan/cairn-os.git",
            override="auto",
        )

        self.assertEqual(result["selected_worker"], "claude")
        self.assertEqual(
            result["implementation_loop"],
            "coding-agent-handoff-supervision",
        )

    def test_nested_github_path_cannot_spoof_allowlisted_repository(self):
        with self.assertRaises(select_issue_worker.RoutingError):
            select_issue_worker.select_worker(
                ticket_repo="HHS/simpler-grants-protocol",
                remote_url="https://github.com/attacker/HHS/simpler-grants-protocol.git",
                override="auto",
            )

    def test_explicit_gpt_uses_host_native_path(self) -> None:
        result = select_issue_worker.select_worker(
            ticket_repo="example/public-project",
            remote_url="git@forge.example:example/public-project.git",
            override="gpt",
        )

        self.assertEqual(result["selected_worker"], "gpt")
        self.assertIsNone(result["implementation_loop"])

    def test_explicit_qwen_overrides_visible_claude_default(self) -> None:
        result = select_issue_worker.select_worker(
            ticket_repo="HHS/simpler-grants-gov",
            remote_url="https://github.com/HHS/simpler-grants-gov.git",
            override="qwen",
        )

        self.assertEqual(result["selected_worker"], "qwen")

    def test_explicit_claude_uses_visible_handoff(self) -> None:
        result = select_issue_worker.select_worker(
            ticket_repo="bryan/cairn-os",
            remote_url="git@git.snowboardtechie.com:bryan/cairn-os.git",
            override="claude",
        )

        self.assertEqual(result["selected_worker"], "claude")
        self.assertEqual(
            result["implementation_loop"],
            "coding-agent-handoff-supervision",
        )

    def test_explicit_hermes_uses_visible_handoff(self) -> None:
        result = select_issue_worker.select_worker(
            ticket_repo="bryan/cairn-os",
            remote_url="git@git.snowboardtechie.com:bryan/cairn-os.git",
            override="hermes",
        )

        self.assertEqual(result["selected_worker"], "hermes")
        self.assertEqual(
            result["implementation_loop"],
            "coding-agent-handoff-supervision",
        )

    def test_ticket_and_remote_must_match_without_explicit_implementation_repo(self) -> None:
        with self.assertRaisesRegex(
            select_issue_worker.RoutingError,
            "does not match",
        ):
            select_issue_worker.select_worker(
                ticket_repo="HHS/simpler-grants-gov",
                remote_url="git@github.com:someone/simpler-grants-gov.git",
                override="auto",
            )

    def test_explicit_implementation_repo_allows_cross_repo_ticket(self) -> None:
        result = select_issue_worker.select_worker(
            ticket_repo="example/private-workspace",
            implementation_repo="example/public-project",
            implementation_host="forge.example",
            remote_url="ssh://git@forge.example/example/public-project.git",
            override="auto",
        )

        self.assertEqual(result["ticket_repo"], "example/private-workspace")
        self.assertEqual(result["implementation_repo"], "example/public-project")
        self.assertEqual(result["implementation_host"], "forge.example")
        self.assertEqual(result["remote_repo"], "example/public-project")
        self.assertEqual(result["selected_worker"], "claude")

    def test_explicit_implementation_repo_must_match_remote(self) -> None:
        with self.assertRaisesRegex(
            select_issue_worker.RoutingError,
            "implementation repository .* does not match",
        ):
            select_issue_worker.select_worker(
                ticket_repo="example/private-workspace",
                implementation_repo="example/other-project",
                implementation_host="forge.example",
                remote_url="ssh://git@forge.example/example/public-project.git",
                override="auto",
            )

    def test_cross_repo_requires_explicit_implementation_host(self) -> None:
        with self.assertRaisesRegex(select_issue_worker.RoutingError, "requires --implementation-host"):
            select_issue_worker.select_worker(
                ticket_repo="example/private-workspace",
                implementation_repo="example/public-project",
                remote_url="ssh://git@forge.example/example/public-project.git",
                override="auto",
            )

    def test_explicit_implementation_host_must_match_remote(self) -> None:
        with self.assertRaisesRegex(select_issue_worker.RoutingError, "forge .* does not match"):
            select_issue_worker.select_worker(
                ticket_repo="example/private-workspace",
                implementation_repo="example/public-project",
                implementation_host="github.com",
                remote_url="ssh://git@forge.example/example/public-project.git",
                override="auto",
            )

    def test_same_repo_name_on_different_forge_is_cross_repository(self) -> None:
        result = select_issue_worker.select_worker(
            ticket_repo="example/project",
            ticket_host="private.example",
            implementation_repo="example/project",
            implementation_host="public.example",
            remote_url="git@public.example:example/project.git",
            override="auto",
        )

        self.assertTrue(result["cross_repository"])
        self.assertEqual(result["ticket_host"], "private.example")

    def test_cross_forge_same_repo_requires_explicit_implementation_host(self) -> None:
        with self.assertRaisesRegex(select_issue_worker.RoutingError, "requires --implementation-host"):
            select_issue_worker.select_worker(
                ticket_repo="example/project",
                ticket_host="private.example",
                implementation_repo="example/project",
                remote_url="git@public.example:example/project.git",
                override="auto",
            )

    def test_normalizes_supported_remote_shapes(self) -> None:
        urls = [
            "git@github.com:HHS/simpler-grants-gov.git",
            "ssh://git@github.com/HHS/simpler-grants-gov.git",
            "https://github.com/HHS/simpler-grants-gov.git",
        ]

        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(
                    select_issue_worker.repo_from_remote(url),
                    "HHS/simpler-grants-gov",
                )

    def test_repository_identity_uses_worktree_common_dir_and_origin(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            trunk = Path(temp_dir) / "repo"
            worktree = Path(temp_dir) / "worktree"
            trunk.mkdir()
            subprocess.run(["git", "init", "-q", "-b", "main"], cwd=trunk, check=True)
            subprocess.run(
                ["git", "config", "user.email", "worker-test@example.com"],
                cwd=trunk,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Worker Test"],
                cwd=trunk,
                check=True,
            )
            (trunk / "README.md").write_text("test\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=trunk, check=True)
            subprocess.run(["git", "commit", "-qm", "Add test"], cwd=trunk, check=True)
            subprocess.run(
                [
                    "git",
                    "remote",
                    "add",
                    "origin",
                    "git@github.com:example/project.git",
                ],
                cwd=trunk,
                check=True,
            )
            subprocess.run(
                ["git", "worktree", "add", "-q", "-b", "feature", str(worktree)],
                cwd=trunk,
                check=True,
            )

            common_dir, remote = select_issue_worker.repository_identity(worktree)

            self.assertEqual(common_dir, (trunk / ".git").resolve())
            self.assertEqual(remote, "git@github.com:example/project.git")


if __name__ == "__main__":
    unittest.main()
