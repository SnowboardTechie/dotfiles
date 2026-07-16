# Peer Git workspace migration

Use this pattern when one computer becomes the primary agent/work host while another keeps permanent checkouts for offline work or fallback. This is **peer replication**, not a one-time source-to-target cutover: the source is retained, and Git remotes remain the normal synchronization layer after migration.

## Invariants

- Identify source, target, and the machine where tools are running.
- The source checkout remains intact unless the user separately authorizes deletion.
- Never overlay an incoming `~/code` tree directly onto an active target tree before comparing overlaps.
- Preserve `.git`, local branches, stashes, untracked files, symlinks, permissions, and linked worktrees.
- Git protects only committed and pushed state. It does not recover ignored files, untracked files, local-only branches, stashes, worktree registrations, vault notes between commits, or agent state.
- Do not live-sync mutable `.git` directories bidirectionally. Use one writer per branch and explicit Git handoffs after initial replication.

## Transfer into staging

Create a dated, target-local staging directory outside active project roots. Copy the source tree into it without `--delete`:

```bash
mkdir -p "$HOME/Downloads/code-imports/macbook-code-YYYY-MM-DD"

rsync -aP \
  --exclude='.DS_Store' \
  --exclude='node_modules/' \
  --exclude='.pnpm-store/' \
  --exclude='.venv/' \
  --exclude='venv/' \
  --exclude='.direnv/' \
  --exclude='.next/' \
  --exclude='.cache/' \
  --exclude='.turbo/' \
  --exclude='.tox/' \
  --exclude='.pytest_cache/' \
  --exclude='.mypy_cache/' \
  --exclude='.ruff_cache/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='coverage/' \
  --exclude='dist/' \
  --exclude='build/' \
  --exclude='target/' \
  --exclude='.gradle/' \
  --exclude='.terraform/' \
  --exclude='.godot/' \
  "$HOME/code/" \
  "user@target:$HOME/Downloads/code-imports/macbook-code-YYYY-MM-DD/"
```

Keep exclusions narrow and clearly regenerable. Do not exclude `.git`. A repository may intentionally vendor dependencies or keep local path dependencies; inspect unusually large directories rather than assuming every `deps/` or `vendor/` directory is disposable.

## Inventory before activation

For both staged and active trees, record:

- Top-level roots and sizes
- Every `.git` directory and `.git` file
- Top-level repositories, current branches, upstream status, HEADs, tracked modifications, and untracked files
- Registered worktrees and whether their paths exist
- Symlinks, especially `vault`, `.notes`, and absolute links
- `AGENTS.md`, `CLAUDE.md`, and other project-level operating instructions
- Existing desktop/Hermes Projects

Do not read or print `.env` or credential contents. It is enough to verify that a secret-bearing file or symlink exists and resolves.

## Reconcile overlapping projects

Classify each overlap instead of choosing one global direction:

1. **Same HEAD, both clean:** a reversible directory swap is reasonable when the staged copy carries fuller worktree metadata. Move the active directory to a dated target-local backup, then move staged content into the original absolute path.
2. **Target ahead or locally modified:** keep the target checkout authoritative. Do not overlay the older source snapshot. Import only specifically verified missing state.
3. **Source ahead or locally modified:** preserve the staged copy and decide explicitly whether to fetch/import its branch or activate the full source checkout. Do not silently overwrite target work.
4. **Diverged:** stop and compare branch ancestry, local changes, and ownership. Use Git branches/remotes for reconciliation, not file-level overlay.

Use checksum-aware `rsync -acni --delete` with `.git` and generated paths excluded to separate real content changes from timestamp noise. Treat `*deleting`, `+++++++`, symlink changes, checksum changes, and size changes as meaningful; `.f..t....` is normally timestamp-only.

### Linked-worktree path trap

A linked worktree's `.git` file and the main repository's `.git/worktrees/<id>/gitdir` commonly contain absolute paths. They may appear broken while the repository is in staging but become valid again when moved to the same final path used on the source.

- Do **not** run `git worktree prune` against a staged snapshot merely because those paths are temporarily absent.
- Before importing one missing worktree into a newer target checkout, verify that its commit object already exists with `git cat-file -e '<oid>^{commit}'`.
- If the worktree HEAD names a local branch absent from the target, recreate only the verified ref with `git update-ref` before registering/copying metadata.
- Copy both the worktree directory and its matching `.git/worktrees/<id>` metadata; one without the other is incomplete.
- Prefer activating a whole clean, same-HEAD checkout over hand-merging dozens of worktree registrations.

## Agent and project state

Do not automatically activate transferred root-level `.claude`, `.omc`, `.sisyphus`, or similar machine-local state. Inspect it first; permissions, absolute paths, and tool settings may be host-specific.

Create permanent Hermes/Desktop Projects for owned or actively contextualized roots. Leave third-party tool clones, generated dependency repositories, and miscellaneous sandboxes accessible on disk without automatically creating sidebar clutter. Repository-specific `AGENTS.md` files remain canonical; do not copy one project's behavioral boundary to unrelated projects.

## Vault and symlink handling

Distinguish active links from historical worktree links:

- Verify active project `vault` and `.notes` links resolve to canonical target-local notes.
- Broken absolute links inside old worktrees may be historical state. Do not rewrite tracked symlinks merely to make an audit green; that dirties the worktree and can alter old branches.
- Record broken historical links separately from active readiness.
- Avoid copying machine-specific Obsidian workspace/session state over a newer target workspace unless explicitly desired.

## Verification gates

Before calling the migration ready:

1. Run `git status --short --branch` for every primary repository and record all pre-existing local state.
2. Run `git fsck --connectivity-only --no-dangling` for every Git object store.
3. Enumerate every registered worktree; require zero missing paths and zero unintended prunable entries.
4. Verify active vault links resolve.
5. Verify final top-level layout and project registrations.
6. Confirm no commits, pushes, posts, cleans, or source deletions occurred unless explicitly authorized.

Git's empty tree object is deterministic: `4b825dc642cb6eb9a060e54bf8d69288fbee4904`. If an otherwise intact repository reports only that object missing, reconstruct it locally with:

```bash
printf '' | git hash-object -t tree -w --stdin
```

Then rerun `git fsck`; do not generalize this repair to arbitrary missing objects.

## Cleanup semantics

Name cleanup precisely. "Migration staging" means target-local temporary copies under a path such as `~/Downloads/code-imports`; it does **not** mean source-machine checkouts or active target projects.

Report:

- Exact staging paths
- Their sizes and remaining contents
- Which active paths are unaffected
- Whether a rollback copy exists

Delete target-local staging only after explicit approval. If the source is a permanent fallback, say plainly that staging cleanup does not alter it.
