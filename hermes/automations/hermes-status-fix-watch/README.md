# Retired: Hermes upstream status-fix hold watcher

This watcher is no longer installed or scheduled by the dotfiles manifest.
The exact installed script digest is recorded in `removedCopiedScripts` so
normal reconciliation removes only the unmodified managed copy. The source
and its offline recognition tests remain as history, not an active release gate.

The watcher originally supported Bryan's 2026-10-14 temporary nightly-update
hold while the classic `/status` query used `session_key` instead of the
`session_id` used by `/yolo`. Herdr's admission checks needed the local repair.

Bryan clarified on 2026-10-23 that repairing automatic updates means making
them work, not disabling them. The replacement in nix-configs follows the
installation's configured update channel, accepts detached stable releases,
and admits only the exact reviewed status patch. It predicts the patch merge
before downtime, uses Hermes's supported stash/restore, and checks the target,
install stamp, retained correction and service health after updating. An
identical upstream correction is absorbed automatically; upstream is no longer
a prerequisite for normal upgrades.

Source of truth:
https://git.snowboardtechie.com/bryan/nix-configs/src/branch/main/docs/hermes-auto-updates.md

Do not re-enable this watcher or use its historical “nightly remains disabled”
message to infer current operational state. Nix owns the update schedule;
read the deployed launchd job and updater receipts for live evidence. The
unrelated clarify-context watcher is unchanged.
