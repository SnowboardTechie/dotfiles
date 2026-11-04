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

A bot touches only the lists listed here for it. Every other list is off limits: don't read it, don't write it. Adding a row, changing access, or creating a list needs Bryan's approval first, then an update here and in the bot's SOUL.

| Bot | List | Access | Notes |
|---|---|---|---|
| home | Home ToDos | write | House upkeep and projects |
| home | Honey Do | read | Shared with Traci. Write only when Bryan asks for that exact reminder there |
| gear | RV Fix | write | RV jobs |
| gear | Garage | write | Bikes, motorcycles, vehicles, snowboard gear, the garage (created 2026-11-04) |
| gear | Home ToDos | read | Machine jobs that land there (existing weekend-check behavior) |

"Write" means add, change the due date, title or notes, and complete or delete when he says so. It never means completing something on his behalf.

Approved for later, not built yet: a Ledger "Taxes" list for deadline reminders.

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
- A request for a list you have no write access to: say which list it would go on and that it isn't connected yet. Offer the closest connected list. Never write there anyway.

## 3. Changing reminders

Use the full `id` from the `--json` output, never the numeric index; indexes shift.

- Move: `remindctl edit <id> --due <YYYY-MM-DD>`. `--due` doesn't move the alarm (checked with remindctl 0.3.9). When moving a timed reminder, pass the same new time to both: `--due "2026-11-07 18:00" --alarm "2026-11-07 18:00"`. When turning it into an all-day reminder, add `--clear-alarm`. Don't delete and recreate the reminder to fix the alarm.
- Done (only when he says it's done): `remindctl edit <id> --complete`
- Drop (only when he says drop it): `remindctl delete <id> --force`
- Reword: `remindctl edit <id> --title "..."`

Check the JSON output for the new due date or the completed state before you tell him it's done.

## 4. The evening check

Each bot with write lists has a script-only routine at 19:15 (`[bot:<name>] Evening reminder check`). The script is `scripts/evening_check.py` in this skill, run through a small wrapper in `<profile>/scripts/reminders_evening.py`.

- It reads the bot's write lists (and Honey Do for Home, which only holds marked reminders if Bryan asked for them there). It takes the marked, non-repeating reminders that are still open and due today or earlier.
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
