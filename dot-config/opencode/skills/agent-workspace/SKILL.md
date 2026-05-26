---
name: agent-workspace
description: Working directory conventions for agents - task context, drafts, research cache in .notes/.agents/
---

# Agent Workspace - Working Directory Conventions

This skill defines how agents use the `.notes/.agents/` directory for working state, drafts, and ephemeral context that isn't ready for permanent notes.

## Philosophy

**.notes/ = Permanent knowledge** - Ideas, explorations, decisions worth keeping
**.notes/.agents/ = Working state** - Task context, drafts, cache that lives until task completion

The `.agents/` prefix keeps working files separate from permanent notes while allowing them to coexist in the same vault (Obsidian will treat the dot-folder as hidden by default).

---

## Directory Structure

```
.notes/.agents/
├── muse/                    # Muse's exploration context
│   └── {task-slug}/         # Per-task working files
│       ├── context.md       # Task context and goals
│       ├── progress.md      # What's been explored/decided
│       └── threads.md       # Open threads to pursue
│
├── sage/                    # Sage's research cache
│   └── {topic-slug}/        # Per-topic research
│       ├── findings.md      # Synthesized findings
│       └── sources.md       # Raw source links/excerpts
│
├── archivist/               # Archivist's search context
│   └── recent-searches.md   # Recent search queries and results
│
├── drafts/                  # Notes not ready for .notes/
│   └── {draft-name}.md      # Draft notes (may graduate)
│
└── _archive/                # Completed task context (optional)
    └── {date}-{task-slug}/  # Archived for reference
```

---

## File Conventions

### Task Context (muse/{task-slug}/context.md)

```markdown
---
task: {task-slug}
created: YYYY-MM-DD
status: active | paused | complete
---

# Task: {Title}

## Goal

{What are we trying to accomplish?}

## Scope

- In scope: {what's included}
- Out of scope: {what's excluded}

## Context

{Background, constraints, relevant notes}

## Related Notes

- [[{existing note}]]
```

### Task Progress (muse/{task-slug}/progress.md)

```markdown
---
task: {task-slug}
updated: YYYY-MM-DD
---

# Progress: {Title}

## Completed

- [x] {What's been done}
- [x] {Another completed item}

## In Progress

- [ ] {Current focus}

## Insights So Far

- {Key insight 1}
- {Key insight 2}

## Open Questions

- {Question to resolve}

## Next Steps

- {What to do next}
```

### Research Cache (sage/{topic-slug}/findings.md)

```markdown
---
topic: {topic-slug}
researched: YYYY-MM-DD
expires: YYYY-MM-DD  # Optional TTL
confidence: high | medium | low
---

# Research: {Topic}

## Summary

{2-3 sentence synthesis}

## Key Findings

### From Web
- **{Source}**: {finding}

### From Docs
- {Official guidance}

### From Code
- **{repo}**: {pattern found}

## Gaps

- {What couldn't be verified}

## Raw Sources

{Links, excerpts for reference}
```

### Draft Notes (drafts/{name}.md)

```markdown
---
draft: true
created: YYYY-MM-DD
target: idea | exploration | decision  # What it might become
---

# Draft: {Title}

{Content being developed}

## Notes to Self

- {What needs more work}
- {Questions to resolve before promoting}
```

---

## Lifecycle Rules

### Task-Scoped Content

| Phase | Action |
|-------|--------|
| Task starts | Create `{task-slug}/context.md` |
| During work | Update `progress.md`, add `threads.md` |
| Task complete | Archive to `_archive/` OR delete |
| Insights emerge | Promote to permanent note via Scribe |

### Research Cache

| Condition | Action |
|-----------|--------|
| Topic researched | Create `sage/{topic}/findings.md` |
| Re-researching same topic | Update existing, note date |
| Topic stale (>30 days) | Consider refreshing or deleting |
| Task complete | Delete unless useful for future |

### Drafts

| Condition | Action |
|-----------|--------|
| Idea forming | Create draft in `drafts/` |
| Draft ready | Promote to `.notes/` via Scribe |
| Draft abandoned | Delete via Pyre |
| Draft stale (>14 days) | Review - promote or delete |

---

## Agent Responsibilities

### Muse

- Creates task context when starting significant exploration
- Updates progress as exploration proceeds
- Signals task completion → triggers cleanup
- Can request draft promotion to permanent notes

### Scribe

- Writes task context files to `.agents/muse/{task}/`
- Writes drafts to `.agents/drafts/`
- Promotes drafts to `.notes/` when ready
- Updates progress files

### Sage

- Caches research findings in `.agents/sage/{topic}/`
- Checks cache before re-researching same topic
- Updates findings with new research
- Notes confidence and freshness

### Archivist

- Searches both `.notes/` AND `.notes/.agents/` for context
- Prioritizes permanent notes over working state
- Reports working state separately ("Also found in working files...")

### Pyre

- Cleans up `.agents/` content when tasks complete
- **Relaxed confirmation** for ephemeral files (task context, cache)
- **Normal confirmation** for drafts (might have valuable content)
- Archives to `_archive/` if requested instead of deleting

---

## Integration Patterns

### Starting a Task (Muse)

```
@scribe [TASK_CONTEXT] Create task context for "API Authentication Design":
- Goal: Design auth strategy for new API
- Scope: JWT vs sessions, refresh tokens, security
- Related: [[2026-01-15-exploration-auth]]
```

Creates: `.notes/.agents/muse/api-authentication-design/context.md`

### Updating Progress (Muse)

```
@scribe [TASK_PROGRESS] Update progress for "api-authentication-design":
- Completed: Evaluated JWT vs sessions
- In progress: Refresh token strategy
- Insight: Short-lived tokens (15min) are standard
- Next: Research token rotation patterns
```

Updates: `.notes/.agents/muse/api-authentication-design/progress.md`

### Caching Research (Sage)

Sage automatically writes to `.agents/sage/{topic}/` when researching.
Before new research, checks if recent cache exists.

### Promoting Draft to Note (Muse)

```
@scribe [PROMOTE_DRAFT] Promote draft "api-auth-decision" to DECISION note:
- It's ready - we've made the decision
- Move from drafts/ to .notes/
```

### Task Completion Cleanup (Muse)

```
@pyre Clean up task "api-authentication-design":
- Task is complete
- Archive the context (or delete if not needed)
- Keep the permanent notes we created
```

---

## Deletion via Pyre

Pyre handles all deletions from `.agents/` with tiered confirmation levels based on file type. See `pyre.md` for the full confirmation protocol.

**Quick reference:**
- Ephemeral files (task context, research cache) → Relaxed confirmation
- Drafts → Normal confirmation
- Permanent notes → Full confirmation

**Archive option:** `@pyre Archive task "..." instead of deleting`

---

## Directory Initialization

When first using `.agents/`, create the structure:

```bash
mkdir -p .notes/.agents/{muse,sage,archivist,drafts,_archive}
```

Add to `.gitignore` if the notes folder is tracked:

```
notes/.agents/
```

Or keep in git if you want working state versioned.

---

## Worktree-Aware Resolution (CRITICAL)

**You may be operating inside a git worktree.** Worktrees share the same git object store but have separate working directories. The `.notes` symlink lives in the **trunk** (main worktree), not in each worktree.

### Why This Matters

`git rev-parse --show-toplevel` returns the **worktree** path, not the trunk path. Without worktree detection, agents would:
- Create separate `.notes` per worktree (e.g., `~/notes/simpler-grants-protocol.feat-auth/`)
- Lose access to shared project notes
- Fragment the notes system

### Detection

```bash
# Check if we're in a worktree (not the trunk)
if [ -f "$(git rev-parse --show-toplevel)/.git" ]; then
  IS_WORKTREE=true
else
  IS_WORKTREE=false
fi
```

**How it works:** In a worktree, `.git` is a **file** (contains `gitdir:` pointer). In the trunk, `.git` is a **directory**.

### Resolving the Trunk Root

```bash
# Get the trunk (main worktree) root - ALWAYS use this instead of git rev-parse --show-toplevel
resolve_trunk_root() {
  local toplevel
  toplevel=$(git rev-parse --show-toplevel)

  if [ -f "${toplevel}/.git" ]; then
    # We're in a worktree - resolve trunk from git common dir
    # git rev-parse --git-common-dir returns the shared .git/ directory in the trunk
    local common_dir
    common_dir=$(git rev-parse --git-common-dir)
    # common_dir is like /path/to/trunk/.git — parent is the trunk root
    dirname "$common_dir"
  else
    # We're in the trunk
    echo "$toplevel"
  fi
}

TRUNK_ROOT=$(resolve_trunk_root)
PROJECT_NAME=$(basename "$TRUNK_ROOT")
```

### Rules

| Scenario | `git rev-parse --show-toplevel` | `resolve_trunk_root` | `.notes` location |
|----------|-------------------------------|---------------------|-------------------|
| In trunk `simpler-grants-protocol/` | `~/code/HHS/simpler-grants-protocol` | `~/code/HHS/simpler-grants-protocol` | `~/code/HHS/simpler-grants-protocol/.notes` |
| In worktree `simpler-grants-protocol.feat-auth/` | `~/code/HHS/simpler-grants-protocol.feat-auth` | `~/code/HHS/simpler-grants-protocol` | `~/code/HHS/simpler-grants-protocol/.notes` |
| In worktree `simpler-grants-protocol.fix-header/` | `~/code/HHS/simpler-grants-protocol.fix-header` | `~/code/HHS/simpler-grants-protocol` | `~/code/HHS/simpler-grants-protocol/.notes` |

**Key principle:** `.notes` is ONLY created in the trunk. All worktrees access the trunk's `.notes` by resolving `TRUNK_ROOT`.

---

## Project-Local Notes Pattern

For **task-oriented agents** (workday, gamedev) that operate within specific repositories, use a project-local `.notes/` directory that symlinks to a centralized location.

### Why This Pattern?

| Goal | Solution |
|------|----------|
| Notes stay with project context | `.notes/` in project root (trunk only) |
| Notes don't pollute git | `.notes` in `.gitignore` |
| Notes discoverable by Archivist | Symlink to `~/notes/{context}/` |
| Multiple projects stay organized | Subfolders by project name |
| Worktrees share notes | `.notes` lives in trunk, worktrees resolve to it |

### Directory Structure

```
# Trunk repository
~/code/HHS/simpler-grants-protocol/
├── .notes -> ~/notes/workday/simpler-grants-protocol/  # Symlink (lives here ONLY)
├── .gitignore                                # Contains ".notes"
└── ...

# Worktree (sibling) - NO .notes here
~/code/HHS/simpler-grants-protocol.feat-auth/
├── .git                                      # File (not directory) - worktree marker
└── ...source files...
# Agents resolve TRUNK_ROOT → use ~/code/HHS/simpler-grants-protocol/.notes

# Centralized notes (searchable by Archivist)
~/notes/
├── workday/
│   ├── simpler-grants-protocol/        # Project-specific workday notes (shared across all worktrees)
│   ├── common-grants/
│   └── commongrants-cli/
├── gamedev/
│   └── burnt-ice/           # Project-specific gamedev notes
└── ...                      # Muse notes, explorations, etc.
```

### Setup Protocol

When launching in a new project, agents should:

1. **Resolve the trunk root** (handles worktrees automatically)
   ```bash
   TRUNK_ROOT=$(resolve_trunk_root)
   PROJECT_NAME=$(basename "$TRUNK_ROOT")
   ```

2. **Check for existing `.notes/` symlink in the trunk**
   ```bash
   ls -la "${TRUNK_ROOT}/.notes" 2>/dev/null || echo "MISSING"
   ```

3. **If missing, create symlink and target in the trunk**
   ```bash
   # Determine context and project name
   CONTEXT="workday"  # or "gamedev"
   
   # Create target directory
   mkdir -p ~/notes/${CONTEXT}/${PROJECT_NAME}
   
   # Create symlink IN THE TRUNK (not the worktree)
   ln -s ~/notes/${CONTEXT}/${PROJECT_NAME} "${TRUNK_ROOT}/.notes"
   
   # Add to .gitignore if not present (in trunk)
   grep -q '^\.notes$' "${TRUNK_ROOT}/.gitignore" 2>/dev/null || echo ".notes" >> "${TRUNK_ROOT}/.gitignore"
   ```

4. **Confirm setup**
   ```
   Notes directory ready: {TRUNK_ROOT}/.notes -> ~/notes/{context}/{project}/
   ```

5. **Use the trunk's .notes for all reads/writes**
   ```bash
   NOTES_ROOT="${TRUNK_ROOT}/.notes"
   ```

### Agent Usage

**Workday agent** writes to:
- `.notes/daily/` - Daily standups, EOD summaries
- `.notes/prs/` - PR review notes
- `.notes/sprint/` - Sprint snapshots

**Gamedev agent** writes to:
- `.notes/sessions/` - Dev session logs
- `.notes/playtests/` - Playtest observations
- `.notes/bugs/` - Known issues tracking

### Integration with Athena

Notes written by workday/gamedev agents:
- Use **athena-notes templates** when appropriate (explorations, decisions)
- Are **discoverable by Archivist** since they live under `~/notes/`
- Can be **referenced by Muse** when thinking about related topics

```
# From Muse
@archivist Find past notes about simpler-grants-protocol PR reviews
# → Finds ~/notes/workday/simpler-grants-protocol/prs/*.md
```

### Initialization on First Use

Agents loading this skill should run the setup protocol when they detect `.notes/` is missing. The setup is idempotent - safe to run multiple times.
