# Bryan's Personal Routine Contract

This is the operating contract for the three-week personal-alignment pilot implemented on 2026-07-19. The canonical reasoning is in `/Users/bryan/second-brain/Explorations/2026-07-19-hermes-personal-alignment-routines.md`.

## Desired outcomes

Reduce mental load, improve the work-to-personal transition, reconnect Bryan with deliberately selected goals, support movement or restorative action, preserve gratitude and accomplishments, and identify bounded work Hermes can execute. The routine must not become another administrative obligation.

## System boundaries

- Apple Reminders holds simple self-contained actions requiring no thought.
- The physical whiteboard remains a visible, deliberately lossy cue surface.
- Vaults hold reflection, planning, decisions, learning, and durable project context.
- Hermes initiates, reviews context, resurfaces with reasons, facilitates the routine, and updates vault artifacts after participation.
- SGG retains detailed work planning. Personal artifacts contain only work highlights, pressure, promises, and capacity effects.
- Cross-vault references use names and paths, not wikilinks.

Generated briefings are ephemeral. If Bryan does not participate, create no note and infer no feelings, gratitude, alcohol use, wins, or conclusions.

## Cadence and suppression

- Weekdays: 5:00 PM Pacific, or when Bryan starts a close earlier.
- Saturday: 11:00 AM Pacific, or when Bryan starts earlier.
- Sunday: 11:00 AM Pacific, or when Bryan starts earlier.

A completed daily spoke suppresses that day's weekday/Saturday reminder. A created next-week hub suppresses Sunday's reminder. Suppression emits `[SILENT]` and still counts as a pilot run.

## Source review

The collector reads bounded, read-only context from:

- `second-brain`, including the current weekly hub and recent project activity;
- canonical SGG notes for concise work-capacity context;
- all Apple calendars;
- incomplete Apple Reminders;
- Apple Mail on Sunday, filtered to commitments, appointments, travel, purchases requiring action, property/vehicle projects, family/shared plans, important people, or active goals;
- IP-geolocated `wttr.in` weather, currently resolving to Bend, Oregon;
- Bryan's physical whiteboard through his report during the reset.

Traci's calendar is included only when an event affects shared availability, transportation, household responsibilities, date planning, or an opportunity for support. Source failure means unknown, not empty.

## Artifact paths

- Daily spoke: `Journal/YYYY-MM-DD-daily-check-in.md`
- Weekly hub: `Journal/MONDAY-YYYY-MM-DD-weekly-plan.md`, rendered as `Journal/YYYY-MM-DD-weekly-plan.md` using that Monday's date
- Vault templates: `Templates/Daily Personal Check-in.md` and `Templates/Weekly Planning.md`

The Sunday reset finalizes the current Monday-dated hub when present and creates the next Monday-dated hub. Daily spokes are linked near the bottom. Canonical project notes are updated when project state changes.

Participating through a resting point authorizes these exact non-draft captures and normal vault synchronization without another prompt. It does not authorize unrelated writes or execution of merely resurfaced work.

## Interaction contracts

### Weekday close

Ask about energy, anything weighing on Bryan, and one specific gratitude. Adaptively ask about a win and what would make the evening intentional. Mark work as over, reconnect with no more than the useful portion of the weekly direction, and choose an action suited to real energy.

### Saturday orientation

Surface what remains relevant without treating the weekend as a rescue deadline. Distinguish completed, deliberately deprioritized, renegotiated, blocked, avoided, and genuinely missed outcomes.

### Sunday reset

Review how the week felt, wins and meaningful partial progress, goal outcomes, patterns, coming constraints and opportunities, candidate projects with resurfacing reasons, adaptive active goals, explicit parked projects, possible Hermes delegation, and a short whiteboard slate.

## Growth and challenge

Challenge repeated patterns rather than isolated low-energy days. Appropriate signals include repeatedly skipped movement, promises sliding without renegotiation, persistent avoidance of a selected project, or leisure repeatedly labeled rest despite not restoring Bryan.

Functional Bodybuilding workouts are already programmed. Dogs outside, yoga, sauna, another small physical reset, or genuine recovery can each be a valid depleted-day win.

Alcohol direction: as close to abstinence as realistically possible, no alcohol brought home, no more than two drinks on an occasion, and movement toward less than monthly. Avoid perfectionism while remaining direct about boundary violations, worsening frequency, or safety risk.

## Autonomy boundary

Resurfacing is not execution authorization. Hermes may execute ordinary steps only after an agreed plan defines scope, intended outcome, constraints, permitted actions, evidence, review points, and stop conditions.

## Pilot operation

### Remote workspace

The private encrypted Matrix room named `Personal / Second Brain` is the remote
interaction surface for this pilot. Scheduled personal briefings deliver there;
Bryan can continue, redirect, or stop the conversation from that room. The room
is not canonical storage: `~/second-brain` remains the source of truth, and only
participated reflection is captured under the vault rules.

The room is intentionally scoped to one human domain rather than one agent. It
does not broaden the routine's authority: briefings may gather, synthesize, and
recommend, while further execution still requires an agreed plan under the
autonomy boundary above.

Tracked source lives under `/Users/bryan/code/dotfiles/hermes/`:

- collector: `scripts/personal-alignment-brief.py`
- Mail collector: `scripts/personal-mail-messages.js`
- prompts: `automations/personal-*/prompt.md`
- managed skill: `skills/productivity/personal-routine-automation/`
- cron source: `manifest.json`

Jobs:

- Personal Weekday Close: 15 scheduled pilot runs
- Personal Saturday Orientation: 3 scheduled pilot runs
- Personal Sunday Reset: one implementation test plus 3 scheduled pilot runs

The final Sunday is 2026-08-09. Evaluate mental load, transition quality, intentional movement/time, follow-through, artifact usefulness, noise, and useful delegation. Decide explicitly whether to stop, revise, or continue.
