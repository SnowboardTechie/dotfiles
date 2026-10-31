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

The Hermes parent orchestrates; a Claude worker implements. Hand decision-complete implementation to a
visible Claude worker, including small changes, fixtures, harnesses, tooling,
and repairs discovered during verification. Task size and worker startup cost
are not exceptions. Use a visible Hermes worker for requested read-only work;
simple questions stay with the parent unless Bryan asks for a worker. Only Bryan's
explicit selection changes the implementation role or runtime. The parent owns scope,
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
acceptance, correction, capacity and cleanup rules below. Claude Opus/medium is
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
voice-heavy writing, or exploratory research. Resolve those in the parent conversation first.

## Delivery boundary and substantive handback

Default ordinary implementation handoffs to supervised delivery. "Hand it to
Claude" does not authorize dropping parent acceptance/publication or inventing
a separate future review invocation. Use `session-handoff` status-only or
fire-and-forget only when Bryan explicitly chooses that boundary. Preserve
installation, download, activation and other real safety gates without turning
every mechanical prerequisite into a separate user decision.

Require a durable handback path in the governing plan/ticket. Before settling,
the worker writes candidate identity, changes, actual checks/results, unfinished
criteria, blockers, exact approval requests in dependency order, next owner, and
one `Divergence:` line: how the result differs from the task as given (another
approach, changed scope, a new agreement), or `Divergence: None`. Put that line
in every contract's handback list. Check it against the diff and the contract
rather than recording it; an unstated difference the diff shows is a finding.
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

The parent owns:

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

The parent may inspect source, run existing checks, maintain plans/review artifacts and
perform authorized integration. Sustained prerequisite investigation that needs
new code or a repaired harness belongs in a bounded Claude handoff; do not build
it in the coordinator while the implementer waits. A worker's failure, capacity
limit or closed session does not transfer implementation ownership to the parent.
Recover the permitted worker route or report its concrete blocker.

Do not spend a parent implementation session before handoff and then use Claude
only as reviewer. Do not use a second Claude session to review the first
by default outside Bryan's SGG closeout; the parent is already the independent
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
require. Unexpected adjacent defects are reported to the parent; the worker does not
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

When Claude is selected, use `claude-opus-5-5` at `medium` effort, for
implementers and reviewers alike (Bryan, 2026-10-23). The coordinator's own
effort setting does not carry over to workers. Lightweight implementation still
belongs to Claude; Hermes is the read-only-worker route unless Bryan explicitly
selects otherwise. Use a higher `--claude-effort` only when Bryan asks for it.

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

Hermes tool shells may not inherit the CLI's Herdr variables, so an empty
`env | grep HERDR` there does not prove the session is outside Herdr. Before
reporting a transport blocker, find this session's own Hermes process by walking
the tool shell's ancestry (`p=$$; while [ $p -gt 1 ]; do ps -o command= -p $p;
p=$(ps -o ppid= -p $p); done`), read its `HERDR_*` values with
`ps eww -o command= -p PID`, and export them. Never pick the process by matching
cwd: several Hermes sessions often share a project cwd, and their panes belong to
other conversations. An ancestry ending at `hermes gateway run` does NOT prove the
session has no caller pane: with the Claude direct-SDK provider, a CLI session in a
Herdr pane runs its tools under the gateway, so the walk never reaches the CLI
(Bryan corrected this repeatedly, 2026-10-28). Identify the session's own CLI
process instead: find this conversation's session in `~/.hermes/state.db`
(`select id, source, started_at from sessions where id in (select session_id from
messages where content like '%<a unique phrase from this conversation>%')`); a
`cli` source means a CLI session. Match its `started_at` to the one Hermes process
with `HERDR_PANE_ID` in its environment whose `ps -o lstart=` agrees within a
second or two, and export that process's `HERDR_*` values. Only a gateway-sourced
session (Matrix and similar) has no caller pane: use the native `herdr_*` tools from
"Select the execution surface first". If they refuse too, report the exact
refusal and the two ways to unblock it (relaunch from a Herdr pane in the
project, or authorize the conversation for gateway workers). Check the transport
before writing the contract so the blocker surfaces early; the worktree and
contract stay useful for the resumed session.
Background `terminal` processes do not inherit foreground exports: put the
`export` inside every background `prompt` command, or the helper refuses
before sending.

Use the helper from the canonical skill directory:

```sh
python3 scripts/herdr_worker.py start \
  --worktree "$WORKTREE" \
  --identity-file "$STATE_DIR/worker-identity.json" \
  --name "$AGENT_NAME" \
  --kind claude \
  --title "$TITLE"
```

`--claude-effort` defaults to `medium`. Pass a higher value only when Bryan asks
for one.

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
capacity result stops before a provider turn.

**Bryan's capacity ceiling is 75% consumed of the 5-hour window.** Do not start
or prompt a Claude turn at or above 75%. Below 75%, dispatch: the remaining 25%
is the buffer that absorbs a turn's overrun. Do not forecast whether the
expected turn, a concurrent session or past-lane costs will push past 75%, and
do not defer dispatch to wait for a reset while below it. A self-imposed lower
threshold (say, "start once below 55%") idles ready lanes for hours. Reviewers
are Claude turns too, and the same rule applies to them. The helper's own check
refuses only at 100%, so read its percentage against 75% yourself. When usage
really is at or above 75%, a background waiter may poll for it to drop below 75.
Parse the reading as `references/herdr-claude-handoff.md` describes, and make an
empty reading fail the waiter at once.

Do not hand-edit or reconstruct an identity record. `start` exclusively reserves the identity path before any pane
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

Wait on the handback, not on `agent_status` alone. A Claude turn can settle as
`done` while its own background test shell is still running and its handback is
unwritten, and a `prompt` can return `agent_prompt_stalled` while the worker is in
fact working. In both cases, inspect the worker, then poll until the contract's
handback section ends with its `Divergence:` line *and* the worker is not
`working`. Never re-send a prompt to recover a completion signal.

Complete when the original worker settles and the helper returns a verified
status.

### 5. Treat completion as a claim

Inspect the real branch, diff, worktree, and worker report. Run targeted checks
needed to validate the implementation. Then follow `pr-self-review`:

- the parent performs one integrated Standards, Spec, conditional Risk, and
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

A correction contract the parent writes is itself a candidate source of defects.
Before sending it, trace every edge rule it settles (a default for "nothing
recorded", "stay quiet when...", "fresh state on start") through the first live run
after rollout. That first run is usually exactly the empty-history case, so a
"quiet when nothing is recorded" rule can hide the one change the rollout exists to
announce. When the parent's own instruction caused a gap, say so in the next
correction and report it to Bryan as the parent's error.

Missing verification or an unresolved blocker means do not publish. A stop is
not permission to lower quality or switch providers.

Complete when the parent has independently accepted one exact candidate.

### 6. Release the pane promptly

Keep the pane only while the worker is active, blocked on a specific answer, or
has one identified same-session correction. Pending publication, merge, or live
verification is not a concrete next turn. A pending fresh final review is: its
in-scope blockers return to this worker as the bounded correction. So for a
Risk-lane or high-consequence candidate, keep the implementer's pane until the
final review is dispositioned. A closed pane forces the correction into a new
session that lacks the implementation context.

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

## Running an unattended multi-lane batch

When Bryan approves a queue of issues to run while he is away (an overnight
batch), follow this shape:

- **Record the batch.** Write its order, authority (merge-once-cleared or
  stop-at-PR), concurrency limit and live-uptake rule in the project vault before
  dispatch. Change that record, not just the chat, when a decision changes
  mid-run.
- **Lanes by shared files.** Issues that touch the same files run serially in one
  lane. Independent lanes all run in parallel. Bryan sets no cap on how many
  builders run at once (2026-10-23); only the Claude capacity ceiling above limits
  dispatch. Don't hold a ready lane because other builders are busy.
- **The brief is a contract file.** Write it in the ticket state
  directory: authority links, settled open questions, required behaviour, tests,
  verify commands, permissions and handback shape. The prompt is one line
  pointing at it. List the state directory first: an issue's directory outlives
  its earlier lanes, and its ignored `handback.md`, `contract.md` and identity
  files may be the only copies of that evidence. When it already holds them,
  prefix every new file with the lane name (`<lane>-contract.md`,
  `<lane>-handback.md`, `<lane>-worker-identity.json`), and make the contract
  name that exact handback path, because the worker writes wherever the contract
  says. Run every `prompt` as a background terminal job with
  `notify=true`, so each settlement wakes the coordinator.
- **Integrate before the gate.** Merge the current `origin/main` into the feature
  branch (a signed merge commit, never a rebase) before the canonical gate. The
  gate and final review then judge the integrated candidate.
- **A lane that depends on two unpublished lanes.** Create its branch from one
  prerequisite branch (`wt switch --create <lane> --base <prereq-A>`), then make a
  signed `--no-ff` merge of the other prerequisite into it. Review only the lane's
  own changes, `<that merge commit>...<head>`, and say in the PR body which earlier
  PRs its diff against main includes and in what order they merge. When the gate
  tool a prerequisite adds isn't on main yet, run it from a clean `git archive`
  export of the candidate, with `--root` at the worktree. Record the rerun from main
  after the merge as a closeout step.
- **Re-integrate if main moved before the merge.** Main can advance after a
  branch's gate or review, because a sibling lane merged. Check
  `git diff --stat <branch-base> origin/main -- package.json package-lock.json tsconfig.json packages workspaces`.
  If any code path changed, merge main into the branch again and rerun the gate
  before squash-merging. A squash that git merges cleanly can still combine
  untested code. A move limited to vault or docs doesn't need a rerun.
- **A design choice the worker raises is a decision turn, not a correction.**
  Sometimes a handback asks the coordinator to choose between two implementations.
  When an existing rule settles the choice (an invariant from an earlier merged
  change, for example), write `decision-N.md`: the choice, the rule behind it, the
  added assertion or mutant, and the reruns. Send it to the same worker. It
  doesn't spend the issue's correction. Ask Bryan only when no existing authority
  settles it.
- **Never file issues from review findings without Bryan's approval.** A finding
  that the issue's acceptance criteria cover is fixed in that lane before merge;
  don't split it off, even if the issue's examples didn't name it. For other
  non-blocking or pre-existing findings, record them in the PR body, then draft
  any proposed later work in the vault plan's "Proposed for Bryan's approval"
  section and report it when he returns. Keep working; never stop to wait for
  that conversation. Filing a ticket per nit makes the queue feed itself, so the
  work never ends.
- **Serialize full canonical gates.** Two concurrent full runs (browser suites,
  fake services) contend for load and ports. When the repository has a gate
  runner or lock, start every gate through it; it queues them itself. Only
  without one, queue the next gate behind the running one's PID. Stop a queued
  gate whose candidate a dispatched correction is about to change; its result
  would judge a superseded head.
- **Clean up workers' scratch.** Worker sessions are often refused `rm -rf` of
  their own scratch directories. The coordinator removes the paths named in the
  handback after reading it.
- **Hold live changes that need a human check.** An authorized behaviour change
  whose activation needs a live check, a pending experiment or a message into a
  real room can still merge as source. Hold its live uptake, and record the hold
  and why for Bryan's morning. Its PR says `Refs #N`, not `Closes #N`, so the
  merge doesn't close an issue whose live acceptance item is still open.
- **Conflicts with a sibling lane are a worker turn, not a correction.** When
  `git merge origin/main` stops on conflicts because another lane landed first,
  write an `integration.md` (what landed, which files conflict, keep both sides'
  tests whole, report rather than work around a behavioural clash, one authorized
  `git commit --no-edit`). Send it to a fresh worker identity
  (`integration-worker-identity.json`). The parent doesn't hand-resolve code
  conflicts, and the turn doesn't spend the issue's correction.
- **Final-review findings mid-batch.** Bundle the in-scope blockers into the one
  correction right away and dispatch it. Post the items that are Bryan's call
  (scope or semantics the authority left open) on the issue, each with a
  recommendation, and keep going. Don't hold the lane waiting for him. If the
  candidate changes text he must approve (laws, contracts), park the correction
  until he decides instead of correcting twice.
- **Predicted mutants are not results.** A read-only reviewer may be refused
  permission to execute tests and then only predict which test catches each
  mutant. Put real mutant runs into the correction contract (or run them as the
  parent) before accepting, and name any mutant that survives today.
- **Ask for what needs Bryan; don't park it in a list.** A "waiting for Bryan"
  line is not a question, and a gate with a deadline can sit in those lists
  across sessions until the deadline passes. The first time you report an item
  that needs him, say in plain words what it is and why it exists, what it costs,
  what his answer unblocks, and your recommendation, cancelling included. Lead
  with deadline-bearing items, before routine choices. Ask one question per
  message, in chat, and wait for it to be settled before the next; while lanes
  report in between, end each status update by restating the one open question
  rather than queuing the next.
- **Absolute scratch paths across calls.** Write PR bodies and comment drafts to
  `~/.hermes/cache/scratch/<name>.md` with `write_file`, never `$TMPDIR`: tool
  calls can see different `TMPDIR` values, and a missing body file makes
  `tea pr create` publish an empty description silently. Read the body back
  after creating the PR.

## Reporting to Bryan

- **Bryan doesn't do PR reviews.** PRs are for the coordinator and the Claude reviewers. When something needs his
  approval (laws, a config file, a decision), put what he is approving in the message itself, in plain words. A link
  is welcome for the web UI, but only to the exact file at an exact commit
  (`https://<forge>/<owner>/<repo>/src/commit/<sha>/<path>`), one link per file, never a PR page.
- **Every ask is self-contained.** When Bryan has something to do, restate the exact steps or commands in that message.
  Never point him at "my earlier message" or "the commands above". This holds for every status update that ends on
  his pending action, and for a "where is it now?" answer: give the state table, then the full current ask.
- **Before you say something waits on him, check its evidence by metadata.** Look for the files his step would create,
  or the comment it would post. Then say whether it has happened, rather than repeating the ask blind.
- **Every issue and PR named in a message gets its title and full URL, every time.** A bare `#246` or "PR 2" makes
  Bryan ask again; he has had to repeat this many times. Status updates included.

- **A count you state is the count you list.** "One thing is time-sensitive"
  followed by a numbered list of four reads as four urgent items, so the real
  one drowns. List exactly what you named; anything else goes after it, marked as
  lower weight, or is left for the next session.
- **"Anything before I go?" means only what can't wait.** Answer with the items
  that need his action before he leaves, plus one line that nothing is running.
  Leave review material, connections and open decisions for the session he comes
  back to.
- **Refresh live state before a final report.** Read the remote branch and the
  project index again: a parallel session may already have acted on what you are
  about to report as open.

## Explicit Background-Only Route

Only an explicit same-run background-only request may use Claude Agent View.
Read `references/claude-agent-view.md`. It is a separate surface and cannot
resume a Herdr identity.

## Common Pitfalls

1. Keeping small edits, fixture/harness repairs, or implementation tooling with the parent to save worker startup cost.
2. Confusing per-session turn serialization with a global ban on concurrent Claude work.
3. Making the prompt a second plan.
4. Rechecking identity with improvised shell commands instead of the helper.
5. Treating worker tests, idle status, or prose as parent acceptance.
6. Letting a worker-discovered adjacent defect expand the ticket or candidate without a new user decision.
7. Using "all call sites" as permission for an exhaustive domain audit rather than bounded application of the selected mechanism.
8. Starting a fresh worker for corrections instead of resuming the recorded one.
9. Duplicating the parent's pre-publication acceptance through a generic fresh reviewer.
   Bryan's required post-draft-PR SGG Claude final review is not this pitfall.
10. Leaving a settled pane open as a status marker.
11. Confusing correction allowance with provider capacity.
12. Reading "hand it off to a subagent" as `delegate_task` or a cron-spawned
    hidden subagent. Bryan means this skill's normal visible handoff. A
    deferred start ("after usage resets") changes only when the handoff
    starts. Defer it with a reminder or a check-in back to the parent, never
    by delegating the work itself from a cron job. A hidden subagent also
    inherits the delegation model instead of the worker role's.

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