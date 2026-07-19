# Lightweight Planning Experiments

Use these when the user wants more daily/weekly reflection or planning, but the vault shows that a previous planning system went unused. The goal is to test a behavior before building infrastructure.

## Design constraints

- Reversible: removal should require deleting at most a few notes or sections.
- Low ceremony: no plugins, dashboards, or taxonomy changes for the pilot.
- Attached to an existing habit or active project.
- Short: normally one or two weeks.
- Observable: define what useful evidence would justify continuation.
- Honest: lack of use is a result, not a compliance failure.

## Pilot A: Weekly resting-point note

For two weeks, create one short weekly note only when reviewing active work:

```markdown
# Week of YYYY-MM-DD

## What moved
- ...

## What is stuck
- ...

## What matters next
- ...

## Worth preserving
- [[...]]
```

Success signal: both notes are used to make or revisit at least one real choice. If they become status reports nobody consults, stop.

## Pilot B: Append-only project pulse

Instead of introducing a Journal folder, add a dated `## Pulse` entry to one active project note once or twice a week:

```markdown
### YYYY-MM-DD
- Changed:
- Learned:
- Next:
```

Success signal: the pulse improves continuity when returning to the project. Promote recurring insights into atomic notes rather than allowing the project log to become the permanent knowledge store.

## Pilot C: Capture prompts without mandatory notes

Use three prompts during a natural review:

1. What changed my mind?
2. What am I avoiding or repeatedly rediscovering?
3. What deserves a durable atomic note?

Only create a note when an answer clears the vault's normal capture threshold.

Success signal: at least one useful exploration, decision, or idea emerges without producing low-value diary entries.

## Pilot D: Generated workday handoff note

Use this when a morning briefing is useful and the user explicitly wants a durable daily artifact, but canonical project notes should not be rewritten by unattended synthesis.

Run it for one or two weeks with one file per workday, such as `workdays/YYYY-MM-DD.md`:

```markdown
# Workday — YYYY-MM-DD

<!-- BEGIN GENERATED MORNING BRIEF -->
## Starting point
## Intended outcome
## First action
## Schedule constraints
## Active watch list
<!-- END GENERATED MORNING BRIEF -->

## Day log

## End-of-day handoff
- **Outcome:**
- **Changed:**
- **Carry forward:**

## Canonical context
- [[status]]
```

Design rules:

- Declare the workday note noncanonical; current status/index/MOC notes always win.
- On rerun, replace only the marker-bounded generated block and preserve every manual byte outside it.
- Read the previous workday note as carry-forward evidence, not as automatic truth.
- If notes are Git-synchronized, stage only the dated file and fail closed on divergence or unrelated tracked/staged changes. Never force, reset, stash, or absorb unrelated untracked files.
- Do not add an automatic end-of-day job until actual use shows that the manual handoff is valuable and consistently missing.

Success signal: the previous note materially improves at least two morning restarts or handoffs, while the user returns to the Day log or End-of-day fields voluntarily. Stop if the notes merely duplicate the morning message or create repository churn nobody consults.

## Review questions

At the end of the pilot, ask:

- Did this improve a decision, restart, or handoff?
- Did the user voluntarily return to the artifact?
- Which field or prompt produced value?
- What felt like administrative overhead?
- Should it stop, continue unchanged, or earn one small refinement?

Do not make the pilot permanent merely because it was completed. Continued voluntary use is the stronger signal.

## Session learning: reconciling intent with vault history

A user may sincerely want more daily or weekly thinking while their vault explicitly records that prior planning machinery was dropped for non-use. Do not choose one statement and ignore the other. Preserve both facts: the desired outcome remains valid, while the previous implementation is evidence about what not to repeat.

Investigate *why* the system went unused. If the user valued the output but repeatedly failed to remember or initiate the ritual, reliable agent-initiated prompting changes a real design variable and can justify a fresh pilot. If the artifacts themselves were ignored, automation may only produce more clutter. In either case, offer a minimal pilot aimed at the outcome, preserve no unattended artifact when participation is absent, and do not revive the abandoned system wholesale.
