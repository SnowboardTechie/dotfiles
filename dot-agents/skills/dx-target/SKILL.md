---
name: dx-target
description: Use at PLANNING time, before writing an implementation plan, when designing a consumer- or plugin-author-facing surface in the SGG / CommonGrants repos (a new endpoint, protocol spec, or SDK/extension surface) and you want to work backwards from the developer experience — explore how it could look, compare genuinely different shapes, and pick the target before building. Triggers "what should the DX look like", "design the target usage", "before we build it, show me", "how would a consumer/author write this", "work backwards from the DX", /dx-target. For reviewing the DX of an already-built branch/PR, use dx-preview instead.
---

# dx-target

## Overview

Front-loaded, **prescriptive** counterpart to `dx-preview`. Given a surface you're *about to build*, explore several ways it could look to a **plugin author** and a **consumer**, compare them, and pick the target — so the implementation plan becomes "make this snippet real," not an inward-facing task list. Working backwards from DX, in the currency of concrete usage code.

**Core principle — find the target, don't transcribe one.** You are exploring an option space, not writing down a design the user already holds. The output is *2-3 candidate shapes → a chosen target*, not one design.

**Not this skill's job:** reviewing the DX of code that already exists — that's `dx-preview` (descriptive, grounded against the changed code). dx-target is the inverse: it invents the not-yet-built shape. If the surface is already built and the ask is "how does this look / did the DX hold," point to `dx-preview`.

## Fenced invention (the honesty rule)

dx-target *may* invent — that's the point — but must fence what it invents, or it manufactures the same false confidence dx-preview exists to prevent, and the plan inherits the error.

- **Reused shapes** (existing filters/fields/types/helpers the snippet calls) must be **real and cited** — `file:symbol`. Never invent a helper that already exists under another name.
- **New shapes** are explicitly marked `# PROPOSED`.
- The `PROPOSED` set is a deliverable: it *is* the list of load-bearing decisions / ADR candidates that feed the plan.

## Procedure

Follow in order.

1. **Resolve, classify, and ground FIRST.** Identify the surface (issue / branch / feature description), the repo, and which personas the change touches (table below). Then **read the real catalog before sketching anything** — the existing consumer-facing surface the new shape will live beside (SDK exports, extension API, existing filter/field/transform shapes, schemas). Two things fall out of grounding, and both are load-bearing:
   - **What already exists vs. the genuine gap.** State it plainly. Do not re-propose a shape that already ships.
   - **Whether the ask is mis-framed.** Grounding often reveals the request assumes something untrue (e.g. "mirror what the other SDK got" when this side already has most of it). If so, **correct the framing before sketching** — a target built on a wrong premise wastes the whole exercise.

2. **Generate candidates via independent, distinct-angle agents.** Dispatch 2-3 agents in parallel (via `superpowers:dispatching-parallel-agents` if available, else parallel `Agent`/`Task` calls in one message) — **each designs exactly ONE candidate from a distinct angle**, independently. Pick angles that create a *real* fork for this surface, e.g.:
   - *max-type-safety* — strictest static guarantees, most annotation
   - *minimal-delta* — smallest change from what already ships
   - *most-flexible* — widest escape hatches / runtime generality
   - *most-discoverable* — best autocomplete/dot-drive ergonomics
   
   **Why independent agents, not one agent writing all variants:** a single agent collapses to near-neighbor variants of its first instinct ("really it's just points on one axis"). Independent agents committed to distinct angles produce genuinely different shapes to choose between. Each returns a fenced two-persona snippet (consumer call + author registration + expected response/error payload), reused-cited / new-`PROPOSED`.

3. **Compare, and report convergence honestly.** Lay the candidates side by side; trade-offs tied to the decision drivers (consumer type-safety, cross-SDK **contract** parity, minimal-delta, forward-compat, DX simplicity). Give a reasoned recommendation. **If grounding genuinely shows one honest shape** — the surface is narrow, the angles converged — say so and present the single target with *why there's no real fork*. Do not manufacture a fork to hit "3 options," and do not collapse a real fork into one option. Both are failures; the comparison names which case this is.

4. **Choice gate.** Present the candidates via `AskUserQuestion`, each candidate snippet as a **code preview** (rendered side-by-side), recommendation first. The user's pick becomes the target. **Do not end on an open-questions list** — fold any scope question into an option's trade-offs or into the recommendation, or make it a discrete option in the choice. (An unprompted "a few things to confirm…" tail is the manufactured-open-questions anti-pattern.)

5. **Persist and hand off — always.** A dx-target exploration is a design/plan artifact; it goes to the vault (per the specs-and-plans-go-to-vault rule) **even though it's exploratory** — this is the working-backwards record and the plan's acceptance oracle. Do not skip it because "it's just an exploration."
   - Save to the vault's `explorations/` folder (a dated thinking-session note, `YYYY-MM-DD-<feature-slug>.md`), following `vault-pkm` frontmatter/placement. This is a **separate folder from `dx-preview`** (which lives in `technical/`) by design — the two are decoupled; a dx-preview run must never trip over a target note.
   - The note holds all candidates + trade-offs + the chosen target.
   - Handoff: chosen target + its `PROPOSED` list → plan authoring (`superpowers:writing-plans`) as the acceptance oracle. **Rejected options become the "Alternatives Considered" record** — ADR-ready for `adr-and-spec-coach` / `conforming-tech-specs`.

## Repo-aware personas

dx-target carries its own copy of this table (kept independent of dx-preview by design).

| Repo | Change | Consumer persona | Plugin-author persona |
|------|--------|------------------|-----------------------|
| `simpler-grants-gov` | endpoint | HTTP caller: request + response payload | usually N/A → say so |
| `simpler-grants-protocol` | `.tsp` / SDK surface | uses SDK types / hits the endpoint | extends SDK (`define_plugin`/`definePlugin`, filters, transforms) |
| `ts-cg-grants-gov` / `py-cg-grants-gov` | plugin API | downstream use of the plugin | writing against the changed plugin API |

If a persona genuinely isn't touched, say so in one line — don't manufacture a hollow example.

## Common mistakes

| Mistake | Fix |
|---------|-----|
| One agent writes all "options" | Collapses to near-neighbor variants. Dispatch independent agents, one distinct angle each |
| Forcing 3 shapes when the surface has one honest shape | Present the single target + say why there's no real fork. Don't manufacture strawmen |
| Collapsing a real fork into graduated points on one axis | If distinct angles produce distinct shapes, keep them distinct — that's the choice |
| Sketching before grounding | Ground the catalog first; correct a mis-framed ask before proposing anything |
| Inventing a shape that already exists | Cite reused shapes `file:symbol`; state what already ships |
| Skipping the vault save ("just an exploration") | Always persist — it's the design record + the plan's oracle. `explorations/`, separate from dx-preview |
| Ending on an "open questions" list | Fold scope into an option's trade-offs, the recommendation, or a discrete choice |
| Auto-referencing a prior target from dx-preview | Decoupled by design; only cross them when explicitly asked |
