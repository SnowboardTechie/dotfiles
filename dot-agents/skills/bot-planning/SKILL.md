---
name: bot-planning
description: "Use when adding, changing or retiring one of Bryan's bots."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [bots, profiles, routines, planning, notifications]
    related_skills: [agent-persona-design, hermes-agent, scheduled-automation-change-management, vault-pkm]
---

# Bot planning

Bryan's bots are Hermes profiles. Each is one continuous thread ("Bot Chat") for one area of his life or work that he checks back on: shredder (fitness), ledger (taxes), writer, syllabus (study list), sgg (SGG work), home (house upkeep and projects), gear (bikes, motorcycles, vehicles, RV, snowboard gear, garage), ballot (elections, neutral) and flip (eBay). The current roster and routines are in the decision note below. He reaches them through the Bots tab in Hermes Desktop (Studio, MacBook, Gnarbox) and Hermex on his iPhone, and bot replies are what notify his phone. This skill decides **whether** something should be a bot and plans it. The persona rubric lives in `agent-persona-design`; build mechanics live in the `hermes-agent` skill's `references/bot-profiles.md`.

## 1. Place the request before building anything

| What it is | Where it goes |
|---|---|
| An area he regularly attends to and checks back on | Its own bot (or a new routine on the bot that already owns that area) |
| A recurring brief or work update (morning brief, recap, triage) | The bot for that area, delivered into its Bot Chat |
| Something that needs a reaction (a service down, a release landed, an approval) | A Matrix alert. Matrix is alerts only; he replies in the alert's thread when he wants to talk about it |
| A one-off question or deep work | Main Hermes (terminal, Rex). Not a bot |
| Shared with Traci (Gratifood) | Wherever she can see it (the shared Matrix room) |

Then check, in order:

1. **Does an existing bot already own this area?** Add a routine there before creating a bot. Overlapping bots split the thread he checks.
2. **Has he stopped something like it before?** Search past sessions (`session_search`, user role) for "stop" plus the name. He stopped the Personal Morning Brief and Personal Weekly Orientation on 2026-10-19; don't bring back a stopped routine under a new name.
3. **Is there a real source of truth?** Prefer a bot that reads what he already keeps (vault notes, Reminders lists, an app's API) over one that asks him to keep a new list.
4. **Will it be quiet?** Every routine must have a clear "nothing to say" case that replies `[SILENT]`; a bot that posts noise trains him to ignore its notifications.

Present the placement and its reason; let him decide. When he asks for ideas, review past sessions for recurring needs and offer them as invitations with the evidence behind each.

## 2. Design interview (short, one question at a time when an answer changes the next)

- **Job:** one sentence. What area, and what "where things stand" looks like in its latest message.
- **Split:** if one area has different sources or rhythms (house vs vehicles), make two bots; if they share both, keep one.
- **Sources:** which vault notes, Reminders lists, files or APIs it reads; which it may write (and whether it commits and pushes the vault).
- **Routines:** schedule, what each one says, and when it stays silent. Prefer one script-gated daily or monthly check that speaks only when something is due over many fixed-date jobs.
- **Never list:** side effects it never takes (buy, post, send, contact, file, pay, complete reminders unless asked).
- **Voice:** from the persona rubric (`agent-persona-design`): calm and dated for reminders, warm and conversational for coaching.

## 3. Build, prove, cut over

1. Build the profile, persona, memory and skills per `hermes-agent` → `references/bot-profiles.md`.
1a. Give it reminders, like every bot: symlink `personal/bot-reminders` into its skills, add the SOUL "## Reminders" block, seed `workspace/reminder-lists.json` (`{"lists": []}` unless Bryan approves lists), copy a `scripts/reminders_evening.py` wrapper from an existing bot, and create its `[bot:<name>] Evening reminder check` (19:15, script-only, `--deliver bot-chat`) with `~/.local/bin/hermes`.
2. Prove one routine end to end: a one-shot test that lands in the Bot Chat and reaches his **locked** phone. Remove the test job and script afterwards.
3. When it replaces an older routine (Grok Bot, a Matrix brief), the new routine still goes live as part of the build. Tell Bryan exactly which old routine to switch off so nothing runs twice. Don't quietly leave the new one paused until "cutover": he expects a migrated bot's check-ins and recaps to be running, and finding them paused reads as unfinished work.
4. Record the bot in the decision note `~/second-brain/Decisions/2026-11-02-decision-move-personal-agents-from-grok-bot-to-hermes.md` (roster and routines), committed and pushed.

## 4. After it's live

- The weekly "Bot fleet review" routine (main Hermes, Mondays) flags failed or noisy routines and friction in Bot Chats. Fixes it proposes are Bryan's to pick.
- Retiring a bot: pause its routines, archive nothing he hasn't asked to lose, and note the retirement and why in the decision note.

## Pitfalls

- **Building on the first option found.** Survey official surfaces and what other Hermes users run before proposing an app, plugin or platform, and don't reshape agreed plans around a single search hit.
- **Overclaiming "one thread".** The Bot Chat is the canonical thread, but ordinary side sessions on the same profile are possible (profile switcher, "New chat"). Say so plainly.
- **Assuming push.** Push comes from Hermex's plugin with a local bots-only filter; a routine that ends `[SILENT]` sends nothing, and main-profile replies never push.
