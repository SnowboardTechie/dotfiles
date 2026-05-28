---
name: vault-pkm
description: >
  PKM conventions for Bryan's project vaults (under ~/code/notes/) and personal
  vault (~/second-brain/). Use when working in a repo with a vault/ symlink, in
  ~/code/notes/, or in ~/second-brain/ — or when capturing decisions, taking
  notes, investigating debugs, recording learnings, or making sense of project
  context that doesn't live in code. Encodes MOC-and-spoke topology,
  atomic-spoke discipline, look-first/never-orphan rule, filename conventions,
  frontmatter shape, and per-vault git commit discipline.
---

# Vault PKM conventions

Bryan's vaults are PKM-style: MOC-and-spoke topology, atomic spokes, linked
richly. A living graph, not a filing pile. This skill encodes the shared
conventions across his project vaults and personal vault.

## When this applies

- You're operating in a repo with a `vault/` symlink (project vault)
- You're operating in `~/code/notes/<project>/` directly
- You're operating in `~/second-brain/`
- The user is capturing a decision, investigation, learning, or exploration
- You're asked "where should this note go?" or "what does the vault say about X?"

## Step 1 — check for per-vault overrides

Before applying defaults, check if the vault has an `AGENTS.md` at its root:
- Project vaults: `vault/AGENTS.md` (= `~/code/notes/<vault>/AGENTS.md` via symlink)
- `~/second-brain/`: `~/second-brain/AGENTS.md` (already exists — IS the override file for that vault)

If present:
- Read the override file. Its rules take precedence where they conflict with this skill.
- Check the override's `# Overrides from skill version: <date>` stamp. If the stamp is older than 90 days, warn the user: the skill's references may have changed since the override was written; consider re-reading the references and refreshing the override.

If not present, proceed with skill defaults below.

## Step 2 — at session start in a vault

Read the vault's entry point:
- Project vaults: `vault/INDEX.md` (the Map of Content)
- ~/second-brain/: the `AGENTS.md` at the vault root

Check INDEX.md's `index-last-verified:` frontmatter field. If older than 30 days,
mention this to the user — the Map of Content may have drifted from the vault's
actual MOCs and active threads.

Pull other files lazily, following wikilinks as work surfaces them. Don't
bulk-load the vault.

## Step 3 — pick the right reference for what you're about to do

| Activity | Load |
|---|---|
| Deciding folder + filename shape for a new note | `references/filename-conventions.md` |
| Writing frontmatter | `references/frontmatter.md` |
| Establishing or linking to a MOC, or any "before I write" thinking | `references/hub-and-spoke.md` |
| Committing + pushing a vault write | `references/commit-discipline.md` |

For anything ambiguous, start with `references/hub-and-spoke.md` — it covers
the core philosophy (look-first, atomic spokes, never-orphan, refinement triggers)
that informs every other choice.

## Don't write

- Routine work, things derivable from `git log`, daily logs
- Mid-conversation captures without naming the path and type first

## For non-Skill agents

This skill's content is plain markdown. Agents without a Skill runtime (aider, codex
when not using its own skills system, Cursor) can read `SKILL.md` directly, and
should also read all four files under `references/` since they won't follow the
routing table dynamically. The mechanism differs; the content is the same.

## See also

- `~/second-brain/AGENTS.md` — second-brain has its own note shapes
  (Exploration / Decision / Idea) and frontmatter tuned for personal-knowledge
  work; this skill defers to that file for second-brain specifics
- `~/code/notes/AGENTS.md` — orientation for agents that land in the
  project-vaults repo directly
