# MOC-and-spoke discipline

Bryan's vaults are graphs, not piles. The discipline that makes them compound
in value: every note links to at least one other note, and the vault has *MOCs*
(Maps of Content) that organize *spokes*.

## MOCs (Maps of Content)

- **Topic-named, lives at vault root** (e.g., `Architecture.md`, `Domain Model.md`,
  `Protocol Conventions.md`). Title Case, no date prefix.
- One per major concern of the project.
- A MOC is a **structure note**: curated narrative prose with embedded wikilinks
  that *argues* the shape of the territory. Not a bullet dump of links.
- Evolves over time — refined, expanded, restructured as understanding deepens.
- MOC names map to PARA-ish *domains* within the project (architecture, ops, etc.).
- In PKM-community terms: hub = MOC. Use `type/moc` in frontmatter.

## Spokes

- **Atomic** — one concept per file. *Concept-shaped spokes only* — see below.
- **Linked** — wikilinks to at least one MOC or related spoke.
- Filename shape depends on note kind (see `filename-conventions.md`).

## Note shapes: event vs. concept

Not every spoke is atomic. The distinction matters:

- **Event-shaped notes** (decisions, investigations, explorations) are
  records of moments in time. Multi-section by design (Context, Options,
  Consequences for decisions; Symptom, Hypothesis, Resolution for investigations).
  Date-prefixed filenames. Atomicity does NOT apply — don't try to split a
  decision record into 5 sub-notes.
- **Concept-shaped notes** (learnings, MOCs) are evergreen ideas refined over
  time. Single concept per file. Slug-named. Atomicity DOES apply.

When in doubt: if the note is *about a moment*, it's event-shaped. If it's
*about a thing*, it's concept-shaped.

## The "never orphan" rule

Every new file must wikilink to at least one existing note. Search the vault
first; link liberally. An unlinked note is dead weight — Andy Matuschak's
evergreen notes, Luhmann's zettelkasten, and Tiago Forte's BASB all agree on
this even where they disagree elsewhere.

**Cold-start exception:** if the vault has no notes that the new note could
link to (fresh vault, sparse vault), update `INDEX.md` in the same write to
wikilink the new note from its Map of Content. That backlink from INDEX
satisfies the never-orphan rule AND keeps INDEX current. No special-case math:
every write is in the graph because INDEX is in the graph.

## Look-first protocol (hard pre-write gate)

Before writing a new note:

1. **Search the vault** for related notes using all of:
   - Filename glob (`find vault/ -iname '*<keyword>*'` or shell glob)
   - Content grep (`rg <keyword> vault/`)
   - Tag search (`rg 'type/<kind>' vault/` for prior art of the same kind)
   - MOC backlink check (open the relevant MOC; review its existing spokes)
2. **Decide update vs. create.** If a related note exists, prefer updating it
   or appending a section over creating a new file.
3. **If creating new:** wikilink the related notes you found AND at least one
   MOC (or INDEX.md, for cold-start).
4. **Name the path before writing.** Don't write silently mid-conversation.

This is friction. The friction is the point — it's what keeps the graph from
turning into a pile. Pay the cost.

## One concept per note (concept-shaped only)

If a *concept-shaped* note starts covering two distinct ideas, split it and
link them. Atoms are easier to relink, reuse, and refine than multi-topic notes.

This rule does NOT apply to event-shaped notes (decisions/investigations/explorations)
where multi-section structure is the point.

## Refinement triggers

Vaults rot when MOCs ossify. Refinement triggers — when to revisit and edit
an existing note:

- **After closing an investigation**: does the relevant MOC need a paragraph update?
- **After making a decision that supersedes a prior decision**: link the new
  one with `superseded_by:` frontmatter on the old.
- **After 3+ spokes accumulate that lift a topic out**: create a new MOC; link
  the spokes to it.
- **When INDEX.md is stale (>30 days `index-last-verified:`)**: re-scan MOCs
  at root, prune dead ones, surface new ones.

The skill should prompt these refinements when conditions are met.
