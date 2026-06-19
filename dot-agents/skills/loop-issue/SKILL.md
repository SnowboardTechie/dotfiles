---
name: loop-issue
description: Use when working a queued backlog issue under autonomous-loop policy and you don't want to re-specify the rules each time — invoked as /loop-issue [issue-ref], as the body of /loop to drain a queue, or from a schedule. Triggers: "work the next ready-for-agent issue", "run the issue loop", "drain the ready-for-agent queue", "loop-issue".
---

# loop-issue

## Overview

Work ONE `ready-for-agent` issue end-to-end, then stop — leaving a **draft PR** for a human to merge. This is the goal-scoped-task half of an agent loop; the *wake trigger* (you typing it, `/loop`, or a schedule) is separate and not this skill's job. Thin wrapper over the `issue-work` skill that adds loop policy: discover the issue, draft-PR-only, never merge, route failures to a human.

**The gate lives in the issue, not here.** Every well-formed issue's acceptance criteria already name the repo's check gate (tests, lint, format). So this skill needs no per-repo config and ports to any repo unchanged.

## When to use

- Hand the agent an issue without re-typing the loop rules: `/loop-issue 42`
- Let it pick the work itself: `/loop-issue` (no arg → oldest open `ready-for-agent` issue in the current repo)
- As the body of a `/loop` (drain the queue) or a scheduled run (hands-off)

Run it from **inside the target repo** — it reads the git remote to choose host + CLI.

## Procedure

1. **Pick the issue.**
   - Arg given (number / `owner/repo#N` / URL) → that's the target.
   - No arg → find the **oldest open** issue labeled `ready-for-agent` in the current repo. Detect host from `git remote get-url origin`:
     - Forgejo/Gitea (e.g. `codeberg.org`, `git.snowboardtechie.com`) → `tea issues ls --state open --labels ready-for-agent`; take the lowest number. If `tea` errors with `worktreeconfig`, re-run it from a non-repo dir (`cd /`).
     - `github.com` → `gh issue list --state open --label ready-for-agent`; take the oldest.
   - **None found → report "queue empty" and STOP.** Do not schedule another wake.

2. **Work it** with the `issue-work` skill (hand it the issue URL/ref). issue-work creates a worktree, plans, implements, runs tests, and self-reviews.

3. **Enforce loop policy before finishing:**
   - **Gate:** satisfy *every* acceptance-criteria checkbox. The full check gate named in the ACs (tests + lint + format) must be **green** before any PR.
   - **Draft only, never merge:** open a **draft** PR that links the issue, then stop. A human owns the merge gate — always, every repo, even once you trust the loop.
   - **Failure path:** if you can't get the gate green, the issue is bigger than its "tightly bounded" scope, or you hit genuine ambiguity → do **NOT** open a PR. Comment the specific blocker on the issue, relabel `ready-for-agent` → `needs-human` (via `tea`/`gh`), stop working it.

4. **Report:** the issue worked + draft-PR URL, or the `needs-human` relabel + the reason.

## Quick reference

| Invocation | Behavior |
|---|---|
| `/loop-issue 42` | Work issue 42 |
| `/loop-issue` | Work the oldest open `ready-for-agent` issue; "queue empty" → stop |
| `/loop /loop-issue` | Drain the whole `ready-for-agent` queue, one draft PR each |

| Host | Issue CLI |
|---|---|
| codeberg.org, Forgejo/Gitea | `tea` (run from `/` if it errors on `worktreeconfig`) |
| github.com | `gh` |

**Draft PR per host:** GitHub → `gh pr create --draft`; Forgejo/Gitea → prefix the PR title with `WIP:` (`tea` has no draft flag, so `WIP:` is how a PR stays un-mergeable).

## Common mistakes

- **Opening a non-draft PR or merging.** Never. Draft-only; the human merges.
- **Opening a PR with a red gate.** If checks aren't green, it's the failure path (comment + `needs-human`), not a PR.
- **Looping inside the skill.** This skill does ONE issue and stops. Draining/scheduling is the trigger's job (`/loop`, cron) — keep the seam clean.
- **Forgetting the approval pause:** `issue-work` pauses for plan approval. Under supervision (Stage 0) that's the point — approve each. For unattended `/loop` or scheduled runs you must pre-authorize / auto-accept, or it stalls waiting.
