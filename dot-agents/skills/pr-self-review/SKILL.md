---
name: pr-self-review
description: Use for bounded review of an authored candidate.
version: 2.0.0
author: Bryan Thompson + Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [review, pull-request, acceptance, bounded-correction]
    related_skills: [code-review, issue-work, worktrunk]
---

# PR Self-Review

## Overview

Review an authored branch or pre-PR candidate once in an independent acceptance
context, correct validated blockers in one bundled pass, and stop after one
conditional second correction. The workflow preserves Standards, Spec,
conditional Risk, Ponytail, acceptance criteria, exact-candidate identity, and
final verification without multiplying those checks across several reviewers.

## Entry Modes

- `pre-pr`: `issue-work` supplies state directory, worktree, ticket/plan, branch,
  base, implementation route, candidate identity, and the global
  `correction_passes_consumed` value (`0`, `1`, or `2`).
- `pr-url`: resolve an authored GitHub or Forgejo PR, then use a controlled
  `worktrunk` worktree.
- `branch-inference`: resolve the open authored PR from the current branch.

For someone else's PR use `code-review`, not this correction workflow.

Standalone state lives at:

```text
{TRUNK_ROOT}/.hermes/pr-self-review/{owner}-{repo}-{pr-or-branch}/
```

`pre-pr` reuses the caller's existing ticket-root
`.hermes/issue-work/{owner}-{repo}-{N}/` directory. Never create a second review
state root in the implementation repository for cross-repository work.

## 1. Establish independent acceptance

Independence is about authorship, not process count:

- When a Claude/Hermes/Qwen worker wrote the candidate and Sol did not edit it,
  the Sol parent is the independent acceptance context and runs one integrated
  review directly.
- When the active parent wrote or changed candidate code, dispatch one fresh
  independent review context after the candidate is frozen. Use the host's
  normal independent delegation surface; do not require Claude or Herdr.
- A worker's self-review never satisfies acceptance.

If no context independent of the candidate author is available, stop before
publication. Do not manufacture independence by launching another session of
the same implementation worker.

In `pre-pr`, validate the caller's ticket/implementation repository identities
with `issue-work/scripts/validate_cross_repo_context.py`. Require the supplied
worktree, state root, branch, ticket URL/host/repository, and implementation
host/repository to match its fresh parsed JSON. Private ticket identity must not
flow into a public artifact.

When an independent delegate is required for a cross-repository candidate, pass
the exact `ticket_trunk_root`, `state_dir`, `context_validation_path`, ticket
URL/host/repository, implementation host/repository, and canonical absolute
`context_validator_path` from the loaded `issue-work` skill alongside the
ordinary candidate inputs. The delegate invokes that absolute validator before
admitting a plan or output path beneath that exact validated ticket state
directory; it never resolves the helper from the implementation checkout.

Complete when one acceptance owner is independent of the candidate author and
all repository roles are verified.

## 2. Freeze one exact candidate

Require a named non-default branch and a clean worktree, including untracked
files:

```sh
git status --porcelain --untracked-files=all
```

A nonignored untracked file is invisible to `{base}...HEAD`; refuse it in both
`pre-pr` and standalone modes. Ignored paths are outside the candidate.

Resolve:

```sh
set -euo pipefail
base_sha=$(git rev-parse "$BASE^{commit}")
head_sha=$(git rev-parse HEAD)
merge_base_sha=$(git merge-base "$base_sha" "$head_sha")
expected_head_branch=$(git branch --show-current)
if command -v shasum >/dev/null 2>&1; then
  diff_sha256=$(git diff --binary -M -C --find-copies-harder \
    "$base_sha...$head_sha" -- | shasum -a 256 | cut -d' ' -f1)
else
  diff_sha256=$(git diff --binary -M -C --find-copies-harder \
    "$base_sha...$head_sha" -- | sha256sum | cut -d' ' -f1)
fi
```

Record `base_sha`, `head_sha`, `merge_base_sha`, `diff_sha256`, and
`expected_head_branch`. Before every review and disposition boundary, recompute
them and require the branch and worktree to remain unchanged. A candidate change
invalidates prior review artifacts; the next rereview writes replacements for
the new identity.

Complete when the exact candidate is reproducible from direct Git state.

## 3. Build the acceptance-criteria artifact

Create `{state-dir}/intent-checklist.json` once per candidate. Gather explicit
obligations from every available authority:

- approved `plan_path` acceptance/success/done section;
- source issue task lists and prose sections headed `acceptance criteria`,
  `definition of done`, or `done when`;
- governing spec requirements;
- PR body criteria explicitly presented as criteria.

An issue with no task list is not an issue with no acceptance criteria. When a
forge body is fetched, extract criteria while the full body is in hand; do not
mine a truncated excerpt. Normalize one independently checkable statement per
entry, split every compound criterion, deduplicate equivalent statements, and
retain all source locators.

Use this shape:

```json
{
  "candidate_identity": {
    "base_sha": "...",
    "head_sha": "...",
    "merge_base_sha": "...",
    "diff_sha256": "..."
  },
  "sources": [
    {"kind": "plan", "ref": "...", "available": true, "criteria": 4}
  ],
  "criteria": [
    {
      "id": "AC-1",
      "statement": "...",
      "sources": [{"kind": "plan", "locator": "Acceptance, item 1"}],
      "verdict": "met | unmet | out-of-scope | unswept",
      "evidence": "path:line and test"
    }
  ]
}
```

An unreadable authority is `available: false` and its obligations are unswept,
not absent. Those are different facts, and unswept authority blocks readiness.
Both the acceptance sweep and `summary.md` read this artifact rather than
rebuilding criteria from memory.

Judge each criterion against code, tests, and live artifacts:

- `met`: cite concrete implementation and verification;
- `unmet`: raise a normal blocking finding;
- `out-of-scope`: name the separately owning tracked work and why this candidate
  remains complete;
- `unswept`: block publication.

Complete when every criterion has a candidate-bound verdict and evidence.

## 4. Run one integrated review

Load `code-review`. Use its `scripts/select_review_lanes.py` classifier, then run
one integrated review in this order:

```sh
git diff --name-status -z -M -C --find-copies-harder \
  "$base_sha...$head_sha" -- > "$name_status_file"
git diff -M -C --find-copies-harder \
  "$base_sha...$head_sha" -- > "$unified_diff_file"
```

1. Standards;
2. Spec;
3. Risk when selected; and
4. mandatory Ponytail last.

One review context reads the diff and authorities once and writes
`review-standards.md`, `review-spec.md`, optional `review-risk.md`, and
`review-ponytail.md`. Keep dimension artifacts separate even though execution is
integrated. Each artifact records the full candidate identity and expected
branch.

Do not build broad related-issue or vault-topic caches. Read only explicitly
linked context needed to establish intent or ownership.

For security, persistence, migration, protocol, concurrency, public-contract, or
deployment changes, defer one targeted Risk reviewer until the integrated review
and ordinary correction have stabilized the candidate. It receives the exact
candidate and implicated boundary only. It is not another generic pass.

Complete when all selected artifacts and the checklist match the exact candidate.

## 5. Validate and disposition findings

Reviewer output is advice. The acceptance owner validates each observation,
explanation, and prescription against code, tests, reproductions, and intent.
Several dimensions reading the same files are correlated evidence, not votes.

Use these dispositions:

- `fix`: valid, in scope, and preserves documented intent;
- `reject`: false, speculative, already handled, or worse than the code;
- `defer`: valid, non-blocking, and demonstrably owned by separate tracked work;
- `escalate`: blocking and every reasonable correction materially contradicts
  approved product, architecture, public-contract, or security intent.

Routine findings do not go back to Bryan for individual disposition. Batch all
validated fixes. Ask only for a material intent conflict, with one recommendation
and the exact authority it would change.

Run the acceptance-criteria sweep independently of reviewer findings. An omitted
feature may have no diff line for Spec to flag.

Complete when every unsuppressed finding and criterion has an evidence-backed
disposition.

## 6. Correct within a one-plus-one bound

There is one normal correction and one conditional second correction. There is
never a third correction. In `pre-pr`, initialize the counter from
`correction_passes_consumed`; it is the global issue-work counter and this skill
must not reset it. Standalone modes initialize it to `0`.

### Normal correction

This correction is available only when the counter is `0`. Batch every validated
in-scope blocker into one self-contained correction contract, increment the
counter to `1` before submitting accepted input, and preserve the increment if
the turn fails after submission. On a delegated implementation route, return it
to the original worker:

- visible Claude/Hermes uses the existing `worker-identity.json` with
  `coding-agent-handoff-supervision/scripts/herdr_worker.py prompt`;
- Qwen uses its original session ID;
- a native parent correction follows normal host editing only when that parent
  remains the authorized editor.

The correcting worker does not publish. The parent inspects the real diff, runs
affected targeted checks, commits only accepted paths when authorized, freezes
the new candidate, and performs one complete integrated rereview.

### Conditional second correction

Permit one conditional second correction only when the counter is `1` and every
remaining blocker is a bounded implementation defect that preserves goal, scope,
architecture, public contract, and security model. Increment the counter to `2`
before submitting accepted input. This covers a defect introduced, exposed, or
left incomplete by the normal correction, including a normal correction already
consumed by issue-work Phase 3.

Do not use it for a plan defect, open architecture, scope expansion, unavailable
proof, repeated systemic failure, or a new product decision. Stop and report
those instead.

At counter `2`, no correction is available. After the conditional correction,
freeze the resulting candidate and run one complete integrated rereview. Apply
no further correction. Any validated blocker sets the result to
`Correction bound reached — do not merge.`

Provider capacity is an independent hard gate. Before every Claude correction,
the Herdr helper must verify capacity and acquire that worker runtime session's
turn lease. Unrelated Claude sessions are not a concurrency blocker. Exhausted
or unverifiable capacity consumes no correction and never permits an automatic
provider switch.

Complete when a rereview is clean or the deterministic bound has stopped work.

## 7. Run final verification once

During corrections run focused tests only. After the candidate is stable and all
reviews are clean, run the full repository test, lint, typecheck, build, and
required runtime probes once in a context independent of the code author.

A failed final gate blocks readiness. Fixing it consumes the remaining correction
allowance and requires candidate freeze plus integrated rereview; if no allowance
remains, report the bound rather than extending it.

Complete when exact-candidate verification is green and recorded.

## 8. Write summary and exit

Write `{state-dir}/summary.md` with:

```markdown
---
status: reviewed
ticket: {ticket-or-pr}
candidate: {head_sha}
expected_head_branch: {expected_head_branch}
base_sha: {base_sha}
merge_base_sha: {merge_base_sha}
diff_sha256: {diff_sha256}
review_context: {sol-parent | independent-delegate}
dimensions: [standards, spec, risk?]
quality_gates: [ponytail]
review_invocations: {N}
correction_passes: {0|1|2}
---

## Headline
## Critical and Major Findings
## Minor and Nit
## Lane Selection
## Ponytail
## Acceptance Criteria
## Corrections
## Verification
## Ship Readiness
```

Read acceptance results from `intent-checklist.json`. Read finding counts from
the current review artifacts. Ship Readiness is one of:

- `Ready to publish`;
- `Outstanding blocking intent conflict — do not merge`;
- `Correction bound reached — do not merge`;
- `Review artifact missing or stale — do not merge`;
- `Acceptance authority unswept — do not merge`; or
- `Verification failed — do not merge: {key output}`.

In standalone PR mode, update the existing branch only when already authorized
and read it back. In `pre-pr`, return to `issue-work` for publication. Do not
merge.

## Common Pitfalls

1. Launching a fresh Claude reviewer after Sol already independently reviewed
   Claude's candidate.
2. Paying for one reviewer per dimension instead of one integrated context.
3. Running final full CI after every correction instead of once when stable.
4. Rebuilding acceptance criteria from a body excerpt or memory.
5. Treating green conventional tests as proof of adversarial boundary behavior.
6. Using the conditional correction for plan or architecture churn.
7. Applying a third correction instead of reporting the bound.

## Verification Checklist

- [ ] Review context is independent of the candidate author
- [ ] Ticket/worktree/repository identities verified
- [ ] Named branch and clean tracked/untracked state verified
- [ ] Exact candidate recorded and rechecked at each boundary
- [ ] `intent-checklist.json` includes every available authority
- [ ] Standards, Spec, conditional Risk, and Ponytail ran in one context
- [ ] Targeted Risk reviewer used only for a qualifying stable boundary
- [ ] Every finding was validated and dispositioned
- [ ] Corrections did not exceed one normal plus one conditional pass
- [ ] Final full verification ran once against the stable candidate
- [ ] Current artifacts and summary match the exact candidate
- [ ] Ship Readiness reflects blockers honestly