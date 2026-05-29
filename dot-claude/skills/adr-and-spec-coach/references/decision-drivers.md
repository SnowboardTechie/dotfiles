# Surfacing and Ranking Decisions

Phase 2's job: drive out **every** decision the artifact must settle, then
rank them by weight so Phase 3 can descend the list heaviest-first. This file
is the prompt set for doing that with an author who may not know what to look
for.

## Step 1 — Surface the decisions

Ask "what has to be true for this to ship?" and watch for choices hiding
inside the answer. Prompts that flush them out:

- **Data:** What gets stored, where, in what shape? What's the identifier?
  What's the source of truth?
- **Interface / contract:** What's the API surface, the schema, the wire
  shape? What do consumers depend on?
- **Lifecycle:** How is it created, updated, expired, revoked, deleted? What
  happens on failure partway through?
- **Boundaries:** What's in scope vs. explicitly out? What's someone else's
  responsibility?
- **Integration:** What does this talk to? What does it assume about those
  systems (and is that assumption verified or just hoped)?
- **Operational:** How does it deploy, roll back, get observed? What's the
  blast radius if it's wrong?

Each distinct choice with more than one defensible answer is a decision for
the agenda.

## Step 2 — Rank by weight

> **Weight = how hard to reverse × how many defensible answers.**

| | Cheap to reverse | Expensive to reverse |
|---|---|---|
| **One obvious answer** | trivial — apply default, name it, move on | low — note the default, confirm it |
| **Several defensible answers** | medium — quick deliberation | **load-bearing — full deliberation** |

Load-bearing decisions are the ones that are *both* hard to undo *and*
genuinely contested. They go first. They are also where the author most needs
to make the call themselves — an expensive-to-reverse choice they didn't own
is a choice they can't defend later.

**What makes a decision expensive to reverse:**
- It changes a wire shape / schema consumers ship against.
- It alters a public or typed surface.
- It bakes into stored data that would need migration to change.
- It sets a precedent other work will copy before you can revisit it.

**What makes it cheap to reverse:**
- It's behind a flag or a single config value.
- It's an internal implementation detail with no external contract.
- It's scoped to one feature and easily swapped.

## Step 3 — Show the agenda

Render the ranked list back to the author before descending it (see the
SKILL.md Phase 2 example). The visible agenda does two jobs: it tells the
author what's coming, and it teaches them — by example — how to triage their
*next* spec without you.

## Common mistakes

- **Treating all decisions as equal** → you drown the author in trivia and
  bury the two choices that actually matter. Rank ruthlessly.
- **Skipping the trivial ones entirely** → triage sets order and depth, not
  what's covered. State the default and let them rubber-stamp; don't silently
  decide.
- **Ranking by how interesting the decision is** → rank by reversibility and
  contestedness, not by what's fun to discuss.
