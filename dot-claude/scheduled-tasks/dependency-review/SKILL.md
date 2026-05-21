---
name: dependency-review
description: Look for dependabot PRs that are ready for my eyes
---

Triage open dependency PRs in HHS/simpler-grants-protocol. Be silent unless
there is something to merge, review, handle specially, or close. Do not post
comments, do not merge, do not push. Read-only report.

Every reported PR must carry a changelog read. Classification on CI state
alone is not enough — a green minor can still ship a breaking change, and a
major bump that "looks routine" can hide a migration. If you can't determine
breaking-change status, say so explicitly; do not omit the field.

## Step 1: Gather

```bash
gh pr list -R HHS/simpler-grants-protocol \
  --label dependencies --state open --limit 30 \
  --json number,title,headRefName,author,labels,url,createdAt,statusCheckRollup,mergeable,mergeStateStatus,autoMergeRequest
```

If zero PRs: respond with exactly "No dependency PRs open." and stop.

## Step 2: Classify each into one lane

- A. Green and isolated
- B. Red but attributable (one obvious failing surface)
- C. Red and broad (hold, narrow, or supersede)
- D. Special handling: GitHub Actions, catalog workflow, major version bumps,
  or changeset-relevant runtime deps in published packages

Special handling is still a manual review by you — it's the "review manually
with this elevated-risk reason flagged upfront" bucket. Items routed here go
through your eyes, but the report tags *why* (major bump / GitHub Actions /
catalog / changeset-relevant runtime) so you weigh the right thing on intake.

## Step 2b: Supersedes

For PRs in overlapping lanes, compare file sets:

```bash
gh pr view <N> --json files --jq '[.files[].path] | sort'
```

Flag the narrower PR as superseded if the broader one covers it.

## Step 2c: Verify fix status

If a PR description claims manual fixes:

```bash
gh pr view <N> --json commits --jq '.commits | length'
```

1 commit (Dependabot only) = fixes NOT applied (description is a plan).
2+ commits = inspect and confirm.

## Step 2d: Mergeability and auto-merge

From the gather query, derive per-PR flags:

- `autoMergeRequest != null` → **auto-merge enabled**. Do NOT route to
  Merge now (GitHub will land it once CI goes green). List in Notes so you
  know which PRs are queued.
- `mergeable == "CONFLICTING"` → **conflict with base**. Route to Review
  manually with a `conflict` flag (Dependabot's rebase didn't take or hasn't
  fired yet).
- `mergeStateStatus == "BEHIND"` alone is fine — Dependabot rebases on its
  own cadence. Only flag if also stale (see 2e).

## Step 2e: Age

Compute days from `createdAt` to today. PRs older than 14 days carry a
`stale (Nd)` flag. Stale + red is a candidate for Close / supersede; stale +
green deserves a Notes mention so it doesn't get lost.

## Step 3: Read changelogs (REQUIRED for every reported PR)

This is the step the previous version of the routine skipped. Do not skip it.
Run this for every PR you intend to put in Merge-now, Review-manually,
Special-handling, or Close-supersede. (Hold-only PRs may be skipped.)

### 3a: Pull Dependabot's pasted release notes from the PR body

```bash
gh pr view <N> --json body --jq '.body'
```

Dependabot pastes structured `Release notes` and `Changelog` sections per
package, including grouped PRs (one block per dep). Read them.

For each updated package, identify:

1. **Version delta** — semver classification (major / minor / patch) AND the
   raw range (e.g. `astro 5.13.2 → 6.1.0`). A "minor" that crosses a 0.x
   boundary is effectively a major; flag it.
2. **Breaking changes** — search the body for `BREAKING`, `Breaking change`,
   `Removed`, `Migration`, `deprecat`, or a `### Breaking` heading. Quote the
   one-line summary if present.
3. **Notable behavior changes** — anything that mentions defaults changing,
   APIs renamed, peer-dep range bumps, Node version requirements, or
   transitive lockfile churn.

### 3b: Fallback when the body is truncated or missing release notes

Dependabot truncates very large grouped PRs. If a package block is missing or
cut off, fetch the upstream release page directly. Resolve `<owner>/<repo>`
from the package's npm metadata if the body doesn't already link it:

```bash
# npm package → upstream repo
npm view <pkg> repository.url homepage --json

# fetch release notes for the version range
gh release list -R <owner>/<repo> --limit 20 \
  --json tagName,name,publishedAt,isPrerelease
gh release view <tagName> -R <owner>/<repo> --json body --jq '.body'
```

For Python deps (pip lane), check the project's GitHub releases or
`CHANGELOG.md` the same way; PyPI does not host release notes consistently.

If you still cannot find changelog content for a package, mark its
breaking-change status as `unknown — changelog not available` in the report.
Do not silently omit.

### 3c: Catalog and TypeSpec PRs

For catalog workflow PRs and any PR touching `@typespec/*`, the body usually
omits per-package notes. Always run 3b for these. TypeSpec minor bumps have
historically broken downstream emitters; treat any TypeSpec move as worth a
breaking-change check even when CI is green.

### 3d: GitHub Actions PRs

For `actions/*` package bumps (e.g. `actions/checkout`, `actions/setup-node`),
Dependabot does not paste release notes into the body the way it does for
npm or pip packages. Fetch from the action's release page directly:

```bash
gh release view <tagName> -R <owner>/<action-name> --json body --jq '.body'
```

Tag is the version Dependabot is moving to (e.g. `v4`). Many actions only
publish major-version tags; if `<tagName>` is a moved alias, follow it to
the underlying release for the actual notes.

## Step 4: Security advisory context

For PRs carrying the `security` label, surface advisory severity. Dependabot
pastes `CVSS Score:` and severity lines into the body alongside the GHSA ID;
parse those out:

```bash
gh pr view <N> --json body --jq '.body' \
  | grep -E -i 'GHSA-[0-9a-z-]+|CVSS|Severity'
```

If the body lacks advisory info (older PRs, body truncated), fall back to:

```bash
gh api repos/HHS/simpler-grants-protocol/dependabot/alerts \
  --jq '.[] | {ghsa: .security_advisory.ghsa_id,
               severity: .security_advisory.severity,
               summary: .security_advisory.summary}'
```

Surface the severity in the report flag line, e.g.
`security: CRITICAL (GHSA-xxxx-xxxx-xxxx)`. Critical and high jump to the
top of the order regardless of lane.

## Step 5: Changeset presence

For PRs that touch runtime or peer dependencies in published packages,
verify a changeset entry is present in the PR's files.

Runtime/peer-relevant package files:

- `lib/core/package.json` (peer or runtime change)
- `lib/cli/package.json` (runtime change)
- `lib/ts-sdk/package.json` (runtime change)
- `lib/python-sdk/pyproject.toml` (runtime change)

devDependency-only bumps do not need a changeset. Read the diff of the
package file to confirm whether the change is in `dependencies`,
`peerDependencies`, or `devDependencies`:

```bash
gh pr diff <N> -- lib/core/package.json
```

If a runtime or peer dep moved and the PR's file list contains no
`.changeset/*.md` entry, flag `no changeset` and surface the PR in the
"Changeset review needed for" Notes line.

## Step 6: Order

1. Critical / high security
2. Green isolated
3. Narrow security (moderate / low)
4. Red but attributable
5. GitHub Actions
6. Broad red workspace

## Step 7: Decide per PR

Merge now / Review manually / Special handling / Hold / Close-supersede.

Routing rules:

- **Merge now**: green CI, isolated lane, no breaking changes flagged in
  Step 3, not stale, no `conflict` flag, no `no changeset` flag. Auto-merge
  PRs do NOT go here — they land via GitHub once green and only need a Notes
  mention.
- **Review manually**: red but attributable, OR `conflict` flag, OR Step 3
  surfaced a breaking change in a non-major bump, OR `unknown` changelog
  status for a published-package runtime dep.
- **Special handling**: major version bumps, GitHub Actions PRs, catalog
  workflow PRs, runtime/peer dep changes flagged `no changeset`. Tagged with
  the elevated-risk reason on intake.
- **Hold**: red and broad, no clean attribution, not urgent.
- **Close / supersede**: superseded by a broader PR, OR red and broad and
  stale.

## Step 8: Output

If Merge-now, Review-manually, Special-handling, and Close-supersede are ALL
empty (even if Hold has entries), respond with exactly:

  "No dependency PRs need attention this cycle."

Otherwise emit the report. Only include buckets that have PRs. Preserve PR
links. Every PR line must include a `Versions:` and a `Changelog:` sub-line
— say `none flagged` when the changelog is clean, never omit the field.
Add a `Flags:` sub-line only when there is something to flag (auto-merge,
stale, conflict, no changeset, security severity); skip it otherwise.

```markdown
## Dependency Triage (YYYY-MM-DD)

### Merge now
- #N [title](url) — green, isolated lane X
  - Versions: `pkg 1.2.3 → 1.2.4` (patch)
  - Changelog: none flagged

### Review manually
- #N [title](url) — one attributable failure
  - Versions: `astro 5.13.2 → 6.1.0` (major)
  - Changelog: drops Node 18; `getStaticPaths` return shape changed — see
    [release notes](https://github.com/withastro/astro/releases/tag/astro%406.0.0)
  - Flags: stale (18d), no changeset

### Special handling
- #N [title](url) — major bump
  - Versions: `@typespec/compiler 1.9.0 → 1.10.0` (minor, but emitter-affecting)
  - Changelog: unknown — release notes not in body, releases page empty
  - Flags: security: HIGH (GHSA-xxxx-xxxx-xxxx)

### Close / supersede
- #N [title](url) — superseded by #M

### Notes
- Auto-merge enabled (FYI): #N, #N
- Stale (>14d) and green: #N (24d)
- Changeset review needed for: #N
- Hold (FYI only): #N, #N
```

## Hard rules

- No auto-merge recommendations for broad workspace PRs
- No CI-weakening
- No ignoring changeset requirements
- Every reported PR must carry a `Versions:` line and a `Changelog:` line.
  When you can't read the changelog, say `unknown — <why>`. Silence is not
  acceptable, because silence is what the previous version of this routine
  did and it's the bug being fixed.