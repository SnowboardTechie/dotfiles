---
name: catalog-review
description: Review catalog dependency update PRs with TypeSpec, lockfile, audit, and downstream package impact in mind
argument-hint: <pr-number-or-url>
---

# Catalog Review

Review a catalog dependency update PR created by the separate catalog workflow. This is not an ordinary Dependabot PR: it has wider downstream impact and needs stricter review.

---

## When to Use

Use this skill for PRs created by the catalog workflow or any PR that changes:

- `pnpm-workspace.yaml`
- `pnpm-lock.yaml` from catalog updates
- TypeSpec catalog versions
- Vitest / `@vitest/*` catalog versions
- `@types/node` in the catalog

Do not use this skill for ordinary pip, website-framework, tooling, runtime, or GitHub Actions PRs.

Note: The catalog workflow (`deps-catalog-check.yml`) runs weekly on Mondays and opens PRs on the `chore/update-catalog-deps` branch. It manages `@typespec/*`, `vitest`, `@vitest/*`, `eslint-plugin-vitest`, and `@types/node` — these are excluded from Dependabot due to known pnpm catalog bugs.

---

## Step 1: Confirm It Is a Catalog PR

Check for catalog indicators:

- branch or title like `chore(deps): update catalog dependencies`
- changes to `pnpm-workspace.yaml`
- changes to catalog-managed packages in the root ignore list or lockfile

If it is not a catalog PR, stop and use `dependency-review` instead.

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

---

## Step 5: Handle Audit Pressure Carefully

Catalog PRs often intersect with audit findings. Use a strict rule:

- prefer upgrading over suppressing
- only consider an audit exception if there is no compatible path forward
- any exception must be narrow, advisory-specific, and temporary

Never recommend a blanket exception just to get the PR merged.

---

## Step 6: Check Release / Changeset Impact

Most catalog updates are dev-tooling changes and do not need a changeset.

However, verify whether any published package changed a runtime or peer-facing dependency range as a result of the catalog update. If so, call that out explicitly.

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

### Why
- This is a real compatibility break, not grouped-update noise, so it should be fixed deliberately or held.
```

---

## Hard Rules

- Do not treat catalog PRs like ordinary Dependabot PRs
- Do not recommend merging based on one green package alone
- Do not recommend blanket audit suppressions
- Do not skip downstream impact analysis when TypeSpec packages changed
