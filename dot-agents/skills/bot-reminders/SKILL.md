---
name: bot-reminders
description: "Use when a bot adds, moves or follows up Apple Reminders."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [bots, reminders, apple, routines]
    related_skills: [bot-planning, hermes-agent]
---

# Bot reminders

Bryan's bots use Apple Reminders for nudges, so chat stays quiet. Reminders gives the nudge at the right moment: lock screen, Watch, snooze, location. The bot follows up afterward, when something slipped and needs a decision. Background and reasoning: `~/second-brain/Explorations/2026-11-04-bot-reminders-and-calendar-pattern.md`.

## 1. Connections (Bryan approves each one)

Each bot's approved lists are recorded in its own `<profile>/workspace/reminder-lists.json`. That file is the source of truth; the evening check reads it too. A bot touches only the lists in its file. Every other list is off limits: don't read it, don't write it.

```json
{"lists": [
  {"name": "Home ToDos", "access": "write", "approved": "2026-11-04", "why": "House upkeep and projects"},
  {"name": "Honey Do", "access": "read", "approved": "2026-11-04", "why": "Shared with Traci; write only when he asks for that exact reminder there"}
]}
```

- "write" means add, change the due date, title or notes, and complete or delete when he says so. It never means completing something on his behalf.
- "read" means read only. A read list can hold a reminder of yours only when he asked for that exact reminder there.
- A bot with no file, or an empty `lists`, has no connections yet.

Starting map (2026-11-04): Home writes Home ToDos and reads Honey Do; Gear writes RV Fix and Garage and reads Home ToDos. Ledger writes "Taxes" (created the same day). It holds one reminder per deadline, due on the deadline with its alarm at the 6-week heads-up, plus monthly bookkeeping. Ledger's chat routine keeps the 2-week and 3-day "nothing logged" checks. Every other bot started with none.

## 1a. When no connected list fits

When he asks to be reminded about something and none of your lists fits, don't fall back to a chat ping or a new routine. Offer one of these in one short message, with your recommendation first:

1. **A new list**, named plainly for the job ("Training", "Taxes", "Writing"). Check `remindctl list` first so you don't create a duplicate of one he already has.
2. **An existing list he names.** Suggest one only if its name clearly fits. If it might be shared with Traci (Honey Do, Shopping, Traci, the wishlists), say so and ask whether it should be read-only.
3. **No reminder**, if he'd rather skip it.

Change nothing until he says yes to a specific list. Then, in this order:

1. For a new list: `remindctl list "<name>" --create`.
2. Add the entry to your `reminder-lists.json`: name, access, today's date, and why. Write the file whole and keep the JSON valid.
3. Add the reminder he asked for (section 2).
4. Confirm in one line: the list is connected, and the reminder is on it.

The evening check picks up the new list on its next run. Never create, rename or delete a list, or widen access, without his yes in this conversation.

## 2. Adding a reminder

When Bryan says "remind me to X on <day>", create a reminder on the right write list instead of planning a chat ping. Then confirm in one line: what, which list, when.

```bash
remindctl add "Vacuum the house" --list "Home ToDos" --due 2026-11-06 \
  --notes "Added by Home bot (Hermes)" --json
```

- **Mark every reminder you create.** The last line of its notes is exactly `Added by <Bot> bot (Hermes)`, for example `Added by Home bot (Hermes)`. When there are real notes, put them first and the mark on its own last line. The evening check follows up only on marked reminders. Chores Bryan added himself stay his.
- **Dates.** Work out the absolute date (YYYY-MM-DD) from today's date. Don't pass words like "friday".
  - A date with no time makes an all-day reminder. His phone notifies at its usual "today" time.
  - With a time (`--due "2026-11-06 18:00"`), remindctl also sets an alarm at that time.
  - Ask for a time only if he implies one ("before dinner").
- **Repeating chores** (`--repeat weekly`): add ` · repeats` to the end of the mark line, for example `Added by Home bot (Hermes) · repeats`. Reminders handles repeating chores itself, so the evening check skips them.
- **Location** ("when I get to Home Depot"): `--location "<address>"`, plus `--leaving` when the reminder should fire on leaving.
- **Adopting one of his reminders**, when he asks you to look after it: add the mark line with `remindctl edit <id> --notes`. That command replaces all of the notes, so keep the existing text and append the mark.
- He names a list you have no write access to: say it isn't connected yet and offer to connect it (section 1a). Never write there anyway.
- **Routine vs reminder.** A one-off or personal "remind me" is a reminder. Your own scheduled routines (check-ins, recaps, deadline warnings) stay routines; don't turn them into reminders unless he asks.

## 3. Changing reminders

Use the full `id` from the `--json` output, never the numeric index; indexes shift.

- Move: `remindctl edit <id> --due <YYYY-MM-DD>`. `--due` doesn't move the alarm (checked with remindctl 0.3.9). When moving a timed reminder, pass the same new time to both: `--due "2026-11-07 18:00" --alarm "2026-11-07 18:00"`. When turning it into an all-day reminder, add `--clear-alarm`. Don't delete and recreate the reminder to fix the alarm.
- Done (only when he says it's done): `remindctl edit <id> --complete`
- Drop (only when he says drop it): `remindctl delete <id> --force`
- Reword: `remindctl edit <id> --title "..."`

Check the JSON output for the new due date or the completed state before you tell him it's done.

## 4. The evening check

Every bot has a script-only routine at 19:15 (`[bot:<name>] Evening reminder check`). The script is `scripts/evening_check.py` in this skill, run through a small wrapper in `<profile>/scripts/reminders_evening.py`. A bot with no lists costs nothing: the script reads an empty file and prints nothing.

- It reads every list in the bot's `reminder-lists.json`. Read lists only hold the bot's marked reminders when Bryan asked for one there. It takes the marked, non-repeating reminders that are still open and due today or earlier.
- It asks about each reminder once for each due date. If he doesn't answer, the reminder stays overdue and the weekend sweep names it, but the evening check doesn't ask about it again until its due date changes.
- It counts moves: each time a reminder's due date moves later, its count goes up. The state is kept in `<profile>/workspace/reminders-state.json`.
- Nothing to ask means no output, so no model use and no message.

When the routine arrives, send one short message:
- For each reminder: done, move to another day, or drop? Suggest one specific day.
- For a reminder that has moved 2 or more times, ask instead whether it's still worth keeping, put off to someday, or dropped.
- No guilt.

Don't change anything until he answers. Then apply section 3.

## Never

- Write to a list that isn't connected for you with write access.
- Complete, delete or reschedule a reminder he hasn't told you to.
- Touch reminders without your mark during follow-up, unless he points at one.
- Create or rename lists without his approval.
- Recreate a reminder that has disappeared. He deleted it or finished it.
- Edit your own routines because a failure notice arrived. Report the failure in one line and leave the fix to main Hermes or Bryan.
- Use Calendar. Calendar tooling isn't reviewed yet; it is a separate decision.
