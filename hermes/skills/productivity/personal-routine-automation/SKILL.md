---
name: personal-routine-automation
description: Design and tune proactive personal daily transitions, weekend check-ins, and weekly resets that combine reflection, goals, vault context, and bounded agent delegation without turning life into a work backlog.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  created_by: agent
  hermes:
    tags: [productivity, routines, reflection, weekly-reset, automation, pkm, wellbeing]
    related_skills: [vault-pkm, workday-briefing-automation, scheduled-automation-change-management, skill-retrospective]
---

# Personal Routine Automation

## Overview

Use this skill when a user wants Hermes to proactively initiate personal reflection, goal alignment, transitions, or weekly planning. Design a small behavioral loop that reduces cognitive load and supports intentional action. Do not reproduce a work dashboard for the user's private life.

The core loop is:

> proactive invitation → honest check-in → bounded choice → vault capture → agreed delegation → later review

Read `references/bryan-personal-routine-contract.md` when operating Bryan's personal routine in `~/second-brain`.

## 1. Diagnose the Actual Failure

Before reviving or replacing an earlier planning system, determine why it went unused:

- **Initiation friction:** the user valued the routine but did not remember to start it.
- **Interaction friction:** it was too long, rigid, or demanding.
- **Artifact friction:** it duplicated other systems or produced material nobody revisited.
- **Outcome failure:** it did not improve decisions, continuity, action, or wellbeing.

Automation materially changes a workflow when initiation friction was the main failure. It does not rescue a routine whose interaction, artifact, or outcome was poor. Start with a short, reversible pilot even when proactive initiation appears to solve the missing trigger.

## 2. Establish System Boundaries

Keep each system in a clear role:

- A reminder/task system holds simple, self-contained actions that require little or no reasoning.
- A vault holds thoughts, plans, decisions, learning, project context, and durable reflection.
- Hermes reviews those sources, resurfaces relevant context, facilitates the routine, and updates the vault according to local PKM rules.

Do not duplicate every chore into the vault. Do not let a journal become a second canonical project status page. Read `vault-pkm` and the vault-local instructions before writing.

## 3. Separate Automation From Autonomy

Automated initiation may remind, brief, ask, and resurface. It does not authorize the agent to advance every note, aspiration, or stale project.

Autonomous execution begins only after an explicitly agreed plan establishes:

- scope and intended outcome;
- constraints and prohibited actions;
- permitted actions that do not require another approval;
- evidence and verification requirements;
- review points;
- stop and escalation conditions.

Once agreed, ordinary steps inside that contract need not be reauthorized. Return when work is complete, a planned review point is reached, or a true blocker or boundary appears.

## 4. Give Each Cadence One Job

### Daily transition

Use a daily check-in to help the user cross a boundary, such as leaving work and entering personal time. It may:

- ask how the user feels without scoring performance;
- capture gratitude;
- reconnect the user with selected weekly goals;
- choose one action suited to actual energy;
- prompt a physical, outdoor, relational, creative, or restorative activity;
- identify a promise that must be kept or renegotiated.

The aim is intentional transition, not planning the entire evening.

### Saturday orientation

Use a weekend check-in to surface weekly goals that remain and help the user choose intentionally. Do not frame the weekend as a rescue operation for everything unfinished.

### Weekly reset

Use the weekly reset to produce orientation rather than a fully scheduled week:

1. Reflect on how the previous week felt and why.
2. Review major calendar constraints and visible promises.
3. Choose a few meaningful outcomes for the next week.
4. Select active projects.
5. Explicitly park valued projects that are not active this week.
6. Identify planned work Hermes can execute.
7. Notice repeated friction, corrections, or manual effort that should invoke or update a skill.

## 5. Support Growth Without Perfectionism

Do not equate improvement with maximum output. On a depleted day, meaningful progress may be movement, time outdoors, caring for relationships or animals, yoga, recovery, or one small deliberate action.

Challenge patterns rather than isolated low-energy days. Appropriate challenge signals include:

- repeatedly skipping a planned commitment;
- letting a visible promise slide without renegotiation;
- avoiding a deliberately selected project across multiple check-ins;
- repeatedly defaulting to leisure that leaves the user feeling worse;
- describing a repeated avoidance pattern as restorative rest.

Challenge with curiosity and evidence. Help choose a smaller honest action rather than moralizing or expanding the checklist.

## 6. Use a Weekly Hub With Optional Daily Spokes

When the user wants a durable journal and planning record, prefer one dated weekly note as the hub. Include:

- selected goals with honest completion state;
- major calendar context;
- active and parked projects;
- accomplishments, including valuable work not predicted by the plan;
- a synthesis of how the week felt;
- gratitude or emotional patterns worth remembering;
- planned Hermes delegations;
- links to relevant canonical project notes;
- links to optional daily journal spokes.

Daily notes preserve feelings, gratitude, and detail. The weekly hub must contain enough synthesis to remain useful without opening every daily note. Keep each dated weekly note as its own historical artifact instead of rewriting a permanent `current-week` page.

When the routine changes project state, update the relevant canonical project note through `vault-pkm`. The weekly journal is historical context, not a substitute for canonical status.

## 7. Distinguish Reminder and Working Surfaces

A proactive delivery may exist only to initiate the routine. The reminder should:

- contain enough context to remain useful if the user skips the interaction;
- invite the user into the preferred working surface for the substantive conversation;
- avoid implying that delivery completed the reflection;
- distinguish reminder delivery, completed check-in, and vault update.

If the user engages before the scheduled time, suppress or adapt the later reminder rather than sending a redundant prompt. Treat cross-surface continuation as an explicit design requirement, not an assumption.

## 8. Pilot and Tune

Run a one- or two-week pilot before adding more fields, jobs, templates, or integrations. Review:

- Did proactive initiation increase voluntary engagement?
- Did the routine improve a transition, choice, restart, or sense of alignment?
- Was the weekly hub useful during the week or in retrospect?
- Which prompts produced value, and which felt performative?
- Did resurfacing become noisy?
- Did the agent respect the boundary between proposing and advancing only agreed plans?
- Did the artifacts duplicate reminders or canonical project notes?

Keep, refine, or remove each component based on observed use rather than completion of the pilot.

## 9. Bryan's Interactive Operating Procedure

For Bryan, read `references/bryan-personal-routine-contract.md`, `/Users/bryan/second-brain/AGENTS.md`, and the canonical exploration named there before capture.

Start every interactive routine by using `date` for Pacific time and running:

```text
python3 /Users/bryan/.hermes/scripts/personal-alignment-brief.py --mode MODE
```

Use `weekday`, `saturday`, or `sunday`. Read only relevant source files named by the collector. Name intended paths before writing. No participation means no note, and generated Matrix text is never archived.

### Weekday and Saturday capture

Target `Journal/YYYY-MM-DD-daily-check-in.md`. Ask a compact first group about current energy, anything weighing on Bryan, and one specific gratitude. Adaptively ask what went well and what would make the remaining day intentional. Saturday also distinguishes what still matters from what can be deliberately deprioritized, renegotiated, or parked.

At a resting point, use `templates/daily-spoke.md`, record only Bryan's actual reflections and concise synthesis, link the Monday-dated weekly hub when present, and add the spoke under its `## Daily Reflections` section.

### Sunday capture

Use `Journal/CURRENT-MONDAY-weekly-plan.md` as the ending hub and `Journal/NEXT-MONDAY-weekly-plan.md` as the new hub. Review the current hub and spokes, relevant personal project notes, concise canonical SGG context, all calendars, incomplete Reminders, filtered recent Mail, weather, and the physical whiteboard through Bryan's report.

Guide the reset through feelings and gratitude, wins, honest goal outcomes, cross-day patterns, coming capacity, candidate resurfacing with reasons, adaptive active goals, an explicit parked list, bounded Hermes delegation, and a concise whiteboard slate. Finalize the current hub when it exists, create the next hub with `templates/weekly-hub.md`, link spokes, and update canonical project notes when state changed.

### Capture and synchronization authority

Participation through a resting point authorizes these exact vault writes without another approval prompt. Name every path, read back changes, stage exact non-draft paths, commit, push, and verify the remote SHA. This does not authorize unrelated files, public communication, or advancing a resurfaced project without an agreed plan.

### Direct but non-perfectionist challenge

Challenge repeated patterns, not isolated depleted days. Functional Bodybuilding is already programmed; encourage it when it fits, while dogs outside, yoga, sauna, another small physical reset, or genuine recovery can be meaningful wins. Bryan's alcohol direction is near-abstinence: no alcohol brought home, no more than two drinks on an occasion, and movement toward less than monthly. Do not infer use from silence, but do not soften a worsening or unsafe pattern.

## Verification Checklist

- [ ] The previous system's failure mechanism is explicit.
- [ ] Reminder, vault, and agent responsibilities do not overlap unnecessarily.
- [ ] Automated initiation is distinct from autonomous execution.
- [ ] Every autonomous path has an agreed plan and stop conditions.
- [ ] Daily, Saturday, and weekly routines have distinct jobs.
- [ ] Low-energy support permits recovery without normalizing repeated avoidance.
- [ ] The weekly hub is useful without reading every daily spoke.
- [ ] Canonical project notes remain authoritative.
- [ ] Reminder delivery does not masquerade as a completed check-in.
- [ ] The pilot has a review point and removable scope.

## Common Pitfalls

1. **Treating non-use as rejection.** First determine whether manual initiation was the actual failure.
2. **Turning personal life into a sprint board.** Preserve reflection, play, relationships, recovery, and deliberately parked projects.
3. **Automating unplanned advancement.** Proactive resurfacing is not execution authority.
4. **Creating duplicate task stores.** Keep simple chores in reminders and reasoning-rich material in the vault.
5. **Making a peak day the daily minimum.** Support variable energy and sustainable growth.
6. **Writing daily detail without weekly synthesis.** The hub should remain useful months later.
7. **Sending reminders after the user already engaged.** Prefer event-aware suppression or adaptation.
8. **Assuming the delivery surface is the working surface.** A message can invite a richer Hermes conversation elsewhere.
