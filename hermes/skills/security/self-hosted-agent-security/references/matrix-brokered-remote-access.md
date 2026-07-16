# Matrix-brokered remote access and migration

Use this pattern when an always-on agent must accept requests away from home without publishing its dashboard/API. Re-verify adapter behavior and backup contents against the installed Hermes version before migration.

## Security topology

```text
Remote Matrix client
  -> Matrix homeserver
  -> outbound HTTPS sync from Hermes gateway
  -> local agent runtime
```

The Matrix adapter connects outward to its homeserver and starts a sync loop. No inbound router port, public dashboard, reverse proxy, or tunnel is required for Matrix chat. This materially reduces the public attack surface, but it does **not** make the agent local-only: the authorized Matrix identity becomes a remote command credential.

If local desktop access is also needed, expose `hermes serve` only on the LAN, keep its application auth enabled, do not port-forward it, and firewall it to trusted devices/subnets. If Matrix and cron are sufficient, do not run `hermes serve` at all.

## Matrix hardening checklist

- Use a dedicated bot account and a private encrypted DM/room.
- Set `allowed_users` to exact full Matrix IDs. If unset, any sender in a joined room may trigger an agent turn.
- Set `allowed_rooms` for non-DM rooms. Matrix DMs are exempt from the room filter, so sender authorization remains essential.
- Remember that the adapter auto-accepts room invites; allowlists, not room membership alone, are the authorization boundary.
- Set `MATRIX_E2EE_MODE=required` so missing crypto dependencies fail closed instead of silently allowing plaintext rooms.
- Verify runtime logs show E2EE enabled, initial sync complete, and Matrix connected; configuration presence alone is insufficient.
- Keep approval reactions requester-bound (`MATRIX_APPROVAL_REQUIRE_SENDER=true`) and dangerous-command approvals enabled.
- Keep cross-room, room-creation, invitation, redaction, and public-room tools disabled unless explicitly required.
- Protect the user account, bot token, recovery key, and verified devices. A stolen authorized Matrix session can control the agent even though no agent port is public.
- Run Hermes as a dedicated unprivileged OS account and scope its filesystem, credentials, sudo, and tools.

## Secret-safe configuration audit

When confirming an existing setup, do not print `.env`, tokens, recovery keys, room IDs, or user IDs. Parse config locally and report only:

- whether homeserver, bot user, access token/password, and home room are configured
- counts and sources of allowed users/rooms
- E2EE mode and recovery-key presence
- crypto-store presence and relative location
- mention/notices/approval policy values
- gateway service state

Then inspect recent gateway logs with identifiers and URLs redacted. Look for effective runtime state and warnings; do not equate a configured token with a healthy sync loop.

## Full-backup migration behavior

For Hermes v0.18.2, a normal `hermes backup` walks the Hermes home and includes `.env`, `config.yaml`, `auth.json`, `state.db`, cron state, and `platforms/matrix/store/crypto.db`. SQLite files are copied through the SQLite backup API; WAL/SHM/journal sidecars and machine-local runtime files are excluded. Verify archive member names on the installed version without extracting or printing secret contents.

Important distinctions:

- `hermes backup --quick` captures critical generic state but does **not** include the Matrix crypto store.
- `hermes profile export` strips credentials and is not a full Matrix-device migration.
- Full backups exclude the Hermes codebase, venv/site-packages, caches, and service-manager definitions. Reinstall Hermes, Matrix/E2EE dependencies, `libolm`, and the gateway service on the destination.
- The archive contains live credentials and encryption identity; transfer it securely and delete residual copies.

## Safe migration sequence

1. Install Hermes and Matrix/E2EE prerequisites on the destination.
2. Stop the source gateway before the final backup so Matrix crypto state cannot continue diverging after the snapshot.
3. Run a full `hermes backup` without `--quick`.
4. Transfer securely and run `hermes import` on the destination.
5. Install/start the destination gateway service and verify E2EE, sync, and delivery.
6. Leave the source gateway stopped or give it a separate bot token/device/account.

Never run two gateways concurrently with the cloned Matrix token, device ID, and crypto database. This can create duplicate replies and divergent encryption state. Also verify machine-specific paths, service startup semantics, provider reauthentication, and sleep/login behavior on the destination.

## Authoritative references

- Hermes Matrix setup: https://hermes-agent.nousresearch.com/docs/user-guide/messaging/matrix
- Hermes backup/import FAQ: https://hermes-agent.nousresearch.com/docs/reference/faq#exporting-hermes-to-another-machine
- Installed implementation: `hermes_cli/backup.py` and `plugins/platforms/matrix/adapter.py`
