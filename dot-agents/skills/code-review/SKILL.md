---
name: code-review
description: Use when reviewing an exact code candidate.
version: 2.0.0
author: Bryan Thompson + Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [review, standards, spec, risk, simplicity]
    related_skills: [pr-self-review, tdd, diagnosing-bugs]
---

# Code Review

## Overview

Review one immutable candidate through distinct dimensions without paying for a
separate model invocation per dimension. One review context reads the diff and
authorities once, then evaluates Standards, Spec, conditional Risk, and Ponytail
in order. It writes separate artifacts so each dimension remains visible.

`pr-self-review` owns finding validation, correction routing, and the bounded
loop. This skill owns review semantics.

Provenance: adapted from Matt Pocock's `code-review`. Upstream pin, accepted and
rejected rules, and watched files live in
[`dot-agents/upstreams/mattpocock-skills.json`](../../upstreams/mattpocock-skills.json).

## When to Use

Use for branch, PR, or pre-publication review after the candidate is stable.

Do not use an implementation worker's self-review as independent acceptance. If
the active parent wrote the candidate, run this contract in one independent
review context. If Claude wrote it and Sol only supervised, the Sol parent is the
independent acceptance context and should run it directly.

## 1. Freeze the candidate

Resolve and record:

- `base_sha`;
- `head_sha`;
- `merge_base_sha`;
- `diff_sha256` from `git diff --binary -M -C --find-copies-harder`;
- `expected_head_branch`; and
- an empty `git status --porcelain --untracked-files=all` result.

Use three-dot diff semantics. A symbolic ref is discovery input, not identity.
Reject an empty diff, detached branch, command failure, or dirty worktree before
review. Recompute the same identity immediately before writing artifacts.

## 2. Select dimensions deterministically

Standards and Spec always run. Use
`pr-self-review/scripts/select_review_lanes.py` with both authoritative inputs:

```sh
git diff --name-status -z -M -C --find-copies-harder \
  "$base_sha...$head_sha" -- > "$name_status_file"
git diff -M -C --find-copies-harder \
  "$base_sha...$head_sha" -- > "$unified_diff_file"
python3 dot-agents/skills/pr-self-review/scripts/select_review_lanes.py \
  --repo "$OWNER_REPO" \
  --name-status-from "$name_status_file" \
  --diff-from "$unified_diff_file" --json
```

Name-status owns path identity, including rename/copy sources and binary
deletions. The unified diff owns content signals. Malformed or missing input
fails closed. Risk runs for authentication, credentials, private data, untrusted
input, process execution, network, filesystem, persistence, migrations, queues,
retries, concurrency, deployment, publication, agent permissions, memory, or
cryptography. Risk always runs for CairnOS.

Correctness / Integration / Tests remains an optional caller-selected dimension
for a dedicated behavior trace. It is not automatically added to
`pr-self-review`.

## 3. Read authorities once

Read the complete diff, commit list, repository instructions, neighboring code,
and the approved ticket/plan/spec. Trace consumers for changed behavior. Read the
diff a second time for omissions and surprising scope.

Do not build broad related-issue or vault-topic caches during ordinary review.
Follow an explicitly linked issue, ADR, note, or spec when it is necessary to
validate intent; otherwise keep review on the candidate's governing authority.

## 4. Run one integrated review

Use one review context for the selected dimensions. Keep the reasoning sections
separate and execute Ponytail last. One reviewer writes:

- `review-standards.md`;
- `review-spec.md`;
- `review-risk.md` only when selected;
- `review-ponytail.md`; and
- a concise integrated finding list for disposition.

Each artifact records `base_sha`, `head_sha`, `merge_base_sha`, `diff_sha256`,
`expected_head_branch`, confidence, and reviewed paths. Findings use real
`file:line`, severity, observed behavior, consequence, and smallest correction.

Do not duplicate CI findings. Do not merge dimensions into a majority verdict.
Agreement raises the cost of a potential defect, not confidence in its cause.

### Standards

Report documented rule violations and concrete maintainability/test-quality
defects. Repository rules override generic heuristics. Skip formatting, import
order, and type/lint errors already enforced by tooling.

Use these smell prompts only when evidenced: mysterious name, duplicated code,
feature envy, data clump, primitive obsession, repeated switch, shotgun surgery,
divergent change, speculative generality, message chain, middle man, refused
bequest, excess test sensitivity, and an interface wider than its callers earn.

### Spec

Report requirements that are missing, partial, wrong, unrequested, outside the
approved scope, or contrary to an accepted decision. Quote the authority. An
empty Spec report is not proof that every acceptance criterion is met;
`pr-self-review` performs the independent sweep.

### Correctness / Integration / Tests (optional)

Trace callers, consumers, serialization/storage, errors, and tests. Report
integration drift, state/concurrency bugs, missing wiring, or tests that cannot
distinguish changed behavior from retained behavior. Do not duplicate another
dimension's finding.

### Risk (conditional)

Report concrete exploitable or operationally dangerous behavior. Name the actor,
path, and consequence. Do not emit generic hardening advice without a path in the
candidate.

### Ponytail (mandatory, last)

Review over-engineering only. Walk from largest deletion to smallest
simplification: `delete`, `yagni`, `stdlib`, `native`, then `shrink`. Show the
smaller replacement. Never invent deletions to look useful. If nothing should be
cut, write exactly `Lean already. Ship.` in the Summary.

Ponytail does not report correctness, security, spec conformance, coverage,
naming, formatting, or generic maintainability. Long, defensive, or unfamiliar
code is not automatically over-engineered.

## 5. Targeted Risk deepening

After the parent has dispositioned the integrated review and stabilized the
candidate, add one targeted Risk reviewer for security, persistence, migration,
protocol, concurrency, public-contract, or deployment changes. Give it only the
exact candidate, governing authority, and implicated boundary.

This targeted reviewer is an exception, not a second generic review. If it finds
a valid blocker and the candidate changes, its artifact is stale; rerun one
targeted Risk reviewer against the corrected identity. Do not restart the whole
multi-dimension workflow in several model contexts.

## 6. Severity and output

- Critical: production breakage, data exposure/corruption, or direct user harm.
- Major: real blocking defect or meaningful operational risk.
- Minor: non-blocking quality issue worth addressing.
- Nit: optional wording, naming, or local simplification.

### Finding gate

Zero findings is a valid successful review. Report only concrete defects: the
candidate violates an authority or causes an observable failure or risk, the
consequence matters, and the proposed correction materially improves the
candidate. Do not turn an acknowledged limitation, accepted trade-off,
imprecise-but-accurate wording, or improvement opportunity into a finding merely
to produce a comment.

When the acceptance owner challenges a finding, stop drafting alternative
wording and revalidate it from the exact claim and evidence. If it survives,
defend it with the evidence and consequence. If it does not, withdraw it
immediately. Never preserve the original conclusion by changing qualifiers or
offering a semantically equivalent rewrite.

An empty dimension must state what was checked and its confidence. Reviewer
output is advice. The acceptance owner validates observations, explanations, and
prescriptions before correction.

## Common Pitfalls

1. Spending one model invocation per dimension.
2. Reviewing before the parent has stabilized the candidate.
3. Treating conventional green tests as adversarial boundary coverage.
4. Treating reviewer convergence as independent proof.
5. Letting Ponytail smuggle in correctness or security findings.
6. Re-running every dimension when only a final targeted Risk boundary remains.

## Verification Checklist

- [ ] Exact candidate and clean branch frozen
- [ ] Standards and Spec selected; Risk classifier recorded
- [ ] One review context read the diff and authorities once
- [ ] Separate artifacts preserve dimension visibility
- [ ] Ponytail ran last and stayed narrow
- [ ] Acceptance criteria were swept independently
- [ ] Targeted Risk reviewer used only for a qualifying boundary
- [ ] Every reported finding passed the concrete-defect gate
- [ ] Every challenged finding was defended with evidence or withdrawn
- [ ] Every blocking finding was independently validated
- [ ] Artifacts still match the candidate at disposition