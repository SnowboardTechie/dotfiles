---
name: tdd
description: Test-first discipline for a behavior change — pick the seam, write one failing test that fails for the intended reason, make it pass, then refactor on green. Use when implementing a feature or fixing a bug test-first, when the user mentions red/green/refactor or TDD, or when `issue-work` reaches a task that changes behavior.
---

# TDD

The loop is red → green → refactor. This skill is what makes the loop produce
tests worth keeping: where the test goes, what makes it honest, and when to
stop. Consult it *during* the loop, not after.

Provenance: adapted from Matt Pocock's `tdd`. Upstream pin, accepted and
rejected upstream rules, and the watched source list live in
[`dot-agents/upstreams/mattpocock-skills.json`](../../upstreams/mattpocock-skills.json).

## 1. Fix the seam

A **seam** is the public boundary you test at — the interface where behavior is
observable without reaching inside. Tests live at seams, never against
internals.

Confirm the seam before writing the first test. Two ways that is legitimately
satisfied:

- **Interactively**: ask. "The public surface here is X; I propose testing at
  the Y seam. Agreed?" One question, then work.
- **Pre-agreed**: the issue, spec, or approved plan already names the seam or
  the public contract under change. This is what makes unattended
  implementation possible — `issue-work` runs without a human in the loop, so
  the plan is where the seam gets agreed. Cite it and proceed.

No test at an unconfirmed seam. You cannot test everything, and agreeing the
seam is how the effort lands on the critical path instead of on every edge case.

When the shape of the interface is *itself* the open question — how deep the
module should be, where the seam belongs, what it should expose — that is a
design question, not a testing one. Load `codebase-architecture` for the
vocabulary and come back.

## 2. One slice at a time

Work in **vertical slices**: one test → one minimal implementation → repeat.
Each test is a **tracer bullet** that responds to what the last cycle taught
you.

Never write all the tests first and then all the implementation. Bulk tests
verify *imagined* behavior: they test the shape of things rather than what a
caller experiences, they go insensitive to real changes, and they lock in a test
structure chosen before anyone understood the implementation.

## 3. Red — and red for the right reason

Write the failing test, then **run it and read the failure**.

The test must fail because the intended behavior is *missing* — not because of a
typo, an unresolved import, a missing fixture, or a setup error. A red bar from
a broken harness proves nothing, and the green bar that follows proves less.

If the failure message is not the one you predicted, fix the test before you
touch the implementation.

**Expected values come from an independent source**: a known-good literal, a
worked example, the spec, a value from the real system. Never recompute the
expected value the way the code computes it — that test passes by construction
and can never disagree with the code.

## 4. Green

Write only enough code to pass the test. Do not anticipate the next test, and do
not add behavior the current test does not demand.

Mocks are reserved for **real system boundaries**: third-party APIs, networks,
clocks and randomness, and sometimes databases or the filesystem. Never mock
your own modules, internal collaborators, or anything you control — see
[`references/mocking.md`](references/mocking.md).

## 5. Refactor on green

Refactor only with a passing test, in small steps, re-running the targeted check
after each one. If a refactor turns the bar red, you have a fact: revert the
step rather than debugging forward from an unknown state.

A test that must change because the *implementation* changed was testing past
the interface. That is a signal about the test, not a chore.

## 6. Verify

- **During development**: run the targeted check — the single test, the one
  file, the affected package. Fast enough to run constantly.
- **Before declaring the work complete**: run the project's full relevant gate
  (its test, lint, and typecheck commands) and preserve the real output. A
  targeted green is not a completion gate.

## What this skill does not impose

- **No coverage quota.** "Every function has a test" produces tests at the wrong
  seams. Agreed seams and critical paths decide where effort goes.
- **No blanket delete-and-restart.** A failing cycle is diagnosed, not reset. If
  the same test fails twice for reasons you cannot name, stop guessing and load
  `diagnosing-bugs`.
- **No test written to a seam nobody agreed to**, however tempting the coverage
  gap looks.

## References

- [`references/tests.md`](references/tests.md) — worked good/bad examples:
  implementation-coupled, tautological, and side-channel tests.
- [`references/mocking.md`](references/mocking.md) — boundary rules and
  designing an interface that is honest to mock.

## Related

- `diagnosing-bugs` — when a failure needs a root-cause pass instead of another
  cycle.
- `code-review` — refactoring beyond the loop, and the review lanes.
- `codebase-architecture` — the module/interface/seam/depth vocabulary.
- `issue-work` — pre-agrees the seam in its approved plan and drives this loop.
