---
name: dependency-triage
description: Triage open dependency PRs by blast radius, CI state, and merge order
---

# Dependency Triage

Review open dependency pull requests, sort them into the right review order, and recommend which to merge, review manually, hold, or close.

This skill is designed for low-overhead weekly dependency maintenance in repositories that use Dependabot, grouped update lanes, and CI-heavy monorepos.

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

## Step 4: Apply Decision Rules

For each PR, recommend one of:

- **Merge now** — green, low blast radius, no extra release handling needed
- **Review manually** — worth a focused fix or verification pass
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
- #123 `chore(deps): ...` — green, isolated Python lane

### Review manually
- #124 `chore(deps): ...` — website-only failures, likely attributable

### Hold
- #125 `chore(deps): ...` — broad workspace failures across core/cli/sdk/website

### Special handling
- #126 `chore(deps): ...` — GitHub Actions PR, keep manual

### Notes
- Changeset review needed for: #127
- Older superseded PRs: #121
```

Be specific about *why* each PR landed in that bucket.

---

## Hard Rules

- Do not recommend auto-merging broad workspace PRs
- Do not recommend weakening CI just to get dependency PRs merged
- Do not treat audit exceptions as the default path forward
- Do not ignore changeset requirements when runtime deps in published packages change
- Do not hide uncertainty; if a PR needs deeper inspection, say so and hand it to `dependency-review`
