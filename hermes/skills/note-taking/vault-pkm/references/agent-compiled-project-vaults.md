# Agent-Compiled Project Vaults

Use this when project knowledge is written primarily by agents and paired with live code repositories, issue trackers, ADRs, or other external sources. The main failure mode is not capture scarcity; it is **recompilation debt**: new detail accumulates while indexes, status pages, topic MOCs, plans, and superseded decisions drift apart.

## Core stance

Treat the vault as compiled project knowledge, not as the raw source of truth.

| Role | Function |
|---|---|
| External/live source | Code, exact commit, issue/PR, ADR, API docs, policy, or other primary artifact |
| Index | Stable orientation and routes into the vault; not a dump of every recent note |
| Topic MOC/reference | Current compiled understanding of one durable concern |
| Status page | Current state, blockers, and next actions |
| Decision/exploration/session | Historical reasoning and events; preserve and mark supersession |
| Draft | Noncanonical until deliberately promoted |
| Agent scratch/archive | Excluded from canonical lint unless explicitly promoted |

Do not copy whole repositories or issue threads into a new `raw/` hierarchy. Point precisely to the live source and compile the durable conclusion into the vault.

## Safe snapshot migration

When moving an existing project vault between machines, treat the archive as an untrusted snapshot until inspected and stage it before touching the active workspace.

1. **Receive outside the destination** — transfer the archive into a dated incoming directory, not directly over the active vault. Retain the original archive as a rollback source.
2. **Inventory before extraction** — record archive size and checksum; inspect entry counts, top-level roots, compressed and uncompressed totals, largest members, embedded Git metadata, symlinks, absolute paths, and `..` traversal. Stop on unsafe paths or suspicious expansion ratios.
3. **Extract into isolation** — use a dated staging directory. Exclude transport noise such as `__MACOSX/` and `.DS_Store`; do not flatten paths blindly.
4. **Read the staged vault first** — inspect its `AGENTS.md`, index/MOC, status page, canonical surfaces, Obsidian configuration, and representative notes before deciding how to merge it. Classify it as active, dormant, or historical from its own evidence.
5. **Reconcile instructions deliberately** — preserve vault-native canonical-surface rules and note conventions while adding current approval and publication boundaries. Do not let an imported `AGENTS.md` silently erase destination rules, and do not replace imported rules with a generic boilerplate.
6. **Merge without overwriting blindly** — copy staged content into the destination with explicit exclusions. Preserve destination-only orientation or policy files unless intentionally reconciled. Keep paired repositories out of the migration unless their transfer is separately requested; a vault may reference repos that were never included in the archive.
7. **Verify content, not just command success** — compare every imported file against staging by relative path and checksum, report missing or mismatched files, confirm canonical entry points and app configuration exist, and read back the merged instructions. Preserve staging until the user is satisfied.

A successful transfer is not yet a successful migration: completion requires safe extraction, instruction reconciliation, content-level verification, and an explicit statement of any referenced repositories or external sources that remain absent.

## Multi-repository workspace migration with an external vault

A project workspace and its paired notes vault may be separate trees. Resolve both concrete paths on the destination **before** importing anything. A small archive that looks internally coherent may be only the notes vault, not the multi-gigabyte workspace the user intended to move.

1. **Inspect destination topology first** — check the intended workspace root, the canonical notes repository/vault, local `AGENTS.md`, existing Git state, and current vault symlinks. Do not infer payload scope from an archive name.
2. **Identify the archive's actual role** — inventory top-level entries. If it contains `INDEX.md`, `status.md`, note folders, and no repository `.git` metadata, classify it as a vault snapshot even if its root folder shares the project name. Compare it to the destination's canonical vault before merging.
3. **Transfer large workspaces resumably** — on a trusted LAN, prefer staged `rsync -aP` without compression over making a giant ZIP. Preserve `.git`, untracked files, timestamps, permissions, and symlinks; exclude only regenerable dependency/build/cache directories such as `node_modules`, virtual environments, `.direnv`, `.next`, `dist`, `build`, coverage, and language caches. Re-running the same command should resume safely.
4. **Stage outside the active project** — receive the full workspace into a dated incoming directory. Do not rsync directly over the active Hermes/project root, especially when it already contains orientation files or an accidental earlier import.
5. **Preserve absolute worktree layout** — linked Git worktrees often record absolute paths. If source and destination homes match, place the staged workspace at the same final path. Prefer a reversible directory swap: move the old active root intact to a dated rollback location, then move staged content into the final path. Do not delete the rollback copy yet.
6. **Attach, do not duplicate, the canonical vault** — create or preserve `vault -> <canonical-vault-path>` at the umbrella and any paired repositories that use it. Imported note copies are reconciliation inputs, not a second canonical vault.
7. **Reconcile note differences deliberately** — compare the snapshot against the canonical vault by relative path and checksum. Use timestamps and semantic diffs to distinguish newer append-only updates, missing drafts, intentional machine-local state, and true conflicts. Keep noncanonical drafts noncanonical; do not add them to an index merely because they were recovered. Exclude Obsidian session state such as `.obsidian/workspace.json` unless the user explicitly wants machine UI state migrated.
8. **Verify writes independently** — a copy helper's success message is not proof. Re-read destination files and require source/destination checksums to match before deleting staging. Review the vault repository diff and confirm it contains exactly the intended tracked modifications and untracked additions.
9. **Verify repositories as repositories** — record branch and working-tree status without changing it; run Git connectivity checks; enumerate registered worktrees and verify every path exists after the final move. Distinguish preserved pre-existing changes from migration-created changes.
10. **Clean up only at the end** — after the active workspace, vault links, canonical notes, Git objects, and worktree paths all verify, remove archives/staging/rollback material only with explicit approval. Re-check the active paths after deletion.

Completion means there is one canonical notes vault, the workspace references it through valid symlinks, repository and worktree state survived, reconciled note files match their chosen source exactly, and no commit, push, post, or cleanup happened beyond the user's authorization.

## Ingest loop

For every source-backed update:

1. **Orient** — read the vault index, current status, relevant topic MOC, and local instructions.
2. **Ground** — inspect the live source. Record exact repo path, commit, PR/issue, version, and checked date when the claim can drift. If access fails, label the claim unverified.
3. **Compile** — update an existing canonical concept/status/MOC before creating another note.
4. **Preserve history** — retain event notes and superseded decisions, but add explicit status, `superseded_by`, and a route to the current conclusion.
5. **Reconcile** — propagate the changed conclusion through every canonical sibling surface in the active zone.
6. **Verify** — search the entire active zone for stale copies, validate navigation/frontmatter, review the diff, then synchronize according to local rules.

A durable new note is incomplete until a relevant MOC or index routes to it. A change to current project state is incomplete until the status page and relevant MOC/index have been checked in the same resting-point change.

## Stronger agent-owned conventions

Direct LLM control warrants stricter compilation discipline than a mixed personal vault:

- Treat age-based index warnings as a fallback, not permission to ignore event-driven drift.
- Distinguish **observed current state**, **accepted decision**, **proposed design**, **historical state**, and **unverified inference**.
- Keep provenance proportional but precise for technical claims that can drift.
- Prefer current synthesis in canonical notes and historical detail in dated event notes.
- Do not create append-only ingest logs for facts already recoverable from Git unless a real consumer needs additional data.
- Exclude unpromoted drafts, templates, and agent scratch from normal orphan/link requirements.

## Active, dormant, or historical first

Before normalizing a project vault, classify it:

- **Active compiled zone** — verify against live sources and reconcile current surfaces.
- **Dormant snapshot** — label its snapshot date and preserve it; do not imply ongoing freshness.
- **Historical/archive corpus** — orient readers to its historical value without cosmetically reviving it.

Do not modernize an archived project merely to make metadata uniform. Preserve historical decisions and add dated updates rather than rewriting original rationale.

## Cross-vault and cross-repo boundaries

- Wikilinks resolve only inside one vault. For another vault, name it and use an explicit path or Markdown link; do not copy the target note locally just to satisfy link lint.
- Paired code repositories are source inputs during a vault-only task. Inspect their branch and working tree, but do not edit, stage, switch, or clean them unless the user explicitly expands scope.
- In shared vault repositories, re-check Git state and preserve all pre-existing changes. Stage explicit files only; never sweep unrelated drafts or scratch into a vault commit.

## Targeted project-vault audit

Audit canonical content for:

- index/status pages older than newer canonical notes or code changes;
- current-vs-proposed ambiguity;
- superseded decisions whose consequences still read as current;
- contradictions copied across index/status/MOC/plan/decision surfaces;
- important zero-inbound canonical notes;
- invalid internal or cross-vault links;
- source-backed claims with no traceable source or unsupported precision.

Exclude agent scratch, templates, intentional forward links, and historical placeholders unless they caused a real retrieval failure. Do not create empty stubs to make a checker green.

## Verification sequence

1. Read back every changed canonical surface.
2. Validate changed frontmatter.
3. Confirm every new note has an inbound route.
4. Resolve links in changed canonical content, allowing documented exceptions.
5. Search the full active zone for superseded terms and values.
6. Confirm index, status, MOCs, plans, and decisions agree on current state while preserving history.
7. If a read-only audit script changed, exercise it with a temporary synthetic-vault harness—not only against the real vault. Include one clean vault and fixtures for every promised finding/exclusion. In particular, verify that default discovery can reach a vault missing `INDEX.md`; filtering discovery by `INDEX.md` makes the missing-index check unreachable. Snapshot fixture bytes before/after to prove the audit did not edit input, and remove temporary harnesses and generated caches afterward. Report this as ad-hoc behavioral verification unless a canonical suite exists.
8. Review diffs and ensure no pre-existing work was staged accidentally. Re-check source repositories after any command that may generate lockfiles, caches, or build artifacts; remove only artifacts created by the verification run.
9. Commit related vault and convention repositories separately when they have separate ownership.
