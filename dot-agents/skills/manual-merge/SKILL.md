---
name: manual-merge
description: Manual squash-merge a branch into main locally, using its PR description as the commit message
---

# Merge - Manual Local Squash Merge

For when you need to merge a branch into main **locally** (e.g. Forgejo
repos without squash-merge UI, or manual merges for GPG-signed commits).

Fetches the PR title and description from the forge and uses them as the
commit message. Always squash-merges to keep main's history linear.

---

## Quick Reference

```
/merge                     # merge current branch into main
/merge fix/ci-triggers     # merge named branch into main
```

---

## Execution

### 1. Determine Branch

If a branch name is provided as an argument, use it. Otherwise:

```bash
branch=$(git branch --show-current)
```

**ABORT** if the branch is `main` or `master` — you cannot merge main into main.

### 2. Detect Forge

```bash
remote_url=$(git remote get-url origin 2>/dev/null)
if [[ "$remote_url" == *"github.com"* ]]; then
  forge="github"
elif [[ "$remote_url" == *"forgejo"* || "$remote_url" == *"gitea"* || "$remote_url" == *"codeberg"* || "$remote_url" == *"snowboardtechie"* ]]; then
  forge="forgejo"
else
  forge="none"
fi
```

### 3. Find PR for Branch

Look for a PR (open or merged) with the branch as the head ref.

#### GitHub

```bash
# Try open first, then closed/merged
pr_json=$(gh pr list --head "$branch" --json number,title,body --limit 1 2>/dev/null)
if [ "$pr_json" = "[]" ] || [ -z "$pr_json" ]; then
  pr_json=$(gh pr list --head "$branch" --state merged --json number,title,body --limit 1 2>/dev/null)
fi
```

#### Forgejo

Use `tea api` — `{owner}` and `{repo}` are auto-resolved from the local
git remote context.

```bash
# Search open PRs first, then closed
tea api "/repos/{owner}/{repo}/pulls?state=open" \
  | jq -c --arg branch "$branch" '.[] | select(.head.ref == $branch) | {number: .number, title: .title, body: .body, url: .html_url}' \
  | head -1
```

If empty, try closed PRs with the same pattern.

Parse the result to extract `number`, `title`, `body`, and `url`.

### 4. Handle Missing PR

If no PR is found:

```
No PR found for branch "$branch".

Options:
1. Provide a commit message manually
2. Abort and create a PR first

What would you like to do?
```

If the user provides a manual message, use it. Otherwise abort.

### 5. Confirm with User

Show what will happen:

```
Squash-merging "$branch" into main:

  Title: <PR title>
  PR #<number>

  <first 5 lines of PR body>

Proceed? (This will switch to main and squash-merge)
```

### 6. Pre-flight Checks

Before merging, verify:

```bash
# Working tree is clean
git status --porcelain
# If dirty, ABORT: "Working tree has uncommitted changes. Commit or stash first."

# Main is up to date with remote
git fetch origin main
git log main..origin/main --oneline
# If behind, warn: "main is behind origin/main. Pull first?"
```

### 7. Squash Merge

```bash
git checkout main
git merge --squash "$branch"
```

If there are merge conflicts, report them and abort:
```bash
git merge --abort
git checkout "$branch"
# Report conflicts to user
```

### 8. Commit

Use the PR title as the commit subject and the PR body as the commit body.

Format the commit message as:

```
<PR title> (#<PR number>)

<PR body>
```

Example:
```
fix: allow manual CI triggers, apply rustfmt, fix clippy warnings (#2)

## Summary

Fix CI pipeline configuration and repo discovery filtering.

## Changes

- Add `manual` to Woodpecker CI event filter...
```

```bash
git commit -m "<PR title> (#<PR number>)" -m "<PR body>"
```

**Note:** If the PR body is very long, it's fine to include it all — git
handles long commit messages gracefully.

### 9. Push, Mark Merged, and Clean Up

**Order matters.** The remote branch must still exist when marking the PR
as merged, otherwise Forgejo returns 404/409.

```bash
# 1. Push the squash commit to main
git push origin main

# 2. Mark the PR as manually-merged on the forge (BEFORE deleting branch)
```

#### GitHub

```bash
# gh recognizes squash-merged PRs automatically when main is pushed.
# No extra step needed — GitHub auto-closes the PR as merged.
```

#### Forgejo

```bash
# Get the full SHA of the squash-merge commit
MERGE_SHA=$(git rev-parse HEAD)

# Mark as manually-merged — branch must still exist on remote
# {owner} and {repo} are auto-resolved by tea; replace {index} with the PR number
tea api -X POST "/repos/{owner}/{repo}/pulls/{index}/merge" \
  -f "Do=manually-merged" \
  -f "merge_commit_id=$MERGE_SHA"

# Verify it took
# {owner} and {repo} are auto-resolved by tea; replace {index} with the PR number
tea api "/repos/{owner}/{repo}/pulls/{index}" | jq '{state, merged}'
# Expected: {"state": "closed", "merged": true}
```

**IMPORTANT**: `tea` does NOT have a `pr merge` subcommand that supports
`manually-merged`. Use `tea api` as shown above.

```bash
# 3. NOW delete the branch (after PR is marked merged)
git branch -D "$branch"
git push origin --delete "$branch"

# 4. Prune stale remote tracking refs
git fetch --prune origin
```

Report:

```
Squash-merged "$branch" into main as <short-sha>.
PR #<number> marked as merged. Pushed main, deleted branch.
```

---

## Hard Rules

| Rule | Rationale |
|------|-----------|
| ALWAYS `--squash` | Clean linear history on main |
| NEVER regular merge into main | No merge commits cluttering history |
| ALWAYS push + mark merged + clean up | Complete the workflow end-to-end |
| Mark PR merged BEFORE deleting branch | Forgejo needs the branch to exist for manually-merged |
| ALWAYS look for PR first | PR descriptions are the source of truth |
| ABORT on conflicts | Don't try to resolve automatically |
| ABORT on dirty worktree | Prevent accidental data loss |

---

## Edge Cases

| Situation | Action |
|-----------|--------|
| Already on main | Error: "Switch to the feature branch first, or pass branch name" |
| Branch doesn't exist | Error: "Branch '$branch' not found" |
| No remote | Skip PR lookup, ask for manual commit message |
| Multiple PRs for branch | Use the most recent one |
| PR is still open | Proceed — step 9 will mark it merged on the forge |
| Branch has no commits ahead of main | Warn: "Nothing to merge — branch is up to date with main" |
