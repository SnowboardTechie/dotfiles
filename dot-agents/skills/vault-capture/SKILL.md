---
name: vault-capture
author: Bryan
description: >
  Use at a session's resting point or end to decide whether anything from the
  work just done is worth writing into an Obsidian notes vault — a repo with a
  vault/ symlink, ~/code/notes/<project>/, or ~/second-brain/. Triggers:
  "anything worth capturing in the vault?", "any notes we should capture from
  this session?", "should this go in the vault?", "capture this to the vault",
  or /vault-capture. This skill is the judgment of *whether and what* to
  capture; the conventions for *where a note lives and how it's shaped* belong
  to vault-pkm, which this skill loads and defers to.
---

# Vault capture

The end-of-session triage gate for a notes vault: decide whether anything from
the work just done earns a note, and of what kind — then hand the writing down
to `vault-pkm`. This skill is **judgment, not mechanics.** `vault-pkm` owns
where notes live, their frontmatter, their links, and commit discipline; this
skill owns the decision that sits in front of all that.

Two failure modes this exists to prevent:

- **Writing without being asked to write.** *"Anything worth capturing?"* is a
  question, not authorization. The reflex is to draft notes and commit them
  immediately. Instead: propose a triaged slate, let the author pick, write only
  what they greenlight.
- **Provenance pollution.** Laundering a heuristic the agent synthesized, a
  half-floated idea, or routine mechanics into the vault as if the user or team
  had decided it. Agent-proposed ideas qualify only after Bryan explicitly
  approves or adopts them. When in doubt, don't write.

---

## When to use

- The session has reached a resting point and the author asks whether anything
  is worth capturing — in any phrasing.
- You're about to close out work in a repo with a `vault/`, in `~/code/notes/`,
  or in `~/second-brain/`, and there were real decisions, discoveries, or
  learnings.

**When NOT to use:**

- Mid-task note-writing you weren't asked for → don't; finish the work.
- The mechanics of an already-decided capture (folder, filename, frontmatter,
  linking, commit) → that's `vault-pkm`. This skill hands off to it.
- A behavioral correction for the agent itself → Hermes session memory or
  session history, not the vault. Name it and let that system catch it.

---

## The spine

### Step 1 — Load the conventions, don't reinvent them

Invoke `vault-pkm` **before anything else.** It verifies vault readiness
(symlink target, `INDEX.md` currency, a `vault/AGENTS.md` override, existing
related notes) and owns all topology. When writing an approved note, use
Hermes's native file read, search, patch, and write tools while following
`vault-pkm` for syntax, frontmatter, links, and placement. Do not freelance
vault structure from memory.

### Step 2 — Sweep the session for candidates

List everything from the session that *might* be note-worthy — be generous here,
triage happens next. For each candidate, note one line: **what it is**, and
crucially **who produced it** — the user/team or the agent — plus whether Bryan
explicitly adopted an agent-proposed idea.

### Step 3 — Triage each candidate: two gates, then a tier

**Gate A — Provenance and adoption (hard).** Did the user or team decide,
discover, or produce this? If the agent proposed it, did Bryan explicitly
approve or adopt it? An unadopted suggestion or inferred rule is not vault
material. "mm, maybe" is not adoption. Behavioral notes for the agent belong in
Hermes session memory or session history, not the vault.

**Gate B — Already captured / derivable.** Is it in the active project
instructions (`AGENTS.md`, `.hermes.md`, `CLAUDE.md`, or equivalent), the code,
the git log, or an existing note? Then don't duplicate: one source of truth.
Link, don't copy.

**Tier** (for what survives both gates):

- **capture-now** — real, shaped knowledge: a decision + its *why*, a confirmed
  investigation/incident, an observed system behavior, a learning. → a full spoke.
- **defer-until-signal** — a live but unshaped idea or open thread (floated,
  agreed-interesting, not designed). → **not** a full note; park a thin seed
  (one line in `INDEX.md` "Open threads", or a one-line idea seed) to promote
  when real-usage signal arrives.
- **decline** — routine/derivable, or failed a gate. → nothing.

### Step 4 — Present the slate; the author picks

Show the surviving candidates as a short slate — each with its tier, proposed
note type, and where it would land. Then **stop and let the author choose. Do
not write yet.**

If nothing clears the gates, say so plainly. *"Nothing from this is worth a
vault note"* is a correct and common answer — do not manufacture a capture to
seem useful.

### Step 5 — Write only what's greenlit, via vault-pkm

For each chosen item, follow `vault-pkm` for filename, frontmatter, MOC link,
never-orphan, syntax, and commit discipline, then use native file tools to make
the approved write.

**Any structural change — a new folder, a new MOC — is itself a decision: name
it and get a yes before making it.** Defer items get their one-line seed,
nothing more.

---

## Interaction contract (hard rules)

- **The capture question is not write authorization.** Propose a slate first;
  write only what the author picks.
- **Provenance gate requires adoption.** Agent-proposed material goes in only
  when Bryan explicitly approves or adopts the idea and then greenlights the
  capture.
- **"Nothing worth capturing" is a valid result.** Don't pad the vault to look
  productive.
- **Flag structural changes before making them.** Don't reshape vault topology
  (new folder/MOC) unilaterally.
- **defer ≠ a full note.** A seed is one line; promote later on signal.
- **Don't duplicate** what active project instructions, code, git, or an
  existing note already hold.

---

## Red flags — STOP

You are about to break the contract if you catch yourself:

- Writing or committing a note before showing the author a slate.
- Drafting a note for an agent-proposed convention or heuristic that Bryan has
  not explicitly approved or adopted.
- Creating a new vault folder or MOC to fit a capture, without asking.
- Manufacturing a note because the question was asked and a blank answer feels
  unhelpful.
- Copying something already in project instructions, git, or code into the vault.

## Rationalizations

| Excuse | Reality |
|--------|---------|
| "They asked 'anything worth capturing', so writing them is what they want" | They asked a *question*. The answer is a proposed slate they pick from — not files already committed. |
| "It's my idea but it's a good one, the vault should have it" | Quality is not adoption. Propose it to Bryan first; it becomes eligible only if he explicitly approves or adopts it, and it is written only after he greenlights the capture slate. |
| "'mm, maybe' is basically a yes" | It's a not-yet. Capturing it launders a non-decision into apparent settled convention. |
| "I'll just create the folder, the conventions allow it" | A new folder/MOC is a topology decision. Name it and get a yes first. |
| "There's clearly *something* here, I should write at least one note" | Nothing-worth-capturing is a real outcome. A manufactured note adds noise and dilutes signal. |
| "It's already in project instructions but the vault should have it too" | Two copies drift. One source of truth: link, don't duplicate. |
| "The idea has no shape yet but I'll write it up so it's not lost" | Undeveloped ideas get a one-line seed, not a spoke. Hermes session memory or the relevant backlog catches the rest. |

## See also

- `vault-pkm` — where notes live, frontmatter, linking, commit discipline. This
  skill defers to it for **all** mechanics.
- Hermes native file tools — read, search, patch, and write the files after
  approval while following `vault-pkm` conventions.
- Corrections about agent behavior belong in Hermes session memory or session
  history, not the vault.
