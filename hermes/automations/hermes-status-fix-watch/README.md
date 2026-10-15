# Hermes nightly update hold

Bryan approved pausing his nightly update on 2026-10-14 and requested an upstream
fix watch. Only the user LaunchAgent `gui/501/ai.hermes.update` is disabled and
unloaded. The hold is a persistent launchd disabled override, not a change to
Traci's schedule or the gateway/dashboard. The Nix definition remains present;
this temporary operational override must remain in place until deliberate release.
After any system deployment, verify `launchctl print-disabled gui/$(id -u)` still
lists `ai.hermes.update` as disabled. Do not blindly reload or enable it.

Reason: the required local `cli-status-session.patch` fixes classic `/status`
querying nonexistent `session_key` instead of `session_id`. Herdr uses truthful
native approval status. The managed nightly wrapper rejects the dirty checkout.
A separate successful v0.22.0 update also left detached HEAD, while the existing
wrapper requires `main`; fixing the upstream status line alone does not establish
that nightly updates are safe to resume.

`Watch Hermes status fix for nightly updates` runs daily at 09:20 Pacific,
model-free, through the default-profile Hermes cron scheduler. Its script resolves
upstream main to an immutable SHA, inspects that exact source statically, stays
silent while the known bug remains, and alerts the private Second Brain Matrix
room on the pending-to-fixed transition. Unknown/refactored source or retrieval
failure is an actionable error, not a false pending result. No fetched code is
executed. No runtime update, patch removal, service restart or automatic re-enable
is authorized by this watch. The alert identifies a candidate for review, not a
verified safe update. Cron history owns delivery evidence; watcher state records
notification preparation. Recover saved output if transport fails.

Before resuming:

1. Verify the immutable upstream fix and current Herdr compatibility, including
   current YOLO toggle/preflight behavior.
2. Preserve the local patch and any unrelated work; remove the patch only when the
   replacement runtime supplies the correction.
3. Reconcile current Hermes updater checkout behavior with the Nix-managed wrapper
   (do not force `main` merely to bypass its guard).
4. Exercise the supported update path with its state backup and health checks.
5. Release the launchd override deliberately with
   `launchctl enable gui/$(id -u)/ai.hermes.update`, then load its existing managed
   plist. Verify loaded schedule and enabled state; do not trigger a surprise update.
6. Retire this watcher from manifest/live cron and remove its installed script and
   source-specific tests once the hold is resolved.

Source: `hermes/scripts/check-hermes-status-fix.py`, manifest and adjacent prompt.
Tests: `python3 hermes/test_hermes_status_fix_watch.py`.
