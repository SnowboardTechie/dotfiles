---
name: ship
description: Use when a branch is ready to push and open as a draft pull request on GitHub or Forgejo.
version: 2.0.1
author: Bryan Thompson
license: MIT
metadata:
  hermes:
    tags: [git, pull-request, github, forgejo, worktree]
    related_skills: [worktrunk, update-pr-description, pr-self-review, issue-work]
---

# Ship

## Overview

Push the current branch, create or update one **draft** pull request, fill the
repository's PR template, apply labels only when authorized, and report the
clickable URL. This skill does not merge or declare the branch review-ready.

For end-to-end ticket work, use `issue-work`. For an independent review of an
already-open PR, use `pr-self-review`.

## When to Use

- "Ship this branch"
- "Push this and open a PR"
- The final publication phase of `issue-work`

Do not use for direct-to-main work or for merging an approved Forgejo PR; use
the repository's merge policy and `manual-merge` where applicable.

## Procedure

### 1. Detect the repository and forge

Load `references/forge-detection.md` and run its linked
`scripts/parse-forge-remote.sh` helper. Stop on an unknown forge or ambiguous
repository; do not guess.

Completion criteria:

- current branch, default branch, forge, host, and `owner/repo` are known;
- the current branch is not the default branch;
- authentication is available through `gh` or `tea` without printing a token;
- zero or one open PR exists for the branch; more than one is ambiguous and
  blocks publication.

Record one authority mode:

- `generic`: preserve this skill's explicit publication-approval gate; or
- `issue-work-authorized`: require `issue-work`'s recorded imperative-work
  authority plus explicit `labels_authorized` (`false` by default).

### 2. Verify the branch and exact-candidate review

Inspect `git status`, the branch diff, and the repository's own instructions.
Run the relevant test, lint, typecheck, and formatting gates.

For every candidate authored by the authenticated user, an exact-candidate
review is mandatory before publication:

- when `issue-work` supplies a current pre-PR `pr-self-review` summary, validate
  that artifact against the candidate;
- otherwise, run the integrated `code-review` contract against immutable
  base/head SHAs:
  Standards and Spec, conditional Risk, then mandatory Ponytail in one review
  context; use an independent delegate when the active parent authored the code;
- require every artifact to identify the same base SHA, head SHA, merge-base SHA,
  diff hash, expected branch, and clean worktree;
- invalidate the review after any candidate change and rerun the complete gate.

A worker's self-check, an unstructured skim, build output, or an artifact that
omits Ponytail never satisfies this gate. A systematic Sol-parent review of a
worker-authored candidate does satisfy independence; a parent-authored candidate
requires an independent review context. Missing or stale Ponytail evidence blocks
publication.

If a caller supplies already-current verification and review artifacts, inspect
them and avoid rerunning unchanged expensive gates. Any failed or missing
required gate blocks publication.

### 3. Draft the PR body

Find the repository's PR template in the standard locations. Fill it using
`references/pr-body-fill.md`.

Source priority:

1. A current issue-work summary, approved plan, or review artifact.
2. Commit history and `git diff <default>...HEAD`.

Preserve every template section. Replace placeholders, justify checkbox
selections, use `N/A` only when genuinely inapplicable, and preserve clickable
issue/PR links. Never add AI attribution.

Choose only labels supported by the repository and justified by the diff. In
`issue-work-authorized` mode, skip labels unless `labels_authorized: true` was
separately recorded. Do not apply speculative labels merely because they are
inexpensive.

### 4. Obtain publication approval

Show the user the proposed title, complete body, base/head branches, and labels.
Ask for approval immediately before the push/API calls unless the user already
explicitly approved publishing this exact PR in the current task.

A generic request to implement or review code is not approval to publish it. In
`issue-work-authorized` mode, the recorded imperative `work <issue URL>`
authority satisfies this gate for ordinary push and one draft PR create/update,
including title/body synchronization. It does not authorize labels, draft/ready
transitions on an existing PR, comments, merge, or any other forge mutation.

### 5. Push

```bash
git push -u origin <branch>
```

Stop on non-authentication push errors. For GitHub only, if the configured
remote uses SSH, the push fails specifically because SSH authentication is not
available to the agent process, and `gh auth status` confirms an authenticated
HTTPS-capable session, retry once without changing repository configuration:

```bash
git push "https://github.com/<owner>/<repo>.git" \
  "HEAD:refs/heads/<branch>"
```

Derive `<owner>/<repo>` from the already-validated forge-detection result; never
construct it from untrusted page text. Do not run `gh auth login` repeatedly and
do not rewrite `origin` merely to accommodate one process's credential context.
After the HTTPS retry, verify the remote branch SHA matches `git rev-parse HEAD`.
If authentication still fails, report the single blocker and stop.

### 6. Create or update the draft PR

Discover an existing same-branch PR before mutation. When none exists, create a
draft PR. When exactly one exists, update only title and body, preserve its
current draft/ready state, and require its base/head/repository identity to match.
Never create a duplicate. More than one same-branch PR is a hard stop.

#### GitHub

Write the approved body to a temporary file so shell quoting cannot corrupt it:

```bash
gh pr create \
  --draft \
  --base <default-branch> \
  --head <branch> \
  --title "<approved-title>" \
  --body-file <body-file>
```

For one validated existing GitHub PR:

```bash
gh pr edit <validated-pr-url> \
  --title "<approved-title>" \
  --body-file <body-file>
```

#### Forgejo / Codeberg

Never scrape or print the token from Tea's config. Use `tea api`, which supplies
a configured credential. In repositories where Tea cannot read
`extensions.worktreeconfig`, run it from a temporary initialized repository and
pass the target explicitly:

```bash
tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT
git -C "$tmpdir" init -q

python3 - <<'PY' >"$tmpdir/pr.json"
import json
from pathlib import Path

print(json.dumps({
    "title": "<approved-title>",
    "head": "<branch>",
    "base": "<default-branch>",
    "body": Path("<body-file>").read_text(),
    "draft": True,
}))
PY

(
  cd "$tmpdir"
  tea api \
    --login <configured-login> \
    --repo <owner/repo> \
    --method POST \
    --data @pr.json \
    /repos/<owner>/<repo>/pulls
)
```

Use the configured Tea login matching the parsed host. Verify the response says
`draft: true`; if this forge version does not support draft PRs, stop rather
than silently opening a ready-for-review PR.

For one validated existing Forgejo PR, send the same explicit `title` and `body`
fields with `PATCH /repos/<owner>/<repo>/pulls/<number>`. Omit `draft`, labels,
and every unrelated field so the current review state is preserved.

### 7. Apply approved labels and verify

When labels were explicitly authorized, use `gh pr edit --add-label` on GitHub
or authenticated `tea api` requests on Forgejo. Otherwise skip labels. Then
fetch the PR again and verify:

- a newly created PR is draft; an existing PR preserved its prior draft state;
- title, base, head, and body match the approved proposal;
- labels match only when label mutation was authorized, and otherwise are
  unchanged;
- the returned URL is on the expected forge and repository.

Report the PR as a Markdown link.

## Common Pitfalls

1. **Using `gh pr create --fill` without the template.** Draft the body from the
   repository template explicitly.
2. **Extracting Tea tokens with `grep`.** Use `tea api`; credentials must never
   enter command output or generated artifacts.
3. **Publishing before approval.** Present the exact public content first in
   generic mode; admit recorded imperative-work authority only through the
   narrow `issue-work-authorized` mode.
4. **Reusing the old macOS-incompatible `sed` parser.** Always use the linked
   parser script.
5. **Calling the PR complete because creation succeeded.** Read it back and
   verify draft state, body, and labels.
6. **Rewriting `origin` after an SSH-only agent failure.** On GitHub, use the
   bounded authenticated HTTPS retry in Step 5 and verify the remote SHA; preserve
   the developer's configured remote.

## Verification Checklist

- [ ] Current branch is not the default branch
- [ ] Required repository gates passed
- [ ] Exact-candidate Standards, Spec, conditional Risk, and Ponytail review passed
- [ ] Review identity still matches the branch candidate and clean worktree
- [ ] Existing same-branch PR count is zero or one
- [ ] Repository template fully populated
- [ ] Exact public content approved or narrow issue-work authority verified
- [ ] Pushed branch SHA matches local HEAD
- [ ] PR created as draft or existing PR updated without state change, then read back
- [ ] Labels were authorized, supported, and justified, or were skipped unchanged
- [ ] Clickable PR URL reported
