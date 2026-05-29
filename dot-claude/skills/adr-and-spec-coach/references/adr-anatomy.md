# ADR Anatomy

An ADR (Architecture Decision Record) captures **one decision**, the forces
that shaped it, the alternatives weighed, and what the team now has to live
with. It is a record for the future reader who asks "why on earth did we do it
this way?" — the answer should be in the ADR, with its context intact.

This is the lightweight MADR / Nygard shape. Use it verbatim unless the repo
has its own ADR template (if it does, that template wins — and you're probably
in `conforming-tech-specs` territory).

## Sections, and what each is *for*

### Title
A short noun phrase naming the decision and its outcome.
- ✅ "Use Redis for user session storage"
- ❌ "Session storage" (names the topic, not the decision)

### Status
`Proposed` → `Accepted` → later maybe `Superseded by ADR-NNNN`. The status is
how a reader knows whether this record is live or historical.

### Context
The forces at play: the problem, the constraints, what's already true about
the system, what you know and don't. **This is the hard part and the most
valuable part.** A reader who understands the context can often re-derive the
decision themselves. Write the context so they could.

Resist writing context as a sales pitch for the winner. State the forces
neutrally; the decision falls out of them.

### Decision Drivers (optional but recommended for the author who's learning)
The explicit criteria you judged options against — e.g. "must support
horizontal scaling," "should minimize new infrastructure." Naming drivers
*before* the decision stops you rationalizing backwards from a choice you'd
already made. Every option's evaluation references these drivers.

### Options Considered
The genuine alternatives, each with its trade-offs. **This is the record of
the deliberation** — not padding. For each option: what it buys, what it
costs, and (for the losers) the one driver that knocked it out. A reader
should see that the alternatives were taken seriously, not strawmanned.

### Decision
What you chose, stated plainly, and the driver(s) that decided it. One or two
sentences. "We will use Redis, because horizontal scaling (the dominant
driver) requires shared session state and Redis is already operated by the
platform team."

### Consequences
What gets better, what gets worse, and what you now have to live with. Honest
ADRs name the *negative* consequences too — the new operational dependency,
the failure mode you've accepted. This is what makes the record trustworthy.

## Smell tests

- The Options Considered section has only one real option → you didn't
  deliberate; you documented a foregone conclusion.
- Consequences lists only benefits → you wrote an advertisement, not a record.
- Context reads as justification for the Decision → reorder your thinking;
  context comes first and is neutral.
- The Decision restates the Title with no driver named → say *why*.
