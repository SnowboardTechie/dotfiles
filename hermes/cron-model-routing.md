# Scheduled-agent inference routing

The seven active model-backed jobs use `gpt-6.1-sol` through `openai-codex`.
The October all-job comparison used **medium** effort for all three candidates.
The routing change preserves reasoning inheritance; it does not introduce effort
pins. Script-only jobs remain model-free, and dormant/completed jobs stay dormant.

## Source ownership

- Four jobs are in `hermes/manifest.json`, reconciled by `hermes/reconcile_cron.py`.
- The Friday recap and Inkling/Colibri watches have standalone `job.json` and
  `prompt.md` definitions under `hermes/automations/`. They are not created by the
  fleet reconciler. The Inkling watch references its existing installed collector;
  a definition is not a deployment claim for that script on a new machine.
- The default profile's `cron.model` is also `gpt-6.1-sol`, with
  `cron.model_provider: openai-codex`, for future jobs that inherit routing.

Use the supported CLI after explicit routing authorization:

    hermes config set cron.model gpt-6.1-sol
    hermes config set cron.model_provider openai-codex
    hermes cron edit JOB_ID --model gpt-6.1-sol --provider openai-codex

List jobs first and match the exact name uniquely. Change existing records rather
than recreating them. Preserve schedules, delivery, continuation, finite-run state,
enabled/paused state, prompts, scripts and effort settings. Standalone job files
record desired creation fields, not changing scheduler bookkeeping or credentials.

Run `python3 -m unittest hermes.test_active_cron_model_routing` for the source
contract. Read back live records separately; a stored model assignment is not
proof the next scheduled execution has already used it.
