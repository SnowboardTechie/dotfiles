# Bryan's Personal Routine Contract

This is the operating contract for Bryan's personal-alignment routines. The canonical reasoning and revisions are in the Apple Note `2026-07-19-hermes-personal-alignment-routines` (folder `Second Brain/Explorations`), read through the `apple-notes-pkm` helper. Since 2026-09-16 Apple Notes is the sole personal second brain; `/Users/bryan/second-brain` is a frozen rollback archive that no routine reads or writes.

## Desired outcomes

Reduce mental load, improve the work-to-personal transition, reconnect Bryan with deliberately selected goals, support movement or restorative action, preserve gratitude and accomplishments, and identify bounded work Hermes can execute. The routine must not become another administrative obligation.

## System boundaries

- Apple Reminders holds simple self-contained actions requiring no thought.
- The physical whiteboard remains a visible, deliberately lossy cue surface.
- The Apple Notes second brain holds reflection, planning, decisions, learning, and durable personal project context; project vaults hold project state.
- Hermes initiates, reviews context, resurfaces with reasons, facilitates the routine, and updates second-brain notes after participation.
- SGG retains detailed work planning. Personal artifacts contain only work highlights, pressure, promises, and capacity effects.
- Cross-backend references (project vault, repo, issue) are plain names, paths, or URLs; inside Notes, name other notes by exact title.

Generated briefings are ephemeral. If Bryan does not participate, create no note and infer no feelings, gratitude, alcohol use, wins, or conclusions.

## Cadence and suppression

- Weekday personal morning brief: 7:00 AM Pacific, delta-only and read-only, delivered to Second Brain before the 8:00 AM SGG work brief.
- Weekly personal orientation: Sunday at 11:00 AM Pacific, or when Bryan starts it earlier.
- Weekday closes and Saturday orientations remain available on demand but are not scheduled by default.

A created next-week hub suppresses Sunday's orientation. The morning brief suppresses itself when its bounded sources contain nothing materially new or newly actionable. Suppression emits `[SILENT]`.

## Source review

The collector reads bounded, read-only context from:

- the Apple Notes second brain, through bounded helper searches: the current weekly hub, its spokes, and the few relevant personal project notes;
- canonical SGG notes for concise work-capacity context;
- all Apple calendars;
- incomplete Apple Reminders;
- Apple Mail on Sunday, filtered to commitments, appointments, travel, purchases requiring action, property/vehicle projects, family/shared plans, important people, or active goals;
- location-specific `wttr.in` weather configured privately through `PERSONAL_WEATHER_LOCATION` or `~/.secrets/personal-weather-location`;
- Bryan's physical whiteboard through his report during the reset.

The weekday personal morning brief is a separate one-minute delta update. Its local collector passes only Bryan's non-work calendars, today's incomplete Reminders, actionable weather, and safe active-goal bullets extracted from the current weekly hub (one bounded title search plus one exact-id read in Apple Notes). It excludes every other note, the SGG vault, work repositories, GitHub, work mail, and the calendars named `Bryan @ Agile6` and `Traci`. Prohibited unattended topics are removed from calendar, reminder, and weekly-direction records before model access. The job never writes a note, never opens additional files, and never uses or mentions events from Traci's calendar. Its previous completed output is supplied for deduplication; unchanged standing items remain silent unless newly actionable or due for a bounded weekly resurfacing.

The scheduled weekly orientation collector is intentionally minimal: it exposes only the authoritative time and whether the coming Monday hub exists. Richer source review begins only after Bryan participates, using the interactive procedure below.

Subscription-calendar birthdays are informational, not availability constraints, unless separate evidence shows a gathering, call, travel, or other commitment. Source failure means unknown, not empty.

## Artifact locations (Apple Notes, folder `Second Brain/Journal`)

- Daily spoke: note titled `YYYY-MM-DD-daily-check-in`
- Weekly hub: note titled `YYYY-MM-DD-weekly-plan` using that Monday's date
- Shapes: `templates/daily-spoke.md` and `templates/weekly-hub.md` in this skill (the imported vault templates are historical)

The Sunday reset finalizes the current Monday-dated hub when present and creates the next Monday-dated hub. Daily spokes are named by title under the hub's `Daily Reflections` section. Canonical personal project notes are updated when project state changes.

Participating through a resting point authorizes these exact captures through the `apple-notes-pkm` helper (fresh `revision` on every append/replace, readback verified) without another prompt. It does not authorize unrelated writes or execution of merely resurfaced work.

## Interaction contracts

Interactive routines are conversations, not briefings or questionnaires. The scheduled weekly orientation opens with a brief welcome and exactly one concrete question. Collected context stays in reserve and is introduced only when it helps the next adaptive question. Do not dump the agenda, constraints, candidate list, or all reflection prompts at once, and do not ask Bryan to invoke another command in the same room.

### Weekday close

Ask about energy, anything weighing on Bryan, and one specific gratitude. Adaptively ask about a win and what would make the evening intentional. Mark work as over, reconnect with no more than the useful portion of the weekly direction, and choose an action suited to real energy.

### Saturday orientation

Surface what remains relevant without treating the weekend as a rescue deadline. Distinguish completed, deliberately deprioritized, renegotiated, blocked, avoided, and genuinely missed outcomes.

### Sunday reset

Review how the week felt, wins and meaningful partial progress, goal outcomes, patterns, coming constraints and opportunities, candidate projects with resurfacing reasons, adaptive active goals, explicit parked projects, possible Hermes delegation, and a short whiteboard slate.

Keep the reset in planning mode. Clarify only enough to define an outcome, then record it and move on rather than beginning research or execution inside the reset. If Bryan says a task is not for now, stop expanding it and return to the reset. Before suggesting a new plan or Hermes delegation for a named project, inspect its canonical notes or repository state for existing plans, issues, or active agents; ask rather than assume when current execution state is unavailable.

## Growth and challenge

Challenge repeated patterns rather than isolated low-energy days. Appropriate signals include repeatedly skipped movement, promises sliding without renegotiation, persistent avoidance of a selected project, or leisure repeatedly labeled rest despite not restoring Bryan.

Functional Bodybuilding workouts are already programmed. Dogs outside, yoga, sauna, another small physical reset, or genuine recovery can each be a valid depleted-day win.

Do not introduce alcohol, sobriety, abstinence, recovery, drinking boundaries, streaks, or equivalent euphemisms into personal routines unless Bryan explicitly raises that topic in the current conversation. Historical notes, previous goals, and silence do not authorize resurfacing it.

## Autonomy boundary

Resurfacing is not execution authorization. Hermes may execute ordinary steps only after an agreed plan defines scope, intended outcome, constraints, permitted actions, evidence, review points, and stop conditions.

## Current operation

### Remote workspace

The private encrypted Matrix room named `Second Brain` is the remote
interaction surface for this pilot. Scheduled personal briefings deliver there;
Bryan can continue, redirect, or stop the conversation from that room. The room
is not canonical storage: the Apple Notes `Second Brain` folder is the source of
truth, and only participated reflection is captured there under the
`apple-notes-pkm` rules.

Each personal cron is continuable: its delivery is mirrored into Bryan's
room-specific Hermes session as labelled cron context, so a reply in `Second
Brain` can continue the delivered briefing without restating it. The tracked
manifest names the room and a local environment key, while the Matrix account
identifier remains untracked. A delivered briefing is still not participation;
the existing capture and autonomy boundaries apply to every reply.

The room is intentionally scoped to one human domain rather than one agent. It
does not broaden the routine's authority: briefings may gather, synthesize, and
recommend, while further execution still requires an agreed plan under the
autonomy boundary above.

Tracked source lives under `/Users/bryan/code/dotfiles/hermes/`:

- collector: `scripts/personal-alignment-brief.py` (plus `scripts/personal-notes.py`-style shared lookup in `scripts/personal_notes.py`)
- Mail collector: `scripts/personal-mail-messages.js`
- prompts: `automations/personal-*/prompt.md`
- managed skill: `skills/productivity/personal-routine-automation/`
- cron source: `manifest.json`

Jobs:

- Personal Morning Brief: weekdays at 7:00 AM Pacific, recurring until removed, synthesized by the OpenAI Terra route from locally filtered inputs
- Personal Weekly Orientation: Sundays at 11:00 AM Pacific, recurring until removed, with a minimal collector and one-question opening
- Personal Weekday Close, Personal Saturday Orientation, and Personal Sunday Reset: completed finite pilot records retained for audit but not recreated

Review the revised morning and weekly routines after two weeks. Evaluate repetition, silence rate, useful replies, capture quality, privacy-boundary compliance, and whether the weekly hub improves subsequent reports. Keep, refine, or remove each component based on observed use.
