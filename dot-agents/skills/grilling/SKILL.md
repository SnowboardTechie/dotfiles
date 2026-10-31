---
name: grilling
description: Stress-test a plan, decision, or design in one session by working its decision tree frontier-first. Use only when Bryan explicitly asks to grill, deliberate, pressure-test, or think something through before it is written down — or when `wayfinder` hands a decision ticket over. Researches facts itself, puts only decisions to Bryan, and stops before drafting.
disable-model-invocation: true
---

# Grilling

Interview Bryan until you reach a **shared understanding** of one effort that
fits in a single session. Model it as a **decision tree**: each settled decision
branches into the ones that hang off it.

> **Explicit invocation only.** Start this skill when Bryan asks for it by name
> or by intent ("grill me on this", "pressure-test this", "let's deliberate
> before I write it up"), or when `wayfinder` hands you a `grilling` decision
> ticket. Claude enforces this through `disable-model-invocation`; Hermes and
> OpenCode do not read that key, so this paragraph is the rule for them. Never
> enter a grilling loop because a conversation merely sounds like planning.

Provenance: adapted from Matt Pocock's `grilling`. Upstream pin, accepted and
rejected upstream rules, and the watched source list live in
[`dot-agents/upstreams/mattpocock-skills.json`](../../upstreams/mattpocock-skills.json).

## The frontier

The **frontier** is every decision whose prerequisites are already settled — the
questions answerable *now* without guessing at answers you have not heard yet.

Work in rounds:

1. Recompute the frontier.
2. Research every fact the frontier needs (see *Facts are your job*).
3. Ask the first frontier question. One.
4. Bryan's answers settle decisions, push the frontier outward, and unblock what
   depended on them. Return to 1.

A question whose answer depends on another question still open in this round
belongs to a *later* round. Putting it now invites an answer Bryan will have to
retract.

### One question per round

**Ask exactly one question per round. Always.** Bryan has said this every time
a session batched, and "they are independent" is not an exception he accepts.
A round is one `❓` block with its options and one recommendation, then stop
and wait for his answer.

Independence changes the *order* you ask in, never the count. Put the question
whose answer would reshape the most others first. Hold the rest, re-check their
facts if his answer changes them, and ask the next one on its own.

### Question format

```
❓ **Q1** — **<short title>**: <the question, with the genuine options and what
each one costs or buys>

➡️ **Recommendation:** <your pick, and the reason it wins over the runner-up>
```

Every consequential question carries genuine options, their trade-offs, and a
reasoned recommendation. "What do you want to do?" is not a question, it is an
abdication. A recommendation is not a decision — see *Epistemic status*.

- **Open each question with two or three sentences of context.** Name the
  project or map the ticket belongs to, what it is for in plain terms, and what
  is already settled around it. Bryan works many maps and plans in parallel and
  will not remember which ticket is which. Keep it short: context for this one
  question, not a briefing on every ticket in the session. A long multi-ticket
  overview reads as a wall of text.
- **Ask in the final message, not on a clarify card.** Bryan sees only final
  messages; text written before a tool call never reaches him, and a card
  that carries the explanation renders as an unreadable wall of text. Put the
  context, options, recommendation and the question in a readable final
  message and end the turn.
- **List every genuine option, including ones you recommend against.** Never
  silently drop an option because your recommendation makes it redundant. Show
  it, and say in one clause why it loses. Otherwise Bryan has to ask where it
  went.
- **When Bryan asks what a term or tool is** ("what is X?", "what does it cost
  to add Y now?"), answer that alone, with a reference link and verified costs.
  Then re-ask the same open question. The question is not settled until he
  picks.
- **A conditional question is an answer, not a request to re-ask.** "If we
  do X, can we also Y?" picks X and adds Y. Verify that Y is feasible, record
  X+Y as accepted, and move on to the next frontier question. Re-asking the
  same question with "X+Y" as a new option makes Bryan answer twice, and he
  reads it as you not listening. Re-ask only if Y turns out infeasible or
  changes X's trade-off, and say which fact forced it.

## Facts are your job

Finding *facts* is never Bryan's job. If a frontier question needs something
from the environment — a version, a config value, what an API actually returns,
what a repository already does — go get it. Read the file, run the command,
fetch the doc.

When planning a sibling template or implementation, inspect the existing
siblings' relevant source and documentation before asking each decision.
Present what they do as the baseline, then ask only about meaningful departures
or unresolved gaps. Never substitute an old map or summary for current source,
and never make Bryan repeatedly ask what the existing siblings already do.

Do not block the whole round on it. A running investigation is an unsettled
prerequisite, so only the questions downstream of it wait; ask the rest of the
frontier now.

Bryan answers **decisions**: what he wants, what he will accept, what the work
is for, which trade-off he prefers. Those are his and only his.

## Earlier records are not Bryan's decisions

Treat a decision record or plan written in an earlier session as **what was recorded**, never as something Bryan understood and agreed to. Agents wrote many of those notes, and some say "decided" about things he never saw explained. When a record bears on a question:

- describe what it says and what the running system actually does (verified);
- ask him whether it still holds.

Never use one to rule an option out, or to tell him he already agreed. When he says he didn't agree, reopen it and leave it open. (Bryan, 2026-10-30, on the pilot's model-on-host boundary.)

## Epistemic status

Every claim on the table carries one of four labels, and they are never
interchangeable:

| Status | Meaning |
|---|---|
| **Verified** | Checked against a source this session; name the source |
| **Inferred** | Reasoned from verified facts; state the inference |
| **Proposed** | Your recommendation; Bryan has not responded to it |
| **Accepted** | Bryan explicitly chose it |

Presenting a proposal as an accepted decision is the failure this table exists
to prevent. When you summarize, keep the labels attached.

## Reopening

When new evidence or a correction from Bryan invalidates the *basis* of an
earlier decision, reopen that decision and everything downstream of it. Say so
plainly: "Your correction on X removes the reason we chose Y — reopening Y."

Do not patch around a correction. If every new requirement forces another
exception, the governing model is wrong; surface that as its own decision rather
than accumulating workarounds.

## When knowledge belongs to someone else

Some frontier questions cannot be researched and are not Bryan's to answer —
they need one other person. Do not stall the tree on them and do not have Bryan
guess. Follow [`references/questionnaire.md`](references/questionnaire.md) to
turn the gap into a document Bryan can send. Drafting it is in scope; sending it
is not.

## Completion

The session is done when the frontier is empty: every branch visited, nothing
silently assumed.

**Stop there.** Present the settled tree — accepted decisions, rejected
alternatives and why they lost, verified facts, and anything still open — and
wait for Bryan to confirm shared understanding. Do not draft a plan, spec, ADR,
issue, or implementation until he does.

When `wayfinder` handed over the ticket, the answer that empties the frontier
is that confirmation: return to `wayfinder`, record the resolution, and present
the settled tree with the link to what was recorded. Stop and ask first only if
the tree carries something he did not settle — a decision he never answered, or
a discrepancy with what he said.

If the effort turns out to be too large for one session — the tree keeps growing
faster than you close it, or resolving one branch plainly needs its own research
or prototype effort — say so and offer `wayfinder`, which carries a map across
sessions. Do not silently start charting one.

## Related

- `wayfinder` — multi-session maps; hands `grilling` its decision tickets.
- `adr-and-spec-coach` — the existing planning method, retained during the pilot
  as the comparison control.
- `issue-plan` — turns a confirmed shared understanding into a durable plan.
- `voice-bryan` — human-facing wording for anything a person other than Bryan
  will read.
