# Resolving a Local Clone for `owner/repo`

Loaded on demand from SKILL.md. Used by the orchestrator (not by `ticket-intake` — the analyst only fetches ticket data via API).

---

## Why this exists

When the user shares a ticket, resolve its ticket-workspace clone first. An
approved handoff may then name a different implementation repository whose clone
owns the worktree. A remote URL is not enough for either role: state, vault
discovery, fetches, and worktrees are local operations.

For ordinary issues the two roles are the same clone. For cross-repository work,
run this resolution independently for each expected forge host and
owner/repository. Never accept a clone merely because it sits under the ticket
workspace, has a similar name, or contains equal files.

---

## Search order

Run in order, short-circuit on first match.

### 1. Explicit project path

First honor a concrete clone path named by user input, ticket-workspace
instructions, or a workspace repository manifest such as `repos.tsv`. Verify the
candidate's origin; the declaration is discovery evidence, not identity proof.

### 2. Ticket-workspace checkout

For an implementation repository bound by a private workspace, check
`{TICKET_TRUNK_ROOT}/repos/{repo}`. This is the intended
`private-workspace/repos/public-project`-style topology. Verify both forge hostname and
owner/repository before accepting it.

### 3. Exact name under `~/code/`

```bash
TARGET_REPO="{repo}"  # e.g. "apps"
Glob(pattern="$HOME/code/*/.git")
```

For each match, the parent dir basename is the clone name. If the basename equals
`{repo}`, parse `git remote get-url origin` with
`scripts/select_issue_worker.py`'s identity rules and require the exact expected
hostname and owner/repository. Do not use a substring match.

If the remote matches, use `$CANDIDATE` as the trunk. Done.

### 4. One directory deeper (org subdirs)

Some users organize as `~/code/{org}/{repo}/`. Check:

```bash
Glob(pattern="$HOME/code/*/*/.git")
```

Same remote verification as above.

### 5. Alternate parents

If still missing, also check (Glob for each):

```bash
$HOME/projects/*/.git     # fallback
$HOME/src/*/.git          # fallback
```

### 6. Remote URL fallback (any remote, any name)

If no basename match, enumerate candidate clones and parse each origin with the
same exact identity rules. This catches renamed local directories without
accepting substring or suffix lookalikes.

Enumerate `.git` candidates under `~/code/` at the supported depths with the
host's file-search tool, read each origin, and compare exact parsed identity in
the orchestrator. Never embed an agent tool call in a shell command.

---

## Clone-if-missing

If the search returns nothing, **ask the user first**. Do not auto-clone.

Prompt:

```
I don't see {owner}/{repo} cloned locally under:
  - the explicit workspace path or manifest
  - {TICKET_TRUNK_ROOT}/repos/{repo}
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

## Cross-repository binding

The explicit approved handoff supplies the implementation forge and
owner/repository. Verify both against the candidate clone's `origin` before
binding `{IMPLEMENTATION_TRUNK_ROOT}`. The ticket clone remains
`{TICKET_TRUNK_ROOT}` and owns `.hermes/issue-work/`; the implementation clone
owns the feature worktree. A missing implementation clone follows the same
clone-if-missing approval rule. Legacy `Repository` handoffs may resolve only a
same-repository target.

## Trunk vs worktree

The resolution above gives you the **trunk** (the main checkout). The `issue-work` skill will then create a **worktree** for the ticket.

Rules:
- Do not create a worktree on top of a worktree. If the resolved path is already a worktree (`.git` is a file, not a dir), find its trunk first:

  ```bash
  git -C "$CANDIDATE" rev-parse --git-common-dir
  # The git-common-dir is {trunk}/.git — strip /.git for the trunk path
  ```

- Ticket state and vault discovery use `{TICKET_TRUNK_ROOT}`.
- Git fetch, dirty-tree checks, default-branch lookup, and worktree creation use
  `{IMPLEMENTATION_TRUNK_ROOT}`.
- Prefer `wt` for creation/switching. The controlled fallback is `git -C
  "{IMPLEMENTATION_TRUNK_ROOT}" worktree add -b {branch} {path}
  origin/{DEFAULT_BRANCH}`. See `issue-work` Phase 1.7.

---

## Multi-remote repos

Do not rescue an identity mismatch by switching from `origin` to another remote.
The ticket clone's `origin` must match the ticket repository, and the
implementation clone's `origin` must match the approved implementation forge and
repository because worktree routing and `/ship` publish through that identity. A
fork/upstream workflow requires an explicit future contract for separate source,
base, and publication remotes; until then, stop rather than guessing.

---

## Cache (optional future work)

If resolution becomes slow, consider a cache at
`{TICKET_TRUNK_ROOT}/.hermes/issue-work/.repo-cache.json` keyed by forge host and
owner/repository:

```json
{
  "owner-a/repo-one": "$HOME/code/repo-one",
  "owner-b/repo-two": "$HOME/code/org-b/repo-two"
}
```

Populated on first resolution, invalidated on `gh repo clone` or manual clear. **Skip for now** — premature. Only build if resolution feels slow.
