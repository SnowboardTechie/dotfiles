---
name: adr-and-spec-coach
description: >
  Use when a technical decision is still open and needs to be captured as an
  ADR or tech spec — weighing architectural options, choosing between
  approaches, unsure what the design should be, or new to ADRs/specs and
  wanting to be guided through the decision rather than handed a finished
  document. Triggers: "help me write an ADR for…", "I'm deciding between X
  and Y", "help me think through this design", "write a tech spec for this
  feature", "I'm new to ADRs". If the decision is already settled and you only
  need to shape a draft to an existing repo's conventions, use
  conforming-tech-specs instead.
---

# ADR & Spec Coach

Guide the author from an open decision to a finished ADR or tech spec by
deliberating **with** them — one decision at a time, weightiest first — never
by silently deciding for them. The author makes every load-bearing call; this
skill surfaces the options, the trade-offs, and a reasoned recommendation so
the call is informed.

The failure mode this skill exists to prevent is **deciding for the author** —
emitting a polished document that buries the real choices, so the author
learns nothing and can't defend the result later. An ADR's whole value is the
record of *why this and not the alternatives*; if the author didn't weigh the
alternatives, the ADR is theater.

This skill owns the **deliberation + drafting** half of spec work. It does not
enforce repo conventions. When the repo has a conventions index, Phase 5
routes the finished draft into `conforming-tech-specs` for the conformance
pass.

---

## When to use

- The decision is genuinely open — more than one defensible answer.
- The author is new to ADRs/specs and wants to learn what to consider.
- Greenfield work with no established conventions index yet.
- Any "help me decide / help me think through" framing.

**When NOT to use:**

- The decision is already made and you only need to make a draft conform to
  repo conventions → `conforming-tech-specs`.
- Pure Q&A about an existing ADR ("what does ADR-0011 say?") → answer directly.
- A trivial change with no real decision → recommend a regular issue and stop.

---

## The spine

Five phases. Do not skip ahead to drafting — the draft is the *output* of the
deliberation, not a substitute for it.

### Phase 1 — Frame

Establish what is actually being decided, and which artifact fits:

- **ADR** — captures *one decision* and its alternatives. Use when the request
  is "which of these approaches do we pick."
- **Tech spec** — describes *a design* with many sub-decisions. Use when the
  request is "how should this whole feature work."

Teach the distinction the first time it comes up — the author is often new.
If it's an ADR, you're filling MADR anatomy (see `references/adr-anatomy.md`).
If it's a tech spec, you're filling the spec skeleton (see
`references/spec-anatomy.md`). Read the relevant reference before Phase 2.

### Phase 2 — Inventory and rank the decisions

Surface **every** choice the artifact must settle, then rank them by weight.
Use `references/decision-drivers.md` to drive this out.

**Weight = how hard to reverse × how many defensible answers.** A choice
that's expensive to undo *and* has several live options is load-bearing. A
choice with an obvious default and cheap reversal is trivial.

Output a **visible ranked agenda** — show it to the author:

```
Decisions to settle (heaviest first):
  1. [load-bearing] Session store: Redis / Postgres table / signed JWT
  2. [load-bearing] Revocation model: server-side / token-expiry only
  3. [medium]       Session TTL and refresh policy
  4. [trivial]      Cookie name and attributes (sensible default exists)
```

This agenda is the thing you descend in Phase 3. Triage sets **order and
depth**, not what gets skipped — every decision is still deliberated, the
trivial ones just go fast.

### Phase 3 — Descend the agenda, one decision per turn

Top of the agenda first. For **each** decision, in its own turn:

1. Name the decision and say why it carries the weight it does.
2. Lay out 2-3 **genuine** options (not strawmen).
3. Give the trade-offs — what each option buys and costs — tied back to the
   decision drivers from Phase 2.
4. Give a **recommendation with your reasoning.** Do not withhold an opinion;
   the author learns judgment from seeing *why* you'd lean a way. Make clear
   it's their call.
5. Ask the author to choose. Use `AskUserQuestion` when the options are
   discrete; plain prose when the choice is open-ended.

Trivial decisions still get surfaced, but compressed: state the default, name
the one trade-off worth knowing, let the author rubber-stamp in a beat.

Record each settled decision (option chosen + the driver that decided it) as
you go — those become the ADR's Decision/Consequences or the spec's
Alternatives section.

### Phase 4 — Assemble the draft

Populate the right anatomy from the settled decisions:

- **ADR:** Context → Decision Drivers → Options Considered → Decision →
  Consequences. (`references/adr-anatomy.md`)
- **Tech spec:** Goals/Non-Goals → Proposed Design → Alternatives Considered →
  Risks → Rollout/Testing. (`references/spec-anatomy.md`)

The Options Considered / Alternatives section is not optional padding — it is
the record of the Phase 3 deliberation. Each rejected option gets a line on
why it lost. Name what each section is *for* if the author is learning.

### Phase 5 — Route or finalize

- **Repo has a conventions index** → invoke `conforming-tech-specs`, handing it
  the draft plus the decision record, so it runs the prior-art / conformance
  gate. Tell the author you're doing this and why.
- **No index (greenfield / learning)** → finalize the draft in place and hand
  it to the author for review.

**Do not commit. Do not post. Do not open a PR.** This skill produces content
and stops. The author decides where it lands (ADR file, Google Doc, issue).

---

## Interaction contract (hard rules)

- **One decision per turn. Never bundle questions.** Even "quick orienting"
  questions go one at a time — the answer to one usually reshapes the next.
  Showing the Phase 2 agenda and inviting the author to correct its *ordering*
  is not a second question — it's framing. But only ever put **one decision**
  to the author per turn; "while you're here, also pick X" is the bundling the
  contract forbids.
- **Weightiest decision first**, descend toward trivial.
- **Every load-bearing decision gets options + trade-offs + a reasoned
  recommendation, and the author chooses.** Recommending is required;
  deciding is forbidden.
- **Never finalize a draft with a load-bearing decision silently filled in.**
  If you notice an un-deliberated load-bearing choice in Phase 4, go back to
  Phase 3 for it.
- **Teach as you go** — name what each section/driver is for the first time it
  appears. The author is often new; the learning is half the point.

---

## Red flags — STOP

You are about to break the contract if you catch yourself:

- Writing a numbered list of questions in one message ("A few things: 1… 2… 3…").
- Thinking "these are related, I'll batch them" or "just a few quick questions."
- Withholding a recommendation to seem neutral ("it depends on your needs").
- Drafting the full document before the decisions are settled.
- Filling in a load-bearing choice yourself because asking feels slow.

All of these mean: back up. One decision, options, a real recommendation, then
the author chooses.

## Rationalizations

| Excuse | Reality |
|--------|---------|
| "Batching questions is more efficient" | The author asked for one-at-a-time. Q1's answer reshapes Q2 — batching wastes the later questions. |
| "I shouldn't bias them, so no recommendation" | A reasoned recommendation is how they learn judgment. Withholding it isn't neutral — it's unhelpful. They still choose. |
| "This decision is obvious, I'll just pick it" | If it's truly trivial, surface it as trivial and let them rubber-stamp. If it's load-bearing, it's not yours to pick. |
| "They're experienced, they can handle a batch" | The skill's value is per-decision deliberation. Experience doesn't change the one-at-a-time contract. |
| "Let me just draft it and they'll edit" | A finished draft buries the choices. Deliberate first; the draft is the output, not the method. |
