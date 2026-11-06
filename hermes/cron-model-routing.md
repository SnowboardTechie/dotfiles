# Scheduled-agent inference routing

Unattended inference runs on one of two approved subscriptions. SGG work stays
on Anthropic (`claude-subscription-directsdk-experimental`, the Agile Six seat);
OpenCode Go is kept out of the `sgg` profile entirely. Since 2026-11-04 Bryan's
personal unattended jobs may run on his OpenCode Go subscription (`opencode-go`).
The reconciler accepts only these two providers. Do not route jobs back to GPT.

| Job | Model | Provider |
| --- | --- | --- |
| SGG Morning Brief | `claude-sonnet-5-5` | Claude |
| SGG PR Review Reminder | `claude-sonnet-5-5` | Claude |
| SGG Dependency Triage | `claude-sonnet-5-5` | Claude |
| SGG Friday Recap | `claude-opus-5-5` | Claude |
| Watch Matt Pocock skill updates | `gemini-4-argon` | OpenCode Go |
| YunoHost update report | `deepseek-v4.1-flash` | OpenCode Go |

Sonnet covers collection-and-summary jobs; Opus covers weekly jobs where
judgment or Bryan's voice matters most. Move a Sonnet job to Opus if its output
quality drops. Routing preserves reasoning inheritance; it does not introduce
effort pins. Script-only jobs remain model-free, and dormant/completed jobs stay
dormant.

## Source ownership

- The default profile's jobs are in `hermes/manifest.json`, reconciled by
  `hermes/reconcile_cron.py`, which refuses any agent job that is not a `claude-`
  model on the Claude subscription provider or a named model on `opencode-go`.
- The four SGG routines (morning brief, dependency triage, PR review reminder,
  Friday recap) moved to the `sgg` profile on 2026-11-03 and deliver to its Bot
  Chat. They have standalone `job.json` and `prompt.md` definitions under
  `hermes/automations/` (`"profile": "sgg"`) and are managed with
  `hermes -p sgg cron ...`, never the fleet reconciler. The sgg profile runs its
  own copies of `sgg-morning-brief.py` and `sgg-pr-review-reminder.py` from
  `~/.hermes/profiles/sgg/scripts/`; the collector's helpers
  (`sgg-calendar-events`, `sgg-mail-messages.js`) stay in the main profile's
  `~/.hermes/scripts/`.
- The Inkling-Small and Colibri GLM-5.2 watches were retired on 2026-11-06.
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
