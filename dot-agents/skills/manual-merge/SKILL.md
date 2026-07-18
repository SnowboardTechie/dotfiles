---
name: manual-merge
description: Use when an approved, CI-green Forgejo or Codeberg PR must be squash-merged locally to preserve commit signatures.
version: 2.0.0
author: Bryan Thompson
license: MIT
metadata:
  hermes:
    tags: [git, forgejo, codeberg, squash-merge, signed-commits]
    related_skills: [ship, worktrunk, pr-self-review]
---

# Manual Local Squash Merge

## Overview

Squash an approved PR onto the default branch locally, create the signed commit
from the PR title/body, push the default branch, and mark the Forgejo PR as
manually merged. This is Bryan's sanctioned merge path for Forgejo/Codeberg,
where server-side merging may re-sign or invalidate commit signatures.

This is a significant, externally visible operation. Never treat implementation
approval as merge approval.

## When to Use

- The origin is Forgejo, Gitea, or Codeberg.
- The PR has completed human review and all required CI checks are green.
- Local squash merge is required to preserve the expected signature.

Do not use to bypass review, CI, branch protection, or an unresolved discussion.
Do not run two merges against the same base concurrently.

## Procedure

### 1. Resolve the branch, repository, and PR

Load `ship/references/forge-detection.md` and use its parser. Resolve the target
branch from the argument or current branch. Abort if it is the default branch,
does not exist, or has no commits ahead of the default branch.

Fetch the open PR with authenticated `tea api`. If Tea cannot read the current
repository because of `extensions.worktreeconfig`, run it from a temporary
initialized repository and pass `--login` and `--repo` explicitly, as documented
by `ship`.

No matching open PR means stop. A manual commit message is not a substitute for
the reviewed PR record in this workflow.

### 2. Enforce the merge gate

Read back the PR and its current checks immediately before merging. Verify:

- PR is open and not a draft;
- required human review is present;
- no unresolved review request or blocking conversation remains;
- every required CI check is green;
- head SHA matches the branch SHA being merged;
- base branch is the repository's default branch;
- active project instructions' completion requirements are satisfied: required
  tracked spec, plan, status, or decision updates are included in the reviewed
  PR, or a concrete no-update rationale identifies what was inspected and why
  no change is needed.

If the forge cannot expose one of these facts, show the missing fact and ask the
user to verify it. Never infer approval from silence.

### 3. Present the exact operation for approval

Show:

- clickable PR link and title;
- head SHA and target default branch;
- review/CI evidence;
- planning-closeout evidence from the project instructions;
- squash commit subject;
- planned push, manual-merge API call, and branch cleanup.

Obtain explicit approval immediately before changing the default branch. One
approval may cover the complete listed sequence, including cleanup.

### 4. Prepare the default-branch worktree

The default branch may already be checked out in another Worktrunk worktree.
Use `git worktree list --porcelain` to find that path instead of blindly running
`git switch` in the feature worktree.

In the default-branch worktree:

```bash
git status --porcelain
git fetch origin <default-branch>
git rev-parse <default-branch>
git rev-parse origin/<default-branch>
```

Abort unless the worktree is clean and local default exactly matches origin.
Record the rollback point:

```bash
pre_merge_head=$(git rev-parse HEAD)
```

### 5. Squash and commit

```bash
git merge --squash <feature-branch>
```

If the squash reports conflicts, roll back only the merge attempt:

```bash
git reset --merge "$pre_merge_head"
```

Then verify `git status --porcelain` is empty and `HEAD` still equals
`$pre_merge_head`. If either check fails, stop and ask the user how to proceed;
do not escalate to `git reset --hard` automatically.

On success, inspect the staged diff before committing. Use the reviewed PR title
and body:

```text
<PR title> (#<PR number>)

<PR body>
```

Never add AI attribution. Create the signed commit according to repository git
configuration, then verify the signature locally.

### 6. Push and mark manually merged

Push the default branch first:

```bash
git push origin <default-branch>
```

Verify the remote now points at the new commit. While the feature branch still
exists remotely, mark the PR manually merged:

```bash
MERGE_SHA=$(git rev-parse HEAD)
tea api \
  --login <configured-login> \
  --repo <owner/repo> \
  -X POST \
  -f Do=manually-merged \
  -f MergeCommitID="$MERGE_SHA" \
  /repos/<owner>/<repo>/pulls/<number>/merge
```

Use the exact case-sensitive Forgejo field `MergeCommitID`. The snake-case
`merge_commit_id` field may return HTTP 200 with `{}` while leaving the PR open;
that is not success. Always enforce the read-back gate below.

Run this from the same safe Tea context used for lookup. Read the PR back and
require `state: closed`, `merged: true`, and the expected merge SHA before any
branch deletion.

### 7. Clean up

Only after the forge record is correct:

```bash
git push origin --delete <feature-branch>
git branch -d <feature-branch>
git fetch --prune origin
```

Use `-d`, not `-D`. If Git refuses because squash merges are not recognized as
ancestry, report that and leave the local branch in place unless the user
explicitly approves forced deletion.

Report the clickable PR URL, pushed commit SHA, signature result, forge merge
state, and any retained worktree/branch.

## Common Pitfalls

1. **Merging an open draft or unreviewed PR.** The carve-out is a merge
   mechanism, not a review bypass.
2. **Running against a stale default branch.** Local and origin must match
   exactly before the squash.
3. **Using `git merge --abort` after `--squash`.** A squash conflict may have no
   `MERGE_HEAD`; restore with the recorded commit and verify the result.
4. **Deleting the branch before the API call.** Forgejo may reject the manual
   merge record after branch deletion.
5. **Forcing branch deletion automatically.** Keep it when safe deletion fails.
6. **Parallel base-branch merges.** Serialize them; concurrent pushes can leave
   a false forge merge record.

## Verification Checklist

- [ ] Human review confirmed
- [ ] Required CI green at the current head SHA
- [ ] Project planning-closeout requirements satisfied
- [ ] Explicit merge approval obtained
- [ ] Default worktree clean and synchronized with origin
- [ ] Squash diff inspected before commit
- [ ] Commit signature verified
- [ ] Remote default branch verified after push
- [ ] PR read back as manually merged with expected SHA
- [ ] Remote branch deleted only after merge record succeeded
- [ ] Local branch/worktree cleanup reported accurately
