---
name: wayfinder
description: Chart a body of work too large for one session as a map of decision tickets on a private Forgejo tracker, then resolve them one per session until the route to the destination is clear. Use only when Bryan explicitly asks to wayfind, chart a map, or work an existing map. Plans decisions; it does not implement.
disable-model-invocation: true
---

# Wayfinder

A loose idea has arrived that is too big for one session and wrapped in fog: the
**destination** is nameable, but the way there is not visible yet. Wayfinding
finds the way. It charts a **shared map** on a private issue tracker and works
its **decision tickets** — questions whose resolution is a decision — one at a
time until the route is clear.

> **Explicit invocation only.** Start only when Bryan asks to wayfind, chart a
> map, or work a named map. Claude enforces this through
> `disable-model-invocation`; Hermes and OpenCode do not read that key, so this
> paragraph is the rule for them. An automatic skill match must never chart a
> map, mutate a tracker, or claim a ticket.

Provenance: adapted from Matt Pocock's `wayfinder`. Upstream pin, accepted and
rejected upstream rules, and the watched source list live in
[`dot-agents/upstreams/mattpocock-skills.json`](../../upstreams/mattpocock-skills.json).

## When it is the wrong tool

Wayfinder costs a tracker, a map, and multiple sessions. Do not pay that unless
the effort earns it:

- **No fog** — the way to the destination is already clear and the whole journey
  fits one session. Exit to `grilling`, or to the ordinary issue workflow.
- **The destination is not nameable.** Then the first job is naming it, which is
  a `grilling` session, not a map.
- **It is implementation, not deliberation.** Approved work goes through
  `issue-plan` and `issue-work`.

Charting a map for something small is the failure mode that makes people stop
using maps.

## Plan, don't do

Wayfinder **plans**. Each ticket resolves a decision; the map is done when
nothing remains to decide before someone goes and builds the thing.

A `task` ticket may perform literal prerequisite work — signing up for a service
so its API can be judged, provisioning access, moving data so its shape can be
seen — but only when that work **unblocks a decision**. It earns its place by
unblocking, never by delivering the destination.

Product implementation always leaves the map: it transitions through an accepted
Git artifact (plan, spec, ADR) and normal issue and execution authority. A map
summary is not implementation authority.

## Where the map lives

**Maps are private. This is not negotiable.**

| Effort | Tracker |
|---|---|
| SGG multi-repository | private `sgg-workspace` tracker |
| A private single repository | that repository's own tracker |
| A future public or external multi-repository domain | its private workspace wrapper tracker |
| Public or upstream source repositories | **never** — they receive only team-ready implementation work |

Exploratory deliberation on a public tracker exposes premature thinking, and
some of Bryan's repositories on the same Forgejo host *are* public. The adapter
refuses to create a map in a repository the API reports as public; do not work
around that refusal.

Resolve the exact repository from the origin remote **plus** an explicit choice
by Bryan. Never infer the tracker silently.

## Structure

**The map** is one issue labelled `wayfinder:map` — the canonical artifact. It is
an **index**, not a store: each decision appears as one gist comment on the map
naming the ticket that holds the detail, and `read-map` renders those comments
as the ordered decision index. A decision lives in exactly one place. The map's
*body* holds the destination and notes; after creation it belongs to Bryan and
the adapter never edits it.

**Tickets** are issues carrying `wayfinder:ticket` plus a `wayfinder:<type>`
label, linked to their map by a stable managed metadata block. Each body is one
question, sized to a single agent session.

**Blocking** uses Forgejo's **native** issue dependencies, so the frontier
renders in the tracker's own UI and Bryan can see what is takeable without
opening the map. A ticket is **unblocked** when every ticket blocking it is
closed.

**The frontier** is the open, unblocked, **unclaimed** tickets, in stable map
order — the edge of the known.

**Claiming** is an append-only comment carrying an **operation id** — a fresh,
unguessable token minted per acquisition — alongside the session's identity,
posted *before* any work. The operation id, not the session, is the ownership
token; record the one the claim prints, because releasing and resolving both
require it. Assignment is optional UI decoration on top: it names a person, and
Bryan is every session's assignee, so it cannot separate two of his sessions.
See *Concurrency* below.

Exact body shapes, labels, metadata markers, and API calls live in
[`references/forgejo-tracker.md`](references/forgejo-tracker.md). Do not
improvise them.

### Refer by name

Every map and ticket has a title. In everything Bryan reads, refer to it **by
that name**, never by a bare number. A wall of `#42, #43, #44` is illegible;
names read at a glance. The link rides inside the name.

## Ticket types

Each ticket is **HITL** (worked *with* Bryan, who speaks for himself) or **AFK**
(agent-driven). A HITL ticket resolves only through that live exchange — an
agent that answers its own grilling questions has broken this.

| Type | Mode | What it is |
|---|---|---|
| `grilling` | HITL | Conversation. The default. Load `grilling`. |
| `research` | AFK | Reading docs, third-party APIs, or local sources to surface a fact a decision waits on. Use when the knowledge lives outside the working directory. |
| `prototype` | HITL | Raise the fidelity of the discussion with a cheap concrete artifact to react to. Route it via [`references/prototype-routing.md`](references/prototype-routing.md). |
| `task` | Either | Manual prerequisite work blocking a decision. Resolved when done; the answer records what was done and any facts later tickets depend on. |

## Fog of war

The map is **deliberately incomplete**. Beyond the live tickets is the fog:
decisions you can tell are coming but cannot yet pin down, because they hang on
questions still open. Resolving a ticket clears the fog ahead of it, graduating
whatever is now specifiable into fresh tickets.

The map's **Not yet specified** section holds that dim view.

**Fog or ticket?** The test is whether you can state the question precisely
*now* — not whether you can answer it.

- **Ticket** when the question is already sharp, even if blocked.
- **Not yet specified** when you cannot phrase it that sharply yet. Do not
  pre-slice fog into ticket-sized pieces; one patch may graduate into several
  tickets, or none.

## Out of scope

Fog gathers only *toward* the destination. The destination fixes the scope, so
work beyond it is **out of scope** — it is not fog, and it does not belong in
Not yet specified. Scope, not sharpness, lands it there.

Out-of-scope work never graduates. It returns only if the destination is
redrawn, and then as a fresh effort.

When an existing ticket turns out to sit past the destination, **close it** (a
closed ticket is unambiguously off the frontier) and record one line — the
gist, why it is out, and a link to the closed ticket — in the map body's **Out
of scope** section. The map body is Bryan's after creation (the adapter never
edits it), so either Bryan adds the line or the session leaves it as an
ordinary comment on the map for Bryan to fold in. It stays out of the decision
index, which records the route actually walked — a scope boundary is not a
step on it.

## Safety

Every one of these is enforced by `scripts/forgejo_wayfinder.py`. Use the
adapter rather than hand-rolled API calls, and do not route around a refusal.

- **Preview first.** Every mutation defaults to dry-run. Bryan sees the exact
  content that would appear on the tracker — including any label the adapter
  would have to create — before anything is written.
- **Every write preflights.** Privacy, the issue number the API actually
  returned, the labels, the metadata version and type, the map association, and
  the active claim are revalidated immediately before *each* write, not once
  when the operation started. A body marker alone is not identity.
- **The map body is never written after creation.** Forgejo has no
  compare-and-swap on issue update, so *any* body rewrite could overwrite a
  human edit that landed after the adapter's last read. The decision index is
  therefore not body text: each resolution appends one exact-schema `index`
  comment on the map, and the index is the deterministic replay of those
  comments — two resolutions running at once append two records and can never
  overwrite each other, or Bryan.
- **Tokens never surface, and never travel to an unexpected host.** The default
  transport is Tea, which holds its own credential. Direct-token mode is opt-in
  and refuses any host not explicitly allowlisted; redirects are refused
  outright, because a redirect is how a credential leaves the host it was meant
  for.
- **Append-only managed state.** Every piece of adapter-owned state is a
  created issue or a created comment carrying a stable versioned marker.
  Nothing the adapter does edits existing text, so human prose and comments
  can never be overwritten — at any interleaving.
- **Every write is read back.** A write without a readback is an unverified
  claim.
- **Exact scoping.** No operation closes, deletes, labels, comments on, or
  assigns anything outside the map and ticket set explicitly supplied.

## Concurrency

Bryan may run unblocked tickets in parallel, so expect other sessions to be
editing the tracker at the same time.

Claiming is **append, then arbitrate by server order**: post one claim comment,
re-read every managed record, and replay them in Forgejo's comment-id order.
The **earliest unreleased operation wins**; anyone else stands down and takes
the next frontier ticket. Because every contender computes the winner from the
same ordered comment list, the outcome does not depend on whose write landed
last — which is what makes it safe rather than merely likely.

A claimed timestamp never overrides comment order. A session with a skewed
clock cannot take a ticket from an earlier claimant.

**Ownership is an identity tuple, not a single token.** A claim is owned by
`(operation, session)`. Both halves are load-bearing:

- *session alone* is not ownership — one session legitimately runs nested or
  concurrent operations, and a release matching on session would clear a
  sibling operation's claim;
- *operation alone* is not ownership either — every operation id is written
  into a tracker comment, so anything that can read the issue can quote it
  back. An id is a handle, not a credential.

So:

- a release names the **exact acquisition** it releases — operation and
  session — and clears nothing else;
- a second acquisition from the same session is a genuine contender, not a
  no-op, so one session never holds two overlapping claims on the same ticket;
- a retry carrying the **identical** operation id recognizes its own earlier
  record and posts nothing — that is the only idempotent case.

A contender that posted a claim and then lost **withdraws its own operation**
before standing down, and verifies that exact operation is inactive. Leaving it
queued would hand the ticket to a session that already walked away the moment
the winner released.

**The decision index needs no such machinery.** Indexing a decision is an
append — one `index` comment on the map — and the index is the replay of those
comments in server order, first record per resolution key. Concurrent
resolutions cannot overwrite each other, retries converge on one entry
whatever their wording, and there is no lock a crashed session could leave
held.

**Only the current claimant operation may resolve a ticket.** Two sessions
cannot resolve the same decision differently, and neither can two operations of
one session.

An interrupted session leaves a stale claim. Stale claims are **surfaced for
explicit reclaim**, never silently expired: a claim that looks abandoned may be
a session that is simply slow, and stealing it loses work. Read the exact
operation to recover from `claim-status`, which prints the recovery command
verbatim.

**A queued acquisition is recoverable by name.** When a loser's withdrawal
itself fails, its record sits behind the current winner and becomes the holder
the moment the winner releases. `release` therefore reaches a queued
acquisition as well as the current holder, clearing exactly the identity named
and verifying the winner is untouched. `claim-status` lists queued acquisitions
alongside the holder, each with its verbatim recovery command — recovery cannot
target what inspection does not show.

If safety and authority ever drift — the tracker flips public, a label
disappears, the map stops being identifiable, the claim changes hands — the
adapter **fails closed** before the next write and reports the exact refusal.
An interrupted resolution is finished by re-running the same resolve; a
resolution counts as successful only when its resolution comment, an index
record with its exact key replaying as the ticket's *current* decision, and
the closed ticket all read back.

**Privacy is the last thing checked before every write.** Identity, metadata,
ownership, and dependency reads all happen first; `require_private()` is the
final network round trip before the single mutation, and the write itself reads
nothing. Checking privacy first and then issuing three more reads would leave a
window in which the repository goes public while the adapter is still deciding —
and the write would land on a tracker it had already approved.

## Invocation

Two modes. Either way, **never resolve more than one ticket per session**, with
the exception of research tickets.

### Chart the map

Bryan invokes with a loose idea.

1. **Name the destination.** Load `grilling` to pin down what this map is finding
   its way to — the spec, decision, or change. The destination fixes the scope,
   so it is settled first.
2. **Map the frontier.** Grill again, **breadth-first**: fan out across the whole
   space rather than deep on one thread, surfacing the open decisions and the
   first steps takeable now. **If this surfaces no fog**, stop — you do not need
   a map. Say so and ask how Bryan wants to proceed.
3. **Resolve the tracker.** Origin remote plus Bryan's explicit choice. Confirm
   the repository is private.
4. **Preview, then create the map** with Destination and Notes filled in,
   Decisions-so-far empty, and the fog sketched into Not yet specified.
5. **Preview, then create the tickets you can specify now**, and wire blocking
   edges in a **second pass** — issues need ids before they can reference each
   other. Wiring sorts them into the frontier and the blocked. Create previews
   print a **creation identity**; apply requires the same `--creation`, and a
   retry with it converges on the issue the first attempt made instead of
   duplicating the map or ticket.
6. **Resolve research tickets in parallel** where the host supports it, capturing
   findings as a context pointer on the ticket rather than pasted into it.
7. **Stop.** Charting is one session's work; it resolves nothing by hand.

### Work through the map

Bryan invokes with a map. A ticket is optional — without one, *you* pick the next
decision, not him.

1. Load the **map** at low resolution. Not every ticket body.
2. Choose the ticket: the one Bryan named, else the first frontier ticket in
   order. **Claim it before any work**, and confirm the claim by readback.
   **Keep the operation id the claim preview prints** — applying requires that
   exact `--operation`, so the record posted is the record reviewed — together
   with the session name: release and resolve need both, and no other pair
   will do.
3. Resolve it. Zoom as needed — fetch the full body of any related or closed
   ticket on demand. Load whichever skills the map's Notes name; when in doubt,
   `grilling`.
4. **Preview, then record the resolution**: post the answer as a resolution
   comment, post one index record on the map — the decision's gist, bound to
   this exact ticket and answer — and close the issue **last**, so the
   decision of record is published before the ticket leaves the frontier. The
   operation is resumable: if it fails part-way, running it again completes
   only the steps that did not land, converging on one comment, one index
   entry, and one closed ticket whatever the retry's wording. Only the
   operation holding the claim may resolve. A changed answer for a closed
   ticket is refused: corrections reopen the affected decision, and the
   re-resolved answer supersedes the old index record at replay — history
   stays append-only, and each ticket has at most one current decision.
5. Add newly surfaced tickets (create, then wire). Graduate any fog the answer
   made specifiable — the graduated question lives in its new ticket. The map
   body's "Not yet specified" list is Bryan's prose; note stale fog lines for
   him in an ordinary map comment rather than editing the body. If the answer
   reveals a ticket sits beyond the destination, rule it out of scope rather
   than resolving it on the route. If the decision invalidates other parts of
   the map, update those tickets.

## Handoff

The map ends where implementation begins. When the route is clear:

- the accepted decisions become a durable Git artifact — a plan, spec, or ADR —
  via `issue-plan` or `adr-and-spec-coach`;
- implementation goes through `issue-create` and `issue-work` under normal
  execution authority;
- the map stays as the decision record, not as a work queue.

## Related

- `grilling` — the single-session deliberation this skill dispatches to.
- `issue-plan`, `issue-create`, `issue-work` — the implementation route out.
- `dx-target`, `dx-preview` — SGG interface prototypes; see the routing reference.
- `worktrunk` — trunk resolution when a ticket needs repository state.
