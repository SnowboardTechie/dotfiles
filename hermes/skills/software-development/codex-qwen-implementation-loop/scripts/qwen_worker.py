#!/usr/bin/env python3
"""Run Hermes as an isolated, local-Qwen implementation worker.

The wrapper pins a loopback OpenAI-compatible endpoint, passes only allowlisted
toolchain environment variables, and normalizes the worker report for a
Codex-backed Hermes parent that independently reviews the repository and tests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping
from urllib.error import URLError
from urllib.request import urlopen

MODEL = "qwen3.6:35b-a3b-coding-nvfp4"
PROVIDER = "custom:local-qwen"
BASE_URL = "http://127.0.0.1:11434/v1"
OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"
DEFAULT_WORKER_HOME = Path.home() / ".hermes" / "local-qwen-worker"
SANDBOX_EXEC = Path("/usr/bin/sandbox-exec")
MAX_INPUT_CHARS = 200_000
CLOUD_CREDENTIAL_KEYS = {
    "ANTHROPIC_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "DEEPSEEK_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "GROQ_API_KEY",
    "MISTRAL_API_KEY",
    "NOUS_API_KEY",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "OPENWEBUI_API_KEY",
    "OPEN_WEBUI_API_KEY",
    "TOGETHER_API_KEY",
    "XAI_API_KEY",
}
SAFE_ENV_KEYS = {
    "BUNDLE_GEMFILE",
    "BUNDLE_PATH",
    "CC",
    "CCACHE_DIR",
    "CFLAGS",
    "CMAKE_PREFIX_PATH",
    "CARGO_HOME",
    "CI",
    "CLICOLOR",
    "CLICOLOR_FORCE",
    "COLORTERM",
    "CONDA_PREFIX",
    "CPPFLAGS",
    "CXX",
    "CXXFLAGS",
    "DEVELOPER_DIR",
    "GEM_HOME",
    "GEM_PATH",
    "GOPATH",
    "GOPRIVATE",
    "GOROOT",
    "HOME",
    "JAVA_HOME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "LOGNAME",
    "MACOSX_DEPLOYMENT_TARGET",
    "MAKEFLAGS",
    "NIX_BUILD_CORES",
    "NIX_CFLAGS_COMPILE",
    "NIX_CFLAGS_LINK",
    "NIX_LDFLAGS",
    "NIX_PATH",
    "NIX_PROFILES",
    "NIX_SSL_CERT_FILE",
    "NO_COLOR",
    "PATH",
    "PIP_CACHE_DIR",
    "PKG_CONFIG_PATH",
    "PNPM_HOME",
    "PYENV_ROOT",
    "RUSTFLAGS",
    "RUSTUP_HOME",
    "SDKROOT",
    "SHELL",
    "SSL_CERT_DIR",
    "SSL_CERT_FILE",
    "TEMP",
    "TERM",
    "TERM_PROGRAM",
    "TERM_PROGRAM_VERSION",
    "TMP",
    "TMPDIR",
    "USER",
    "UV_CACHE_DIR",
    "VIRTUAL_ENV",
}
FORBIDDEN_WORKER_CREDENTIAL_PATHS = (
    ".env",
    "auth.json",
    "auth.json.enc",
    "credentials.json",
    "oauth.json",
)
IMPLEMENT_FIELDS = {
    "status",
    "summary",
    "files_changed",
    "tests",
    "plan_deviations",
    "blockers",
    "notes",
}
REVISION_FIELDS = {
    "status",
    "summary",
    "files_changed",
    "tests",
    "findings_addressed",
    "unresolved_findings",
    "blockers",
    "notes",
}


class WorkerError(RuntimeError):
    """A fail-closed local-worker error suitable for a JSON response."""

    def __init__(self, message: str, *, session_id: str | None = None) -> None:
        super().__init__(message)
        self.session_id = session_id


def emit(payload: dict[str, Any], *, exit_code: int) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return exit_code


def resolve_worker_home() -> Path:
    configured = os.environ.get("HERMES_QWEN_WORKER_HOME")
    home = Path(configured).expanduser() if configured else DEFAULT_WORKER_HOME
    home = home.resolve()
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        home.chmod(0o700)
    except OSError as exc:
        raise WorkerError(f"could not secure local Qwen worker home: {exc}") from exc
    return home


def worker_config_text() -> str:
    return f"""_config_version: 33
model:
  default: {MODEL}
  provider: {PROVIDER}
  base_url: {BASE_URL}
agent:
  max_turns: 60
compression:
  enabled: false
auxiliary:
  transient_retries: 1
  compression: &local_auxiliary
    provider: custom
    model: {MODEL}
    base_url: {BASE_URL}
    api_key: ollama
    fallback_chain: []
  title_generation:
    <<: *local_auxiliary
custom_providers:
  - name: local-qwen
    base_url: {BASE_URL}
    api_mode: chat_completions
    model: {MODEL}
    models:
      {MODEL}:
        context_length: 262144
"""


def validate_worker_home_credentials(home: Path) -> None:
    """Reject credential stores that could re-enable a remote auxiliary route."""
    present = [name for name in FORBIDDEN_WORKER_CREDENTIAL_PATHS if (home / name).exists()]
    if present:
        raise WorkerError(
            "local Qwen worker home contains forbidden credential files: "
            + ", ".join(present)
        )


def ensure_worker_config(home: Path) -> Path:
    """Atomically install the worker's local-only Hermes configuration."""
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    home.chmod(0o700)
    validate_worker_home_credentials(home)
    config_path = home / "config.yaml"
    expected = worker_config_text()
    if config_path.is_file() and config_path.read_text(encoding="utf-8") == expected:
        config_path.chmod(0o600)
        return config_path

    fd, temp_name = tempfile.mkstemp(prefix="config-", suffix=".yaml", dir=home)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(expected)
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, config_path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    config_path.chmod(0o600)
    return config_path


def build_worker_env(
    home: Path,
    source: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build a local-only child environment without cloud inference secrets."""
    source_env = source if source is not None else os.environ
    worker_env = {
        key: value
        for key, value in source_env.items()
        if key in SAFE_ENV_KEYS or key.startswith("LC_")
    }
    for key in CLOUD_CREDENTIAL_KEYS:
        worker_env.pop(key, None)
    for key in (
        "HERMES_INFERENCE_MODEL",
        "HERMES_INFERENCE_PROVIDER",
        "HERMES_IGNORE_RULES",
        "HERMES_IGNORE_USER_CONFIG",
        "HERMES_PROFILE",
        "HERMES_SESSION_ID",
        "TERMINAL_CWD",
        "_HERMES_GATEWAY",
    ):
        worker_env.pop(key, None)
    worker_env["HERMES_HOME"] = str(home)
    worker_env["HERMES_YOLO_MODE"] = "1"
    worker_env["PYTHONDONTWRITEBYTECODE"] = "1"
    worker_env["CLAUDE_CONFIG_DIR"] = str(home / "disabled-claude")
    worker_env["CODEX_HOME"] = str(home / "disabled-codex")
    return worker_env


def verify_local_model(timeout: int = 10) -> dict[str, Any]:
    try:
        with urlopen(OLLAMA_TAGS_URL, timeout=timeout) as response:  # noqa: S310
            payload = json.load(response)
    except (OSError, URLError, json.JSONDecodeError) as exc:
        raise WorkerError(f"local Ollama endpoint is unavailable: {exc}") from exc
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        raise WorkerError("local Ollama tag response did not contain a model list")
    match = next(
        (
            item
            for item in models
            if isinstance(item, dict) and item.get("name") == MODEL
        ),
        None,
    )
    if match is None:
        raise WorkerError(f"required local model is not installed: {MODEL}")
    return match


def run_command(
    argv: list[str],
    *,
    cwd: Path,
    timeout: int,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv,
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise WorkerError(f"local Qwen worker timed out after {timeout}s") from exc
    except OSError as exc:
        raise WorkerError(f"could not run Hermes local worker: {exc}") from exc


def repository_status(root: Path) -> str:
    completed = run_command(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=root,
        timeout=30,
        env=os.environ.copy(),
    )
    if completed.returncode != 0:
        raise WorkerError("could not record repository status")
    return completed.stdout


def status_paths(status: str) -> set[str]:
    """Parse NUL-delimited porcelain v1 without quoting or arrow ambiguity."""
    paths: set[str] = set()
    records = status.split("\0")
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        if len(record) < 4 or record[2] != " ":
            raise WorkerError("Git returned malformed porcelain status")
        code = record[:2]
        path = record[3:]
        paths.add(path)
        if "R" in code or "C" in code:
            if index >= len(records) or not records[index]:
                raise WorkerError("Git returned a malformed rename status")
            index += 1
    return paths


def render_status(status: str) -> str:
    paths = sorted(status_paths(status))
    return json.dumps(paths, ensure_ascii=False) if paths else "(clean working tree)"


def _path_fingerprint(root: Path, relative: str) -> str:
    digest = hashlib.sha256()
    diff = subprocess.run(
        ["git", "diff", "--binary", "--no-ext-diff", "HEAD", "--", relative],
        cwd=str(root),
        capture_output=True,
        check=False,
        timeout=30,
    )
    if diff.returncode != 0:
        raise WorkerError(f"could not fingerprint repository path: {relative}")
    digest.update(diff.stdout)
    path = root / relative
    if path.is_symlink():
        digest.update(b"symlink\0" + os.readlink(path).encode("utf-8", "surrogateescape"))
    elif path.is_file():
        digest.update(b"file\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    elif path.exists():
        digest.update(b"other\0")
    else:
        digest.update(b"missing\0")
    return digest.hexdigest()


def fingerprint_paths(root: Path, paths: set[str]) -> dict[str, str]:
    return {path: _path_fingerprint(root, path) for path in paths}


def changed_paths_since_baseline(
    root: Path,
    initial_paths: set[str],
    initial_fingerprints: dict[str, str],
    final_paths: set[str],
) -> set[str]:
    changed = set(final_paths - initial_paths)
    final_initial_fingerprints = fingerprint_paths(root, initial_paths)
    changed.update(
        path
        for path in initial_paths
        if final_initial_fingerprints[path] != initial_fingerprints[path]
    )
    return changed


def resolve_repository(workdir_text: str) -> tuple[Path, Path, str, str]:
    workdir = Path(workdir_text).expanduser().resolve()
    if not workdir.is_dir():
        raise WorkerError(f"working directory does not exist: {workdir}")
    env = os.environ.copy()
    root_result = run_command(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=workdir,
        timeout=30,
        env=env,
    )
    if root_result.returncode != 0:
        raise WorkerError(f"working directory is not a Git repository: {workdir}")
    root = Path(root_result.stdout.strip()).resolve()
    common_result = run_command(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=root,
        timeout=30,
        env=env,
    )
    if common_result.returncode != 0:
        raise WorkerError("could not resolve the repository's Git common directory")
    common_dir = Path(common_result.stdout.strip()).resolve()
    if not common_dir.is_dir():
        raise WorkerError(f"Git common directory does not exist: {common_dir}")
    baseline = repository_status(root)
    staged_result = run_command(
        ["git", "diff", "--cached", "--quiet"],
        cwd=root,
        timeout=30,
        env=env,
    )
    if staged_result.returncode != 0:
        raise WorkerError("local Qwen requires an unstaged baseline")
    head_result = run_command(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        timeout=30,
        env=env,
    )
    if head_result.returncode != 0:
        raise WorkerError("working repository must have an initial commit")
    return root, common_dir, baseline, head_result.stdout.strip()


def validate_initial_status(*, mode: str, baseline: str) -> None:
    if mode == "implement" and baseline:
        raise WorkerError(
            "local Qwen implementation requires a clean worktree; preserve or "
            "remove pre-existing changes before delegation"
        )


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


def result_contract(mode: str) -> str:
    if mode == "implement":
        fields = """{
  "status": "completed | blocked | failed",
  "summary": "concise work report",
  "files_changed": ["repo-relative path"],
  "tests": [{"command": "...", "status": "passed | failed | skipped", "summary": "..."}],
  "plan_deviations": [],
  "blockers": [],
  "notes": []
}"""
    else:
        fields = """{
  "status": "completed | blocked | failed",
  "summary": "concise revision report",
  "files_changed": ["repo-relative path"],
  "tests": [{"command": "...", "status": "passed | failed | skipped", "summary": "..."}],
  "findings_addressed": [],
  "unresolved_findings": [],
  "blockers": [],
  "notes": []
}"""
    return fields


def implementation_prompt(
    root: Path,
    plan_path: Path,
    plan: str,
    baseline: str,
) -> str:
    baseline_text = render_status(baseline)
    return f"""You are the local Qwen implementation worker in a GPT-planned issue-work loop.
The GPT Hermes parent remains the planner, independent reviewer, test gate, and final authority.

Implement the complete approved plan below in the current repository. Read and
follow the repository's AGENTS.md, CLAUDE.md, and other project instructions.
Use test-driven development for behavior changes and run the plan's initial checks.

Repository root: {root}
All file and terminal operations must stay inside this repository root.

Hard boundaries:
- Do not commit, stage, push, create a PR, publish, deploy, reset, clean, stash,
  or rewrite Git history.
- Do not invoke Claude, Codex, another Hermes process, or any cloud model.
- Do not alter unrelated pre-existing work or perform drive-by refactors.
- Never read credential files or reveal secrets.
- If the plan is ambiguous, unsafe, or requires unavailable credentials, stop
  and report a blocker rather than guessing.
- Your report is evidence, not approval. The GPT parent will inspect the actual
  diff and rerun every required check.

Initial repository status:
<initial_git_status>
{baseline_text}
</initial_git_status>

Approved issue-work plan ({plan_path}):
<implementation_plan>
{plan}
</implementation_plan>

Implement and test now. Your final response must be exactly one JSON object,
without a Markdown fence or prose, matching this contract:
{result_contract("implement")}
"""


def revision_prompt(
    root: Path,
    review_path: Path,
    review: str,
    baseline: str,
) -> str:
    baseline_text = render_status(baseline)
    return f"""Continue as the local Qwen implementation worker in the existing GPT-Qwen issue-work loop.
The GPT Hermes parent independently reviewed the repository and supplied the
blocking findings below. Address each finding precisely, update regression tests
where needed, and rerun the relevant checks.

Repository root: {root}
All file and terminal operations must stay inside this repository root.

Hard boundaries remain in force:
- Do not commit, stage, push, create a PR, publish, deploy, reset, clean, stash,
  or rewrite Git history.
- Do not invoke Claude, Codex, another Hermes process, or any cloud model.
- Do not discard unrelated or pre-existing work or broaden scope.
- Never read credential files or reveal secrets.
- If a finding is incorrect, contradictory, ambiguous, or unsafe, leave it
  unresolved and explain why instead of guessing.
- The GPT parent will inspect the full diff and rerun tests independently.

Repository status at the start of this revision:
<revision_git_status>
{baseline_text}
</revision_git_status>

GPT review findings ({review_path}):
<review_findings>
{review}
</review_findings>

Apply corrections now. Your final response must be exactly one JSON object,
without a Markdown fence or prose, matching this contract:
{result_contract("revise")}
"""


def build_sandbox_profile(
    *,
    root: Path,
    common_dir: Path,
    worker_home: Path,
    temp_dir: Path,
) -> str:
    """Constrain worker writes to the repo/runtime and network to loopback."""
    user_home = Path.home().resolve()
    writable = {
        Path("/dev"),
        root.resolve(),
        worker_home.resolve(),
        temp_dir.resolve(),
        (user_home / ".cache").resolve(),
        (user_home / ".npm").resolve(),
        (user_home / "Library" / "Caches").resolve(),
        (user_home / ".cargo" / "registry").resolve(),
        (user_home / ".cargo" / "git").resolve(),
        (user_home / "go" / "pkg").resolve(),
    }
    write_filters = " ".join(
        f"(subpath {json.dumps(str(path))})" for path in sorted(writable)
    )
    denied_reads = {
        user_home / ".secrets",
        user_home / ".ssh",
        user_home / ".gnupg",
        user_home / ".aws",
        user_home / ".kube",
        user_home / ".claude",
        user_home / ".codex",
        user_home / ".docker",
        user_home / ".git-credentials",
        user_home / ".netrc",
        user_home / ".npmrc",
        user_home / ".pypirc",
        user_home / ".config" / "gh",
        user_home / ".config" / "gcloud",
        user_home / ".config" / "glab-cli",
        user_home / ".config" / "gws",
        user_home / ".config" / "himalaya",
        user_home / ".config" / "hub",
        user_home / ".config" / "notion",
        user_home / ".config" / "opencode",
        user_home / ".config" / "pip",
        user_home / ".config" / "tea",
        user_home / "Library" / "Keychains",
        user_home / "Library" / "Application Support" / "Claude",
        user_home / "Library" / "Application Support" / "Hermes",
        user_home / ".local" / "share" / "opencode",
        user_home / ".hermes" / ".env",
        user_home / ".hermes" / "auth.json",
        user_home / ".hermes" / "config.yaml",
        user_home / ".hermes" / "state.db",
        user_home / ".hermes" / "profiles",
    }
    read_filters = " ".join(
        f"(subpath {json.dumps(str(path.resolve()))})" for path in sorted(denied_reads)
    )
    git_paths = {common_dir.resolve(), (root / ".git").resolve()}
    git_write_filters = " ".join(
        f"(subpath {json.dumps(str(path))})" for path in sorted(git_paths)
    )
    return "\n".join(
        (
            "(version 1)",
            "(allow default)",
            "(deny network*)",
            '(allow network-outbound (remote ip "localhost:11434"))',
            f"(deny file-read* {read_filters})",
            "(deny process-exec (literal \"/usr/bin/security\"))",
            f"(deny file-write* (require-not (require-any {write_filters})))",
            f"(deny file-write* {git_write_filters})",
        )
    )


def wrap_sandbox_command(command: list[str], profile: str) -> list[str]:
    if not SANDBOX_EXEC.is_file():
        raise WorkerError(f"required macOS sandbox executable is unavailable: {SANDBOX_EXEC}")
    return [str(SANDBOX_EXEC), "-p", profile, *command]


def build_hermes_command(
    *,
    hermes_bin: str,
    prompt: str,
    max_turns: int,
    session_id: str | None,
) -> list[str]:
    command = [
        hermes_bin,
        "chat",
        "--quiet",
        "--query",
        prompt,
        "--provider",
        PROVIDER,
        "--model",
        MODEL,
        "--toolsets",
        "terminal,file",
        "--skills",
        "test-driven-development,systematic-debugging",
        "--source",
        "tool",
        "--max-turns",
        str(max_turns),
        "--yolo",
    ]
    if session_id:
        command.extend(["--resume", session_id, "--no-restore-cwd"])
    return command


def extract_session_id(stderr: str) -> str:
    matches = re.findall(r"^session_id:\s*(\S+)\s*$", stderr, flags=re.MULTILINE)
    if not matches:
        raise WorkerError("Hermes output did not contain a usable session_id")
    return matches[-1]


def validate_resumed_session_id(requested: str, returned: str) -> None:
    if returned != requested:
        raise WorkerError(
            f"Hermes resumed a different session: requested {requested}, returned {returned}",
            session_id=returned,
        )


def _session_record_path(home: Path, session_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", session_id):
        raise WorkerError(f"invalid worker session ID: {session_id!r}")
    return home / "session-bindings" / f"{session_id}.json"


def write_session_record(home: Path, session_id: str, root: Path, common_dir: Path) -> None:
    path = _session_record_path(home, session_id)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload = {
        "session_id": session_id,
        "root": str(root.resolve()),
        "git_common_dir": str(common_dir.resolve()),
        "provider": PROVIDER,
        "model": MODEL,
        "base_url": BASE_URL,
    }
    fd, temporary = tempfile.mkstemp(prefix="binding-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def validate_session_record(
    home: Path,
    session_id: str,
    root: Path,
    common_dir: Path,
) -> dict[str, Any]:
    path = _session_record_path(home, session_id)
    if not path.is_file():
        raise WorkerError(
            f"worker session has no repository binding: {session_id}; start a new implementation"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkerError(f"worker session binding is invalid: {session_id}") from exc
    expected = {
        "session_id": session_id,
        "root": str(root.resolve()),
        "git_common_dir": str(common_dir.resolve()),
        "provider": PROVIDER,
        "model": MODEL,
        "base_url": BASE_URL,
    }
    if payload != expected:
        raise WorkerError(
            f"worker session is bound to a different repository or runtime: {session_id}"
        )
    return payload


def _json_objects(stdout: str) -> list[dict[str, Any]]:
    """Extract JSON objects even when a local model adds prose or a fence."""
    text = stdout.strip()
    fenced = re.findall(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    candidates = [*fenced, text]
    decoder = json.JSONDecoder()
    objects: list[dict[str, Any]] = []
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            for match in re.finditer(r"\{", candidate):
                try:
                    parsed, _ = decoder.raw_decode(candidate, match.start())
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    objects.append(parsed)
            continue
        if isinstance(parsed, dict):
            objects.append(parsed)
    return objects


def _require_string_list(result: dict[str, Any], field: str) -> None:
    value = result[field]
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise WorkerError(f"worker field {field!r} must be a list of strings")


def validate_worker_result(result: dict[str, Any], *, mode: str) -> None:
    required = IMPLEMENT_FIELDS if mode == "implement" else REVISION_FIELDS
    missing = sorted(required - set(result))
    extra = sorted(set(result) - required)
    if missing:
        raise WorkerError(f"worker result is missing required fields: {', '.join(missing)}")
    if extra:
        raise WorkerError(f"worker result has unexpected fields: {', '.join(extra)}")
    if result["status"] not in {"completed", "blocked", "failed"}:
        raise WorkerError("worker status must be completed, blocked, or failed")
    if not isinstance(result["summary"], str):
        raise WorkerError("worker summary must be a string")
    for field in required - {"status", "summary", "tests"}:
        _require_string_list(result, field)
    tests = result["tests"]
    if not isinstance(tests, list):
        raise WorkerError("worker tests field must be a list")
    for index, test in enumerate(tests):
        if not isinstance(test, dict) or set(test) != {"command", "status", "summary"}:
            raise WorkerError(f"worker test {index} has an invalid shape")
        if not all(isinstance(test[key], str) for key in test):
            raise WorkerError(f"worker test {index} fields must be strings")
        if test["status"] not in {"passed", "failed", "skipped"}:
            raise WorkerError(f"worker test {index} has an invalid status")


def parse_worker_output(stdout: str, *, mode: str) -> dict[str, Any]:
    objects = _json_objects(stdout)
    validation_error: WorkerError | None = None
    valid: list[dict[str, Any]] = []
    for result in objects:
        try:
            validate_worker_result(result, mode=mode)
        except WorkerError as exc:
            validation_error = exc
        else:
            valid.append(result)
    if valid:
        return valid[-1]
    if validation_error is not None:
        raise validation_error
    excerpt = stdout.strip()[-2000:]
    raise WorkerError(f"local Qwen returned no valid JSON object; output: {excerpt}")


def validate_reported_paths(
    root: Path,
    reported_paths: list[str],
    status_paths: set[str],
    changed_paths: set[str],
) -> None:
    root = root.resolve()
    for reported in reported_paths:
        relative = Path(reported)
        resolved = (root / relative).resolve()
        if relative.is_absolute() or not resolved.is_relative_to(root):
            raise WorkerError(f"worker reported a path outside the repository: {reported}")
        normalized = str(relative)
        if normalized not in status_paths | changed_paths:
            raise WorkerError(
                f"worker-reported path is not present in Git status or invocation changes: {reported}"
            )
    unreported = sorted(changed_paths - set(reported_paths))
    if unreported:
        raise WorkerError(
            "local Qwen changed paths it did not report: " + ", ".join(unreported)
        )

def final_repository_status(root: Path, initial_head: str) -> tuple[str, set[str]]:
    env = os.environ.copy()
    head_result = run_command(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        timeout=30,
        env=env,
    )
    if head_result.returncode != 0 or head_result.stdout.strip() != initial_head:
        raise WorkerError("local Qwen changed repository HEAD or commit history")
    staged_result = run_command(
        ["git", "diff", "--cached", "--quiet"],
        cwd=root,
        timeout=30,
        env=env,
    )
    if staged_result.returncode != 0:
        raise WorkerError("local Qwen staged repository changes")
    status = repository_status(root)
    return status, status_paths(status)


def verify_hermes_config(
    hermes_bin: str,
    *,
    home: Path,
    env: dict[str, str],
) -> None:
    completed = run_command(
        [hermes_bin, "config", "check"],
        cwd=home,
        timeout=60,
        env=env,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()[-2000:]
        raise WorkerError(f"local Qwen Hermes configuration is invalid: {detail}")


def validate_session_metadata(
    metadata: dict[str, Any],
    session_id: str,
) -> dict[str, Any]:
    recorded_id = metadata.get("session_id") or metadata.get("id")
    if recorded_id is not None and recorded_id != session_id:
        raise WorkerError(
            f"session export returned unexpected ID {recorded_id!r}",
            session_id=session_id,
        )
    expected = {
        "model": MODEL,
        "billing_provider": "custom",
        "billing_base_url": BASE_URL,
        "source": "tool",
    }
    for field, value in expected.items():
        actual = metadata.get(field)
        if field == "billing_base_url":
            actual = str(actual or "").rstrip("/")
            value = value.rstrip("/")
        if actual != value:
            raise WorkerError(
                f"worker session used unexpected {field} {actual!r}; expected {value!r}",
                session_id=session_id,
            )
    return {
        "model": metadata.get("model"),
        "source": metadata.get("source"),
        "billing_provider": metadata.get("billing_provider"),
        "billing_base_url": metadata.get("billing_base_url"),
        "input_tokens": metadata.get("input_tokens"),
        "output_tokens": metadata.get("output_tokens"),
        "tool_call_count": metadata.get("tool_call_count"),
        "actual_cost_usd": metadata.get("actual_cost_usd"),
        "estimated_cost_usd": metadata.get("estimated_cost_usd"),
    }


def verify_session_metadata(
    hermes_bin: str,
    session_id: str,
    *,
    cwd: Path,
    timeout: int,
    env: dict[str, str],
) -> dict[str, Any]:
    completed = run_command(
        [
            hermes_bin,
            "sessions",
            "export",
            "--format",
            "jsonl",
            "--session-id",
            session_id,
            "-",
        ],
        cwd=cwd,
        timeout=timeout,
        env=env,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()[-2000:]
        raise WorkerError(f"could not verify local worker session metadata: {detail}")
    try:
        metadata = json.loads(completed.stdout.strip().splitlines()[0])
    except (json.JSONDecodeError, IndexError) as exc:
        raise WorkerError("Hermes session metadata was not valid JSONL") from exc
    return validate_session_metadata(metadata, session_id)


def execute_worker(args: argparse.Namespace) -> dict[str, Any]:
    worker_home = resolve_worker_home()
    config_path = ensure_worker_config(worker_home)
    for directory in (worker_home / "disabled-claude", worker_home / "disabled-codex"):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
    worker_env = build_worker_env(worker_home)
    model_info = verify_local_model()
    hermes_bin = shutil.which("hermes")
    if not hermes_bin:
        raise WorkerError("hermes executable was not found on PATH")
    verify_hermes_config(hermes_bin, home=worker_home, env=worker_env)

    if args.mode == "check":
        return {
            "ok": True,
            "mode": "check",
            "provider": PROVIDER,
            "model": MODEL,
            "base_url": BASE_URL,
            "worker_home": str(worker_home),
            "config_path": str(config_path),
            "config_check": "passed",
            "model_size": model_info.get("size"),
            "sandbox": str(SANDBOX_EXEC),
        }

    root, common_dir, baseline, initial_head = resolve_repository(args.workdir)
    validate_initial_status(mode=args.mode, baseline=baseline)
    initial_paths = status_paths(baseline)
    initial_fingerprints = fingerprint_paths(root, initial_paths)
    worker_env["TERMINAL_CWD"] = str(root)
    if args.mode == "implement":
        source_path, source_text = read_bounded(args.plan, "plan")
        prompt = implementation_prompt(root, source_path, source_text, baseline)
        session_id = None
    else:
        source_path, source_text = read_bounded(args.review, "review")
        prompt = revision_prompt(root, source_path, source_text, baseline)
        session_id = args.session_id
        validate_session_record(worker_home, session_id, root, common_dir)
        verify_session_metadata(
            hermes_bin,
            session_id,
            cwd=root,
            timeout=60,
            env=worker_env,
        )

    command = build_hermes_command(
        hermes_bin=hermes_bin,
        prompt=prompt,
        max_turns=args.max_turns,
        session_id=session_id,
    )
    temp_dir = Path(worker_env.get("TMPDIR") or tempfile.gettempdir()).resolve()
    sandbox_profile = build_sandbox_profile(
        root=root,
        common_dir=common_dir,
        worker_home=worker_home,
        temp_dir=temp_dir,
    )
    completed = run_command(
        wrap_sandbox_command(command, sandbox_profile),
        cwd=root,
        timeout=args.timeout,
        env=worker_env,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()[-4000:]
        match = re.findall(r"^session_id:\s*(\S+)\s*$", completed.stderr, flags=re.MULTILINE)
        raise WorkerError(
            f"local Qwen worker exited with status {completed.returncode}: {detail}",
            session_id=match[-1] if match else session_id,
        )

    worker_session_id = extract_session_id(completed.stderr)
    if session_id is not None:
        validate_resumed_session_id(session_id, worker_session_id)
    try:
        worker_result = parse_worker_output(completed.stdout, mode=args.mode)
        session_metadata = verify_session_metadata(
            hermes_bin,
            worker_session_id,
            cwd=root,
            timeout=60,
            env=worker_env,
        )
        if args.mode == "implement":
            write_session_record(worker_home, worker_session_id, root, common_dir)
        final_status, final_paths = final_repository_status(root, initial_head)
        changed_paths = changed_paths_since_baseline(
            root,
            initial_paths,
            initial_fingerprints,
            final_paths,
        )
        validate_reported_paths(
            root,
            worker_result["files_changed"],
            final_paths,
            changed_paths,
        )
        validate_worker_home_credentials(worker_home)
    except WorkerError as exc:
        raise WorkerError(
            f"session {worker_session_id}: {exc}",
            session_id=worker_session_id,
        ) from exc
    return {
        "ok": True,
        "mode": args.mode,
        "provider": PROVIDER,
        "model": MODEL,
        "base_url": BASE_URL,
        "worker_home": str(worker_home),
        "workdir": str(root),
        "git_common_dir": str(common_dir),
        "input_file": str(source_path),
        "initial_git_status": render_status(baseline),
        "final_git_status": render_status(final_status),
        "changed_paths_this_invocation": sorted(changed_paths),
        "session_id": worker_session_id,
        "sandbox": str(SANDBOX_EXEC),
        "worker_result": worker_result,
        "hermes_metadata": session_metadata,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run an isolated local-Qwen implementation worker; the GPT Hermes "
            "parent must independently review and test the result."
        )
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)
    subparsers.add_parser("check", help="verify the local endpoint and exact model")

    def add_common(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--workdir", default=os.getcwd())
        subparser.add_argument("--max-turns", type=int, default=60)
        subparser.add_argument("--timeout", type=int, default=3600)

    implement = subparsers.add_parser(
        "implement", help="start a local Qwen session from an approved plan"
    )
    add_common(implement)
    implement.add_argument("--plan", required=True)

    revise = subparsers.add_parser(
        "revise", help="resume the local Qwen session with GPT review findings"
    )
    add_common(revise)
    revise.add_argument("--session-id", required=True)
    revise.add_argument("--review", required=True)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if hasattr(args, "max_turns") and args.max_turns < 1:
        return emit({"ok": False, "error": "--max-turns must be at least 1"}, exit_code=2)
    if hasattr(args, "timeout") and args.timeout < 30:
        return emit({"ok": False, "error": "--timeout must be at least 30 seconds"}, exit_code=2)
    try:
        payload = execute_worker(args)
    except WorkerError as exc:
        error_payload = {"ok": False, "mode": args.mode, "error": str(exc)}
        if exc.session_id:
            error_payload["session_id"] = exc.session_id
        return emit(error_payload, exit_code=1)
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
