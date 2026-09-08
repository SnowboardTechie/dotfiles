# Security review

Review scope: this plugin and its installer behavior in the same Git candidate.
The review covers source, privileges, data flow, egress, authorization,
persistence, updates, and failure behavior.

## Provenance and execution privilege

The plugin is repository-owned Python with no third-party code and no imports
beyond the standard-library `logging` module. Hermes plugins are not sandboxed:
once loaded, this code executes with the full privileges of Bryan's Hermes
process. The manifest requests no capabilities, and activation explicitly denies
built-in tool override permission. The narrow source is therefore the security
boundary; any future source change requires a new review before deployment.

## Data and network flow

The plugin reads only Matrix crypto objects already held by the connected
Mautrix client: current room membership, device identities and trust, existing
Olm state, and a retained Megolm room key requested through Mautrix. It opens no
files, reads no environment variables or credentials, starts no processes, and
constructs no network destination. Its only egress is through Mautrix's existing
authenticated homeserver connection: one-time-key claims for authorized devices
and encrypted room-key delivery to the exact requesting device. It does not log
message bodies, room keys, device keys, credentials, or ciphertext.

## Authorization boundary

Cross-user recovery is limited to:

- `@bryan:snowboardtechie.com`;
- four exact, private Bryan/Hermes room IDs;
- a user who is currently joined to the requested room; and
- devices whose effective Mautrix trust is `CROSS_SIGNED_TOFU`,
  `CROSS_SIGNED_TRUSTED`, or `VERIFIED`.

Deleted, blacklisted, unknown, forwarded-only, unverified, other-user, and
other-room requests retain Mautrix's default policy. Live inspection confirmed
that all 16 of Bryan's current devices are cross-signed. The shared three-person
Welcome room is deliberately excluded.

## Persistence and updates

The installer copies a frozen plugin directory rather than linking the mutable
repository checkout. It rejects source-tree symlinks, foreign or broken
destination symlinks, and paths escaping `HERMES_HOME`; updates preserve the
previous deployed tree under the existing timestamped backup root. Activation
uses Hermes's own CLI with `--no-allow-tool-override`.

## Failure behavior and residual risk

The plugin uses Mautrix's private `_create_outbound_sessions` method and private
`_force_recreate_session` argument. An incompatible Mautrix update can therefore
break key recovery availability. It cannot widen a recipient or network target:
authorization remains at the exact user/room/trust checks and Mautrix's own
send path. Pre-share Olm refresh failure is logged and falls back to Mautrix's
normal encrypted send; a later authorized key request retries over a fresh Olm
channel. A failed recovery request remains undecryptable rather than being sent
plaintext.

Review decision: acceptable for the stated four private rooms after the
cross-signed-device restriction and frozen-copy deployment changes above.
