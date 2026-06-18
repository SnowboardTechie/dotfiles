---
name: gamedev
description: Game development workflows for Burnt Ice - Obsidian integration, playtest capture, dev sessions
---

# Gamedev Skill - Burnt Ice

Workflows for Burnt Ice game development with Obsidian vault integration.

## Prerequisites

**Load the `obsidian` skill first** for wikilink syntax and vault error handling patterns.

## Configuration

```
VAULT_PATH="~/notes/burnt-ice"
PROJECT_PATH="~/code/games/burnt-ice"
```

## Link Targets

Key notes in the Burnt Ice vault:

| Wikilink | Path | Content |
|----------|------|---------|
| `[[GDD]]` | `design/GDD.md` | Game Design Document |
| `[[mechanics]]` | `design/mechanics.md` | Temperature, fuel, combat |
| `[[architecture]]` | `technical/architecture.md` | Code patterns, scripts |
| `[[roadmap]]` | `planning/roadmap.md` | Development phases |
| `[[godot-setup]]` | `technical/godot-setup.md` | Project configuration |

Use wikilink patterns from the `obsidian` skill (header links, display text, embeds).

---

## Workflow: Dev Session Start

When starting a session:

### Step 1: Git Status
```bash
cd ~/code/games/burnt-ice && git branch --show-current && git status --short
```

### Step 2: Read AGENTS.md
Read `~/code/games/burnt-ice/AGENTS.md` for current phase, known issues, patterns.

### Step 3: Recent Commits
```bash
cd ~/code/games/burnt-ice && git log --oneline -10
```

### Step 4: Report Format
```markdown
## Dev Session Started

**Branch:** {branch}
**Phase:** {phase from AGENTS.md}
**Uncommitted:** {yes/no}

### Known Issues
From [[architecture]] or AGENTS.md:
- [ ] Issue 1
- [ ] Issue 2

### Today's Focus
Based on [[roadmap]] phase {N}:
- Task 1
- Task 2
```

---

## Workflow: Playtest Capture

Create notes at `playtests/{YYYY-MM-DD}.md`:

```markdown
# Playtest - {date}

Related: [[GDD]], [[mechanics]], [[roadmap]]
Phase: {current phase from [[roadmap]]}

## Session
- Duration: {time}
- Build: {git commit or branch}
- Focus: {what was being tested}

## What Worked
- Mechanic/feature - per [[mechanics#Section|section]]

## What Didn't Work
- Issue - relates to [[GDD#Section]] or [[architecture#Pattern]]

## Bugs Found
- [ ] Bug description
  - Severity: {critical/major/minor}
  - Relates to: [[mechanics#Temperature System]] / [[architecture#Signals]]
  - Steps to reproduce: ...

## Ideas
- Idea description - would affect [[mechanics#Section]]
- Balance tweak - see [[GDD#Balance Targets]]

## Priority Fixes
1. **Critical**: Description - [[architecture#file.gd]]
2. **High**: Description - [[mechanics#affected-system]]

## Metrics (if applicable)
| Metric | Target | Actual |
|--------|--------|--------|
| Clear time | X min | Y min |
| Deaths | N | M |
```

---

## Workflow: Design Check

When checking design docs for a topic:

1. Read relevant vault file
2. Quote the authoritative section
3. Link back: `Per [[mechanics#Temperature System]]...`

Example response:
```markdown
Per [[mechanics#Temperature System]], the temperature ranges are:

| Range | Name | Effects |
|-------|------|---------|
| 75-100% | Warm | Normal operation |
| 50-74% | Cool | Blue vignette begins |
| 25-49% | Cold | Movement reduced to 85% |
| 1-24% | Freezing | Movement reduced to 70%, heavy frost |
| 0% | Frozen | Death |

This is defined in [[GDD#Core Mechanic]] as the central loop replacement for HP.
```

---

## Workflow: Update Design Docs

When updating vault documentation:

1. Read current content first
2. Preserve existing wikilinks
3. Add new wikilinks for cross-references
4. Use consistent header hierarchy

Example edit:
```markdown
## Flamethrower

Primary weapon. See [[GDD#Weapons]] for design rationale.

### Stats
- Fuel: 100 max
- Drain: 25/sec
- Regen: 10/sec
- Heal: +2 temp/sec (per [[mechanics#Temperature System]])

### Implementation
See [[architecture#Flamethrower.gd]] for code patterns.
```

---

## Git Workflow

**CRITICAL: No AI attribution in commits.**

```bash
# Feature branch naming
git checkout -b phase{N}-{feature}

# Commit (NEVER add --trailer or Co-authored-by)
git commit -m "Add temperature shader effects"

# FORBIDDEN patterns:
# git commit -m "..." --trailer "..."
# git commit -m "... Co-authored-by: ..."
```

---

## Phase Reference

| Phase | Focus | Key Deliverables |
|-------|-------|------------------|
| 0 | Blender | Learn pipeline, export workflow |
| 1 | First Playable | Move, shoot, kill one enemy |
| 2 | Core Loop | Temperature system, 3 enemies, death/restart |
| 3 | Dungeon | Rooms, floors, transitions |
| 4 | Progression | Currency, unlocks, upgrades |
| 5 | Polish | Audio, VFX, juice |
| 6 | Launch | Steam release |

Check [[roadmap]] for detailed phase breakdown.

---

## Error Handling

**See `obsidian` skill for vault error handling patterns.**

### Project Inaccessible
If `~/code/games/burnt-ice` missing:
1. Report error
2. Ask user for correct path
3. Update session context
