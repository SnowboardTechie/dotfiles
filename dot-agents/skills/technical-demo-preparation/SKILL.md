---
name: technical-demo-preparation
description: Use for short technical demos, sprint reviews, and release walkthroughs (Team of Teams, stakeholder demos). Produces a verified runbook plus a presenter companion web page served on the tailnet.
version: 1.1.0
author: Bryan Thompson
license: MIT
metadata:
  hermes:
    tags: [demo, presentation, rehearsal, developer-experience, verification]
    related_skills: [voice-bryan, vault-pkm, sprint-deliverable-update]
---

# Technical Demo Preparation

Prepare short, credible technical demos that show a real result rather than narrating implementation detail. The deliverable has three parts: a rehearsed runbook backed by fresh execution, a compact fallback if the live path fails, and a **presenter companion page**. That's a simple slideshow-style web page Bryan keeps beside the meeting, with the talk track and every link he might follow, served at a tailnet URL. Bryan expects the companion every time; don't wait for him to ask.

## When to use

Use this skill when the user asks to prepare, rehearse, or tighten:

- a sprint demo, team-of-teams update, stakeholder walkthrough, or engineering show-and-tell;
- a terminal, API, SDK, data-pipeline, or developer-experience demo;
- a short live presentation that needs commands, narration, timing, and fallback evidence;
- a documentation or release walkthrough where nothing runs live (read `references/documentation-walkthrough-demos.md`).

Do not use it for a written sprint-status comment alone, a slide deck whose content is nontechnical, or exploratory QA without a presentation deliverable.

## Core principles

1. **Lead with the result.** The audience should understand the problem, the observable change, and why it matters without learning the implementation history.
2. **Use the shortest proof that carries the claim.** A three-minute demo usually needs one live action and one inspected result, not an architecture tour.
3. **Verify the exact candidate.** Resolve the linked PR, issue, commit, branch, release, or deployment and run the commands against that state.
4. **Rehearse what will actually be shown.** Do not call a demo ready because tests pass. Execute the same commands, in the same order, from the same checkout and shell the presenter will use.
5. **Keep the live path deterministic.** Prefer committed fixtures, caches, vendored schemas, local servers, or pinned inputs when they still prove the claim. Do not add avoidable credentials or venue-network dependencies.
6. **Fallbacks are part of the demo.** Capture the successful output and one representative result before the meeting. A fallback is not a TODO.
7. **Fit the requested time.** Do not expand a short update merely because the work was technically deep.

## Workflow

### 1. Gather authoritative context

Inspect the original artifact first:

- linked PR or issue, including current merge/close state and acceptance criteria;
- exact files, scripts, README commands, and output shape;
- prior demo runbooks or earlier presentation feedback;
- current local checkout, remotes, branch, and commit.

Use conversation history or project notes to recover a proven format, but verify volatile facts against the live source.

For a recurring meeting or follow-on demo, find the previous runbook first (vault `drafts/` and `sessions/` for the meeting name, then the harness's session history). Reuse its format, time ceiling, and runbook structure, and open the new talk track by connecting to what the last demo showed.

For a sprint or release review, inventory merged PRs and published releases across every relevant repository for the sprint window, confirm "shipped" against the package registries, and reconcile with the team's posted sprint report. The commands are in `references/documentation-walkthrough-demos.md`.

### 2. Ask only the questions that change the demo

When the user says "like last time" and the prior runbook records the time ceiling and format, reuse them without asking; state the assumption in the runbook and the final report so the user can correct it. Otherwise, when not already clear, ask these together:

- How much time is available?
- Is the format live terminal, talk-only, or slides?
- Which outcome deserves the most airtime?

Treat the answers as constraints. For a three-minute terminal demo, default to one command, one result inspection, and one closing claim.

### 3. Define the story before choosing commands

Write one sentence in this form:

> Starting from **input/problem**, the work now **does observable thing**, producing **verified outcome** for **consumer/stakeholder**.

Choose two or three numbers or facts the audience should remember. Do not turn the story into a ticket list.

Content rules for Bryan's stakeholder demos (team-of-teams, sprint and release walkthroughs). They apply to the talk track, story, and checklist, not only to wording:

- **Present what shipped and works.** Leave out bugs that validation found, their fixes, and pending patch releases. These are unnecessary detail and reflect poorly on the release. Mention the validation itself in neutral terms ("we tested against real award data") without its defect findings. If a public team report already mentions the fix, keep at most one neutral, reactive Q&A line, and label it "only if asked."
- **Do not present future or next-sprint work unless Bryan confirms it is planned and owned.** A posted sprint report, a tracker sprint field, or an assignee does not establish that. Close on a takeaway about delivered capability instead of a "next we will" line. If the tracker disagrees with Bryan, note it once in the runbook's evidence and move on.
- When the team's posted sprint report includes either kind of item, the demo can be a positive subset of it. The rule is not to contradict it, not to mirror it.

### 4. Prepare the exact demo environment

- Move the local checkout to the exact merged or approved candidate without publishing unrelated state.
- Install dependencies using the repository's declared package manager and lockfile.
- Confirm the presenter's normal shell can resolve every command.
- Keep secrets off screen. Prefer a path that needs none.
- Avoid showing distracting repository state, unrelated windows, or machine-specific warnings.
- Make generated output disposable and keep it out of commits unless it is intentionally the reference artifact.

### 5. Prove the live path

Run the exact demo command and the relevant correctness gates. Depending on the project, verify:

- typecheck, tests, build, schema validation, or reference comparison;
- output counts and failure counts;
- expected representative record or response;
- exact commit or deployment identity;
- offline behavior by pointing optional network dependencies at an unreachable local address when the claim is that the run is offline.

A command that exits successfully is not enough if the demo's claim depends on the generated data. Inspect the output.

For a documentation walkthrough, the screens are the live path: open every URL at the presentation viewport, screenshot it, and confirm the anchor shows the heading and the whole snippet without scrolling.

### 6. Select one representative result

Show a compact projection, not a giant raw object. Choose a result that is:

- understandable without domain archaeology;
- stable across rehearsals;
- visually concise in a terminal;
- strong enough to make the value concrete.

Use a deterministic selector rather than relying on array position when ordering may change. Project only the fields needed for narration.

### 7. Write the runbook

Use `templates/live-demo-runbook.md`. Include:

- verified state and source links;
- the one-sentence story;
- setup commands;
- spoken opening, narration beats, and closing;
- exact live commands;
- canned successful output;
- likely questions with short grounded answers;
- a pre-meeting checklist.

If the project uses a vault, follow `vault-pkm`: name the path before writing, add an inbound link, and synchronize according to local rules.

### 7a. Build the presenter companion page

Build it from `templates/presenter-companion.html` following `references/presenter-companion-page.md`. It has a Prep tab, one tab per item with the screen link, the verbatim talk track, and the item's links, then Q&A and Fallback tabs. Save it beside the runbook in the vault and commit it with the runbook. Publish it to the Artifact Shelf (or `tailscale serve`), check that the URL loads, and put the URL in the runbook's screen plan. Check every link on the page.

### 8. Rehearse and measure

- Run the exact sequence end to end.
- Record command duration.
- Count spoken words and estimate delivery time at roughly 120 to 140 words per minute: `python3 <this skill's dir>/scripts/talk-track-timing.py <runbook.md>` reports per-subsection counts, the time range, and any em-dashes in spoken lines. Record the counts in the runbook, and say plainly when no spoken rehearsal has happened.
- Leave at least one-third of a very short slot for pauses, screen-share friction, and one question.
- Shorten by removing context and extra commands before shortening the actual value statement.

For the detailed three-minute terminal pattern, read `references/short-live-terminal-demos.md`.

### 9. Final verification

Before handoff, confirm:

- [ ] Exact source candidate is current and identified
- [ ] Every command was executed successfully
- [ ] The result shown was inspected, not assumed
- [ ] The talk track fits the requested time
- [ ] No secrets appear in commands or fallback output
- [ ] Canned output matches a successful rehearsal
- [ ] Likely numerical questions reconcile with the output
- [ ] Talk track has no defects found or fixes pending, and no future work Bryan hasn't confirmed
- [ ] Runbook is saved, linked, and synchronized where required
- [ ] Companion page matches the runbook's talk track, every link on it returns 200, and its tailnet URL loads

### 10. Hand off with web links

The handoff message always leads with clickable web links, never just repo paths:

- the companion page's tailnet URL;
- the runbook's forge URL, plus the companion source's forge URL (note when a private repo needs a login).

Then give the talk track inline, if asked, and anything Bryan must not say. After the meeting, once he says it's done, retire the shelf item.

## Common pitfalls

### Overbuilding a short demo

Do not add presented slides, architecture diagrams, multiple language paths, or a second live scenario without a clear reason. A short stakeholder demo is not a code tour. The presenter companion page is not a presented deck. Always build it, and never put it on screen.

### Treating installation success as demo readiness

Dependencies being installed proves only setup. Run the actual demo and inspect its result.

### Showing a giant JSON object

Large output makes the audience search for the point. Select one representative item and project six or fewer meaningful fields.

### Using live services when committed evidence proves the same thing

Live data can be appropriate, but avoid credentials, rate limits, and venue-network risk when a deterministic snapshot still demonstrates the contract. State clearly whether the data was refreshed from production and when.

### Hiding mismatched counts

Explain funnels honestly. If 37 matched opportunities yield 84 awards, say why. If some inputs do not match, distinguish expected coverage limits from failures.

### Treating a caught bug as a credibility story

Engineers read "testing caught a bug before adopters did" as rigor; a cross-team audience hears "the release was broken." In stakeholder demos, keep the testing and drop the defect (see the content rules in step 3).

### A fallback that requires new work

Never hand off a note that says to capture output later. Capture it during rehearsal and package it beside the talk track.

### Confusing exact candidate state with fork tracking state

A local checkout can match the merged upstream commit while its configured fork remains behind. Verify the commit directly and avoid putting irrelevant `git status` noise on screen. Do not sync or publish a fork unless the user asked.

## Supporting files

- `references/short-live-terminal-demos.md`: detailed timing, command, output-selection, and fallback pattern for a three-minute engineering demo.
- `references/documentation-walkthrough-demos.md`: release/sprint walkthroughs with no live execution: sprint inventory commands, screen selection and rehearsal, GitHub anchor pitfalls, claim discipline, and format-specific runbook sections.
- `references/collaborative-data-pipeline-demos.md`: presentation-machine checks, collaborator credit, real-world example selection, and jq formatting for data-pipeline demos.
- `references/presenter-companion-page.md`: companion page shape, link checks, Artifact Shelf publishing and retirement, and handoff links.
- `templates/presenter-companion.html`: self-contained companion page skeleton (tabs, keyboard nav, timer).
- `scripts/talk-track-timing.py`: counts spoken (blockquote) words per talk-track subsection and estimates delivery time.
- `templates/live-demo-runbook.md`: reusable runbook skeleton for live technical demos.
