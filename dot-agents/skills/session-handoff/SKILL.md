---
name: session-handoff
description: >
  Use when the next slab of implementation work lives in Bryan's head rather
  than on a tracker, and he wants it carried out by fresh sessions instead of
  this one. Triggers: "hand this off", "what's next here and who runs it",
  "write the prompt for the next session", "can this be split across agents",
  "spin up a fresh context for this". Reconciles the vault record, decides
  whether the frontier is one separable slice or several, and emits a handoff
  prompt per slice. Needs no ticket. Decides slicing and agent topology. A
  default launch is status-tracked: it keeps one bounded terminal-status watch
  that notifies Bryan when the worker settles, blocks, or fails, and nothing
  else; review and acceptance stay a separate future invocation.
---

# Session Handoff

Slice untracked implementation work out of this session's head and into fresh
contexts. By default this session keeps exactly one thing: a status-only watch
that tells Bryan when the delegated turn settled, blocked, or failed. It keeps
no review, correction, or acceptance duty.

Every other route to a fresh agent starts from a ticket. This one starts from a
vault record and a judgment about where the frontier actually is.

## When to use

All of these:

- the work is **implementation**, not an open architecture question;
- it is **untracked** — no issue exists and creating one is not the point;
- this session holds context the record does not yet;
- nobody is going to supervise the result in this session (a status-only
  watch is notification, not supervision).

Do not use it for open questions. If the work is not decision-complete, handing
it off produces a confident wrong implementation. Say so and stop — route to
`grilling` or brainstorming if this runtime carries one.

Do not use it to plan decisions (`wayfinder`), and do not use it for work that
already has a ticket (`issue-work`, `loop-issue`). Each of those routing targets
is curated per runtime; when one is not installed here, still stop and name the
problem rather than handing off anyway.

## The boundary this skill exists to hold

> **Tripwire: if you are about to call `prompt`, `inspect`, `read`,
> `answer-blocked`, or `close`, or to review, correct, or accept the worker's
> output, you are in the wrong skill. The one thing you may keep is the
> status-only tracked wait that `handoff-status` performs.**

Three engagement modes exist, and they never mix:

- **status-only** (default): delegate, keep one bounded terminal-status watch,
  notify Bryan once on done/idle, blocked, failed, timed out, disappeared, or
  identity mismatch. No review or acceptance duty.
- **fire-and-forget** (explicit only — Bryan says "fire and forget", "do not
  monitor", or equivalent): delegate and retain no watcher at all.
- **supervised** (explicit): `coding-agent-handoff-supervision`, with its
  inspection, review, correction, acceptance, and cleanup responsibilities.

In status-only and fire-and-forget modes this session does not read the
worker's output, answer its questions, judge its diff, or close its pane.
Acceptance is a **future invocation**, not a retained duty — a separate context
gets invoked for it, the same way any PR gets reviewed. A "blocked" notification
names the pane and identity locator; it never scrapes the question from the
worker's output. A "done/idle" notification means only that the delegated turn
settled and a candidate may be ready — not that tests passed, a commit exists,
or the candidate is correct.

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

### On explicit request: launch it (status-only by default)

Only when Bryan asks for the worker to be started, **and** this runtime is
sitting in a Herdr pane. Check first: `HERDR_ENV=1`, a non-empty `HERDR_PANE_ID`,
and an executable `HERDR_BIN_PATH`. Without them there is no launch route — emit
the prompt as above, say why, and stop. That is a normal outcome, not a failure:
the prompt is the deliverable and the launch is only convenience.

Write the prompt to **session scratch beside the identity file** — not the vault,
not `.hermes/`. It is a disposable pointer with no independent content, so a
vault copy would be exactly the second copy the pointer contract forbids. The
helper requires the prompt file to sit inside the identity file's directory.

The helper lives in the dotfiles repo and is reached by its pool path, because
`coding-agent-handoff-supervision` is not curated into every runtime's skills
directory:

```sh
python3 dot-agents/skills/coding-agent-handoff-supervision/scripts/herdr_worker.py handoff-status \
  --worktree "$WORKTREE" \
  --identity-file "$SCRATCH/worker-identity.json" \
  --prompt-file "$SCRATCH/worker-prompt.md" \
  --name "$AGENT_NAME" \
  --claude-model opus \
  --title "$TITLE"
```

`--claude-model` defaults to `opus`. When Bryan explicitly selects another
Claude model, pass its exact full model name and carry that choice in the prompt;
never add a fallback model.

`handoff-status` starts the worker, records `engagement_mode: status-only`
before anything is sent, submits the prompt exactly once through Herdr's
wait-capable path under the same turn lease and capacity gates as a supervised
prompt, re-validates the worker identity after it settles, and prints one
compact JSON result: `terminal_status` (`idle`, `done`, `blocked`, `failed`,
`timed-out`, `disappeared`, or `identity-mismatch`), the pane, agent name,
branch, identity path, and prompt path. It never returns worker output. The
worker and pane are left intact for a future independent acceptance.

**Run it as your runtime's tracked background process with completion
notification** — the turn can outlast any foreground time budget. End your
conversational turn; when the completion event arrives, report the compact
status once, with the locators, and stop. Do not poll. If this runtime cannot
arrange a completion event, either keep the wait attached until it settles or
emit the pointer prompt and say plainly that automatic notification is
unavailable — never claim a watch that does not exist.

If the caller dies mid-wait, do **not** run `handoff-status` again — that would
be a second prompt. The identity file's `status_phase` says where it stopped
(`prompt-not-sent`, `turn-in-flight`, `settled`); `status-wait --identity-file
…` waits for the already-submitted turn and never resends.

**Explicit fire-and-forget** (Bryan said "fire and forget", "do not monitor",
or equivalent): use `handoff` with the same arguments minus `--timeout-ms`. It
starts the worker, records `engagement_mode: fire-and-forget`, delivers the
prompt once **without** `--wait`, and returns. It holds no turn lease and
watches nothing. Then terminate: report what was handed off, where the record
lives, and the identity path — and stop.

Consequences worth knowing rather than rediscovering:

- The helper **refuses** `prompt` and `answer-blocked` on a fire-and-forget
  record, and additionally refuses `read`, `inspect`, and `close` on a
  status-only record. The boundary above is structural, not just prose. If you
  find yourself hitting a refusal, re-read the tripwire.
- If delivery fails, the pane is **kept** — startup already succeeded and the
  send is the cheap, retryable step. The command exits non-zero and reports both
  the identity path and the prompt path so Bryan can finish it by hand. Do not
  close the pane and do not retry into a supervision loop.
- Legacy identity records that carry only `supervised: false` are
  fire-and-forget; nothing was ever watching them.

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

After state 1 (fire-and-forget) or state 2 (status-only), this session carries
no further responsibility for any slice.
