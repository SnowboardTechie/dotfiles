---
name: dependency-review
description: Review one SGG / CommonGrants dependency PR for risk, failing checks, release impact, and merge readiness
argument-hint: <pr-number-or-url>
---

# Dependency Review

Review a single dependency pull request in the SGG / CommonGrants monorepo and decide whether it is safe to merge, needs a focused fix, should be held, or should be closed as not worth the churn. Its dependency update types, commands, and release-attribution rules are project-specific.

---

## Input

First confirm the PR belongs to a repository in the SGG workspace manifest `~/code/sgg/repos.tsv`. Stop if it belongs to `HHS/simpler-grants-gov`: Bryan doesn't manage that repo's dependencies. The verification matrix below is fullest for `simpler-grants-protocol`; for any other repo, use only commands actually defined by that repo.

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

## Step 2: Determine the Dependency Update Type

Classify the PR before deciding what to do.

Possible dependency update types:

- Python isolated lockfile
- website framework
- tooling
- runtime
- GitHub Actions
- catalog workflow
- major version bump

State the dependency update type explicitly in your review.

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
| `pnpm audit` failure | New transitive vulnerabilities | Follow the remedy ladder in `dependency-pr-readiness` (refresh, upgrade the parent, drop the dependency, then an approved override); never suppress. Flag any cross-major override written as a bare `pkg@<range>` key: it should be one `parent>pkg@<range>` entry per parent so future dependents stay visible to the audit |
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
ships a bump only if it passes **both** rules below.

### Rule 1 — path

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
  path. **This rule does not exist in the plugin repos** — do not carry the
  protocol repo's path rule over to them.

### Rule 2 — type

The title's conventional-commit type must render a changelog entry: `feat` →
minor, `fix` / `perf` / `revert` / `docs` / `refactor` / `build` → patch, any
`!` → breaking (minor while pre-1.0). `chore`, `ci`, and `test` are `hidden` in
`changelog-sections`, render nothing, and cut no release.

Both bots default to a type that **fails** this rule: Dependabot is configured
`commit-message.prefix: "chore"`, and the catalog workflow titles its PR
`chore(deps): update catalog dependencies`.

### Classify into one of three outcomes

Read the diff to decide whether the moved dependency is consumer-visible —
`dependencies` / `peerDependencies` in a `package.json`, or `[project]
dependencies` in `pyproject.toml`. Do not guess; open the file.

| What the PR changes | Outcome | What to report |
|---|---|---|
| devDependencies only | Correctly no release | Nothing to flag. |
| A consumer-visible dep, **and** it touches a released path | Blocked by rule 2 only | **Actionable** — flag `retitle needed`. Retitling to `fix(<scope>): …` before squash-merge cuts a patch release. |
| A consumer-visible dep, but touches **only** non-released paths (catalog and pnpm `overrides` updates, which live in `pnpm-workspace.yaml` / `pnpm-lock.yaml`) | Blocked by rule 1 | Flag `unreleasable by path`. **No title change fixes this** — retitling satisfies rule 2 while rule 1 still blocks. Report it and stop there. |

That last row is a real gap with no mechanism behind it, not an oversight you
should route around. Say plainly that the change reaches consumers without a
version bump, and leave it there: how the repo should declare these ranges is
an open question for the team, not a call this review makes. Do not propose
restructuring `catalog:` usage, and do not recommend a changeset — the tool is
gone.

---

## Step 5: Verify Locally Before Recommending Merge

This step applies a no-claim-without-evidence discipline using native terminal execution: never say "safe to merge" on the strength of a green PR badge alone; run the commands and read the output. The per-type matrix below is this skill's domain-specific check.

Before recommending "safe to merge," check out the branch and run the relevant verification commands:

```bash
gh pr checkout {number}
```

### Verification by dependency update type

| Dependency update type | Verification command | What it covers |
|-------------|---------------------|----------------|
| npm root (tooling/runtime) | `pnpm run ci` | Full workspace build + test in dependency order |
| website-framework | `pnpm run ci:website` | Website build, checks, link validation |
| Python isolated | `cd lib/python-sdk && make checks && make test` | Formatting, linting, type checking, test suite |
| GitHub Actions | `pnpm install --frozen-lockfile` | Validates lockfile integrity |
| Catalog | `pnpm run ci` | Full workspace (catalog deps affect all packages) |

Use `pnpm run ci`, not `pnpm ci`: pnpm still reserves the latter as an
unimplemented native command (`ERR_PNPM_CI_NOT_IMPLEMENTED`). Verified against
pnpm 11.20.0, the version this repo pins in `packageManager`.

If running the full workspace CI is too slow, use the package-specific command for the affected dependency update type:

- `pnpm run ci:core` — core package
- `pnpm run ci:cli` — CLI package
- `pnpm run ci:sdk` — TypeScript SDK
- `pnpm run ci:changelog-emitter` — changelog-emitter (unpublished, but it has its own CI)
- `pnpm run ci:website` — website

Skip local verification only when the PR is green on GitHub CI and changes are clearly dev-only patches.

### Model generator bumps (Python SDK)

When the PR changes the `datamodel-code-generator` version in `lib/python-sdk`, also compare what the old and new versions generate, even when the skip rule above would apply. Its output is not committed (only `lib/python-sdk/generated/scripts/` is), so CI never shows the drift; the next `generate_models.sh` run would. Reviewers ask for this (Karina on [#1411](https://github.com/HHS/simpler-grants-protocol/pull/1411#discussion_r4635003037), 0.83 to 0.96).

From the PR checkout's root, with `OLD` and `NEW` set to the exact versions from the lockfile diff:

```bash
repo=$(git rev-parse --show-toplevel); work=$(mktemp -d)
cp "$repo"/lib/python-sdk/generated/scripts/*.sh "$work"/ && cd "$work"
sed -i '' 's/poetry run datamodel-codegen/datamodel-codegen/' generate_models.sh
for v in "$OLD" "$NEW"; do
  uvx --python 3.13 --from "datamodel-code-generator==$v" \
    bash ./generate_models.sh "$repo/website/public/schemas/yaml" "out-$v" >/dev/null 2>&1
done
ls "out-$OLD/pydantic" | wc -l   # non-zero, or the run failed
diff -r -I '^#   timestamp:' "out-$OLD/pydantic" "out-$NEW/pydantic" && echo "no change beyond timestamps"
```

The scripts call each other by relative path, so they run from the copy's directory. The check is done when both versions generated the same non-zero file count and the diff is read. Report the result in the review: identical output, or what changed and in how many files.

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

The recommendation is not authorization to edit or publish. Present the diagnosis, proposed scope, acceptance criteria, and required checks for its dependency update type, then ask whether to implement the fix.

If the user approves and the current harness is a Pi orchestrator or a Codex-backed Hermes orchestrator:

1. Create or reuse an isolated worktree for the dependency PR; do not switch the primary checkout in place.
2. Load `coding-agent-handoff-supervision`, reuse or create the governing project-workspace issue, and launch the normal visible Pi background agent handoff through Rex. An unavailable Rex route stops the handoff; do not silently choose a hidden background route instead.
3. Give the background agent the issue/PR URLs, exact implementation repository and worktree, explicit authority boundaries, and this skill's Step 5 verification outcome. Do not duplicate a self-contained implementation plan into the prompt.
4. The orchestrator inspects the actual diff and independently reruns the verification for its dependency update type. Return to Step 6 and recompute the recommendation from the final evidence.

The background agent's local commit, push, and PR/issue permissions must each be stated explicitly; the normal route forbids all three and leaves local commit creation and the reviewed dependency-PR branch push orchestrator-owned. The user's approval to implement the fix authorizes the orchestrator to edit, verify, commit, and push that reviewed unit without a second prompt. Commenting, approving, closing, and merging each still require their own direct request under Hard Rules. In other harnesses, use the approved harness-native implementation workflow while preserving the same diagnosis, verification, and authorization contract.

**Explicit background-only alternative.** Use `codex-claude-implementation-loop` only when Bryan explicitly requests a background wrapper for that same run. It is never an automatic substitute for the visible Rex handoff, and wrapper unavailability stops rather than switching to another background agent.

---

## Step 7: Report

Use this format:

```markdown
## Dependency Review

- PR: #123
- Dependency update type: tooling
- Decision: Fix in this PR

### What changed
- TypeScript and ESLint minor bumps in the root workspace

### Failing checks
- `build` — tsconfig incompatibility in website only
- `validate-workspace` — same root cause cascades outward

### Release impact
- devDependency-only; correctly no release

### Why
- Failure appears attributable and contained to the tooling update, so this is worth fixing.
```

---

## Hard Rules

- Do not say “safe to merge” without checking status checks
- Do not recommend a retitle without first reading the diff to confirm the dependency is consumer-facing (`dependencies` / `peerDependencies` / `[project] dependencies`)
- Do not recommend a retitle for a PR confined to `pnpm-workspace.yaml` / `pnpm-lock.yaml` — rule 1 blocks it regardless of title. Report `unreleasable by path` and stop; do not invent a remedy
- Never tell the reader to add a changeset or run `pnpm changeset` — Changesets was removed in ADR-0027 and `.changeset/` does not exist
- Do not recommend audit exceptions just because CI is noisy
- Do not bury the decision; the report must contain one explicit recommendation
- The review itself is advisory: producing it authorizes no writes.
- Once the user approves a fix, that approval covers the whole unit of work — edit, verify, commit, and push to the PR branch. Do not stop after the edit to ask about committing, and do not ask a second time before pushing.
- Commenting on, approving, closing, or merging the PR speaks to other people and still requires a direct request each time.

## Related Skills

- `dependency-triage` — queue-level classification and review routing.
- `catalog-review` — stricter review for catalog-managed updates.
- `coding-agent-handoff-supervision` — normal visible, issue-backed fix handoff.
- `codex-claude-implementation-loop` — explicit background-only alternative.
