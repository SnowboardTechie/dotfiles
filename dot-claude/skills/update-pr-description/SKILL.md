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

Determine which forge hosts this repo:

```bash
remote_url=$(git remote get-url origin 2>/dev/null)
if [[ "$remote_url" == *"github.com"* ]]; then
  forge="github"
elif [[ "$remote_url" == *"forgejo"* || "$remote_url" == *"gitea"* || "$remote_url" == *"codeberg"* || "$remote_url" == *"snowboardtechie"* ]]; then
  forge="forgejo"
else
  forge="unknown"
fi
```

### Forgejo: URL Parsing

`tea api` auto-resolves `{owner}` and `{repo}` placeholders from the local
git remote, so manual URL parsing is rarely needed. Just ensure `tea` is
logged in (`tea login list`).

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
tea api "/repos/{owner}/{repo}/pulls?state=open" \
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
# Get PR metadata including current description
# {owner} and {repo} are auto-resolved by tea; replace {index} with the PR number
tea api "/repos/{owner}/{repo}/pulls/{index}" \
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

Using the diff to understand what changed:

1. **Follow the template's own instructions** (delete what it says to delete)
2. **Fill in all sections** based on the actual changes
3. **Check relevant boxes** with `[x]` or add justifications like `_N/A - reason_`
4. **Be specific and factual** - use the diff to inform your answers
5. **Link to issues** if you find issue numbers in branch name, commits, or original body

---

## Step 5: Update the PR

**GitHub:**

```bash
gh pr edit {number} --body "$(cat <<'EOF'
{generated description}
EOF
)"
```

**Forgejo:**

Use `tea api` with `-X PATCH` and `-f` for string fields.
`{owner}` and `{repo}` are auto-resolved from the local repo context.
Replace `{index}` with the actual PR number.

```bash
# Update body only
tea api -X PATCH "/repos/{owner}/{repo}/pulls/{index}" \
  -f "body={generated description}"

# Update both title and body
tea api -X PATCH "/repos/{owner}/{repo}/pulls/{index}" \
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
