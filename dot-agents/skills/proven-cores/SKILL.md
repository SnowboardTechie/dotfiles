---
name: proven-cores
description: Use when planning logic whose rules must never break. Weigh a Bend 2 proven core (human-approved laws, agent-written proofs, a gate outside the candidate) as one option beside ordinary tests, with its fit limits and costs.
---

# Proven cores

Bryan's standing direction (2026-10-22): when planning work whose rules must never break, consider a
Bend 2 proven core as one option. It is an option to weigh, not a default. Using it in a repository
needs that repository's own accepted plan, plus Bryan's approval for the toolchain in CI and Nix
under his software-additions rule.

Record of the review and the experiment: durable-pi-workspace
`vault/explorations/2026-10-22-bend-proven-cores-reference.md`.

## When to raise it

Raise it for pure decision logic with rules that must hold over every sequence of events:

- lifecycles and state machines;
- approval and authority gates;
- ledgers and conservation rules;
- deduplication and exactly-once bookkeeping;
- retry and recovery ceilings.

It matters most behind unattended actions, where tests only sample and a miss is expensive.

Do not raise it for:

- IO, HTTP, JSON or text glue;
- whole services or UI;
- Python hosts (no Python target yet);
- 64-bit or floating-point math (no U64, I64 or F64, and nothing about F32 can be proven);
- cheap failures that tests already cover well.

## How to present it

- **Shape.** The host keeps effects, transactions and readback, and calls one exported pure
  `step(state, op)`. `bend core.bend -o core.mjs` emits a dependency-free ES module. Values cross as
  `{$: "Ctor", field: …}`, with Nat as a JavaScript number.
- **First cost.** Extracting a pure decision function from transactional code is usually the larger
  cost, and it pays even if Bend is rejected.
- **Alternatives.** Name them with honest trade-offs:
  - property tests in the host language;
  - Dafny (compiles to JavaScript; its SMT backend writes most proof steps but can fail
    unpredictably);
  - SPARK or Verus where the host language fits.

  Bend's case is fast, explicit, deterministic checking. Its cost is hand-written proofs and a young
  toolchain.

## Conditions for any use

1. **Gate the laws outside candidate control.** The gate requires the approved `LAWS.bend` digest,
   the pinned Bend version and ALL PROOFS CHECK, plus `--verdict` once Lean v4.34 is available. Bend
   itself only checks that `PROOF.bend` imports `LAWS.bend`, so a weakened law passes.
2. **Make laws quantify only over the exported entry point.** Define every predicate and the replay
   of operations inside `LAWS.bend`. A law that reads a helper from the core can be made vacuous by
   editing that helper.
3. **Test the host glue.** Ordinary tests must show the host routes its decisions through the core;
   the proof covers only the core.
4. **Pin the version and upgrade deliberately.** Releases are weekly, and 2.0.38 changed how JS hosts
   see constructor tags.
5. **Model what the law protects.** Laws reason only about what the model represents. The spike's
   model tracked state labels, not in-flight work, so mislabeling a still-stopping run as failed
   passed. If a rule is about work in flight, the model must carry it.
6. **Add Bend's AGENTS.md block.** Every repository where Bend code is committed carries this block
   verbatim, by Bryan's direction. Its own conditions (gate, approvals) follow it. Bryan's global git
   ignore excludes AGENTS.md, so the repository opts in with `!AGENTS.md` in its `.gitignore`.

   ```text
   When using Bend:
   - run `bend guide` to learn it
   - use `LAWS.bend` to keep important rules
   - run `bend PROOF.bend` before committing
   - parallelize the code whenever possible
   ```

## Writing Bend proofs

- Read `bend guide` and `demos/app_win_is_bug_2d` first. It is the step-and-replay template.
- **The pattern:**
  - a Boolean invariant `inv`, reflected as a type with `T(b)`;
  - one lemma per operation, where most cases close by conversion and simply return `h`;
  - induction over the operation list;
  - converting `T(law)` into the law's equality inside that same induction, so the affine `ops` is
    walked once.
- **Matching rules.**
  - Matches follow parameter order.
  - A computed value cannot be matched: pass it to a helper parameter (`+ok: Bool`) and match there.
  - Reuse needs `+` on parameters, pattern fields and lambda parameters.
  - An erased `-` parameter cannot be matched.
- **Budget for basics.** Base ships almost no lemmas.
- **A rejection is not a bug.** Brittle proofs reject safe changes. Classify a rejected change by a
  concrete counterexample from the compiled core, not by the gate's verdict.
- **Calibrate every checker.** A randomized check must find a planted bug before its silence means
  anything. Low-bit moduli of a power-of-two LCG produced near-identical sequences and missed the
  planted bug entirely.

## Cost reference (one data point)

The plan-run lifecycle spike:

- 3 laws, 15 lines of statements, over a 402-line core;
- 535 proof lines, 8 check rounds, about 9 minutes of Claude Opus time;
- 0.08 s to check;
- a 767-line `.mjs`, about 0.1 µs per step in Node;
- all real injected bugs unprovable, and two safe changes needing one proof-repair round.

Head-to-head with the existing TypeScript suite (291 tests, about 52 s per run), on the same injected
bugs:

- Both caught overlap, an ignored generation and a cancel that does not advance the generation.
- The laws alone caught "resume ignores the readback", which is probably unreachable in the host
  today.
- The suite alone caught an authorization bug, which is outside the core.
- The laws missed a bug the model cannot represent (in-flight work).
- Weigh the laws as every-ordering coverage of a narrow core, not a replacement for host tests.

Upkeep:

- **A new law:** 1 round, 96 s, no core change.
- **A new state plus operation:** 2 rounds, 37 s, about 60 lines each in core and proof. The edit is
  mechanical: every case-by-case match gains one arm.

## Environment

- Bend 2.0.38 is installed user-locally on Studio in `~/.bend` and is not on `PATH`. Run it with
  `export PATH="$HOME/.bend/bin:$PATH" BEND_NO_TELEMETRY=1`. No service uses it, and Lean is not
  installed.
- The spike is at `~/code/bend-lifecycle-spike` on Studio: local only, with its gate in
  `tools/laws-gate.sh` and injected-bug runs in `tools/mutants.py`.
