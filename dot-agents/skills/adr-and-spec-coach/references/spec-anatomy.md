# Tech Spec Anatomy

A tech spec describes **a design** — usually several decisions bundled into
one coherent proposal for how a feature or system will work. Where an ADR
captures one decision, a spec captures the shape of the whole thing and the
sub-decisions inside it.

This is a general skeleton. If the repo has its own spec conventions (Goals /
Non-Goals headers, required sections), those win — and `conforming-tech-specs`
enforces them.

## Sections, and what each is *for*

### Goals / Non-Goals
What this design is trying to achieve, and — just as important — what it is
explicitly *not* trying to achieve. Non-Goals are the cheapest scope control
you have: they pre-empt the "but what about X?" reviews by saying "X is out,
on purpose." Name them early.

### Context / Background
What exists today, what problem this solves, what constraints are fixed. The
reader needs enough to evaluate the design without already knowing the system.

### Proposed Design
The actual shape: components, data flow, interfaces, the key mechanisms. Lead
with the load-bearing decisions (the ones the deliberation surfaced as
heaviest), then the supporting detail. A reader should be able to hold the
design in their head after this section.

### Alternatives Considered
The other designs you weighed and why they lost. **This is the spec's
equivalent of an ADR's Options Considered** — the record that the chosen
design beat real competition, not strawmen. Each alternative gets the driver
that knocked it out. Skip this and reviewers will re-propose the alternatives
you already rejected.

### Risks / Open Questions
What could go wrong, what you're unsure about, what you're explicitly
deferring. Naming a risk is not weakness — it's how reviewers know where to
focus, and how future-you knows what to watch.

### Rollout / Migration
How this ships safely: phasing, feature flags, backfills, the rollback plan.
A design that can't be rolled out incrementally is a design with a hidden
risk. (`N/A — greenfield, nothing to migrate` is a valid answer; the explicit
N/A forces the thinking pass.)

### Testing
How you'll know it works: what's unit-tested, what needs integration or
end-to-end coverage, what's hard to test and why.

## Cross-cutting axes (sweep these — most will be N/A, say so)

Security · Privacy · Observability · Reliability · Performance · Cost ·
Operations. For each, the spec either addresses it inline or records
`N/A — <reason>`. The explicit N/A forces a thinking pass rather than silence.

## Smell tests

- No Non-Goals → scope is unbounded; reviewers will expand it for you.
- No Alternatives Considered → the design reads as the only option, which it
  never is.
- Rollout missing on a change to a live system → the riskiest part is undocumented.
