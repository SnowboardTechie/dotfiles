---
name: coding-agent-handoff-supervision
description: Use for visible CLI or Matrix coding-agent handoffs.
version: 3.0.0
author: Bryan Thompson + Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [coding-agents, handoff, supervision, pi, hermes, rex]
    related_skills: [issue-work, pr-self-review, subscription-coding-worker-governance]
---

# Coding Agent Handoff Supervision

## Overview

The parent (a Pi or Hermes session) orchestrates; a Pi worker implements. Hand decision-complete
implementation to a visible Pi worker, including small changes, fixtures, harnesses, tooling,
and repairs discovered during verification. Task size and worker startup cost
are not exceptions. Pi is the worker for everything (Bryan, 2026-11-10):
implementers, reviewers and requested read-only work alike; simple questions
stay with the parent unless Bryan asks for a worker. Only Bryan's explicit
selection changes the implementation role or runtime (Claude or Hermes). The parent owns scope,
dependencies, handoffs, supervision, independent acceptance, authorized Git
integration/publication, and live verification. A worker produces a candidate,
not an accepted deliverable.

The workflow optimizes for one useful implementation turn and one bundled
correction, not a prolonged conversation. Rex mechanics are owned by
[references/rex-claude-handoff.md](references/rex-claude-handoff.md) and its
scripts (`scripts/rex_subagent_slot.py`, `scripts/rex_wait.sh`); follow that
procedure rather than improvising pane commands in chat.

## Select the execution surface first

Visible workers run from an interactive Pi or Hermes CLI session in a Rex pane, using
the Rex procedure below. Select the transport before checking its environment.

A gateway-only conversation (Matrix and similar) has no caller pane and no
visible-worker transport. Report that blocker and the way to unblock it
(continue from a Pi or Hermes CLI session in a Rex pane in the project); do not offer
a background fallback. Do not fabricate context bindings, caller-pane variables
or authorization to make a transport work.

For a natural request such as "Have a worker take a look at the dotfiles README",
resolve the project directory from established context; do not ask the user to
supply internal task IDs or paths already known. For a bounded read-only review,
the user's request is the brief authority: narrow the brief to inspection and
reporting, prohibit edits/publication, and start the worker. Ask a question only
when that changes the work or a required project/permission is genuinely unknown.
Implementation still needs the governing ticket/approved plan and the role,
acceptance, correction, capacity and cleanup rules below. The default worker,
for either parent and every role, is a visible Pi worker on
`claude-code/claude-opus-5-5` with medium thinking, its seat following the
worktree.
Bryan's explicit runtime selection overrides this
policy. Do not expand a simple question into an audit: keep the brief and
verification proportional to the requested answer.

## When to Use

Use for repository implementation of any size when all of these are true:

- one governing ticket or approved plan exists;
- goal, scope, exclusions, and architecture are decision-complete;
- acceptance is observable through tests, probes, or exact readback;
- edit and delivery permissions are explicit.

Delegate a `single-loop` change too; right-size its brief and verification, not
its implementation owner. For ticket work, use `issue-work`'s router with the
standing Pi selection. Do not turn a fixture or tooling repair into parent
implementation by calling it verification.

Do not use this workflow for open architecture, live incident diagnosis,
voice-heavy writing, or exploratory research. Resolve those in the parent conversation first.

## Delivery boundary and substantive handback

Default ordinary implementation handoffs to supervised delivery. "Hand it to a worker" does not authorize dropping parent acceptance/publication or inventing
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
Read the report and the real candidate before reporting completion or answering what the worker said. A lifecycle `done` event is not a handback. If the report is
absent, retrieve the final message by reading the recorded worker's pane after
checking its identity, or request the missing report from the same worker
within its capacity and turn boundary. Never substitute a runbook for an unread final message while
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
new code or a repaired harness belongs in a bounded worker handoff; do not build
it in the coordinator while the implementer waits. A worker's failure, capacity
limit or closed session does not transfer implementation ownership to the parent.
Recover the permitted worker route or report its concrete blocker.

Do not spend a parent implementation session before handoff and then use a worker only as reviewer. Do not use a second worker session to review the first
by default outside Bryan's SGG closeout; the parent is already the independent
pre-publication acceptance context. For SGG issue implementation, `issue-work`
owns the required sequence: parent acceptance, verified draft PR, fresh worker final PR self-review, parent disposition, and cleanup. That post-publication final
gate is required, not an optional redundant pre-publication reviewer.

## Procedure

### Continuation and decision boundaries

When Bryan selects a worker, settles the plan, and says to proceed, execute the
handoff rather than returning a prompt for him to carry. Verify worker delivery;
only a real transport/capacity blocker or an explicit prompt-only request
justifies stopping at text. A planning artifact's earlier execution-disabled
status must not erase a later explicit implementation instruction.

For Bryan's SGG issue-implementation handoffs, "proceed" executes the established
complete closeout through the draft PR and fresh worker final self-review, unless
he explicitly sets an earlier stopping boundary. Record that delivery authority
and continue under `issue-work`; do not return "done" at worker settlement or a
pushed branch. Plan-only and prompt-only requests remain non-execution requests.

A scope boundary stops applying an unapproved change, not ordinary investigation
of its remedies. Before escalating a blocked candidate, inspect upstream fixes,
compatibility requirements and the actual affected call paths; perform isolated
probes when already authorized. Preserve the candidate and return a concrete,
evidence-backed decision only where implementation would cross the boundary.
Do not ask permission merely to investigate the next recovery step.

When Bryan asks for follow-up issues to be filed, filing includes handing each
one to a worker and supervising it through merge and live verification. A
filed-but-undelivered issue is not the deliverable.

Keep an authorized multi-issue outcome moving: dispatch ready independent work
within the governing concurrency limit, collect handbacks, accept prerequisites,
and advance their consumers. Routine in-scope implementation and fixture repairs
remain the worker's under the existing completion authority, not another
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

Pi workers are not approval-gated and not sandbox-confined: Pi runs every tool
call, so a worker's limits rest on its contract's prohibitions only. That fits
work in Bryan's own repositories. When a task requires an approval gate or hard
confinement, stop and ask Bryan; he may select a Claude worker
(`--permission-mode auto`) or a Hermes one (`approvals.mode: smart`, no
`HERMES_YOLO_MODE`, no `--yolo`) for it. Stop when hard confinement is required
but cannot be proved.

Use `claude-code/claude-opus-5-5` at `medium` thinking for implementers and
reviewers alike (Bryan, 2026-10-23). The coordinator's own thinking level does
not carry over to workers. Use a higher level only when Bryan asks for it.

For an explicitly selected Claude worker, starting it in the inspected worktree
created for Bryan's authorized task already authorizes Claude's ordinary **Yes,
I trust this folder** startup step. Accept only that recognizable trust prompt,
after confirming the path it shows is the exact worktree in the recorded startup
pane. This is not blanket permission for unrelated paths, login prompts,
destructive commands, broader permission modes, or new task decisions.

Complete when the worker can identify the artifact, worktree, and authority
boundary without a second copy of the plan.

### 3. Start the worker in Rex

Require the caller's injected `REX_BLOCK` and `REX_SESSION`, and start the
worker through the `rex` CLI as
[references/rex-claude-handoff.md](references/rex-claude-handoff.md) describes.
Visible work has no silent Agent View, print-mode, tmux, or background fallback.

Pi's tool shell carries `REX_SESSION`, `REX_BLOCK` and `REX_BIN_DIR` directly:
on Pi, `echo $REX_SESSION $REX_BLOCK` settles it, and an empty result means the
session is outside Rex. The process recovery below applies only to Hermes.

Hermes usually passes the `REX_*` values straight into the tool shell
(`terminal.client_env_passthrough`); check `echo $REX_SESSION $REX_BLOCK` first.
On Hermes, an empty result there does not prove the session is outside Rex. Before
reporting a transport blocker, find this session's own CLI process and read its
`REX_*` values with `python3 ~/code/dotfiles/dot-agents/lib/terminal_host.py PID`
(exact JSON; never hand-parse `ps eww`, which joins variables with spaces and
breaks any value that contains one, such as Rex's `REX_BIN_DIR`), and export
them. Never pick the process by matching cwd: several Hermes sessions often
share a project cwd, and their panes belong to other conversations. An ancestry
ending at `hermes gateway run` does NOT prove the session has no caller pane:
with the Claude direct-SDK provider, a CLI session in a pane runs its tools
under the gateway, so walking the tool shell's ancestry never reaches the CLI
(Bryan corrected this repeatedly, 2026-10-28). Identify the session's own CLI
process instead: find this conversation's session in `~/.hermes/state.db`
(`select id, source, started_at from sessions where id in (select session_id from
messages where content like '%<a unique phrase from this conversation>%')`); a
`cli` source means a CLI session. Match its `started_at` to the one Hermes process
with `REX_BLOCK` in its environment whose `ps -o lstart=` agrees within a
second or two, and export that process's `REX_*` values. Only a gateway-sourced
session (Matrix and similar) has no caller pane; see "Select the execution
surface first". Check the transport before writing the contract so the blocker
surfaces early; the worktree and contract stay useful for the resumed session.

The worker opens in the orchestrator's "<tab label> Sub Agents" tab (then
"... 2", "... 3"), at most four per tab in a 2x2 grid placed by
`scripts/rex_subagent_slot.py`, a new tab's root block being the worker itself,
never beside the coordinator's own block. The worker gets the prompt file as
its first turn and a fixed `--session-id`. The coordinator does the checks by hand:
identity record, the 75% capacity gate, one turn at a time, settlement from
transcript plus handback, close. Background `terminal` processes do not inherit
foreground exports: put the `export` (or the literal values) inside every
background command.

Never retry a refused action through another tool or infer permission from
frustration. A still-refused action remains blocked; do not escalate to a
broader mode or another execution route. (For an explicitly selected Claude
worker whose approved installation auto mode misclassifies, pass a scratch file
of only `{"autoMode":{"allow":[...]}}` as inline `--settings`, keep auto mode,
change no deny rules, and record its hash in the identity record.)

Start Claude or Hermes workers only on Bryan's explicit selection, as the
reference's "Other worker runtimes" describes; check a Hermes worker's
smart-approval prerequisites independently first.

After the start, the coordinator computes Git identity and records, once:

- `worker_surface`;
- `worker_agent_name`;
- `worker_pane_id`;
- `worker_kind`;
- `worker_runtime_session_id`; and
- `worker_worktree_identity`.

Run the live capacity gate before the block is created. A Pi worker on
`claude-code/...` spends a Claude seat, so the gate reads the seat it uses:
`CLAUDE_CONFIG_DIR` set to the worker's `PI_CLAUDE_CODE_CONFIG_DIR`, unset for the
work seat. Any nonzero
capacity result stops before a provider turn. An empty capacity reading is a stop, never a pass.

**Bryan's capacity ceiling is 75% consumed of the window the gate reads.** The
gate reads the 5-hour window when the seat has one, and the weekly window when
it doesn't. The 75% ceiling applies to whichever window it reads. For a weekly-only
seat, that ceiling is the coordinator's reading of Bryan's rule, recorded
2026-11-11, and it stands until he sets another number. Do not start
or prompt a worker turn at or above 75%. Below 75%, dispatch: the remaining 25%
is the buffer that absorbs a turn's overrun. Do not forecast whether the
expected turn, a concurrent session or past-lane costs will push past 75%, and
do not defer dispatch to wait for a reset while below it. A self-imposed lower
threshold (say, "start once below 55%") idles ready lanes for hours. Reviewers
are worker turns too, and the same rule applies to them. When usage really is
at or above 75%, a background waiter may poll for it to drop below 75. Parse the
reading as `references/rex-claude-handoff.md` describes, and make an empty
reading fail the waiter at once.

Write the identity record once, from observed values only. Do not hand-edit or reconstruct an
identity record afterwards, and never overwrite an existing identity path,
including a closed one. Use a new state path for a separately authorized new
worker.

Complete when the identity file records one ready worker in the intended
worktree.

### 4. Submit one turn per worker session

Put the short brief in a state-root file. The first turn is that file, given to
the worker as its start argument; a later turn (a correction) is typed into the same
block only after settlement, as the Rex reference's "A second turn" section
shows. Before every turn:

1. confirm no turn is in flight in that worker runtime session;
2. perform a fresh provider-capacity check;
3. check the recorded block still shows the recorded label and window; and
4. send exactly one prompt.

A command's exit status proves only that the keystrokes were sent, not that
the worker accepted the prompt. Until a new `user` record appears in the
transcript, report delivery as unconfirmed. A nonzero exit or rejected
submission requires immediate inspection and authorized recovery; do not end
with a delivery claim or an apology. A settled worker can accept its
same-session correction; do not replace it merely because its previous turn
completed. Never retry an uncertain submission until its delivery state is
resolved, skip identity/capacity checks, or expand permissions to make recovery
succeed.

At most one turn may be in flight **within each worker runtime session**.
Independent sessions may run concurrently in their own worktrees, including
when they share a subscription. Another agent working on another task is not a
handoff blocker. Capacity and exact worker/worktree identity checks still apply.
One coordinator owns each worker, and nothing else sends to it.

If the worker blocks on a question or approval, read its pane with `capture`
and compare the request with the governing plan. Answer an already-settled
question from that approved authority; ask Bryan only for a new decision or
permission. Never treat worker-suggested input as approval (including a greyed
predicted prompt in the input line), infer a new security approval from general
task authorization, or weaken an explicit gate. Send only input covered by
Bryan's approval, as literal text or an interactive key choice such as
`down enter`, and confirm in the pane that it was accepted before reporting it
delivered. If the prompt is gone when you look, inspect the live state before
any retry: the user may have answered in the visible pane or the prompt may have
timed out. Do not invent which actor resolved it.

Wait on the handback, not on a turn's end alone. A worker turn can end while its
own background test shell is still running and its handback is unwritten. Run
`scripts/rex_wait.sh` as a tracked background process, which settles only when
the transcript shows the turn ended *and* the contract's handback section ends
with its `Divergence:` line. Never re-send a prompt to recover a completion
signal.

Complete when the original worker settles and its identity still matches the
record.

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

Close it with the Rex reference's "Close" steps: exit the worker, close only the
recorded block, confirm the block is gone, and then mark the identity closed/non-resumable.
Do not ask for cleanup approval and never close the caller or an unrelated pane.

Complete when the recorded block is absent.

## Running an unattended multi-lane batch

When Bryan approves a queue of issues to run while he is away (an overnight
batch), follow this shape:

- **Record the batch.** Write its order, authority (merge-once-cleared or
  stop-at-PR), concurrency limit and live-uptake rule in the project vault before
  dispatch. Change that record, not just the chat, when a decision changes
  mid-run.
- **Lanes by shared files.** Issues that touch the same files run serially in one
  lane. Independent lanes all run in parallel. Bryan sets no cap on how many
  builders run at once (2026-10-23); only the capacity ceiling above limits
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
  says. Run every `scripts/rex_wait.sh` wait as a background terminal job with
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
- **A stacked branch after its base PR is squash-merged.** Merging main into it
  conflicts add/add on every file the base PR added and this branch changed,
  because the squash isn't the base branch's commit. When
  `git diff <base branch head> origin/main` is empty (main's only change is that
  squash), abort and `git merge -s ours --no-ff -S origin/main` with a message
  saying so, then check `git diff <gated head> HEAD` is empty: the gate evidence
  still holds. If main has anything else, it's an integration worker turn.
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
- **Don't restart a shared service under another coordinator's run.** Rebuilding the shared deployment or restarting a
  proxy cuts the in-flight model turns and replays of any other lane using it. Before a live uptake, check the
  service's own records for running case VMs and recent requests. If either shows activity, start a background waiter
  that settles once the service has been idle for about ten minutes, and do the uptake then.
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
- **Don't ask what you can already answer.** A call whose answer is obvious from
  checked facts is yours to make, even where a design names Bryan as its owner
  (residue rulings, labels, dispositions): make it, record it as yours with the
  reason, and name it in the report. Ask him only a genuinely open call, one at a
  time, with what it changes. Six questions that each came with a confident
  recommendation read as manufactured blockers (Bryan, 2026-11-09, #21).
- **Don't hold work for a date without a reason.** Run authorized work now
  unless a concrete dependency or harm needs the wait. "Run after the window
  closes" for experiments that needed nothing from the window cost a day of
  back-and-forth before Bryan ended it (2026-11-09, #21).
- **Absolute scratch paths across calls.** Write PR bodies and comment drafts to
  an absolute path, never `$TMPDIR`: on Pi, with the `write` tool into the ticket
  state directory (`<state dir>/<name>.md`); on Hermes, to
  `~/.hermes/cache/scratch/<name>.md` with `write_file`. Tool
  calls can see different `TMPDIR` values, and a missing body file makes
  `tea pr create` publish an empty description silently. Read the body back
  after creating the PR.

## Reporting to Bryan

- **Bryan doesn't do PR reviews.** PRs are for the coordinator and the worker reviewers. When something needs his
  approval (laws, a config file, a decision), put what he is approving in the message itself, in plain words. A link
  is welcome for the web UI, but only to the exact file at an exact commit
  (`https://<forge>/<owner>/<repo>/src/commit/<sha>/<path>`), one link per file, never a PR page.
- **Every message stands alone.** When Bryan has something to do, restate the exact steps or commands in that message.
  Never point him at "my earlier message", "the commands above" or "the three items I listed". This holds for every
  status update that ends on his pending action, every summary, and a "where is it now?" answer: give the state, then
  the full current ask.
- **Re-raising a pending question means re-explaining it.** Never write "my question is still open" or a one-line
  pointer to it: by the next update he has lost the context. Each time it appears, say what it is, why it exists, what
  each answer does, and your recommendation, in plain words.
- **Don't flip-flop.** Change a recommendation only with named new evidence, and say what that evidence is. Before
  contradicting what he says you said or decided, check the record first; never correct him and reverse your own
  recommendation in the same message. Don't keep tacking a standing proposal ("want me to chart the map?") onto every
  report; re-check that it still fits before offering it again, or drop it.
- **Finish the assigned outcome in one pass.** When he approves a move or migration, do every item the approved scope
  covers. Don't stage it into a first slice he didn't ask for, don't keep the old path as a quiet fallback that defeats
  the purpose, and don't spend his resources on baselines he didn't ask for. Staging is a choice to offer, not a default.
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
resume a visible Rex worker's identity.

## Common Pitfalls

1. Keeping small edits, fixture/harness repairs, or implementation tooling with the parent to save worker startup cost.
2. Confusing per-session turn serialization with a global ban on concurrent worker sessions.
3. Making the prompt a second plan.
4. Sending to a worker without first checking that its block still matches the identity record.
5. Treating worker tests, idle status, or prose as parent acceptance.
6. Letting a worker-discovered adjacent defect expand the ticket or candidate without a new user decision.
7. Using "all call sites" as permission for an exhaustive domain audit rather than bounded application of the selected mechanism.
8. Starting a fresh worker for corrections instead of resuming the recorded one.
9. Duplicating the parent's pre-publication acceptance through a generic fresh reviewer.
   Bryan's required post-draft-PR SGG final review is not this pitfall.
10. Leaving a settled pane open as a status marker.
11. Confusing correction allowance with provider capacity.
12. Reading "hand it off to a subagent" as a hidden sub-agent mechanism
    (Hermes's `delegate_task`, a cron-spawned subagent, or the like; Pi has
    none). Bryan means this skill's normal visible handoff. The one Pi
    exception is read-only fan-out that a skill names: parallel research,
    candidate drafts, or review lanes returning findings only may run as
    headless `pi -p --no-session` children limited to
    `--tools read,grep,find,ls`. A child that must run read-only commands
    (`gh` reads, `git show`, `curl`) gets `--tools read,grep,find,ls,bash`
    with its prompt naming the only commands it may run; Pi has no approval
    gate, so any write it makes voids its result. Implementation, and any
    independent review that acceptance rests on, stays a visible worker. A
    deferred start ("after usage resets") changes only when the handoff
    starts. Defer it with a reminder or a check-in back to the parent, never
    by delegating the work itself from a cron job. A hidden subagent also
    inherits the delegation model instead of the worker role's.

## Verification Checklist

- [ ] A Pi worker owns implementation regardless of task size; any alternate runtime has Bryan's explicit selection
- [ ] One verified ticket or approved plan governs the handoff
- [ ] Brief contains locator, worktree, authority, and delivery permissions only
- [ ] Destructive/history-rewriting Git operations remain prohibited
- [ ] Visible path uses a Rex sub-agents tab slot (max four, 2x2) per references/rex-claude-handoff.md, without stealing focus
- [ ] The worker command sets `PI_PROGRAM_STATUS=0` (Claude: `CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1`), so Rex raises no alerts for it
- [ ] The coordinator persisted all six identity fields
- [ ] Seat capacity passed (below 75%) and no other turn was in flight in the worker runtime session
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

- [Visible Pi workers in Rex](references/rex-claude-handoff.md)
- [Design-preview promotion](references/design-preview-handoff.md)
- [Explicit background Agent View](references/claude-agent-view.md)