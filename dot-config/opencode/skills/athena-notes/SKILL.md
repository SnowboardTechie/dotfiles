---
name: athena-notes
description: Note type system for Muse - templates, linking patterns, capture triggers, and vault structure
---

# Athena Notes - Thinking System Foundation

Standardized note types and patterns for the Muse thinking system. This skill defines HOW thoughts are captured, organized, and connected.

## CRITICAL: Notes Location

> **ALWAYS use `.notes/` relative to the working directory when in a project repo.**
> 
> NEVER use Obsidian iCloud paths (`~/Library/Mobile Documents/...`) in project contexts.
> The `.notes/` symlink handles the mapping automatically.

### Two Modes

| Mode | Detect By | Notes Path |
|------|-----------|------------|
| **Project Repo** | Working dir is a code repo (has `.git/`, `package.json`, etc.) | `.notes/` |
| **Direct Vault** | Working dir IS `~/notes/{vault}` | `./` (current dir) |

**Examples:**
```bash
# In simpler-grants-protocol project:
.notes/my-note.md  ✅ CORRECT
~/Library/Mobile Documents/.../my-note.md  ❌ NEVER

# In ~/notes/second-brain directly:
./my-note.md  ✅ CORRECT
```

---

## Core Philosophy

1. **Notes are memory** - Every note should be findable, linkable, useful later
2. **Types signal intent** - Note type tells readers what to expect
3. **Links create understanding** - Connected notes > isolated notes
4. **Capture early, refine later** - Don't wait for perfect thoughts

---

## Note Types

### 1. IDEA - Quick Capture

Raw thoughts, sparks, unprocessed inspiration. Low friction, high volume.

**When to use:**
- Flash of insight
- "What if..." moments
- Something worth remembering but not exploring yet

**Filename:** `YYYY-MM-DD-idea-{slug}.md`

```markdown
---
type: idea
date: YYYY-MM-DD
tags:
  - idea
  - {topic}
status: captured
sparked_by: "[[source note or conversation]]"  # optional
---

# {One-line description}

{The idea in 1-3 sentences}

## Why This Matters

{Brief context - why capture this now?}

## Questions

- {Question this raises}

## Related

- [[{existing note if any}]]
```

---

### 2. EXPLORATION - Thinking Session

Muse conversations, deep dives, question-driven exploration. The core output of thinking sessions.

**When to use:**
- Muse session produces insights
- Working through a problem
- Exploring options/approaches

**Filename:** `YYYY-MM-DD-exploration-{topic}.md`

```markdown
---
type: exploration
date: YYYY-MM-DD
tags:
  - exploration
  - muse
  - {topic}
status: in-progress | complete
session_context: "{what prompted this exploration}"
---

# {Topic} - Exploration

## Context

{What prompted this exploration? What question are we trying to answer?}

## Key Insights

> [!tip] Insight 1: {title}
> {Explanation}

> [!tip] Insight 2: {title}
> {Explanation}

{Or numbered list for simpler insights}

## Open Questions

> [!question] {Most important question}
> {Context or sub-questions}

- {Other question}
- {Other question}

## Threads to Pull

{Future exploration directions}

- [[{Topic for later}]] - {why}
- {Unexplored angle}

## Session Notes

{Optional: Raw notes, quotes, fragments from the session}
```

---

### 3. DECISION - Choice Record

Decisions made, with rationale and consequences. Future-you needs to know WHY.

**When to use:**
- A choice was made
- Direction was chosen
- Architecture/design decision

**Filename:** `YYYY-MM-DD-decision-{what}.md`

```markdown
---
type: decision
date: YYYY-MM-DD
tags:
  - decision
  - {domain}
status: decided | pending | superseded
superseded_by: "[[newer decision]]"  # if status: superseded
---

# Decision: {Title}

## Context

{What decision needed to be made? What constraints exist?}

> [!info] Background
> {Additional context if helpful}

## Options Considered

### Option A: {Name}

{Brief description}

| Pros | Cons |
|------|------|
| {pro} | {con} |
| {pro} | {con} |

### Option B: {Name}

{Brief description}

| Pros | Cons |
|------|------|
| {pro} | {con} |
| {pro} | {con} |

## Decision

> [!tip] Chosen: **{Option X}**
> {One-sentence rationale}

{More detailed explanation}

## Consequences

> [!warning] Watch For
> {Risks or things to monitor}

- {Expected outcome}
- {What this enables}
- {What this prevents}

## Related

- [[{Related decision}]]
- [[{Exploration that led here}]]
```

---

### 4. SESSION - Conversation Summary

Full session capture when a thinking conversation was particularly valuable.

**When to use:**
- End of significant muse session
- Conversation worth preserving in full
- Multiple topics covered

**Filename:** `YYYY-MM-DD-session-{topic}.md`

```markdown
---
type: session
date: YYYY-MM-DD
tags:
  - session
  - muse
duration: "{approximate length}"
participants: [muse, bryan]
---

# Session: {Topic or Date}

## Summary

{3-5 sentence overview of what was discussed/discovered}

## Topics Covered

1. **{Topic 1}** - {one line}
2. **{Topic 2}** - {one line}
3. **{Topic 3}** - {one line}

## Key Takeaways

- {Takeaway 1}
- {Takeaway 2}
- {Takeaway 3}

## Artifacts Created

- [[{Note 1}]] - {type}
- [[{Note 2}]] - {type}

## Follow-up

- [ ] {Action item if any}
- [[{Topic to explore next}]]

## Raw Notes

{Optional: Unprocessed fragments, quotes, or full transcript}
```

---

### 5. THREAD - Connected Ideas

Meta-note that links related ideas across sessions. Emerges when patterns appear.

**When to use:**
- Same topic keeps coming up
- Multiple notes are clearly related
- Building toward something bigger

**Filename:** `YYYY-MM-DD-thread-{theme}.md`

```markdown
---
type: thread
date: YYYY-MM-DD
tags:
  - thread
  - {theme}
status: active | complete | abandoned
---

# Thread: {Theme}

## What This Is

{Brief description of the recurring theme or connected idea}

## Connected Notes

| Date | Note | Contribution |
|------|------|--------------|
| YYYY-MM-DD | [[Note 1]] | {what it adds} |
| YYYY-MM-DD | [[Note 2]] | {what it adds} |
| YYYY-MM-DD | [[Note 3]] | {what it adds} |

## Emerging Pattern

{What's becoming clear as these ideas connect?}

## Open Questions

- {Question the thread raises}

## Next Steps

- {Where this thread might lead}
```

---

### 6. TASK - Work Tracking

For tracking tickets, PRs, ongoing work items with status and blockers.

**When to use:**
- Tracking a ticket/issue
- PR chain status
- Work that spans multiple sessions

**Filename:** `{ticket-id}-{slug}.md` or `YYYY-MM-DD-task-{slug}.md`

```markdown
---
type: task
date: YYYY-MM-DD
updated: YYYY-MM-DD
tags:
  - task
  - {project}
status: in-progress | blocked | complete
ticket: {TICKET-ID}
---

# Task: {Title}

## Overview

**Ticket:** {ID} - {Title}
{Links to GH issues, PRs, etc.}

## Current Status

> [!info] Status Update
> {Current state, what's done, what's next}

## Blocker (if any)

> [!warning] Blocked
> {What's blocking and who/what needs to act}

## Timeline

- **{date}:** {event}
- **{date}:** {event}

## Related

- [[{related notes}]]
```

---

## Capture Triggers

### When Muse Should Auto-Capture

| Signal | Note Type | Action |
|--------|-----------|--------|
| "That's interesting" or insight emerges | IDEA | @scribe quick capture |
| Session explores topic deeply | EXPLORATION | @scribe at natural pause |
| "I've decided" or choice made | DECISION | @scribe decision record |
| Session ending, was valuable | SESSION | @scribe session summary |
| Same topic 3+ times | THREAD | @scribe thread note |
| Checking ticket/PR status | TASK | @scribe update/create task note |

### Capture Prompts

Muse should use these internal prompts:

```
IDEA CAPTURE:
"An insight just emerged. I'll capture it briefly before continuing."

EXPLORATION CAPTURE:
"We've developed this topic significantly. Let me preserve the key insights."

DECISION CAPTURE:
"A decision was made. I'll record the choice and rationale."

SESSION CAPTURE:
"This session covered valuable ground. I'll create a summary before we close."

THREAD DETECTION:
"This topic has come up multiple times. I should create a thread to connect the dots."

TASK UPDATE:
"Checking work status. I'll update the task note with current state."
```

---

## Linking Patterns

### Within Notes

Always link to related notes using wikilinks:

```markdown
# Good
This builds on [[2026-01-15-exploration-auth]].
As decided in [[2026-01-20-decision-jwt|JWT decision]]...
See [[thread-api-design]] for the bigger picture.

# Bad
This builds on the auth exploration from last week.
As decided earlier...
```

### Backlinks

When creating a new note that relates to existing notes:

1. Link TO the existing note from the new note
2. Obsidian handles backlinks automatically
3. Consider updating the existing note's "Related" section

### Tag Hierarchy

```
#idea          → raw thoughts
#exploration   → deep dives
#decision      → choices made
#session       → conversation records
#thread        → connected ideas
#task          → work tracking
#muse          → captured by muse system

#project/{name} → project-specific
#domain/{area}  → knowledge domain
```

---

## Vault Structure

### Default: Flat structure in `.notes/`

```
.notes/
├── 2026-02-10-idea-something.md
├── 2026-02-10-exploration-topic.md
├── 2026-02-10-decision-choice.md
├── sgp-412-cli-auth.md  (task)
└── ...
```

This is simplest and works everywhere. Type is in frontmatter and filename.

### Optional: Folders by type

```
.notes/
├── ideas/
├── explorations/
├── decisions/
├── sessions/
├── threads/
└── tasks/
```

If using folders, scribe places notes in appropriate folder by type.

---

## Integration Notes

### Loading This Skill

Agents that capture notes should load this skill:

```yaml
# In agent frontmatter
skills:
  - athena-notes
```

### Scribe Integration

Scribe should reference this skill's templates when writing notes. Pass the note type to scribe:

```
@scribe [EXPLORATION] Create a note about our auth discussion:
- Context: We explored authentication options...
- Key insights: JWT preferred because...
- Questions: How to handle refresh tokens?
```
