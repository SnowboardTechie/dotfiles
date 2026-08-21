---
name: diagnosing-bugs
description: Root-cause loop for hard bugs, flaky failures, and performance regressions — build a tight failing command first, minimize it, rank falsifiable hypotheses, then fix once at the source. Use when something is broken/throwing/failing/slow, when a fix has already failed once, or when `issue-work` escalates a repeated test failure.
---

# Diagnosing Bugs

A discipline for bugs that did not yield to the obvious fix. Skip a phase only
with an explicit reason.

Provenance: adapted from Matt Pocock's `diagnosing-bugs`, retaining the
multi-component boundary tracing from the bundled `systematic-debugging`
workflow it replaces. Upstream pin, accepted and rejected upstream rules, and
the watched source list live in
[`dot-agents/upstreams/mattpocock-skills.json`](../../upstreams/mattpocock-skills.json).

## 0. Redact first

This skill has you show commands, outputs, and captured artifacts. **Redact
every secret before it appears anywhere**: write `<REDACTED>` in its place.
Build loops against environment variables so credentials stay in the
environment rather than in what you print. Captured artifacts (HAR files, log
dumps, request traces) carry auth headers — quote only the lines carrying the
signal.

If the redacted evidence is not enough to diagnose the bug, say so and ask.

## 1. Build a feedback loop

**This is the skill.** Everything after it is mechanical. With a tight pass/fail
signal that goes red on *this* bug, you will find the cause; bisection,
hypothesis testing, and instrumentation all just consume it. Without one, no
amount of reading code will save you.

Spend disproportionate effort here.

Ways to construct one, in roughly this order:

1. **Failing test** at whatever seam reaches the bug.
2. **Curl / HTTP script** against a running dev server.
3. **CLI invocation** with a fixture input, diffed against a known-good snapshot.
4. **Headless browser script** driving the UI, asserting on DOM/console/network.
5. **Replay a captured trace** — a real request, payload, or event log, replayed
   through the code path in isolation.
6. **Throwaway harness** — a minimal subset of the system reaching the bug path
   in one call.
7. **Property / fuzz loop** for "sometimes wrong output".
8. **Bisection harness** when the bug appeared between two known states.
9. **Differential loop** — same input through two versions or configs, diffed.
10. **Human-in-the-loop script** — last resort, when a person must click. Drive
    them with a structured script so the loop stays repeatable.

### Tighten it

Treat the loop as a product. Once you have *a* loop: make it faster (cache
setup, skip unrelated init, narrow scope), make the signal sharper (assert the
specific symptom, not "didn't crash"), make it deterministic (pin time, seed
RNG, isolate the filesystem, freeze the network).

A 30-second flaky loop is barely better than none. A 2-second deterministic one
is a superpower.

### Non-deterministic bugs

The goal is not a clean repro but a **higher reproduction rate**. Loop the
trigger 100×, parallelize, add stress, narrow timing windows, inject sleeps. A
50%-flake bug is debuggable; 1% is not. Keep raising the rate until it is.

### Completion criterion

Phase 1 is done when you can name **one command** you have **already run at
least once** (show the invocation and its redacted output) that is:

- **Red-capable** — drives the actual bug path and asserts the *user's exact
  symptom*, so it goes red now and green once fixed;
- **Deterministic** — same verdict every run, or a pinned high repro rate;
- **Fast** — seconds, not minutes;
- **Agent-runnable** — runnable unattended.

If you catch yourself reading code to build a theory before this command exists,
**stop**. Jumping to a hypothesis is the exact failure this skill prevents.

### When you genuinely cannot build one

Say so explicitly, list what you tried, and ask for one of: access to an
environment that reproduces it, a redacted captured artifact, or permission to
add temporary production instrumentation. Do **not** proceed to hypothesize.

## 2. Reproduce and minimize

Run the loop. Watch it go red. Confirm:

- it produces the failure mode **the user described**, not a different one
  nearby — wrong bug, wrong fix;
- it reproduces across runs (or at a high enough rate to debug against);
- you captured the exact symptom, so later phases can prove the fix addressed it.

Then shrink the repro to the **smallest scenario that still goes red**. Cut
inputs, callers, config, data, and steps **one at a time**, re-running after
each cut. Done when every remaining element is load-bearing: removing any one of
them turns the loop green.

Minimizing pays twice — it shrinks the hypothesis space in phase 3 and becomes
the clean regression test in phase 5.

## 3. Hypothesize

Generate **3–5 ranked hypotheses before testing any of them**. Single-hypothesis
generation anchors on the first plausible idea.

Each must be **falsifiable** — state the prediction:

> "If X is the cause, then changing Y makes the bug disappear / changing Z makes
> it worse."

If you cannot state the prediction, it is a vibe. Discard or sharpen it.

Show the ranked list before testing. Domain knowledge re-ranks it instantly
("we just deployed a change to #3"). Do not block on it — proceed with your
ranking if nobody is there.

## 4. Instrument

Each probe maps to a specific prediction from phase 3. **Change one variable at
a time.**

Tool preference:

1. **Debugger or REPL inspection** where the environment supports it — one
   breakpoint beats ten logs.
2. **Targeted logs** at the boundaries that distinguish hypotheses.
3. Never "log everything and grep".

**Tag every debug log** with a unique prefix, e.g. `[DEBUG-a4f2]`, so cleanup is
one grep. Untagged instrumentation survives; tagged instrumentation dies.

### Multi-component systems

When the failure crosses component boundaries (API → service → database, CI →
build → deploy), locate the failing component before investigating inside any of
them. At **each boundary**, capture what data enters, what data exits, and
whether environment and configuration actually propagated. Run once to gather
the whole picture, read it to identify *where* it breaks, and only then descend
into that component.

Then **trace the bad value upstream**: where does it originate, and what called
with it? Keep going until you reach the source. Fix at the source, never at the
symptom.

### Performance branch

For performance regressions, logs are usually the wrong instrument. Establish a
baseline measurement (timing harness, profiler, query plan), then bisect.
Measure first, fix second.

## 5. Fix and regression-test

Write the regression test **before the fix** — but only if a **correct seam**
exists for it. A correct seam exercises the real bug pattern as it occurs at the
call site. A single-caller unit test for a bug that needs multiple callers gives
false confidence.

**If no correct seam exists, that is itself the finding.** Note it: the
architecture is preventing the bug from being locked down.

If one exists:

1. Turn the minimized repro into a failing test at that seam.
2. Watch it fail.
3. Apply **one root-cause fix**.
4. Watch it pass.
5. Re-run the phase 1 loop against the **original, un-minimized** scenario.

## 6. Clean up

Required before declaring done:

- [ ] Original repro no longer reproduces (phase 1 loop re-run).
- [ ] Regression test passes, or the absence of a correct seam is documented.
- [ ] All `[DEBUG-…]` instrumentation removed (grep the prefix).
- [ ] Throwaway harnesses deleted, or moved somewhere clearly marked.
- [ ] The hypothesis that turned out correct is stated in the commit or PR, so
      the next person debugging this learns from it.

## Stop conditions

Stop and raise an architecture discussion rather than attempting another patch
when **repeated failed fixes reveal systemic coupling**: two or more root-cause
fixes have each moved the failure somewhere else, no correct seam exists for a
regression test, or the minimized repro keeps requiring elements from unrelated
components. That is a design finding, not a bug that wants a third patch. Hand
it to `codebase-architecture` or back to the user.

Also stop when the loop cannot be built (phase 1), or when a fix would need a
decision outside the reported bug's scope.

## Related

- `tdd` — writing the regression test at the seam.
- `codebase-architecture` — when the diagnosis becomes a design finding.
- `issue-work` — escalates here on a second consecutive failure of the same task.
