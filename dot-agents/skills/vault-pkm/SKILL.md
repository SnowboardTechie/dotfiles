---
name: vault-pkm
description: >
  PKM conventions for Bryan's project and workspace Markdown vaults (tracked
  vault/ dirs in project or workspace repos, plus retained snapshots under
  ~/code/notes/). Use when working in a repo with a top-level vault/ or in
  ~/code/notes/ — or when capturing project decisions, investigations,
  learnings, plans, or project context that doesn't live in code. Encodes
  MOC-and-spoke topology, atomic-spoke discipline, look-first/never-orphan
  rule, compiled-project ingest/reconciliation, filename conventions,
  frontmatter shape, and per-vault git commit discipline. Personal knowledge
  is NOT a vault any more: it lives in Apple Notes under apple-notes-pkm, and
  ~/second-brain is a frozen rollback archive.
---

# Vault PKM conventions

Bryan's project vaults are PKM-style: MOC-and-spoke topology, atomic spokes,
linked richly. A living graph, not a filing pile. This skill encodes the shared
conventions across his project and workspace vaults. Personal knowledge moved
to Apple Notes on 2026-09-16 (`apple-notes-pkm`); `~/second-brain/` is a frozen
read-only rollback archive and is never a write destination or a live source.

## When this applies

- You're operating in a repo with a top-level `vault/` — a tracked directory
  (project-owned vault, e.g. `~/code/cairn-os/vault/`; workspace repo, e.g.
  `~/code/sgg/vault/`) or a legacy symlink
- You're operating in `~/code/notes/<project>/` directly (retained
  dormant/historical snapshots — check the vault's INDEX.md disposition before
  treating contents as current)
- The user is capturing a project decision, investigation, learning, or
  exploration (personal ones route to `apple-notes-pkm` via `knowledge-capture`)
- You're asked "where should this note go?" or "what does the vault say about X?"

## Step 1 — check for per-vault overrides

Before applying defaults, check if the vault has an `AGENTS.md` at its root:
- Project vaults: `vault/AGENTS.md` (= `~/code/notes/<vault>/AGENTS.md` via symlink)

If present:
- Read the override file. Its rules take precedence where they conflict with this skill.
- Check the override's `# Overrides from skill version: <date>` stamp. If the stamp is older than 90 days, warn the user: the skill's references may have changed since the override was written; consider re-reading the references and refreshing the override.

If not present, proceed with skill defaults below.

## Step 2 — at session start in a vault

Read the vault's entry point: `vault/INDEX.md` (the Map of Content).

Check INDEX.md's `index-last-verified:` frontmatter field. If older than 30 days,
mention this to the user — the Map of Content may have drifted from the vault's
actual MOCs and active threads. This is a fallback warning, not a freshness
window: verified changes to current state trigger reconciliation immediately.

For an agent-maintained project vault, also read `status.md` when present and the
relevant topic MOC before writing. Classify the vault as active compiled work,
a dormant snapshot, or a historical/archive corpus before treating old state as
current.

Pull other files lazily, following wikilinks as work surfaces them. Don't
bulk-load the vault.

## Step 3 — pick the right reference for what you're about to do

| Activity | Load |
|---|---|
| Deciding folder + filename shape for a new note | `references/filename-conventions.md` |
| Writing frontmatter | `references/frontmatter.md` |
| Establishing or linking to a MOC, or any "before I write" thinking | `references/hub-and-spoke.md` |
| Grounding and recompiling an agent-maintained project vault | `references/agent-compiled-project-vaults.md` |
| Committing + pushing a vault write | `references/commit-discipline.md` |

For anything ambiguous, start with `references/hub-and-spoke.md` — it covers
the core philosophy (look-first, atomic spokes, never-orphan, refinement triggers)
that informs every other choice.

## Don't write

- Routine work, things derivable from `git log`, daily logs, append-only ingest logs
  that add no information beyond Git
- Mid-conversation captures without naming the path and type first

## For non-Skill agents

This skill's content is plain markdown. Agents without a Skill runtime (aider, codex
when not using its own skills system, Cursor) can read `SKILL.md` directly, and
should also read all files under `references/` since they won't follow the
routing table dynamically. The mechanism differs; the content is the same.

## See also

- `apple-notes-pkm` — Bryan's personal second brain (Apple Notes). Personal
  note shapes (Exploration / Decision / Idea) live there now; nothing personal
  is written to a Markdown vault.
- `knowledge-capture` — the router that decides personal vs. project at a
  session's resting point.
- `~/code/notes/AGENTS.md` — orientation for agents that land in the
  project-vaults repo directly
