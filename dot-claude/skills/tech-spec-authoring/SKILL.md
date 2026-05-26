---
name: tech-spec-authoring
description: >
  Phase-gated workflow for drafting a tech spec, ADR, or new-endpoint design
  doc when an established conventions index exists. Use when asked to "draft a
  tech spec", "write a tech spec for X", "spec out the endpoint", "let's write
  the spec for #N", "draft an ADR for X", "write the ADR for the new endpoint",
  or similar. Enforces conform-by-default: prior art is gathered before drafting,
  the draft uses established shapes verbatim, and every divergence is
  justified in a final Conforms-to / Diverges-from table before handoff.
---

# Tech Spec Authoring

Draft a tech spec or ADR by gathering prior art first, conforming to it by
default, and surfacing every divergence with an explicit ADR-exception
justification. The failure mode this skill exists to prevent is **citing an
ADR and writing around it** — disposition gap, not discovery gap.

The conform-by-default rule, pre-finalize checklist, and required artifact
table live in the host repo's `AGENTS.md` under `## TECH SPEC AUTHORING`.
This skill enforces the *flow*; it does not restate the rules.

---

## Customization point

Every repo using this skill needs a **conventions index** — a discoverable
markdown file enumerating established conventions with source links.

- **simpler-grants-protocol:** `.notes/technical/protocol-conventions.md`
- **Other repos:** populate the equivalent file before running this skill.

If no conventions index exists in the current repo, stop and tell the user.
Do not synthesize one inline.

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

The prior-art table is the input to Phase 2, not an afterthought.

---

## Phase 2 — Draft

**Input:** the prior-art table from Phase 1.

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
   - every technical claim cites a source (file path, ADR number, line
     range) or is marked `[unverified]`
   - no fabricated assumptions about external system properties

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

**Do not commit. Do not post. Do not open a PR.** This skill produces
the spec content and stops.

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
