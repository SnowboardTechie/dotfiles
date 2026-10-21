# Scheduled-agent inference routing

Bryan is retiring his OpenAI subscription, so unattended inference runs on his
Claude subscription through the `claude-subscription-directsdk-experimental`
provider. Do not route jobs back to GPT unless no Claude route can do the work.

| Job | Model |
| --- | --- |
| Workday Morning Brief | `claude-sonnet-5-5` |
| SGG PR Review Reminder | `claude-sonnet-5-5` |
| Workday Dependency Triage | `claude-sonnet-5-5` |
| Watch Inkling-Small release | `claude-sonnet-5-5` |
| Watch Colibri GLM-5.2 Studio readiness | `claude-sonnet-5-5` |
| Watch Matt Pocock skill updates | `claude-opus-5-5` |
| SGG Friday Recap | `claude-opus-5-5` |
| Watch for official Pi Durable Claude provider | `claude-opus-5-5` |

Sonnet covers collection-and-summary jobs; Opus covers weekly jobs where
judgment or Bryan's voice matters most. Move a Sonnet job to Opus if its output
quality drops. Routing preserves reasoning inheritance; it does not introduce
effort pins. Script-only jobs remain model-free, and dormant/completed jobs stay
dormant.

## Source ownership

- Five jobs are in `hermes/manifest.json`, reconciled by `hermes/reconcile_cron.py`,
  which refuses any agent job that is not a `claude-` model on the Claude
  subscription provider.
- The Friday recap and Inkling/Colibri watches have standalone `job.json` and
  `prompt.md` definitions under `hermes/automations/`. They are not created by the
  fleet reconciler. The Inkling watch references its existing installed collector;
  a definition is not a deployment claim for that script on a new machine.
- The default profile's `cron.model` is `claude-sonnet-5-5`, with
  `cron.model_provider: claude-subscription-directsdk-experimental`, for future
  jobs that inherit routing.

Use the supported CLI:

    hermes config set cron.model claude-sonnet-5-5
    hermes config set cron.model_provider claude-subscription-directsdk-experimental
    hermes cron edit JOB_ID --model MODEL --provider claude-subscription-directsdk-experimental

List jobs first and match the exact name uniquely. Change existing records rather
than recreating them. Preserve schedules, delivery, continuation, finite-run state,
enabled/paused state, prompts, scripts and effort settings. Standalone job files
record desired creation fields, not changing scheduler bookkeeping or credentials.

Run `python3 -m unittest hermes.test_active_cron_model_routing` for the source
contract. Read back live records separately; a stored model assignment is not
proof the next scheduled execution has already used it.
