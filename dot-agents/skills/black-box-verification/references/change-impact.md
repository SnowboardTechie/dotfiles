# Change-impact investigation

Source-informed and deliberately narrow. The goal is not a list of callers —
grep produces that in seconds. The goal is the breakage grep will not show, and
proof of the one or two facts the change is safe because of.

## Find the load-bearing fact

Most changes that look risky are safe because of a single fact: "this call only
drops entries that are already dead", "nothing outside this module reads the
field", "the consumer tolerates an unknown key". Name that fact. If it holds,
most of the risky cases clear at once; if it fails, that is the finding.

Stop at one or two. Do not build an exhaustive caller inventory, and do not
open another reviewer, model, or agent fan-out to widen the search — that is
the owning workflow's review step, not this one.

## Look where grep stops

- The source and pinned version of a library you call, including local patches.
- When things run: async ordering, teardown, retries, scheduled jobs.
- What a symbol search misses: a JSON payload, a DB column, a wire or file
  format, a config key, a feature flag, another language reading the same bytes.

## How far each fact is proven

Push each fact as far down this ladder as is cheap, and report where it stopped.

1. **Asserted.** Worthless on its own.
2. **Pointed at.** A real `file:line`, or the library's own source.
3. **Reasoned.** The failure path walked step by step and shown not to reach.
4. **Executed.** A small script or test that calls the real code and fails loudly
   if the fact is wrong.
5. **Reproduced.** Observed through the running application's public interface
   (the black-box procedure in [`../SKILL.md`](../SKILL.md)).

Level 4 is usually one short script that imports what the application ships and
calls exactly the function in question.

## Planning versus implementation

During `issue-plan`, levels 1–3 come from read-only inspection, and level 4 may
too when an isolated scratch or in-memory probe proves the fact — planning
already permits those. A check that writes real state, launches the
application, or calls a live service (including any level 5 reproduction) goes
into the plan as a named verification step for implementation authority. It is
not deferred as "verify feasibility", and it is not run covertly during
planning.

## Report

- **The fact(s)** the change depends on, the level each reached, and the proof
  (command and output), or **unproven**.
- **Confirmed risks**: how it breaks, `file:line`, likelihood and cost, the
  cheapest check that catches it.
- **Cleared**: what was checked and why it is fine. A search that found nothing
  is still an answer; never invent a caller or an API.
