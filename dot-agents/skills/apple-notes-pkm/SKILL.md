---
name: apple-notes-pkm
description: >
  Bryan's personal second brain lives in Apple Notes, in the iCloud folder
  "Second Brain". Use for personal recall ("what did I decide/explore about X",
  gift ideas, vehicles, home, learning, journal), personal capture, and any
  read or write of personal knowledge. Search, read, create, append, replace,
  and link through the bounded helper script in this skill — never by
  memo, an MCP, Full Disk Access, or the Notes database. Project and
  workspace knowledge is NOT here; that stays in Markdown vaults under
  vault-pkm. The frozen Git archive at ~/second-brain is rollback history,
  not a live source.
---

# Apple Notes personal knowledge

Apple Notes is the sole active personal second brain (decision record:
`~/second-brain/Decisions/2026-09-16-decision-apple-notes-personal-second-brain.md`).
All agent access goes through one repo-owned helper:

```bash
~/code/dotfiles/dot-agents/skills/apple-notes-pkm/scripts/apple-notes-pkm.py <command> …
```

Every tool that receives this skill can also reach it relative to the skill
directory (`<skill dir>/scripts/apple-notes-pkm.py`). It prints one JSON
object per call and is hard-scoped to the iCloud `Second Brain` folder: notes
outside it do not exist as far as the helper is concerned. There is no delete.

## When this applies

- Bryan asks about anything personal: decisions, explorations, ideas, vehicles,
  tools, home projects, gifts and dates, reading notes, journal, learning.
- A conversation reaches a resting point with personal knowledge worth keeping.
- A skill or routine says "record this in the second brain" or names a Notes
  folder such as `Journal`, `Decisions`, `Explorations`, `Inbox`.

Not for project or workspace knowledge (`vault/` dirs, `~/code/notes/`) — load
`vault-pkm` for those. Not for agent-internal memory — that is Hindsight.

## Commands (all bounded)

| Need | Command | Notes |
|---|---|---|
| Preflight | `health` | account, root, folders, counts. Run first in a new session. |
| Find | `search "<query>" [--mode title\|body\|any] [--folder F] [--limit N]` | ≤25 summaries `{id,title,folder,modified,snippet}`; never the whole library |
| Browse one folder | `list --folder F [--limit N]` | summaries only |
| Read | `read <id>` | clean Markdown + `revision`; `--raw` adds HTML/plaintext with media omitted |
| Create | `create --folder F --title T --body-file f.md` | folder must already exist beneath the root; `--attach` files |
| Append | `append <id> --revision R --body-file f.md` | rejects a stale revision (exit 3) |
| Replace | `replace <id> --revision R --body-file f.md` | refuses notes with attachments or rich objects (exit 4) |
| Links out | `links <id>` | anchors resolved against titles |
| Links in | `backlinks --title T` or `--id <id>` | `linked` (anchor text) vs `mentions` (title in body) |

Exit codes: 0 ok · 1 error · 2 usage · 3 stale · 4 refused · 5 Automation
permission missing (a human action) · 6 post-write verification failed.

## Recall workflow

1. `search` with the topic and one or two synonyms; try `--mode title` first
   when Bryan names a note. Keep `--limit` small (10 is the default).
2. `read` only the ids that matter. Quote the note's title and folder in the
   answer; never paste whole notes back unless asked.
3. Distinguish decisions from explorations and later updates; call out
   superseded material rather than reporting the oldest conclusion.
4. Conversation memory is secondary context, not proof of what a note says.

## Write workflow (guarded)

1. Search first for an existing note to extend; prefer `append` to a new note.
2. Name the folder and title (or the id) in one line before writing.
3. `read` immediately before a write and pass that `revision`. A stale
   revision means someone edited the note (often from a phone): re-read,
   merge by hand, retry.
4. Write Markdown; the helper renders the subset Apple Notes keeps (headings,
   lists, checklists as ☐/☑ glyphs, tables, code, links, blockquotes as bold
   lead-ins). Wikilinks are flattened to titles; use native links instead
   (below).
5. Every write is read back and verified by the helper; report the returned
   title, folder, and id.

Guardrails: create only in an existing folder beneath the root (`Inbox` for
unclassified capture, `Explorations`, `Decisions`, `Journal`, or a topic
hub at the root). Never `replace` to "clean up" a note Bryan wrote; append or
ask. Never grant, click, or widen macOS permissions on Bryan's behalf; if the
helper returns exit 5, stop and ask.

## Links and backlinks (best effort)

Apple Notes supports native links to notes. When a new note should point at
another, write the target's exact title as the link text and let Bryan (or a
later human pass) turn it into a native link; the helper's `links`/`backlinks`
resolve anchor text and title mentions, which works for helper-written and
title-labelled links. This is a search-backed convenience, not a complete
graph. Legacy `[[wikilinks]]` from the vault import survive as plain titles
(aliases render as `alias (Target)`; sections as `Target › Section`).

## Note shapes and folders

Read `references/note-shapes.md` for the personal note shapes (Exploration,
Decision, Idea, Journal hub/spoke, topic hubs), the folder map, and how the
retained frontmatter lines (`Aliases:`, `Tags:`, `Status:` …) are used.

## Capture from devices

`Second Brain/Inbox` receives Siri and Apple Watch capture through the Shortcut
"Capture to Second Brain". Inbox notes are unclassified by design; route or
synthesize them only in an explicit review, and always by `append`/`create`
into the destination — never by deleting the inbox note.
