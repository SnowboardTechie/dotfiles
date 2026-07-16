---
name: vault-pkm
description: Use when recalling, exploring, planning, or capturing durable knowledge in a personal or project Markdown/Obsidian vault. Enforces look-first context gathering, per-vault instructions, atomic linked notes, explicit capture boundaries, and lightweight experimentation instead of imposing unused PKM machinery.
version: 1.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [pkm, obsidian, vaults, atomic-notes, knowledge-management]
    related_skills: [obsidian]
---

# Vault PKM

## Overview

Treat a vault as a living knowledge system, not a generic folder of Markdown files. First understand its local structure and prior thinking; then help the user reason; finally leave a durable, linked artifact only when the work reaches a useful resting point.

The user is the author. The agent is a collaborative researcher and writer: concise and direct by default, willing to explain connections, challenge weak assumptions, surface concerns, and propose worthwhile ideas without flattery.

## When to Use

Load this skill when:

- Reading, searching, recalling, creating, or editing notes in a personal or project vault.
- Capturing decisions, investigations, learnings, plans, or project context that belongs outside code.
- The user refers to `~/second-brain`, a project `vault/`, Obsidian, atomic notes, PKM, evergreen notes, daily notes, or weekly planning.
- A task may benefit from connecting current work to prior decisions or knowledge in a vault.

Do not use it merely because a repository contains incidental Markdown documentation. Use repository-specific development skills for code docs unless the material is explicitly part of a knowledge vault.

## Core Workflow

### 1. Resolve the actual vault

Determine the concrete vault path from the user, project context, or environment. Do not assume that an Obsidian default path is authoritative when the user names a direct path.

**Completion criterion:** one concrete vault root has been identified.

### 2. Read local instructions before touching notes

Look for `AGENTS.md` at the vault root. For project vaults, inspect `vault/AGENTS.md`; for a personal vault, inspect its root instructions. These local instructions override generic conventions in this skill.

Pay attention to:

- Allowed note types and capture thresholds.
- Folder and filename rules.
- Frontmatter, tags, status values, and templates.
- Linking conventions.
- Git commit/push requirements.
- Explicitly abandoned workflows or machinery.
- Privacy and publication boundaries.

**Completion criterion:** local rules are known, or their absence is explicit.

### 3. Look first

Before answering a recall question or writing a note, search filenames and contents for:

- The topic and likely synonyms.
- Existing index/MOC notes.
- Related projects, people, tools, decisions, and prior explorations.
- Existing notes the new material should extend instead of duplicate.
- Contradictions between the current request and prior recorded decisions.

Read a small set of representative notes rather than inferring the vault style from filenames alone. For a new vault, sample at least one central/project note and, when present, one decision and one exploration.

**Completion criterion:** the response or draft is grounded in relevant existing notes, or the search found none after trying reasonable synonyms.

### 3a. Validate plans against authoritative local sources

When the vault contains a relevant manual, standard, datasheet, policy, contract, or other primary source, read it directly before confirming an existing plan. A vault note may contain prior interpretation, transcription errors, variant confusion, or advice that is sensible but not source-required.

Validate claim by claim and distinguish:

- What the source explicitly requires.
- What is merely consistent with the source.
- What is an extra-conservative practice for the situation.
- What conflicts with a specification, interval, procedure, or replacement rule.

Check the exact model, year, version, jurisdiction, and any supplements. Preserve the difference between qualitative evidence and a source-prescribed test: do not turn “it rotates and produces some compression” into a factory compression pass without the specified test conditions. Likewise, distinguish prerequisites for a controlled diagnostic operation from prerequisites for safe real-world use.

For the detailed source-check method, PDF extraction pattern, and validation pitfalls, read `references/authoritative-source-validation.md`. When the user asks to apply the findings, also read `references/authoritative-source-reconciliation.md`: it covers propagating corrections across the hub/MOC, work log, procedures reference, and shopping list; converting source findings into actionable gaps; removing stale paraphrases and duplicate tasks; and invalidating totals made misleading by new requirements.

**Completion criterion:** the verdict identifies both confirmations and corrections, cites the applicable source sections, and labels non-source additions honestly. If edits were requested, every canonical project surface is consistent and a post-edit search finds no superseded guidance.

### 4. Think before capture

Do not turn every exchange into a note. Work the problem conversationally first. Capture when one of these boundaries is reached:

- A problem has reached a useful stopping point.
- A decision was made and its reasoning should survive.
- A sharp idea is worth preserving for later.
- The user explicitly asks to capture something.

If local instructions define note types, use them. If capture type remains genuinely ambiguous and changes the destination or shape, ask one concise question.

**Completion criterion:** the intended artifact type and purpose are clear.

### 5. Name the artifact before writing

State the proposed note type and concrete vault-relative path before writing unless the user already supplied both. Never silently create notes mid-conversation.

For edits, name the existing note and the section or change being made.

**Completion criterion:** the user can see where durable content will live before the write occurs.

### 6. Write vault-native material

Follow the local note shape exactly. In the absence of local rules:

- Prefer one central idea per note.
- Use a descriptive title that remains understandable out of context.
- Record provenance, date, status, or tags only when the vault already uses them.
- Explain reasoning and trade-offs, not just conclusions.
- Link to existing notes with vault-native wikilinks.
- Keep wikilinks inside the current vault. For material in another vault, name the source vault and quote or summarize it without creating a `[[wikilink]]` that cannot resolve locally.
- Add a short related-notes section when it improves navigation.
- Update an existing canonical note instead of creating a near-duplicate.

Do not introduce a new taxonomy, template system, plugin dependency, daily-note framework, or folder hierarchy as a side effect of a single capture.

**Completion criterion:** the note matches local conventions, has a clear purpose, and connects to relevant existing knowledge.

### 6a. Use compiled knowledge zones selectively

When a mixed personal vault contains a mature cluster of MOCs, references, project logs, explorations, and decisions, treat that cluster as a **compiled knowledge zone** rather than forcing the entire vault into an LLM-wiki schema.

- Make existing canonical roles legible; do not pre-create empty folders or pages.
- Prioritize orientation and trust: repair stale MOCs/indexes and unsupported consequential claims before normalizing metadata.
- Keep provenance proportional to consequence. Exact sources matter for safety, health, money, legal, specifications, and procedures; personal reflection does not need decorative citations.
- Lint the active zone and observed retrieval failures, not journals and archives merely because they are sparse.
- Reconcile a changed claim across every canonical sibling surface, then search the full zone for stale copies before declaring the correction complete.
- Put broad cleanup into an update-on-touch queue instead of churning the whole historical vault.
- Treat interoperability formats as an export concern until a real consumer exists.

Read `references/compiled-knowledge-zones.md` for the role model, audit workflow, proportional-provenance rules, targeted-lint scope, and post-edit verification sequence.

**Completion criterion:** the active zone has a clear route from its MOC, consequential claims are traceable at an appropriate level, sibling surfaces agree, and no global vault machinery was introduced without demonstrated need.

### 6b. Recompile agent-maintained project vaults

When agents directly maintain code-adjacent project vaults, capture is usually not the bottleneck. Watch for **recompilation debt**: detailed notes advance while the index, status page, topic MOCs, plans, and superseded decisions disagree.

Use a stricter source → compile → reconcile → verify loop:

- Treat live code, exact commits, issues/PRs, ADRs, and primary docs as source inputs; do not copy them wholesale into a `raw/` hierarchy.
- Check the index, status page, and relevant MOC before writing. New evidence must update canonical surfaces, not merely append another note.
- Distinguish observed current state, accepted decisions, proposals, historical state, and unverified inference.
- Classify each vault as active, dormant, or historical before normalizing it; do not cosmetically revive archived projects.
- Exclude unpromoted drafts and agent scratch from canonical lint.
- Keep cross-vault references explicit because local wikilinks do not resolve across vault boundaries.
- During vault-only work, inspect paired code repositories as read-only sources and preserve all pre-existing changes across repositories.
- For a transferred archive or machine migration, receive outside the active vault, inspect for unsafe members and expansion risk, extract to staging, reconcile imported and destination instructions, merge with explicit exclusions, and verify imported files by path and checksum. If the project workspace and notes vault are separate trees, inspect both destination paths first, migrate the large workspace resumably, and reconnect the one canonical vault by symlink. The detailed procedures are in `references/agent-compiled-project-vaults.md` under **Safe snapshot migration** and **Multi-repository workspace migration with an external vault**.

Read `references/agent-compiled-project-vaults.md` for the role model, safe snapshot and paired-workspace migration procedures, ingest loop, active/dormant/archive classification, targeted audit, cross-repo boundaries, and verification sequence.

**Completion criterion:** current canonical surfaces agree with verified live sources, historical artifacts point to the current conclusion without being rewritten, every new durable note has an inbound route, and unrelated working-tree content remains untouched.

### 7. Verify and synchronize

After writing:

- Read back the changed area.
- Check frontmatter and wikilink syntax.
- Confirm every modified file is inside the intended vault.
- Review the diff when available.
- Follow local git commit and push discipline exactly.
- Never publish, email, post, or otherwise make vault content public without explicit approval.

#### Default Git synchronization for Bryan's project vaults

Bryan treats Git synchronization as part of completing a non-draft vault update, not as a separate publishing action. Unless a vault-local rule says otherwise:

1. Fetch and confirm the vault branch can be updated safely; preserve unrelated tracked and untracked work.
2. Stage only the exact non-draft note paths changed for the task.
3. Run `git diff --cached --check`, commit with a concise vault-scoped message, and push.
4. Fetch again and verify local `HEAD` equals the remote branch SHA.
5. Leave `drafts/` uncommitted unless Bryan explicitly promotes or asks to commit the draft.

Do not wait for a separate commit/push request when Bryan asked to update non-draft project-vault notes and synchronization is safe. If synchronization is blocked by remote divergence or overlapping edits, preserve the work and report the blocker rather than forcing it.

#### Pre-handoff freshness gate

For this user's coding-agent handoffs, synchronization is a prerequisite to prompt drafting rather than an afterthought:

1. Review the live implementation/release sources and every related canonical vault surface.
2. Reconcile current state, accepted decisions, proposals, and superseded history.
3. Commit and push the note updates before writing the Claude/Codex/OpenCode prompt.
4. Cite the synchronized note paths or commit in the prompt when they help the agent orient.
5. Require an implementation agent on another machine to commit and push its completed branch for review; opening a PR remains a separate permission boundary.

This does **not** require notes to change after every conversational turn. Apply it at implementation-handoff boundaries and other meaningful resting points. For the full cross-machine artifact and review workflow, load `cross-machine-coding-agent-handoffs`.

When the vault branch is behind its remote and the working tree already contains edits:

1. Fetch before committing and inspect the incoming commits and overlapping paths.
2. Distinguish pre-existing local edits from remote changes already pushed by another session. Diff the working tree against `origin/<branch>`; when the same earlier edits are now upstream, that comparison isolates the still-local delta.
3. Preserve that delta, restore only the affected tracked paths, fast-forward, and reapply the delta. Do not use a blanket reset when unrelated tracked work exists.
4. Stage explicit paths. Leave unrelated untracked drafts and scratch directories untouched.
5. Verify the pushed remote SHA equals local `HEAD` and report any intentionally preserved untracked content.

**Completion criterion:** the artifact is readable, correctly located, linked, synchronized as required by the vault, and no concurrent or unrelated local work was absorbed into the commit.

## Recall Workflow

When asked what was previously decided, explored, or known:

1. Search the original vault first; conversation memory is secondary context, not proof of current vault contents.
2. Search both note metadata and prose because older notes may use different schemas.
3. Read the relevant note rather than summarizing from a search snippet.
4. If one note clearly answers the question, summarize it and provide its path.
5. If several notes matter, distinguish decision, exploration, and later updates; preserve links or paths.
6. Call out superseded decisions and revisit logs instead of presenting the oldest conclusion as current.

## Planning and Habit Experiments

A desire to capture more daily or weekly reflection does not automatically justify installing a planning system. First search for evidence of previous attempts and why they failed.

If the vault records that planning machinery went unused but the user wants to revisit the outcome, treat this as a design constraint rather than a contradiction:

- Preserve the prior learning.
- Offer the smallest reversible experiment.
- Time-box it and define what success looks like.
- Avoid new folder/template/plugin infrastructure until actual use earns it.
- Review the experiment before making it permanent.

See `references/lightweight-planning-experiments.md` for practical pilot shapes.

## Researching emerging workflow concepts

When the user asks to learn a workflow concept by reviewing both their projects and external sources, read `references/researching-workflow-concepts.md`. Search for the mechanism's older component terms—not only its current label—map the concept onto practices already present in the vault, and recommend the smallest risk-appropriate experiment rather than imposing new machinery.

## Collaboration Style

For this user's vault work:

- Lead with the result or key tension; keep routine narration short.
- Explain connections when they improve understanding.
- Challenge assumptions with evidence from the vault or external research.
- Surface honest gaps and counterarguments.
- Propose promising adjacent ideas, but distinguish them from the requested work.
- Be safely proactive with local, reversible research and drafting.
- Obtain approval before public-facing communication or significant destructive action.

## Common Pitfalls

1. **Writing before reading.** This creates duplicate or contradictory notes. Search and sample existing notes first.
2. **Treating every exchange as capture-worthy.** Wait for a resting point unless capture is explicit.
3. **Silently writing.** Name the note and path before creation or substantial editing.
4. **Imposing generic PKM doctrine.** Local conventions and demonstrated use beat fashionable systems.
5. **Reintroducing abandoned machinery.** Investigate why it failed and run a minimal experiment instead.
6. **Weak linking.** A polished isolated note is less useful than an adequately written connected one.
7. **Flattening decision history.** Preserve revisit triggers, later updates, and superseding decisions.
8. **Using memory instead of the source.** Search the vault first whenever it is accessible.
9. **Publishing by implication.** A vault may be private even when it is a Git repository; external communication always requires approval.
10. **Overexplaining the mechanics.** Do the research and present the useful result; detail the process only when it teaches something or affects trust.
11. **Only dogfooding an audit on the real vault.** Existing data may never exercise promised negative checks. Use a temporary synthetic fixture for each finding and exclusion, prove read-only behavior, and clean generated artifacts.
12. **Confusing the vault with its paired workspace.** A same-named archive may contain only notes while the actual project is a separate multi-repository tree. Inspect destination topology and archive contents first; stage large workspace transfers separately, then reconnect the one canonical vault by symlink. See `references/agent-compiled-project-vaults.md` § “Multi-repository workspace migration with an external vault.”

## Verification Checklist

- [ ] Concrete vault path resolved
- [ ] Vault-local `AGENTS.md` read when present
- [ ] Existing notes searched by topic and synonyms
- [ ] Representative related notes read
- [ ] Relevant primary sources read directly; exact variant/version confirmed
- [ ] Source-required, source-supported, extra-conservative, and source-conflicting claims distinguished
- [ ] Prior decisions and abandoned workflows reconciled
- [ ] Capture boundary reached or capture explicitly requested
- [ ] Note type and path named before writing
- [ ] Local filename, frontmatter, and note shape followed
- [ ] Relevant wikilinks added without duplicating a canonical note
- [ ] Changed content read back and checked
- [ ] Local synchronization discipline followed
- [ ] No public-facing or destructive action taken without approval
