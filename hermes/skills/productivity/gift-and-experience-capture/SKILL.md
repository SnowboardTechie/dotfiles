---
name: gift-and-experience-capture
description: >
  Use whenever Bryan attributes a gift idea, preference, movie or show, restaurant,
  outing, activity, or date idea to a named person in any chat, especially phrases
  such as “Traci wants to see…”, “Dad would love…”, “save this for Mom”, or “we
  should go here”; also use when planning or shopping for gifts, dates, or shared
  experiences. Captures clear signals into person-specific notes in Bryan's
  second-brain vault and resurfaces them later without turning every mention into a
  task.
version: 1.0.0
author: Hermes Agent
metadata:
  created_by: agent
  hermes:
    tags: [gifts, dates, relationships, preferences, capture, pkm]
    related_skills: [vault-pkm]
---

# Gift and Experience Capture

## Purpose

Turn casual, attributable preference signals into useful future context. Bryan should
be able to mention an idea naturally in Matrix or another Hermes surface and trust
that it will be available when planning a date, choosing an experience, or shopping
for a gift.

The canonical system is a small compiled knowledge zone in
`/Users/bryan/second-brain`:

- Hub: `Gift and Experience Ideas.md`
- One detail note per person: `{Person} Gift and Experience Ideas.md`
- Event-specific plans remain separate and link to the relevant person note.

Load `vault-pkm` and follow `/Users/bryan/second-brain/AGENTS.md` before reading or
writing this zone. The vault, not Hermes memory or chat history, is canonical.

## Capture Contract

A statement authorizes capture without a second approval when all three are clear:

1. **Person** — a named or unambiguous person is associated with the idea.
2. **Candidate** — the movie, show, restaurant, item, activity, place, or experience
   is identifiable enough to preserve.
3. **Signal** — Bryan attributes interest, desire, suitability, or save-for-later
   intent to that person or to a shared date/experience.

Examples of clear signals:

- “Traci wants to see this movie.”
- “Traci said she wants to eat at this restaurant.”
- “Dad would love one of these.”
- “Save this as a possible gift for Mom.”
- “We should go here for a date.” when the partner is unambiguous from context.

Before the write, name the exact vault-relative person-note path in one short sentence,
then make the capture. Do not ask for confirmation after a clear signal. Afterward,
confirm the captured idea and path concisely.

Ask exactly one concise clarification question only when the person or capture intent
is genuinely ambiguous. Do not capture:

- a generic “this looks cool” with no person or planning intent;
- an agent-generated recommendation Bryan has not adopted;
- an inferred preference derived only from a person's traits;
- a hypothetical example used to discuss how the system works;
- a task or purchase commitment merely because an idea was captured.

If Bryan uses uncertain language such as “maybe for Dad,” capture the uncertainty in
the context instead of upgrading it to a known preference.

## Capture Workflow

1. Read the hub and search for an existing person note and duplicate idea.
2. Read the person note before editing. If none exists, announce the proposed path,
   create it at the vault root, and add its wikilink under the hub's `## People`
   section. Do not create a new folder or MOC for each person.
3. Append one row to `## Open Ideas` with:
   - capture date;
   - kind (`gift`, `date`, `movie`, `show`, `restaurant`, `food`, `activity`,
     `place`, or `other`);
   - the specific idea;
   - the attributed signal and any useful occasion, constraint, or uncertainty;
   - the user-provided URL or source when present.
4. Preserve exact names and user-provided URLs. Do not browse, enrich, estimate price,
   or invent details unless Bryan asks.
5. Deduplicate before appending. If the same open idea already exists, add only new
   context or a newer signal instead of creating another row.
6. Read back the changed section, inspect the diff, stage only the exact vault files,
   and follow the vault's commit-and-push rules.
7. Reply with a compact confirmation, not a planning discussion.

Escape Markdown table pipes inside captured text as `\|`. Use `—` when there is no
source URL. Keep one idea per row.

## Person Note Shape

Use this shape for the first capture involving a person:

```markdown
---
aliases:
  - {Person} Gift Ideas
  - {Person} Date Ideas
tags:
  - area/relationships
  - gifts
  - experiences
  - type/reference
created: YYYY-MM-DD
status: active
---

# {Person} — Gift and Experience Ideas

Part of [[Gift and Experience Ideas]].

## Preferences & Signals

_Durable, source-supported preferences that improve future choices._

## Open Ideas

| Captured | Kind | Idea | Signal / context | Source |
|---|---|---|---|---|

## Used or Retired

| Updated | Idea | Outcome |
|---|---|---|

## Related
```

For people other than Bryan's partner, omit the `{Person} Date Ideas` alias when it
would be misleading. A preference belongs under `## Preferences & Signals` only when
it is durable and directly supported; ordinary one-off candidates remain in the open
ideas table.

## Lifecycle Updates

When Bryan later says an idea was bought, booked, visited, watched, rejected, or is no
longer relevant:

1. Find the exact open row.
2. Remove it from `## Open Ideas`.
3. Add it to `## Used or Retired` with the update date and outcome.
4. Preserve why it was originally considered when that context remains useful.

Do not silently delete history. Do not infer completion from calendar events, receipts,
or elapsed time unless Bryan asks for reconciliation and the evidence is explicit.

## Retrieval and Planning

When Bryan asks for gift, birthday, holiday, anniversary, restaurant, date, movie,
show, or outing ideas:

1. Start at `Gift and Experience Ideas.md`.
2. Read the relevant person note and linked event-specific plans.
3. Surface relevant open ideas first.
4. Distinguish direct person signals, Bryan's possibilities, and new agent suggestions.
5. If current availability, showtimes, menus, prices, or product stock matter, verify
   them from live sources before presenting them as current.
6. Update idea status only after Bryan reports or authorizes the outcome.

## Boundaries

- Capture is context, not a Reminder, shopping task, reservation, or purchase.
- Never contact the person, reveal the list, make a booking, or buy anything without
  explicit authorization.
- Keep the zone private in Bryan's vault.
- Keep the hub orienting and the person notes detailed; do not accumulate idea rows in
  the hub.
- Create a person note only after the first real signal. Empty pre-created profiles add
  noise.

## Verification Checklist

- [ ] The person, candidate, and signal were explicit.
- [ ] The statement was not merely a hypothetical example.
- [ ] The hub and existing person note were read first.
- [ ] No duplicate open idea was introduced.
- [ ] Exact names, context, uncertainty, and user-provided URL were preserved.
- [ ] The write was announced before editing and confirmed afterward.
- [ ] The exact vault changes were read back, committed, pushed, and remotely verified.
