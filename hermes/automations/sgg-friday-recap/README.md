# SGG Friday recap

Accepted by Bryan on 2026-10-06: Fridays at 11 a.m. America/Los_Angeles, a Slack-ready weekly SGG recap delivered to the existing private SGG Matrix room for review. Never automatically post to Slack.

`prompt.md` is the versioned synthesis and source contract. `job.json` records the desired scheduler fields; it is a standalone ongoing job managed through `cronjob_manage`, deliberately not an entry in the fleet's pin-requiring `hermes/manifest.json`. No new inference pin was authorized. The job follows Hermes's configured cron default.

Creation: list jobs first and require at most one exact name match. Create paused with the prompt bytes and matching schedule, delivery, skills, workdir, toolsets and continuation fields. Validate the scheduler timezone is America/Los_Angeles. Set explicit continuation origin to the room and Bryan's Matrix identity, using the supported cron.jobs update API if creation from CLI lacks origin context. Read back all fields before running.

Run every Friday indefinitely until Bryan pauses or stops the job. `repeat: null` means no execution limit; live state must store `repeat.times=null`. Preserve the completed execution count when changing the limit or prompt. The initial partial-week preview is execution history, not a limit on future recaps. Bryan explicitly corrected the agent's mistaken four-Friday pilot on 2026-10-06; the requested cadence is ongoing.

First scheduled run: October 9, 2026, at 11 a.m. Pacific, then every Friday without an end date. Holidays remain weekdays; short weeks receive shorter honest updates. No calendar source or new holiday integration is needed.

Collection uses read-only file, git and GitHub lookups plus Granola metadata and notes. The terminal/file tools are not a capability-enforced read-only sandbox: the prompt prohibits mutations, while scheduler delivery is explicitly limited to private Matrix. No messaging toolset is enabled. All source context stays within SGG, and the concluded workday-note experiment remains retired.

Verify a real preview's rendered draft, exact date window, direct GitHub links, source-gap separation, and a concrete Matrix delivery event ID. A scheduler success alone is not delivery proof. Cron retains local execution history; this job does not create a vault archive or copy Granola notes into the vault.

Future edits: read the exact live definition, compare it with these files, update only task-owned fields through cronjob_manage, read back, and commit/push the source changes. Preserve execution history and existing model policy. The fleet reconciler leaves this standalone job untouched. Never create a duplicate, impose a finite repeat limit, or enable Slack delivery by implication.

Setup verification, 2026-10-06: live job `007cf5e7b93f` produced a correctly labeled Monday-through-Tuesday partial-week preview. Granola metadata and read-only GitHub lookups executed. Matrix transport acknowledged event `$CDx0DjV3i8uxNGEvCvrLCY5mpaFGahnbqnX3GoVDXdo`, and the reply-facing Matrix session was seeded. Scheduler readback shows success, no delivery error, one completed execution, and the next run at `2026-10-09T11:00:00-07:00`. Recipient confirmation remains separate from transport acknowledgement. Preview inspection prompted stronger checks for repeated bare issue numbers and unsupported negative implementation claims. The previously unset Hermes timezone was explicitly set to America/Los_Angeles, matching the host's current Pacific time. The original five-execution limit was an agent mistake and was removed at Bryan's correction; no additional test delivery is required for a repeat-limit-only change.
