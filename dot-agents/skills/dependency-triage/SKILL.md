---
name: dependency-triage
description: Triage open dependency PRs in the SGG / CommonGrants monorepo by blast radius, CI state, and merge order
---

# Dependency Triage

Review open dependency pull requests, sort them into the right review order, dispatch a parallel read-only review of every PR worth reviewing, and recommend which to merge, review manually, hold, or close.

This skill is intentionally specific to low-overhead weekly dependency maintenance in the SGG / CommonGrants monorepo, with its Dependabot groups, catalog lane, published packages, and CI layout. Do not generalize its package or changeset rules to unrelated repositories.

---

## Quick Reference

```
dependency-triage
```

---

## When to Use

Use this skill when:

- Several dependency PRs are open and you need a sane merge order
- CI is red on some PRs and you need to decide what is worth fixing
- You want a weekly review pass instead of ad hoc dependency babysitting

Do not use this skill to deeply debug one PR. Use `dependency-review` for that.

### SGG scope prerequisite

From the `~/code/sgg/` umbrella, triage only the dependency queues Bryan maintains:

- `HHS/simpler-grants-protocol`
- `common-grants/py-cg-grants-gov`
- `common-grants/ts-cg-grants-gov`

Exclude `HHS/simpler-grants-gov`; its Renovate queue is outside this maintenance workflow. Before gathering PRs, resolve which of the three maintained repositories is in scope. If the invocation is from the umbrella and does not identify one, use the runtime's structured clarification mechanism (Hermes: `clarify`) rather than silently scanning all repositories.

---

## Step 1: Gather the Queue

Collect the open dependency PRs and their current check state.

At minimum, inspect:

- PR number
- title
- branch name
- labels
- author
- URL
- status checks

Prefer forge-native tools:

### GitHub

```bash
gh pr list --label dependencies --state open --limit 30 \
  --json number,title,headRefName,author,labels,url,statusCheckRollup
```

### Forgejo

```bash
tea api "/repos/{owner}/{repo}/pulls?state=open" \
  | jq '[.[] | select(any(.labels[]?; .name == "dependencies"))]'
```

If the repo uses Dependabot labels beyond `dependencies` (for example `python`), include them in your summary.

---

## Step 2: Classify Each PR

Put every PR into one of these lanes:

### A. Green and isolated

Examples:

- isolated Python SDK dependency PRs
- narrow website-framework PRs
- small tooling-only PRs

These are the best merge candidates.

### B. Red but attributable

Examples:

- one PR, one group, one obvious failing surface
- website framework PR only failing website checks
- tooling PR only failing lint/build checks

These are worth manual review next.

### C. Red and broad

Examples:

- one grouped PR failing checks across multiple packages
- workflow PRs destabilizing many unrelated jobs
- lockfile-heavy workspace PRs with unclear root cause

These should usually be held, narrowed, or superseded instead of debugged immediately.

### D. Special-handling lanes

Always call out separately:

- GitHub Actions PRs
- catalog workflow PRs
- major version bumps
- PRs that may require a changeset because they touch runtime deps in published packages

---

## Step 2b: Detect Superseded PRs

Before ordering the queue, check whether any PR's changes are a subset of another's.

```bash
# Compare changed files between two PRs in the same lane
gh pr view {A} --json files --jq '[.files[].path] | sort'
gh pr view {B} --json files --jq '[.files[].path] | sort'
```

A PR is likely superseded when:

- Its changed files are a strict subset of another PR's changed files
- Both target the same dependency at the same version
- The broader PR includes companion upgrades the narrower one lacks (e.g., a Starlight-only PR superseded by a full Astro v6 migration)

Mark superseded PRs for closure in the report. Do not close them until the superseding PR actually passes CI and lands.

## Step 2c: Verify Fix Status

For any PR whose description claims manual fixes were applied, verify with a commit count:

```bash
gh pr view {number} --json commits --jq '.commits | length'
```

- **1 commit** with a Dependabot commit message → fixes are documented but NOT applied. The description is a plan.
- **2+ commits** → inspect the additional commits to confirm fixes were actually pushed.

This distinction matters: a PR with a detailed fix guide but only the Dependabot commit is still broken and needs implementation work, not just review.

---

## Step 3: Order the Queue

Recommend merge/review order using this default priority:

1. **Green isolated PRs**
2. **Narrow security fixes**
3. **Red but attributable PRs**
4. **GitHub Actions PRs**
5. **Broad red workspace PRs**

If two PRs overlap the same dependency lane, prefer the newer PR and note when the older one should be closed or ignored.

---

## Step 3b: Fan out parallel review (all reviewable lanes)

Once the queue is classified (Step 2) and ordered (Step 3), review **every PR worth reviewing in parallel** rather than serially. Dispatch one read-only review task per PR through the runtime's native delegation mechanism, routed to the right reviewer skill. In Hermes, use `delegate_task` in foreground batches of **at most three concurrent tasks**. Wait for all three before dispatching the next batch; never use background tasks that emit per-review commentary. The fan-out parallelizes the slow, context-heavy *investigation* (reading CI logs, diffs, changelogs); it never runs builds.

### What to review

Review every open PR **except** those whose fate is already decided by inspection:

- **Skip** explicitly-held PRs: `DO NOT MERGE` / hold branches, and PRs already marked superseded in Step 2b. Their disposition is settled — a review adds nothing. Say in the report that you skipped them and why.
- **Review everything else**, *including green isolated PRs*. A green PR is exactly where a missed changeset on a runtime dep in a published package slips through, so it still gets a (light) read-only pass — for a green PR there are no failing checks to diagnose, so the review is mostly the changeset-impact check.

Cap **concurrency, not coverage**. Hermes delegation is capped at three concurrent tasks, so run `ceil(reviewable / 3)` batches — do not drop the tail. If you defer any reviewable PR, name it in the report; never silently truncate.

### Routing

| PR | Reviewer skill | What the subagent runs | Serial follow-up by the main agent |
|----|----------------|------------------------|-------------------------------------|
| Catalog workflow PR | `catalog-review` | the whole skill — it has no local-build step (it judges the CI validation path) | none; the verdict is complete |
| Every other lane (green isolated, website-framework, tooling, runtime, GitHub Actions, major bump, broad grouped) | `dependency-review` | **read-only analysis only — its Steps 0–4** (metadata, lane, fix-status, CI-log diagnosis, changeset impact) | local verification, if and only if the verdict warrants it (below) |

The only routing decision you make here is *catalog vs. not* (a catalog PR changes `pnpm-workspace.yaml` / catalog-managed versions). Each subagent self-classifies its finer lane, so triage and the reviewer never diverge.

Each subagent returns: its decision (Safe to merge / Fix in this PR / Hold / Close), the lane it classified, and a one-line reason.

### Do NOT fan out local verification

`dependency-review` Step 5 (`gh pr checkout` + `pnpm ci`) mutates a single shared working tree; running it in parallel corrupts checkouts. **Local verification stays serial.** After the parallel review returns, run Step 5 yourself, one PR at a time, only on the candidates whose read-only verdict was *Safe to merge* or *Fix in this PR*.

Broadening the *review* fan-out does **not** broaden the *build* fan-out. No matter how many PRs you reviewed in parallel, the local builds run one at a time. (`catalog-review` has no checkout/build step, so catalog subagents need no serial follow-up.)

### Report once, when the whole batch returns

This step sends the user **exactly two messages, in order:**

1. **At dispatch** — one line naming the PRs being reviewed in parallel (e.g. "Reviewing 6 PRs in parallel; I'll report once all are in").
2. **After every review has returned** — the single consolidated report (Step 4 / Step 5), with all verdicts folded into their buckets.

Nothing goes to the user between those two messages. Do **not** post an update as each individual review finishes — wait for the whole batch, then report once.

---

## Step 4: Apply Decision Rules

Using the review verdicts from Step 3b (not the heuristic classification alone), recommend one of:

- **Merge now** — green, low blast radius, review found no extra release handling needed
- **Review manually** — worth a focused fix or serial local-verification pass
- **Hold** — do not spend time yet; wait for another cycle or lane cleanup
- **Close / supersede** — broad grouped PR is not worth debugging in current form

Use these rules:

- Prefer fixing PRs that fail in one obvious surface area
- Avoid spending time on grouped PRs that light up half the repo
- Keep GitHub Actions manual unless the repo has proven they are consistently safe
- Treat catalog PRs as their own lane; do not lump them with ordinary Dependabot PRs

---

## Step 5: Report

Return a concise triage report in this format:

```markdown
## Dependency Triage

### Merge now
- [#123](https://github.com/{owner}/{repo}/pull/123) `chore(deps): ...` — green, isolated Python lane; review confirms no changeset

### Review manually
- [#124](https://github.com/{owner}/{repo}/pull/124) `chore(deps): ...` — website-only failures, attributable (per review)

### Hold
- [#125](https://github.com/{owner}/{repo}/pull/125) `chore(deps): ...` — broad workspace failures across core/cli/sdk/website (per review)

### Special handling
- [#126](https://github.com/{owner}/{repo}/pull/126) `chore(deps): ...` — GitHub Actions PR, keep manual

### Notes
- Changeset review needed for: [#127](https://github.com/{owner}/{repo}/pull/127)
- Older superseded PRs: [#121](https://github.com/{owner}/{repo}/pull/121)
- Skipped (not reviewed): [#128](https://github.com/{owner}/{repo}/pull/128) — DO NOT MERGE hold branch
```

**Always render every PR reference as a markdown link to its PR URL — `[#NNN](url)`, never a bare `#NNN`** — so the reader can click straight through. Use the `url` field gathered in Step 1 (or `https://github.com/{owner}/{repo}/pull/NNN` for GitHub, the equivalent for Forgejo). This applies everywhere a PR is named, including the Notes section.

Be specific about *why* each PR landed in that bucket, and ground the reason in its Step 3b review verdict.

---

## Hard Rules

- Do not recommend auto-merging broad workspace PRs
- Do not recommend weakening CI just to get dependency PRs merged
- Do not treat audit exceptions as the default path forward
- Do not ignore changeset requirements when runtime deps in published packages change
- Every reviewable PR gets a read-only review via Step 3b (parallel); never parallelize the local builds — `dependency-review` Step 5 stays serial, one PR at a time
- Do not hide uncertainty; if a reviewed PR still needs deeper single-PR local verification, run `dependency-review` Step 5 on it serially
- This workflow recommends actions only. Closing, commenting on, approving, or merging a PR is public-facing and requires the user's explicit approval immediately before the forge command.
