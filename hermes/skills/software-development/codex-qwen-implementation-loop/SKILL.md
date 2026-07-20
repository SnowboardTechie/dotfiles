---
name: codex-qwen-implementation-loop
description: Use when Codex delegates planned work to local Qwen.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [codex, qwen, local-model, implementation, review, testing, orchestration]
    related_skills: [issue-work, plan, test-driven-development, systematic-debugging, requesting-code-review, codex-claude-implementation-loop]
---

# Codex–Qwen Implementation Loop

## Overview

Keep authority and conversational context with the GPT/Codex-backed Hermes parent while a locally hosted Qwen Coder worker executes an approved issue-work plan.

```text
Codex plans → local Qwen implements/tests → Codex reviews/retests
                    ↑                              │
                    └──── actionable fixes ────────┘
```

This is an implementation engine for planned issue work. It is not a global rule that prevents GPT from implementing directly outside `issue-work` or after an explicit worker override.

## When to Use

Use this skill when:

- `issue-work` has an approved, self-contained `plan.md`;
- the repository is outside the Simpler Grants Gov allowlist, or Bryan explicitly selected Qwen for this run;
- no explicit worker override selected GPT or Claude;
- the GPT Hermes parent will independently inspect and test the result.

Do not use it for:

- ad hoc implementation outside `issue-work`, unless Bryan explicitly requests Qwen;
- planning-only, research, or review-only work;
- Simpler Grants Gov issue-work, which uses `codex-claude-implementation-loop`;
- concurrent editing of the same worktree;
- a plan that requires secrets or external side effects the worker must not access.

## Invariants

1. **Parent authority.** GPT/Codex owns the plan, acceptance decision, engineering review, independent test gate, commits, and publication.
2. **Local inference only.** The worker pins `custom:local-qwen`, `qwen3.6:35b-a3b-coding-nvfp4`, and `http://127.0.0.1:11434/v1` in an isolated Hermes home.
3. **No cloud fallback or inherited secrets.** Compression and title generation are disabled or pinned to the same loopback route, the worker home rejects credential stores, and the child environment carries only allowlisted toolchain settings rather than tokens, API keys, or parent session variables.
4. **Explicit context handoff.** Qwen receives the repository, repository instructions, approved plan, initial status, and later review contracts. It does not rely on the parent conversation or memory database.
5. **Enforced local boundary.** The macOS sandbox permits outbound network access only to loopback Ollama port `11434`, blocks writes outside the repository/runtime/cache paths, blocks writes to the Git common directory, and denies reads from known credential stores. Qwen must not stage, commit, push, open a PR, post, deploy, or rewrite Git state.
6. **Sequential edits.** Wait for Qwen to exit before the parent edits or launches another worker in the same worktree.
7. **Bounded corrections.** Allow at most two retained-session revision passes unless Bryan explicitly extends the bound.
8. **Repository proof.** Qwen's JSON is a work report. The parent verifies the actual diff and reruns every required check.
9. **Fail closed.** Missing local model, unexpected model metadata, invalid JSON, missing session ID, unexplained changes, or failed independent checks blocks completion.
10. **Clean implementation baseline.** The initial `implement` command refuses modified, staged, or untracked work. Retained `revise` commands accept the worker's existing uncommitted diff.

## Worker Isolation

The wrapper manages a dedicated runtime home at:

```text
~/.hermes/local-qwen-worker
```

Override only for testing with `HERMES_QWEN_WORKER_HOME`. The wrapper atomically installs a mode-`600` local-only `config.yaml`, rejects persistent credential files, stores repository-bound retained worker sessions in that home, enables only Hermes `terminal` and `file` toolsets, passes only ordinary toolchain/runtime environment keys, and points Claude/Codex configuration variables at empty worker-owned directories. `sandbox-exec` restricts network access to `127.0.0.1:11434`, blocks Git metadata writes, limits filesystem writes, and denies common credential stores. A plan whose tests genuinely require credentials or any other network endpoint must stop for the parent rather than broadening this environment implicitly.

This is defense in depth rather than a separate macOS account or VM. The read denylist covers known credential stores but is not a complete confidentiality boundary for every user-readable file. Keep the plan bounded, inspect the diff, and do not pass secrets.

## Prerequisite Check

Locate the script through the skill path returned by `skill_view`, then run:

```bash
python3 <skill-dir>/scripts/qwen_worker.py check
```

The check must report:

- `provider: custom:local-qwen`;
- the exact Qwen model tag;
- the loopback base URL;
- a secured worker home and config path;
- the model installed in the local Ollama tag inventory.
- the `/usr/bin/sandbox-exec` enforcement path.

Stop if the check fails. Do not switch to OpenRouter, OpenAI, Claude, or another remote provider on the run's behalf.

## Phase 1 — Parent Contract

Before invoking Qwen:

1. Inspect the repository, relevant symbols, tests, manifests, and project instructions.
2. Require a clean, unstaged implementation worktree. Revisions may start from the retained worker's uncommitted diff but must also remain unstaged.
3. Write an approved `plan.md` containing goals, non-goals, acceptance criteria, exact scope, edge cases, test-first steps, and targeted plus broader verification commands.
4. Include every relevant memory-derived fact explicitly in the plan. Do not expect the worker to read the parent session or memory.

**Complete when:** a worker with only the repository and plan can implement without guessing.

## Phase 2 — Qwen Implements

Run from the issue worktree:

```bash
python3 <skill-dir>/scripts/qwen_worker.py implement \
  --workdir "$PWD" \
  --plan /absolute/path/to/plan.md
```

Save the complete normalized envelope in the issue-work state directory, for example:

```text
{state-dir}/qwen-implementation.json
```

Record its `session_id` in `progress.md` as `worker_session_id` alongside `implementation_loop: codex-qwen-implementation-loop`. Immediately compare the repository status and diff with the baseline. Every changed path must be planned or explicitly justified.

A zero exit code means Hermes used the exact recorded Qwen model and returned contract-valid JSON. It does not mean the implementation passed parent review.

## Phase 3 — Parent Reviews and Retests

The GPT/Codex parent performs two separate passes over the actual repository:

1. **Contract pass:** trace every acceptance criterion and changed path to the approved plan.
2. **Engineering pass:** review correctness, security, privacy, simplicity, maintainability, and test quality independently of acceptance traceability.

Then rerun the plan's targeted checks and appropriate broader suite, lint, type checking, or build. Distinguish Qwen-reported commands from commands the parent actually ran.

- **Clean diff and green checks:** accept the implementation state.
- **Concrete implementation findings:** enter the revision loop.
- **Plan defect, ambiguity, destructive conflict, or external blocker:** stop for Bryan instead of asking Qwen to guess.

## Revision Loop

Write a self-contained review file with each blocking finding's severity, path/location, observed behavior, expected behavior, evidence, and required correction. Resume the exact worker session:

```bash
python3 <skill-dir>/scripts/qwen_worker.py revise \
  --workdir "$PWD" \
  --session-id <qwen-session-id> \
  --review /absolute/path/to/codex-review.md
```

Save each envelope as `{state-dir}/qwen-revision-{pass}.json`. After every pass, inspect the full final diff and rerun the complete parent gate. Do not review only the files Qwen reports.

Maximum: two revision passes. If the second revision still fails, preserve the evidence and ask Bryan rather than starting another model or an unbounded loop.

## Worker Output

The wrapper prints one normalized JSON object:

```json
{
  "ok": true,
  "mode": "implement",
  "provider": "custom:local-qwen",
  "model": "qwen3.6:35b-a3b-coding-nvfp4",
  "base_url": "http://127.0.0.1:11434/v1",
  "session_id": "...",
  "worker_result": {
    "status": "completed",
    "summary": "...",
    "files_changed": [],
    "tests": [],
    "plan_deviations": [],
    "blockers": [],
    "notes": []
  },
  "hermes_metadata": {
    "model": "qwen3.6:35b-a3b-coding-nvfp4",
    "tool_call_count": 0
  }
}
```

Revision results replace `plan_deviations` with `findings_addressed` and `unresolved_findings`.

## Common Pitfalls

1. **Making Qwen the global implementation default.** Route to it only from approved `issue-work` or an explicit user request. GPT remains free to implement ad hoc work.
2. **Routing SGG to Qwen accidentally.** Simpler Grants Gov issue-work defaults to the Claude exception; use Qwen there only after Bryan explicitly selects it for the current run.
3. **Trusting the report.** Read the diff and rerun tests; structured output is not proof.
4. **Starting a fresh revision.** Preserve and resume `worker_session_id`.
5. **Passing chat history.** Pass a self-contained plan and review contracts instead.
6. **Concurrent writes.** Parent and worker never edit one worktree at the same time.
7. **Silent cloud fallback.** A local failure stops the run. Do not bypass the wrapper with the default Hermes profile or another provider.
8. **Treating the sandbox as a separate account.** It enforces write, network, Git metadata, and known-credential boundaries, but is not a VM-level confidentiality boundary for every user-readable path.
9. **Infinite correction loops.** Two revisions, then user escalation.
10. **Using a session from another worktree.** Retained sessions are bound to the resolved repository root and Git common directory; a mismatch fails before inference.

## Verification Checklist

- [ ] Invocation came from approved `issue-work` or an explicit Qwen request
- [ ] Repository was outside the SGG Claude allowlist, or Bryan explicitly selected Qwen for this run
- [ ] `qwen_worker.py check` passed
- [ ] Approved plan was self-contained and contained relevant parent context
- [ ] Initial repository status was recorded
- [ ] Exact local provider and model were recorded in the worker envelope
- [ ] Qwen session ID was retained for revisions
- [ ] Every changed path was planned or justified
- [ ] Parent completed distinct contract and engineering review passes
- [ ] Parent independently reran required checks
- [ ] Correction count stayed within two revisions
- [ ] No stage, commit, push, PR, deployment, or other publication was attributed to Qwen
