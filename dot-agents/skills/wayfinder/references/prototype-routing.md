# Prototype routing

A `prototype` ticket exists to raise the fidelity of a discussion: build
something cheap and concrete to react to, so the decision is made against a real
artifact instead of everyone's imagination. This reference decides *which*
artifact.

Adapted from Matt Pocock's `prototype` (`LOGIC.md`, `UI.md`); see
[`dot-agents/upstreams/mattpocock-skills.json`](../../../upstreams/mattpocock-skills.json).

## Route by the blocking question

| Blocking question | Route |
|---|---|
| "Is this technically feasible / will this approach even work?" | `spike` |
| "Does this logic or state model feel right?" | `spike`, plus a shareable state walkthrough (below) |
| "What should this look like?" (general UI alternatives) | `sketch` |
| "What should the SGG target consumer or plugin interface be?" | `dx-target` |
| "Am I happy with the SGG interface we built?" | `dx-preview` |

Getting the branch wrong wastes the whole prototype, because the shapes produce
entirely different artifacts. If the question is genuinely ambiguous and Bryan is
not reachable, pick the branch matching the surrounding code (a backend module →
feasibility or logic; a page or component → UI) and state the assumption at the
top of the artifact.

## Runtime availability

The routes above are **named workflows, and where they exist they are the
route.** They are not all available on every harness:

| Route | Where it lives | Elsewhere |
|---|---|---|
| `spike` | builtin Hermes skill (`software-development/spike`) | use the inline feasibility/logic procedure below |
| `sketch` | builtin Hermes skill (`creative/sketch`) | use the inline UI-variants procedure below |
| `dx-target`, `dx-preview` | canonical pool; curated for Hermes | pooled and curated only for Hermes — on Claude/OpenCode, hand the session to Hermes rather than improvising an SGG interface target |

**On Hermes: load the named skill.** Do not reimplement it from the fallback
below — the builtin is the maintained version, and duplicating it here is how the
two drift apart.

**On Claude or OpenCode**, where `spike` and `sketch` are not installed, use the
bounded inline procedure for that shape. Say which you did, so the artifact is
not mistaken for the output of the named workflow. If the decision is
consequential and Hermes is available, prefer handing it over.

## Inline fallback: feasibility spike

*Only when `spike` is unavailable.*

The question is whether an approach works at all.

Write the smallest possible thing that would fail if the approach is unsound —
one call against the real API, one query against real-shaped data, one build with
the actual toolchain. Not a slice of the eventual implementation; the cheapest
possible disproof.

Record the verdict on the ticket in one line — *what was tried, what happened,
what it means for the decision* — and link the spike. The verdict is the
deliverable; the code is evidence.

## Inline fallback: logic walkthrough

*Only when `spike` is unavailable.* Pairs with a feasibility spike when the
question is about behavior rather than possibility.

1. **State the question in one paragraph, visibly**, at the top of the artifact.
   A prototype answering the wrong question is pure waste.
2. **Isolate the logic in a portable module** — a pure reducer, a state machine,
   a small set of pure functions, whichever fits. No DOM, no handlers reaching
   inside it. The page around it is a disposable shell; this module is written
   deliberately production-grade so it *can* graduate. Graduation is not
   automatic: it enters the real code only through the owning project's normal
   review and publication gates, like any other change (see rule 5).
3. **Surface the complete state** after every action, as labelled fields in
   domain language, not a raw dump. Call out what just changed.
4. **Provide free-play controls plus guided walkthroughs.** One control per
   action, always available; then ordered scenarios — the happy path, a genuinely
   awkward edge case, and an attempt at something that *should be illegal*. Each
   walkthrough resets to a known initial state so it runs the same way twice.

The illegal-attempt scenario is what earns the prototype. "Wait, that shouldn't
be possible" is a bug in the *idea*, which is what you came for.

Keep it runnable with no install — a single self-contained file someone can open
— when a non-developer needs to drive it.

## Inline fallback: UI variants

*Only when `sketch` is unavailable.*

**Prefer an existing page.** Variants rendered on a real route, against real
data, density, and chrome, are judgeable; a variant alone on a throwaway route
looks fine in a vacuum, which tells you nothing. Only create a new route when the
thing genuinely has no existing page to live inside.

- **Default to 3 variants**, capped at 5. Past that they stop being different
  and start being noise.
- **Switch with a stable `?variant=` URL parameter** so a variant is shareable
  and survives reload, with an obvious in-page switcher visually distinct from
  the design being judged.
- **Variants must differ structurally** — different layout, information
  hierarchy, primary affordance. Three tweaked card grids is wallpaper. If two
  drafts come out similar, redo one under an explicit "do not use that
  structure" constraint.
- **Read-only.** Point anything that would mutate at a stub. The question is what
  it should look like, not whether the backend works.

The useful feedback is usually *"the header from B with the sidebar from C"* —
that hybrid is the actual design.

## Rules for all shapes

1. **The shell is throwaway from day one, and marked as such.** Locate it next
   to what it is prototyping so context is obvious, and name it so a casual
   reader can see it is not production.
2. **Trivial to run.** One command, or one file to open.
3. **No persistence by default.** State lives in memory unless persistence is the
   question, in which case use a scratch store with an obvious "wipe me" name.
4. **Skip the polish.** No tests, no abstractions, no error handling beyond what
   makes it run. A prototype that needs tests is no longer a prototype. (The
   logic walkthrough's portable module is the exception here as in rule 5: it
   is deliberately clean, and it picks up its tests when it graduates through
   the owning project's gates.)
5. **Never promote prototype *shell* code to production.** The page, the
   controls, the wiring — anything written under prototype constraints — gets
   rewritten properly when folding the decision in. The one exception is the
   logic walkthrough's deliberately isolated portable module (step 2 above),
   which was written production-grade on purpose: it may graduate, but only
   through the owning project's normal review and publication gates, never by
   being copied in because the prototype "already worked".

## Capture and retention

Record the **answer** — the verdict and the question it settled — on the
decision ticket. That is what the map needs.

Do **not** automatically commit a prototype branch, and do not assume every
prototype is worth keeping. Retention follows the owning project's rules and its
publication gates: some prototypes are worth preserving as primary sources, most
are worth deleting once the decision is recorded, and either way it is Bryan's
call, made explicitly.
