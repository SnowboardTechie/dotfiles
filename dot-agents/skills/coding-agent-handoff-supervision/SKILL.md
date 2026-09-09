---
name: coding-agent-handoff-supervision
description: Use for visible, ticket-backed coding-agent handoffs.
version: 2.0.0
author: Bryan Thompson + Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [coding-agents, handoff, supervision, claude, hermes, herdr]
    related_skills: [issue-work, pr-self-review, subscription-coding-worker-governance]
---

# Coding Agent Handoff Supervision

## Overview

Hand decision-complete implementation to one visible Claude worker, or to a
visible Hermes worker when Bryan explicitly selects it. Sol remains the pairing,
acceptance, publication, and live-verification authority. The worker produces a
candidate; Sol independently accepts it.

The workflow optimizes for one useful implementation turn and one bundled
correction, not a prolonged conversation. Herdr mechanics are owned by
`scripts/herdr_worker.py`; do not reconstruct its command choreography in chat.

## When to Use

Use for substantial repository work when all of these are true:

- one governing ticket or approved plan exists;
- goal, scope, exclusions, and architecture are decision-complete;
- acceptance is observable through tests, probes, or exact readback;
- edit and delivery permissions are explicit; and
- the work benefits from sustained repository reading or multiple coordinated
  edits.

Keep a `single-loop` change with the parent when it is one coherent edit/test
cycle and touches no security, persistence, migration, protocol, concurrency,
public-contract, or deployment boundary. An explicit same-run Claude request
overrides this right-sizing rule. Use `issue-work`'s router for ticket work.

Do not use this workflow for open architecture, live incident diagnosis,
voice-heavy writing, or exploratory research. Resolve those with Sol first.

## Role Boundary

Sol owns:

- user deliberation and material decisions;
- plan acceptance and risk calibration;
- independent diff inspection and finding disposition;
- commits, publication, deployment, and live readback.

The worker owns:

- repository inspection needed to execute the settled plan;
- test-first implementation and local checks;
- one bundled correction, plus one narrowly conditional second correction when
  `pr-self-review` permits it.

Do not spend a second Sol implementation session before handoff and then use
Claude only as reviewer. Do not use a second Claude session to review the first
by default; the Sol parent is already the independent acceptance context.

## Procedure

### 1. Bind one governing ticket

Reuse the ticket supplied by `issue-work`. Outside that umbrella, search the
project workspace and read plausible matches. If none governs the work, load
`issue-create`, obtain its normal approval, post one ticket, and read it back.
Never create a duplicate ticket or replace durable authority with a large prompt.

Complete when one verified ticket URL or approved plan path owns the outcome.

### 2. Brief authority, not implementation

The reachable artifact, not the prompt, is self-contained. The prompt contains
only:

- ticket or plan URL/path;
- implementation repository and worktree;
- authority boundaries;
- local commit, push, and PR/issue permissions as separate values; and
- a current blocker not already recorded in the artifact.

Do not restate steps, files, tests, requirements, or safeguards from a reachable
plan or ticket. If the worker cannot access it, make it reachable first; for a
true cross-machine handoff use `cross-machine-coding-agent-handoffs`.

Destructive and history-rewriting Git operations are absolute and not
approval-eligible: forbid `git reset`, `git clean`, checkout-discard operations,
rebase, amend, every other history rewrite, force-push, delete or overwrite any
local ref or branch, branch deletion, and update-ref deletion.

Visible workers are approval-gated, not sandbox-confined. Claude uses
`--permission-mode auto`; Hermes requires `approvals.mode: smart`, no
`HERMES_YOLO_MODE`, and no `--yolo`. Stop when hard confinement is required but
cannot be proved.

Complete when the worker can identify the artifact, worktree, and authority
boundary without a second copy of the plan.

### 3. Start through the deterministic helper

Require `HERDR_ENV=1`, the injected `HERDR_PANE_ID`, and compatible
`HERDR_BIN_PATH`. Visible work has no silent Agent View, print-mode, tmux, or
background fallback.

Use the helper from the canonical skill directory:

```sh
python3 scripts/herdr_worker.py start \
  --worktree "$WORKTREE" \
  --identity-file "$STATE_DIR/worker-identity.json" \
  --name "$AGENT_NAME" \
  --kind claude \
  --title "$TITLE"
```

For explicit Hermes selection, use `--kind hermes` after independently checking
its smart-approval prerequisites.

The helper checks Herdr compatibility, targets the injected caller pane, splits
without focus, starts the worker, computes Git identity, and atomically records:

- `worker_surface`;
- `worker_agent_name`;
- `worker_pane_id`;
- `worker_kind`;
- `worker_runtime_session_id`; and
- `worker_worktree_identity`.

For Claude it also runs the live capacity gate before pane creation. Any nonzero
capacity result stops before a provider turn. Do not hand-edit or reconstruct an
identity record. `start` exclusively reserves the identity path before any pane
side effect while holding a per-identity start lock. It refuses every
pre-existing record, including a closed one. If an interruption leaves
`starting` or `cleanup_required`, run `recover-start`; it either validates the
exact recorded worker into an active identity or closes recorded resources and
terminalizes the record. A pre-split pane inventory plus caller tab/workspace
identity closes the crash window before the returned pane ID is journaled. Use a
new state path for a separately authorized new worker.

Complete when the identity file validates one ready worker in the intended
worktree.

### 4. Submit one turn per Claude session

Put the short brief in a state-root file, then run `prompt` as a tracked bounded
background process so completion returns to the parent:

```sh
python3 scripts/herdr_worker.py prompt \
  --identity-file "$STATE_DIR/worker-identity.json" \
  --prompt-file "$STATE_DIR/worker-prompt.md" \
  --timeout-ms 7200000
```

`prompt` atomically:

1. acquires a Claude-turn lease keyed to the recorded worker runtime session;
2. rejects an overlapping turn in that same session, not unrelated agents;
3. performs a fresh provider-capacity check;
4. validates all six worker and Git identity fields;
5. submits exactly one prompt with Herdr `--wait`;
6. revalidates identity after settlement; and
7. returns compact start/end capacity and status data.

At most one Claude turn may be in flight **within each worker runtime session**.
Independent sessions may run concurrently in their own worktrees, including
when they share a subscription. Another agent working on another task is not a
handoff blocker. Capacity and exact worker/worktree identity checks still apply.
The helper derives its lock filename from `worker_runtime_session_id`; different
identity files for the same runtime session still share the lock. Idle retained
sessions do not own a lease. Process exit releases it, so no stale PID cleanup
or bypass is allowed.

If the worker blocks on a question or approval, use the helper's identity-checked
`read` operation, then ask Bryan. Never submit suggested input automatically.
Send only Bryan's approved input through `answer-blocked`, not `prompt`; it
requires recorded `blocked` state, acquires the same lease, reruns capacity,
requires recorded `blocked` state, captures `state_change_seq`, retains the
lease until a newer idle/done/blocked state exists, and revalidates all identity
fields. Use `--text` for a literal answer or `--keys` for an interactive choice
such as `down enter`.

Complete when the original worker settles and the helper returns a verified
status.

### 5. Treat completion as a claim

Inspect the real branch, diff, worktree, and worker report. Run targeted checks
needed to validate the implementation. Then follow `pr-self-review`:

- the Sol parent performs one integrated Standards, Spec, conditional Risk, and
  Ponytail review plus the acceptance-criteria sweep;
- all validated blockers are batched into one correction contract;
- correction returns to this same worker identity;
- the parent performs one complete rereview of the corrected candidate;
- one conditional second correction is allowed only for a newly introduced or
  newly exposed bounded implementation blocker; and
- there is never a third correction.

For security, persistence, migration, protocol, concurrency, public-contract, or
deployment changes, add one targeted Risk reviewer only after the parent gate has
stabilized the candidate. A candidate change invalidates that targeted review;
rerun it once against the corrected exact candidate.

Missing verification or an unresolved blocker means do not publish. A stop is
not permission to lower quality or switch providers.

Complete when the parent has independently accepted one exact candidate.

### 6. Release the pane promptly

Keep the pane only while the worker is active, blocked on a specific answer, or
has one identified same-session correction. Pending publication, merge, or live
verification is not a concrete next turn.

```sh
python3 scripts/herdr_worker.py close \
  --identity-file "$STATE_DIR/worker-identity.json"
```

The helper validates the recorded agent and pane, closes only that pane, verifies
both resources are absent, and marks the identity closed/non-resumable. It
journals `closing` before the pane mutation, so a lost acknowledgement or
readback failure resumes safely through the same `close` operation. Do not ask
for cleanup approval and never close the caller or an unrelated pane.

Complete when the recorded pane and agent are absent.

## Explicit Background-Only Route

Only an explicit same-run background-only request may use Claude Agent View.
Read `references/claude-agent-view.md`. It is a separate surface and cannot
resume a Herdr identity.

## Common Pitfalls

1. Handing off a single-loop edit whose startup cost exceeds the work.
2. Confusing per-session turn serialization with a global ban on concurrent Claude work.
3. Making the prompt a second plan.
4. Rechecking identity with improvised shell commands instead of the helper.
5. Treating worker tests, idle status, or prose as parent acceptance.
6. Starting a fresh worker for corrections instead of resuming the recorded one.
7. Running a generic fresh Claude reviewer after Sol already reviewed the work.
8. Leaving a settled pane open as a status marker.
9. Confusing correction allowance with provider capacity.

## Verification Checklist

- [ ] Work is substantial or Claude was explicitly selected
- [ ] One verified ticket or approved plan governs the handoff
- [ ] Brief contains locator, worktree, authority, and delivery permissions only
- [ ] Destructive/history-rewriting Git operations remain prohibited
- [ ] Visible path uses compatible injected Herdr without stealing focus
- [ ] Helper atomically persisted all six identity fields
- [ ] Claude capacity passed and the worker runtime session's turn lease was held
- [ ] No overlapping turn targeted the same session; unrelated sessions were not blocked
- [ ] Parent inspected and tested the actual candidate
- [ ] One integrated parent review and AC sweep completed
- [ ] Corrections stayed within the one-plus-one bound
- [ ] High-risk change received one targeted Risk review when required
- [ ] Pane closed as soon as the worker had no concrete next turn
- [ ] Publication and live state were verified separately

## References

- [Herdr helper operations](references/herdr-claude-handoff.md)
- [Design-preview promotion](references/design-preview-handoff.md)
- [Explicit background Agent View](references/claude-agent-view.md)