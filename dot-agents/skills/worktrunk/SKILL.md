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

## Canonical trunk resolution

This skill **owns** trunk/worktree resolution for the whole shared pool. Other
skills cite this section; none of them re-spell the logic. Anything that needs
the trunk — repo-scoped state directories, project vaults, shared caches,
per-repo config — resolves it here first.

`git rev-parse --show-toplevel` gives the *current* checkout, which is the
worktree when you are inside one. The trunk is the parent of the shared
`--git-common-dir`:

```bash
resolve_trunk_root() {
  local toplevel common_dir
  toplevel=$(git rev-parse --show-toplevel) || return 1

  if [ -f "$toplevel/.git" ]; then
    # Inside a worktree: .git is a regular file pointing at the shared store.
    # --git-common-dir is the trunk's .git directory; its parent is the trunk.
    common_dir=$(git rev-parse --path-format=absolute --git-common-dir) || return 1
    dirname "$common_dir"
  else
    echo "$toplevel"
  fi
}

TRUNK_ROOT=$(resolve_trunk_root)
PROJECT_NAME=$(basename "$TRUNK_ROOT")
```

| Where you are | `--show-toplevel` | `resolve_trunk_root` |
|---|---|---|
| Trunk `simpler-grants-protocol/` | `…/simpler-grants-protocol` | `…/simpler-grants-protocol` |
| Worktree `simpler-grants-protocol.feat-auth/` | `…/simpler-grants-protocol.feat-auth` | `…/simpler-grants-protocol` |

Pass `--path-format=absolute` explicitly: without it Git may return
`--git-common-dir` relative to the current directory, and `dirname` on a
relative path silently yields the wrong trunk.

**Repo-scoped state lives in the trunk, never per worktree.** Sibling worktrees
of one repository share it, so a review, plan, or cache written from a worktree
must be written under `{TRUNK_ROOT}` to be visible to the next session. Reading
that state is not permission to create it: a skill that finds no state directory
reports the absence and continues, rather than scaffolding one.

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
| Create + switch | `wt switch --create <branch>` | Creates from the default branch; add `--base <ref>` when the base is explicit |
| Create + run agent | `wt switch -c -x <agent-cli> <branch>` | Use `hermes`, `claude`, `opencode`, or `pi` as installed |
| List all worktrees | `wt list` | Shows branch, status, ahead/behind, age |
| Full list with summaries | `wt list --full` | Includes LLM-generated branch summaries |
| Remove worktree | `wt remove` | Removes current worktree and its branch |
| Remove specific | `wt remove <branch>` | Removes named worktree |
| Merge to target | `wt merge <target>` | Local repos only — for remotes, see "Wrapping Up" |
| Commit with LLM msg | `wt step commit` | Uses configured LLM for commit message |
| Copy build caches | `wt step copy-ignored` | Copies node_modules, target/, etc. from trunk |

### Important Flags

- `--create` / `-c` — Create a new branch and worktree
- `--base` / `-b <ref>` — Choose the base for `--create` (for example `origin/main`)
- `--execute` / `-x <cmd>` — Run a command after switching (for example `-x hermes` or `-x claude`)
- `--no-verify` — exists, but agents must not use it; hooks remain mandatory
- `--` — Pass arguments to the executed command when that CLI supports them

---

## Hooks

Worktrunk supports lifecycle hooks configured in two places:

### User Config (`~/.config/worktrunk/config.toml`)

Global hooks that run for all repos:

```toml
[post-create]
direnv = "[ -f .envrc ] && direnv allow"
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
| `post-switch` | After switching to worktree | Refresh shell or editor context |
| `pre-commit` | Before committing | Lint changed files |
| `pre-merge` | Before merging | Run tests on changed files |
| `post-merge` | After merging | Clean up, notify |

Hooks support **template variables**: `{{ branch }}`, `{{ branch | sanitize }}`, `{{ branch | hash_port }}`.

### Shared agent context

Personal `AGENTS.md`, its `CLAUDE.md` symlink, and vault links may be globally
ignored and therefore absent from a new worktree. After creation, run the linked
`scripts/link-shared-context.sh` helper against the new worktree. It links only
missing context files/directories from the trunk and never replaces existing
paths.

This can be called manually after `wt switch --create`, or from a trusted
`post-create` hook. Verify its reported links before starting an agent in the
worktree.

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

- Use `wt switch` instead of `git checkout` or `git switch`; Hermes can also keep the session in place and target the worktree through each tool's `workdir`
- Use `wt list` to see what other worktrees/branches exist
- Use `wt step commit` for committing (gets LLM-generated message)
- Use `wt merge <target>` for local-only repos without a remote — for repos with a remote, push and open a PR instead (see "Wrapping Up")
- Check `wt list` before creating a new worktree to avoid duplicates
- Remember that `git stash` and `git log` are shared across all worktrees

### DON'T

- **Never** `git checkout <branch>` — this switches branches in-place, defeating the purpose of worktrees
- **Never** delete or modify the `.git` file in a worktree
- **Never** use raw `git worktree` when `wt` is available. If `wt` is unavailable, a controlled `git worktree add` fallback is allowed, but record the path and clean it up with `git worktree remove` rather than `rm -rf`
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

For a repository with a remote, load `ship`; it owns forge detection,
verification, publication approval, draft PR creation, template filling, and
labels. Do not duplicate that logic here.

For a local-only repository, `wt merge <target>` is available after the user
approves the merge and project hooks pass.

After a remote PR is merged and the forge state is verified, clean up with
`wt remove`. Never remove a worktree merely because its PR exists.

---

### Edge Cases

| Situation | Action |
|-----------|--------|
| No remote | Fall back to `wt merge` |
| Not authenticated | Bail: "Run `gh auth login` or `tea login`" |
| PR already exists | Show URL via `gh pr view --web` or `tea pr view`, skip creation |
| On trunk branch | Warn user, do not create PR |
| Forgejo merge requested | Do not use `wt merge` for a remote PR. Load `manual-merge`, require reviewed/CI-green state plus explicit approval, and serialize merges against the same base. |

---

## Shell Integration

### Aliases

```bash
wls   # wt list
wsw   # wt switch
wrm   # wt remove
wmg   # wt merge
```
