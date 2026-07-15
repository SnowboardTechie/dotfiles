---
name: loop-issue
description: "Use when working one queued ready-for-agent issue under bounded autonomous-loop policy, either interactively or from a pre-authorized schedule."
version: 2.0.0
author: Bryan Thompson
license: MIT
metadata:
  hermes:
    tags: [issues, automation, cron, draft-pr]
    related_skills: [issue-work, ship]
---

# Loop Issue

## Overview

Work exactly one `ready-for-agent` issue through `issue-work`, then stop. A
successful supervised run may leave a draft PR for human review. This skill
never merges and never recursively schedules itself.

The wake mechanism is separate: a user invocation, an external loop, or a
Hermes cron job can start a run. Keeping one issue per run bounds failures and
makes every result attributable.

## When to Use

- Work a named queued issue under the repository's autonomous-work policy.
- Select the oldest open `ready-for-agent` issue in the current repository.
- Use as a self-contained Hermes cron prompt after publication permissions are
  explicitly chosen.

Run inside the target repository so its context instructions and gate are
available.

## Authorization Modes

### Supervised

The user is present. `issue-work` may ask for plan and publication approval.
Public comments, relabeling, pushing, and draft PR creation still require the
normal approval gates.

### Unattended

A cron-run agent cannot ask questions. The cron prompt must explicitly state
which external actions, if any, Bryan pre-authorized. Authorization must name
the repository and action class; "run autonomously" alone is insufficient.

Without explicit publication authorization, an unattended run may inspect and
work locally, but it must not:

- comment or relabel an issue;
- push a branch;
- create or update a PR;
- send any other public-facing communication.

Instead, deliver a local blocker or ready-to-publish report for Bryan.

## Procedure

1. **Pick one issue.** Use an explicit issue reference when supplied. Otherwise,
   query the current forge for the oldest open `ready-for-agent` issue. Use
   `gh` on GitHub or authenticated `tea api` on Forgejo. If none exists, report
   `queue empty` and stop.
2. **Run `issue-work`.** Preserve its intake, worktree, plan, implementation,
   verification, and self-review gates. Unattended mode must stop rather than
   invent an answer to a load-bearing ambiguity.
3. **Enforce acceptance criteria.** Every acceptance criterion and repository
   test/lint/typecheck/format gate must be satisfied before publication is even
   proposed.
4. **Choose the authorized finish:**
   - Green + supervised approval or explicit unattended publication authority:
     use `ship` to create a draft PR, then stop.
   - Green but publication not authorized: report the branch, checks, proposed
     PR title/body, and exact next action; do not push.
   - Blocked or red: report the blocker locally. Commenting and changing
     `ready-for-agent` to `needs-human` are separate public actions and happen
     only after approval or explicit cron authorization.
5. **Stop after one issue.** Do not invoke another issue and do not create a new
   schedule.

## Forge Notes

Use `ship/references/forge-detection.md` for forge parsing. On Forgejo, create a
real draft with the API's `draft: true` field and read it back. Do not silently
substitute a `WIP:` title; if the instance cannot create drafts, stop and report
that limitation.

## Result Contract

Return exactly one of:

- `queue empty`;
- a clickable draft PR URL plus verified gate summary;
- a ready-to-publish local branch/report;
- a blocker report with the issue link and proposed public follow-up.

## Common Pitfalls

1. **Draining the queue inside the skill.** One invocation means one issue.
2. **Treating cron execution as publication approval.** External writes require
   explicit action-specific authorization.
3. **Opening a red PR.** A failed required gate blocks publication.
4. **Auto-commenting on failure.** Prepare the comment, but do not post it
   without authorization.
5. **Merging.** Human review and merge remain outside this skill.

## Verification Checklist

- [ ] Exactly one issue selected
- [ ] Repository instructions and acceptance criteria loaded
- [ ] Authorization mode identified
- [ ] Required gates green before any publication
- [ ] Every external write was explicitly authorized
- [ ] Result uses a clickable issue/PR link
- [ ] Run stopped without recursive scheduling
