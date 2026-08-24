---
name: catalog-review
description: Review SGG / CommonGrants catalog dependency PRs with TypeSpec, lockfile, audit, and downstream package impact in mind
argument-hint: <pr-number-or-url>
---

# Catalog Review

Review an SGG / CommonGrants catalog dependency update PR created by the separate catalog workflow. This is not an ordinary Dependabot PR: it has wider downstream impact and needs stricter, project-specific review.

---

## When to Use

Use this skill for PRs created by the catalog workflow or any PR that changes:

- `pnpm-workspace.yaml`
- `pnpm-lock.yaml` from catalog updates
- TypeSpec catalog versions
- Vitest / `@vitest/*` catalog versions
- `@types/node` in the catalog

Do not use this skill for ordinary pip, website-framework, tooling, runtime, or GitHub Actions PRs.

This lane is specific to `HHS/simpler-grants-protocol`. Confirm the PR belongs to that repository before continuing; plugin-repo dependency PRs route to `dependency-review`.

Note: there are **two** catalog workflows, both weekly on Mondays at 15:00 UTC. Everything in the `catalog:` block of `pnpm-workspace.yaml` is excluded from Dependabot (known pnpm catalog bugs) and managed by these instead:

| Workflow | Branch | PR title | State |
|---|---|---|---|
| `deps-catalog-check.yml` | `chore/update-catalog-deps` | `chore(deps): update catalog dependencies` | normal PR, within-major bumps only |
| `deps-catalog-check-majors.yml` | `chore/update-catalog-deps-majors` | `chore(deps-major): catalog major-version bumps — REQUIRES MANUAL REVIEW` | **draft** PR, cross-major bumps |

Read the current `catalog:` block rather than trusting a list here — it moves. As of 2026-08-24 it holds 21 entries, and the ones that matter for this review are the **consumer-facing** ones:

- `@typespec/*` — all seven are `peerDependencies` of `lib/core` (declared `catalog:`)
- `zod` — a runtime `dependencies` entry of both `lib/ts-sdk` and `lib/cli`
- `@typespec/compiler` — also a runtime `dependencies` entry of `lib/cli`

The rest (`typescript`, `eslint`, `prettier`, `vitest`, `@vitest/*`, `globals`, `ts-node`, `typescript-eslint`, `@types/node`, `eslint-config-prettier`, `eslint-plugin-prettier`, `@eslint/js`) are dev-tooling. Note `eslint-plugin-vitest` was renamed upstream to `@vitest/eslint-plugin`; the old name still appears in Dependabot's ignore list but not in the catalog.

---

## Step 1: Confirm It Is a Catalog PR

Check for catalog indicators:

- branch `chore/update-catalog-deps` or title `chore(deps): update catalog dependencies` (within-major lane)
- branch `chore/update-catalog-deps-majors` or a `chore(deps-major):` title (majors lane — opened as a **draft**; treat a draft here as "not ready to merge, review the migration cost," not as a reason to skip the review)
- changes to `pnpm-workspace.yaml`
- changes to catalog-managed packages in the root ignore list or lockfile

Both catalog lanes belong to this skill. If it is not a catalog PR at all, stop and use `dependency-review` instead.

---

## Step 2: Read the Impact Surface

Inspect the changed files and identify which catalog-managed packages moved.

Pay special attention to:

- `@typespec/*`
- `vitest`
- `@vitest/*`
- `eslint-plugin-vitest`
- `@types/node`

Then map likely downstream impact:

- TypeSpec packages can affect core, changelog-emitter, cli, sdk, and website
- test packages can affect multiple JS packages and website tests
- `@types/node` can affect type-checking across the workspace

---

## Step 3: Review Validation Results

Catalog PRs should be judged against the full validation path, not a single package workflow.

At minimum inspect:

- catalog validation workflow
- audit step
- core CI
- changelog-emitter CI
- cli CI
- sdk CI
- website CI

If TypeSpec packages changed, treat failures in downstream packages as potentially expected until you determine whether they are real breaking changes.

---

## Step 4: Decide Whether the PR Is Mergeable

Use this decision model:

### Merge when

- the full validation path is green
- or any remaining non-blocking concern is understood and acceptable

### Fix in the PR when

- the new versions are clearly desirable
- the breakage is attributable
- the required code changes are straightforward and local

### Hold when

- the failures suggest a real upstream compatibility break
- the team should review release notes or wait for follow-up patches

### Reject / close when

- the update is clearly destabilizing and not worth carrying right now

### Approved “Fix in the PR” handoff

“Fix in the PR” is a recommendation, not authorization to edit or publish. Present the attributable breakage, proposed scope, affected downstream packages, and full catalog validation plan, then ask whether to implement it.

If the user approves and the current host is a Codex-backed Hermes parent with `codex-claude-implementation-loop` installed:

1. Create or reuse an isolated worktree for the catalog PR; never switch the trunk checkout in place.
2. Codex writes a self-contained plan from the catalog diff, release notes, failing logs, and downstream impact mapped in Steps 2–3.
3. Run the loop with Claude Opus as implementer and initial tester. Never silently downgrade models; Opus unavailability is a blocker.
4. Codex reviews the actual diff and independently reruns the full relevant validation path, including audit and every affected downstream package. Then return to Step 4 and recompute the merge/hold/reject decision.

Claude does not commit or push. Local commit creation and every PR mutation remain parent-owned actions; the explicit public-action approval in Hard Rules still applies. On other hosts, use the approved host-native implementation workflow with the same downstream-validation contract.

---

## Step 5: Handle Audit Pressure Carefully

Catalog PRs often intersect with audit findings. Use a strict rule:

- prefer upgrading over suppressing
- only consider an audit exception if there is no compatible path forward
- any exception must be narrow, advisory-specific, and temporary

Never recommend a blanket exception just to get the PR merged.

---

## Step 6: Check Release Attribution

Most catalog updates are dev-tooling changes that correctly produce no release. But when one moves a consumer-facing range, the catalog lane hits a structural limit you need to report accurately rather than route around.

Since [ADR-0027](https://github.com/HHS/simpler-grants-protocol/blob/main/website/src/content/docs/governance/adr/0027-release-please.md) (merged 2026-08-14) releases are cut by release-please, not Changesets; `.changeset/` no longer exists. release-please attributes a commit to a package **purely by the file paths it touches** (`src/util/commit-split.ts`: "Commits that only touch files under paths not specified here are ignored"). The released paths are `lib/core/`, `lib/cli/`, `lib/ts-sdk/`, and `lib/python-sdk/`. The conventional-commit scope in the title plays no part in attribution.

A catalog PR touches `pnpm-workspace.yaml` and `pnpm-lock.yaml`. **Neither is under a released path**, so release-please ignores the commit entirely.

That matters because `lib/core/package.json` declares every one of its `peerDependencies` as `catalog:`. pnpm substitutes the resolved range at publish time, so a `@typespec/*` catalog bump does change the peer range consumers of the published `@common-grants/core` see — while the commit that caused it is invisible to release-please.

### What to report

- **Catalog move is dev-tooling only** (vitest, `@types/node`, eslint — devDependencies everywhere they appear): correctly no release. Nothing to flag.
- **Catalog move changes a consumer-facing range**: flag **`unreleasable by path`**. State plainly that the published range moves for consumers with no version bump behind it. This fires for any `@typespec/*` bump (core's `catalog:` peer ranges, and `lib/cli`'s runtime `@typespec/compiler`) and for any `zod` bump (a runtime `dependencies` entry of both `lib/ts-sdk` and `lib/cli`) — so a catalog PR is **not** automatically dev-tooling-only.

Verify rather than assume: read `lib/core/package.json` and the other `lib/*/package.json` files to confirm which block (`peerDependencies`, `dependencies`, `devDependencies`) each moved catalog entry appears in.

**This flag is a reporting obligation, not a merge blocker.** It does not change the Step 4 decision on its own: a green catalog PR whose only outstanding item is `unreleasable by path` is still a Merge. Every `@typespec/*` bump trips this gate, so holding on it would stall catalog maintenance indefinitely and still not produce a release. Record the flag in the report and let the merge decision rest on validation, audit, and downstream impact as it did before.

### Do not route around it

Retitling does **not** fix this, and the reviewer checklist in the catalog workflow's own PR body currently says it does:

> If peerDep ranges changed for `@common-grants/core`, retitle this PR `fix(core): ...` so the change ships in a release (`chore(deps)` does not trigger a version bump)

Retitling to `fix(core):` clears the commit-type gate, but the path gate still blocks — no file under `lib/core/` is touched, so there is nothing for release-please to attribute the commit to. Note the discrepancy in your review if it is load-bearing for the decision; do not silently follow the checklist item as though it works.

There is no mechanism in this lane that turns a catalog bump into a release. Report the gap and stop. Whether the repo should declare these ranges literally instead of via `catalog:`, and what those ranges should promise consumers, is an open question headed for team discussion — not a call this review makes. Do not propose a restructuring, and do not recommend a changeset; the tool is gone.

---

## Step 7: Report

Use this format:

```markdown
## Catalog Review

- PR: #123
- Decision: Hold

### Catalog packages updated
- `@typespec/compiler` 1.9.x → 1.10.x
- `@typespec/openapi3` 1.9.x → 1.10.x

### Validation result
- `validate-workspace` fails in core and website

### Downstream impact
- TypeSpec emit changes likely affected generated OpenAPI and website schema generation

### Audit impact
- No new exception justified

### Release attribution
- `unreleasable by path` — the `@typespec/*` move changes `@common-grants/core`'s published peer range, but the PR touches only `pnpm-workspace.yaml` / `pnpm-lock.yaml`, so release-please attributes nothing. No retitle fixes this.

### Why
- This is a real compatibility break, not grouped-update noise, so it should be fixed deliberately or held.
```

---

## Hard Rules

- Do not treat catalog PRs like ordinary Dependabot PRs
- Do not recommend merging based on one green package alone
- Do not recommend blanket audit suppressions
- Do not skip downstream impact analysis when TypeSpec packages changed
- Do not recommend a changeset or `pnpm changeset` — Changesets was removed in ADR-0027
- Do not recommend a retitle to force a release; the path gate blocks catalog PRs regardless of title. Report `unreleasable by path` and leave the resolution to the team
- The review is advisory. Pushing, commenting on, approving, closing, or merging the PR is public-facing and requires the user's explicit approval immediately before the action.

## Related Skills

- `dependency-triage` — queue-level routing into the catalog lane.
- `dependency-review` — non-catalog dependency PRs.
- `codex-claude-implementation-loop` — approved attributable fixes on a Codex-backed Hermes parent.
