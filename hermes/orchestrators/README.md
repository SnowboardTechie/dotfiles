# Hermes orchestrator contracts

This directory holds reusable operating-contract assets for durable Hermes
orchestrators. It does not register an agent, start a goal, grant authority, or
replace a domain skill. A contract makes an already-proven control loop explicit
before it receives durable continuation or publication authority.

## Contract layers

An orchestrator contract has two linked layers:

1. **Persistent goal block** — the compact `/goal` or `!goal` contract Hermes
   must preserve on initial kickoff and every resume: objective, outcomes,
   verification, constraints, authority boundaries, and stop conditions.
2. **Operating annex** — trigger and lifecycle, canonical sources and state,
   reconciliation, specialist lanes, approval gates, idempotency, checkpoints,
   failure behavior, escalation, and activation evidence.

Use [`contract-template.md`](contract-template.md) for both layers. Keep large
domain procedures in their owning repository or skill and link them from the
annex instead of copying them into the pasteable goal block.

## Adoption rules

- Start from a representative manual run or an existing proven loop.
- Name one orchestrator as final synthesis and authority owner.
- Divide specialists by independent evidence lane, not personality or arbitrary
  sequential phase.
- Give every specialist a bounded input, output, mutation policy, and verifier.
- Separate initiation from authority. Cron, webhook, Matrix, or Desktop kickoff
  does not broaden allowed actions.
- Bind authorization to each supported surface. Desktop workspace identity and
  a Matrix sender/room identity are different proofs.
- Keep canonical state outside chat. Name the repository, vault, issue tracker,
  or database that owns each state domain.
- Make reruns and resumes reconcile before acting. Define idempotency and
  concurrent-run behavior.
- Fail closed when authority, state, sources, or verification are incomplete.
- Distinguish designed, implemented, installed, activated, and verified-live.

## Validation

Validate the persistent goal block deterministically:

```bash
python3 hermes/orchestrators/validate_contract.py path/to/contract.md
```

Use `--allow-placeholders` only for an uninstantiated template. The validator
checks syntax and minimum safety structure; it cannot prove that sources,
permissions, identity, or runtime activation claims are true. Those require the
operating annex's concrete probes and live evidence.

The first concrete reference is CairnOS Autopilot. Its active issue-21 candidate
is intentionally validated read-only while that worktree remains in progress;
this directory must not rewrite or absorb concurrent repository work.
