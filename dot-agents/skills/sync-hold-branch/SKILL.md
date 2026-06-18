---
name: sync-hold-branch
description: Use when a long-lived feature-bucket branch (HOLD-*, integration-*, batch-*, etc.) has drifted behind its source branch and PRs targeting it are blocked by stale-base symptoms — failing dep-audits, lockfile conflicts, missing CI fixes, or rebase pain. Also when the user says "sync HOLD-X", "catch HOLD-X up to main", or invokes `/sync-hold-branch`.
---

# Sync HOLD Branch

## Overview

A HOLD branch is a long-lived integration branch where related PRs batch together before landing on `main` at a checkpoint. The longer it lives without a sync, the more it accumulates phantom drift — security advisories patched on main but unfixed on HOLD, CI workflow updates, lockfile bumps — that turn into hard CI failures for every PR pointed at it.

This skill performs a **fast-forward-via-merge sync from a source branch (default `main`) into a target HOLD branch**, with explicit stop-points on conflicts, no auto-resolution, no force-push, and a post-sync notification step that comments on every open PR targeting the HOLD branch.

## When to Use

**Use when:**
- A PR's CI fails on `Audit dependencies` / lockfile / `pnpm-lock.yaml` mismatch and the HOLD base branch is older than the fix.
- User wants to "catch up" or "sync" a HOLD branch from main.
- User invokes `/sync-hold-branch [branch]`.
- A feature-bucket merge checkpoint is approaching and HOLD has drifted.

**Do NOT use when:**
- The branch is `main` / `master` / `develop` — these are downstream targets, not HOLD branches.
- The user wants to merge HOLD → main (that's a different operation — the checkpoint merge).
- The working tree is dirty (stop and report; do not stash, do not modify uncommitted work).

## Arguments

`/sync-hold-branch [target-branch] [--from <source-branch>] [--skip-pr-comments]`

- **target-branch** — the HOLD branch to update. If omitted, use the current branch if it matches `HOLD-*` / `integration-*` / `batch-*`; otherwise prompt.
- **`--from`** — source branch to merge in. Default: `main` (fall back to `master` if `main` doesn't exist).
- **`--skip-pr-comments`** — skip step 6 (PR notification). Useful for dry-runs.

## Workflow

### 1. Pre-flight

Verify:
- Current directory is inside a git repo (`git rev-parse --git-dir`).
- An `origin` remote exists (`git remote -v`).
- The working tree is clean (`git status --porcelain` is empty). **If dirty: STOP. Report the dirty files. Do not stash.**
- `gh` is authenticated for the repo's origin (`gh auth status`).

### 2. Fetch and check out the target

```bash
git fetch origin
git checkout <target-branch>
git pull --ff-only origin <target-branch>
```

If `pull --ff-only` fails (the local target has diverged from origin): **STOP. Report.** Do not force-update.

### 3. Detect "is there anything to merge?"

```bash
git log --oneline origin/<source-branch> ^<target-branch> | wc -l
```

If `0`: report **"no-op: <source> unchanged since last sync"** and exit. Skip steps 4–6.

### 4. Merge source → target

```bash
git merge --no-ff origin/<source-branch> -m "Merge <source> into <target> ($(date +%Y-%m-%d))"
```

**On conflict:**
- Run `git status` and `git diff --name-only --diff-filter=U` to list conflicting files.
- For each conflicting file, show the conflict regions verbatim (`<<<<<<<` / `=======` / `>>>>>>>` blocks).
- Run `git merge --abort` to leave the branch clean.
- **STOP. Report. Do not auto-resolve.** The conflict needs human judgment — abandon the routine and surface the conflict for a real human merge.

### 5. Validate (only if merge was clean)

Identify packages touched by the incoming commits:

```bash
git diff --name-only HEAD@{1}..HEAD | awk -F/ '/^lib\// || /^packages\// || /^apps\// {print $1"/"$2}' | sort -u
```

Run the project's documented verification command. Common shapes:
- **pnpm workspace:** `pnpm install && pnpm run -r --filter '...[HEAD@{1}]' ci` (or `pnpm run ci` at the root if not a monorepo).
- **Poetry / Python:** `poetry install && poetry run pytest` per touched package.
- **Cargo:** `cargo test --workspace` if a `Cargo.toml` workspace.

If the project's verification command isn't obvious: read its `README.md` / `CONTRIBUTING.md` / root `package.json` `scripts` field, **or ask the user**. Don't guess.

Report which packages were exercised and whether they passed. **If verification fails: STOP. Do not push.** (This is the same prove-it-before-declaring-done gate that `superpowers:verification-before-completion` formalizes — the synced branch isn't "done" until the build/test actually runs green, badge or no badge.)

**Known false-positive class: gitignored files in the working tree.** Personal files like `AGENTS.md`, `.omc/state/*.json`, or anything in the user's global `~/.config/git/ignore` are invisible to CI but visible to local prettier / eslint / format-check. If verification fails *only* on such files, treat it as local-toolchain noise — not a sync regression — and proceed.

Quick check before deciding:
```bash
git check-ignore -v <failing-file>     # non-empty output = globally ignored = false positive
```

If the failure is on a tracked file, it's real — STOP and surface. If it's on a globally-ignored file, bypass format-check and re-run the rest of the package's verification (lint / types / build / test) to confirm the genuine checks pass.

### 6. Push (no force)

```bash
git push origin <target-branch>
```

Never `--force` or `--force-with-lease` on a HOLD branch — it's shared, and downstream PRs are pinned to specific commit SHAs.

### 7. Notify open PRs targeting the HOLD branch (relevance-filtered)

Unless `--skip-pr-comments`, list open PRs:

```bash
gh pr list --base <target-branch> --state open --json number,title,headRefName,files
```

**Filter for relevance before commenting.** A sync that touches paths a PR doesn't care about is noise. For each PR, compute the intersection between the synced packages and the PR's own touched packages:

```bash
# Synced packages (from step 5)
SYNCED=$(git diff --name-only HEAD@{1}..HEAD | awk -F/ '/^lib\// || /^packages\// || /^apps\// {print $1"/"$2}' | sort -u)

# This PR's touched packages
gh pr view <N> --json files -q '.files[].path' | awk -F/ '{print $1"/"$2}' | sort -u
```

Decision:
- **No overlap** → skip the comment. The sync doesn't materially affect this PR.
- **Overlap exists** → post a relevance-tailored comment that calls out *which* synced change matters for this PR (e.g., "fixes the GHSA-… that this PR's `Audit dependencies` step was flagging", or "bumps astro which affects your website changes").

Bonus heuristic — check the PR's currently-failing CI checks (`gh pr checks <N>`). If a synced commit plausibly fixes a named failure (audit advisory, lockfile mismatch, missing CI fix), surface that connection explicitly in the comment.

Comment template (only for relevant PRs):

```
Synced `<source>` → `<target>` on YYYY-MM-DD (merge commit <sha>). <N> commits landed:
- <count> dependency bumps
- <count> CI / workflow updates
- <count> other

Notable for this PR: <specific call-out tied to overlap or to a fixed CI failure>. **To pick up the fix, rebase this PR onto the updated `<target>` tip (`<sha>`)** or use GitHub's "Update branch" button — a CI re-run alone tests the original merge commit and won't see the new base.
```

Use `gh pr comment <number> --body "..."`. Categorize via conventional-commit prefixes (`feat`, `fix`, `chore`, `ci`, `docs`, `deps`, dependabot pattern `chore(deps)`).

## Constraints (hard rules)

- **No force-push.** Ever. Not with `--force-with-lease`. Not "just this once."
- **No edits to `.changeset/`.** Changeset files are managed by their own automation.
- **No source edits beyond what the merge produces.** If you find yourself editing a file mid-merge, stop — that's a conflict resolution, which requires human judgment per step 4.
- **No `--no-verify`** on git operations. If a hook fails, surface it.
- **No auto-resolution of merge conflicts.** The skill's job is to detect and report, not to resolve.

## Red Flags — STOP

| Symptom | What it means | Action |
|---|---|---|
| `git status` not empty pre-flight | User has uncommitted work | STOP. Report. Do not stash. |
| `pull --ff-only` fails | Local HOLD has diverged from origin | STOP. Report. Don't force-update. |
| Merge conflict | Real human judgment needed | `git merge --abort`, surface conflicts, STOP. |
| Verification fails post-merge | Sync introduced a regression | STOP. Do not push. Surface the failure. |
| `gh pr list` returns unexpected PRs (e.g. one targeting a stale ref) | Branch protection / config drift | Report and ask before commenting. |

## Quick Reference

```
1. Pre-flight       → clean tree + auth + remote
2. Fetch + pull     → bring origin's view of target local
3. Diff-check       → 0 commits = no-op exit
4. Merge --no-ff    → conflicts: abort + surface + STOP
5. Validate         → run project's verification command
6. Push             → no force, no exceptions
7. Comment on PRs   → relevance-filter first (touched-packages overlap), then comment with PR-specific call-out
```

## Common Mistakes

- **Stashing a dirty tree to proceed.** The user's uncommitted work is not yours to move. Stop and ask.
- **Auto-resolving "trivial" conflicts** (e.g. lockfiles). Lockfile conflicts are rarely trivial — they hide dep-version churn. Surface and let a human regenerate.
- **Force-pushing because the merge is "obviously fine."** HOLD branches are shared; downstream PR commits reference specific SHAs. Force-push silently breaks every open PR pointed at the branch.
- **Skipping verification because "main's CI already passed."** Main's CI ran on main, not on HOLD's combined state. A green main + green HOLD-pre-sync can still produce a broken HOLD-post-sync.
- **Commenting on PRs before the push lands.** If the push fails (e.g. branch protection), the comments are now lying. Push first, comment after.
- **Blanket-commenting on every open PR without relevance filter.** Sync notifications create signal only when the synced commits intersect with paths the PR cares about. Non-overlapping PRs get noise instead. Always do the touched-packages intersection in step 7 first.
- **Treating a gitignored-file format-check failure as a sync regression.** Personal files in the user's global `~/.config/git/ignore` (e.g. `AGENTS.md`, `.omc/state/*.json`) are invisible to CI but visible to local tooling. Use `git check-ignore -v` to distinguish; bypass format-check locally when the only failures are globally-ignored files, and re-run lint/types/build/test to confirm the genuine checks pass.
- **Telling PR authors to "just re-run CI" after the sync.** With `actions/checkout@v6` defaults, `pull_request` jobs run against a merge commit computed when the workflow was *originally triggered*. A re-run uses that same merge commit and won't see the updated base. Affected PRs need a rebase, an "Update branch" click, or a fresh push to regenerate the merge commit. Reflect this in the step-7 comment template.
