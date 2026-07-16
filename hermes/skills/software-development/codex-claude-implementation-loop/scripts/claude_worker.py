#!/usr/bin/env python3
"""Run a subscription-authenticated Claude Code implementation worker.

This wrapper intentionally does not decide whether work is correct. It only
normalizes Claude Code's structured response for a Codex-backed Hermes parent,
which must inspect the repository and rerun tests independently.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parent.parent
REFERENCE_DIR = SKILL_DIR / "references"
IMPLEMENT_SCHEMA = REFERENCE_DIR / "implementation-result-schema.json"
REVISION_SCHEMA = REFERENCE_DIR / "revision-result-schema.json"
MAX_INPUT_CHARS = 200_000


class WorkerError(RuntimeError):
    """A fail-closed worker error suitable for a JSON response."""


def run_command(
    argv: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 30,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv,
            cwd=str(cwd) if cwd else None,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise WorkerError(f"command timed out after {timeout}s: {argv[0]}") from exc
    except OSError as exc:
        raise WorkerError(f"could not run {argv[0]}: {exc}") from exc


def emit(payload: dict[str, Any], *, exit_code: int) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return exit_code


def read_bounded(path_text: str, label: str) -> tuple[Path, str]:
    path = Path(path_text).expanduser().resolve()
    if not path.is_file():
        raise WorkerError(f"{label} file does not exist: {path}")
    content = path.read_text(encoding="utf-8")
    if not content.strip():
        raise WorkerError(f"{label} file is empty: {path}")
    if len(content) > MAX_INPUT_CHARS:
        raise WorkerError(
            f"{label} file exceeds {MAX_INPUT_CHARS} characters: {path}"
        )
    return path, content


def verify_subscription_auth(claude_bin: str) -> str:
    if os.environ.get("ANTHROPIC_API_KEY"):
        raise WorkerError(
            "ANTHROPIC_API_KEY is set; refusing to risk Anthropic API billing. "
            "Unset it before using the subscription-backed worker."
        )

    status = run_command([claude_bin, "auth", "status", "--text"], timeout=30)
    if status.returncode != 0:
        detail = (status.stderr or status.stdout).strip()[-2000:]
        raise WorkerError(f"Claude authentication check failed: {detail}")

    text = status.stdout.strip()
    match = re.search(r"^Login method:\s*(.+)$", text, flags=re.MULTILINE)
    if not match:
        raise WorkerError("Claude authentication output did not include a login method")

    method = match.group(1).strip()
    if "account" not in method.lower() or "api" in method.lower():
        raise WorkerError(
            f"Claude login is not recognized as subscription-backed: {method}"
        )
    return method


def resolve_repository(workdir_text: str) -> tuple[Path, str]:
    workdir = Path(workdir_text).expanduser().resolve()
    if not workdir.is_dir():
        raise WorkerError(f"working directory does not exist: {workdir}")

    root_result = run_command(
        ["git", "rev-parse", "--show-toplevel"], cwd=workdir, timeout=30
    )
    if root_result.returncode != 0:
        raise WorkerError(f"working directory is not a Git repository: {workdir}")

    root = Path(root_result.stdout.strip()).resolve()
    status_result = run_command(
        ["git", "status", "--short", "--untracked-files=all"],
        cwd=root,
        timeout=30,
    )
    if status_result.returncode != 0:
        raise WorkerError("could not record the repository's initial status")
    return root, status_result.stdout.rstrip()


def load_schema(path: Path) -> dict[str, Any]:
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkerError(f"could not load worker schema {path}: {exc}") from exc
    if not isinstance(schema, dict):
        raise WorkerError(f"worker schema is not a JSON object: {path}")
    return schema


def disabled_user_plugin_settings() -> dict[str, Any]:
    """Return a CLI settings override that disables user-enabled plugins.

    User settings are not loaded by the worker, but Claude's plugin registry is
    independent of setting-source selection. Explicit false entries prevent
    personal hooks from writing helper artifacts into the target repository.
    """
    config_dir = Path(
        os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))
    ).expanduser()
    settings_path = config_dir / "settings.json"
    if not settings_path.is_file():
        return {"enabledPlugins": {}}
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkerError(f"could not inspect Claude plugin settings: {exc}") from exc
    enabled = settings.get("enabledPlugins") if isinstance(settings, dict) else None
    if not isinstance(enabled, dict):
        return {"enabledPlugins": {}}
    return {"enabledPlugins": {str(name): False for name in enabled}}


def implementation_prompt(plan_path: Path, plan: str, baseline: str) -> str:
    baseline_text = baseline or "(clean working tree)"
    return f"""You are the implementation worker in a Codex-planned development loop.
Codex remains the planner, independent reviewer, test gate, and final authority.

Implement the complete plan below in the current repository. Follow the
repository's CLAUDE.md and other project instructions. Use test-driven
development where the plan calls for it, and run the plan's initial test suite.

Hard boundaries:
- Do not commit, push, create a PR, publish, deploy, reset, clean, stash, or
  rewrite Git history.
- Do not stage files.
- Do not alter unrelated pre-existing work.
- Do not broaden scope or perform drive-by refactors.
- Never read credential files or reveal secrets.
- If the plan is ambiguous or unsafe, stop and report a blocker rather than
  guessing.
- Your structured response is a work report, not final approval. Codex will
  inspect the actual diff and rerun tests independently.

Initial repository status before your run:
<initial_git_status>
{baseline_text}
</initial_git_status>

Codex implementation plan ({plan_path}):
<codex_plan>
{plan}
</codex_plan>

Implement and test now, then return the required structured result."""


def revision_prompt(review_path: Path, review: str, baseline: str) -> str:
    baseline_text = baseline or "(clean working tree)"
    return f"""Continue as the implementation worker in the existing Codex–Claude loop.
Codex independently reviewed the repository and returned the findings below.
Address every blocking finding precisely, add or update regression tests where
needed, and rerun the relevant tests.

Hard boundaries remain in force:
- Do not commit, push, create a PR, publish, deploy, reset, clean, stash, stage
  files, or rewrite Git history.
- Do not discard unrelated or pre-existing work.
- Fix the reported issues without unrelated refactoring or new features.
- Never read credential files or reveal secrets.
- If a finding is incorrect, contradictory, ambiguous, or unsafe to implement,
  leave it unresolved and explain why instead of guessing.
- Codex will inspect the full final diff and rerun tests independently.

Repository status at the start of this revision:
<revision_git_status>
{baseline_text}
</revision_git_status>

Codex review findings ({review_path}):
<codex_review>
{review}
</codex_review>

Apply the corrections and return the required structured result."""


def retryable_claude_failure(completed: subprocess.CompletedProcess[str]) -> bool:
    if completed.returncode == 0:
        return False
    try:
        payload = json.loads(completed.stdout)
    except (json.JSONDecodeError, TypeError):
        return False
    if not isinstance(payload, dict):
        return False
    status = payload.get("api_error_status")
    return status in {429, 500, 502, 503, 529} or payload.get("terminal_reason") == "api_error"


def parse_claude_output(stdout: str) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError as exc:
        excerpt = stdout.strip()[-2000:]
        raise WorkerError(f"Claude returned invalid JSON: {exc}; output: {excerpt}") from exc
    if not isinstance(envelope, dict):
        raise WorkerError("Claude JSON output was not an object")

    structured = envelope.get("structured_output")
    if structured is None and isinstance(envelope.get("result"), str):
        try:
            candidate = json.loads(envelope["result"])
        except json.JSONDecodeError:
            candidate = None
        if isinstance(candidate, dict):
            structured = candidate

    if not isinstance(structured, dict):
        raise WorkerError("Claude output did not contain a structured_output object")
    return envelope, structured


def execute_worker(args: argparse.Namespace) -> dict[str, Any]:
    claude_bin = shutil.which("claude")
    if not claude_bin:
        raise WorkerError("claude executable was not found on PATH")

    login_method = verify_subscription_auth(claude_bin)
    if args.mode == "check":
        return {
            "ok": True,
            "mode": "check",
            "claude_bin": claude_bin,
            "login_method": login_method,
        }

    root, baseline = resolve_repository(args.workdir)
    if args.mode == "implement":
        source_path, source_text = read_bounded(args.plan, "plan")
        schema_path = IMPLEMENT_SCHEMA
        prompt = implementation_prompt(source_path, source_text, baseline)
    else:
        source_path, source_text = read_bounded(args.review, "review")
        schema_path = REVISION_SCHEMA
        prompt = revision_prompt(source_path, source_text, baseline)

    schema = load_schema(schema_path)
    command = [
        claude_bin,
        "-p",
        "--setting-sources",
        "project,local",
        "--settings",
        json.dumps(disabled_user_plugin_settings(), separators=(",", ":")),
        "--disable-slash-commands",
        "--model",
        args.model,
        "--permission-mode",
        "acceptEdits",
        "--allowedTools",
        "Read,Edit,Write,Glob,Grep,Bash",
        "--disallowedTools",
        "Bash(git commit *),Bash(git push *),Bash(git reset *),Bash(git clean *),Bash(git stash *),Bash(git add *)",
        "--max-turns",
        str(args.max_turns),
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(schema, separators=(",", ":")),
    ]
    if args.mode == "revise":
        command.extend(["--resume", args.session_id])
    command.append(prompt)

    worker_env = os.environ.copy()
    worker_env["PYTHONDONTWRITEBYTECODE"] = "1"
    worker_env["NODE_COMPILE_CACHE"] = str(
        Path(tempfile.gettempdir()) / "hermes-claude-worker-node-cache"
    )
    completed: subprocess.CompletedProcess[str] | None = None
    for attempt in range(1, args.attempts + 1):
        completed = run_command(
            command,
            cwd=root,
            timeout=args.timeout,
            env=worker_env,
        )
        if completed.returncode == 0:
            break
        if attempt >= args.attempts or not retryable_claude_failure(completed):
            break
        time.sleep(min(5 * (2 ** (attempt - 1)), 30))

    assert completed is not None
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()[-4000:]
        raise WorkerError(
            f"Claude worker exited with status {completed.returncode}: {detail}"
        )

    envelope, structured = parse_claude_output(completed.stdout)
    session_id = envelope.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip():
        raise WorkerError("Claude output did not contain a usable session_id")

    return {
        "ok": True,
        "mode": args.mode,
        "model": args.model,
        "login_method": login_method,
        "workdir": str(root),
        "input_file": str(source_path),
        "initial_git_status": baseline,
        "session_id": session_id,
        "worker_result": structured,
        "claude_metadata": {
            "num_turns": envelope.get("num_turns"),
            "duration_ms": envelope.get("duration_ms"),
            "duration_api_ms": envelope.get("duration_api_ms"),
            "is_error": envelope.get("is_error"),
            "stop_reason": envelope.get("stop_reason"),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run Claude Code as a subscription-backed implementation worker; "
            "the Codex parent must independently review and test the result."
        )
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    subparsers.add_parser(
        "check", help="verify Claude CLI subscription authentication without a model call"
    )

    def add_common(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--workdir", default=os.getcwd())
        subparser.add_argument("--model", default="opus")
        subparser.add_argument(
            "--allow-non-opus",
            action="store_true",
            help="allow a non-Opus model only after explicit user confirmation",
        )
        subparser.add_argument("--max-turns", type=int, default=40)
        subparser.add_argument("--timeout", type=int, default=1800)
        subparser.add_argument(
            "--attempts",
            type=int,
            default=2,
            help="total Claude invocations after retryable API failures (default: 2)",
        )

    implement = subparsers.add_parser(
        "implement", help="start a Claude implementation session from a Codex plan"
    )
    add_common(implement)
    implement.add_argument("--plan", required=True)

    revise = subparsers.add_parser(
        "revise", help="resume a Claude implementation session with Codex findings"
    )
    add_common(revise)
    revise.add_argument("--session-id", required=True)
    revise.add_argument("--review", required=True)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if (
        hasattr(args, "model")
        and "opus" not in args.model.lower()
        and not args.allow_non_opus
    ):
        return emit(
            {
                "ok": False,
                "error": (
                    "non-Opus Claude models require explicit user confirmation; "
                    "rerun with --allow-non-opus only after receiving it"
                ),
            },
            exit_code=2,
        )
    if hasattr(args, "max_turns") and args.max_turns < 1:
        return emit(
            {"ok": False, "error": "--max-turns must be at least 1"}, exit_code=2
        )
    if hasattr(args, "attempts") and args.attempts < 1:
        return emit(
            {"ok": False, "error": "--attempts must be at least 1"}, exit_code=2
        )
    if hasattr(args, "timeout") and args.timeout < 30:
        return emit(
            {"ok": False, "error": "--timeout must be at least 30 seconds"},
            exit_code=2,
        )

    try:
        payload = execute_worker(args)
    except WorkerError as exc:
        return emit({"ok": False, "mode": args.mode, "error": str(exc)}, exit_code=1)
    except Exception as exc:  # Fail closed without a raw traceback in agent context.
        return emit(
            {
                "ok": False,
                "mode": args.mode,
                "error": f"unexpected worker failure: {type(exc).__name__}: {exc}",
            },
            exit_code=1,
        )
    return emit(payload, exit_code=0)


if __name__ == "__main__":
    sys.exit(main())
