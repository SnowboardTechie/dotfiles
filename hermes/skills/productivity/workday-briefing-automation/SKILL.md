---
name: workday-briefing-automation
description: Plan, implement, and tune recurring workday-morning briefings that synthesize notes, calendar, email, and engineering activity into a concise, read-mostly plan for the day.
version: 1.2.0
author: Hermes Agent
license: MIT
metadata:
  created_by: agent
  hermes:
    tags: [productivity, morning-brief, cron, calendar, email, github, pkm]
    related_skills: [vault-pkm, google-workspace, himalaya, hermes-agent]
---

# Workday Briefing Automation

## Overview

Use this skill to design or operate a recurring morning brief that answers three questions:

1. Where did work stop on the previous workday?
2. What constraints and preparation does today require?
3. What is the most valuable concrete outcome to pursue today?

A useful brief is a bounded decision aid, not a dashboard dump. Prefer read-only collection, explicit source authority, deterministic data gathering, and concise agent synthesis.

## Planning Workflow

### 1. Establish the decision the brief supports

Start with the user outcome, not the available integrations. A strong default is:

- Reconstruct the previous workday's resting point.
- Show today's meetings and usable focus windows.
- Surface only actionable messages, reviews, or failures.
- Recommend one primary outcome and one first action.

Do not add news, weather, broad inbox summaries, automatic task creation, or note maintenance unless the user identifies a real need.

### 2. Discover the actual sources and their authority

Inspect the current environment before proposing automation:

- Resolve the word **notes** to concrete paths and products. Do not infer Apple Notes merely because Apple Calendar or Apple Mail is in scope; distinguish app data from Markdown/Obsidian vaults explicitly.
- Identify canonical project status/index notes and noncanonical drafts or historical plans.
- For multiple vaults, use previous-workday Git history plus a bounded recent-activity window to nominate active projects; then read each selected project's `AGENTS.md`, `INDEX.md`, and `status.md` when present. Recent activity is a candidate signal, not proof every project belongs in the brief.
- Check whether referenced task files or dashboards actually exist; stale pointers are not data sources.
- Determine which calendar is most complete rather than assuming the direct provider API is canonical.
- Identify the exact work mailbox and engineering repositories in scope.
- Check existing scheduled jobs to avoid duplicate deliveries.

Use direct sources first. Session history is secondary context for uncaptured work, never stronger evidence than current notes, repositories, or service state.

### 3. Define the previous-workday boundary

Use the user's timezone. Monday looks back to Friday, not Sunday. For notes and activity, summarize changes from the start of the prior business day through the briefing time. Treat holidays as weekdays unless the user wants holiday suppression or the calendar clearly marks leave.

Do not imply that an unrecorded decision can be recovered. If the morning brief repeatedly lacks a usable stopping point, propose a lightweight end-of-day check-in as a separate experiment.

### 4. Set schedule and delivery semantics

Confirm:

- Weekdays and local delivery time.
- Timezone and daylight-saving behavior.
- Delivery destination.
- Whether the delivery should be continuable so the user can reply in context.
- Whether the scheduler host and gateway are expected to be awake and running.

For Hermes cron jobs, use a project `workdir` when project instructions should govern the run. Pin the intended provider/model so an unattended job does not silently follow a future global model change.

### 5. Separate collection from synthesis

For multi-source briefs, prefer:

1. A deterministic, bounded pre-run collector for calendar, email metadata, GitHub state, source-health signals, and recent version-control activity.
2. An LLM-driven cron run that reads canonical notes, reconciles the sources, and writes the human brief.

Do not use script-only/no-agent mode when prioritization and reconciliation are the value of the job. Keep collector output structured and bounded so the prompt is not flooded with raw data.

### 6. Apply source-specific rules

#### Notes and project state

- Read vault-local instructions and canonical status/index surfaces first.
- Use recent note commits and changed paths to reconstruct where work stopped and to identify other recently active projects.
- Bound cross-vault discovery by time and changed paths; open only the few relevant Markdown files needed for current state.
- Label proposals, drafts, observed current state, accepted decisions, and historical state distinctly.
- Never let a dated plan override a canonical current surface.
- A morning brief should normally be read-only; flag stale notes rather than silently editing them.

#### Opt-in workday-note companion

When the user explicitly wants the brief to leave a durable daily handoff, keep the write path narrower than the read path:

- Treat the dated note as **noncanonical operational evidence**. Canonical status/index/MOC surfaces always win when they disagree.
- Time-box the experiment (normally two weeks) and define a review date before adding templates, more folders, or an end-of-day job.
- Use one dated path such as `workdays/YYYY-MM-DD.md`; read the previous workday's note as carry-forward evidence.
- Put machine-managed content inside an explicit marker pair. On reruns, replace only the generated block and preserve frontmatter, day log, end-of-day handoff, and every manual byte outside the markers.
- Keep the generated block small: starting point, intended outcome, first action, schedule constraints, and a bounded watch list. Link to canonical notes instead of copying detailed state.
- Separate synthesis from synchronization. Use a deterministic helper to fetch, require a safe fast-forward, validate the marker structure, stage only the exact dated path, commit, push, and verify local/remote equality.
- Fail closed on divergence, pre-existing staged changes, unrelated tracked changes, malformed markers, or push failure. Never force, reset, stash, or absorb unrelated untracked files.
- Report note synchronization separately from brief delivery. A generated brief, local note, or local commit is not proof that the note reached the remote.

The morning job must retain read-only behavior for mail, calendar, GitHub, canonical project notes, and every path outside the explicitly approved dated note.

#### Calendar

- Preserve source-calendar names for classification and troubleshooting.
- Separate all-day events from timed commitments.
- Identify conflicts, meeting preparation, and realistic focus windows.
- Reconcile duplicate events from synchronized/shared calendars.
- Collect bounded organizer and current-user attendee metadata when available. Never infer that the user owns a presentation, demo, review, or preparation task from the event title alone; attendee status is not ownership.
- If Apple Calendar is canonical, prefer read-only EventKit collection, with AppleScript as a fallback. Avoid unattended GUI driving for routine collection.
- Verify source health or recent synchronization before treating an empty day as fact.

#### Email

- Scope to the work account and a bounded time window.
- First determine whether a local client already synchronizes the authoritative work mailbox. Do not add a second direct provider integration, OAuth client, or duplicate collector unless the local source is insufficient for a demonstrated requirement.
- Before asking the user to create provider credentials, explain why the extra source is necessary and confirm that the reliability benefit justifies the account setup.
- Prioritize direct requests, active-thread replies, meeting changes, and alerts that add information not already available elsewhere.
- Ignore newsletters and routine automation by default.
- Read bodies only when envelope metadata is insufficient.
- Never mark read, move, label, archive, draft, reply, or send in a read-only brief.
- If two genuinely necessary sources represent the same mailbox, deduplicate by RFC `Message-ID`; fall back to normalized sender, subject, and timestamp. Prefer the server/API copy when both represent the same message.

#### GitHub and engineering systems

- Limit checks to authored PRs, assigned review requests, actionable comments, meaningful state changes, and failed CI.
- Every GitHub artifact mentioned anywhere in the delivered brief—including pull requests, issues, commits, Actions runs/checks, discussions, releases, repositories, and project items—must have a direct clickable GitHub URL. Use descriptive Markdown links rather than bare numbers or unlinked titles.
- Apply the link rule outside the dedicated GitHub section too: prior-work summaries, recommended outcomes, first actions, and generated companion-note blocks must not contain unlinked GitHub references.
- Prefer URLs supplied by the collector. If an artifact is relevant but its URL is missing, resolve it with a read-only GitHub lookup before mentioning it; omit it rather than emit an unreliable or unlinked reference.
- Respect repository ownership boundaries; broad dependency or notification triage may not belong to the user even when they can access it.
- Keep the section bounded unless something is actively broken.
- Never comment, label, merge, dispatch, or otherwise mutate state from the morning brief.

### 7. Design a bounded output

A good default structure is:

- **Where you left off** — 2–5 grounded bullets and the recorded resting point.
- **Other recent projects** — up to 3 concrete open threads from other active vaults; omit the section when recent activity produced no actionable state.
- **Today's calendar** — commitments, preparation, conflicts, focus windows.
- **Messages requiring attention** — up to 3 actionable items.
- **Engineering watch list** — up to 3 reviews, comments, CI failures, or status changes.
- **Recommended primary outcome** — exactly one meaningful result.
- **Suggested first action** — one concrete next step.
- **Unverified / needs judgment** — missing sources, disagreements, or assumptions.

Target a brief readable in under two minutes, usually no more than about twelve substantive bullets. If a section has nothing useful, keep it short instead of filling space.

### 8. Handle permissions and empty results safely

- Request only read scopes.
- Never automate permission dialogs, passwords, API keys, or security challenges.
- During setup, stop and let the user grant OS or provider access. Put the exact action or command in the same visible question/message that asks them to report the result; do not ask for confirmation of an instruction that may have been hidden in preceding UI narration.
- Distinguish “source returned zero items” from “source unavailable or stale.”
- Surface collection failures explicitly; do not convert them into an apparently empty calendar or inbox.

### 9. Pilot before making it permanent

1. Run one manual briefing.
2. Review source accuracy, length, privacy, and the suggested primary outcome.
3. Enable a one-week weekday pilot.
4. Measure whether the brief is useful without substantial correction and whether it identifies a credible first action.
5. Remove noisy inputs before adding new ones.
6. Add an end-of-day companion only if the morning run exposes a persistent capture gap.

## Implementation Verification

Before declaring the job complete:

- [ ] Every source can be queried read-only.
- [ ] Source health failures are visible.
- [ ] Previous-business-day logic works on Monday.
- [ ] Calendar and email duplicates collapse correctly.
- [ ] Canonical notes outrank drafts and dated plans.
- [ ] GitHub scope respects repository ownership boundaries, and every mentioned GitHub artifact has a verified direct clickable URL.
- [ ] The job performs no writes or external communication except an explicitly approved, path-bounded companion note and the requested delivery.
- [ ] If a companion note is enabled, reruns preserve all content outside the generated markers, synchronization stages only that dated file, and remote equality is verified.
- [ ] Delivery is continuable if requested.
- [ ] Scheduler, timezone, gateway, and host-awake assumptions are tested.
- [ ] A manual run produces a concise, grounded brief.
- [ ] Delivery is verified at the destination transport level (for example, a platform send log and event/message ID), not only by `last_status=ok` or the existence of a local cron output file.

## Project References

- `references/sgg-morning-brief-pilot.md` — agreed Simpler Grants source hierarchy, output contract, Matrix verification, and opt-in workday-note synchronization details.

## Common Pitfalls

1. **Building around stale pointers.** Verify that task files and dashboards exist before making them primary inputs.
2. **Treating every notification as actionable.** Bound each live-system section and suppress duplicated automation.
3. **Using GUI automation for routine local-app reads.** Prefer supported read-only APIs or scripting bridges.
4. **Trusting empty output without source health.** An unsynchronized calendar and an empty day are not equivalent.
5. **Letting the brief mutate canonical or external sources.** Morning synthesis must not mark mail read, change calendar/GitHub, or rewrite project status. The only exception is an explicitly approved, path-bounded noncanonical companion note.
6. **Overbuilding before observing use.** Run a reversible pilot; only add machinery that solves a demonstrated retrieval or planning failure.
7. **Duplicating a synchronized mailbox without need.** A second direct API can add OAuth burden and duplicate data while contributing no authority or coverage. Prove the gap first.
8. **Overwriting an externally managed gateway service.** Before using Hermes gateway install/start/restart commands, inspect who owns the launchd/systemd definition. If Nix, Home Manager, or another supervisor owns it, restore or restart through that source of truth instead of replacing its runtime path.
9. **Mistaking successful synthesis for successful delivery.** Verify the adapter connected and recorded a platform event/message ID.
10. **Mentioning GitHub artifacts without links.** A PR number or title is not enough in a delivered brief. Require a verified clickable URL everywhere the artifact appears, including outcome and first-action sections, then test-fire and inspect the rendered output before approval.
11. **Turning a companion note into a second status page.** Keep it noncanonical, generated-block bounded, and linked to canonical state; never let unattended synthesis rewrite the project MOC or status file.
