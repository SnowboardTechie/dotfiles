---
name: worktrunk
description: Git worktree management via worktrunk (wt) - layout conventions, commands, hooks, and agent integration
---

# Worktrunk - Git Worktree Management

This skill teaches agents how to operate within a worktrunk-managed worktree environment. Worktrunk (`wt`) makes git worktrees as easy as branches, enabling parallel agent workflows.

---

## Detecting a Worktree

Check whether you're in a worktree or the main checkout:

```bash
# Worktree: .git is a FILE containing "gitdir: /path/to/main/.git/worktrees/<name>"
# Main checkout: .git is a DIRECTORY
test -f .git && echo "worktree" || echo "main checkout"
```

If in a worktree, you can find the main repo path:

```bash
git worktree list --porcelain | head -1
```

---

## Directory Layout

Worktrunk uses a **sibling directory layout** by default:

```
~/code/org/
├── simpler-grants-protocol/                # Trunk (main branch)
├── simpler-grants-protocol.feat-auth/      # Worktree for feat-auth branch
├── simpler-grants-protocol.fix-nav/        # Worktree for fix-nav branch
└── simpler-grants-protocol.chore-deps/     # Worktree for chore-deps branch
```

The pattern is `{repo}.{branch}` as a sibling directory. All worktrees share the same `.git` object store, so commits, stashes, and reflogs are shared.

---

## Core Commands

| Task | Command | Notes |
|------|---------|-------|
| Switch to worktree | `wt switch <branch>` | Changes directory to the worktree |
| Create + switch | `wt switch --create <branch>` | Creates branch and worktree from current HEAD |
| Create + run agent | `wt switch -c -x claude <branch>` | Creates worktree and launches Claude Code |
| List all worktrees | `wt list` | Shows branch, status, ahead/behind, age |
| Full list with summaries | `wt list --full` | Includes LLM-generated branch summaries |
| Remove worktree | `wt remove` | Removes current worktree and its branch |
| Remove specific | `wt remove <branch>` | Removes named worktree |
| Merge to target | `wt merge <target>` | Local repos only — for remotes, see "Wrapping Up" |
| Commit with LLM msg | `wt step commit` | Uses configured LLM for commit message |
| Copy build caches | `wt step copy-ignored` | Copies node_modules, target/, etc. from trunk |

### Important Flags

- `--create` / `-c` — Create a new branch and worktree
- `--execute` / `-x <cmd>` — Run a command after switching (e.g., `-x claude`)
- `--no-verify` — Skip hooks on create/switch
- `--` — Pass arguments to the executed command (e.g., `-x claude -- 'Fix the bug'`)

---

## Hooks

Worktrunk supports lifecycle hooks configured in two places:

### User Config (`~/.config/worktrunk/config.toml`)

Global hooks that run for all repos:

```toml
[post-create]
direnv = "[ -f .envrc ] && direnv allow"

[post-switch]
tmux = '[ -n "$TMUX" ] && tmux rename-window {{ branch | sanitize }}'
```

### Project Config (`.config/wt.toml` in repo root)

Project-specific hooks that append to global hooks:

```toml
[post-create]
deps = "yarn install --frozen-lockfile"

[post-start]
copy = "wt step copy-ignored"

[pre-commit]
lint = "yarn lint:changed"

[pre-merge]
test = "yarn test:changed"
```

### Hook Lifecycle

| Hook | When | Use Case |
|------|------|----------|
| `post-create` | After worktree creation | Install deps, allow direnv |
| `post-start` | After worktree starts | Copy build caches |
| `post-switch` | After switching to worktree | Rename tmux window |
| `pre-commit` | Before committing | Lint changed files |
| `pre-merge` | Before merging | Run tests on changed files |
| `post-merge` | After merging | Clean up, notify |

Hooks support **template variables**: `{{ branch }}`, `{{ branch | sanitize }}`, `{{ branch | hash_port }}`.

---

## LLM Commit Messages

Worktrunk pipes a templated prompt (containing the diff) to a configured command:

```toml
[commit.generation]
command = "~/.config/worktrunk/commit-msg.sh"
```

The bridge script (`commit-msg.sh`) reads the prompt from stdin and passes it to opencode's `commit-msg` agent:

```bash
prompt=$(cat)
opencode run --agent commit-msg --format json "$prompt" 2>/dev/null \
  | jq -sr '[.[] | select(.type == "text")] | map(.part.text) | join("")'
```

Trigger with `wt step commit` or `wt merge` (which commits automatically).

---

## Agent Best Practices

### DO

- Use `wt switch` instead of `git checkout` or `git switch`
- Use `wt list` to see what other worktrees/branches exist
- Use `wt step commit` for committing (gets LLM-generated message)
- Use `wt merge <target>` for local-only repos without a remote — for repos with a remote, push and open a PR instead (see "Wrapping Up")
- Check `wt list` before creating a new worktree to avoid duplicates
- Remember that `git stash` and `git log` are shared across all worktrees

### DON'T

- **Never** `git checkout <branch>` — this switches branches in-place, defeating the purpose of worktrees
- **Never** delete or modify the `.git` file in a worktree
- **Never** `git worktree add` or `git worktree remove` directly — use `wt` commands which also handle branch cleanup
- **Never** `rm -rf` a worktree directory — use `wt remove` to properly unregister it
- Don't assume you're on the main branch — check `git branch --show-current`

### Working in a Worktree

When operating inside a worktree:

1. **You're on a feature branch** — the branch name matches the worktree suffix
2. **Other agents may be working in sibling worktrees** — don't modify shared resources (main branch, tags)
3. **Build caches may be shared** — `node_modules/`, `target/`, `.next/` may have been copied from trunk
4. **The trunk worktree has the main branch** — it lives at the unsuffixed directory path

---

## Wrapping Up

**Trigger phrases:** "wrap up", "open a PR", "ship it", "I'm done", "create a pull request"

When work is complete and committed, follow this flow to open a PR and clean up.

### Step 1: Detect Forge

```bash
remote_url=$(git remote get-url origin 2>/dev/null)
if [[ "$remote_url" == *"github.com"* ]]; then
  forge="github"   # use gh CLI
elif [[ "$remote_url" == *"forgejo"* || "$remote_url" == *"gitea"* || "$remote_url" == *"snowboardtechie"* ]]; then
  forge="forgejo"  # use tea CLI
else
  forge="none"     # no remote or unknown — fall back to wt merge
fi
```

### Step 2: Pre-flight Checks

Before offering to open a PR:

- Not on trunk: `git branch --show-current` must not be `main` or `master`
- Remote exists: `git remote -v` returns output
- Forge CLI authenticated: `gh auth status` (GitHub) or `tea login list` (Forgejo) — if not, bail early with setup instructions
- No existing PR: `gh pr list --head <branch>` (GitHub) or `tea pr list --state open | grep <branch>` (Forgejo) returns empty

### Step 3: Ask User

Ask conversationally: "Should I open a PR for this work?" — do not use a shell prompt.
Also ask: draft or ready-for-review?

### Step 4: Push Branch

```bash
git push -u origin <branch>
```

Note: `git push` triggers an opencode permission prompt (not in allow-list by design).

### Step 5: Create PR

| Forge | Ready | Draft |
|-------|-------|-------|
| GitHub | `gh pr create --fill` | `gh pr create --fill --draft` |
| Forgejo | `tea pr create --head <branch> --base main` | `tea pr create --head <branch> --base main --draft` |

### Step 6: Fill PR Description

Invoke `/update-pr-description` (or load the `update-pr-description` skill) to fill the PR template from the diff. It auto-detects the PR from the current branch.

The skill is **forge-aware** — it detects GitHub vs Forgejo from the remote URL and uses the appropriate API (`gh` for GitHub, `tea api` / Forgejo REST API for Forgejo).

### Step 7: Report

Show the PR URL to the user.

### Step 8: Post-Merge Cleanup

After the PR is merged (may be a separate session), clean up:

```bash
wt remove  # removes current worktree and branch
```

---

### Edge Cases

| Situation | Action |
|-----------|--------|
| No remote | Fall back to `wt merge` |
| Not authenticated | Bail: "Run `gh auth login` or `tea login`" |
| PR already exists | Show URL via `gh pr view --web` or `tea pr view`, skip creation |
| On trunk branch | Warn user, do not create PR |

---

## Shell Integration

### Aliases

```bash
wls   # wt list
wsw   # wt switch
wrm   # wt remove
wmg   # wt merge
```

### wcode Function

`wcode` creates a worktree and opens opencode in a new tmux window:

```bash
wcode feat-auth                    # Create worktree + tmux window + opencode
wcode feat-auth "Fix the login"    # Same, but sends a prompt to opencode
```

This is the primary workflow for launching parallel agent sessions.

---

## Tmux Integration

When inside tmux, worktrunk automatically renames the current window to the branch name on `wt switch` (via the `post-switch` hook). The `wcode` function creates a new tmux window per worktree.

Typical tmux layout with parallel agents:

```
[0] main        — trunk, manual work
[1] feat-auth   — agent working on auth
[2] fix-nav     — agent fixing navigation
[3] chore-deps  — agent updating deps
```
