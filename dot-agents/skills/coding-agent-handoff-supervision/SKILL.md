---
name: coding-agent-handoff-supervision
description: Use for supervised Claude handoffs, including Herdr panes.
version: 1.1.4
author: Bryan Thompson + Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [coding-agents, handoff, supervision, claude, herdr, design-preview]
    related_skills: [cross-machine-coding-agent-handoffs, subscription-coding-worker-governance, claude-code]
---

# Coding Agent Handoff Supervision

## Overview

Hand approved implementation to Claude Code, Codex, OpenCode, or another coding
worker while the parent remains responsible for supervision, review, and
delivery. For Bryan, a Claude handoff made from inside Herdr is visible by
default: launch it in a sibling pane without changing the active window,
workspace, tab, or pane, and keep a completion watcher attached to the parent.

## When to Use

Use when a parent agent delegates implementation or review to a coding worker
but still owns acceptance and delivery.

Do not use for a self-contained reasoning subtask whose result needs no visible
terminal, branch inspection, or independent verification.

## Procedure

### 1. Brief the outcome, not an imagined implementation

Make implementation handoffs concept-led. State:

- the approved behavior, idea, or layout;
- the exact repository and base;
- authoritative product or visual references;
- only compatibility, safety, and publication outcomes that are load-bearing;
- the worker's publication authority.

Let the worker inspect repository guidance, trace consumers, research current
tool behavior, choose files, and determine implementation and verification.
Do not invent hard constraints, file lists, commands, architecture, or
exclusions merely to make the brief look complete.

**Complete when:** the worker can identify the approved result, source context,
and publication boundary without being handed an imagined implementation.

### 2. Choose the visibility path

For a Claude handoff, use the Herdr-native path when `HERDR_ENV=1` unless Bryan
explicitly asks to keep the worker in the background. Split the exact caller
pane to the right with `--no-focus`, then start and prompt Claude without
changing the active window, workspace, tab, or pane. Start a tracked watcher;
focus the worker only when Bryan explicitly asks to see it.

Read `references/herdr-claude-handoff.md` for the exact discovery, non-focusing
dispatch, monitoring, continuation, failure, and cleanup sequence.

When the parent is outside Herdr, Herdr control is unavailable, or Bryan asks
for background-only work, use a named Claude Agent View session instead. Read
`references/claude-agent-view.md` for that fallback.

**Complete when:** the worker's session identity, repository, name, pane or
background row, and working state are verified, and a promised completion
notification has a real watcher.

### 3. For design-driven handoffs, promote one direction

Exploration pages may contain intentionally competing variants. Once Bryan
selects one, create a dedicated preview containing only that direction. Retain
useful adaptive controls, remove competing designs, and verify the page through
the network path Bryan actually uses.

Give the worker the dedicated link as design intent, not a pixel-perfect
contract. Read `references/design-preview-handoff.md` for the promotion and
reachability checklist.

**Complete when:** the worker receives one reachable approved direction rather
than a gallery it must interpret.

### 4. Treat worker completion as a claim

After the worker finishes:

1. Inspect the actual branch, commits, diff, and working tree.
2. Disposition its questions and recommendations against the approved concept.
3. Independently run the relevant validation and focused runtime probes.
4. Verify publication and remote readback separately.
5. Activate or reload the live system only after accepting the candidate.
6. Read back the live target before declaring completion.

A `done` or `idle` status proves only that the worker settled. It does not prove
the implementation is acceptable.

**Complete when:** every acceptance criterion is independently verified against
the candidate and, where applicable, the live target.

### 5. Continue the same worker

Send follow-ups through the existing Herdr agent name or original Claude
session. Do not launch another row or pane when continuity is intended. Text
already visible in a worker's prompt box may be an automatic suggestion; never
submit it without the user's direction.

**Complete when:** the original session identity returns to `working` after the
follow-up, with no duplicate worker created.

### 6. Clean up after acceptance

After merge, publication readback, and live verification:

- stop or close only the worker session or pane created by this handoff;
- remove its disposable worktree and merged feature branch when appropriate;
- stop disposable preview servers;
- preserve unrelated local edits;
- finish with the canonical branch clean and current.

Do not close a foreground Herdr pane while Bryan may still be using it.

## Common Pitfalls

1. **Splitting Herdr's globally focused pane.** Target the injected
   `HERDR_PANE_ID`; Bryan may be viewing another tab while the handoff is built.
2. **Stealing Bryan's focus.** Pane creation, startup, prompting, and updates
   must preserve his active window, workspace, tab, and pane. Run `agent focus`
   only after an explicit request to see that worker.
3. **Calling visibility monitoring.** A visible worker still needs a tracked
   `herdr agent wait` or equivalent watcher when the parent promises follow-up.
4. **Resolving Herdr through shell `PATH`.** Foreground and background shells
   may select an older client. Require the pane-injected `HERDR_BIN_PATH`, gate
   on `compatible: yes`, and use that inherited absolute path for every command.
5. **Over-constraining the worker.** Describe the approved result, not a guessed
   implementation plan.
6. **Starting a duplicate for corrections.** Continue the original Herdr agent
   or Claude session.
7. **Treating suggested prompt text as authorization.** Submit only user- or
   parent-authored instructions.
8. **Trusting worker-reported tests or pushes.** Independently inspect and verify.
9. **Cleaning before checking for unrelated edits.** Preserve user work and close
   only resources created by the handoff.

## Verification Checklist

- [ ] Brief states outcome, repository/base, references, and authority
- [ ] Herdr path used when available unless background-only was requested
- [ ] Exact caller pane targeted and new pane ID parsed from Herdr JSON
- [ ] Worker identity, cwd, session ID, and `working` state verified
- [ ] Active window, workspace, tab, and pane preserved unless focus was requested
- [ ] Tracked watcher uses the verified Herdr client and a finite timeout
- [ ] Follow-ups preserve the original session
- [ ] Candidate independently reviewed and tested
- [ ] Publication and live state read back separately
- [ ] Only handoff-owned resources cleaned up after acceptance
