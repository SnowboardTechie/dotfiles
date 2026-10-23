---
name: black-box-verification
description: Use when proving behavior through a public interface.
---

# Black-box verification

Reach for this when a change has behavior a user or caller would see (a CLI,
API, UI, written files, or external side effects), when "does it actually work
end to end" is the open question, when a plan rests on an unproven claim about
code across a boundary ("X already handles Y", "nothing else reads this"), or
when a project needs a reusable recipe for driving its real application.

It covers two jobs that are easy to blur. Keep them apart, and label which one
produced each piece of evidence.

| Job | Source reading | What it proves |
|---|---|---|
| **Black-box verification** | Not required to execute or to judge the result; permitted for choosing what to test. Expectations come from the contract | The change behaves as a caller expects, end to end |
| **Change-impact investigation** | Yes — source, callers, libraries, data formats | The one or two facts the change is safe *because of* |

Reading the implementation is useful **test selection**: it tells you which
inputs, paths, and boundaries are worth driving. It is not black-box execution,
and a test whose expected value was copied from the code under test proves only
that the code agrees with itself.

Provenance: concepts adapted from pstack's `blast-radius` and
`create-verification-skill`. Upstream pin, license, and the accepted and
rejected upstream rules live in
[`dot-agents/upstreams/pstack-claude.json`](../../upstreams/pstack-claude.json).

## When this is the wrong tool

- Trivial changes, documentation, or pure internal logic with no observable
  boundary: ordinary unit tests at the seam (`tdd`) are the proof. Do not add
  a black-box gate on top.
- Root-causing a failure: use `diagnosing-bugs`.
- Review and acceptance: `code-review`, `pr-self-review`, and the owning
  workflow's acceptance step stay authoritative. This skill supplies evidence
  to them; it is not another reviewer.

## Authority comes from the workflow, never from this skill

- **Planning is read-only.** Resolve known facts by inspection and by the
  isolated scratch or in-memory probes planning already permits. Checks that
  write real state, launch the application, or call a live service are
  recorded as verification steps for implementation authority to run.
- **This skill grants nothing.** No dependency or software install, no live or
  customer write, no outbound message, no long-running process launch beyond
  what the current authority already permits. Use the project's existing tools
  and harnesses. When the proof needs more, name the permission and stop.
- Existing outbound, destructive-Git, model, worker, finite-correction, and
  publication gates remain authoritative.

## Black-box procedure

1. **Name the interface.** The exact command, endpoint, page, or file a caller
   touches, and the version or build under test.
2. **Write the expected result first, from the contract.** Ticket acceptance
   criteria, spec, documentation, or `--help` output — not the implementation.
   If the contract is silent, say so; do not fill the gap by reading the code.
3. **Drive the real interface in isolation.** A scratch `HOME`, temp data dir,
   test port, sandbox account, or disposable worktree. Never double-drive an
   instance the user is using.
4. **Capture the action and the resulting state.** Exit code, output, response
   body, files written. Read back every external side effect (files, rows,
   links, refs, messages) rather than trusting the success message. When the
   safe path is a dry run or check mode, verify by observation that it really
   skipped the effect.
5. **Exercise the edges that matter.** A repeat run (idempotence), a pre-existing
   foreign entry, an invalid input — whichever the contract makes promises
   about.
6. **Clean up what you started, keep the evidence.** Kill only processes you
   launched, remove only scratch state you created, and leave the evidence at a
   named path outside the disposable area.

## Honest results

- Mocks and internal setters are not proof of a real end-to-end journey. Use
  them only where a production boundary already isolates the external system,
  and list each substituted boundary.
- List what stayed untested and why (no credentials, no live target, outside
  authority).
- A failing setup, missing fixture, or broken harness is not a reproduced
  regression. A red result counts only when it fails for the reason the
  contract predicts.
- A stand-in target (container for a VM, local stack for a remote one) leaves
  every step the real target would do unverified until it runs there.

## References — open when the trigger fires

- [`references/change-impact.md`](references/change-impact.md) — **open when** a
  change's safety rests on a claim about code you are not changing ("only this
  caller", "the library already handles it", "the wire format is unchanged"),
  or a brief asserts something about existing code before you design against
  it. It decides which one or two facts to prove and how far to prove them.
- [`references/project-recipe.md`](references/project-recipe.md) — **open when**
  the same project keeps needing its real app driven and nobody wrote down how
  — launch, readiness, drive, evidence, cleanup — or when someone asks to
  "make a verify skill" for a repository. It decides what a reusable recipe
  contains and where it belongs.

## Report shape

- **Interface and build** driven.
- **Expected results** and where each came from.
- **Evidence** — commands run, observed results, side-effect readback, and the
  absolute path where the evidence lives.
- **Substituted boundaries** and **untested boundaries**.
- **Safety facts** (when change-impact ran) with how far each was proven, or
  marked unproven.
