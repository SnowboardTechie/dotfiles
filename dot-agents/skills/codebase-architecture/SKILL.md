---
name: codebase-architecture
description: Shared vocabulary and method for deep modules — module, interface, depth, seam, adapter, leverage, locality. Use when designing or reshaping a module's interface, deciding where a seam goes, surveying a codebase for deepening opportunities, making code more testable, or when another skill needs the deep-module terms.
---

# Codebase Architecture

Design **deep modules**: a lot of behavior behind a small interface, placed at a
clean seam, testable through that interface. The aim is leverage for callers,
locality for maintainers, and testability for everyone.

Two uses, and they are different sizes:

- **As a vocabulary** — another skill (`tdd`, `code-review`, `diagnosing-bugs`)
  needs the terms. Read the glossary and the principles; do not start a session.
- **As a survey** — the user asks what is worth deepening here. Run the process.

Provenance: adapted from Matt Pocock's `codebase-design` and
`improve-codebase-architecture`, merged into one skill. Upstream pin, accepted
and rejected upstream rules, and the watched source list live in
[`dot-agents/upstreams/mattpocock-skills.json`](../../upstreams/mattpocock-skills.json).

## Glossary

Use these terms **exactly**. Do not substitute "component", "service", "API", or
"boundary" — consistent language is the whole point.

**Module** — anything with an interface and an implementation. Deliberately
scale-agnostic: a function, class, package, or tier-spanning slice. *Avoid*:
unit, component, service.

**Interface** — everything a caller must know to use the module correctly: the
type signature, but also invariants, ordering constraints, error modes, required
configuration, and performance characteristics. *Avoid*: API, signature — both
too narrow, referring only to the type-level surface.

**Implementation** — what is inside a module. Distinct from **adapter**: a thing
can be a small adapter with a large implementation (a Postgres repository) or a
large adapter with a small one (an in-memory fake).

**Depth** — leverage at the interface: how much behavior a caller or test can
exercise per unit of interface they must learn. **Deep** = a lot of behavior
behind a small interface. **Shallow** = an interface nearly as complex as the
implementation.

**Seam** *(Michael Feathers)* — a place where you can alter behavior without
editing in that place; the *location* where a module's interface lives. Where to
put the seam is its own decision, distinct from what goes behind it. *Avoid*:
boundary — overloaded with DDD's bounded context.

**Adapter** — a concrete thing satisfying an interface at a seam. Describes the
*role* it fills, not what is inside it.

**Leverage** — what callers get from depth: more capability per unit of
interface learned. One implementation pays back across N call sites and M tests.

**Locality** — what maintainers get from depth: change, bugs, knowledge, and
verification concentrate in one place instead of spreading across callers. Fix
once, fixed everywhere.

## Principles

- **Depth is a property of the interface, not the implementation.** A deep
  module may be internally composed of small swappable parts; they are simply
  not part of its interface. A module can have **internal seams** (private,
  used by its own tests) as well as an **external seam** at its interface.
- **The deletion test.** Imagine deleting the module. If complexity vanishes, it
  was a pass-through. If complexity reappears across N callers, it was earning
  its keep.
- **The interface is the test surface.** Callers and tests cross the same seam.
  Wanting to test *past* the interface means the module is the wrong shape.
- **One adapter means a hypothetical seam. Two means a real one.** Do not
  introduce a seam unless something actually varies across it.

### Deep vs shallow

Deep — small interface, substantial implementation:

```
┌─────────────────────┐
│   small interface   │  few entry points, simple params
├─────────────────────┤
│  deep implementation│  complexity hidden here
└─────────────────────┘
```

Shallow — large interface, thin implementation (avoid):

```
┌─────────────────────────────────┐
│        large interface          │  many methods, complex params
├─────────────────────────────────┤
│  thin implementation            │  mostly passes through
└─────────────────────────────────┘
```

When designing an interface: can I reduce the number of entry points? Can I
simplify the parameters? Can I hide more complexity inside?

### Designing for testability

1. **Accept dependencies, do not create them.** `processOrder(order, gateway)`
   is testable; `processOrder(order)` constructing its own gateway is not.
2. **Return results, do not mutate in place.** `calculateDiscount(cart):
   Discount` is testable; `applyDiscount(cart): void` is not.
3. **Small surface area.** Fewer entry points, fewer tests; fewer parameters,
   simpler setup.

## Survey process

Run this only when the user asks what is worth deepening.

### 1. Scope before you scan

Deepening pays off by making *future* changes easier, so weight the parts that
have recently changed.

- If the user named a direction (a module, a subsystem, a pain point), take it.
- Otherwise walk the commit history (`git log --oneline`) for hot spots — the
  files and areas that keep coming up — and let those pull your attention first.
  If changes are scattered with no hot spot, widen the net.

Read the project's domain glossary and any ADRs in the area first. ADRs record
decisions this survey should not re-litigate.

### 2. Explore

Walk the code — delegate this if the host supports it — and note where you
experience friction, rather than following rigid heuristics:

- Where does understanding one concept require bouncing between many small
  modules?
- Where is a module **shallow** — interface nearly as complex as implementation?
- Where were pure functions extracted for testability while the real bugs hide
  in how they are called (no **locality**)?
- Where do tightly coupled modules leak across their seams?
- What is untested, or hard to test through its current interface?

Apply the **deletion test** to anything you suspect is shallow.

### 3. Present candidates in the conversation

For each candidate: the files involved, the friction the current shape causes,
what would change in plain English, the benefit stated in **locality** and
**leverage** terms, how tests would improve, and a strength — `Strong`,
`Worth exploring`, or `Speculative`. End with which one you would tackle first
and why.

If a candidate contradicts an existing ADR, surface it **only** when the
friction is real enough to warrant reopening that ADR, and mark it as such. Do
not enumerate every refactor an ADR forbids.

Do **not** propose interfaces yet. Ask which one to explore.

> Upstream writes this as a generated Tailwind + Mermaid HTML report opened in a
> browser. Not adopted: it puts a build artifact and a CDN dependency in the
> loop for something a conversation carries fine, and Bryan reviews in the
> terminal and in Obsidian. If a visual is genuinely load-bearing, produce one
> deliberately, not by default.

### 4. Work the chosen candidate

Load `grilling` and walk the decision tree: constraints, dependencies, the shape
of the deepened module, what sits behind the seam, which tests survive.

- Naming the deepened module after a concept the project's glossary lacks? Add
  the term there.
- Candidate rejected for a load-bearing reason a future reviewer would need?
  Offer an ADR so the next survey does not re-suggest it. Skip ephemeral reasons
  ("not worth it right now") and self-evident ones.
- Want alternative interfaces? Use
  [`references/design-it-twice.md`](references/design-it-twice.md).

## References

- [`references/deepening.md`](references/deepening.md) — dependency categories,
  seam discipline, and replace-don't-layer testing.
- [`references/design-it-twice.md`](references/design-it-twice.md) — exploring
  several radically different interfaces in parallel, then comparing them.

## Related

- `tdd` — consumes this vocabulary when the seam is in question.
- `code-review` — Standards findings about interface shape land here.
- `diagnosing-bugs` — escalates here when no correct seam exists for a
  regression test.
- `adr-and-spec-coach` — for recording a rejected candidate as an ADR.
