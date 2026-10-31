---
name: apple-notes
description: "Apple Notes on this Mac is NOT Bryan's second brain any more. Personal knowledge returned to the ~/second-brain Markdown vault on 2026-10-31; the iCloud Notes folder 'Second Brain' is a read-only rollback copy. Use this pointer when a task mentions Apple Notes, Notes.app, or personal notes; do not use memo, a Notes MCP, or the Notes database."
version: 3.0.0
author: Bryan
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [Notes, Apple, macOS, note-taking, pkm]
    related_skills: [vault-pkm, knowledge-capture]
---

# Apple Notes

Bryan's personal second brain is the Markdown vault `~/second-brain`, synced
only through Forgejo Git. Apple Notes held it from 2026-09-16 to 2026-10-31;
everything written there in that window was brought back into the vault
(decision: `~/second-brain/Decisions/2026-10-31-decision-return-personal-second-brain-to-markdown-git.md`).

## What to load instead

- **`vault-pkm`** plus `~/second-brain/AGENTS.md` — personal recall and capture.
- **`knowledge-capture`** — decides at a resting point whether something is
  worth keeping and whether it belongs in `~/second-brain` or a project vault.

## Rules

1. Do not read Apple Notes as a current source and do not write to it. The
   iCloud folder `Second Brain` is a rollback copy only; never delete it.
2. If Bryan explicitly asks about something only in Apple Notes, the retired
   `apple-notes-pkm` helper source remains in the dotfiles pool
   (`dot-agents/skills/apple-notes-pkm/`); use it read-only and say that it is
   the rollback copy.
3. `memo`, a Notes MCP, the Notes database, and widened macOS permissions stay
   out of scope.
