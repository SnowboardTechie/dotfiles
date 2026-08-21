# Questionnaire branch

A frontier question that only one other person can answer is neither a fact you
can research nor a decision Bryan can make. Turn it into a **questionnaire**: a
Markdown document Bryan hands to that person, async or in a meeting.

This is a disclosed procedure owned by `grilling`, not a separate skill. It is
adapted from Matt Pocock's `to-questionnaire`; see
[`dot-agents/upstreams/mattpocock-skills.json`](../../../upstreams/mattpocock-skills.json).

## Trigger

All three must hold:

1. A frontier question is blocking the tree.
2. It cannot be answered from the environment, the repository, or documentation.
3. The knowledge belongs to **one identifiable person** other than Bryan.

Knowledge spread across a team is not this. Narrow it to one recipient or leave
it as fog for `wayfinder`.

## Grill the send, not the subject

Interview Bryan only about the **send** — the part he can always answer. He does
not know the subject; that is the entire reason the questionnaire exists.

1. **Who is it going to?** One exchange: the recipient's role, expertise, and
   relationship to Bryan. This fixes the tone and how much context the document
   must carry. Done when you know who they are and what they know that Bryan
   does not.
2. **What must come back?** One exchange: the specific decisions or facts Bryan
   cannot resolve alone. Done when you have a concrete list of what he must walk
   away able to decide.

Then map **every** item from step 2 to at least one question the recipient can
actually answer from their own knowledge. An item with no question is a gap; a
question serving no item is padding.

## Wording

Use `voice-bryan` for everything the recipient reads. This document goes out
under Bryan's name, so it must sound like him rather than like an agent.

## Where it goes

Ask Bryan for the path before writing, and offer both shapes:

- **Temporary** — under the effort's state directory, when the questionnaire is
  scaffolding that dies with the decision.
- **Vault-native** — inside the relevant project vault or `~/second-brain`, when
  the answers are durable knowledge. Follow that vault's conventions and its
  `AGENTS.md`.

Never pick silently, and never write into the installed skill directory.

## Never send it

Drafting is in scope. Sending, posting, emailing, filing as an issue, or sharing
it anywhere is **not** — that is Bryan's action, taken after he has read the
exact text. Report the path and stop.

## Document structure

```markdown
# <Questionnaire title>

**Purpose:** why this exists and the decision riding on it.

**From:** Bryan · **To:** <recipient> · **How your answers will be used:** <where they go>

## Context

One paragraph orienting someone who was not in the room. Enough to answer well,
not a page.

## How to answer

Deadline and rough effort. Partial answers and "I don't know" are useful — flag
anything uncertain rather than skipping it.

## <Theme>

One `##` section per theme, most-important-first, because async may get you only
one pass. Each question is a single idea, never compound, with an answer stub
directly beneath it, and a one-line *why this matters* only where the question
could be misread or invite a throwaway answer.

### What load is the system expected to handle at launch?

_Why this matters: it decides whether we provision for burst traffic now or defer it._

>

## Anything else?

Anything we didn't ask that we should know?
```
