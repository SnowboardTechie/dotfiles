---
name: session-handoff
description: >
  Use when the next slab of implementation work lives in Bryan's head rather
  than on a tracker, and he wants it carried out by fresh sessions instead of
  this one. Triggers: "hand this off", "what's next here and who runs it",
  "write the prompt for the next session", "can this be split across agents",
  "spin up a fresh context for this". Reconciles the vault record, decides
  whether the frontier is one separable slice or several, and emits a handoff
  prompt per slice. Needs no ticket. Decides slicing and agent topology.
  Ordinary implementation handoffs retain supervised delivery; status-only or
  separate acceptance requires Bryan's explicit choice and a durable handback.
---

# Session Handoff

Slice untracked implementation work out of this session's head and into fresh
contexts. First select the delivery boundary: ordinary requests to implement or
hand work to Claude route to `coding-agent-handoff-supervision`, retaining parent
review, correction and authorized publication. Use the handoff-only procedure
below only when Bryan explicitly chooses separate acceptance, status-only
notification, or fire-and-forget. Do not infer that stopping boundary from
"hand it off".

The governing authority may be a ticket or a decision-complete approved plan.
This handoff-only route starts from a durable record and a judgment about where
the frontier actually is; do not create a ticket solely for transport.

## When to use

All of these:

- the work is **implementation**, not an open architecture question;
- it is **untracked** — no issue exists and creating one is not the point;
- this session holds context the record does not yet;
- Bryan explicitly chose a handoff-only boundary with acceptance owned by a
  separate invocation (a status-only watch is notification, not supervision).

Do not use it for open questions. If the work is not decision-complete, handing
it off produces a confident wrong implementation. Say so and stop — route to
`grilling` or brainstorming if this runtime carries one.

Do not use it to plan decisions (`wayfinder`), and do not use it for work that
already has a ticket (`issue-work`, `loop-issue`). Each of those routing targets
is curated per runtime; when one is not installed here, still stop and name the
problem rather than handing off anyway.

## The boundary this skill exists to hold

> **Tripwire: this handoff-only route cannot send the worker another turn,
> read its pane, answer it, or close it, or review, correct, or accept
> the candidate. Retain only the status watch and read its durable handback
> artifact to communicate the result; neither grants acceptance authority.**

Three engagement modes exist, and they never mix:

- **status-only** (explicit handoff-only boundary): delegate, keep one bounded terminal-status watch,
  notify Bryan once when the turn settles, ends without a handback (possibly
  blocked), or times out. No review or acceptance duty.
- **fire-and-forget** (explicit only — Bryan says "fire and forget", "do not
  monitor", or equivalent): delegate and retain no watcher at all.
- **supervised** (ordinary implementation default): `coding-agent-handoff-supervision`, with its
  inspection, review, correction, acceptance, and cleanup responsibilities.

In explicit status-only and fire-and-forget modes this session does not read the
worker pane, answer questions, judge the diff, or close the pane. Require a
durable handback path in the governing artifact: candidate identity, actual
checks/results, unfinished work, blockers, approval requests in dependency order,
and next acceptance owner. After a status-only turn settles, read that handback
(not the pane) and report its substantive outcome, labeling worker claims as
unverified. A missing handback means result unavailable, not completion.
Acceptance remains a **future invocation** only because Bryan chose that boundary.
A settled watch proves turn settlement, never task completion. A blocked
notification names the pane and identity without scraping its prompt.

If Bryan wants a supervised worker whose output he accepts in this session, that
is `coding-agent-handoff-supervision` — use it instead of this one, and never
combine them. Where that skill is not installed for this runtime, say that the
request is supervision rather than handoff, and stop.

## 1. Reconcile the record

Invoke `vault-pkm` first — it routes per-vault and the target vault's own
`AGENTS.md` overrides its defaults.

Then make the canonical surfaces this session actually moved agree with each
other:

- the status or project/log page;
- the topic MOC or the exploration that owns the reasoning;
- the index routing line that gets someone there.

Reconcile **in place**. Never append a fresh note beside a stale one — that
manufactures the contradiction the next session has to resolve.

Form the **handoff dependency set**: the canonical record plus every vault file
it links or names whose content the next agent needs. A `draft` or
`noncanonical` designation is an authority label, not a Git transport rule.
Invoking `session-handoff` is explicit authorization to commit and push
task-owned drafts in that dependency set without promoting or approving them.
Do not absorb unrelated drafts.

Fetch, stage the exact dependency paths, check the staged diff, commit, push,
fetch again, and verify every dependency is reachable from the pushed commit
with no required local delta left behind. Availability in the same dirty
working tree does not count. If vault-local policy truly forbids versioning a
required artifact, stop and report that the handoff is not portable instead of
emitting a prompt that points to local-only content.

This step is not hygiene. With nobody supervising, **the record is the handoff**
and the prompt is only a pointer into it. That gives this skill its completion
test: *if the record cannot stand alone, the handoff is not done*, however good
the prompt is.

## 2. Carve the frontier and decide who runs it

One judgment, not two. What makes something a separate slice is exactly what
makes it parallelizable, so deciding "what is next" and "how many agents" is a
single test applied to each candidate piece.

A piece stands alone only if **all four** hold:

1. it touches files no other live piece touches;
2. nothing must land before or after it;
3. its own tests can go green without the other pieces;
4. it is decision-complete by itself.

Fail any one and it is not a slice — it is part of the piece beside it. Merge it
into that piece and re-test.

The output is **N prompts**, and N is usually one. Reach that by applying the
test, not by preferring single agents.

### Worked example — four changes that looked splittable and were not

From the 2026-09-14 SGG factory review:

- **Engine-side send counter.** Passes the file test. Fails (2): the submodule
  re-pin must follow its commit. Fails (3): `test_bootstrap.py` asserts the
  ledger and gitlink agree, so it cannot go green alone.
- **Two changes to `review_pr.py`.** Both edit line 449 — one deletes an
  argument from a phase, the other wraps that same phase. Fails (1).
- **The fourth change.** A decision *not* to build something. Not work at all.

Nothing survived alone. One slice, one agent.

## 3. Route

### Default: emit the prompt

Print it for Bryan to carry into a fresh context. The prompt is a **pointer, not
a copy**.

Carry only what does not autoload and what drifts:

- the vault note that owns the outcome, by path;
- worktree paths and current heads;
- ordering constraints;
- the scope fence;
- what to report back.

Do **not** restate steps, files, tests, requirements, or safeguards that the
reachable note already carries, and do not tell the agent to read `AGENTS.md` —
it autoloads. A second copy of the specification is the copy that goes stale.

### On explicit handoff-only launch: status watch

Only when Bryan asks for the worker to be started, **and** this runtime is
sitting in a Rex pane. Check first: non-empty `REX_BLOCK` and `REX_SESSION`
(found as `coding-agent-handoff-supervision` describes when the tool shell
lacks them). Without them there is no launch route — emit the prompt as above,
say why, and stop. That is a normal outcome, not a failure: the prompt is the
deliverable and the launch is only convenience.

Write the prompt to **session scratch beside the identity file** — not the vault,
not `.hermes/`. It is a disposable pointer with no independent content, so a
vault copy would be exactly the second copy the pointer contract forbids.

The procedure lives in the dotfiles repo and is reached by its pool path,
because `coding-agent-handoff-supervision` is not curated into every runtime's
skills directory. Start the worker exactly as the "Start" section of
`dot-agents/skills/coding-agent-handoff-supervision/references/rex-claude-handoff.md`
describes: the capacity gate, a slot in this session's sub-agents tab, the
prompt as Claude's first turn (so it is submitted exactly once), and the
identity record. Add `engagement_mode: status-only` to that record.

The default model is `claude-opus-5-5`. When Bryan explicitly selects another
Claude model, pass its exact full model name and carry that choice in the prompt;
never add a fallback model. Claude effort defaults to `medium`
(Bryan, 2026-10-23); pass a higher value only when Bryan asks for one.

The status watch is that skill's `scripts/rex_wait.sh <transcript> <handback>
<cap seconds>`. It prints one line — `SETTLED` (exit 0), `ENDTURN-NO-HANDBACK`
(exit 2), or `TIMEOUT` (exit 1) — and never returns worker output. The worker
and pane are left intact for a future independent acceptance.

**Run it as your runtime's tracked background process with completion
notification** — the turn can outlast any foreground time budget. End your
conversational turn; when the completion event arrives, read the durable handback
and report its remaining gates in order, distinguishing worker claims from
independent verification. Include locators and stop at Bryan's chosen boundary.
Do not poll. If this runtime cannot
arrange a completion event, either keep the wait attached until it settles or
emit the pointer prompt and say plainly that automatic notification is
unavailable — never claim a watch that does not exist.

If the caller dies mid-wait, do **not** start the worker again — that would be a
second prompt. When the identity record exists, the prompt was already
submitted with the start; rerun only `rex_wait.sh` against the recorded
transcript and handback. It never resends.

**Explicit fire-and-forget** (Bryan said "fire and forget", "do not monitor",
or equivalent): start the worker the same way, record
`engagement_mode: fire-and-forget`, and start no wait. Then terminate: report
what was handed off, where the record lives, and the identity path — and stop.

Nothing in Rex refuses a later `send` to a handed-off worker, so the tripwire
above is the whole boundary. Do not type into, read, or close a status-only or
fire-and-forget worker's pane, and do not retry into a supervision loop.

## Completion

Three distinct states; never collapse them:

1. **Handoff delivered** — the vault record stands alone as the specification;
   every required vault artifact is reachable from the synchronized commit with
   no handoff-only working-tree delta; each slice passed all four parts of the
   test; one prompt exists per slice, each a pointer rather than a copy; and
   the prompt reached the worker (or was emitted for Bryan to carry).
2. **Delegated turn settled** — the status-only watch reported a terminal
   status. Say "the worker's turn is done" (or blocked/failed), never "done":
   the qualifier is mandatory, because this is not evidence that tests passed, a
   commit exists, or the candidate is correct.
3. **Candidate independently accepted** — a separate, later invocation reviewed
   and accepted it. This skill never reaches this state.

For fire-and-forget, responsibility ends after state 1's delivery report. For
status-only, it ends only after state 2 AND reading and communicating the durable
handback (or explicitly reporting it missing). Neither authorizes acceptance.
