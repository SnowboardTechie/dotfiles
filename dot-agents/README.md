# dot-agents

Single source of truth for Bryan's **personal agent skills**, shared across the
four coding agents he runs: **Claude Code**, **Pi**, **OpenCode**, and **Hermes**.

## How it works

`skills/` is a flat pool — one directory per skill, one canonical copy. Each tool
gets a *curated subset* via per-skill symlinks created by
[`../setup-platform-configs.sh`](../setup-platform-configs.sh):

```
~/.claude/skills/<name>          -> dot-agents/skills/<name>
~/.config/opencode/skills/<name> -> dot-agents/skills/<name>
~/.pi/agent/skills/<name>        -> dot-agents/skills/<name>
~/.hermes/skills/personal/<name> -> dot-agents/skills/<name>
```

The setup script is idempotent: it links the curated skills, prunes symlinks that
are no longer curated, and **never touches** anything that isn't a symlink into
this pool — so Claude's plugin skills (`gsd-*`, `superpowers`, etc.) are left alone.

Why a flat pool instead of per-tool subfolders: most skills are wanted by 2+ tools.
Subfolders would force either duplicate copies or a `common/` + cross-folder symlink
layer. A flat pool keeps one copy of each skill and makes "give tool X skill Y" a
one-line change to an array below.

## Curation

Not every tool gets every skill. Pi is kept lean. Hermes gets adapted personal
workflows but keeps its bundled/local `obsidian` and `vault-pkm` implementations,
so those names are intentionally excluded from its pool links. The authoritative
lists are the `*_SKILLS` arrays in `setup-platform-configs.sh`; this table mirrors
them.

| Skill | What it does | Claude | OpenCode | Pi | Hermes |
|-------|--------------|:------:|:--------:|:--:|:------:|
| `ship` | wrap up worktree → push → open PR | ✅ | ✅ | ✅ | ✅ |
| `worktrunk` | git worktree (wt) management | ✅ | ✅ | ✅ | ✅ |
| `git-master` | git workflow (strips AI attribution) | ✅ | ✅ | ✅ | — |
| `update-pr-description` | fill PR body from template | ✅ | ✅ | ✅ | ✅ |
| `pr-self-review` | 4-lens autonomous review + fix loop | ✅ | ✅ | ✅ | ✅ |
| `agent-workspace` | `.agents/` working-dir conventions | ✅ | ✅ | ✅ | — |
| `vault-pkm` | PKM conventions for vaults | ✅ | ✅ | ✅ | local |
| `vault-capture` | session-end vault capture | ✅ | ✅ | ✅ | ✅ |
| `skill-retrospective` | conversation-to-workflow improvement triage | ✅ | ✅ | ✅ | ✅ |
| `obsidian` | Obsidian vault patterns | ✅ | ✅ | ✅ | bundled |
| `manual-merge` | Forgejo local squash-merge | ✅ | ✅ | — | ✅ |
| `issue-create` | draft & post an issue | ✅ | ✅ | — | ✅ |
| `issue-plan` | prepare a vault-backed implementation plan | ✅ | ✅ | — | ✅ |
| `issue-work` | end-to-end ticket workflow | ✅ | ✅ | — | ✅ |
| `loop-issue` | autonomous backlog-drain loop | ✅ | ✅ | — | ✅ |
| `adr-and-spec-coach` | guide an ADR/spec decision | ✅ | ✅ | — | ✅ |
| `conforming-tech-specs` | conformance-gated spec pass | ✅ | ✅ | — | ✅ |
| `voice-bryan` | write in Bryan's voice (teammate-facing) | ✅ | ✅ | — | ✅ |
| `dx-target` | derive consumer-first DX target | — | — | — | ✅ |
| `dx-preview` | review implemented consumer DX | — | — | — | ✅ |
| `gamedev` | Burnt Ice game-dev workflow | — | ✅ | — | — |
| `sync-hold-branch` | resync long-lived feature branches | ✅ | — | — | — |
| `catalog-review` | catalog dep-PR review | ✅ | — | — | ✅ |
| `dependency-review` | single dep-PR review | ✅ | — | — | ✅ |
| `dependency-triage` | dep-PR triage by blast radius | ✅ | — | — | ✅ |
| `sprint-deliverable-update` | sprint update comments | ✅ | — | — | ✅ |
| `weekly-planning` | retired weekly-planning machinery | ✅ | — | — | — |
| `find-skills` | browse community skills.sh | ✅ | — | — | — |

**Counts:** Claude 25 · OpenCode 19 · Pi 10 · Hermes 20 (28 distinct).

## Adding or re-curating a skill

1. Create `skills/<name>/SKILL.md` (plus optional `references/`, `templates/`).
2. Add `<name>` to the relevant `*_SKILLS` array(s) in `setup-platform-configs.sh`
   — or to `COMMON_SKILLS` to give it to all three tools.
3. Run `./setup-platform-configs.sh` to (re)build the symlinks.

To pull a skill from a tool, drop it from that tool's array and re-run — the prune
step removes the now-stale symlink.

## Notes

- Hermes's `personal/` entries are ordinary symlinks into this repository. A
  foreground skill edit can therefore modify the canonical pool; review diffs
  before committing. Hermes's autonomous curator does not own these files.
- Some skills carry **local-only, gitignored** content (e.g. `voice-bryan`'s
  verbatim corpus under `references/`). It lives in the pool dir on each machine but
  is never committed; a fresh clone starts without it.
- This pool replaced two former per-tool copies (`dot-claude/skills/`,
  `dot-config/opencode/skills/`) that drifted out of sync.
