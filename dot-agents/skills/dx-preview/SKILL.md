---
name: dx-preview
description: Use when reviewing the developer experience of a branch or PR before finalizing it — you want to see what a plugin author and a consumer would write and receive against a new endpoint, protocol spec, or SDK surface in the SGG / CommonGrants repos. Triggers "show me examples of using this", "preview the DX", "what would an author/consumer write against #N", "am I happy with the end result", /dx-preview.
---

# dx-preview

## Overview

Read-only DX review of a branch or PR. Given a ref, show what a **plugin author** and a **consumer** would write and see against the changed surface — requests, response payloads, and authoring code — so the reviewer can judge whether the end result feels right *before* committing to it.

**Core principle:** illustrate only what you've read. This is a preview, not a proof — it never has to build, install, or run anything to succeed.

**Not this skill's job:** proving correctness / regression. That's the runnable consumer playground (`~/code/sgg/sgp-consumer-playground/`). If the ask is "does the contract hold" / "test it", point there instead.

## Procedure

Follow in order. Each step is required unless marked optional.

1. **Resolve the exact ref you were handed.** `/dx-preview <PR-url | PR-number | branch>` previews *that* ref — never the local checkout's current branch, unless the user explicitly passes `--local`.
   - The PR head often lives in a git worktree while the main checkout sits on the base branch (e.g. `HOLD-filters`). Find the head ref (`gh pr view <N> --json headRefName,baseRefName`; locate the worktree with `git worktree list`) and read from there. Previewing the wrong branch = previewing stale surface. This is the single most common way to be confidently wrong.

2. **Classify: repo + changed surface + which personas apply.** Diff the head against its base. Identify the repo and map it to personas (table below). If a persona genuinely isn't touched by the change, say so in one line — do not manufacture a hollow example to fill the slot.

3. **Ground from what the branch already ships.** Read, in this priority order: the branch's own `examples/`, its tests, then the changed source (schemas / `.tsp` / route handler / SDK exports). For a `.tsp` change, trace it *through* to the emitted json-schema/openapi + SDK public exports — the consumer sees what it compiles to, not the `.tsp`. Derive request/response payloads from the source (the classifier/serializer/schema). Run code live ONLY if a payload genuinely can't be derived from source AND running is cheap — do not monkeypatch transports or fabricate fixtures for a DX eyeball.

4. **Present the output contract** (below).

5. **Save to the vault. Always.** Follow the `vault-pkm` skill's conventions for placement and frontmatter. A DX preview is event-shaped, keyed to the ref: filename `dx-preview-pr<N>-<slug>.md` (or `dx-preview-<branch-slug>.md` if no PR), linked from a relevant MOC. **On a follow-up question, find and update that same note — never spawn a second one.** Present inline first; the vault note carries the same content.

## Repo-aware personas

| Repo | Change | Consumer persona | Plugin-author persona |
|------|--------|------------------|-----------------------|
| `simpler-grants-gov` | endpoint | HTTP caller: request + response payload | usually N/A → say so |
| `simpler-grants-protocol` | `.tsp` / SDK surface | uses SDK types / hits the endpoint | extends SDK (`define_plugin`/`definePlugin`, filters, transforms) |
| `ts-cg-grants-gov` / `py-cg-grants-gov` | plugin API | downstream use of the plugin | writing against the changed plugin API |

## Output contract

State what the preview IS — these parts, in this order:

- **Per applicable persona, a few grounded scenarios:**
  - *Consumer* — a basic request + its response payload; a feature-exercising request (the new filter/field/endpoint) + its payload; one error/empty/rejected case + its payload.
  - *Plugin author* — the minimal registration/extension; one realistic non-trivial one.
- **Payloads are shown, not just described** — the request body a consumer sends and the response shape they get back, in fenced blocks.
- **Grounding tag** — for each persona block, name the source file(s) it was drawn from, so the reviewer can trust or spot-check it.
- **DX notes** (see shape below) — only where a genuine wrinkle surfaced.

## DX notes: the shape

State each wrinkle you actually hit as a **fact**, grounded in a file: *"`define_plugin`'s first positional arg is required; `Config` raises without `api_key`."* *"Range filters have no alias, unlike scalar filters (`filters/opportunity.py`)."*

Do **not** convert wrinkles into decisions for the reviewer: no "worth deciding whether that's acceptable", no "you should consider", no invented open questions. Report what is; the reviewer decides what to do. If nothing notable surfaced, write nothing — an empty DX-notes section beats filler.

## Grounding (prime directive)

Every field name, type, and signature in an example must trace to something read in step 3. If the surface can't be grounded — ref won't resolve, files unreadable, change is opaque — say so and stop. A plausible-but-wrong preview is worse than none: it manufactures confidence in DX that doesn't exist.

## Common mistakes

| Mistake | Fix |
|---------|-----|
| Previewing the local checkout's current branch | Resolve the handed ref; the head is often in a worktree while main sits on the base |
| Skipping the vault save | Always save + link; update the same note on follow-ups |
| "Worth deciding whether…" DX notes | State the wrinkle as a fact; the reviewer decides |
| Running the SDK live / monkeypatching to get a payload | Derive it from the classifier/schema source; run only if cheap and unavoidable |
| Filling both persona slots when the change touches one | Say which persona isn't touched and why, in one line |
