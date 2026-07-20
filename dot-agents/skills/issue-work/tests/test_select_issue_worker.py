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
    def test_auto_routes_sgg_to_claude(self) -> None:
        result = select_issue_worker.select_worker(
            ticket_repo="HHS/simpler-grants-protocol",
            remote_url="git@github.com:HHS/simpler-grants-protocol.git",
            override="auto",
        )

        self.assertEqual(result["selected_worker"], "claude")
        self.assertEqual(
            result["implementation_loop"],
            "codex-claude-implementation-loop",
        )

    def test_sgg_suffix_on_untrusted_host_does_not_authorize_claude(self) -> None:
        result = select_issue_worker.select_worker(
            ticket_repo="HHS/simpler-grants-gov",
            remote_url="git@evil.example:HHS/simpler-grants-gov.git",
            override="auto",
        )

        self.assertEqual(result["selected_worker"], "qwen")
        self.assertFalse(result["sgg_allowlisted"])
        self.assertEqual(result["remote_host"], "evil.example")

    def test_auto_routes_non_sgg_to_local_qwen(self) -> None:
        result = select_issue_worker.select_worker(
            ticket_repo="bryan/cairn-os",
            remote_url="ssh://forgejo@git.snowboardtechie.com/bryan/cairn-os.git",
            override="auto",
        )

        self.assertEqual(result["selected_worker"], "qwen")
        self.assertEqual(
            result["implementation_loop"],
            "codex-qwen-implementation-loop",
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
            ticket_repo="bryan/dotfiles",
            remote_url="git@git.snowboardtechie.com:bryan/dotfiles.git",
            override="gpt",
        )

        self.assertEqual(result["selected_worker"], "gpt")
        self.assertIsNone(result["implementation_loop"])

    def test_explicit_qwen_can_override_sgg_default(self) -> None:
        result = select_issue_worker.select_worker(
            ticket_repo="HHS/simpler-grants-gov",
            remote_url="https://github.com/HHS/simpler-grants-gov.git",
            override="qwen",
        )

        self.assertEqual(result["selected_worker"], "qwen")

    def test_claude_override_is_rejected_outside_sgg(self) -> None:
        with self.assertRaisesRegex(
            select_issue_worker.RoutingError,
            "Claude is restricted",
        ):
            select_issue_worker.select_worker(
                ticket_repo="bryan/cairn-os",
                remote_url="git@git.snowboardtechie.com:bryan/cairn-os.git",
                override="claude",
            )

    def test_ticket_and_remote_must_match(self) -> None:
        with self.assertRaisesRegex(
            select_issue_worker.RoutingError,
            "does not match",
        ):
            select_issue_worker.select_worker(
                ticket_repo="HHS/simpler-grants-gov",
                remote_url="git@github.com:someone/simpler-grants-gov.git",
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
