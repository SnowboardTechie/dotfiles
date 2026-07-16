---
name: cross-agent-skill-migration
description: Use when auditing, consolidating, or porting a skill library and agent configuration between Claude Code, OpenCode, Codex, Hermes, or another agent framework. Separates durable workflow knowledge from framework mechanics, validates portability, preserves user-specific policy, and recommends a curated migration rather than copying everything wholesale.
version: 1.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [skills, migration, agent-config, portability, consolidation]
    related_skills: [hermes-agent-skill-authoring]
---

# Cross-Agent Skill Migration

## Overview

Agent skill libraries mix several kinds of material: durable procedures, user policy, project context, framework-specific tool calls, transient state, and historical sediment. A good migration does not copy that mixture unchanged. It identifies what behavior remains valuable, maps it to the destination framework, and leaves one maintainable source of truth per concern.

The target is a small set of class-level skills with rich main instructions and progressively disclosed references, not a flat pile of one-session workflows.

## When to Use

Use this skill when:

- Reviewing skills or agent configs from another framework.
- Adding a new agent runtime to an existing shared skill pool.
- Consolidating duplicate skills that have drifted across tools.
- Deciding whether a custom workflow still adds value over destination-native capabilities.
- Converting custom agents, hooks, scheduled tasks, commands, or permission rules.

Do not use it for ordinary edits to one already-native skill. Use the destination framework's skill-authoring workflow directly.

## Migration Workflow

### 1. Inventory the whole ecosystem

Inspect more than `skills/`. Include:

- Skill documents and their linked references, templates, scripts, and examples.
- Global and project instruction files.
- Custom subagent definitions.
- Scheduled tasks and monitors.
- Hooks, permission policies, plugin lists, and launcher scripts.
- Distribution logic such as symlink arrays, external directories, or setup scripts.

Record the canonical source for each item and whether multiple tools share it.

**Completion criterion:** every relevant artifact is represented once in the inventory, including supporting files and distribution configuration.

### 2. Validate source structure before judging content

Run the destination framework's actual validator or an equivalent local check. At minimum verify:

- Frontmatter delimiters and YAML parseability.
- Required `name` and `description` fields.
- Name and description length limits.
- Linked support files exist.
- Referenced skills and commands resolve.
- Duplicate names and destination precedence are understood.

Do not assume an agent that tolerated malformed metadata proves another agent will.

**Completion criterion:** structural failures are separated from workflow-quality findings.

### 3. Classify each artifact by responsibility

Assign each item to one primary class:

| Class | Destination |
|---|---|
| Durable cross-project procedure | Class-level skill |
| Bulky or session-derived detail | `references/` under an umbrella |
| Copy-and-modify starter | `templates/` |
| Deterministic repeatable action | `scripts/` |
| Stable user preference or boundary | Relevant skill body; optionally compact user memory |
| Project-specific domain context | Project `AGENTS.md` or project-local skill |
| Runtime identity or personality | Destination-native identity/profile mechanism |
| Current task or transient state | Do not migrate |
| Scheduled recurring reasoning | Destination scheduler plus attached skill |
| Fixed-output watchdog | Script-only scheduled job |

A narrow skill is usually evidence that an umbrella needs a reference or section, not proof that another top-level skill should exist.

**Completion criterion:** every retained item has a clear long-term home.

### 4. Compare against destination-native capabilities

For each custom item, ask:

1. Does the destination already provide the mechanism?
2. Does the custom item encode user-specific judgment that the generic feature lacks?
3. Is it domain-specific enough to remain project-local?
4. Would loading both create conflicting instructions?

Common mappings include:

- Custom subagent file → delegated prompt inside the owning workflow skill.
- Slash command wrapper → native skill invocation or skill bundle.
- Claude scheduled task → Hermes cron job.
- Claude memory plugin → Hermes memory plus session search.
- Context-management plugin → native compression/session facilities.
- Permission allowlist → native approvals and security configuration.
- Shared skill symlinks → destination-supported external skill directories or a curated installation list.

Retain custom workflows when they encode meaningful policy, decision quality, forge behavior, review lenses, or a demonstrated user preference. Drop wrappers that merely restate native commands.

**Completion criterion:** each custom artifact has an explicit `retain`, `adapt`, `project-local`, `merge`, `retire`, or `redundant` disposition.

### 5. Separate framework mechanics from durable intent

Translate behavior, not tool names. Examples:

- `AskUserQuestion` becomes the destination's user-decision tool.
- Claude `Task`/`Agent` fan-out becomes destination-native delegation with its real concurrency limit.
- `~/.claude/...` state becomes a destination-native working path.
- `/loop` wrappers become scheduled prompts or jobs.
- Plugin-specific skill invocations become direct tool calls or destination skills.

Preserve completion criteria, safety gates, source-first behavior, and user approval boundaries. Remove obsolete model names, plugin identities, and product-specific syntax.

**Completion criterion:** no retained procedure depends on a source-only tool, path, model, or command without an explicit destination mapping.

### 6. Reconcile safety and side effects

Classify every side effect:

- Local reversible reads and analysis.
- Local writes and git changes.
- Destructive operations.
- Public-facing actions such as posting, emailing, commenting, relabeling, opening PRs, or merging.

An autonomous or scheduled workflow cannot ask a user who is absent. If public mutation requires approval, redesign the unattended path to report the proposed action rather than perform it. Explicit per-job authorization may narrow this, but do not infer authorization from the existence of an old automation.

**Completion criterion:** every unattended branch has a safe behavior when approval is unavailable.

### 7. Check live assumptions before preserving monitors

Scheduled tasks and project workflows often contain expiring assumptions: a branch, issue, release gate, teammate, project mapping, or tool version. Inspect the original live source before calling the automation useful.

When a monitor's trigger has already fired, report the action now and retire or redesign the monitor. Do not immortalize completed waiting conditions as skills.

**Completion criterion:** retained automations still monitor a live condition, and completed monitors have a clear retirement path.

### 8. Design the target library

Prefer this order:

1. Patch an existing loaded umbrella.
2. Add a reference, template, or script under that umbrella.
3. Broaden an existing class-level skill.
4. Create a new class-level umbrella only when responsibility is genuinely distinct.

Keep personalized source material in one canonical location where practical. Use destination-supported external directories only when the entire exposed subset is valid and desired. Otherwise maintain a curated destination list; do not expose a mixed pool wholesale.

When name collisions exist, document precedence. A local adapted skill may intentionally shadow a shared generic version.

**Completion criterion:** the proposed library has clear ownership, minimal overlap, and no stale skill exposed merely because it existed before.

### 9. Implement shared distribution conservatively

When one canonical pool feeds several runtimes, prefer a per-runtime allowlist and a dedicated destination category. A setup script must prune only pool-owned symlinks that are no longer wanted. It must never replace a real directory, regular file, or foreign symlink automatically: warn and skip instead.

When authored assets live inside a runtime home that also contains credentials, databases, sessions, scheduler history, or encryption state, do **not** stow or version the whole runtime root. Track the authored layer plus a declarative manifest, leave mutable state local, and reconcile scheduled jobs through the runtime API rather than committing its job database. If the runtime rejects executable symlinks that resolve outside its sandbox, install that entry point as a backed-up regular copy while keeping the Git source canonical.

Sandbox the installer with a temporary `HOME`. Test an empty destination, a colliding real directory containing a sentinel file, a stale pool link, and a foreign link. See `references/shared-distribution-and-portability.md` for the general test pattern and `references/git-backed-runtime-assets.md` for the mutable-runtime boundary, first-adoption sequence, scheduler reconciliation, and full restore verification matrix.

**Completion criterion:** the installer is idempotent, collision-safe, keeps secrets and mutable runtime state out of Git, recreates declarative automations, and is proven not to destroy independently managed skill data.

### 10. Verify repository changes and runtime activation separately

After adapting skills:

- Re-run metadata validation.
- Search for source-framework paths, tool names, slash commands, model references, unsafe credential examples, and stale project paths. Distinguish an intentional compatibility mapping (for example, “Hermes `delegate_task`; Claude `Task`”) from an unresolved hard dependency; do not fail merely because a source tool is named as a supported alternative or explicitly prohibited legacy path.
- For every concrete CLI recipe added or changed, inspect the installed command's live `--help` and verify the exact flags and defaults. Do not infer worktree base behavior, launcher syntax, or similar details from memory.
- Exercise deterministic helper scripts against representative fixtures.
- Verify safety gates with a public-facing or destructive dry run.
- Confirm shared-source edits happen in the intended repository, not an accidental copied fork.
- In multi-agent/shared-repo sessions, re-read a file immediately after any sibling-modification warning and before editing it again. Verify the final merged file contains both agents' intended changes; never assume a fuzzy patch preserved concurrent work.
- Install or link the curated set into the real destination runtime.
- Trigger the destination's skill rescan or start a new session.
- Confirm each migrated skill appears in the destination index and loads its support files.

Do not collapse these into one claim. “The setup script is ready” is not “the runtime is installed.” If activation or final review remains undone, report the repository work as partial and name the remaining gate.

**Completion criterion:** repository validation passes, concrete commands match the installed CLI, concurrent edits are reconciled, runtime activation is verified independently, migrated skills load, references resolve, representative behavior works, and unsafe actions remain gated.

## Reporting Format

Present the audit in four compact groups:

1. **Adapt first** — high-value personalized procedures.
2. **Keep project-local or on-demand** — useful but narrow domain workflows.
3. **Merge or mine for parts** — overlap where only some rules survive.
4. **Retire or skip** — malformed, stale, redundant, or conflicting material.

Include structural validation failures and live stale-state findings separately. End with a phased migration order rather than a vague recommendation to “port the useful ones.”

## Common Pitfalls

1. **Copying the whole directory.** This imports stale automations, malformed metadata, and conflicting skills along with the good material.
2. **Judging from descriptions only.** The real value and incompatibilities often live in references, hooks, and failure branches.
3. **Treating generic overlap as full redundancy.** A custom skill may encode user-specific policy or domain judgment absent from a generic destination skill.
4. **Porting tool syntax literally.** Preserve intent and gates; remap mechanics.
5. **Ignoring concurrency differences.** A four-agent workflow must be batched or redesigned when the destination allows three.
6. **Letting unattended jobs mutate public systems.** Report when approval is unavailable.
7. **Importing stale profile files wholesale.** Mine stable rules; reject outdated roles, hours, people, paths, and project state.
8. **Forgetting local precedence.** A destination-local skill can silently shadow the shared pool.
9. **Using external directories as a read-only boundary.** Writable external skills may be modified in place by skill-management tooling.
10. **Creating one skill per old artifact.** Consolidate around task classes and move detail behind references.
11. **Replacing real directories during symlink setup.** A canonical-pool migration does not justify deleting independently managed or local-corpus data; warn and skip collisions.
12. **Confusing distributable code with installed runtime state.** Verify the real destination index after linking and reloading before saying the migration is active.
13. **Using non-portable shell regexes.** Test helper scripts on the actual host and prefer deterministic parsing over BSD/GNU-sensitive expressions.
14. **Letting URL-scheme syntax fall into an SCP parser.** Reject unsupported `*://` schemes before handling `user@host:path`; otherwise `file://` and similar inputs can be accepted as fake forge hosts.
15. **Treating an early probe as final verification.** After the last helper-script edit, run a fresh OS-safe temporary verifier with positive and negative fixtures, clean it up, and label the result ad-hoc when no canonical suite exists.
16. **Editing a delegated path before its worker finishes.** Partition ownership, wait for completion, then inspect and amend the consolidated diff.

## Verification Checklist

- [ ] Skills, references, agents, hooks, schedules, and distribution config inventoried
- [ ] Every candidate structurally validated
- [ ] Native destination overlap assessed
- [ ] Stable policy separated from stale project/profile state
- [ ] Source-specific tools, paths, models, and commands mapped
- [ ] Public and destructive actions explicitly gated
- [ ] Scheduled-task assumptions checked against original sources
- [ ] Target library organized around class-level umbrellas
- [ ] Symlink setup preserves real directories and foreign links
- [ ] External-directory and name-precedence behavior understood
- [ ] Repository validation and runtime activation verified separately
- [ ] Migrated skills and support files loaded and exercised

## References

- `references/hermes-porting-checklist.md` — concise Hermes-oriented mapping and audit checklist.
- `references/shared-distribution-and-portability.md` — collision-safe symlink distribution, repository-versus-runtime completion gates, portable forge parsing, and multi-agent edit discipline.
- `references/git-backed-runtime-assets.md` — selective Git protection for authored skills, scripts, and automations stored beside mutable runtime state.