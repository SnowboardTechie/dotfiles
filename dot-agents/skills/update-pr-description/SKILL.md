---
name: update-pr-description
description: Update PR description following template instructions and including diff summary
argument-hint: <pr-number-or-url>
---

# Update PR Description

Update a pull request description by following whatever template instructions exist in the PR body and including a summary of changes from the diff. Supports both GitHub and Forgejo forges.

---

## Input

Accepts either:

- PR number: `update-pr-description 42170`
- PR URL: `update-pr-description https://github.com/org/repo/pull/42170`
- PR URL (Forgejo): `update-pr-description https://git.example.com/owner/repo/pulls/1`
- Nothing (will detect PR from current branch)

---

## Step 0: Detect Forge

Determine which forge hosts this repo via the shared [forge-detection reference](../ship/references/forge-detection.md) — it sets `forge` to `github`, `forgejo`, or `unknown`. On `unknown`, error out with the supported-forge list (see the "Forge not detected" error below).

### Forgejo: URL Parsing

Use the host and `owner_repo` returned by the shared parser. Run authenticated
`tea api` with explicit `--login` and `--repo` values. If Tea cannot read the
current checkout because of `extensions.worktreeconfig`, use the temporary
initialized-repository pattern documented by `ship`; do not fall back to token
scraping.

If a PR URL is provided (e.g. `https://codeberg.org/owner/repo/pulls/1`),
extract the PR index from path segment 4.

---

## Step 1: Identify the PR

### If PR number/URL provided:

Parse the input to extract the PR number and repo (if URL provided).

### If no argument provided:

**GitHub:**

```bash
BRANCH=$(git branch --show-current)
gh pr list --head "$BRANCH" --json number,title,url,body --limit 1
```

**Forgejo:**

```bash
BRANCH=$(git branch --show-current)
tea api --login {login} --repo {owner/repo} \
  "/repos/{owner}/{repo}/pulls?state=open" \
  | jq -c --arg branch "$BRANCH" '.[] | select(.head.ref == $branch) | {number: .number, title: .title, url: .html_url, body: .body}' \
  | head -1
```

---

## Step 2: Fetch PR Details and Diff

**GitHub:**

```bash
gh pr view {number} \
  --repo {org}/{repo} \
  --json number,title,url,body,baseRefName

git diff {baseRefName}...HEAD --stat
git diff {baseRefName}...HEAD
```

**Forgejo:**

```bash
# Run from a Tea-safe context; replace placeholders with parsed values.
tea api --login {login} --repo {owner/repo} \
  "/repos/{owner}/{repo}/pulls/{index}" \
  | jq '{number: .number, title: .title, url: .html_url, body: .body, baseRefName: .base.ref}'

# Get the diff (same git commands for both forges)
git diff {baseRefName}...HEAD --stat
git diff {baseRefName}...HEAD
```

---

## Step 3: Read the Template

The PR body contains the repository's template. Read it carefully:

1. **Look for instructions** at the top (often says to delete placeholder text)
2. **Identify sections** (Summary, Testing, Related Issues, etc.)
3. **Find placeholders** - usually in italics, parentheses, or marked as `_(placeholder)_`
4. **Note checkboxes** - which need to be filled `[x]` or justified

**Follow whatever instructions the template provides.**

---

## Step 4: Generate Updated Description

Fill the template (read from the PR body in Step 3) following the shared fill discipline in [../ship/references/pr-body-fill.md](../ship/references/pr-body-fill.md) — follow the template's own instructions, strip `>` / `<!-- -->` / placeholder text, fill every section with no empties, check/justify boxes (`[x]` or `_N/A - reason_`), and link issues from the branch name / commits / original body.

The **source material** here is the diff from Step 2 — this skill has no summary artifact, so drive every section factually from the diff.

Do not add AI attribution, generated-by notices, or `Co-authored-by` text. Preserve factual issue links and the repository template exactly.

### Step 4.5: Approval gate

Updating a PR body is public communication. Present the complete generated description inline and ask for explicit approval using interactive clarification (Hermes: `clarify`) or the host's conversational equivalent. Iterate on requested edits and re-present. **Do not call `gh pr edit`, `tea api`, or the Forgejo REST API until the user approves the exact body.** Silence and ambiguity are not approval. In unattended runs, write/report the proposed body and stop without mutating the PR.

---

## Step 5: Update the PR

Proceed only after Step 4.5 approval.

**GitHub:**

```bash
gh pr edit {number} --body "$(cat <<'EOF'
{generated description}
EOF
)"
```

**Forgejo:**

Use `tea api` with explicit login/repository context, `-X PATCH`, and `-f`
for string fields. Replace `{index}` with the actual PR number.

```bash
# Update body only
tea api --login {login} --repo {owner/repo} -X PATCH "/repos/{owner}/{repo}/pulls/{index}" \
  -f "body={generated description}"

# Update both title and body
tea api --login {login} --repo {owner/repo} -X PATCH "/repos/{owner}/{repo}/pulls/{index}" \
  -f "title={new title}" \
  -f "body={generated description}"
```

**IMPORTANT**: `tea` does NOT have a `pr edit` subcommand. `tea api` is
the correct way to update PR title/body on Forgejo. Do NOT attempt
`tea pr edit` — it does not exist.

---

## Step 6: Confirm Completion

Report:

```
Updated PR #{number}: {title}
   {url}
```

---

## Error Handling

### PR not found

```
Could not find PR #{number}
   Verify the PR exists and you have access.
```

### Cannot determine current PR

```
No PR found for current branch: {branch}
   Please provide a PR number: update-pr-description <number>
```

### Forge not detected

```
Could not detect forge from remote URL: {remote_url}
   Supported forges: GitHub (github.com), Forgejo/Gitea/Codeberg (forgejo/gitea/codeberg/snowboardtechie in URL)
```

### tea not authenticated (Forgejo)

```
tea CLI not authenticated. Run: tea login add
   Or set FORGEJO_TOKEN environment variable.
```

---

## Related

Three skills touch a PR; they don't overlap:

- `ship` — fills the description **at creation** (and refuses if a PR already exists). Create-time only.
- `update-pr-description` (this skill) — re-syncs an **existing** PR's body to its current diff + template, on demand. The only tool for updating a PR body after it's opened.
- `pr-self-review` — reviews a PR and writes `summary.md`; it pushes fix commits but never edits the PR body.

No superpowers/GSD delegation — this is a forge-API utility, not a dev-lifecycle skill.
