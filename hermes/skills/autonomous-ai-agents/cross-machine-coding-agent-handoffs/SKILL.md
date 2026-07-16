---
name: cross-machine-coding-agent-handoffs
description: Prepare, deliver, and independently review coding-agent work when the authoring agent and reviewer may run on different machines.
version: 1.1.0
metadata:
  hermes:
    tags: [coding-agents, handoff, cross-machine, review, git, knowledge-sync]
---

# Cross-machine coding-agent handoffs

Use this skill when preparing a coding prompt for Claude Code, Codex, OpenCode, or another implementation agent whose filesystem may not be shared with the reviewing agent.

The handoff is complete only when the reviewer can fetch the artifact, reproduce the checks, and distinguish verified state from the implementation agent's self-report.

## 1. Refresh durable context before writing the prompt

When the project has a canonical notes vault, status page, implementation plan, or decision record:

1. Read the live source first: repository state, relevant issues/PRs, decisions, and current branches.
2. Reconcile the related canonical notes. Do not append a new note while leaving the index, status page, or active plan contradictory.
3. Commit and push the note updates before drafting the coding-agent prompt.
4. Treat this as a pre-handoff freshness gate, not a requirement to edit notes after every conversational turn.

The coding agent should start from synchronized context it can actually read.

## 2. Make the task self-contained

A good implementation prompt names:

- repository and exact base branch or SHA;
- the user-visible bug or desired behavior;
- scope boundaries and explicitly excluded adjacent work;
- authoritative examples or prior commits that are references rather than wholesale cherry-pick targets;
- required tests, static checks, downstream consumer checks, and expected failure modes;
- whether the agent may edit, commit, push, or open a PR;
- what to do when credentials, live API keys, or other external prerequisites are unavailable.

For narrow release fixes, require the agent to trace semantic consumers of changed metadata before declaring the change local. A small file diff can still change generic reflection, serialization, schema, or transform behavior elsewhere.

## 3. Require a reachable artifact

If authoring and review may happen on different machines, include these delivery rules in the prompt:

1. Work on a dedicated branch from the named base.
2. Commit the completed, tested work.
3. Push the branch to the agreed remote after tests pass.
4. Do not open a PR unless explicitly requested; pushing a review branch and publishing a PR are separate actions.
5. Report branch name, commit SHA, base SHA, files changed, commands run, results, and blockers.

A local worktree path plus an unpushed commit SHA is not a usable cross-machine handoff.

## 4. Independently review the result

Do not approve from the agent's summary alone.

1. Fetch the pushed branch by name and verify the reported commit and ancestry.
2. Review the full diff against the exact base.
3. Read changed files in surrounding context.
4. Trace definitions and every semantic consumer affected by changed field metadata, configuration, aliases, annotations, schemas, or reflection state.
5. Run focused tests and the project's full relevant gate.
6. Reproduce critical compatibility claims with a minimal before/after probe when practical.
7. Separate implementation correctness from unavailable external verification. A missing live credential may block an end-to-end call without invalidating local tests, but the gap must remain explicit.

See `references/pydantic-alias-migration-review.md` for a concrete metadata-consumer review pattern.

## 5. Reconcile late delivery-direction changes

A technically correct branch is not automatically the right artifact to ship. Review comments, maintainer clarification, or release sequencing may change the delivery vehicle after implementation has started.

When that happens:

1. Re-read the maintainer's exact direction and separate **technical correctness** from **accepted release scope**.
2. Inspect the lower layer that the maintainer named (consumer plugin, adapter, config, docs, or call site) rather than assuming the upstream/library fix must still land.
3. In a disposable worktree, test the smallest compliant workaround against the exact intended base and dependency versions. Run both static checks and runtime/wire assertions when aliasing, serialization, or reflection is involved.
4. If the narrower route passes, park the broader branch without opening a PR. Preserve its branch/SHA and verification record for the follow-up rather than deleting or silently merging it.
5. Update canonical notes and the release sequence so later agents do not revive the superseded delivery plan.
6. Report both truths: whether the parked work is technically sound, and why it is not being delivered now.

Read `references/release-scope-reconciliation.md` for a concrete consumer-workaround verification pattern and status vocabulary.

## 6. Review output

Lead with the verdict:

- **Approved**: no blocking findings.
- **Changes requested**: identify the concrete regression and required fix.
- **Blocked**: artifact or prerequisite is unavailable.

For each finding include:

- severity;
- path and line or symbol;
- the broken behavior;
- a reproduction or evidence;
- the narrowest acceptable correction.

Then list checks independently rerun and distinguish them from checks reported only by the authoring agent.

## Pitfalls

- Drafting the coding prompt before synchronizing notes, leaving the agent with stale release state.
- Saying “do not push” when a different machine must review the work.
- Treating branch push and PR creation as the same permission boundary.
- Trusting “all usages traced” without searching generic helpers and reflection-based consumers.
- Verifying only direct model behavior while missing callers that inspect field metadata.
- Claiming static regression coverage from a scratch file that is not part of the committed CI surface.
- Continuing toward a technically clean upstream PR after a maintainer has redirected the release fix to a consumer or plugin.
- Testing a workaround in a disposable tree, then reporting as though the real branch was changed or pushed.
- Turning a transient credential or installation problem into a permanent workflow restriction.

## Completion checklist

- [ ] Canonical context reviewed, reconciled, committed, and pushed before prompt drafting
- [ ] Base branch/SHA and scope boundaries named
- [ ] Required verification and external blockers named
- [ ] Agent instructed to commit and push the branch
- [ ] PR creation permission stated separately
- [ ] Reviewer fetched the pushed artifact and verified ancestry
- [ ] Full diff and semantic metadata consumers reviewed
- [ ] Focused and full relevant checks rerun independently
- [ ] Before/after compatibility probe run for risky behavior changes
- [ ] Late maintainer/release feedback reconciled with the chosen delivery vehicle
- [ ] Any parked branch recorded by branch/SHA without opening an unrequested PR
- [ ] Consumer workaround, when chosen, verified statically and at runtime in a disposable worktree
- [ ] Final verdict distinguishes observed results from agent self-report
