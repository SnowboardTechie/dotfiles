# Git-backed authored assets inside a mutable agent runtime

Use this pattern when an agent runtime keeps authored skills and scripts beside credentials, databases, logs, caches, sessions, scheduler state, or encryption material.

## Ownership boundary

Version only the reproducible layer:

- User- or agent-authored skills, including references, templates, and deterministic helper scripts.
- Authored automation source.
- Declarative scheduler definitions: name, schedule, prompt, attached skills, delivery mode, toolsets, and workdir.
- A manifest that explicitly allowlists what the installer manages.

Leave these local:

- Credentials, `.env`, auth pools, and encryption keys.
- Sessions, memories, SQLite databases and WALs, logs, caches, PIDs, and locks.
- Scheduler execution history, output, next-run timestamps, and mutable job stores.
- Compiled binaries that can be rebuilt from tracked source.

Built-in skills come from the agent installation. Record Hub/registry additions by source identifier and version when possible rather than copying third-party trees. For Hermes, `hermes skills list --source local` gives the candidate set that needs explicit protection; inspect it rather than assuming every installed skill is custom.

## Installer shape

1. Keep the managed source tree outside normal whole-home Stow processing.
2. Use an explicit manifest of skills, scripts, and automations; never discover everything under the runtime root and copy it wholesale.
3. Link managed skill directories and source scripts when the runtime accepts external symlinks.
4. If a runtime validates that an executable or scheduler script resolves inside its sandbox, install that entry point as a regular copy instead. Back up an older installed copy before replacing it; keep the Git copy canonical.
5. Reconcile scheduled jobs by exact stable name through the runtime API. Do not commit or hand-edit the mutable jobs database as the source of truth.
6. Gate machine-specific collectors and schedules by host/platform while keeping portable skills reusable.

## Safe first adoption

Before replacing live directories:

1. Take a fresh snapshot of every allowlisted source, excluding caches and generated files.
2. Checksum-compare the snapshot to the live source. If another agent changes a skill during the copy, re-read and resnapshot the entire affected set.
3. Commit and push the protected snapshot before changing live ownership.
4. Replace only destinations that are byte-identical to the committed source.
5. Move identical originals to a timestamped backup, then create the canonical link.
6. Refuse non-identical real files/directories, foreign symlinks, and broken symlinks. Never auto-delete or auto-adopt them.

Use an isolated Git worktree when the normal checkout has unrelated edits. Stage exact paths, and keep repository integration separate from runtime activation. A pushed feature branch is a backup, but automatic recovery is not complete until the canonical branch contains the installer and the live runtime points at its stable checkout.

## Ad-hoc verification matrix

When no canonical suite covers distribution, explicitly label this as ad-hoc verification and exercise:

- Fresh empty runtime home.
- Second identical run (idempotence).
- Destination discovery through the real runtime CLI, not just filesystem assertions.
- Native helper compilation, if applicable.
- Scheduler create followed by update; verify every declarative field, not just job existence.
- Non-identical real-file/directory collision with a sentinel that must survive.
- Foreign and broken symlink refusal.
- Identical-directory adoption plus backup verification.
- Stow/dotfile dry run proving the support tree is excluded from whole-home linking.
- Repository cleanliness and local/remote commit equality after the last edit.

Create fixtures with the host OS's safe temporary-directory API, run the verifier from the final source tree, and remove it afterward. Repository validation and live runtime activation remain separate completion gates.
