---
name: teammate-pr-review
description: Use when reviewing someone else's pull request (a teammate's or another author's PR, on GitHub or Forgejo), including re-reviews, a simplicity review (the Ponytail pass) of one, drafting review comments, and choosing the review event. For a PR or branch Bryan authored, use pr-self-review instead.
version: 1.0.0
author: Bryan Thompson
license: MIT
metadata:
  hermes:
    tags: [review, pull-request, teammate]
    related_skills: [code-review, pr-self-review, voice-bryan]
---

# Teammate PR Review

## Overview

Review another author's PR in four passes, then draft the review Bryan's way.
Matt Pocock's `code-review` skill supplies only the Standards and Spec passes.
This skill adds the conditional Risk pass and the mandatory Ponytail pass from
`pr-self-review`'s review contract, then owns how the review is drafted and
posted.

This skill does not correct the candidate. The author owns the fix; Bryan owns
whether and when the review is submitted.

## 1. Freeze the PR head

Resolve the PR, its base branch, and its exact head SHA. Check the head out in
a Worktrunk-managed worktree (`worktrunk`), not by switching the primary
checkout. Record `base_sha`, `head_sha`, `merge_base_sha`, `diff_sha256`, and
`expected_head_branch` as section 1 of
[`../pr-self-review/references/review-contract.md`](../pr-self-review/references/review-contract.md)
describes. Every link and inline anchor in the draft is pinned to that head.

## 2. Standards and Spec: Matt Pocock's `code-review`

Load `code-review` (Matt Pocock's skill) and run it with `merge_base_sha` as the
fixed point. Give it the PR's linked issue or spec as the spec source by path or
fetched text, so it needs no tracker lookup. Keep its two reports as it
produces them, under `## Standards` and `## Spec`.

His skill covers Standards and Spec and nothing else. It has no Risk pass, no
over-engineering pass, and no rules for drafting or posting a review.

## 3. Risk and Ponytail, the simplicity review: `pr-self-review`'s review contract

Ponytail checks the PR for over-engineering only: what could be deleted or made
smaller. It is named after the Ponytail plugin, recorded in
[`dot-agents/upstreams/ponytail.json`](../../upstreams/ponytail.json), and
"simplicity review" is another name for it. A request for only a simplicity
review runs the Ponytail section alone, then drafts as below.

Read
[`../pr-self-review/references/review-contract.md`](../pr-self-review/references/review-contract.md).
Run its lane selector (section 2) to decide Risk. When Risk is selected, run the
Risk section against the frozen head. Then run the Ponytail section, always,
and last, after both of his reports have settled. Use its severity scale for
every finding, and its finding gate (repeated below) for every finding from all
four passes.

Do not merge or rerank findings across passes.

## Human-facing review draft

Include a clickable PR link and a source permalink for every file/line finding,
pinned to the reviewed head. Verify the path and line or range against that
candidate. Keep exact inline posting metadata alongside the link so the reader
can both inspect the code and place the comment.

Choose the proposed review event from the evidence: `APPROVE` for a completed
review with no validated blockers; `REQUEST_CHANGES` for validated blocking
findings; `COMMENT` for unresolved discussion or incomplete review coverage.
Optional suggestions do not require withholding approval. When a blocker's fix
already exists outside the candidate, as prerequisite PRs that are open now,
the author has nothing to change: propose a conditional `APPROVE`, not
`REQUEST_CHANGES`, and re-choose the event whenever the fix moves. Never
promise future work in a review ("I'll put up a PR"): either make the fix now,
before the review is posted, or make it the author's ask, which rules out
`APPROVE`.
When an open choice would change the candidate itself (an overlapping PR
carries a newer copy of the same work, or the merge order decides what this
head contains), the head is not what will merge. Propose `COMMENT` that asks
the question and recommends the order when the evidence points to one. Do not
approve it, and do not request changes just to hold a question.
On a re-review where the author settled every earlier ask and no new finding
passes the gate, propose `APPROVE` with an empty body: the approval closes the
loop, and a line that recaps the fixes adds nothing (PR 1299, 2026-10-14).
Preparing a draft
and submitting that review are separate actions; preserve the user's submission
authorization boundary.

Make actionable inline corrections concrete with a small suggestion block when
the replacement is known and verified. Keep its selected range exact. An
inline's anchor, ask, and evidence cover the same lines: when the concrete
defect is one assertion, ask for that assertion, not the test or file around
it. A Ponytail whole-file deletion stays in the private audit unless its
evidence covers the whole file. Separate
publishable review text from private reviewer provenance and test logs. Inspect
the saved artifact so links, anchors, and complete code fences remain usable.

Write the overall review body in Bryan's voice, leading with the judgment.
Keep routine test counts, execution details, and repeated change or inline-
comment summaries in the private audit. Include technical detail in the
publishable body only when it affects the review decision. Planning or tracker
gaps that do not decide this PR's merge (an unfiled upstream issue, a ticket's
stale assumption) stay in the private audit. Any condition on
the event belongs in the body, never only in an inline: list the PRs that must
merge first as linked, numbered items in merge order. Inlines carry the code
defect and point back to that list.

Self-review the publishable text against `voice-bryan` before presenting it:
body length, no restating the author's own claims back, no opener reused from
the same author's other reviews that day. The chat handoff opens with the
drafts themselves, with no narrative or commentary ahead of them: a `Proposed
event:` line, the review body as a rendered `>` blockquote, then every inline
(optional or not-recommended ones included) as its exact-head permalink, side,
and line range, followed by its full text as a blockquote with any suggestion
code nested inside the quote. Never put chat drafts in fenced blocks: the
terminal shows them as raw markdown. Raw copy-paste text lives in the saved
draft. The saved-draft link comes after. Every later turn that changes or
discusses the drafts repeats the whole current set the same way, never only
the changed part. Never summarize an inline or point to the note instead of
showing it: if the user has to ask to see the drafts, the handoff failed.
Considered-not-posted items, evidence, and explanations stay in the saved
draft.

## Finding gate

Zero findings is a valid successful review. Report only concrete defects: the
candidate violates an authority or causes an observable failure or risk, the
consequence matters, and the proposed correction materially improves the
candidate. Do not turn an acknowledged limitation, accepted trade-off,
imprecise-but-accurate wording, or improvement opportunity into a finding merely
to produce a comment. Drop an inline whose fix already arrives through a
decision the body asks for (the newer copy on an overlapping PR, a suggestion
already pending there).

For test-quality comments, a surviving mutation establishes a coverage gap,
not a current implementation defect. Check legitimate inputs and the stated
assertion or requirement, then explain the meaningful consequence. Distinguish
a mis-scoped existing assertion from a request for extra assertions; withdraw
marginal coverage requests that fail the finding gate. Do not imply that an
artificially broken variant is the current code or that a future regression
will occur if the suggestion is left unaddressed.

When the acceptance owner challenges a finding, stop drafting alternative
wording and revalidate it from the exact claim and evidence. If it survives,
defend it with the evidence and consequence. If it does not, withdraw it
immediately. Never preserve the original conclusion by changing qualifiers or
offering a semantically equivalent rewrite.

An empty dimension must state what was checked and its confidence. Reviewer
output is advice. The acceptance owner validates observations, explanations, and
prescriptions before correction.

## Verification Checklist

- [ ] PR head frozen and every link pinned to it
- [ ] Standards and Spec came from Matt Pocock's `code-review`
- [ ] Risk classifier recorded; Risk ran when selected
- [ ] Ponytail ran last and stayed narrow
- [ ] Every reported finding passed the finding gate
- [ ] Human-facing draft has clickable PR and exact-head file/line links
- [ ] Proposed event matches blocker status and review coverage
- [ ] Suggestions have verified replacements and valid inline ranges
- [ ] Nothing was submitted without Bryan's authorization
