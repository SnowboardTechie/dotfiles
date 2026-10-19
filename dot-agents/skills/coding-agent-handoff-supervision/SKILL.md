---
name: coding-agent-handoff-supervision
description: Use for visible CLI or Matrix coding-agent handoffs.
version: 2.3.0
author: Bryan Thompson + Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [coding-agents, handoff, supervision, claude, hermes, herdr]
    related_skills: [issue-work, pr-self-review, subscription-coding-worker-governance]
---

# Coding Agent Handoff Supervision

## Overview

Sol orchestrates; Claude implements. Hand decision-complete implementation to a
visible Claude worker, including small changes, fixtures, harnesses, tooling,
and repairs discovered during verification. Task size and worker startup cost
are not exceptions. Use a visible Hermes worker for requested read-only work;
simple questions stay with Sol unless Bryan asks for a worker. Only Bryan's
explicit selection changes the implementation role or runtime. Sol owns scope,
dependencies, handoffs, supervision, independent acceptance, authorized Git
integration/publication, and live verification. A worker produces a candidate,
not an accepted deliverable.

The workflow optimizes for one useful implementation turn and one bundled
correction, not a prolonged conversation. Herdr mechanics are owned by
`scripts/herdr_worker.py`; do not reconstruct its command choreography in chat.

## Select the execution surface first

The helper procedure below is the CLI transport, not a universal prerequisite
for visible workers. Select the transport before checking its environment.

In a Matrix conversation with the native `herdr` toolset available, load
`herdr-gateway:workflow` and use `herdr_start`, `herdr_wait`, `herdr_read`,
`herdr_prompt`, `herdr_status` and `herdr_close` for the request-bound worker.
These plugin tools may be progressively deferred rather than directly declared:
when `tool_describe` and `tool_call` are available, describe the six exact names,
then invoke them through `tool_call(calls=[{name, arguments}])`. Describing does
not make them first-class provider tools. Absence from the initial schema array
is not proof of unavailability; an actual discovery or native-policy refusal is.
Keep the same authorization, approval, identity and cleanup checks through the
bridge. Correlate a nested `tool_call` / `herdr_start` result with its owned pane,
not merely the outer recorded tool name.
No injected caller pane is expected in Matrix. Do not run the CLI helper's
`HERDR_ENV`/`HERDR_PANE_ID` gate there and do not offer a background fallback
because those values are absent. Do not fabricate context bindings, caller-pane
variables or authorization to make either transport work. The native gateway
enforces the actual room/user/thread, permitted project and runtime policy.

For a natural request such as "Have a worker take a look at the dotfiles README",
resolve the project directory and configured preset from established context and
the authorized gateway configuration; do not ask the user to supply internal
task IDs, preset names or paths already known. For a bounded read-only review,
the user's request is the brief authority: narrow the brief to inspection and
reporting, prohibit edits/publication, and start the worker. Ask a question only
when that changes the work or a required project/permission is genuinely unknown.
Implementation still needs the governing ticket/approved plan and the role,
acceptance, correction, capacity and cleanup rules below. Claude Opus/xhigh is
the implementation default; Hermes/high is the read-only-worker default.
Bryan's explicit runtime selection overrides this
policy. Do not expand a simple question into an audit: keep the brief and
verification proportional to the requested answer.

If native tools are unavailable or return a refusal, report that exact transport
or policy blocker. Do not substitute a CLI caller-pane requirement or silently
change execution surfaces. In an interactive CLI, continue with the deterministic
helper procedure below and retain its injected-pane prerequisites.

## When to Use

Use for repository implementation of any size when all of these are true:

- one governing ticket or approved plan exists;
- goal, scope, exclusions, and architecture are decision-complete;
- acceptance is observable through tests, probes, or exact readback;
- edit and delivery permissions are explicit.

Delegate a `single-loop` change too; right-size its brief and verification, not
its implementation owner. For ticket work, use `issue-work`'s router with the
standing Claude selection. Do not turn a fixture or tooling repair into parent
implementation by calling it verification.

Do not use this workflow for open architecture, live incident diagnosis,
voice-heavy writing, or exploratory research. Resolve those with Sol first.

## Delivery boundary and substantive handback

Default ordinary implementation handoffs to supervised delivery. "Hand it to
Claude" does not authorize dropping parent acceptance/publication or inventing
a separate future review invocation. Use `session-handoff` status-only or
fire-and-forget only when Bryan explicitly chooses that boundary. Preserve
installation, download, activation and other real safety gates without turning
every mechanical prerequisite into a separate user decision.

Require a durable handback path in the governing plan/ticket. Before settling,
the worker writes candidate identity, changes, actual checks/results, unfinished
criteria, blockers, exact approval requests in dependency order, and next owner.
Read the report and the real candidate before reporting completion or answering
what Claude said. A lifecycle `done` event is not a handback. If the report is
absent, retrieve the final message using the supervised helper's identity-checked
`read`, or request the missing report from the same worker within its capacity
and turn boundary. Never substitute a runbook for an unread final message while
implying that message was read.

Disposition remaining items as parent verification/publication, worker
correction, genuinely new user permission, or later optional scope. Finish
parent-owned prerequisites before requesting a downstream approval, and bundle
independent permissions. An unmet assigned criterion cannot become complete
merely because the worker stopped.

For bounded semantic omission checks, TypeSafe/Jev may compare criteria,
handback and evidence through separate typed questions. Read its current API,
use authorized credentials and minimal nonsecret state, and validate any flags
yourself. It supplements source review and real tests, never replaces the
acceptance owner; unavailable access does not block ordinary review.

## Role Boundary

Sol owns:

- user deliberation and material decisions;
- plan acceptance, dependency scheduling, bounded handoffs, and risk calibration;
- worker supervision and recovery within the existing authority;
- independent diff inspection and finding disposition;
- commits, publication, deployment, and live readback.

The worker owns:

- repository inspection needed to execute the settled plan;
- test-first implementation and local checks, including fixtures, test harnesses,
  implementation probes, and tooling repairs;
- one bundled correction, plus one narrowly conditional second correction when
  `pr-self-review` permits it.

Sol may inspect source, run existing checks, maintain plans/review artifacts and
perform authorized integration. Sustained prerequisite investigation that needs
new code or a repaired harness belongs in a bounded Claude handoff; do not build
it in the coordinator while the implementer waits. A worker's failure, capacity
limit or closed session does not transfer implementation ownership to Sol.
Recover the permitted worker route or report its concrete blocker.

Do not spend a Sol implementation session before handoff and then use Claude
only as reviewer. Do not use a second Claude session to review the first
by default outside Bryan's SGG closeout; the Sol parent is already the independent
pre-publication acceptance context. For SGG issue implementation, `issue-work`
owns the required sequence: parent acceptance, verified draft PR, fresh Claude
final PR self-review, parent disposition, and cleanup. That post-publication final
gate is required, not an optional redundant pre-publication reviewer.

## Procedure

### Continuation and decision boundaries

When Bryan selects a worker, settles the plan, and says to proceed, execute the
handoff rather than returning a prompt for him to carry. Verify worker delivery;
only a real transport/capacity blocker or an explicit prompt-only request
justifies stopping at text. A planning artifact's earlier execution-disabled
status must not erase a later explicit implementation instruction.

For Bryan's SGG issue-implementation handoffs, "proceed" executes the established
complete closeout through the draft PR and fresh Claude final self-review, unless
he explicitly sets an earlier stopping boundary. Record that delivery authority
and continue under `issue-work`; do not return "done" at worker settlement or a
pushed branch. Plan-only and prompt-only requests remain non-execution requests.

A scope boundary stops applying an unapproved change, not ordinary investigation
of its remedies. Before escalating a blocked candidate, inspect upstream fixes,
compatibility requirements and the actual affected call paths; perform isolated
probes when already authorized. Preserve the candidate and return a concrete,
evidence-backed decision only where implementation would cross the boundary.
Do not ask permission merely to investigate the next recovery step.

Keep an authorized multi-issue outcome moving: dispatch ready independent work
within the governing concurrency limit, collect handbacks, accept prerequisites,
and advance their consumers. Routine in-scope implementation and fixture repairs
remain Claude's work under the existing completion authority, not another
"may I proceed?" gate. Preserve actual correction counts and quality stops; ask
Bryan only for a genuinely new decision, permission or applicable safety gate.

When Bryan interrupts with a direct question about the work or agent behavior,
answer that question before further tools. Frustration is not authorization to
cross an explicit scope boundary, and additional activity is not a substitute
for answering.

### 1. Bind one governing ticket or approved plan

Reuse the ticket supplied by `issue-work` or the decision-complete approved plan
already governing the request. Outside those routes, search the project
workspace and read plausible matches. Only if neither a ticket nor an adequate
approved plan governs the work, load `issue-create`, obtain its normal approval,
post one ticket, and read it back. Never create a duplicate or require a ticket
solely for transport; never replace durable authority with a large prompt.

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

Treat the artifact's scope as closed. A worker may inspect broadly enough to
implement safely, but it edits only what the settled acceptance criteria
require. Unexpected adjacent defects are reported to Sol; the worker does not
add characterization tests, production fixes, trackers, or "helpful" cleanup
for them. In particular, "cover every existing call site" means apply the
selected mechanism at every site, not exhaustively discover every latent
behavior behind those calls unless the governing artifact explicitly requires
conformance exhaustiveness. The parent dispositions observations against the
original contract before authorizing any correction.

Destructive and history-rewriting Git operations are absolute and not
approval-eligible: forbid `git reset`, `git clean`, checkout-discard operations,
rebase, amend, every other history rewrite, force-push, delete or overwrite any
local ref or branch, branch deletion, and update-ref deletion.

Visible workers are approval-gated, not sandbox-confined. Claude uses
`--permission-mode auto`; Hermes requires `approvals.mode: smart`, no
`HERMES_YOLO_MODE`, and no `--yolo`. Stop when hard confinement is required but
cannot be proved.

When Claude is selected, use `claude-opus-5-5` and `xhigh` effort; do not
downgrade effort for simple or documentation-only work. Lightweight
implementation still belongs to Claude; Hermes is the read-only-worker route
unless Bryan explicitly selects otherwise. Escalate to
`--claude-effort max` only when the work is simultaneously narrowly scoped,
security-critical, and expensive enough that another correction cycle would be
especially costly. Broad or decision-incomplete work does not qualify for
`max`; narrow the scope or settle the decisions first.

Starting a worker in the inspected worktree created for Bryan's authorized task
already authorizes Claude's ordinary **Yes, I trust this folder** startup step.
Do not ask Bryan again. The helper accepts only that recognizable trust prompt
for the exact worktree and recorded startup pane, then verifies readiness.
This is not blanket permission for unrelated paths, login prompts, destructive
commands, broader permission modes, or new task decisions.

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

`--claude-effort` defaults to `xhigh`. Add `--claude-effort max` only when all
three escalation conditions above hold.

When an explicitly approved installation is misclassified, distinguish missing
authorization from missing runtime configuration. Never retry a refused action
through another tool or infer permission from frustration. Investigate the
supported consent/configuration path. Claude ignores `autoMode` in project-local
settings; standalone `auto-mode config --settings FILE` can read a file that the
interactive runtime ignores. Do not claim that test proves runtime activation.
For a parent-reviewed, user-authorized source/action-scoped exception, `start
--claude-settings FILE` accepts only `{"autoMode":{"allow":[...]}}` and passes
its contents as inline CLI JSON for that worker, retaining auto mode and recording
the config hash. Preserve the existing effective allow rules; change no hard or
soft deny rules, global settings, or unrelated permission controls. Keep the
exception in scratch, never in tracked instructions or the worker's own edits.
If the existing runtime cannot consume CLI overrides, collect its substantive
handback, close it normally, and launch the continuation with the same approved
model/effort and governing artifact. Verify startup arguments/hash and the next
normal permission gate before claiming recovery. A still-refused action remains
blocked; do not escalate to a broader mode or another execution route.

For read-only work or explicit Hermes selection, use `--kind hermes` after independently checking
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

A tracked process handle proves only that the helper started, not that Herdr
accepted the prompt. Until acknowledgement is observed, report delivery as
unconfirmed. A nonzero exit or rejected submission requires immediate inspection
and authorized recovery; do not end with a delivery claim or an apology. Inspect
the exact worker and the helper's documented recovery path before declaring a
blocker. A verified `done` worker can accept its same-session correction through
`prompt`; do not replace it merely because its previous turn completed. Never
retry an uncertain submission until its delivery state is resolved, bypass
identity/capacity/lease checks, or expand permissions to make recovery succeed.

At most one Claude turn may be in flight **within each worker runtime session**.
Independent sessions may run concurrently in their own worktrees, including
when they share a subscription. Another agent working on another task is not a
handoff blocker. Capacity and exact worker/worktree identity checks still apply.
The helper derives its lock filename from `worker_runtime_session_id`; different
identity files for the same runtime session still share the lock. Idle retained
sessions do not own a lease. Process exit releases it, so no stale PID cleanup
or bypass is allowed.

If the worker blocks on a question or approval, use the helper's identity-checked
`read` operation and compare the request with the governing plan. Answer an
already-settled question from that approved authority; ask Bryan only for a new
decision or permission. Never treat worker-suggested input as approval, infer a
new security approval from general task authorization, or weaken an explicit
gate. Send only input covered by Bryan's approval through `answer-blocked`, not
`prompt`; it
requires recorded `blocked` state, acquires the same lease, reruns capacity,
requires recorded `blocked` state, captures `state_change_seq`, retains the
lease until a newer idle/done/blocked state exists, and revalidates all identity
fields. Use `--text` for a literal answer or `--keys` for an interactive choice
such as `down enter`.

An `answer-blocked` process handle is not a confirmed approval. Report delivery
only after its result verifies accepted input. If it returns `recorded worker
is not blocked`, inspect the live state before any retry: the user may have
answered in the visible pane or the prompt may have timed out. Do not invent
which actor resolved it. For a worker still running after a lost answer race,
reattach a read-only identity-checked wait to the existing state-change sequence;
never send a duplicate prompt merely to regain completion notification.

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

1. Keeping small edits, fixture/harness repairs, or implementation tooling with Sol to save worker startup cost.
2. Confusing per-session turn serialization with a global ban on concurrent Claude work.
3. Making the prompt a second plan.
4. Rechecking identity with improvised shell commands instead of the helper.
5. Treating worker tests, idle status, or prose as parent acceptance.
6. Letting a worker-discovered adjacent defect expand the ticket or candidate without a new user decision.
7. Using "all call sites" as permission for an exhaustive domain audit rather than bounded application of the selected mechanism.
8. Starting a fresh worker for corrections instead of resuming the recorded one.
9. Duplicating Sol's pre-publication acceptance through a generic fresh reviewer.
   Bryan's required post-draft-PR SGG Claude final review is not this pitfall.
10. Leaving a settled pane open as a status marker.
11. Confusing correction allowance with provider capacity.

## Verification Checklist

- [ ] Claude owns implementation regardless of task size; any alternate owner has Bryan's explicit selection
- [ ] One verified ticket or approved plan governs the handoff
- [ ] Brief contains locator, worktree, authority, and delivery permissions only
- [ ] Destructive/history-rewriting Git operations remain prohibited
- [ ] Visible path uses compatible injected Herdr without stealing focus
- [ ] Helper atomically persisted all six identity fields
- [ ] Claude capacity passed and the worker runtime session's turn lease was held
- [ ] No overlapping turn targeted the same session; unrelated sessions were not blocked
- [ ] Delivery claims have acknowledgement evidence, not merely a background process handle
- [ ] Rejected or uncertain submissions were inspected and recovered without bypass or duplicate delivery
- [ ] Parent read a substantive handback, dispositioned remaining gates in order, and tested the actual candidate
- [ ] One integrated parent review and AC sweep completed
- [ ] Corrections stayed within the one-plus-one bound
- [ ] High-risk change received one targeted Risk review when required
- [ ] Pane closed as soon as the worker had no concrete next turn
- [ ] Publication and live state were verified separately

## References

- [Herdr helper operations](references/herdr-claude-handoff.md)
- [Design-preview promotion](references/design-preview-handoff.md)
- [Explicit background Agent View](references/claude-agent-view.md)