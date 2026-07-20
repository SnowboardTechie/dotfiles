---
name: issue-plan
description: Plan an existing issue into a vault-backed handoff.
version: 1.0.0
author: Bryan Thompson + Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [issues, planning, vaults, implementation]
    related_skills: [issue-work, plan, vault-pkm, adr-and-spec-coach, dx-target, conforming-tech-specs]
---

# Issue Plan

## Overview

Turn an existing GitHub or Forgejo issue into an approved, durable implementation
plan before implementation starts. The workflow grounds itself in the current
issue, codebase, and project vault; deliberates unresolved decisions with the
user; invokes the appropriate design skills; and saves one canonical plan note
that `issue-work` can consume later.

Planning is read-only with respect to tracked code and the working tree. An
authenticated ticket read and `git fetch` of the default branch are allowed so
the plan is grounded in the current remote base. Do not create a worktree, edit
project files, commit code, post issue comments, or begin implementation. Vault
writes and the vault's own commit/push discipline are the only content mutations.

## When to Use

Use when the user:

- Has an issue that is known work but is not ready to implement yet.
- Wants to discuss implementation details before running `issue-work`.
- Asks to prepare, pre-plan, design, or flesh out an existing issue.
- Wants the resulting implementation context saved in the appropriate project
  vault.

Do not use for a rough idea that is not yet an issue; use `issue-create`. Do not
use when the user wants implementation to begin now; use `issue-work`, whose
plan-source gate will either accept an approved vault plan, accept a sufficiently
clear issue as planning authority, or stop.

## Inputs

Accept the same issue identifiers as `issue-work`:

- GitHub or Forgejo issue URL.
- GitHub shorthand `{owner}/{repo}#{N}`.
- A directly named issue plus an unambiguous current repository.

This workflow plans issues, not pull-request reviews. If the identifier resolves
to a PR, route to the appropriate review workflow instead.

## Phase 1: Resolve and Ground

### 1. Resolve the issue and repository

Use `issue-work`'s source detection, ticket-fetch, and repository-resolution
references. Fetch the current issue body, `updatedAt`/`updated_at`, every comment
with its stable ID and update timestamp, labels, linked references one level
deep, and acceptance criteria. Compute the canonical comment checkpoint defined
in the ticket-fetch reference.

Resolve the local trunk checkout and the forge's actual default branch. Fetch
that branch, bind `origin/{default}` (or the forge-equivalent remote ref) as the
planning base, and record its full commit SHA. Do not switch branches or create a
worktree. Inspect repository content against that fetched base; a dirty or stale
local checkout is not provenance.

If default-branch resolution or fetch fails, stop and surface the authentication
or remote error. Never fall back to a stale local ref.

**Complete when:** the canonical issue URL, issue update timestamp, comment
checkpoint, repository identity, trunk path, default branch, and fetched base
revision are known.

### 2. Resolve the project vault

Load `vault-pkm`; it owns vault discovery, local instructions, topology,
frontmatter, linking, and synchronization. Resolve in this order:

1. A vault path explicitly named by project instructions.
2. `{TRUNK_ROOT}/vault` when it is a directory or symlink.
3. `~/code/notes/{repo}` when it exists and clearly belongs to the repository.

Do not silently fall back to `~/second-brain` for project implementation plans.
If no project vault can be resolved, stop and ask where this project's durable
notes belong.

Read the vault's `AGENTS.md`, entry point, status note when present, relevant MOC,
and existing notes that mention the canonical issue URL, issue number plus repo,
title terms, and likely synonyms.

**Complete when:** one concrete vault root and one existing or proposed canonical
note location are known, with local rules loaded.

### 3. Inspect the implementation surface read-only

Read repository instructions, manifests, relevant implementation files, nearby
patterns, tests, and repository-owned specs/ADRs. Trace named symbols to their
definitions and usages. Use one or two bounded exploration delegates when the
issue spans distinct areas; delegates return findings only and must not write to
the repository or vault.

Do not invent exact file paths or APIs. External research is conditional: use
primary documentation only when the issue depends on an API or library that the
repository does not already establish.

**Complete when:** affected surfaces, reusable patterns, tests, coupling, and
source-backed constraints are mapped well enough to identify the real decisions.

## Phase 2: Deliberate with the Right Skills

Classify the remaining work before drafting. Load every applicable skill; these
are composable, not mutually exclusive:

| Planning need | Required skill and role |
|---|---|
| Vault discovery, note shape, links, synchronization | `vault-pkm` throughout |
| Consumer/plugin-author-facing SGG or CommonGrants surface | `dx-target` before task planning; its chosen target is an acceptance oracle |
| A load-bearing architectural choice is still open | `adr-and-spec-coach`; the user chooses one decision at a time |
| A formal ADR/spec must conform to an established conventions index | `conforming-tech-specs` after decisions are settled |
| Concrete implementation sequence, files, and checks | `plan` after design decisions are settled |

Runtime mapping is explicit:

| Capability | Hermes | Claude / OpenCode |
|---|---|---|
| Generic task-plan authoring | installed `plan` | `superpowers:writing-plans` or an explicitly installed equivalent; stop if absent |
| DX target exploration | installed `dx-target` | use `dx-target` only when installed; otherwise stop and hand the session to Hermes |
| Decision coaching | installed `adr-and-spec-coach` | installed pooled `adr-and-spec-coach` |
| Spec conformance | installed `conforming-tech-specs` | installed pooled `conforming-tech-specs` |

Do not silently replace a missing specialized workflow with generic drafting.

A skill's narrower applicability still governs. Do not force `dx-target` onto an
internal bug fix or `conforming-tech-specs` onto a trivial change.

Build a ranked agenda of unresolved decisions. For each load-bearing decision,
use the owning skill's interaction contract: present genuine options, trade-offs,
and a recommendation, then ask one focused question. Never hide unresolved
choices inside a polished plan. Cheap, established defaults may be stated and
confirmed briefly.

If the issue and prior decisions already settle everything important, skip
manufactured Q&A and proceed to drafting.

**Complete when:** every load-bearing decision is either user-settled or explicitly
recorded as an implementation blocker. A blocker stops the workflow; it may not
be deferred into an "approved" plan.

## Phase 3: Draft the Canonical Vault Plan

### 1. Choose the note before writing

Follow `vault-pkm` and vault-local conventions. Prefer updating an existing
canonical issue plan over creating a duplicate. Otherwise propose the concrete
vault-relative path and note type before writing. Planning work commonly lands
in an existing `planning/`, `plans/`, or `explorations/` area, but do not create
a new folder or MOC without approval.

Supporting `dx-target`, ADR, or spec notes remain separate atomic notes and link
to the implementation plan. The implementation plan is the canonical handoff.

### 2. Invoke the mapped plan-authoring skill with a path override

After design decisions are settled, load Hermes `plan` or the mapped host
equivalent above. Override its normal workspace destination with the chosen vault
note path and adapt its output to the vault's frontmatter and linking conventions.
The plan must include:

- Goal and externally observable outcome.
- In-scope and out-of-scope boundaries.
- Accepted decisions and linked supporting design notes.
- Current implementation context and assumptions.
- Ordered, bite-sized implementation tasks with exact likely paths.
- Test, lint, typecheck, integration, migration, and rollout checks as applicable.
- Risks and only non-blocking open questions.
- The machine-readable handoff section defined in
  [references/handoff-contract.md](references/handoff-contract.md).

Expected command output must be an evidence-shaped expectation such as "targeted
test passes" rather than invented counts from commands that were not run.

**Complete when:** another agent could implement without making a load-bearing
product or architecture decision, and every exact path or API claim is grounded
in the inspected repository.

## Phase 4: Review, Approve, and Synchronize

Present the complete plan inline and name its vault path. Iterate conversationally
until the user explicitly approves it. Before approval, the handoff section must
say `Planning status: draft`; do not let `issue-work` consume an unfinished plan.

On approval:

1. Set `Planning status: approved` in the handoff section.
2. Re-read the note and linked decision/design artifacts.
3. Verify the issue URL, issue timestamp, comment checkpoint, repository
   identity, default branch, and fetched base revision.
4. Ensure the relevant MOC or index has an inbound route to every new durable
   note.
5. Follow `vault-pkm`'s vault-local commit and push discipline, staging only the
   approved non-draft notes.
6. Fetch and verify the vault remote contains the committed plan when local rules
   require synchronization.

Report the canonical plan path, supporting note paths, issue URL, repository
revision, and whether synchronization succeeded. End by explaining that a future
`issue-work {issue}` run will validate freshness before using the plan.

**Complete when:** the approved note is readable, linked, synchronized as
required, and conforms to the handoff contract.

## Change and Freshness Rules

An approved plan is not immutable. If the issue, comments, source code, or a
linked decision changes materially, reopen the plan:

- Change `Planning status` back to `draft`.
- Reconcile the affected sections and linked notes.
- Re-run the applicable design skill for any reopened load-bearing decision.
- Obtain explicit approval again before restoring `approved`.

Timestamp or commit drift alone is not material. Scope, acceptance criteria,
architecture, API shape, implementation pattern, migration requirements, or test
strategy drift is material.

## Common Pitfalls

1. **Using generic `plan` alone.** It writes workspace execution state and does
   not perform vault lookup, decision coaching, or the issue handoff contract.
2. **Creating a worktree "for exploration."** Planning inspects the fetched base
   read-only and never needs a worktree.
3. **Saving only an exploration.** Candidate designs are supporting notes; the
   workflow still needs one approved canonical implementation plan.
4. **Marking a plan approved with open architecture choices.** Unresolved
   load-bearing decisions are blockers, not plan footnotes.
5. **Treating stale metadata as automatic invalidation.** Inspect the drift and
   distinguish material change from harmless movement.
6. **Writing to the personal vault by default.** Project implementation plans
   belong in the project vault unless the user explicitly chooses otherwise.
7. **Duplicating issue prose.** Link and synthesize; capture decisions and
   implementation detail the issue does not already preserve.

## Verification Checklist

- [ ] Current issue body, update timestamp, and all comment IDs/update timestamps fetched
- [ ] Canonical comment checkpoint computed
- [ ] Default branch fetched and plan grounded against its remote revision
- [ ] Repository and project vault resolved without guessing
- [ ] Vault-local instructions, index/MOC, and related notes read
- [ ] Relevant code, tests, specs, and prior patterns inspected read-only
- [ ] Applicable planning/design skills loaded in the right order
- [ ] Every load-bearing decision settled by the user
- [ ] Canonical plan path named before writing
- [ ] Plan contains exact grounded paths and verification steps
- [ ] Handoff section matches the shared contract
- [ ] User explicitly approved the final plan
- [ ] Vault links, diff, commit, push, and remote state verified as required
- [ ] No worktree, code edit, issue comment, or implementation action occurred
