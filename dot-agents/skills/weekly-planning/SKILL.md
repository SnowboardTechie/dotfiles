---
name: weekly-planning
description: Guided weekly planning session for ADHD - Q&A flow that fills out the Weekly Planning template in Second Brain
---

# Weekly Planning — Guided Session

A structured Q&A session that walks Bryan through his weekly planning. Uses the VOMIT system as the process backbone, outputs a filled Weekly Planning note in the Second Brain vault.

## When to Use

- Monday morning planning
- User says "let's plan the week", "weekly planning", "plan my week"
- `/weekly-planning` command

## Quick Reference

```
/weekly-planning    # start a new weekly planning session
```

---

## Vault & Template Location

```
VAULT: ~/notes/second-brain
TEMPLATE: ~/notes/second-brain/Templates/Weekly Planning.md
OUTPUT: ~/notes/second-brain/Journal/{YYYY-MM-DD}-weekly-plan.md
```

If `Journal/` doesn't exist, create it.

---

## Session Flow

Run this as an interactive Q&A using the `question` tool. Each phase maps to a section of the template. Keep it conversational — this isn't a form, it's a thinking session.

### Phase 0: Setup

Before asking anything:

1. Check for last week's planning note: look in `~/notes/second-brain/Journal/` for the most recent `*-weekly-plan.md`
2. If found, read it — especially the "This Week's Rocks" and "End of Week" sections
3. Note any incomplete rocks or carry-forward items to reference during planning

### Phase 1: Vent (Clear the Noise)

> The VOMIT system starts with Vent. ADHD brains can't plan when they're full of noise.

Ask:

```
Before we plan — what's on your mind right now? Any stress, frustration, or mental noise you want to dump out first? This doesn't need to be organized. Just get it out.
```

- Let them vent freely
- Don't try to solve anything here
- Acknowledge what they shared, then transition: "Good, that's out of your head now. Let's look at last week."

### Phase 2: Last Week Review

> If there's a previous weekly note, reference specific rocks from it.

Ask using the `question` tool with options based on last week's rocks. If no previous note exists, ask open-ended:

```
question: "How did last week go?"
header: "Last week"
options:
  - label: "Crushed it"
    description: "Got most/all rocks done"
  - label: "Mixed bag"
    description: "Some progress, some dropped"
  - label: "Rough week"
    description: "Not much landed"
  - label: "First week"
    description: "No previous plan to review"
```

Then follow up based on their answer. For each of last week's rocks, ask:

```
What happened with [rock]? Done, in progress, or dropped?
```

Collect:
- **Wins** — what got done (celebrate briefly, dopamine matters)
- **Dropped** — what didn't happen (no judgment, just note it)
- **Carry forward** — anything that should become a rock this week

### Phase 3: Obligations (VOMIT - O)

> Surface what actually needs doing. "Will it make the boat go faster?"

Ask:

```
What obligations or commitments do you have this week? Work deadlines, appointments, things you promised someone — anything with a real external deadline or expectation.
```

This grounds the rocks in reality. Some rocks might be obligations, some might be personal goals.

### Phase 4: Pick 3 Rocks

> This is the core decision. Constrain to exactly 3.

Present what you've gathered:
- Carry-forward items from last week
- Obligations surfaced in Phase 3
- Any items from their Projects TODO if referenced

Then ask:

```
question: "Based on everything above — what are your 3 rocks for this week? These should be the 3 things that, if you did nothing else, you'd feel good about the week."
header: "3 Rocks"
```

For each rock, follow up:

```
Why does [rock] matter this week specifically? (One sentence is fine.)
```

**If they list more than 3:** Gently push back. "You listed [N]. The constraint is the feature — which 3 matter most? The rest can wait."

**If they list fewer than 3:** That's fine. 2 rocks is a real week. 1 rock with full focus is better than 3 with scattered attention.

### Phase 5: Energy Routing

Ask:

```
Let's set up your "when stuck" options. For each energy level, what's one thing you could do?

⚡ High energy (focused, sharp) → what task needs your best brain?
🔧 Medium energy (functional, steady) → what maintenance or routine task?
📖 Low energy (tired, scattered) → what passive or easy thing could you do?
```

These don't need to be rocks. They can be anything — chores, reading, organizing, walks. The point is having a pre-decided answer for "I don't know what to do right now."

### Phase 6: Today's One Thing

Ask:

```
What's the ONE thing you're going to do today that moves one of your rocks forward? Just one.
```

### Phase 7: Generate the Note

Using all collected answers, generate the weekly planning note:

1. Use the template structure from `~/notes/second-brain/Templates/Weekly Planning.md`
2. Fill in all sections with their answers
3. Include the whiteboard section pre-formatted for easy copying
4. Add any wikilinks to relevant vault notes (projects, routines, etc.)
5. Save to `~/notes/second-brain/Journal/{YYYY-MM-DD}-weekly-plan.md`

### Phase 8: Whiteboard Summary

After saving, present the whiteboard content in a clean block they can copy to the physical board:

```
Here's what goes on your whiteboard this week:

THIS WEEK'S 3 ROCKS
━━━━━━━━━━━━━━━━━━━
1. {rock 1}
2. {rock 2}
3. {rock 3}

TODAY → {today's one thing}

WHEN STUCK:
⚡ High   → {high energy task}
🔧 Med    → {med energy task}
📖 Low    → {low energy task}
```

---

## Tone Guidelines

- **Warm but direct.** This is a thinking partner, not a therapist or a drill sergeant.
- **No judgment on bad weeks.** Dropped rocks happen. Name them, move on.
- **Celebrate wins briefly.** ADHD brains need the dopamine hit from acknowledgment.
- **Push back on overcommitment gently.** More than 3 rocks = scattered attention = nothing lands.
- **Keep it moving.** The whole session should take 5-10 minutes. Don't over-discuss.

---

## Edge Cases

**User is having a really rough day:**
Don't force the full flow. Ask: "Do you want to do the full planning session, or just pick one rock and call it a week?" One rock is valid.

**User wants to skip the vent:**
Let them. It's optional. Jump to Phase 2.

**No previous weekly note exists:**
Skip Phase 2's rock review. Ask open-ended: "How was last week in general?"

**User is mid-week:**
Adjust language — "rest of the week" instead of "this week." Still pick 3 rocks (or fewer).

**User says they don't know what their rocks should be:**
Pull from `~/notes/second-brain/Projects TODO.md` and present the list. Ask: "Any of these calling to you this week?"

---

## Dependencies

- **Obsidian skill** — for vault path conventions and wikilink syntax

---

## Guardrails

- Do NOT skip the vent phase unless the user explicitly asks to
- Do NOT allow more than 3 rocks without pushback
- Do NOT make the session feel like a performance review — it's planning, not grading
- Do NOT write the note until all phases are complete
- Do NOT add rocks the user didn't choose — this is their plan, not yours
- ALWAYS present the whiteboard summary at the end — it's the bridge between digital and physical
