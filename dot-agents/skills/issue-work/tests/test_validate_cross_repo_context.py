from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_cross_repo_context.py"
SPEC = importlib.util.spec_from_file_location("validate_cross_repo_context", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class CrossRepoContextTests(unittest.TestCase):
    def make_repo(self, root: Path, name: str, remote: str) -> Path:
        repo = root / name
        repo.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
        (repo / "README.md").write_text("test\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "Initial"], cwd=repo, check=True)
        subprocess.run(["git", "remote", "add", "origin", remote], cwd=repo, check=True)
        return repo

    def write_progress(
        self,
        state_dir: Path,
        *,
        ticket_url: str,
        worktree: Path,
        ticket_repo: str,
        implementation_host: str,
        implementation_repo: str,
        implementation_trunk: Path,
        branch: str = "main",
    ) -> None:
        state_dir.mkdir(parents=True)
        (state_dir / "progress.md").write_text(
            "\n".join(
                [
                    "---",
                    f"ticket: {ticket_url}",
                    f"worktree: {worktree}",
                    f"branch: {branch}",
                    f"ticket_repository: {ticket_repo}",
                    f"implementation_forge: {implementation_host}",
                    f"implementation_repository: {implementation_repo}",
                    f"implementation_trunk: {implementation_trunk}",
                    "---",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    def test_cross_repository_context_is_admitted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ticket = self.make_repo(root, "private-workspace", "git@private.example:example/workspace.git")
            implementation_trunk = self.make_repo(
                root, "public-project", "git@public.example:example/project.git"
            )
            implementation = root / "public-project-worktree"
            subprocess.run(
                ["git", "worktree", "add", "-q", "-b", "feature", str(implementation)],
                cwd=implementation_trunk,
                check=True,
            )
            state = ticket / ".hermes" / "issue-work" / "example-workspace-7"
            url = "https://private.example/example/workspace/issues/7"
            self.write_progress(
                state,
                ticket_url=url,
                worktree=implementation,
                ticket_repo="example/workspace",
                implementation_host="public.example",
                implementation_repo="example/project",
                implementation_trunk=implementation_trunk,
                branch="feature",
            )

            result = validator.validate_context(
                ticket_trunk=ticket,
                state_dir=state,
                worktree=implementation,
                ticket_url=url,
                ticket_host="private.example",
                ticket_repo="example/workspace",
                implementation_host="public.example",
                implementation_repo="example/project",
            )

            self.assertTrue(result["cross_repository"])
            self.assertEqual(result["ticket_url"], url)
            self.assertEqual(result["ticket_host"], "private.example")
            self.assertEqual(result["ticket_repo"], "example/workspace")
            self.assertEqual(result["implementation_host"], "public.example")
            self.assertEqual(result["implementation_repo"], "example/project")
            self.assertEqual(result["source_issue_mode"], "plan_only")
            self.assertEqual(result["state_dir"], str(state.resolve()))
            self.assertEqual(result["implementation_root"], str(implementation.resolve()))
            self.assertEqual(result["implementation_trunk"], str(implementation_trunk.resolve()))

    def test_cross_repository_review_paths_are_admitted_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ticket = self.make_repo(
                root,
                "private-workspace",
                "git@private.example:example/workspace.git",
            )
            implementation_trunk = self.make_repo(
                root,
                "public-project",
                "git@public.example:example/project.git",
            )
            implementation = root / "public-project-worktree"
            subprocess.run(
                [
                    "git",
                    "worktree",
                    "add",
                    "-q",
                    "-b",
                    "feature",
                    str(implementation),
                ],
                cwd=implementation_trunk,
                check=True,
            )
            state = ticket / ".hermes" / "issue-work" / "example-workspace-7"
            url = "https://private.example/example/workspace/issues/7"
            self.write_progress(
                state,
                ticket_url=url,
                worktree=implementation,
                ticket_repo="example/workspace",
                implementation_host="public.example",
                implementation_repo="example/project",
                implementation_trunk=implementation_trunk,
                branch="feature",
            )
            context = validator.validate_context(
                ticket_trunk=ticket,
                state_dir=state,
                worktree=implementation,
                ticket_url=url,
                ticket_host="private.example",
                ticket_repo="example/workspace",
                implementation_host="public.example",
                implementation_repo="example/project",
            )
            context_path = state / "context-validation.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")
            plan_path = state / "plan.md"
            plan_path.write_text("# Plan\n", encoding="utf-8")
            output_dir = state / "review"
            output_dir.mkdir()

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT.resolve()),
                    "--ticket-trunk",
                    str(ticket),
                    "--state-dir",
                    str(state),
                    "--worktree",
                    str(implementation),
                    "--ticket-url",
                    url,
                    "--ticket-host",
                    "private.example",
                    "--ticket-repo",
                    "example/workspace",
                    "--implementation-host",
                    "public.example",
                    "--implementation-repo",
                    "example/project",
                    "--context-validation",
                    str(context_path),
                    "--plan-path",
                    str(plan_path),
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=implementation,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            admitted = json.loads(result.stdout)
            self.assertEqual(admitted["state_dir"], str(state.resolve()))
            self.assertEqual(admitted["output_dir"], str(output_dir.resolve()))
            self.assertEqual(admitted["validator_script"], str(SCRIPT.resolve()))

    def test_same_repository_context_is_admitted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo(root, "project", "git@forge.example:example/project.git")
            state = repo / ".hermes" / "issue-work" / "example-project-4"
            url = "https://forge.example/example/project/issues/4"
            self.write_progress(
                state,
                ticket_url=url,
                worktree=repo,
                ticket_repo="example/project",
                implementation_host="forge.example",
                implementation_repo="example/project",
                implementation_trunk=repo,
            )

            result = validator.validate_context(
                ticket_trunk=repo,
                state_dir=state,
                worktree=repo,
                ticket_url=url,
                ticket_host="forge.example",
                ticket_repo="example/project",
                implementation_host="forge.example",
                implementation_repo="example/project",
            )

            self.assertFalse(result["cross_repository"])
            self.assertEqual(result["source_issue_mode"], "plan_only")

    def test_same_github_repository_enables_source_issue_shorthand(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo(root, "project", "git@github.com:example/project.git")
            state = repo / ".hermes" / "issue-work" / "example-project-4"
            url = "https://github.com/example/project/issues/4"
            self.write_progress(
                state,
                ticket_url=url,
                worktree=repo,
                ticket_repo="example/project",
                implementation_host="github.com",
                implementation_repo="example/project",
                implementation_trunk=repo,
            )

            result = validator.validate_context(
                ticket_trunk=repo,
                state_dir=state,
                worktree=repo,
                ticket_url=url,
                ticket_host="github.com",
                ticket_repo="example/project",
                implementation_host="github.com",
                implementation_repo="example/project",
            )

            self.assertEqual(result["source_issue_mode"], "github_shorthand")

    def test_wrong_progress_identity_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ticket = self.make_repo(root, "private-workspace", "git@private.example:example/workspace.git")
            implementation = self.make_repo(root, "public-project", "git@public.example:example/project.git")
            state = ticket / ".hermes" / "issue-work" / "example-workspace-7"
            url = "https://private.example/example/workspace/issues/7"
            self.write_progress(
                state,
                ticket_url=url,
                worktree=implementation,
                ticket_repo="example/workspace",
                implementation_host="public.example",
                implementation_repo="example/other-project",
                implementation_trunk=implementation,
            )

            with self.assertRaisesRegex(validator.ContextError, "progress implementation_repository"):
                validator.validate_context(
                    ticket_trunk=ticket,
                    state_dir=state,
                    worktree=implementation,
                    ticket_url=url,
                    ticket_host="private.example",
                    ticket_repo="example/workspace",
                    implementation_host="public.example",
                    implementation_repo="example/project",
                )

    def test_ticket_url_repository_must_match_ticket_repo(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ticket = self.make_repo(root, "private-workspace", "git@private.example:example/workspace.git")
            implementation = self.make_repo(root, "public-project", "git@public.example:example/project.git")
            state = ticket / ".hermes" / "issue-work" / "example-workspace-7"
            wrong_url = "https://private.example/example/other/issues/7"
            self.write_progress(
                state,
                ticket_url=wrong_url,
                worktree=implementation,
                ticket_repo="example/workspace",
                implementation_host="public.example",
                implementation_repo="example/project",
                implementation_trunk=implementation,
            )

            with self.assertRaisesRegex(validator.ContextError, "ticket URL repository"):
                validator.validate_context(
                    ticket_trunk=ticket,
                    state_dir=state,
                    worktree=implementation,
                    ticket_url=wrong_url,
                    ticket_host="private.example",
                    ticket_repo="example/workspace",
                    implementation_host="public.example",
                    implementation_repo="example/project",
                )

    def test_state_dir_must_stay_under_ticket_state_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ticket = self.make_repo(root, "private-workspace", "git@private.example:example/workspace.git")
            implementation = self.make_repo(root, "public-project", "git@public.example:example/project.git")
            outside = root / "outside"
            outside.mkdir()

            with self.assertRaisesRegex(validator.ContextError, "state directory"):
                validator.validate_context(
                    ticket_trunk=ticket,
                    state_dir=outside,
                    worktree=implementation,
                    ticket_url="https://private.example/example/workspace/issues/7",
                    ticket_host="private.example",
                    ticket_repo="example/workspace",
                    implementation_host="public.example",
                    implementation_repo="example/project",
                )


if __name__ == "__main__":
    unittest.main()
