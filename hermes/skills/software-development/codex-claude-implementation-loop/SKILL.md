---
name: codex-claude-implementation-loop
description: "Use when a Codex-backed Hermes parent should plan and gate code changes while Claude Code implements, runs the first tests, and revises from Codex feedback using a subscription-backed CLI session."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [codex, claude, implementation, review, testing, subscription, orchestration]
    related_skills: [plan, test-driven-development, requesting-code-review, claude-code, codex]
---

# Codex–Claude Implementation Loop

## Overview

Keep authority with the Codex-backed Hermes parent while using Claude Code as a subscription-backed implementation worker.

**Ownership:** Codex plans, reviews, independently tests, and decides whether work is complete. Claude implements, runs the first test pass, and revises its work when Codex returns concrete findings.

```text
Codex plans → Claude implements/tests → Codex reviews/retests
                    ↑                         │
                    └──── actionable fixes ──┘
```

The loop is sequential: never let Codex and Claude edit the same working tree concurrently.

## When to Use

Use this skill when:

- The active Hermes parent uses an OpenAI Codex subscription model.
- A non-trivial coding task is ready for implementation.
- The user asks for Codex planning with Claude implementation.
- Independent cross-model review is valuable before reporting completion.

Do not use for:

- Planning-only requests.
- Read-only research or explanation.
- Tiny edits where process overhead exceeds risk, unless the user explicitly requests the loop.
- Repositories with unresolved destructive operations or secrets that Claude must not access.

## Invariants

1. **Codex owns the plan and final verdict.** Claude never declares the overall task complete.
2. **Repository state is authoritative.** Treat Claude's summary as a lead; verify files and tests directly.
3. **Subscription only.** The worker refuses to run when `ANTHROPIC_API_KEY` is present and never uses `--bare`.
4. **No publication.** Claude must not commit, push, open PRs, post comments, or publish artifacts.
5. **Preserve user work.** Snapshot the initial status and never overwrite, discard, stage, or clean unrelated changes.
6. **Bounded loop.** Allow at most two revision passes after the initial implementation unless the user explicitly extends it.
7. **Fail closed.** Authentication failure, invalid JSON, missing session ID, unexplained file changes, or unverified tests blocks completion.

## Prerequisites

Before planning, verify:

```bash
claude --version
claude auth status --text
```

The login method must be a Claude subscription account such as Pro, Max, Team, or Enterprise. If `ANTHROPIC_API_KEY` is set, stop and tell the user the worker would risk API billing.

Locate this skill's worker through the loaded skill path. The normal user-local location is:

```text
~/.hermes/skills/software-development/codex-claude-implementation-loop/scripts/claude_worker.py
```

Use the actual path reported by `skill_view` if the skill is installed elsewhere.

## Phase 1 — Codex Plans

### 1. Establish the baseline

From the repository root, inspect:

```bash
git status --short
git branch --show-current
git diff --stat
git diff
```

Record all pre-existing changed and untracked paths. Do not ask Claude to modify those paths unless the task explicitly requires it and the user changes are understood.

**Completion criterion:** the parent can distinguish pre-existing work from changes expected by the plan.

### 2. Inspect before designing

Read project context and trace relevant symbols, tests, manifests, and neighboring conventions. Do not make Claude rediscover requirements that Codex can state precisely.

**Completion criterion:** every proposed file and API has been observed in the repository; no invented symbols or dependencies remain in the plan.

### 3. Write an implementation contract

Create a temporary plan file outside the repository or under an already-ignored `.hermes/plans/` directory. Include:

- Goal and non-goals
- Acceptance criteria
- Exact files or components in scope
- Required behavior and edge cases
- Test-first steps where practical
- Exact targeted and broader test commands
- Project constraints from `AGENTS.md`, `CLAUDE.md`, or equivalent
- Explicit prohibition on commit, push, reset, clean, and unrelated refactors

Do not include secrets. Do not rely on conversation history: Claude receives only the plan, repository, and its own project context.

**Completion criterion:** a competent implementer with no parent-chat context could execute the plan without guessing.

## Phase 2 — Claude Implements and Tests

Run the worker from the repository root:

```bash
python3 <skill-dir>/scripts/claude_worker.py implement \
  --workdir "$PWD" \
  --plan /absolute/path/to/plan.md \
  --model sonnet
```

Use `--model opus` only when the user requests it or the implementation is unusually architecture- or security-sensitive. Sonnet is the routine default to conserve subscription capacity.

The worker starts Claude Code in print mode with editing tools, structured output, a bounded turn count, and explicit prohibitions against Git publication/history changes. It loads project/local Claude settings while excluding user-level plugins and hooks so personal Claude extensions do not create repository artifacts or consume worker turns. It returns a normalized JSON envelope containing `session_id` and `worker_result`.

After Claude returns:

1. Save the `session_id`; revisions must resume this session.
2. Read `worker_result.status`, but do not trust it as the final verdict.
3. If Claude reports `blocked` or `failed`, inspect the blocker. Codex either repairs the plan, asks the user, or stops.
4. Compare `git status --short` with the baseline immediately.
5. Stop if Claude touched unrelated pre-existing work or performed an unexplained broad change.

**Completion criterion:** Claude produced a parseable result with a session ID, and every changed path is either planned or explicitly explained.

## Phase 3 — Codex Reviews and Retests

Codex now performs an independent gate. Do not delegate this gate back to Claude.

### 1. Review the implementation

Inspect the complete diff and relevant files. Check:

- Every acceptance criterion is implemented.
- Behavior matches the plan rather than merely Claude's summary.
- Error paths, boundaries, and security implications are handled.
- Tests assert behavior and would catch a regression.
- No unrelated refactor, generated debris, secret, or debug output appeared.
- Existing user changes remain intact.

### 2. Run tests independently

Run the targeted tests from the plan, then the appropriate broader suite, linter, type checker, or build. Distinguish:

- tests Claude reported,
- tests Codex actually ran,
- pre-existing failures,
- new failures caused by the implementation,
- live/manual checks still outstanding.

**Completion criterion:** Codex has fresh local output for every required automated check and has reviewed every changed file.

### 3. Decide

- **Pass:** proceed to Final Report.
- **Fixable findings:** write a review file and enter the Revision Loop.
- **Ambiguous requirements, destructive conflict, or external blocker:** stop and ask the user.

## Revision Loop

Write concise findings to a temporary Markdown or JSON file. Every blocking finding must contain:

- severity,
- file and location,
- observed behavior,
- expected behavior,
- evidence such as a failing command or diff excerpt,
- required correction without prescribing unnecessary refactors.

Resume the same Claude session:

```bash
python3 <skill-dir>/scripts/claude_worker.py revise \
  --workdir "$PWD" \
  --session-id <session-id> \
  --review /absolute/path/to/codex-review.md \
  --model sonnet
```

After each revision, repeat the entire Codex review and independent test gate. Do not review only the files Claude says it changed.

Maximum: two revision passes. After the second failed gate, report the unresolved findings to the user with concrete evidence and ask how to proceed.

**Completion criterion:** either Codex passes the complete final state or the user receives a bounded escalation instead of an endless agent loop.

## Final Report

Only Codex reports completion. Include:

- What was implemented
- Files changed
- Claude implementation/test summary
- Codex review verdict
- Tests Codex independently ran and their actual outcomes
- Any manual/live checks still outstanding
- Remaining risks or follow-ups

Do not imply commit, push, PR creation, deployment, or publication unless those actions were explicitly requested and verified.

## Worker Output Contract

The worker prints one JSON object. Important fields:

```json
{
  "ok": true,
  "mode": "implement",
  "model": "sonnet",
  "session_id": "...",
  "worker_result": {
    "status": "completed",
    "summary": "...",
    "files_changed": [],
    "tests": [],
    "plan_deviations": [],
    "blockers": [],
    "notes": []
  }
}
```

A shell exit code of zero means Claude ran and produced schema-valid output. It does not mean Codex approved the implementation.

## Common Pitfalls

1. **Inverting ownership.** Claude implements; Codex plans and gates. Never ask Claude to approve itself.
2. **Starting a fresh revision session.** Use `--resume`; otherwise Claude loses implementation context.
3. **Trusting reported tests.** Codex reruns them independently.
4. **Passing chat history instead of a contract.** Give Claude a self-contained plan with acceptance criteria.
5. **Using `--bare`.** It disables subscription OAuth and can force API-key authentication.
6. **Allowing Git publication.** The worker prohibits commit/push, but Codex must still inspect history and status if behavior looks suspicious.
7. **Infinite ping-pong.** Two revision passes, then user escalation.
8. **Parallel edits in one tree.** Wait for Claude to exit before Codex edits or launches another worker.
9. **Mistaking structured output for proof.** Git state and fresh command output are proof.
10. **Loading user-level Claude plugins.** Personal hooks can consume turns or write helper artifacts into the repository. The wrapper intentionally disables user plugins, uses only project/local settings, redirects runtime caches outside the repository, and disables slash-command skills; do not remove that isolation without testing it.
11. **Treating overload as an implementation failure.** Claude may return HTTP 429/529 before doing work. The wrapper retries transient API failures once by default; if both attempts fail, preserve repository state and report the provider outage rather than changing the plan.

## Verification Checklist

- [ ] Codex inspected the repository and wrote the plan
- [ ] Initial dirty state was recorded and preserved
- [ ] Claude authentication was subscription-backed and no Anthropic API key was active
- [ ] Claude implemented and ran the first tests
- [ ] Claude session ID was retained for revisions
- [ ] Codex reviewed every changed file
- [ ] Codex independently reran required checks
- [ ] Any findings were returned with evidence
- [ ] Revision count stayed within the bound
- [ ] Final report distinguishes Claude claims, Codex checks, and remaining manual validation
- [ ] No commit, push, reset, clean, PR, deployment, or publication occurred without explicit authorization
