---
name: gift-and-experience-capture
description: >
  Use whenever Bryan attributes a gift idea, preference, movie or show, restaurant,
  outing, activity, or date idea to a named person in any chat, especially phrases
  such as “Traci wants to see…”, “Dad would love…”, “save this for Mom”, or “we
  should go here”; also use when planning or shopping for gifts, dates, or shared
  experiences. Captures clear signals into person-specific notes in Bryan's Apple
  Notes second brain (through apple-notes-pkm) and resurfaces them later without
  turning every mention into a task.
version: 1.0.0
author: Hermes Agent
metadata:
  created_by: agent
  hermes:
    tags: [gifts, dates, relationships, preferences, capture, pkm]
    related_skills: [apple-notes-pkm]
---

# Gift and Experience Capture

## Purpose

Turn casual, attributable preference signals into useful future context. Bryan should
be able to mention an idea naturally in Matrix or another Hermes surface and trust
that it will be available when planning a date, choosing an experience, or shopping
for a gift.

The canonical system is a small compiled knowledge zone at the root of the Apple
Notes folder `Second Brain`:

- Hub: the note `Gift and Experience Ideas`
- One detail note per person: `{Person} Gift and Experience Ideas`
- Event-specific plans remain separate and name the relevant person note by title.

Load `apple-notes-pkm` and use only its helper (`search`, `read`, `create`,
`append`) for this zone. Apple Notes, not Hermes memory or chat history, is
canonical. `/Users/bryan/second-brain` is a frozen archive: never read or write it.

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

Before the write, name the exact person-note title in one short sentence, then make
the capture. Do not ask for confirmation after a clear signal. Afterward,
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

1. `search --mode title` for the hub and the person note; `read` them by id and check
   for a duplicate idea.
2. If no person note exists, announce the proposed title, `create` it in the root
   folder (`--folder ""`) from the shape below, and `append` its title under the hub's
   `People` section. Do not create a new folder or MOC for each person.
3. `append` one bullet under `Open Ideas` (a bullet, not a table row: appended
   Markdown cannot join an existing native table; the imported tables stay as history)
   with:
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
6. Pass the fresh `revision` from the read; the helper verifies the append by readback.
   Nothing is committed or pushed — iCloud syncs the note.
7. Reply with a compact confirmation, not a planning discussion.

Bullet shape: `- YYYY-MM-DD · kind · idea — signal / context (source or —)`. Keep one
idea per bullet.

## Person Note Shape

Use this shape for the first capture involving a person:

```markdown
Part of Gift and Experience Ideas.

## Preferences & Signals

_Durable, source-supported preferences that improve future choices._

## Open Ideas

- (one bullet per idea: `YYYY-MM-DD · kind · idea — signal / context (source)`)

## Used or Retired

- (one bullet per outcome: `YYYY-MM-DD · idea — outcome`)

## Related

Aliases: {Person} Gift Ideas, {Person} Date Ideas
Created: YYYY-MM-DD
Status: active
Tags: area/relationships, gifts, experiences, type/reference
```

The helper writes the title (`{Person} Gift and Experience Ideas`) as the note's
first line; do not repeat it in the body.

For people other than Bryan's partner, omit the `{Person} Date Ideas` alias when it
would be misleading. A preference belongs under `Preferences & Signals` only when it
is durable and directly supported; ordinary one-off candidates remain in the open
ideas list.

## Lifecycle Updates

When Bryan later says an idea was bought, booked, visited, watched, rejected, or is no
longer relevant:

1. Find the exact open bullet (or imported table row).
2. `append` the outcome under `Used or Retired` with the update date; an appended
   note cannot remove the original bullet, so mark it as retired in the appended
   line rather than rewriting the note (`replace` is refused when attachments exist
   and is never used to prune Bryan's history).
3. Preserve why it was originally considered when that context remains useful.

Do not silently delete history. Do not infer completion from calendar events, receipts,
or elapsed time unless Bryan asks for reconciliation and the evidence is explicit.

## Retrieval and Planning

When Bryan asks for gift, birthday, holiday, anniversary, restaurant, date, movie,
show, or outing ideas:

1. Start at the hub note `Gift and Experience Ideas` (title search, then read by id).
2. Read the relevant person note and any event-specific plans it names.
3. Surface relevant open ideas first.
4. Distinguish direct person signals, Bryan's possibilities, and new agent suggestions.
5. If current availability, showtimes, menus, prices, or product stock matter, verify
   them from live sources before presenting them as current.
6. Update idea status only after Bryan reports or authorizes the outcome.

## Boundaries

- Capture is context, not a Reminder, shopping task, reservation, or purchase.
- Never contact the person, reveal the list, make a booking, or buy anything without
  explicit authorization.
- Keep the zone private in Bryan's Apple Notes.
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
- [ ] The helper's readback verification passed and the note id was reported.
