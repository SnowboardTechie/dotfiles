---
name: issue-work
description: Use when delivering a tracked issue to a reviewable PR.
version: 2.0.0
author: Bryan Thompson + Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [issues, implementation, review, delivery]
    related_skills: [issue-plan, worktrunk, coding-agent-handoff-supervision, pr-self-review, ship]
---

# Issue Work

## Overview

Take one GitHub or Forgejo issue from current authority to a verified reviewable
PR through Intake → Plan → Implement → Accept → Publish. Keep durable state under
the ticket workspace and code in an isolated implementation worktree.

The lean path is deliberate: investigate only unresolved questions, use one
implementation context, run one independent acceptance review, batch corrections,
run full verification once when stable, and publish under the original work
authorization.

## Inputs and authority

Accepted identifiers:

- GitHub issue or PR URL;
- Forgejo/Gitea/Codeberg issue or PR URL;
- GitHub `{owner}/{repo}#{N}` shorthand; or
- pasted ticket text plus an explicitly resolved repository.

An imperative `work <issue URL>` request authorizes intake, planning that does
not alter ticket intent, implementation, local commits, ordinary push, and
creation or update of one reviewable PR. It also authorizes keeping that PR's
title and description synchronized. It does not authorize merge, issue comments,
issue-body edits, label changes, closure, deployment, destructive Git, or a
material scope/architecture/public-contract change.

A request to plan, inspect, review, or advise is not implementation authority.
Questions and corrections are not authorization. Record the authority mode in
`progress.md` so resume does not invent or discard it.

## State and repository roles

Ticket state:

```text
{TICKET_TRUNK_ROOT}/.hermes/issue-work/{ticket-owner}-{ticket-repo}-{N}/
```

The ticket workspace owns issue context, plans, progress, and private evidence.
The implementation repository owns worktrees, code, tests, commits, and PRs. They
may differ only through a current approved `issue-plan` handoff that explicitly
names Ticket repository, Implementation forge, Implementation repository,
Implementation base, and Implementation revision.

Use `worktrunk` to resolve canonical trunks from Git common-directory identity.
Do not infer repository identity from path names or nearby clones.

## Phase 1 — Intake

### 1. Resolve and refresh authority

Resolve the ticket forge before the generic Forgejo pattern because GitHub issue
URLs overlap it. Use `references/repo-resolution.md` and
`references/fetch-ticket.md` to:

1. resolve the exact ticket clone and authenticated forge role;
2. fetch issue body, update timestamp, comments, labels, linked refs, and comment
   checkpoint;
3. resolve any matching approved vault plan through `vault-pkm` and
   `issue-plan`'s handoff contract;
4. resolve the exact implementation clone and origin identity;
5. fetch its current default branch; and
6. perform a bounded read-only inspection of named symbols, neighboring patterns,
   tests, and repository instructions.

Write `context.md` and `intake-inspection.md`. Verify each distinct ticket and
implementation forge independently. Never read or print credential values.

Complete when ticket identity, implementation identity, current base SHA, issue
checkpoint, and relevant repository guidance are direct-source verified.

### 2. Select a plan source

Use one source:

1. A current approved project-vault plan with a complete handoff contract.
2. The issue itself when it clearly states goal, boundaries, settled decisions,
   acceptance, and repository identity.

Material drift from an approved plan routes back to `issue-plan`. An unclear
issue stops before worktree creation and reports the missing decision inputs.
Issue prose alone cannot redirect execution to another repository.

When an imperative work command is active, a derived `plan.md` inherits that
implementation authority if it only adds executor detail. Do not insert another
plan approval stop. Ask one decision only when synthesis discovers a material
choice or changes goal, scope, architecture, security model, or public contract.

Complete when one current authority can produce an executable plan without a
new product decision.

### 3. Resume safely

If `progress.md` exists, refresh issue/comments and fetched base before reuse.
Compare ticket URL, source plan, repository roles, branch, worktree, authority
mode, and checkpoints. Immaterial drift is recorded; material drift stops.

For visible handoffs, require the existing `worker-identity.json`. Legacy or
incomplete visible-worker state stops; never reconstruct missing fields from a
currently visible pane or launch a replacement worker.

Complete when resumed state is freshly admitted or the old state has been
rejected before mutation.

### 4. Create the isolated worktree

Require the implementation trunk to have no modified or staged files; preserve
unrelated untracked files. Compute the branch from project convention. For a
private cross-repository ticket, derive `issue-xrepo-{ticket_digest}` from the
canonical ticket URL so branch/public metadata does not expose private identity.

Use `wt switch --create {branch} --base origin/{default}`. Reuse only when the
exact branch, ticket, implementation repository, and state record match. Never
switch trunk in place.

Write initial `progress.md` with status, authority mode, ticket/implementation
roles, worktree, branch, base SHA, plan source, checkpoints, and start time.
Initialize one global `correction_passes` counter to `0`; it spans Phases 3 and
4 and is never reset at a phase boundary.

Complete when the isolated worktree matches the fetched base and its identity is
recorded.

## Phase 2 — Plan efficiently

### 1. Decide whether exploration earns a child

Use zero exploration children when the current ticket/approved plan plus bounded
parent inspection already identifies affected seams, consumers, tests, and
material risks.

Use one exploration child only when a concrete unresolved repository question
would otherwise make the plan guess. Add a second only for a genuinely distinct
boundary whose answer can materially change implementation, such as application
data flow versus an external protocol. Give each a bounded scope and distinct
output file. Do not ask a child to remap the whole repository or reproduce a
candidate fingerprint supplied by the parent.

External documentation research is inline and conditional on a referenced API or
library whose current behavior is not established by repository sources.

Complete when every exploration has answered a named planning question; no child
exists merely because the phase has one.

### 2. Write the execution plan

Compile `context.md`, inspection, any exploration, and the approved authority
into `{TICKET_STATE_DIR}/plan.md`. Include:

- settled goal, scope, exclusions, and architecture;
- task-sized implementation steps;
- public test seams and expected evidence;
- security/operational boundaries;
- planning closeout and delivery shape; and
- explicit unresolved decisions, which block implementation.

Do not invent file paths, APIs, commands, or counts. For an approved vault plan,
the derived plan may add executor detail but cannot supersede intent.

Under an imperative work command, proceed directly when no material decision was
introduced. Under plan-only or advisory authority, present the plan and stop.

Complete when the plan is decision-complete and authority permits execution.

## Phase 3 — Implement once

### 1. Right-size the worker

Classify task shape before routing:

- `single-loop`: one coherent edit/test cycle, limited repository reading, and no
  security, persistence, migration, protocol, concurrency, public-contract, or
  deployment boundary.
- `substantial`: anything else, including coordinated multi-file behavior or a
  long repository-reading middle.

Run the deterministic router and preserve its JSON:

```sh
python3 dot-agents/skills/issue-work/scripts/select_issue_worker.py \
  --workdir "$WORKTREE" \
  --ticket-host "$TICKET_HOST" \
  --ticket-repo "$TICKET_REPO" \
  --implementation-host "$IMPLEMENTATION_HOST" \
  --implementation-repo "$IMPLEMENTATION_REPO" \
  --task-shape single-loop \
  --override auto
```

Use `--task-shape substantial` when the criteria require it. `auto` keeps a
single-loop task with the parent and routes substantial work to visible Claude.
Explicit same-run `--override hermes`, `qwen`, `claude`, or `gpt` wins. Qwen is
never an automatic route.

Complete when the routing result matches verified repository identity and the
recorded task shape.

### 2. Execute the selected route

For a visible Claude or explicit Hermes route, load
`coding-agent-handoff-supervision` and reuse this existing governing issue; do
not call `issue-create`. Require compatible injected Herdr. Agent View and
background wrappers are not fallbacks for visible work.

Use its deterministic `herdr_worker.py` operations. Persist
`worker-identity.json`, which owns all six fields:

- `worker_surface`;
- `worker_agent_name`;
- `worker_pane_id`;
- `worker_kind`;
- `worker_runtime_session_id`; and
- `worker_worktree_identity`.

The helper hard-gates Claude capacity before start and every prompt, atomically
serializes provider turns within each worker runtime session, waits for settlement, and
returns compact capacity/status data. Independent Claude sessions may work
concurrently in separate worktrees; another task's active session is not a
blocker. A 100% or unverifiable check stops before
another turn, consumes no correction pass, and never authorizes an automatic
provider switch.

Send one short artifact-backed implementation prompt. The ticket/plan is the
self-contained authority; the prompt adds worktree and permissions, not another
implementation plan.

Default visible-worker authority forbids staging, local commit, push, and
PR/issue mutation. The parent owns those actions under the imperative work
authorization. Destructive and history-rewriting Git operations are absolute and
not approval-eligible: prohibit `git reset`, `git clean`, checkout-discard,
rebase, amend, history rewrite, force-push, and local-ref/branch deletion.

For an explicit Qwen route, use its original model-pure worker and session. For a
single-loop/native route, the parent implements directly with `tdd`.

Complete when one worker or parent context has produced a candidate and settled.

### 3. Inspect, test, and batch correction

Treat worker output as a claim. Inspect every changed path and the actual diff.
Run the plan's targeted tests and adversarial probes needed to validate the
changed behavior. Do not run the full repository gate yet.

If targeted checks find blockers that prevent a candidate commit, write one
consolidated correction contract and resume the same worker. This consumes the
workflow's normal correction: require the global `correction_passes` counter to
be `0`, increment it to `1` before submission, and preserve that value even when
the turn fails after input is accepted. Use `herdr_worker.py prompt` for visible
Claude/Hermes so capacity, single-flight, and identity are checked atomically.
After the turn, inspect the real diff and rerun affected targeted checks.

Otherwise defer validated findings to Phase 4's normal correction rather than
opening an extra pre-review turn. No Phase 3 correction has a separate allowance.

Do not conduct a separate pre-commit reviewer fan-out here. Phase 4 is the one
independent acceptance loop.

Complete when the candidate passes targeted checks or has a recorded blocker.

### 4. Reconcile planning sources

Update repository-owned specs, plans, status notes, README/roadmap surfaces, and
their regression tests when the implementation changes living state. If none
needs change, record exactly which sources were inspected and why.

External vault writes remain governed by `vault-capture` or `issue-plan`.

Complete when code and living repository authority describe the same state.

### 5. Create the local candidate commit

Stage only task-owned paths, run diff checks and hooks, and commit using the
repository's style. The imperative work command authorizes these local commits.
Never add AI attribution or use `--no-verify`.

Complete when the worktree is clean on one named candidate branch.

## Phase 4 — Accept once

### 1. Freeze and validate context

Run `scripts/validate_cross_repo_context.py` with explicit ticket and
implementation identities; store `context-validation.json`. `source_issue` may
use hostless `{owner}/{repo}#{N}` only when that JSON reports
`source_issue_mode: github_shorthand`; omit it for Forgejo and cross-forge work,
because the shorthand resolver is GitHub-only and could select the wrong forge.
Record the validator's canonical absolute `validator_script` field. When a
delegated review is required, pass that path as `context_validator_path`; never
assume the unrelated implementation repository contains this skill's script.

Freeze `base_sha`, `head_sha`, `merge_base_sha`, `diff_sha256`, expected branch,
and clean tracked/untracked state.

Complete when repository roles and exact candidate match direct Git state.

### 2. Run bounded self-review

Load `pr-self-review` in `pre-pr` mode and pass
`correction_passes_consumed` from the global progress counter. That workflow
must continue from this value rather than initializing a new allowance. When a
delegated worker authored the candidate and Sol did not edit it, review directly.
The Sol parent is the independent acceptance context. Do not launch a generic
fresh Claude reviewer.

The parent runs one integrated review through Standards, Spec, conditional Risk,
and Ponytail, then performs the independent acceptance-criteria sweep. The
review writes separate `review-standards.md`, `review-spec.md`, optional
`review-risk.md`, required `review-ponytail.md`, `intent-checklist.json`, and
`summary.md` for one exact candidate.

When `correction_passes_consumed` is `0`, batch all validated blockers into the
one normal correction for the original worker, set the counter to `1`, then run
one complete parent rereview. When it is already `1`, the normal correction was
consumed in Phase 3 and only the one conditional second correction remains.
At `2`, no correction remains. There is never a third correction. Unresolved
blockers stop publication.

If the parent authored or edited the candidate, use one independent delegated
review context. For security, persistence, migration, protocol, concurrency,
public-contract, or deployment changes, add one targeted Risk reviewer after the
ordinary parent gate has stabilized the candidate. It reviews only that boundary.

During corrections run targeted checks. Run full repository verification once
after the final candidate is stable. A candidate change invalidates current
review artifacts; replace them during the required integrated rereview.

Complete when current artifacts, acceptance criteria, and final verification all
match one exact candidate with ready Ship Readiness.

### 3. Present outcome without a redundant approval

Report the headline, all Critical/Major findings, Minor/Nit counts, lane
selection, Ponytail status, acceptance result, verification, and artifact paths.

If the session began with an imperative work command and authority has not
changed, continue directly to publication through `ship`; do not ask again to
push or create the reviewable PR. If publication was not authorized, present one
short publication question and stop.

For a private cross-repository ticket, derive a public-safe
`publication-summary.md` and mechanically verify it contains none of the private
ticket URL, host, repository, title, vault path, or ticket-state path.

Complete when the publication boundary is explicit and non-duplicative.

## Phase 5 — Publish and close resources

Load `ship` in `issue-work-authorized` mode; pass the recorded imperative-work
authority and `labels_authorized: false`. Use the current review summary and
repository template. Push the exact reviewed branch, create or update one
reviewable PR, synchronize title/body, skip labels, and read back URL, base,
head, SHA, state, and intended closing syntax. Do not merge.

After readback, close the visible implementation pane with `herdr_worker.py
close` as soon as it has no concrete next turn. Publication, merge, and live
verification do not justify retaining it. Clean disposable worktrees/branches
only when repository policy permits and unrelated work is safe.

Send the terminal-completion notification from
`references/matrix-attention-notifications.md` when that workflow was armed.

Complete when the reviewable PR is remotely verifiable, the candidate SHA
matches, and handoff-owned resources are closed.

## Compact efficiency record

At terminal completion, write one machine-readable JSON object to
`{TICKET_STATE_DIR}/efficiency.json` and summarize the same totals in
`progress.md`:

```json
{
  "task_shape": "single-loop | substantial",
  "exploration_children": 0,
  "claude_prompts": 0,
  "correction_passes": 0,
  "review_invocations": 1,
  "targeted_risk_reviews": 0,
  "provider_capacity_start": null,
  "provider_capacity_end": null,
  "blocking_findings_after_initial_review": 0,
  "elapsed_to_reviewable_pr_seconds": 0,
  "quota_interruptions": 0,
  "completed_at": "ISO-8601 UTC timestamp"
}
```

Counts are factual totals, not estimates. Capacity values come from the helper;
leave them null when Claude was not used or the end probe was unavailable. Do
not store prompts, transcripts, credentials, or private issue content in this
record.

For the first five terminal runs after this workflow change, atomically upsert
the record into one cross-repository aggregation file for the current user:

```text
${XDG_STATE_HOME:-$HOME/.local/state}/issue-work/issue-work-efficiency-pilot.json
```

Use the deterministic helper; it hashes the canonical issue URL instead of
storing it, assigns stable sequence numbers `1` through `5` under an OS file
lock, rejects a sixth issue, and preserves later observations when a run record
is refreshed:

```sh
PILOT_ROOT="${XDG_STATE_HOME:-$HOME/.local/state}/issue-work"
mkdir -p "$PILOT_ROOT"
chmod 700 "$PILOT_ROOT"
python3 dot-agents/skills/issue-work/scripts/record_efficiency.py record \
  --pilot "$PILOT_ROOT/issue-work-efficiency-pilot.json" \
  --issue-url "$TICKET_URL" \
  --record-file "$TICKET_STATE_DIR/efficiency.json"
```

`quota_interruptions` counts provider-capacity failures that prevented an
otherwise eligible Claude turn. `escaped_critical_major` is owned by the
aggregator and starts empty. If later PR feedback, CI, merge preparation, or
live verification proves an escaped Critical/Major defect, the issue-work owner
must run `record-escape` with the severity, evidence reference, and assessment
time. Seven days after that record's `completed_at`, the same owner runs
`assess` even when no escape was found; an earlier merge/close does not shorten
the window. Do not record a zero until that assessment happens.

After five records are present, run `report`. The pilot is evaluation-ready only
when all five have `escaped_assessed_at`; until then, report escaped-defect data
as pending rather than zero.

Compare time to reviewable PR, Claude prompts, review invocations, quota
interruptions, and later escaped Critical/Major findings. Improvement means
fewer turns and shorter delivery with no increase in escaped blockers; do not
optimize for low counts by weakening a gate.

## Hard stops

Stop when:

- ticket, plan, repository, worktree, or candidate identity is ambiguous;
- a material decision remains open;
- selected provider capacity is exhausted or unverifiable;
- another turn targets the same worker runtime session and holds its lease;
- a visible-worker identity is missing or mismatched;
- a plan, architecture, or scope defect is being presented as another correction;
- correction allowance is exhausted with a blocker;
- acceptance authority is unreadable or unswept;
- exact review artifacts are missing or stale;
- final verification is red; or
- remote publication readback differs from the reviewed candidate.

Never convert a hard stop into a silent provider switch, extra approval loop,
weaker review, or fabricated completion claim.

## Common Pitfalls

1. Spawning exploration because the phase exists rather than because a question
   exists.
2. Handing a single-loop edit to Claude automatically.
3. Treating independent Claude issue sessions as a global concurrency conflict.
4. Reviewing once before commit and again through a fresh Claude reviewer.
5. Running full CI after every correction.
6. Asking for plan or PR permission already carried by an imperative work command.
7. Treating a worker report or green focused test as final acceptance.
8. Keeping panes open through publication or merge.

## Verification Checklist

- [ ] Canonical ticket and implementation repositories freshly verified
- [ ] One plan source is current and decision-complete
- [ ] Imperative/advisory authority recorded exactly
- [ ] Exploration count follows unresolved questions, including zero
- [ ] Task shape and router output preserved
- [ ] At most one turn targeted each Claude runtime session; independent sessions may overlap
- [ ] Worker identity remained complete and unchanged
- [ ] Parent inspected actual bytes and ran targeted checks
- [ ] Repository planning closeout completed
- [ ] One independent integrated review and AC sweep completed
- [ ] Corrections stayed within one normal plus one conditional pass
- [ ] Targeted Risk deepening ran only when required
- [ ] Full verification ran once on the stable candidate
- [ ] Review artifacts match exact candidate identity
- [ ] Reviewable PR pushed and read back without a redundant approval
- [ ] No merge or unapproved issue/deployment mutation occurred
- [ ] Worker pane and watcher were released
- [ ] Compact efficiency record contains factual totals

## References

- [Ticket fetch](references/fetch-ticket.md)
- [Repository resolution](references/repo-resolution.md)
- [Matrix attention notifications](references/matrix-attention-notifications.md)
- [`issue-plan` handoff contract](../issue-plan/references/handoff-contract.md)