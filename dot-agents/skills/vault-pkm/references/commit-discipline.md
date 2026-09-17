# Vault commit discipline

After writing notes, commit and push the vault's own repo. **Per session or
per resting-point, whichever comes first** — not per individual write.

## Why per-session, not per-write

Per-write commits were the original spec, but the empirical baseline
(~11 commits/month in the former personal vault, multi-note batches) shows that per-write
discipline would have been silently abandoned. Per-session matches actual
cadence; multi-note batches are normal and fine.

A "resting point" is when you finish a coherent unit of work — a decision
captured, an investigation closed, an exploration concluded. If a session
covers multiple resting points, commit at each. If a session covers one
sustained exploration, commit at the end.

## Mechanics

Use `git -C <vault-root>` so you don't change your working directory:

- Project vaults: `git -C ~/code/notes` (or the workspace repo that tracks `vault/`)
- `~/second-brain` is a frozen archive: never commit to it from note work

```sh
git -C <vault-root> add <files>
git -C <vault-root> commit -m "<msg>"
git -C <vault-root> push
```

## Message format

Single-note commit: `<vault>(<trigger-type>): <topic>`

Multi-note commit (resting-point batch): `<vault>: <summary>`

Examples:

- `sgg(decisions): use SQLite for cache`
- `sgg(MOC): refine Architecture for new caching layer`
- `sgg(learnings): nyquist phase ordering interactions`
- `sgg: caching design session (decision + 2 learnings + MOC update)`
- `cairn-os(decisions): adopt vault-backed handoffs`

Case in `<trigger-type>` matches the vault's folder naming.

## Cadence

- One commit per session OR per resting-point note, whichever comes first.
- Push immediately at commit time — don't queue. The "always available
  context" promise requires that other machines can pull right after.
- If a note adds a new MOC or shifts the vault's map, update `INDEX.md` in
  the same commit so the map stays current. Also bump `index-last-verified:`.
- If evidence changes current project state, check and reconcile `status.md`,
  the relevant MOC, and `INDEX.md` in the same resting-point commit. Search the
  full active zone for stale copies before staging.
- Stage explicit files only. Preserve unrelated modified/untracked work; never
  use `git add .` or `git add -A` in a shared vault repository.

## Handoff portability

For `session-handoff`, build the required artifact set from the handoff record
and every linked or named note whose content the next agent needs. A `draft` or
`noncanonical` designation is an authority label, not a Git transport rule.
Invoking `session-handoff` is explicit authorization to commit and push the
task-owned drafts in that set while preserving their draft status. Do not stage
unrelated drafts.

After pushing, fetch and verify that every required artifact is reachable from
the pushed commit and has no remaining local delta. A handoff that works only
because the next session inherits the same dirty checkout is incomplete.

## Cross-repo isolation

Vault commits live in the vault's repo, **never** in the working repo. Don't run
`git add vault/` from the project's working directory — `vault/` is gitignored
globally so that's a no-op anyway, but be explicit: use `git -C <vault-root>`.
