# Personal note shapes in Apple Notes

The vault's shapes carried over; only the container changed. Titles are the
note's first line (the helper writes it as the H1). Frontmatter no longer
exists: the retained values live as plain trailing lines (`Aliases:`,
`Related:`, `Created:`, `Status:`, `Tags:`) so they stay searchable on every
device. Append to those lines rather than inventing a new metadata scheme.

## Folder map (beneath `Second Brain`)

| Folder | Holds | Title convention |
|---|---|---|
| root | topic hubs and reference notes (`Tool Inventory`, `2005 Suzuki DRZ250`, `Gift and Experience Ideas`) | Title Case thing name |
| `Inbox` | Siri / Watch / quick capture, unclassified | whatever was said |
| `Explorations` | a problem worked to a useful stopping point | `YYYY-MM-DD-{topic-slug}` |
| `Decisions` | a choice with reasons worth keeping | `YYYY-MM-DD-decision-{slug}` |
| `Journal` | weekly hubs `YYYY-MM-DD-weekly-plan` (Monday date) and daily spokes `YYYY-MM-DD-daily-check-in` | dated |
| `Journal/2025`, `Archive/…` | historical imports; read, do not extend | as imported |
| `Learning/Agent-Assisted Planning` | guided-learning workspace (`INDEX`, `RESOURCES`; records as notes `0001-{slug}` in a lazily created `learning-records` subfolder) | as the skill says |
| `Readings/…` | reading notes and their atoms | as imported |
| `Manuals` | one carrier note per PDF manual (attachment) | manual file name |
| `Templates` | historical templates; the routines now carry their own shapes | as imported |
| `Bookmarks`, `Daily` | imported collections | as imported |

Ideas (one paragraph, `YYYY-MM-DD-idea-{slug}`) go in the root, as before.

## Exploration

```markdown
# {Title} — {short subtitle}

## The Question
{driving question; name related notes by exact title}

## The Exploration
### {Sub-angle}
{narrative; trade-offs as prose or a table}

## Insights
- **{Distilled takeaway}** — {why, in one or two sentences}

Related: {Title A}, {Title B}
Created: YYYY-MM-DD
Status: active
Tags: area/{domain}, {topic}, type/exploration
```

## Decision

```markdown
# Decision: {Title}

## Context
## Options Considered
### Option A — {name}
| Pros | Cons |
|---|---|
## Decision
> **Chosen: {Option}** — one-line rationale
## Consequences
## Related
- {exploration title that led here}

Created: YYYY-MM-DD
Status: decided
Tags: area/{domain}, type/decision
```

## Journal hub and spoke

The weekly hub keeps the sections the routines read: `## Active Goals and
Projects` (one `- ` bullet per goal; the morning brief extracts only these),
`## Explicitly Parked`, `## Daily Reflections` (one line per spoke title). A
daily spoke records only what Bryan actually said plus a concise synthesis.

## Linking

- Name targets by their exact note title; Apple Notes' native `>>` link picker
  and the helper's title resolution both key on it.
- Prefer one canonical note per thing; extend it (`append`) instead of creating
  near-duplicates. Search before every new note.
- Cross-vault references (a project vault, a repo, an issue) are plain text
  with a path or URL; nothing in Notes can resolve them.

## What not to do

- No new taxonomy, template system, or folder tree from a single capture.
- No routing of `Inbox` items without an explicit review conversation.
- No bulk rewrites: `replace` is for a note the agent created or Bryan asked
  to rewrite, and it refuses notes with attachments anyway.
- Nothing here is published, shared, emailed, or posted without approval.
