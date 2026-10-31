---
name: knowledge-capture
author: Bryan
description: >
  Use at a session's resting point or end to decide whether anything from the
  work just done is worth keeping as durable knowledge, and where it belongs.
  Triggers: "anything worth capturing?", "any notes we should save from this
  session?", "should this go in the vault / second brain?", "capture this",
  or /knowledge-capture (formerly /vault-capture). Routes personal knowledge
  to the ~/second-brain Markdown vault and project/workspace knowledge to that
  repository's vault, both written through vault-pkm. This skill is the
  judgment of *whether, what, and which destination*; the mechanics belong to
  vault-pkm and the destination vault's AGENTS.md.
---

# Knowledge capture

The end-of-session triage gate: decide whether anything from the work just done
earns a durable note, of what kind, and in which backend — then hand the
writing to that backend's skill. This skill is **judgment and routing, not
mechanics.**

| Knowledge is about… | Backend | Skill |
|---|---|---|
| Bryan's life: decisions, explorations, ideas, vehicles, home, tools, gifts, journal, learning | `~/second-brain` (Markdown, Forgejo Git) | `vault-pkm` + `~/second-brain/AGENTS.md` |
| A project or workspace: code, plans, issues, handoffs, architecture, DX artifacts, reviews | that repo's Markdown vault (`vault/`, `~/code/notes/<project>/`) | `vault-pkm` |
| Agent behaviour corrections, "remember to…" for the agent itself | the harness's native memory (e.g. Claude auto-memory, Hermes `MEMORY.md`/`USER.md`) | none — name it and let that native system catch it |

Apple Notes' `Second Brain` folder is a retired rollback copy (personal
knowledge returned to `~/second-brain` on 2026-10-31). Never write there and
never treat it as a live source.

## Bryan's closeout authorization (overrides the slate gate below)

Treat an end-of-session request such as "any notes to save before I end this
chat?" as authorization to capture and reconcile the decisions and plans Bryan
already adopted. Name the bounded destinations (backend + folder/path), write,
verify, and follow the backend's synchronization rules without another approval
round. The default slate-and-wait gate applies when adoption, scope, or backend
is genuinely unclear, not to an authorized closeout. Do not capture unadopted
suggestions or make structural changes under this exception.

Answer a substantive new question before capture housekeeping. If Bryan
interrupts drafting to resume discussion, stop writing. Before resuming a
partial capture, re-read the live target (pull and read the live Git copy): another session may already have saved it or advanced the plan.

Two failure modes this exists to prevent:

- **Writing without being asked to write.** *"Anything worth capturing?"* is a
  question, not authorization. Propose a triaged slate; write what is picked.
- **Provenance pollution.** Laundering an agent-synthesized heuristic or a
  half-floated idea into the record as if Bryan had decided it. Agent-proposed
  ideas qualify only after Bryan explicitly approves or adopts them.

---

## The spine

### Step 1 — Route, then load the backend's conventions

Decide the backend from the table above before anything else. Mixed sessions
split: the project part goes to the project vault, the personal part to
`~/second-brain`. Then load `vault-pkm` and the destination's own `AGENTS.md`
(`~/second-brain/AGENTS.md` for personal: note shapes, folders, frontmatter,
commit discipline; a project's `vault/AGENTS.md` and `INDEX.md` otherwise).
Search for existing notes to extend. Do not freelance structure from memory.

### Step 2 — Sweep the session for candidates

List everything that *might* be note-worthy; triage happens next. For each,
note **what it is** and **who produced it** — Bryan/the team or the agent —
plus whether Bryan explicitly adopted an agent-proposed idea.

### Step 3 — Triage: two gates, then a tier

**Gate A — Provenance and adoption (hard).** Did Bryan or the team decide,
discover, or produce this? If the agent proposed it, did Bryan explicitly
approve or adopt it? "mm, maybe" is not adoption.

**Gate B — Already captured / derivable.** Is it in the active project
instructions, the code, the git log, or an existing note? Then link, don't
duplicate.

**Tier** (for what survives):

- **capture-now** — shaped knowledge: a decision + its why, a confirmed
  investigation, an observed behaviour, a learning → a full note.
- **defer-until-signal** — a live but unshaped idea → a one-line seed (an
  `Idea` note in `~/second-brain`; an "Open threads" line in a project vault's
  `INDEX.md`).
- **decline** — routine, derivable, or failed a gate → nothing.

### Step 4 — Present the slate; the author picks

Show survivors with tier, note type, backend, and destination folder/path.
Then **stop and let Bryan choose.** "Nothing worth capturing" is a correct and
common answer.

### Step 5 — Write only what's greenlit, via the backend skill

Both destinations → `vault-pkm`: search first, name the path, extend an
existing note where one fits, otherwise create one with the vault's filename,
frontmatter, and linking rules; then commit and push per that vault's
`AGENTS.md` and confirm local `HEAD` equals the remote.

Any structural change — a new folder, a new MOC — is itself a decision:
name it and get a yes first.

---

## Interaction contract (hard rules)

- The capture question is not write authorization (closeout exception above).
- Provenance gate requires adoption.
- "Nothing worth capturing" is a valid result.
- Route before writing; never put project plans in `~/second-brain` or personal
  reflection in a project vault because it was convenient.
- defer ≠ a full note.
- Don't duplicate what instructions, code, git, or an existing note hold.

## Red flags — STOP

- Writing before showing a slate (outside an authorized closeout).
- Capturing an agent-proposed convention Bryan has not adopted.
- Writing to Apple Notes, or reading it as if it were current.
- Creating a folder/MOC to fit a capture without asking.
- Manufacturing a note because a blank answer feels unhelpful.

## See also

- `vault-pkm` — Markdown vault mechanics for both destinations: topology,
  frontmatter, links, commit discipline.
- `~/second-brain/AGENTS.md` — personal note shapes, folders, and Git rules.
