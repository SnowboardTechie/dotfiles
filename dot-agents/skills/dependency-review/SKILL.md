---
name: dependency-review
description: Review one SGG / CommonGrants dependency PR for risk, failing checks, changeset impact, and merge readiness
argument-hint: <pr-number-or-url>
---

# Dependency Review

Review a single dependency pull request in the SGG / CommonGrants monorepo and decide whether it is safe to merge, needs a focused fix, should be held, or should be closed as not worth the churn. Its package lanes, commands, and changeset rules are project-specific.

---

## Input

First confirm the PR belongs to one of the maintained SGG dependency queues: `HHS/simpler-grants-protocol`, `common-grants/py-cg-grants-gov`, or `common-grants/ts-cg-grants-gov`. Stop if it belongs to `HHS/simpler-grants-gov`; that Renovate queue is outside this workflow. The lane matrix below is fullest for `simpler-grants-protocol`; for either plugin repo, use only commands actually defined by that repo.

Accepts either:

- PR number: `dependency-review 123`
- PR URL: `dependency-review https://github.com/org/repo/pull/123`
- Nothing (detect the PR from the current branch)

---

## Step 0: Identify the PR

Use the same detection pattern as other PR-oriented skills:

- If a PR number or URL is provided, parse it
- If nothing is provided, resolve the PR from the current branch

Prefer forge-native tooling.

---

## Step 1: Fetch PR Metadata and Changed Files

Collect:

- title
- URL
- body
- base branch
- labels
- changed files
- current status checks

### GitHub

```bash
gh pr view {number} \
  --json number,title,url,body,baseRefName,labels,files,statusCheckRollup
```

Also inspect the diff:

```bash
git diff {baseRefName}...HEAD --stat
git diff {baseRefName}...HEAD
```

---

## Step 2: Determine the Update Lane

Classify the PR before deciding what to do.

Possible lanes:

- Python isolated lockfile lane
- website-framework lane
- tooling lane
- runtime lane
- GitHub Actions lane
- catalog workflow lane
- major version bump

State the lane explicitly in your review.

---

## Step 2b: Verify Fix Status

Check whether the PR has only the Dependabot commit or additional fix commits:

```bash
gh pr view {number} --json commits --jq '.commits[] | "\(.oid[0:8]) \(.messageHeadline)"'
```

- **1 commit** with a Dependabot message → fixes described in the PR body are NOT applied. Treat the description as a plan, not a report.
- **2+ commits** → inspect the additional commits to confirm fixes match what the description claims.

Do not trust PR descriptions as evidence of applied changes without verifying the commit history.

---

## Step 3: Review the Failing Checks

### 3a: Identify failures

Get the list of failing checks and their run URLs:

```bash
gh pr view {number} --json statusCheckRollup \
  --jq '.statusCheckRollup[] | select(.conclusion == "FAILURE") | "\(.name)\t\(.detailsUrl)"'
```

### 3b: Read the actual failure logs

Extract the run ID from the details URL and read the failing job output:

```bash
gh run view {run_id} --log-failed
```

### 3c: Diagnose the root cause

For every failing check, answer three questions:

1. **What failed?**
2. **Is it in the same surface area as the dependency update?**
3. **Is this likely a real compatibility issue or just grouped-update noise?**

### Known failure patterns

| Error | Cause | Fix |
|-------|-------|-----|
| `ERR_PNPM_BROKEN_LOCKFILE` | Dependabot generated a malformed lockfile | `gh pr checkout {n}`, then `rm pnpm-lock.yaml && pnpm install`, commit, push |
| `ERR_PNPM_LOCKFILE_CONFIG_MISMATCH` | Lockfile version doesn't match pnpm version | `pnpm install` to regenerate |
| Import or compile error after bump | Breaking API change in updated dependency | Read the dep's changelog (linked in PR body), search codebase for affected API, migrate |
| `pnpm audit` failure | New transitive vulnerabilities | Add `pnpm.auditConfig.ignoreGhsas` entries only after reading the advisory; prefer upgrading over suppressing |
| Missing secret (e.g., `FIDER_API_TOKEN`) | Dependabot PRs lack access to repo secrets | Add `&& env.SECRET_NAME != ''` guard to the workflow step condition |
| Publish dry-run failure | Release metadata or changeset issue | Check whether release handling is missing or a changeset is needed |

### Attribution examples

- website build failures on an Astro bump → likely attributable
- broad failures across core, cli, sdk, and website on a grouped runtime PR → likely too broad to debug; consider closing
- publish dry-run or version workflow failures → check whether they are expected or whether release handling is missing

---

## Step 4: Check Changeset Impact

Review whether the update touched runtime or peer dependencies in published packages.

Use the repository's dependency-management rules:

- `lib/core` — peer dependency range changes may need a changeset
- `lib/cli` — runtime dependency changes may need a changeset
- `lib/ts-sdk` — runtime dependency changes may need a changeset
- `lib/python-sdk` — runtime dependency changes may need release handling
- devDependency-only bumps do **not** need a changeset

Do not guess. Read the relevant `package.json` or `pyproject.toml` files if needed.

---

## Step 5: Verify Locally Before Recommending Merge

This step applies a no-claim-without-evidence discipline using native terminal execution: never say "safe to merge" on the strength of a green PR badge alone; run the commands and read the output. The per-lane matrix below is this skill's domain-specific gate.

Before recommending "safe to merge," check out the branch and run the relevant verification commands:

```bash
gh pr checkout {number}
```

### Per-lane verification

| Lane | Verification command | What it covers |
|------|---------------------|----------------|
| npm root (tooling/runtime) | `pnpm ci` | Full workspace build + test in dependency order |
| website-framework | `pnpm ci:website` | Website build, checks, link validation |
| Python isolated | `cd lib/python-sdk && make checks && make test` | Formatting, linting, type checking, test suite |
| GitHub Actions | `pnpm install --frozen-lockfile` | Validates lockfile integrity |
| Catalog | `pnpm ci` | Full workspace (catalog deps affect all packages) |

If running the full workspace CI is too slow, use the package-specific command for the affected lane:

- `pnpm ci:core` — core package
- `pnpm ci:cli` — CLI package
- `pnpm ci:sdk` — TypeScript SDK
- `pnpm ci:website` — website

Skip local verification only when the PR is green on GitHub CI and changes are clearly dev-only patches.

---

## Step 6: Make a Recommendation

Return one clear decision:

- **Safe to merge**
- **Fix in this PR**
- **Hold for later**
- **Close / let a narrower PR replace it**

Use these defaults:

- Merge if green and low blast radius
- Fix if the failure is narrow and attributable
- Hold if the change is plausible but not urgent and the failure needs more time
- Close if the grouped PR is so broad that debugging it is wasted effort

### Approved “Fix in this PR” handoff

The recommendation is not authorization to edit or publish. Present the diagnosis, proposed scope, acceptance criteria, and required lane-specific checks, then ask whether to implement the fix.

If the user approves and the current host is a Codex-backed Hermes parent with `codex-claude-implementation-loop` installed:

1. Create or reuse an isolated worktree for the dependency PR; do not switch the trunk checkout in place.
2. Codex writes a self-contained implementation plan grounded in the failing logs, dependency changelog, affected call sites, and this skill's Step 5 verification commands.
3. Run the loop with Claude Opus as implementer and initial tester. Never silently downgrade models; an unavailable Opus run stops with a blocker.
4. Codex inspects the actual diff and independently reruns the affected lane's verification. Return to Step 6 and recompute the recommendation from the final evidence.

Claude does not commit or push. Local commit creation and any update to the dependency PR remain parent-owned actions, and pushing, commenting, approving, closing, or merging still requires the explicit public-action approval in Hard Rules. On other hosts, use the approved host-native implementation workflow while preserving the same diagnosis and verification contract.

---

## Step 7: Report

Use this format:

```markdown
## Dependency Review

- PR: #123
- Lane: tooling
- Decision: Fix in this PR

### What changed
- TypeScript and ESLint minor bumps in the root workspace

### Failing checks
- `build` — tsconfig incompatibility in website only
- `validate-workspace` — same root cause cascades outward

### Changeset impact
- No changeset needed; devDependency-only changes

### Why
- Failure appears attributable and contained to the tooling lane, so this is worth fixing.
```

---

## Hard Rules

- Do not say “safe to merge” without checking status checks
- Do not recommend a changeset without verifying the dependency is runtime or peer-facing
- Do not recommend audit exceptions just because CI is noisy
- Do not bury the decision; the report must contain one explicit recommendation
- The review is advisory. Pushing, commenting on, approving, closing, or merging the PR is public-facing and requires the user's explicit approval immediately before the action.

## Related Skills

- `dependency-triage` — queue-level classification and review routing.
- `catalog-review` — stricter lane for catalog-managed updates.
- `codex-claude-implementation-loop` — approved narrow fixes on a Codex-backed Hermes parent.
