---
name: guided-learning
description: Run a stateful personal learning mission in an explicitly named vault workspace — assess first, teach against a mission, and record only demonstrated understanding. Use only when Bryan explicitly asks to learn, study, or continue a learning mission and names the workspace. Never starts itself.
disable-model-invocation: true
---

# Guided Learning

Bryan is learning something across multiple sessions. This skill holds the
progression: what the mission is, what has actually been demonstrated, and what
comes next.

> **Explicit invocation only.** Start only when Bryan asks to learn, study, or
> continue a named learning mission. Claude enforces this through
> `disable-model-invocation`; Hermes and OpenCode do not read that key, so this
> paragraph is the rule for them. A conversation that merely explains something
> is not a learning session, and must not start one.

Provenance: adapted from Matt Pocock's `teach`, reduced to a minimal stateful
core. Upstream pin, accepted and rejected upstream rules, and the watched source
list live in
[`dot-agents/upstreams/mattpocock-skills.json`](../../upstreams/mattpocock-skills.json).

## 0. Resolve the workspace, or stop

The workspace is an **absolute path inside a vault**, supplied by Bryan or read
from a prior session's state. There is no default and no inference from the
current directory.

**Refuse and stop** when:

- no absolute workspace path was given — ask for one; do not guess;
- the path resolves inside this **installed skill directory**, or anywhere under
  `dot-agents/skills/`. The skill is shared, version-controlled procedure; a
  learning zone is Bryan's personal knowledge. Writing one into the other would
  publish his learning state to every machine and every runtime;
- the path is outside a vault Bryan named, or on a cloud-sync path.

The current pilot workspace is `~/second-brain/Learning/Agent-Assisted Planning/`.

See [`references/workspace-contract.md`](references/workspace-contract.md) for
the full layout and what may and may not be created in it.

## 1. Read before writing

In order, every session:

1. The vault's own `AGENTS.md`. It overrides everything below for that vault —
   frontmatter shape, filenames, linking, commit discipline.
2. The workspace's `INDEX.md`: mission, observable success, constraints, out of
   scope, current orientation.
3. `RESOURCES.md`.
4. Every existing record in `learning-records/`, if the directory exists.

Never open a session by teaching. What has already been demonstrated determines
what is worth teaching next, and only the records say what that is.

## 2. Assess before selecting new material

Before choosing anything new, run a **short** assessment — a few targeted
questions or one small real task against what the records claim is known. Two
things come out of it:

- **Calibration.** A record says the concept is known; the assessment says
  whether it is *usable*. Where they disagree, the assessment wins and the
  record gets a correction.
- **The next step.** Teach the most relevant thing that is genuinely just past
  the current edge — challenging enough to require effort, close enough to
  succeed.

Keep it short. An assessment that becomes an exam is a session Bryan will not
want to repeat.

## 3. Exposure is not understanding

The distinction this skill exists to protect:

| | |
|---|---|
| **Exposure** | The material was covered. Bryan read it, you explained it, it appeared in a session. |
| **Demonstrated understanding** | Bryan used the concept correctly on something you did not hand him — answered a question that required it, applied it to real work, caught an error with it, or explained why an alternative was wrong. |

Only demonstrated understanding raises the floor. Coverage never does. Fluency
in the moment is not retention: prefer retrieval from memory, spacing across
sessions, and application to real work over re-explanation.

## 4. Ground every claim

Never teach from parametric memory. Use the same research and citation
discipline as any other factual work here: find high-trust primary sources,
cite them inline where the claim matters, and record them in `RESOURCES.md` with
what each is good for.

Label an unsourced claim as your own inference. "I think" is honest; a confident
unsourced assertion inside a learning record is a fabricated foundation for
everything built on it later.

## 5. Apply to real work first

The preferred application surface is **Bryan's actual work** — a live
`wayfinder` map, a real `grilling` session, an issue he is genuinely planning.
Synthetic exercises are the fallback, used when no real surface is available
right now.

This is a deliberate departure from the upstream skill, which builds
self-contained exercises. Bryan's mission is a skill he exercises weekly; the
real thing is both better practice and better evidence.

## 6. Propose a slate before writing a record

A learning record is written **only** after Bryan approves it. Present the
proposed record — what was learned, the evidence, and why it changes what to
teach next — and wait.

Write one only when there is real evidence:

- Bryan demonstrated genuine understanding of something non-trivial;
- Bryan disclosed prior knowledge, so future sessions do not re-teach it;
- a misconception was corrected — the highest-value kind, because it predicts
  where related topics will stumble;
- the mission shifted in response to what he learned.

Do **not** write one for material merely covered. A zero-record session is a
successful session.

Format and numbering: [`references/learning-record.md`](references/learning-record.md).

## 7. Corrections supersede; they never delete

When a later understanding contradicts an earlier record, mark the old one
superseded and point at the new one. The history of how understanding changed is
itself signal — it shows which ideas were sticky and which had to be unlearned.
Never delete a record, and never quietly rewrite one.

The same applies to the mission: revise `INDEX.md` with Bryan's confirmation and
record *why* it changed.

## 8. End every session with a choice

Offer these, and let Bryan pick:

1. **New material** — the next thing past the current edge.
2. **Retrieval review** — recall something from an earlier session, unaided.
3. **Real-work application** — take it into a live effort.
4. **Revise the mission** — what he cares about has moved.
5. **Complete** — the mission's observable success criteria are met.

## Boundaries

- **Never copy the learning zone into Hindsight.** The zone is Bryan's exact,
  curated knowledge; Hindsight holds learned agent experience. A recalled memory
  about a session is **not evidence** that Bryan learned anything, and must
  never stand in for a record backed by demonstrated understanding.
- **No scheduling.** No spaced-repetition cron, no reminders, no automation.
  Bryan invokes this when he wants it.
- **No HTML lessons, stylesheets, reusable widgets, or quizzes.** The upstream
  skill builds all of them; none is adopted. They are earned by real use, not
  scaffolded up front.
- **Never write outside the resolved workspace** except to the vault surfaces
  that vault's `AGENTS.md` sanctions.
- **Never post, publish, or share** any of it.

## Related

- `wayfinder` / `grilling` — the preferred real-work application surface.
- `vault-pkm` — cross-vault conventions; the vault's own `AGENTS.md` overrides it.
- `voice-bryan` — wording for anything another person will read.
