# Design it twice

When exploring alternative interfaces for a chosen deepening candidate. Based on
"Design It Twice" (Ousterhout): your first idea is unlikely to be the best. Uses
the vocabulary in [`../SKILL.md`](../SKILL.md). Adapted from Matt Pocock's
`codebase-design/DESIGN-IT-TWICE.md`; see
[`dot-agents/upstreams/mattpocock-skills.json`](../../../upstreams/mattpocock-skills.json).

## 1. Frame the problem space

Before spawning anything, write a short explanation of the problem space for the
chosen candidate:

- the constraints any new interface must satisfy;
- the dependencies it relies on, and their category from
  [`deepening.md`](deepening.md);
- a rough illustrative sketch — to make the constraints concrete, **not** a
  proposal.

Show it, then proceed immediately. The reader thinks while the alternatives are
being drafted.

## 2. Draft radically different alternatives

Three or more, each under a **different design constraint**, so they disagree
about structure rather than about naming:

- **Minimize the interface** — 1–3 entry points maximum; maximize leverage per
  entry point.
- **Maximize flexibility** — support many use cases and extension.
- **Optimize for the most common caller** — make the default case trivial.
- **Ports and adapters** — when a cross-seam dependency dominates.

Draft them in parallel where the host supports it (Hermes `delegate_task`,
otherwise `Task`/`Agent`); on Hermes never exceed three active children. Serial
drafting works, but write each one before reading back the last — the value is
independence, and a serial pass tends to converge on the first design.

Each brief carries the file paths, coupling details, dependency category, what
sits behind the seam, the vocabulary from [`../SKILL.md`](../SKILL.md), and the
project's own domain terms, so all of them name things consistently.

Each alternative outputs:

1. the interface — types, entry points, parameters, plus invariants, ordering,
   and error modes;
2. a usage example showing how callers use it;
3. what the implementation hides behind the seam;
4. dependency strategy and adapters;
5. trade-offs: where leverage is high, where it is thin.

## 3. Compare and recommend

Present the designs one at a time so each can be absorbed, then compare them in
prose along three axes: **depth** (leverage at the interface), **locality**
(where change concentrates), and **seam placement**.

Then give your own recommendation: which is strongest and why. If elements from
different designs combine well, propose the hybrid explicitly. Be opinionated —
a menu is not a recommendation.
