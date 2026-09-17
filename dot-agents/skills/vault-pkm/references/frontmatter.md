# Frontmatter shape

Every project-vault note has YAML frontmatter. (The former personal vault's
shape is kept below only to explain the tag-namespace split; personal notes now
live in Apple Notes without frontmatter — see `apple-notes-pkm`.)

## Project vaults

```yaml
---
tags:
  - type/<moc|decision|investigation|learning|exploration>
  - project/<vault-name>           # cross-vault search
  - domain/<architecture|ops|tooling|domain|...>   # project-internal domain
  - <topic-tag>                    # one or more topical tags
aliases: []                        # Obsidian rename/link-alias support
up: "[[Parent-MOC]]"               # parent MOC (for spokes); omit for MOCs themselves
created: 2026-05-27
updated: 2026-05-27                # bumped on each meaningful edit
status: active                     # active | decided | complete | archived
source:                            # optional: one exact source pointer
sources: []                        # optional: multiple exact source pointers
source-checked: 2026-07-15         # optional: checked date for claims that can drift
---
```

**Note:** Project vaults use `domain/` (not `area/`) — `area/<life-domain>` was
the personal vault's namespace and the imported Apple Notes still carry it as
searchable `Tags:` text. The two universes stay separate.

**No `related:`** field. Use inline `[[wikilinks]]` for lateral relations in
the note body. Use `up:` for parent-MOC relations (typed for Bases queries).
Maintaining `related:` as a separate frontmatter list creates two sources of
truth that drift.

Use provenance proportionally. Source-backed technical claims that can drift
should identify the repo path plus commit, PR/issue, document version, or URL and
checked date where useful. Inline pointers are often clearer for claim-level
support. Original reasoning, project logs, and historical narrative do not need
decorative citations. Label observed current state, accepted decisions, proposed
design, historical state, and unverified inference explicitly in prose.

## Personal notes (historical shape; frozen archive only)

`~/second-brain/` is a frozen rollback archive. Its notes used this shape,
which the Apple Notes import preserved as trailing `Tags:`/`Created:`/`Status:`
lines:

```yaml
---
tags:
  - area/<life-domain>             # area/tools, area/moto, area/homelab, ...
  - <plain-topic-tag>              # bare topic tags fine alongside
  - type/<exploration|decision|idea>
created: 2026-05-23
updated: 2026-05-23
status: active                     # active | decided | complete
---
```

## Key differences

- Project vaults use `domain/` for project-internal areas; personal notes used
  `area/` for life-area categorization. Tag namespaces deliberately separate.
- Project vaults use `project/<vault>` for cross-vault search; personal notes
  don't (they're not tied to a code project).
- Project vaults express parent-MOC relations via `up:`; personal notes rely
  on inline links throughout the note body.
- Personal type values are Exploration/Decision/Idea (matching the Notes
  folders); project vaults are richer (moc, learning, investigation, etc.).

## Properties UI expectations

Obsidian renders YAML as the Properties panel. To render correctly:
- `tags:` must be a YAML list (each tag on its own line with `- `), not an inline string
- Dates must be `YYYY-MM-DD` (no quotes, no `T` — those break the date picker)
- `aliases:` shows up in the file-explorer when populated
