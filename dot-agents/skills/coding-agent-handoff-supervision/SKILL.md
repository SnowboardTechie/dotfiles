---
name: coding-agent-handoff-supervision
description: Use for visible, ticket-backed Claude or Hermes handoffs.
version: 1.4.0
author: Bryan Thompson + Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [coding-agents, handoff, supervision, claude, hermes, herdr, design-preview]
    related_skills: [issue-create, cross-machine-coding-agent-handoffs, subscription-coding-worker-governance, claude-code]
---

# Coding Agent Handoff Supervision

## Overview

Hand approved implementation to a visible Claude or explicitly selected Hermes
worker while the parent remains responsible for supervision, review, and
delivery. Every implementation handoff is backed by one governing ticket. In
Herdr, launch the worker in a sibling pane without changing the active window,
workspace, tab, or pane, and keep a completion watcher attached to the parent.

## When to Use

Use whenever implementation is handed to Claude or another Hermes instance, and
for Claude review, research tied to a working tree, or an iterative coding-agent
session. Claude is the default implementation worker. Hermes is selected only
by an explicit same-run request. Herdr is the default handoff surface whenever
it is available; do not silently substitute print mode, a standalone tmux
session, or a background process merely because it is simpler for the parent.

The visible route requires Herdr for both Claude and Hermes. If Herdr is
unavailable, stop; never convert a requested visible handoff into a background
worker. Claude Agent View and the subscription wrapper remain available only
after an explicit same-run background-only request. Do not use this workflow for
a self-contained reasoning subtask whose result needs no visible terminal,
branch inspection, or independent verification.

### Handoff boundary: Sol pairs, Claude executes, Sol accepts

When the interactive parent is Sol, preserve the role split deliberately. Sol
owns pairing, deliberation, planning, unresolved architecture or product
choices, risk calibration, and final acceptance. Claude implements after the
work is decision-complete; Sol then independently reviews and accepts the exact
candidate. In short: Claude produces the candidate; Sol independently accepts
it.

Cross the boundary only when one governing ticket or approved plan exists, goal
and scope are settled, no unresolved answer could materially change the
architecture, acceptance is observable through tests or readback, and mutation
permissions are explicit. Keep live incident diagnosis, voice-heavy ADR or
communication work, and open-ended research with Sol until those decisions are
settled. A genuinely tiny single-loop edit may also stay with the parent when
handoff overhead exceeds the work.

Once this boundary is satisfied, do not spend a second Sol-backed implementation
session on the same middle phase by default and then ask Claude only to review.
Use Claude as the implementation worker; the Sol parent remains the acceptance,
publication, deployment, and live-verification authority.

## Procedure

### 1. Bind one governing ticket

Before composing a worker prompt, read the active repository instructions and
resolve the project workspace they define. That workspace may be a private
planning repository distinct from the implementation repository.

- If the caller already supplies an existing governing issue, fetch and read it
  back from its forge. Reuse it when its goal and acceptance boundary govern the
  requested implementation. Do not create a duplicate implementation ticket.
- Otherwise search open issues in the project workspace with the forge-native
  authenticated client. Use a few specific title/problem/outcome terms, inspect
  each plausible result, and reuse a suitable governing issue. A loose keyword
  match or incidental mention is not authority.
- If no suitable issue exists, load `issue-create` and target the project
  workspace. Its normal flow must draft a concise implementation ticket, show
  it for approval, run the duplicate check, post it, and read back the exact
  created URL. Do not launch a worker until the posted ticket and metadata have
  been verified.

If the workspace cannot be resolved, candidate issues cannot be read, posting
is not approved, or issue readback fails, stop. Never fall back to an oversized
prompt as a substitute for durable ticket authority.

**Complete when:** one verified ticket URL governs the handoff and duplicate
prevention has completed.

### 2. Brief the outcome, not an imagined implementation

Keep the implementation handoff short. State:

- the ticket URL as intent authority;
- the exact implementation repository, base, and worktree;
- the authority boundaries, including what the worker may edit or execute;
- the delivery permissions as explicit independent decisions: whether local
  commit creation is allowed, whether push is allowed, and whether PR or issue
  mutation is allowed. Never infer one permission from another.

When the worker can read an authoritative plan or ticket, make the handoff
artifact, not the prompt, self-contained. The prompt needs only the plan or
ticket path/URL, implementation repository/worktree, execution scope or
authority boundaries, delivery permissions, and any current blocker that is not
already recorded there. Do not restate requirements, steps, files, tests, or
safeguards from a reachable artifact. A fresh agent lacks chat context; the
artifact is how it receives that context without a second, drifting plan in the
prompt.

If the worker cannot read the artifact, make it reachable first. For a genuinely
cross-machine handoff, follow `cross-machine-coding-agent-handoffs`; inline only
the minimum context that still cannot be retrieved after that synchronization.

Destructive and history-rewriting Git operations are absolute and not
approval-eligible in every worker-facing brief: the worker must never run
`git reset`, `git clean`, a checkout-discard operation, `rebase`,
`commit --amend`, any other history rewrite, or `force-push`; delete or overwrite
any local ref or branch, including branch deletion and `git update-ref -d`
update-ref deletion, is likewise forbidden. Keep this separate from the explicit
approval decisions for staging, ordinary local commits, ordinary pushes,
PR/issue mutation, and publication.

Tell the worker to read the ticket and repository guidance, trace consumers,
research current tool behavior, choose files, and determine implementation and
verification. Do not duplicate the implementation plan or complete context in
the prompt, and do not invent hard constraints, file lists, commands,
architecture, or exclusions merely to make the brief look complete.

The worker is approval-gated, not sandbox-confined. Do not claim filesystem,
network, credential, or Git sandbox confinement. If the requested task requires
hard confinement and the selected runtime cannot prove it, stop. Likewise stop
when Claude auto mode is unavailable or Hermes smart approvals are disabled; do
not relax the approval mode to make the handoff start.

**Complete when:** the worker can identify the approved result, source context,
and publication boundary without being handed an imagined implementation.

### 3. Choose the visibility path

For every visible Claude or Hermes work handoff, require the injected Herdr
environment. Split the exact caller pane to the right with `--no-focus`, then
start and prompt the selected worker without changing the active window,
workspace, tab, or pane. Start a tracked watcher; focus the worker only when
Bryan explicitly asks to see it. If Herdr, the exact caller pane, or a compatible
injected client is unavailable, stop rather than silently changing worker kind,
surface, or visibility.

Read `references/herdr-claude-handoff.md` for the exact discovery, non-focusing
dispatch, monitoring, continuation, failure, and cleanup sequence.

Only after an explicit background-only request may Claude use a named Agent View
session instead. Read `references/claude-agent-view.md` for that separate
surface. It is not a fallback for visible work and its identity cannot satisfy
the Herdr correction-resume contract below.

### 4. Persist the complete visible-worker identity

After `herdr agent start` and before the first prompt, write every field below to
`progress.md` and pass the same values to any review/correction workflow:

- `worker_surface: herdr`;
- `worker_agent_name`: the stable Herdr control target;
- `worker_pane_id`: the exact pane returned by the split;
- `worker_kind`: `claude` or `hermes`;
- `worker_runtime_session_id`: `.result.agent.agent_session.value` from
  `herdr agent get`;
- `worker_worktree_identity`: a compact JSON object containing the canonical Git
  worktree root, canonical Git common directory, and current branch.

All six fields are independent identity evidence. Do not overload an agent name
as a runtime session ID, omit the pane, or reduce worktree identity to cwd text.
Fetch `herdr agent get {worker_agent_name}` and recompute the Git identity; only
persist after every value matches the intended launch. A legacy or incomplete
record cannot be upgraded from whatever happens to be visible now: stop, mark
the handoff blocked, and never launch a duplicate worker.

**Complete when:** the complete persisted identity resolves to one working Herdr
agent and a promised completion notification has a real finite watcher.

### 5. For design-driven handoffs, promote one direction

Exploration pages may contain intentionally competing variants. Once Bryan
selects one, create a dedicated preview containing only that direction. Retain
useful adaptive controls, remove competing designs, and verify the page through
the network path Bryan actually uses.

Give the worker the dedicated link as design intent, not a pixel-perfect
contract. Read `references/design-preview-handoff.md` for the promotion and
reachability checklist.

**Complete when:** the worker receives one reachable approved direction rather
than a gallery it must interpret.

### 6. Treat worker completion as a claim

After the worker finishes:

1. Inspect the actual branch, commits, diff, and working tree.
2. Disposition its questions and recommendations against the approved concept.
3. Freeze the exact candidate and run the authored-candidate review workflow:
   Standards and Spec, conditional Risk, then mandatory Ponytail. Prefer
   `pr-self-review`; use `code-review` directly only when no supported pre-PR
   entry exists. The reviewer context must be independent of the worker, and a
   parent ad-hoc pass or correction in the same worker session does not count.
4. If any correction changes the candidate, invalidate every review artifact and
   rerun the complete gate against the new identity.
5. Independently run the relevant validation and focused runtime probes.
6. Verify publication and remote readback separately.
7. Activate or reload the live system only after accepting the candidate.
8. Read back the live target before declaring completion.

A `done` or `idle` status proves only that the worker settled. It does not prove
the implementation is acceptable. Missing or stale Ponytail evidence means the
handoff review is incomplete and the candidate must not be described as ready.

**Complete when:** every acceptance criterion is independently verified against
the candidate and, where applicable, the live target.

### 7. Continue the same worker

Before and after every follow-up prompt, fetch the existing Herdr agent and
compare `worker_surface`, `worker_agent_name`, `worker_pane_id`, `worker_kind`,
`worker_runtime_session_id`, and `worker_worktree_identity` with the persisted
record. Any missing field, lookup failure, changed value, or worktree mismatch
stops the handoff. Send the follow-up only through the matching
`worker_agent_name`; do not launch another row or pane and do not switch between
Claude and Hermes. Text
already visible in a worker's prompt box may be an automatic suggestion; never
submit it without the user's direction.

**Complete when:** the original session identity returns to `working` after the
follow-up, with no duplicate worker created.

### 8. Clean up after acceptance

After merge, publication readback, and live verification:

- stop or close only the worker session or pane created by this handoff;
- remove its disposable worktree and merged feature branch when appropriate;
- stop disposable preview servers;
- preserve unrelated local edits;
- finish with the canonical branch clean and current.

Do not close a foreground Herdr pane while Bryan may still be using it.

## Common Pitfalls

1. **Splitting Herdr's globally focused pane.** Target the injected
   `HERDR_PANE_ID`; Bryan may be viewing another tab while the handoff is built.
2. **Stealing Bryan's focus.** Pane creation, startup, prompting, and updates
   must preserve his active window, workspace, tab, and pane. Run `agent focus`
   only after an explicit request to see that worker.
3. **Calling visibility monitoring.** A visible worker still needs a tracked
   `herdr agent wait` or equivalent watcher when the parent promises follow-up.
4. **Resolving Herdr through shell `PATH`.** Foreground and background shells
   may select an older client. Require the pane-injected `HERDR_BIN_PATH`, gate
   on `compatible: yes`, and use that inherited absolute path for every command.
5. **Launching without a ticket.** Reuse the existing governing issue or finish
   `issue-create` through approval, post, and read back before dispatch.
6. **Over-constraining the worker.** Point to the ticket and authority boundary,
   not a duplicated implementation plan.
7. **Making the prompt a second plan.** A reachable plan or ticket owns the
   requirements, steps, files, tests, and safeguards. The prompt points to it
   and adds only execution scope, delivery permissions, and current blockers.
8. **Starting a duplicate for corrections.** Compare all six persisted identity
   fields and continue only the original Herdr agent.
9. **Treating suggested prompt text as authorization.** Submit only user- or
   parent-authored instructions.
10. **Trusting worker-reported tests or pushes.** Independently inspect and verify.
11. **Cleaning before checking for unrelated edits.** Preserve user work and close
   only resources created by the handoff.

## Verification Checklist

- [ ] Existing governing issue reused, or `issue-create` approved, posted, and read back
- [ ] Ticket targets the project workspace and duplicate prevention completed
- [ ] Brief states ticket URL, implementation repository/worktree, authority boundaries, and delivery permissions
- [ ] Reachable plan/ticket is the self-contained artifact; prompt does not restate its steps, files, tests, requirements, or safeguards
- [ ] Prompt does not duplicate the implementation plan or complete context
- [ ] Worker kind is Claude by default or Hermes by explicit same-run request
- [ ] Visible work uses Herdr; unavailable Herdr stops rather than falling back
- [ ] Exact caller pane targeted and new pane ID parsed from Herdr JSON
- [ ] All six visible-worker identity fields persisted and passed distinctly
- [ ] Legacy/incomplete identity state fails closed without duplicate launch
- [ ] Claude uses `auto` permission mode; Hermes uses smart approvals without yolo
- [ ] Local commit, push, and PR/issue permissions are each explicit
- [ ] Destructive/history-rewriting Git operations remain absolutely prohibited
- [ ] Active window, workspace, tab, and pane preserved unless focus was requested
- [ ] Tracked watcher uses the verified Herdr client and a finite timeout
- [ ] Follow-ups preserve the original session
- [ ] Exact candidate independently reviewed through Standards, Spec, conditional Risk, and mandatory Ponytail
- [ ] Every correction invalidated stale review artifacts and triggered a complete rereview
- [ ] Candidate independently tested
- [ ] Publication and live state read back separately
- [ ] Only handoff-owned resources cleaned up after acceptance
