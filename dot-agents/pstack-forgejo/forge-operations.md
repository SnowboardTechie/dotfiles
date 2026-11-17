# pstack's pull request steps on Forgejo

Read this when a pstack playbook (opening-a-pr, babysit, shipping, autopilot-full,
autopilot-stack, orchestrate, multi-phase-plan) names a `gh pr` or `gh api`
command and the origin is Forgejo. It gives the Forgejo command and how to read
the result back. Detect the forge with `ship/references/forge-detection.md`.

Checked against Forgejo 16.0.6 and tea 0.16.0 on 2026-11-16. **Verified** means
the command ran against a real pull request and returned what is described.
**Unverified** means it is a write: it was not run against a real pull request,
and the command comes from the `ship` or `manual-merge` skill or Forgejo's API
schema. Read every write back before relying on it.

## Setup

```bash
LOGIN=<tea login>    # tea logins list -o json; the entry whose url host is the origin's
REPO=<owner>/<repo>  # from ship's parse-forge-remote.sh
cd "$(mktemp -d)"    # run tea outside the checkout, as ship does
```

`tea api` prints a Forgejo error body (`{"message": ...}`) with exit 0, so check
the JSON, not the exit code. Never print the token from tea's config.

## Create

`gh pr create --base <base>` (ready; pstack opens every PR ready):

```bash
tea pulls create --login "$LOGIN" --repo "$REPO" \
  --head <branch> --base <base> --title "<title>" --description-file <body-file>
```

Draft: add `--draft`, which prefixes the title with `WIP: `. A Forgejo draft
*is* that prefix. Forgejo 16's create schema has no `draft` field, so a
`"draft": true` in a `tea api` payload (as `ship` sends) is ignored; only the
title decides. A stack child passes the parent's branch as `--base`.
The ready form is **verified** (with `--description "$(cat <body-file>)"`); `--draft`
and a non-default `--base` are **unverified**.

Read back with the view below: `draft` matches what you asked for, `base.ref`
and `head.ref` are right, and no second open PR exists for the branch.

## View

`gh pr view <n> --json state,isDraft,mergedAt,baseRefName,headRefOid`:

```bash
tea api --login "$LOGIN" /repos/$REPO/pulls/<n> | jq '{number, state, draft, merged,
  merged_at, merge_commit_sha, mergeable, title, base: .base.ref, head: .head.ref,
  head_sha: .head.sha, base_sha: .base.sha, html_url}'
```

**Verified.** `state` is `open` or `closed`, and a merged PR is `closed` with
`merged: true`. `draft` follows the `WIP: ` prefix. `mergeable` is `false` on a
draft and while Forgejo is still checking, so it is not a conflict signal;
`watch-pr-forgejo` confirms conflicts with `git merge-tree`.

The PR for a branch (`gh pr view` with no number):

```bash
tea pulls list --login "$LOGIN" --repo "$REPO" --state open \
  --fields index,title,head,base -o json | jq '.[] | select(.head == "<branch>")'
```

**Verified.** `tea pulls <n> --login "$LOGIN" --repo "$REPO" -o json` also
works (fields `index`, `headSha`, `hasMerged`, `mergeable`, `base`, `head`),
**verified**, but the API form above carries `draft` and `merge_commit_sha`.

## Edit title, body, base

`gh pr edit <n> --title/--body-file/--base`:

```bash
jq -n --arg title "<title>" --rawfile body <body-file> --arg base <base> \
  '{title: $title, body: $body, base: $base}' > edit.json
tea api --login "$LOGIN" --repo "$REPO" -X PATCH --data @edit.json /repos/$REPO/pulls/<n>
```

Send only the fields you change. Keep an existing `WIP: ` prefix in a title
edit unless you mean to mark the PR ready. Title and body are **verified**; `base` is
**unverified**. Read back `title`, `body` and `base.ref`.

## Mark ready

`gh pr ready <n>`:

```bash
tea pulls edit <n> --login "$LOGIN" --repo "$REPO" --ready
# or, as manual-merge does:
tea api --login "$LOGIN" --repo "$REPO" -X PATCH -f title="<title without WIP: >" /repos/$REPO/pulls/<n>
```

`--ready` strips a leading `WIP: ` or `[WIP]` (**unverified**). The PATCH form is
**verified**: `draft` went to `false` and `mergeable` to `true`. Read back
`draft: false` and a title with no prefix.

## Checks

`gh pr checks <n>` and pstack's `watch-pr`: run `watch-pr-forgejo` (beside this
file) from the repository's checkout, after `git fetch origin`. It takes
`watch-pr`'s options and gives its verdicts.

```bash
watch-pr-forgejo --pr <n> --status-only --pretty   # one table, then exit
watch-pr-forgejo --pr <n>                          # poll until READY or BLOCKER
```

**Verified** on a draft, and on an open pull request whose CI was running: it
reported `WAITING` with the pending check, then `READY` when the check passed.
`--status-only` exits 0 with a table (CI, review, merge); exit 0 means it was
read, not that the PR is ready. Without
`--allow-draft` a draft blocks the merge. It looks in `$PI_CODING_AGENT_DIR`,
`~/.pi/pstack` and `~/.pi/agent`; set `PSTACK_WATCH_PR_DIR` when pstack is
elsewhere.

Where a repository's CI reports commit statuses, the watcher reads them as its
checks, and `READY` is reachable. Most of Bryan's repositories report none: CI
then reads "no checks reported yet" and polling ends in `TIMEOUT`, never
`READY`. In a repository that reports none, the required check is the
repository's full local test run on the exact head, as `manual-merge` says. Check
with `tea api --login "$LOGIN" /repos/$REPO/commits/<sha>/status`:
`total_count: 0` means none.

## Review comments

List (`gh api .../pulls/<n>/comments`, or the watcher's threads):

```bash
tea pulls review-comments <n> --login "$LOGIN" --repo "$REPO" -o json
# fields: id, path, line, body, reviewer, resolver, created, updated, url
```

**Verified** only as an empty list: no PR on Bryan's Forgejo has a review
comment yet. The API form is
`tea api --login "$LOGIN" /repos/$REPO/pulls/<n>/reviews` (verified, `[]`), then
`.../reviews/<review-id>/comments` for each review with `comments_count > 0`.

Forgejo has no thread object. A conversation is the review comments at one
`path` and position. Forgejo 16's API has no resolve or reply endpoint: tea
0.16's `pulls resolve` and `pulls reply` call routes that return "The target
couldn't be found", and neither is in its API schema (**verified**). Resolving is the web UI's Resolve button, so
an agent never resolves. "Resolved" means the conversation's first comment has a
`resolver`; that is what the button sets and what the web UI shows. Fix or
disprove the finding, reply, and report the conversation as waiting for Bryan to
resolve it.

`watch-pr-forgejo` reads a conversation as resolved the same way: its first
comment has a `resolver`. Forgejo 16.0.6's Resolve button sends the first
comment's ID, and `MarkConversation` in `models/issues/review.go` sets the
resolver on that comment only, so replies never carry one (read from the
source).

Reply (`gh api --method POST .../comments/<id>/replies`): post a comment review
at the same path and line, so it joins that conversation. Keep the reply in a
file and build the payload with `jq`, never with the comment text in the shell
command:

```bash
jq -n --rawfile body <reply-file> --arg path <path> --argjson line <new-line> \
  '{event: "COMMENT", body: "", comments: [{path: $path, new_position: $line, body: $body}]}' > reply.json
tea api --login "$LOGIN" --repo "$REPO" -X POST --data @reply.json /repos/$REPO/pulls/<n>/reviews
```

**Unverified.** Read back the review comments and find yours at that `path` and
line. For a reply that is not about a line, comment on the PR with
`jq -n --rawfile body <reply-file> '{body: $body}'` as the payload, posted to
`/repos/$REPO/issues/<n>/comments`, also **unverified**.

## Merge

There is no Forgejo form of `gh pr merge`. Never merge on the server: no
`tea pulls merge`, no `POST .../pulls/<n>/merge` with any `Do` other than
`manually-merged`, and no auto-merge. A server-side merge breaks Bryan's commit
signatures.

The merge is the `manual-merge` skill: a signed local squash onto the default
branch, a push, then recording the PR as manually merged. Run it only under a
recorded standing merge authority (an approved plan that grants "merge once
cleared" and names the checks that replace Bryan's review), or with Bryan's
explicit approval of that merge. Without one, stop at merge-ready and report.
Forgejo has no server-side head condition like `--match-head-commit`;
`manual-merge` compares the PR's `head.sha` with the branch it squashes, right
before it squashes. Merge one PR at a time per base.

The record step, from `manual-merge` (**verified**: the PR read back `closed`,
`merged: true`, with the pushed commit):

```bash
tea api --login "$LOGIN" --repo "$REPO" -X POST \
  -f Do=manually-merged -f MergeCommitID="$MERGE_SHA" /repos/$REPO/pulls/<n>/merge
```

Read back with the view above: `state: closed`, `merged: true`,
`merge_commit_sha` equal to the pushed commit (**verified** on merged PRs), and
`git merge-base --is-ancestor <merge_commit_sha> origin/<default>` after a fetch
(**verified**).

## Stacks

A child PR's base is the parent's branch. When the parent merges, find its
children:

```bash
tea api --login "$LOGIN" "/repos/$REPO/pulls?state=open&limit=50" \
  | jq '.[] | select(.base.ref == "<parent-branch>") | .number'
```

**Verified** (with `main` as the branch). Retarget each child to the default
branch, before replaying its commits as pstack's shipping playbook says:

```bash
tea api --login "$LOGIN" --repo "$REPO" -X PATCH -f base=<default-branch> /repos/$REPO/pulls/<child>
```

**Unverified.** Read back `base.ref`. Forgejo does not retarget children by
itself; until this runs, the child still targets the merged branch.
