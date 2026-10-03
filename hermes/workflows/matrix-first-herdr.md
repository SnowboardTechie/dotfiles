# Matrix-first, request-bound Herdr work

## Authority and decisions

Bryan approved this implementation in the setup conversation on 2026-10-02,
including a visible Claude implementation worker. This document is the governing
approved-scope handoff, not permission to publish publicly or activate unreviewed
software.

- Matrix rooms own the ongoing conversation, decisions, authorization and final
  synthesis. Room-first continuity; explicit task threads when useful.
- No standing project coordinators and no `Matrix Channel Coordinators` workspace.
- Open visible, task-specific Herdr workers for authorized work; retain saved
  sessions when useful but close panels once no concrete next turn remains.
- Request-bound authority: carry agreed work to its stopping point, then wait.
  Nested delegation is permitted only when the task contract authorizes it.
- The Matrix gateway and Herdr server already run on the same machine. The old
  worker helper's injected-caller-pane requirement is a helper assumption, not
  a Herdr server limitation. Never fabricate HERDR_ENV or a caller pane.
- Keep existing services, E2EE credentials/store, default model, soul, memory,
  unrelated Claude settings, scheduled jobs, and deferred maintenance unchanged.
- Default remains gpt-6.1-sol / openai-codex. Jev is a future structured-decision
  tuning candidate, not part of this implementation.
- Timed resets no longer run in installed Hermes core; do not add a reset plugin
  or rely on midnight boundaries. Preserve existing room and thread routing.

## Existing implementation and adaptation choice

Adapt the MIT-licensed plugin at:
https://github.com/steven-terrana/hermes-herdr-plugin
Pinned base: c33aa2eb2e27087134eb03c9b807eea44e61b9a5 (version 0.1.0).
Retain Steven Terrana's MIT notice and record upstream provenance and divergence.

Read-only review downloaded the complete Python source to a scratch snapshot.
The baseline's 14 tests pass; installed Hermes plugin doctor admits five tools.
Those checks are not live dispatch verification or security approval.

Confirmed problems to remove:
- Claude defaults to --dangerously-skip-permissions.
- Empty settings restore defaults, so documented empty bridge/agent-args settings
  do not actually disable them.
- Read/relay resolve arbitrary untracked agents and lack origin ownership.
- Ledger lacks runtime-session/Git identity fencing, atomic crash-safe writes,
  verified cleanup, and robust concurrent-start handling.
- Prompt submission alone is reported as working; no verified settlement watch.

Other surveyed work does not replace this adaptation: Herdres is Telegram-first;
pikujs/herdr-agent-gateway has unsafe focus/pane-inventory selection fallbacks;
herdr-auto-reconcile is a wake mechanism rather than control, and its catalog
repository/pin currently return 404. No public issues/PRs existed in the exact
chosen plugin repository at the research cutoff. No upstream contact authorized.

## Implementation deliverable

### Approved guarded Hermes admission amendment

On resumption, Bryan approved the narrowly scoped amendment in
[`matrix-first-herdr-admission.md`](matrix-first-herdr-admission.md) after a
fresh authorized startup probe. For Hermes only, intended launch policy is
prechecked before layout creation; actual runtime/profile/approval/session proof
is completed after bounded owned startup and before any task brief. All other
requirements and approval boundaries remain in force. The original worker's
two correction passes remain consumed; the amendment has a separately authorized
implementation worker and bounded acceptance scope.

Bryan subsequently approved explicit per-worker YOLO control from the private
Matrix conversation, governed by
[`matrix-first-herdr-yolo.md`](matrix-first-herdr-yolo.md). Smart approvals remain
the startup default. A native user command may change one owned Hermes worker's
session mode; model task text is not the privileged-control interface. This
supersedes a blanket prohibition on deliberately user-selected YOLO, not the
runtime-identity, ownership, verification or activation boundaries below.

Build a self-contained, shareable native Hermes plugin under
`hermes/plugins/herdr-gateway/`, adapting the existing plugin architecture rather
than adding a network bridge or patching Hermes/Herdr core. Add a focused public
handler/CLI-boundary test suite and operator documentation/security assessment.
Personal room IDs, user IDs, paths and model policy belong in local configuration,
not the shared package. Keep configuration examples clearly illustrative.

The plugin connects locally to the existing Herdr service via explicit endpoint
selection, with no listener, TCP auto-bridge, daemon, automatic installs/updates,
service restart, fabricated caller identity or focus-dependent targeting.

Required behavior:
1. Disabled/default-deny until the operator explicitly configures supported
   origins and permitted project directories. Use trusted runtime conversation
   context, not model-supplied origin fields. Capture platform, chat, user,
   thread/session routing as appropriate; fail closed for missing, ambiguous,
   unsupported or stale context. Do not let process-env fallback grant an
   otherwise unbound gateway request authority.
2. All worker operations are origin-scoped. Expose owned workstreams only;
   never read/control/adopt arbitrary existing user/agent panes. Bind each owned
   record to the exact endpoint, agent, pane, runtime session, directory and Git
   identity where applicable; revalidate before input, reading or cleanup.
3. Spawn only task-owned layout with --no-focus and an explicit directory.
   Validate inputs, endpoint compatibility, permission/model preset and capacity
   before creating resources. Never select a pane from focus or last inventory
   position. Preserve unrelated panes/workspaces and working trees.
4. Permission-respecting agent launches. No skip-permissions/yolo flags, shell
   interpolation, or model-controlled arbitrary launch arguments. Keep model and
   effort configurable by operator presets. Claude capacity checks and exact
   model/session identity must not silently fall back. Hermes smart-approval
   prerequisites must be checked; its observed unknown/launch_pending readiness
   must be a honest blocker, not a raw pane-run bypass or wider outage claim.
5. Reserve ownership before mutation and use locked, owner-only, atomic local
   records. Handle concurrent starts, partial failures, lost acknowledgements and
   corrupt state without resetting ownership to empty or blindly respawning.
6. Track submitted versus actually-started work, blocked, settled, timed-out and
   unknown states truthfully. Provide a bounded wait/settlement operation so an
   authorized request can supervise its worker through completion. A synchronous
   wait in the originating request is acceptable; do not add perpetual wake-ups
   or automatic task generation. Timeouts preserve recoverable ownership and
   never trigger duplicate prompts. Serialize turns per runtime worker session.
7. Read and follow-up only exact owned workers. Surface approvals/questions to
   the parent; do not automatically answer arbitrary dialogs. Do not promote
   model-supplied answers into human approval. Ordinary inspected-folder trust
   may follow the existing authorized-worker convention only when verified.
8. Close only the recorded owned worker after identity verification, read back
   absence, preserve useful result/session locators, and make retries safe.
9. Bundle concise workflow guidance: Matrix owns authority/context; task-specific
   workers carry bounded briefs; parent independently accepts results; saved
   history is not a simultaneously attached Matrix/terminal conversation.
10. No credentials/auth stores, transcript directory scans, environment dumps,
    broad network access, new dependencies or installers. Bounded pane output
    can contain secrets; document that residual same-user risk and avoid logging
    raw prompts/output unnecessarily. Behavioral request authorization is not a
    kernel sandbox or proof that a user approved arbitrary model text.

## Acceptance seam and checks

The public native plugin handlers and its Herdr subprocess protocol are the
acceptance seam. Tests must exercise registered public handlers with real
filesystem state and a fake external Herdr executable/transport; mocks belong
only at the true Herdr/runtime-context boundary, not internal algorithms.
Work test-first in vertical slices and capture actual failures/passes.

Cover default denial; origin/thread/user cross-scope attempts; unbound/stale env
context; permission-bypass attempts; wrong endpoint/agent/runtime/Git identity;
corrupt/unsafe state; concurrent starts/turns; incompatible or missing server;
capacity refusal before layout mutation; non-ready/blocked startup; partial start
and lost acknowledgements; actual prompt activity and timeout; and owned-only,
idempotent cleanup. Do not manufacture live API/model evidence from fixtures.

Run stdlib tests with host Python and Hermes's installed `plugins doctor --ci`.
Inspect the exact manifest/API against installed Hermes source. No dependency
installation is authorized. The parent will independently inspect/test the
candidate, conduct one targeted security review and perform an authorized live
canary before calling the workflow ready. Missing live evidence remains pending.

## Worker scope and permissions

Worker edits ONLY:
- hermes/plugins/herdr-gateway/**
- hermes/test_herdr_gateway_plugin.py

The parent owns installer/manifest wiring, configuration, existing shared skill
changes, broader docs, review, deployment and publication. Report adjacent gaps;
do not fix them. The worker must not alter this governing contract.

Worker: visible Claude, exact claude-opus-5-5, xhigh effort, auto permissions,
no fallback. One implementation writer; no nested agents in this handoff.
No worker commits, pushes, external messages, PR/issue edits, installation,
plugin activation, runtime update, service restart, settings/credentials/memory/
soul changes. Never reset/clean/discard/rebase/amend/force-push/delete refs or
otherwise rewrite Git history. Preserve dot-claude/settings.json unchanged.

Parent delivery: commit exact task-owned paths to dotfiles main and push origin
main per repository policy after acceptance; verify remote commit. Public
upstream submission/release is separately authorized, not implied by that push.
Activation requires a detailed security review first; gateway restart and
external messaging/canary delivery require specific approval. No silent restart.

## Resumption checkpoint

Canonical repository: /Users/bryan/code/dotfiles-workspace/repos/dotfiles
Initial branch/main HEAD: 498aa31; only initial modification is
`dot-claude/settings.json`, explicitly excluded from this task.
Installed Hermes source: /Users/bryan/.hermes/hermes-agent at
f42f579cf8bac4918ac9599bece71618afadd846, clean at cutoff.
Herdr 0.9.3, default session, compatible endpoint/private protocol 22.
Upstream review snapshot:
/Users/bryan/.hermes/cache/scratch/herdr-plugin-review-3ytii_6e
Visible worker helper:
dot-agents/skills/coding-agent-handoff-supervision/scripts/herdr_worker.py
Worker identity and prompt checkpoint:
/Users/bryan/.hermes/cache/scratch/matrix-herdr-implementation/worker-identity.json
/Users/bryan/.hermes/cache/scratch/matrix-herdr-implementation/worker-prompt.md

After compaction, reload relevant skills, read this file and worker identity,
recheck Git/worker identity, and consume the original worker completion. Do not
start a duplicate worker or claim completion from a compacted summary. Review
and activation are unfinished until independently verified.
