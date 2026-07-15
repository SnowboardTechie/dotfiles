# Agent-compiled project vaults

Use this for code-adjacent vaults that agents maintain directly. Their main failure mode is **recompilation debt**: detailed notes advance while the index, status page, topic MOCs, plans, and superseded decisions disagree.

## Role model

Treat the vault as compiled project knowledge, not as the raw source of truth.

| Role | Function |
|---|---|
| External/live source | Paired code repo, exact commit, issue/PR, ADR, API docs, policy, or another primary artifact |
| `INDEX.md` | Stable orientation and routes; not a dump of every recent note |
| Topic MOC/reference | Current compiled understanding of one durable concern |
| `status.md` | Current state, blockers, and next actions |
| Decision/exploration/session | Historical reasoning and events; preserve and mark supersession |
| Draft | Noncanonical until deliberately promoted |
| `.agents/` | Agent scratch/archive; excluded from canonical lint unless promoted |

Do not copy repositories or issue threads wholesale into a new `raw/` hierarchy. Point precisely to the live source and compile the durable conclusion into the existing vault-native surfaces.

## Ingest and reconciliation loop

For every source-backed update:

1. **Orient** — read `INDEX.md`, `status.md` when present, the relevant topic MOC, and local `AGENTS.md` overrides.
2. **Ground** — inspect the live code, issue/PR, ADR, or primary source. Record exact repo path, commit, PR/issue, version, and checked date when the claim can drift. If access fails, label the claim unverified.
3. **Compile** — update the existing canonical concept, status, or MOC before creating another note.
4. **Preserve history** — retain event notes and superseded decisions, but add explicit status, `superseded_by`, and a route to the current conclusion. Never silently rewrite the original decision as if it had always said the new thing.
5. **Reconcile** — propagate the changed conclusion through every canonical sibling surface in the active zone.
6. **Verify** — search the full active zone for stale copies, validate navigation/frontmatter, review the complete diff, then synchronize according to local rules.

A durable new note is incomplete until a relevant MOC or `INDEX.md` routes to it. A change to current project state is incomplete until `status.md` and the relevant MOC/index have been checked in the same resting-point commit.

## State labels and provenance

Distinguish these explicitly:

- **Observed current state** — verified against a named live source and snapshot date.
- **Accepted decision** — a governed choice, with who/where/when when that matters.
- **Proposed design** — not yet adopted or shipped.
- **Historical state** — true at the recorded time, no longer current.
- **Unverified inference** — plausible, but source access or evidence is incomplete.

Use inline source pointers and/or `source:` / `sources:` metadata for source-backed technical notes. Include exact repo path plus commit, PR/issue, document version, and checked date where useful. Keep provenance proportional: do not add decorative citations to original reasoning or project logs with no external factual claim.

## Classify before normalizing

- **Active compiled zone** — verify against live sources and reconcile current surfaces.
- **Dormant snapshot** — label its snapshot date and preserve it; do not imply continuous freshness.
- **Historical/archive corpus** — orient readers to its historical value without cosmetically reviving it.

Dormant and archived vaults should not be kept looking active merely to satisfy metadata. Apply broad cleanup on touch instead of churning historical notes.

## Boundaries

- Wikilinks resolve only inside one vault. For another vault, name it and use an explicit Markdown link or path.
- Paired code repositories are source inputs during vault-only work. Inspect branch/status before relying on them; do not edit, stage, switch, or clean them unless scope explicitly expands.
- Preserve all pre-existing changes. Stage explicit files only; never use `git add .` or `git add -A`.
- Do not add append-only ingest logs for information already recoverable from Git unless a concrete consumer needs data Git does not provide.
- Keep Obsidian wikilinks and organic folder structures. Treat OKF-like interchange as an export concern until a real consumer exists.

## Targeted audit

Audit canonical content—not `.agents/`, unpromoted `drafts/`, or templates—for:

- stale or overloaded indexes and status pages;
- current-vs-proposed ambiguity;
- superseded decisions whose consequences still read as current;
- contradictions across index/status/MOC/plan/decision surfaces;
- important zero-inbound canonical notes and broken navigation;
- invalid cross-vault wikilinks;
- source-backed claims with no traceable source or unsupported precision;
- stale paths to moved skills or repositories.

Distinguish intentional forward links, historical placeholders, folder links, and examples from retrieval failures. Do not create empty notes merely to make a checker green.

The optional read-only helper `scripts/audit-project-vaults.py` reports structural candidates; its output is triage, not authority.

## Verification sequence

1. Read back every changed canonical surface.
2. Validate changed YAML/frontmatter.
3. Confirm every new note has an inbound route.
4. Resolve wikilinks in changed canonical content, allowing documented exceptions.
5. Search the full active zone for superseded terms and values.
6. Confirm index, status, MOCs, plans, and decisions agree on current state while preserving history.
7. Run `git diff --check` and review complete diffs.
8. Ensure no pre-existing work was staged accidentally.
9. Commit and push related vault and convention repositories separately when ownership differs.
