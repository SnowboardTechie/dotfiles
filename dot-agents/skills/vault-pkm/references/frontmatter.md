# Frontmatter shape

Every vault note has YAML frontmatter. The shape differs slightly between
a workspace's vault and the personal vault, ~/second-brain/.

## A workspace's vault

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

**Note:** Workspace vaults use `domain/` (not `area/`) to avoid cross-vault tag
collision with the personal vault's `area/<life-domain>` namespace. The two vaults
have different categorical universes; tag namespaces stay separate.

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

## ~/second-brain/

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

- Workspace vaults use `domain/` for project-internal areas; the personal vault uses
  `area/` for life-area categorization. Tag namespaces deliberately separate.
- Workspace vaults use `project/<vault>` for cross-vault search; personal vault
  notes don't (they're not tied to a code project).
- Workspace vaults express parent-MOC relations via `up:`; the personal vault relies
  on inline wikilinks throughout the note body.
- The personal vault's type values are Exploration/Decision/Idea (matching its
  folder structure); workspace vaults are richer (moc, learning, investigation, etc.).

## Properties UI expectations

Obsidian renders YAML as the Properties panel. To render correctly:
- `tags:` must be a YAML list (each tag on its own line with `- `), not an inline string
- Dates must be `YYYY-MM-DD` (no quotes, no `T` — those break the date picker)
- `aliases:` shows up in the file-explorer when populated
