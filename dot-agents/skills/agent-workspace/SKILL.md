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
├── sage/                     # Sage's research cache
│    └── {topic-slug}/        # Per-topic research
│        ├── findings.md      # Synthesized findings
│        └── sources.md       # Raw source links/excerpts
│
├── drafts/                   # Notes not ready for .notes/
│    └── {draft-name}.md      # Draft notes (may graduate)
│
└── _archive/                 # Completed task context (optional)
     └── {date}-{task-slug}/   # Archived for reference
```

---

## File Conventions

### Research Cache (sage/{topic-slug}/findings.md)

```markdown
---
topic: {topic-slug}
researched: YYYY-MM-DD
expires: YYYY-MM-DD   # Optional TTL
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
target: idea | exploration | decision   # What it might become
---

# Draft: {Title}

{Content being developed}

## Notes to Self

- {What needs more work}
- {Questions to resolve before promoting}
```

---

## Lifecycle Rules

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
| Draft ready | Promote to `.notes/` directly |
| Draft abandoned | Delete |
| Draft stale (>14 days) | Review - promote or delete |

---

## Integration Patterns

### Caching Research (Sage)

Sage automatically writes to `.agents/sage/{topic}/` when researching.
Before new research, checks if recent cache exists.

### Directory Initialization

When first using `.agents/`, create the structure:

```bash
mkdir -p .notes/.agents/{sage,drafts,_archive}
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

  if [ -f "{toplevel}/.git" ]; then
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
|----------|---------------------------------|----------------------|-------------------|
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
| Notes discoverable in vault | Symlink to `~/notes/{context}/` |
| Multiple projects stay organized | Subfolders by project name |
| Worktrees share notes | `.notes` lives in trunk, worktrees resolve to it |

### Directory Structure

```
# Trunk repository
~/code/HHS/simpler-grants-protocol/
├── .notes -> ~/notes/workday/simpler-grants-protocol/   # Symlink (lives here ONLY)
├── .gitignore                                 # Contains ".notes"
└── ...

# Worktree (sibling) - NO .notes here
~/code/HHS/simpler-grants-protocol.feat-auth/
├── .git                                       # File (not directory) - worktree marker
└── ...source files...
# Agents resolve TRUNK_ROOT -> use ~/code/HHS/simpler-grants-protocol/.notes

# Centralized notes (searchable in vault)
~/notes/
├── workday/
│    └── simpler-grants-protocol/         # Project-specific workday notes (shared across all worktrees)
├── gamedev/
│    └── burnt-ice/            # Project-specific gamedev notes
└── ...
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
    CONTEXT="workday"   # or "gamedev"
    
     # Create target directory
    mkdir -p ~/notes/${CONTEXT}/${PROJECT_NAME}
    
     # Create symlink IN THE TRUNK (not the worktree)
    ln -s ~/notes/${CONTEXT}/${PROJECT_NAME} "${TRUNK_ROOT}/.notes"
    
     # Add to .gitignore if not present (in trunk)
    grep -q '^\..notes$' "${TRUNK_ROOT}/.gitignore" 2>/dev/null || echo ".notes" >> "${TRUNK_ROOT}/.gitignore"
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

### Notes from workday/gamedev agents

Notes written workday/gamedev agents:
- Live under `~/notes/{context}/`
- Can **be referenced by other agents** when thinking about related topics

### Initialization on First Use

Agents loading this skill should run the setup protocol when they detect `.notes/` is missing. The setup is idempotent - safe to run multiple times.
