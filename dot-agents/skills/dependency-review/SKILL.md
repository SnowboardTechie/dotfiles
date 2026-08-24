---
name: dependency-review
description: Review one SGG / CommonGrants dependency PR for risk, failing checks, release impact, and merge readiness
argument-hint: <pr-number-or-url>
---

# Dependency Review

Review a single dependency pull request in the SGG / CommonGrants monorepo and decide whether it is safe to merge, needs a focused fix, should be held, or should be closed as not worth the churn. Its package lanes, commands, and release-attribution rules are project-specific.

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
| Publish dry-run failure | Release metadata or packaging issue | Check the package's `files`/`exports` and version state; releases themselves are cut by release-please, not by anything in the PR |

### Attribution examples

- website build failures on an Astro bump → likely attributable
- broad failures across core, cli, sdk, and website on a grouped runtime PR → likely too broad to debug; consider closing
- publish dry-run or version workflow failures → check whether they are expected or whether release handling is missing

---

## Step 4: Check Release Attribution

Decide whether merging this PR actually ships a version bump for the affected
published package. There is no `.changeset/` directory in any of these repos —
[ADR-0027](https://github.com/HHS/simpler-grants-protocol/blob/main/website/src/content/docs/governance/adr/0027-release-please.md)
replaced Changesets with release-please on 2026-08-14. Releases are now derived
from the squashed PR title and the touched file paths, and a dependency change
ships a bump only if it clears **both** gates below.

### Gate 1 — path

release-please attributes a commit to a package purely by the files it touches
(`src/util/commit-split.ts`: "Commits that only touch files under paths not
specified here are ignored"). The conventional-commit **scope** in the title
plays no part in attribution.

- `simpler-grants-protocol` released paths: `lib/core/`, `lib/cli/`,
  `lib/ts-sdk/`, `lib/python-sdk/`. Everything else — `pnpm-workspace.yaml`,
  `pnpm-lock.yaml`, `website/`, `lib/changelog-emitter/` — is **not** a
  released path, so a commit confined to those is ignored outright.
- `ts-cg-grants-gov` and `py-cg-grants-gov` each publish a **single package
  rooted at `.`**, which release-please assigns every commit regardless of
  path. **This gate does not exist in the plugin repos** — do not carry the
  protocol repo's path rule over to them.

### Gate 2 — type

The title's conventional-commit type must render a changelog entry: `feat` →
minor, `fix` / `perf` / `revert` / `docs` / `refactor` / `build` → patch, any
`!` → breaking (minor while pre-1.0). `chore`, `ci`, and `test` are `hidden` in
`changelog-sections`, render nothing, and cut no release.

Both bots default to a type that **fails** this gate: Dependabot is configured
`commit-message.prefix: "chore"`, and the catalog workflow titles its PR
`chore(deps): update catalog dependencies`.

### Classify into one of three outcomes

Read the diff to decide whether the moved dependency is consumer-visible —
`dependencies` / `peerDependencies` in a `package.json`, or `[project]
dependencies` in `pyproject.toml`. Do not guess; open the file.

| What the PR changes | Outcome | What to report |
|---|---|---|
| devDependencies only | Correctly no release | Nothing to flag. |
| A consumer-visible dep, **and** it touches a released path | Blocked by gate 2 only | **Actionable** — flag `retitle needed`. Retitling to `fix(<scope>): …` before squash-merge cuts a patch release. |
| A consumer-visible dep, but touches **only** non-released paths (the catalog lane and pnpm `overrides` lane, which live in `pnpm-workspace.yaml` / `pnpm-lock.yaml`) | Blocked by gate 1 | Flag `unreleasable by path`. **No title change fixes this** — retitling clears gate 2 while gate 1 still blocks. Report it and stop there. |

That last row is a real gap with no mechanism behind it, not an oversight you
should route around. Say plainly that the change reaches consumers without a
version bump, and leave it there: how the repo should declare these ranges is
an open question for the team, not a call this review makes. Do not propose
restructuring `catalog:` usage, and do not recommend a changeset — the tool is
gone.

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
| npm root (tooling/runtime) | `pnpm run ci` | Full workspace build + test in dependency order |
| website-framework | `pnpm run ci:website` | Website build, checks, link validation |
| Python isolated | `cd lib/python-sdk && make checks && make test` | Formatting, linting, type checking, test suite |
| GitHub Actions | `pnpm install --frozen-lockfile` | Validates lockfile integrity |
| Catalog | `pnpm run ci` | Full workspace (catalog deps affect all packages) |

Use `pnpm run ci`, not `pnpm ci`: pnpm 10.33 reserves the latter as an
unimplemented native command (`ERR_PNPM_CI_NOT_IMPLEMENTED`).

If running the full workspace CI is too slow, use the package-specific command for the affected lane:

- `pnpm run ci:core` — core package
- `pnpm run ci:cli` — CLI package
- `pnpm run ci:sdk` — TypeScript SDK
- `pnpm run ci:website` — website

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

### Release impact
- devDependency-only; correctly no release

### Why
- Failure appears attributable and contained to the tooling lane, so this is worth fixing.
```

---

## Hard Rules

- Do not say “safe to merge” without checking status checks
- Do not recommend a retitle without first reading the diff to confirm the dependency is consumer-facing (`dependencies` / `peerDependencies` / `[project] dependencies`)
- Do not recommend a retitle for a PR confined to `pnpm-workspace.yaml` / `pnpm-lock.yaml` — gate 1 blocks it regardless of title. Report `unreleasable by path` and stop; do not invent a remedy
- Never tell the reader to add a changeset or run `pnpm changeset` — Changesets was removed in ADR-0027 and `.changeset/` does not exist
- Do not recommend audit exceptions just because CI is noisy
- Do not bury the decision; the report must contain one explicit recommendation
- The review is advisory. Pushing, commenting on, approving, closing, or merging the PR is public-facing and requires the user's explicit approval immediately before the action.

## Related Skills

- `dependency-triage` — queue-level classification and review routing.
- `catalog-review` — stricter lane for catalog-managed updates.
- `codex-claude-implementation-loop` — approved narrow fixes on a Codex-backed Hermes parent.
