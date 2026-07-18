---
name: skill-retrospective
description: Use after chats with repeated workflow friction.
version: 1.0.0
author: Bryan Thompson + Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [Skills, Retrospective, Workflows, Learning]
    related_skills: [vault-capture]
---

# Skill Retrospective

## Overview

Review a completed conversation for evidence-backed improvements to procedural
knowledge. Contrast failed and successful paths, then decide whether to patch an
existing skill, create something new, route the learning elsewhere, or capture
nothing.

**Core rule:** a long conversation is not evidence that a skill is needed. A
candidate must identify a reusable trigger, an exact change to future behavior,
and a way to verify that change.

The foreground audit does not call mutation tools until the user approves named
candidates.

## When to Use

Use at a natural stopping point when the user asks what the agent should learn
from the conversation, mentions loops or repeated friction, or requests
candidates for new or existing skills.

Also use for a supplied transcript or prior-session reference.

Do not use when:

- The user already identified one proven procedure and only wants it authored.
- The main result belongs in a knowledge vault. Use `vault-capture`.
- The task is still in progress and more evidence is likely.
- A loaded skill is already known to be stale or wrong and host policy requires
  an immediate patch. Fix it during the task instead of postponing it.

## Relationship to Hermes Learning

This skill complements rather than replaces Hermes's native learning features:

- `/learn` packages one already-understood workflow into a new user-local skill.
- The background self-improvement review periodically considers skills and
  memory with a restricted tool set.
- The curator manages lifecycle and optional consolidation of agent-created
  skills.
- This skill performs a user-invoked, transcript-grounded audit, checks project
  sources and existing skills, and presents a candidate slate before writing.

## Promotion Tests

Default to no action. Every candidate must have transcript-backed evidence,
generalize beyond accidental identifiers, change future behavior at a clear
trigger, define verification, avoid duplication, and exclude sensitive or
volatile state.

Then apply the gate for its proposed destination:

| Destination | Minimum evidence |
|---|---|
| Existing skill patch | The current artifact is missing or contradicts needed guidance, and the corrected path is evidenced |
| User memory | An explicit stable preference or durable environment fact should affect behavior across sessions |
| Project instructions | A repository or team invariant has a canonical project owner and should apply whenever work occurs there |
| New skill | A verified non-obvious class-level procedure has a stable trigger, no suitable existing owner, and either recurrence across episodes or an explicit user request |
| Vault or automation | The observation meets that destination's own capture or change-management gate |

Repeated loops, user corrections, verified recovery, and repeatedly rediscovered
prerequisites raise confidence but do not replace the destination gate. Decline
one-off facts, generic advice, transient failures, unverified theories, task
progress, and successful trajectories whose method was not shown to cause the
success.

## Workflow

### 1. Establish the evidence boundary

Use the current visible conversation by default, including user corrections,
tool failures, successful results, and verification.

When the user provides a transcript, URL, or session reference, inspect that
direct source first. In Hermes, resolve `@session:<profile>/<id>` with
`session_search`; use discovery search only for broad cross-session questions or
to corroborate a borderline candidate. A search hit is not evidence until its
actual messages are read in context.

If compression, missing tool output, or an unavailable source limits coverage,
say so. Never reconstruct absent events from the final summary alone.

Analyze the source in the current agent. Do not delegate the core audit unless
the full transcript is explicitly passed to the child; subagents do not inherit
the parent conversation. Delegation is acceptable for an independent overlap
check once candidate details and target files are supplied.

**Complete when:** the response can state exactly which conversation material
was and was not reviewed.

### 2. Build a friction ledger

Privately inventory the consequential sequence before suggesting changes:

- user steering, corrections, and repeated clarification;
- commands or tool calls repeated without new evidence;
- prerequisites discovered only after failed attempts;
- guessed APIs, flags, paths, or capabilities;
- premature completion followed by missing verification;
- handoffs that lost scope, decisions, or source links;
- the final successful path and the checks that proved it.

Distinguish an **unproductive loop** from a **diagnostic loop**. Hypothesis,
test, new evidence, and refinement is productive iteration. Repeating the same
action or assumption without new evidence is friction.

For each meaningful observation, retain a concise transcript anchor, impact,
root cause if established, successful alternative, and expected reuse horizon.
Do not paste raw secrets or large tool output into the ledger or final slate.

**Complete when:** every claimed pattern has direct evidence and the successful
path, if any, is separated from failed attempts.

### 3. Generate minimal candidates

Turn an observation into a candidate only if it passes the promotion tests.
Write its behavioral delta as:

> When **trigger**, perform **changed behavior**, then verify **observable
> result**.

Prefer the smallest change that prevents the observed friction. A missing
pitfall in an existing skill is usually a patch, not a new sibling skill. A
repeated deterministic sequence may belong in a script or template rather than
more prose.

Reject candidates that merely say "be careful," restate generic engineering
practice, preserve version-specific syntax without a discovery step, or encode
negative capability claims from one failed environment.

**Complete when:** every retained candidate has a trigger, behavior change,
verification, evidence strength, and root-cause rationale.

### 4. Inspect existing destinations before proposing a new skill

Inventory installed and project-local skills by name and description, then read
the full content of the closest matches. Search project instructions and the
canonical shared skill pool where relevant. Do not infer overlap from names
alone.

For each candidate, choose one primary destination:

| Destination | Use when |
|---|---|
| Existing skill patch | A current workflow owns the trigger but lacks or contradicts the needed behavior |
| Existing skill support file | The umbrella is correct but needs bulky reference, template, or deterministic script |
| New skill | A distinct recurring task class has its own trigger, procedure, and verification, with no suitable owner |
| User memory | A stable cross-task preference or environment fact changes behavior broadly |
| Project instructions | The rule is specific to one repository, product, or team |
| Vault capture | The learning is durable domain knowledge, a decision, or project context rather than agent procedure |
| Automation | The real need is a repeated schedule or machine-enforceable check |
| No action / defer | Evidence is weak, transient, still unverified, or accurately encoded in an artifact that will be reliably retrieved |

Prefer one source of truth. Dual-write only when the destinations serve genuinely
different retrieval scopes, and state which one owns the procedure.

For a new-skill candidate, search the local library first and the community
catalog only if useful. Installation or publication remains a separate action.

**Complete when:** each candidate has a proposed target or an explicit reason to
decline it, plus an overlap assessment based on full content.

### 5. Present the candidate slate and stop

Use a compact table:

| ID | Evidence and root cause | Recommendation and exact target | Exact future behavior | Confidence |
|---|---|---|---|---|

Then include:

- **Proposed delta:** exact patch text or a sufficiently exact new-artifact
  preview, every affected file or manifest, and planned validation.
- **Declined or deferred:** plausible observations that failed the promotion
  tests and why.
- **Evidence limits:** omitted or compressed material that could change the
  judgment.
- **Privacy/redactions:** sensitive source material excluded from the proposal.
- **Approval ask:** request the IDs the user wants implemented or investigated.

The foreground retrospective does not create, patch, install, publish, commit,
push, or write memory from a slate. A broad "capture anything useful" is not
item-level selection. If the user explicitly overrides the slate gate for a
named change, follow that instruction and host safety policy.

Hermes's optional `skills.write_approval` staging is useful defense-in-depth,
but it is off by default and does not replace this slate-and-approval boundary.
Guaranteeing no independent background skill or memory writes requires staging
or disabling those host features separately; never change those settings as a
side effect of this retrospective.

If nothing qualifies, say so directly. A zero-candidate slate is a successful
outcome.

### 6. Implement only approved candidates

For each approved ID:

1. Re-read the target and its supporting files to avoid a stale patch. If the
   target drifted after approval, show the revised delta and ask again rather
   than adapting silently.
2. Load the runtime's authoring workflow. In Hermes, use
   `hermes-agent-skill-authoring` and treat current Hermes documentation as the
   source of truth.
3. Use host-native equivalents for session retrieval, skill discovery,
   mutation, and approval. If a host lacks durable memory or prior-session
   retrieval, report that route as unsupported rather than inventing storage.
4. Confirm the canonical writable source. Patch a tracked or shared source
   rather than a generated symlink. For bundled or hub-installed skills,
   default to the upstream/source artifact and disclose update-lifecycle
   consequences before patching an installed copy. Resolve shadowed duplicates
   before approval.
5. Patch existing content in place and remove superseded wording. Create a new
   skill only after overlap has been ruled out.
6. Update distribution lists, indexes, or symlink wiring when the canonical
   skill pool requires them.
7. Validate frontmatter, links, supporting files, and the exact behavior delta.
8. Exercise the trigger in a fresh session or representative scenario and
   inspect the response, not merely whether the file loaded.

Approval to edit a skill is not approval to commit, push, publish, install a
community package, or perform another externally visible action. Obtain whatever
separate authorization the host and repository require.

**Complete when:** each approved change is behaviorally tested and reported per
artifact as **saved**, **staged/pending**, **blocked**, or **failed**, with its
verification evidence.

## Common Pitfalls

1. **Length implies reuse.** Long sessions often contain necessary exploration.
   Apply the promotion tests instead.
2. **Hindsight storytelling.** Do not claim a root cause the transcript never
   established.
3. **One session, many narrow skills.** Prefer an existing umbrella or one
   class-level abstraction.
4. **Skipping full overlap review.** A name list cannot reveal a missing section
   in an existing skill.
5. **Capturing task residue.** IDs, temporary paths, outputs, progress, and
   current failures do not belong in a skill.
6. **Losing the successful path.** A failure is useful only when paired with the
   correction and verification that should replace it.
7. **Mutating during the audit.** Present the slate before reaching for authoring
   or memory tools.
8. **Testing file presence only.** Verify future agent behavior in a fresh
   context.

## Verification Checklist

- [ ] Evidence boundary and limitations are explicit
- [ ] Productive diagnostic iteration was not mislabeled as friction
- [ ] Every candidate passes the promotion and behavioral-delta tests
- [ ] Closest existing skills were read in full
- [ ] Each candidate has one primary destination
- [ ] Declined and deferred observations are visible
- [ ] The foreground audit invoked no mutation before candidate approval
- [ ] Approved changes were validated and behaviorally exercised
- [ ] Every artifact is reported as saved, staged/pending, blocked, or failed
- [ ] Secrets and session-specific residue were excluded
