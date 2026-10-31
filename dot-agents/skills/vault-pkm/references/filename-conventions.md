# Filename conventions

Rule of thumb: **date if the note refers to a moment; slug if it refers to a thing.**

## Project vaults (under ~/code/notes/)

| Kind | Folder | Filename | Example |
|---|---|---|---|
| MOC (evolving project area) | vault root | `<Topic>.md` Title Case | `Architecture.md` |
| Decision (immutable, dated) | `decisions/` | `YYYY-MM-DD-<topic>.md` | `2026-05-27-use-sqlite-cache.md` |
| Investigation (one debug trace) | `investigations/` | `YYYY-MM-DD-<bug>.md` | `2026-05-27-cache-invalidation-bug.md` |
| Learning (atomic concept) | `learnings/` | `<topic-slug>.md` | `nyquist-phase-ordering.md` |
| Exploration (thinking session) | `Explorations/` | `YYYY-MM-DD-<topic>.md` | `2026-05-27-caching-approach.md` |

Existing vaults with organic structure (sgg's `explorations/`, `sessions/`,
`technical/`; burnt-ice's `design/`, `art/`, `planning/`, `technical/`) preserve
their folders. Add the canonical folders above only when first needed.

## ~/second-brain/

Follow `~/second-brain/AGENTS.md` filename rules:

- Exploration: `YYYY-MM-DD-{topic-slug}.md` in `Explorations/`
- Decision: `YYYY-MM-DD-decision-{slug}.md` in `Decisions/`
- Idea: vault root, `YYYY-MM-DD-idea-{slug}.md`
- Topic notes (life areas, hubs): Title Case slug at vault root (e.g., `Garage Tools Buildout.md`)
