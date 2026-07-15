# Resolving a Local Clone for `owner/repo`

Loaded on demand from SKILL.md. Used by the orchestrator (not by `ticket-intake` — the analyst only fetches ticket data via API).

---

## Why this exists

When the user shares a ticket from `owner/repo`, the skill needs to know where that repo is cloned locally so it can create a worktree there. A remote URL is not enough — the worktree is a local git operation.

---

## Search order

Run in order, short-circuit on first match.

### 1. Exact name under `~/code/`

```bash
TARGET_REPO="{repo}"  # e.g. "apps"
Glob(pattern="$HOME/code/*/.git")
```

For each match, the parent dir basename is the clone name. If the basename == `{repo}`, verify the remote:

```bash
cd "$CANDIDATE" && \
  git remote get-url origin | grep -iE "(github\.com[:/]|git@github\.com:){owner}/{repo}(\.git)?$"
```

If the remote matches, use `$CANDIDATE` as the trunk. Done.

### 2. One directory deeper (org subdirs)

Some users organize as `~/code/{org}/{repo}/`. Check:

```bash
Glob(pattern="$HOME/code/*/*/.git")
```

Same remote verification as above.

### 3. Alternate parents

If still missing, also check (Glob for each):

```bash
$HOME/projects/*/.git     # fallback
$HOME/src/*/.git          # fallback
```

### 4. Remote URL fallback (any remote, any name)

If no basename match, grep all clones for the remote URL. This catches renamed local dirs:

```bash
# Iterate every .git parent under ~/code/ (1 and 2 levels deep)
shopt -s nullglob  # so missing patterns expand to empty instead of literal
for dir in "$HOME"/code/*/.git "$HOME"/code/*/*/.git; do
  parent="$(dirname "$dir")"
  remote=$(git -C "$parent" remote get-url origin 2>/dev/null) || continue
  if [[ "$remote" == *"{owner}/{repo}"* ]]; then
    echo "$parent"
    break
  fi
done
```

Prefer the host's file-search tool over shell globbing when available (Hermes: `search_files(target="files")`; Claude/OpenCode/Pi: `Glob` or equivalent). Never embed an agent tool call inside a shell command.

---

## Clone-if-missing

If the search returns nothing, **ask the user first**. Do not auto-clone.

Prompt:

```
I don't see {owner}/{repo} cloned locally under:
  - ~/code/
  - ~/code/*/
  - ~/projects/ / ~/src/

Clone it to ~/code/{repo}? [y/N]
```

On yes:

```bash
gh repo clone {owner}/{repo} "$HOME/code/{repo}"
```

For Forgejo repos, `gh` won't work — prompt the user for the right clone command or use `git clone` with the instance URL.

On no, stop and report: "Cannot proceed without a local clone."

---

## Trunk vs worktree

The resolution above gives you the **trunk** (the main checkout). The `issue-work` skill will then create a **worktree** for the ticket.

Rules:
- Do not create a worktree on top of a worktree. If the resolved path is already a worktree (`.git` is a file, not a dir), find its trunk first:

  ```bash
  git -C "$CANDIDATE" rev-parse --git-common-dir
  # The git-common-dir is {trunk}/.git — strip /.git for the trunk path
  ```

- All `git fetch`, dirty-tree checks, and default-branch lookups should happen against the trunk.
- Prefer `wt` for creation/switching. Hermes then targets the returned path through each tool's `workdir`; hosts that provide `EnterWorktree` may enter the already-created path. The controlled fallback is `git -C "{TRUNK_ROOT}" worktree add -b {branch} {path} origin/{DEFAULT_BRANCH}`. See `issue-work` Phase 1.6.

---

## Multi-remote repos

Some repos have both `origin` (forge hosting) and e.g. `upstream` (fork). The ticket's forge should match `origin`. If a repo has the right `upstream` but wrong `origin`, still use it — but fetch from `upstream` instead for the default branch.

Rare edge case. Don't optimize unless it comes up.

---

## Cache (optional future work)

If resolution becomes slow in practice (many cloned repos), consider a tiny cache at `{TRUNK_ROOT}/.hermes/issue-work/.repo-cache.json`:

```json
{
  "owner-a/repo-one": "$HOME/code/repo-one",
  "owner-b/repo-two": "$HOME/code/org-b/repo-two"
}
```

Populated on first resolution, invalidated on `gh repo clone` or manual clear. **Skip for now** — premature. Only build if resolution feels slow.
