---
name: upstream-contribution-assessment
description: "Assess upstream contribution fit and collaboration paths."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Open-Source, Contributions, Architecture, GitHub, Feasibility]
    related_skills: [codebase-inspection, github-pr-workflow, github-code-review]
---

# Upstream Contribution Assessment

Assess whether a reported problem is suitable for an upstream contribution, where the change belongs, and how to collaborate without duplicating active work. This skill stops at a grounded recommendation unless the user also asks to implement or publish.

## When to Use

- A user asks whether “we could help implement” a fix or feature upstream.
- A local defect may actually be an upstream product limitation.
- Several existing issues or pull requests overlap with the proposed work.
- The implementation boundary is unclear: client vs server, configuration vs UI, bundled asset vs user dependency.
- You need to recommend joining, salvaging, superseding, or avoiding an existing PR.

## Prerequisites

- Access to the canonical source repository and its current default branch.
- Read-only Git and forge access for contribution docs, issues, PRs, reviews, checks, and diffs.
- The product version or local source revision that exhibits the behavior when available.

Load repository-specific `AGENTS.md`, `CONTRIBUTING.md`, design documents, and PR templates before drawing conclusions.

## Procedure

### 1. Establish the canonical source and current state

1. Identify the repository that actually builds the affected product surface.
2. Record the local revision and compare it with the current upstream default branch.
3. Refresh remote refs before relying on local history.
4. Keep local runtime configuration and credentials out of reports and commands.

Do not assume the CLI, web UI, desktop app, and backend share the same implementation.

### 2. Reproduce and localize the behavior

1. Confirm the symptom in the affected surface.
2. Compare against a known-working surface using the same user configuration.
3. Trace the relevant symbol from construction through every consumer.
4. Search sibling implementations for duplicated behavior.
5. Separate transport artifacts from product behavior—for example, a non-PTY automation shell does not describe an embedded terminal’s runtime.

### 3. Read the repository’s contribution contract

Inspect:

- `CONTRIBUTING.md` and repository instruction files
- architecture or design documents for the affected package
- branch, commit, test, and cross-platform requirements
- PR template and required documentation
- license and dependency or asset-provenance rules

Treat scoped architecture documents as stronger guidance than generic repository advice.

### 4. Search existing work before designing

Search issues and pull requests across open, closed, and merged states using several vocabulary families, including user-facing terms and relevant source symbols. For each relevant PR inspect:

- full diff and changed files
- body, comments, reviews, and maintainer feedback
- checks, conflicts, mergeability, and last meaningful activity
- linked issues and adjacent or overlapping PRs
- whether maintainers can edit the contributor branch

A title-only search is insufficient. When no issue or PR names the observed behavior, trace recent commits for the affected paths and map the introducing commit back to its PR (for GitHub, `GET /repos/{owner}/{repo}/commits/{sha}/pulls`). Read that PR's patch and discussion to recover design intent. Distinguish clearly between an exact duplicate, adjacent work in the same state area, and implementation provenance that merely explains why the behavior exists.

Existing work can reveal both the intended direction and approaches maintainers already rejected.

### 5. Identify the correct authority

Before recommending code, ask who owns the state and behavior:

- **Device-local presentation:** renderer or desktop preference store
- **Shared user behavior:** profile or application configuration
- **Remote execution behavior:** backend configuration
- **Protocol behavior:** shared transport package
- **Packaged defaults:** bundled assets and build pipeline

Use deployment topology as a test. If a value names a resource installed only on the client device, a remote backend usually should not own it.

### 6. Compare implementation footprints

Evaluate at least these options when relevant:

1. documentation or configuration workaround
2. narrowly scoped bug fix
3. user-facing setting
4. bundled fallback asset or dependency
5. renderer or protocol change

Compare:

- correctness and live-update behavior
- cross-platform support
- persistence scope
- package-size and performance cost
- licensing, provenance, and supply-chain impact
- tests and manual verification burden
- overlap with active PRs

Prefer the smallest option that fixes the class of problem without violating ownership boundaries.

### 7. Validate contribution feasibility

Run the repository’s baseline checks before claiming the environment is ready. Distinguish:

- failures caused by the proposed change
- pre-existing failures
- incomplete dependency bootstrap

Do not persist environment-specific setup failures as durable rules. Report the required bootstrap step and rerun once implementation begins.

### 8. Recommend a collaboration path

Use this order:

1. Improve an active PR when its direction is sound.
2. Comment with concrete architectural or testing findings and offer help.
3. Submit a PR to the contributor’s branch if they agree and their fork permits it.
4. If abandoned, prepare a superseding PR that preserves credit and explains the changed design.
5. Open a new upstream PR only when no viable active work exists.

Never post comments, open issues, or publish branches without the user’s approval.

## Deliverable

Lead with a direct verdict, then provide:

- confirmed root cause and relevant source paths
- existing issue/PR landscape
- architectural fit and flaws in current proposals
- recommended implementation shape
- expected files, tests, platforms, and review risks
- the next collaboration step

Distinguish confirmed facts from recommendations. Link upstream issues and PRs where possible.

## Pitfalls

- Opening a duplicate PR before reading active diffs and reviews.
- Treating backend config as the universal home for client-local presentation state.
- Assuming an existing theme typography token is safe for terminal cell metrics.
- Recommending a bundled font or binary asset without size, license, and attribution analysis.
- Ignoring live-update requirements such as terminal refit or renderer cache invalidation.
- Claiming checks pass when dependencies were never bootstrapped.
- Posting to upstream merely because the technical recommendation is clear.

## Verification

Before finalizing, verify that the recommendation answers all five questions:

1. Is the problem confirmed and localized?
2. Does existing upstream work already cover it?
3. Which component owns the behavior and persistence?
4. What is the smallest mergeable implementation?
5. How should we collaborate without duplicating or erasing prior work?

## References

- [Hermes Desktop terminal-font case study](references/hermes-terminal-font.md) — client/server preference ownership, overlapping PRs, and terminal font-rendering concerns.
- [Hermes Desktop project-scope navigation case study](references/hermes-desktop-project-scope.md) — separating workspace authority from sidebar navigation intent and tracing unnamed behavior back through path history to its introducing PR.
