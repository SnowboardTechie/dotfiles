# Reusable project verification recipe

A recipe is how a project's real application gets driven and proven, written for
an agent that arrives cold mid-task. Write one only when a project keeps needing
it; a one-off check belongs in the plan or the handback, not a new file.

## Reuse before generating

Start from what the project already owns: README quickstart, `Makefile` or
package scripts, existing end-to-end harnesses (Playwright, expect, PTY helpers,
curl-able endpoints), test fixtures, and its `AGENTS.md`. When those already
cover a section below, link them instead of restating them. Answer the questions
from the repository; ask Bryan only what cannot be observed.

## Placement is a decision

Choose where the recipe lives deliberately and record why:

- a section or reference in the project's existing docs or `AGENTS.md`, when it
  is short;
- a project-owned skill, when several runtimes should discover it — under the
  path the project's own agent conventions use, not unconditionally
  `.claude/skills/verify/` (that name shadows a Claude Code built-in and is
  invisible to the other runtimes);
- in a monorepo, beside the package it drives.

Creating the file is a repository change under the project's normal authority
and review.

## What a recipe contains

- **Launch, readiness, and ownership.** The exact command to start the
  application for verification from an empty data directory, how to tell it is
  *usable* rather than merely answering, and a read-only "doctor" check: process
  up, expected build, port or socket owned by this run, credentials valid.
  For a short-lived CLI there is no server: launch means build once, then run
  each drive in its own isolated environment.
- **Drive.** The real public-interface recipe with this repository's actual
  commands, routes, or selectors. Prefer stable handles (prompt strings, route
  paths, ARIA labels, data attributes) over coordinates.
- **Independent expected results.** Where each feature's expected outcome comes
  from (spec, acceptance criteria, documentation), so a verifier never derives
  it from the implementation under test.
- **Evidence and side-effect readback.** What to capture, where it goes, and how
  to read back every external effect (files, rows, refs, links, messages).
  Name which dry-run or check modes are trusted, and how that was observed.
- **Isolation and cleanup.** How two runs coexist (ports, data dirs, scratch
  `HOME`), or an explicit refusal to double-drive a shared instance. Cleanup
  kills only what the run started — never by process name — and never deletes
  the evidence.
- **Features.** The few user-facing journeys that matter most, each with how to
  reach it, how to drive it, and the observable end state that proves it. When
  seed data lacks a precondition, the journey reports the gap; it is never
  weakened to pass.
- **Boundaries.** Which external systems are substituted, which are untested,
  and which writes need extra authorization.

## Prove it once

Run the recipe end to end before calling it done: launch, doctor, drive one
journey, capture evidence, clean up, then confirm the evidence survived the
cleanup. A recipe that was never executed is a draft. Keep it honest as the
application changes by fixing it when a run disagrees with it — no scheduled
maintenance loop or watcher.
