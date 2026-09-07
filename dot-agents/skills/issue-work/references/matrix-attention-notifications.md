# Matrix attention notifications

Use this reference after `issue-work` starts work that may continue while Bryan is
away. These alerts supplement the normal conversation; they do not replace the
inline checkpoint, blocker report, review summary, or completion report.

## Arm once asynchronous work starts

Arm attention notifications immediately before the first Phase 2-or-later
delegated, background, or visible task or finite watcher is launched, including
Phase 2 exploration, Herdr Claude/Hermes work, Qwen work, or the fresh review
worker. A short-lived Phase 1 intake child does not arm them. Keep notifications
armed through the terminal end of the workflow. Record the armed timestamp and
resolved target under `## Attention notifications` in `progress.md`.

If the run stops before notifications are armed, use the normal conversation only.
Do not send routine startup or progress notices.

## Resolve the room conservatively

1. Derive the project identity from the **ticket workspace authority**: its
   canonical project name, active repository instructions, and any explicit
   project-family or Matrix-room alias. In a cross-repository handoff, do not
   route from the implementation repository alone; the ticket workspace owns the
   project context.
2. Run `hermes send --list matrix --json` and inspect the current configured
   targets. Never read Matrix credentials and never infer a room from list order.
3. Select a project room only when exactly one listed room has an obvious match:
   an exact normalized project name or an explicit alias from trusted project
   instructions. Normalize by lowercasing and removing spaces, punctuation, and
   separators; do not otherwise fuzzy-match a similarly named room.
4. With no unique obvious project match, select the unique listed room whose
   normalized name is `Hermes`. If that room is unavailable or ambiguous, use
   bare `--to matrix` only after the canonical configured Matrix home target is
   independently confirmed to be the Hermes room. Otherwise record notification
   delivery as unavailable rather than guessing.
5. Persist the exact `matrix:!room-id` target for the run. Re-resolve it on resume
   before sending; if it disappeared or changed identity, apply the same rules
   again and record the change.

## Alert only on attention transitions

After notifications are armed, send one alert when either condition becomes
true:

- **Action needed / blocked:** the parent cannot continue without Bryan's answer,
  approval, correction, credentials, local-tree decision, or other intervention;
  or the run reaches a persistent blocker or retry/review bound. Plan approval
  and the ready-to-ship approval checkpoint count as action needed even though
  they are expected workflow gates.
- **Complete:** the user-requested terminal result has been verified and no
  further issue-work step remains. On the default path this means `/ship` has
  created the draft PR, remote readback succeeded, and handoff-owned panes whose
  work is over have been released. A settled worker, green implementation,
  completed review, or `ready to ship` state is not completion. If Bryan
  explicitly limits the requested scope to a pre-publication result, that
  verified result may be terminal completion.

Do not alert for routine phase changes, successful worker settlement that the
parent can process, test passes, correction iterations, or informational
progress. Continue the normal inline response at every action-needed or complete
transition.

## Message shape and mention

Load `outbound-communication-safety` and its Matrix mention reference. Every
attention alert starts with Bryan's authoritative full MXID; the currently
confirmed value is `@bryan:snowboardtechie.com`. Do not use a display name.

Keep the message short and actionable:

- Action needed: `Issue work needs you — {project/ticket}`; then `State: {gate or
  blocker}` and `Need: {one exact answer or action}`.
- Complete: `Issue work complete — {project/ticket}`; then `Result: {verified
  terminal outcome}`, `Checks: {concise verified evidence}`, and the PR URL when
  one exists.

Include issue, PR, repository, and local-state identifiers only when they are safe
for the selected room. Preserve the private cross-repository publication rules;
a notification is not permission to disclose a private ticket identity.

If the current conversation already originates in the exact resolved Matrix room,
make the normal action-needed/completion response itself the alert by beginning it
with the MXID. Do not send a duplicate one-off message. From another surface, send
through:

```bash
hermes send --to "matrix:!room-id" --json "{message}"
```

The user's request for issue-work attention notifications authorizes these two
message classes and their conservative project-room routing; do not ask for a
second send confirmation.

## Deduplicate and verify

Before sending, compute a stable event key from the canonical ticket, alert class,
and exact gate/blocker or terminal-result identity. Check `progress.md`; do not
repeat a key already recorded as delivered. A changed blocker or a materially new
question gets a new key.

For a one-off send, parse the JSON result and require a successful Matrix adapter
response with an event/message identifier before recording delivery. When a
supported Matrix history/readback surface is available, read back the exact
target/event as well. An event ID proves adapter handoff, not that Bryan saw the
alert; report it as sent, not seen. For the same-room inline path, record the
event key, exact current Matrix origin, and `delivery: current-session`; a
separate adapter event ID is neither available nor required, and the one-off
sender must not create a duplicate.

Append the timestamp, event key, alert class, target room ID/name, adapter event
ID or current-session marker, and outcome to `progress.md`. On a definite
project-room send failure, make one fallback attempt to the resolved Hermes room,
marking the message and ledger as fallback delivery. On timeout or uncertain
delivery, inspect available history/log evidence before retrying so the safeguard
does not create a duplicate.
If delivery still fails, record the failure and surface it in the current
conversation, but continue issue work whenever the notification transport itself
is not the implementation blocker.
