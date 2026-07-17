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

Push the current branch, open a **draft** pull request, fill the repository's PR
template, apply justified labels, and report the clickable URL. This skill does
not merge or declare the branch review-ready.

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
- no open PR already exists for the branch.

### 2. Verify the branch

Inspect `git status`, the branch diff, and the repository's own instructions.
Run the relevant test, lint, typecheck, and formatting gates. In Hermes, use the
installed verification/review skills where applicable; in another agent, use
its equivalent verification workflow.

If a caller supplies an already-current verification artifact, inspect it and
avoid rerunning unchanged expensive gates. Any failed or missing required gate
blocks publication.

### 3. Draft the PR body

Find the repository's PR template in the standard locations. Fill it using
`references/pr-body-fill.md`.

Source priority:

1. A current issue-work summary, approved plan, or review artifact.
2. Commit history and `git diff <default>...HEAD`.

Preserve every template section. Replace placeholders, justify checkbox
selections, use `N/A` only when genuinely inapplicable, and preserve clickable
issue/PR links. Never add AI attribution.

Choose only labels supported by the repository and justified by the diff. Do
not apply speculative labels merely because they are inexpensive.

### 4. Obtain publication approval

Show the user the proposed title, complete body, base/head branches, and labels.
Ask for approval immediately before the push/API calls unless the user already
explicitly approved publishing this exact PR in the current task.

A request to implement or review code is not approval to publish it.

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

### 6. Create the draft PR

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

### 7. Apply approved labels and verify

Use `gh pr edit --add-label` on GitHub or authenticated `tea api` requests on
Forgejo. Then fetch the PR again and verify:

- draft state is true;
- title, base, head, body, and labels match the approved proposal;
- the returned URL is on the expected forge and repository.

Report the PR as a Markdown link.

## Common Pitfalls

1. **Using `gh pr create --fill` without the template.** Draft the body from the
   repository template explicitly.
2. **Extracting Tea tokens with `grep`.** Use `tea api`; credentials must never
   enter command output or generated artifacts.
3. **Publishing before approval.** Present the exact public content first.
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
- [ ] Existing PR check completed
- [ ] Repository template fully populated
- [ ] Exact public content approved
- [ ] Pushed branch SHA matches local HEAD
- [ ] PR created as draft and read back successfully
- [ ] Labels are supported and justified
- [ ] Clickable PR URL reported
