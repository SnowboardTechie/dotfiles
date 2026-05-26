---
name: ship
description: Wrap up worktree work - push branch, open PR, fill description, report URL
---

# Ship - Worktree Wrap-Up

Push the current branch, open a PR, and fill the description.

Ships WIP as a draft PR by default — self-review and merge-readiness are not this skill's job. For end-to-end ticket work with self-review baked in, use [`/issue-work`](../issue-work/SKILL.md) instead; for a standalone review pass on a branch already shipped with `/ship`, run [`/pr-self-review`](../pr-self-review/SKILL.md) against the open PR.

---

## Quick Reference

```
/ship           # wrap up current branch — detect forge, push, open PR
```

---

## Execution

### 1. Detect Forge

```bash
remote_url=$(git remote get-url origin 2>/dev/null)
if [[ "$remote_url" == *"github.com"* ]]; then
  forge="github"
elif [[ "$remote_url" == *"forgejo"* || "$remote_url" == *"gitea"* || "$remote_url" == *"codeberg"* || "$remote_url" == *"snowboardtechie"* ]]; then
  forge="forgejo"
else
  echo "No supported forge detected — use wt merge instead"
  exit 1
fi
```

### 2. Pre-flight

- `git branch --show-current` must not be `main` or `master`
- `git remote -v` returns output
- Forge CLI authenticated: `gh auth status` (GitHub) or tea config file exists with token (Forgejo)
- No existing PR: `gh pr list --head <branch>` (GitHub) or Forgejo API `GET /repos/{owner}/{repo}/pulls?state=open` (Forgejo)

If any check fails, report what's wrong and stop.

### 3. Confirm

Ask: "Ready to push and open a draft PR?"

### 4. Push

```bash
git push -u origin <branch>
```

### 5. Create PR

#### GitHub

```bash
gh pr create --fill --draft
```

**Always open as draft.** Never use `--fill` without `--draft`.

#### Forgejo

**Never use `tea pr` commands.** They require TTY interaction and will fail in agent environments. Always use the Forgejo API directly:

```bash
# 1. Extract token from tea config
TEA_CONFIG=""
for candidate in \
  "${XDG_CONFIG_HOME:-$HOME/.config}/tea/config.yml" \
  "$HOME/Library/Application Support/tea/config.yml" \
  "$HOME/.tea/tea.yml"; do
  [ -f "$candidate" ] && TEA_CONFIG="$candidate" && break
done

# 2. Parse token (requires PyYAML or grep)
TOKEN=$(grep 'token:' "$TEA_CONFIG" | head -1 | awk '{print $2}')

# 3. Parse owner/repo from remote
remote_url=$(git remote get-url origin)
# SSH: ssh://forgejo@git.example.com/owner/repo.git → owner/repo
# HTTPS: https://git.example.com/owner/repo.git → owner/repo
owner_repo=$(echo "$remote_url" | sed -E 's|.*[:/]([^/]+/[^/]+?)(\.git)?$|\1|')
instance=$(echo "$remote_url" | sed -E 's|.*(@\|//)([^:/]+).*|https://\2|')

# 4. Create PR via API
curl -s -X POST "${instance}/api/v1/repos/${owner_repo}/pulls" \
  -H "Authorization: token $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"<PR title>\",\"head\":\"<branch>\",\"base\":\"main\",\"body\":\"<description>\",\"draft\":true}"
```

Extract the PR number and URL from the JSON response:
```bash
| python3 -c "import sys,json; d=json.load(sys.stdin); print(f'PR #{d[\"number\"]}: {d[\"html_url\"]}')"
```

### 6. Fill Description

**Check for a PR template first:**

```bash
# Look for PR template (GitHub supports both casings and locations)
template=""
for candidate in \
  ".github/pull_request_template.md" \
  ".github/PULL_REQUEST_TEMPLATE.md" \
  ".github/PULL_REQUEST_TEMPLATE/pull_request_template.md" \
  "pull_request_template.md"; do
  [ -f "$candidate" ] && template="$candidate" && break
done
```

**Source-of-truth priority when filling sections:**

1. If the invoker passes a **review / summary artifact** (e.g., `issue-work` hands off its `~/.claude/issue-work/{owner}-{repo}-{N}/summary.md`, or the user cites a plan document) — read it first and use its findings + rationale as the authoritative source for Summary, Test-plan, and any other narrative sections. The artifact is *why* this PR exists; the diff is *what*.
2. Otherwise, derive from the commit history + diff.

**If a template exists:** Read it and use its sections as the structure for the PR body. Fill each section with relevant content per the priority above. Strip instruction/placeholder text before posting — templates commonly use either `> ` blockquotes or `<!-- ... -->` HTML comments (this repo's `.github/PULL_REQUEST_TEMPLATE.md` uses the HTML-comment style), so remove both. Do not leave empty sections — write `N/A` if a section doesn't apply.

**If no template exists:** Write a comprehensive PR description covering:
- Summary of changes (what and why)
- Key features/files added or modified
- Testing (test counts, what was verified)
- Commit list

Then update via the API:
```bash
# GitHub
gh pr edit {number} --body "$BODY"

# Forgejo (always use API)
body_json=$(python3 -c "import json,sys; print(json.dumps({'body': sys.stdin.read()}))" <<< "$BODY")
curl -s -X PATCH "${instance}/api/v1/repos/${owner_repo}/pulls/{number}" \
  -H "Authorization: token $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$body_json"
```

### 7. Apply Labels

Check the repo's available labels and apply all that are relevant to the PR.

```bash
# GitHub — list available labels, then apply
gh label list --json name
gh pr edit {number} --add-label "label1,label2"

# Forgejo — use API
curl -s -X POST "${instance}/api/v1/repos/${owner_repo}/issues/{number}/labels" \
  -H "Authorization: token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"labels": [label_id_1, label_id_2]}'
```

**Selection heuristic:** Match labels to the PR's domain. Common mappings:
- Files in `lib/core/` → `core`
- Files in `lib/cli/` → `cli`
- Files in `lib/ts-sdk/` → `sdk`, `typescript`, `ts-sdk`
- Files in `lib/python-sdk/` → `sdk`, `python`, `py-sdk`
- Files in `website/` → `website`
- Dependency file changes → `dependencies`
- Docs-only changes → `documentation`

When in doubt, apply more labels rather than fewer — they're cheap and help with filtering.

### 8. Report

Show the PR URL to the user.
