---
name: apple-notes
description: "Apple Notes on this Mac: Bryan's personal second brain is the iCloud folder 'Second Brain', accessed only through the apple-notes-pkm skill and its bounded helper script. Use this pointer when a task mentions Apple Notes, Notes.app, or personal notes; do not use memo, a Notes MCP, or the Notes database."
version: 2.0.0
author: Bryan
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [Notes, Apple, macOS, note-taking, pkm]
    related_skills: [apple-notes-pkm, knowledge-capture]
---

# Apple Notes

This replaces the bundled `memo`-based guidance, which advertised CLI syntax the
installed tool never had (its search was an interactive `fzf` flow that
materialized every note). `memo` is not installed and is not the backend.

## What to load instead

- **`apple-notes-pkm`** (personal, `~/.hermes/skills/personal/apple-notes-pkm`)
  — bounded search, exact-id read, guarded create/append/replace, links and
  backlinks, all hard-scoped to the iCloud folder `Second Brain`. Every Notes
  interaction goes through its helper:

  ```bash
  python3 ~/.hermes/skills/personal/apple-notes-pkm/scripts/apple-notes-pkm.py health
  python3 ~/.hermes/skills/personal/apple-notes-pkm/scripts/apple-notes-pkm.py search "drz250 valve" --limit 10
  ```

- **`knowledge-capture`** — decides at a resting point whether something is
  worth keeping and whether it is personal (Apple Notes) or project (Markdown
  vault via `vault-pkm`).

## Rules

1. Never return or read the whole library; search is capped and content is
   fetched only by exact id.
2. Never delete a note; the helper has no delete and neither does this skill.
3. Never widen macOS permissions. If the helper reports Automation permission
   missing (exit 5), stop and tell Bryan; the one-time grant is his action.
4. Notes outside the `Second Brain` folder are out of scope for agents.
5. `/Users/bryan/second-brain` is a frozen Git rollback archive, not a source.
