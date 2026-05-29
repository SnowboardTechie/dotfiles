---
name: conforming-tech-specs
description: >
  Conformance-gated pass for tech specs, ADRs, or new-endpoint design docs
  in repos with an established ADR / conventions index. Surfaces prior-art
  shapes before drafting, drafts conforming shapes verbatim, and requires
  every divergence to be justified in a final Conforms-to / Diverges-from
  table before handoff. Use when asked to "draft a tech spec for #N", "write
  the ADR for the new endpoint", "make this spec conform to our conventions",
  or similar. Does not coach the underlying decision (options, drivers,
  alternatives) — pair with adr-and-spec-coach for that. Does not provide
  general spec-body structure (Goals / Non-Goals / Rollout / Testing) — pair
  with project conventions for those.
---

# Conforming Tech Specs

Draft a tech spec or ADR by gathering prior art first, conforming to it by
default, and surfacing every divergence with an explicit ADR-exception
justification. The failure mode this skill exists to prevent is **citing an
ADR and writing around it** — disposition gap, not discovery gap.

This skill owns the **conformance** half of spec work — making a draft obey
established conventions and gating every divergence. It does **not** coach the
*decision* behind the spec (what to build, which options, what trade-offs).
For greenfield decisions or when you're weighing alternatives, run
`adr-and-spec-coach` first; it deliberates and drafts, then routes the draft
here when a conventions index exists.

The conform-by-default rule, pre-finalize checklist, and required artifact
table live in the host repo's `AGENTS.md` under `## TECH SPEC AUTHORING`.
This skill enforces the *flow*; it does not restate the rules.

---

## Customization point

Every repo using this skill needs a **conventions index** — a discoverable
markdown file enumerating established conventions with source links.

- **simpler-grants-protocol:** `vault/technical/protocol-conventions.md`
- **Other repos:** populate the equivalent file before running this skill.

If no conventions index exists in the current repo, stop and tell the user.
Do not synthesize one inline.

---

## Phase 0 — Is this spec-worthy?

Before invoking the conformance discipline, check that a full spec is what
the request actually needs. The skill's overhead (prior-art table,
divergence justifications, conforms/diverges gate) is wasted on changes
that have no protocol-shape decisions to make.

**Skip the skill and recommend a regular implementation issue when:**

- The change is a single-field addition to an existing model with no
  naming choice (the conventions index already settled the field type).
- The change renames or relocates an existing path/param/field with no
  consumer-visible shape change.
- The request is ad-hoc Q&A about an existing ADR ("what does ADR-0011
  say about cursor pagination?") — answer directly, no spec.
- The work sits inside an already-specced feature with no new
  shape-category being introduced.

**Invoke the skill when:**

- The change introduces a new endpoint, new query parameter family, new
  response shape, or new error shape.
- The request has protocol-shape ambiguity that more than one prior ADR
  could plausibly settle.
- The change is consumer-facing (SDK surface, public schema, OpenAPI
  output).
- An ADR exception is on the table.

If the request fails the "invoke" criteria, write a one-line
recommendation pointing to a regular implementation issue and stop.

---

## Phase 1 — Gather prior art

**Input:** the spec request (a feature, endpoint, ADR topic, issue number).

**Action:**

1. Enumerate every shape the spec will touch: endpoints, path parameters,
   query parameters, headers, request/response field names, response
   wrappers, error shapes, identifier types, status semantics.
2. For each shape, look it up in the repo's conventions index.
3. Grep the source-of-truth directories for shapes the index doesn't cover.
   In `simpler-grants-protocol`, that means:
   - `lib/core/lib/core/routes/` for verbs, paths, headers, parameter names
   - `lib/core/lib/core/models/` for field naming and response wrappers
   - `lib/core/lib/core/fields/metadata.tsp` for system timestamps
   - `website/src/content/docs/governance/adr/` for prior ADRs by topic
4. Read any ADR the request references before drafting. Citation is not
   satisfaction.

**Scaling the gather (judgment call):** when the spec touches many shape
categories across a large source tree, dispatch this gather via
`superpowers:dispatching-parallel-agents` — one `Explore` agent per
shape-category (routes / models / fields / prior-ADRs), each returning only
its prior-art-table rows. This isn't about speed so much as **context
isolation**: Phase 2 drafting wants a clean head, and raw grep output from
`routes/` + `models/` + `adr/` is noise the drafting context shouldn't carry.
For a small spec touching a handful of shapes, inline greps are fine — don't
spin up agents for three lookups.

**Output:** a **prior-art table**. One row per shape the spec needs:

| Shape needed                | Status                 | Source                                          |
|-----------------------------|------------------------|-------------------------------------------------|
| Pagination on list endpoint | conforms-to-existing   | ADR-0011 (`page` / `pageSize`)                  |
| Path parameter for org      | conforms-to-existing   | `{resource}Id` pattern → `orgId`                |
| Bulk sync filter shape      | new-territory          | (no precedent in `lib/core/.../routes/`)        |
| `modifiedSince` query param | conflicts-with-prior   | ADR-0011 uses page-based pagination, not deltas |

Status values:
- **conforms-to-existing** — convention covers this shape; the draft will
  use the established name/structure verbatim.
- **new-territory** — no prior convention; the draft proceeds normally and
  flags the new pattern for ADR consideration.
- **conflicts-with-prior** — the request as stated diverges from an
  established convention. Surface this to the user *before* drafting;
  default action is to reshape the request to conform.

**Escape hatch — prototype first when the table goes mostly `new-territory`.**
If your prior-art table fills with `new-territory` rows (most shapes are
unprecedented), the spec author probably doesn't know enough yet to
enumerate the right shapes. Stop and run a consumer-playground prototype
first (`~/code/sgg/consumer-playground/`, `ts/<feature>.ts` scenario);
return with the shapes the prototype taught you. The spec works better as
synthesis after experiential learning than as speculation before it.

The prior-art table is the input to Phase 2, not an afterthought.

---

## Phase 2 — Draft

**Input:** the prior-art table from Phase 1.

**Lead with Decision Drivers.** Before drafting shapes, open the spec
body with the MUST / SHOULD criteria the design must satisfy. Drivers
come from the request's actual user (see the host repo's `USERS, GOALS,
AND DECISION FRAMEWORK` section, e.g. "vendor engineer adapting existing
data to speak CommonGrants"), not from abstract principle. Every Phase 4
Diverges justification later binds to a specific driver — "this diverges
from ADR-0011 because MUST-driver X is incompatible" reads differently
than ad-hoc prose. Example:

- **MUST** preserve consumer-side type safety on filter responses
  (lead-user need: vendor plugins ship typed clients).
- **SHOULD** keep wire format aligned with existing pagination pattern
  (ADR-0011) to reduce adopter surprise.

**Action:**

1. For every `conforms-to-existing` row, the draft uses the established
   shape **verbatim** — same parameter name, same field name, same response
   wrapper, same casing. No paraphrases, no near-synonyms.
2. For every `new-territory` row, draft the new shape normally and note
   that it's a new pattern (Phase 3 will check whether an ADR is needed).
3. For every `conflicts-with-prior` row, the draft either conforms (the
   default) or includes the divergence with a placeholder ADR-exception
   subsection that Phase 4 will fill in.
4. Apply the repo's drafting voice rules:
   - structural facts and grounded rationale only — no "obviously",
     "we prefer", "significantly easier"
   - every technical claim cites a source or is marked `[unverified]`.
     Citation shape: `path:line` for a single anchor, `path (start-end)`
     for a span, each followed by a one-line purpose gloss (e.g.,
     `app/src/workspace/workspace.rs (120-220)` — "state/event handling
     this spec will change"). For ADRs, cite as `ADR-NNNN §section` when
     pointing at a specific section.
   - `[unverified]` means "I tried and couldn't confirm." Use
     `Assumption:` as a sibling marker for "I'm proceeding as if this is
     true, please confirm" — different semantics, different fix paths
     (verification vs. confirmation).
   - no fabricated assumptions about external system properties
   - each section earns its place — omit any that would restate another
     from a different angle or contain only boilerplate. Especially:
     don't pad with empty "Goals / Non-Goals / Out of Scope" headers
     when the surrounding prose already names them implicitly.

**Output:** spec body draft, with every cross-reference to prior art linked
to its source.

---

## Phase 3 — Consistency pass

**Input:** the draft from Phase 2 plus the prior-art table.

**Action:** walk the pre-finalize checklist from the host repo's
`AGENTS.md` → `## TECH SPEC AUTHORING` → `### Pre-finalize consistency pass`.
For `simpler-grants-protocol` that's:

- For each new **endpoint** → grep `lib/core/lib/core/routes/` for similar
  verbs and matching path conventions.
- For each **path parameter** → check existing routes for the
  `{resource}Id` pattern.
- For each **query parameter** → check ADR-0011 / ADR-0012 / ADR-0013.
- For each **header** → check existing routes for established header names.
- For each **response field** → grep `lib/core/lib/core/fields/metadata.tsp`
  and `lib/core/lib/core/models/`.
- For each **new pattern** → ask "is there an ADR that already settled
  this?" before introducing it.

**Cross-cutting sweep.** After the shape-category checklist, sweep the
cross-cutting axes. For each, the spec either addresses it inline or
records `N/A — <reason>`:

- **Security** — auth boundaries, input validation, exposed surface.
- **Privacy** — PII handling, log-redaction obligations.
- **Observability** — what's logged / metered for the new shape.
- **Reliability** — error paths, retry semantics, partial-failure modes.
- **Performance** — query cost, N+1 risk, payload size.
- **Cost** — storage, compute, third-party API spend.
- **Operations** — deploy / rollback / migration / versioning concerns.

Many of these will be `N/A` for most SGG specs — the explicit `N/A`
forces a thinking pass rather than silence. Diverges justifications must
name a specific cost in this dimension (what conformance would have
prevented), not a generic "more flexible."

This pass re-greps the same shape-categories as Phase 1; the same scaling
judgment applies — for a draft touching many shapes, dispatch the checklist
via `superpowers:dispatching-parallel-agents` (one agent per category,
each returning only its divergence flags) to keep the annotation pass out
of the drafting context. For a small draft, inline greps are fine.

**Citation check:** for every ADR or convention the draft cites, verify
the draft's shape actually matches what the ADR says. Citing ADR-0011 and
then specifying cursor pagination is the exact failure mode this gate
catches. Flag any cited-but-not-satisfied ADR as a divergence.

**Output:** an annotated draft where every potential divergence from prior
art is flagged inline (HTML comment, footnote, or margin marker — any form
the user can scan). Each flag carries: the convention diverged from, the
source link, and a one-line note on why the draft chose to diverge.

---

## Phase 4 — Conforms-to / Diverges-from table

**Input:** the annotated draft from Phase 3.

**Action:** append the required table at the end of the spec body. Use the
canonical shape from `AGENTS.md`:

| Aspect          | Convention                          | Conforms / Diverges     |
|-----------------|-------------------------------------|-------------------------|
| Pagination      | ADR-0011 `page`/`pageSize`          | Conforms                |
| Path identifier | `{resource}Id` (e.g. `orgId`)       | Conforms                |
| Timestamps      | `createdAt` / `lastModifiedAt`      | Conforms                |
| ...             | ...                                 | ...                     |

At minimum cover: pagination, identifiers, headers, field names, response
shapes. Add rows for any other convention the spec touches.

**Every `Diverges` row needs an inline ADR-exception justification
immediately under the table.** Each exception names the conflicting ADR,
states why conformance fails the use case, and proposes either a
superseding ADR or a scoped exception.

**Superseding-ADR shape.** When a Diverges row proposes a superseding ADR,
the proposal must specify:

- The new ADR's status line: `Proposed (Supersedes ADR-NNNN)`.
- Same handoff updates the prior ADR's status: `Superseded by ADR-<new-number>`.
- The superseding ADR's body recaps the prior ADR's context, states the
  reversal, and includes a **Lessons Learned** section naming what the
  prior ADR over- or under-estimated (e.g., "ADR-0011 underestimated
  cursor-resume edge cases under concurrent inserts").

Lessons Learned is not optional polish — it's how the next ADR avoids
repeating the prior ADR's blind spot. Without it, the superseding ADR
reads as arbitrary reversal.

**Choosing superseding ADR vs. scoped exception.** Reversibility is the
deciding axis: a Diverges row that's hard to roll back later (changes the
wire shape consumers ship against; alters the typed surface; renames a
field consumers depend on) needs the superseding-ADR path. A row that's
reversible inside one feature (an opt-in flag, a per-request override,
behavior scoped behind a capability bit) can stay a scoped exception. If
unsure, default to superseding — the protocol is easier to evolve via one
clean reversal than via accumulated scope-exception rooms.

**Hard gate:** if a `Diverges` row has no justification, the spec is **not
ready**. Return to Phase 2 and rewrite that piece to conform, or fill in
the exception with a real proposal. A missing justification is not
acceptable handoff state.

---

## Phase 5 — Finalize

**Input:** the spec body plus the appended Conforms-to / Diverges-from
table.

**Action:** hand the spec to the user for review. The output is content,
not a destination — the spec may land as an ADR
(`website/src/content/docs/governance/adr/NNNN-name.md(x)` in
`simpler-grants-protocol`) or as a Google Doc feeding an ADR or
implementation issue. The user decides where it goes.

**If the spec is destined for the ADR directory**, include the
frontmatter block at the top of your handoff response (not just in a
file you write), matching the repo's `adr-template.md`:

    ---
    title: "<Decision summary>"
    description: ADR documenting the decision to use <outcome> for <topic>
    draft: true
    ---

The ADR's first heading should declare status — `## Status: Proposed`
(or `Proposed (Supersedes ADR-NNNN)` if Phase 4 produced a superseding
proposal). In the superseding case, the same handoff updates the prior
ADR's status to `Superseded by ADR-<new-number>`.

**Do not commit. Do not post. Do not open a PR.** This skill produces
the spec content and stops.

**Terminal prompt.** End the run with this exact phrasing:

> Spec ready. Reply "approve" to finalize, "edit" with feedback to
> revise, or tell me where this should land (ADR file path, GDoc,
> implementation issue).

---

## Hard rules

- Skip no phase. The prior-art table is the input to drafting, not an
  afterthought. The Diverges table is a gate, not decoration.
- "Cited an ADR" does not equal "satisfied an ADR." Phase 3 verifies the
  draft's shape against every ADR it cites.
- Adding a new experimental pattern alongside the existing one is a smell,
  not a resolution. The protocol can only afford one answer to settled
  questions.
- No opinion language in the spec body — structural facts and grounded
  rationale only.
- Every technical claim cites a source or is marked `[unverified]`.
- Do not post or commit. The skill ends at handoff.
