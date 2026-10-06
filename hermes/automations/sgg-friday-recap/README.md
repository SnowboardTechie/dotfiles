# SGG Friday recap pilot

Accepted by Bryan on 2026-10-06: Fridays at 11 a.m. America/Los_Angeles, a Slack-ready weekly SGG recap delivered to the existing private SGG Matrix room for review. Never automatically post to Slack.

`prompt.md` is the versioned synthesis and source contract. `job.json` records the desired scheduler fields; it is a standalone finite pilot managed through `cronjob_manage`, deliberately not an entry in the fleet's pin-requiring `hermes/manifest.json`. No new inference pin was authorized. The job follows Hermes's configured cron default.

Creation: list jobs first and require at most one exact name match. Create paused with the prompt bytes and matching schedule, delivery, skills, workdir, toolsets and continuation fields. Validate the scheduler timezone is America/Los_Angeles. Set explicit continuation origin to the room and Bryan's Matrix identity, using the supported cron.jobs update API if creation from CLI lacks origin context. Read back all fields before running.

Five executions reserve one manual partial-week preview plus four scheduled Fridays. Manual runs consume pilot progress. After the initial preview, require repeat.completed=1, repeat.times=5, and the next run at Friday 11 a.m. Pacific. Do not reset completed counts on later prompt updates or recreation. Do not silently extend the pilot after it finishes; review usefulness with Bryan before continuing.

Expected scheduled dates: October 9, 16, 23 and 30, 2026. Holidays remain weekdays; short weeks receive shorter honest updates. No calendar source or new holiday integration is needed.

Collection uses read-only file, git and GitHub lookups plus Granola metadata and notes. The terminal/file tools are not a capability-enforced read-only sandbox: the prompt prohibits mutations, while scheduler delivery is explicitly limited to private Matrix. No messaging toolset is enabled. All source context stays within SGG, and the concluded workday-note experiment remains retired.

Verify a real preview's rendered draft, exact date window, direct GitHub links, source-gap separation, and a concrete Matrix delivery event ID. A scheduler success alone is not delivery proof. Cron retains local execution history; this job does not create a vault archive or copy Granola notes into the vault.

Future edits: read the exact live definition, compare it with these files, update only task-owned fields through cronjob_manage, read back, and commit/push the source changes. Preserve pilot progress and existing model policy. The fleet reconciler leaves this standalone job untouched. Never create a duplicate or enable Slack delivery by implication.
