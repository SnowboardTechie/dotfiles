# Hermes Laptop-to-Studio Migration Reference

> Session-specific facts from 2026-07-15. Re-read `~/code/nix-configs` and inspect the live target before using these values; this file is context, not a substitute for current state.

## Hosts and intent

- Source: Bryan's laptop, Hermes Agent v0.18.2 during planning.
- Target: Apple Silicon Studio (`aarch64-darwin` / `arm64`), user `bryan`.
- Desired runtime: native Hermes for terminal troubleshooting, local AI services, and Apple Reminders.
- Remote command path: outbound-only Matrix gateway; no public Hermes dashboard/API.
- Only one canonical Matrix gateway/state writer may run after cloning state.

## Declarative architecture

Primary sources:

- `~/code/nix-configs/modules/hosts/studio.nix`
- `~/code/nix-configs/modules/services/smb-mount.nix`
- `~/code/nix-configs/modules/base/homebrew.nix`

Evaluated Studio values during the session:

- `system.primaryUser = "bryan"`
- `services.smb-mount.mountPoint = "/Users/bryan/Media"`
- `services.smb-mount.credentialsFile = "/Users/bryan/.smb-credentials"`
- Unraid address: `192.168.1.3`
- SMB share: `media`

The SMB service is a user LaunchAgent. It mounts directly at `/Users/bryan/Media`, unless Finder already mounted the share under `/Volumes/<SHARE>`, in which case the service may symlink the canonical home path to that Finder mount. `/Volumes` showing only Macintosh HD therefore does not establish that the NAS is absent.

## Storage boundary

- The NAS is an unsnapshotted 80 TB dual-parity Unraid array.
- Parity protects against certain disk failures, not logical deletion or overwrite.
- Hermes may access the Studio broadly, but NAS access requires Bryan's explicit authorization for an exact operation.
- The mount is owned by the same `bryan` identity used by native Hermes, so policy and command denials are guardrails rather than a kernel-enforced boundary.
- Do not rearchitect the media server or mount merely to deploy Hermes unless Bryan asks.

Useful command-deny targets prepared for the imported Studio configuration:

- `/Users/bryan/Media`
- Shell aliases that expand to it: `~/Media`, `$HOME/Media`, `${HOME}/Media`
- `/Volumes/media`
- `192.168.1.3`
- Bonjour identity `UnraidTower`
- `mount_smbfs`, `mount_nfs`, and `smbutil`

Hermes matches `approvals.deny` against raw/deobfuscated command text before the shell expands `~` or environment variables. An absolute-path glob alone therefore does not catch `ls ~/Media`; include the common syntactic aliases separately. These remain terminal-command guardrails, not file-tool or OS containment.

Do not use a broad `*unraid*` denial: it can block harmless inspection of local monitoring configuration that uses `unraid` as a label.

## Backup and cutover invariants

A full Hermes backup was confirmed to include:

- `.env`
- `config.yaml`
- `auth.json`
- `state.db`
- `platforms/matrix/store/crypto.db`

Do not use a quick backup or profile export for the final migration because they do not preserve the complete credential/E2EE state.

Cutover order:

1. Install and validate Hermes/native prerequisites on Studio without starting its gateway.
2. Stop the laptop gateway.
3. Create and securely transfer a full backup.
4. Import on Studio while its gateway is stopped.
5. Apply Studio NAS policy and command denials.
6. Test the Studio gateway in the foreground.
7. Install/start the Studio LaunchAgent.
8. Leave the laptop gateway disabled and remove transient archives.

After Studio processes Matrix traffic, rollback requires moving the latest Studio state back to the laptop before restarting the laptop gateway.

## Offline cutover handoff

The operator had to turn Hermes off while performing the final migration. The successful handoff pattern was:

- Open/save a local Markdown runbook before shutdown.
- Label every command block by laptop versus Studio.
- Stop the laptop gateway only from an independent Terminal; commands launched as tools inside that gateway are children of the process being stopped and may be blocked or terminated.
- Use a unique full-backup ZIP, `chmod 600`, `unzip -t`, and a SHA-256 sidecar before encrypted SCP/AirDrop transfer.
- Verify the checksum again on Studio before `hermes import --force`.
- Apply Studio-specific policy after import because import restores source `config.yaml`.
- Validate deny globs by calling the approval matcher with command strings; do not execute a probe against the NAS.
- Test Matrix foreground first, then install the Studio LaunchAgent.
- After acceptance, uninstall the laptop LaunchAgent so login cannot revive the stale cloned gateway.
- Syntax-check the final runbook's fenced shell blocks and execute config-edit snippets only against a temporary isolated Hermes home during verification.

## Reminders and package ownership

`remindctl` was manually installed and authorized during preflight, then declared in the Studio flake so Nix-managed Homebrew cleanup would retain it:

- Tap: `steipete/tap`
- Formula: `steipete/tap/remindctl`
- File: `modules/hosts/studio.nix`

The change passed `nix flake check`, merged-option evaluation, `git diff --check`, and a focused ad-hoc script asserting the evaluated tap/formula.

Hermes Agent itself was not found in Nixpkgs or Homebrew during this session and uses its official managed installation under `~/.hermes`. Do not turn that transient package-search result into a permanent prohibition; re-check current package sources before future changes.

## Hermes Desktop client packaging regression

The final topology used Studio as the only Matrix gateway and `hermes serve` backend, with MBP and gnarbox as Desktop clients over Tailscale. The clients already had a working URL/token saved in Hermes Desktop's per-user connection settings.

A shared Nix module initially wrapped `hermes-desktop` with only:

```text
HERMES_DESKTOP_REMOTE_URL=http://<studio-tailscale-address>:9119
```

This broke gnarbox at runtime even though Nix evaluation and builds passed. Hermes Desktop's resolver gives the environment override precedence over global saved settings; when `HERMES_DESKTOP_REMOTE_URL` is present, it requires `HERMES_DESKTOP_REMOTE_TOKEN` in the environment too. The URL-only wrapper therefore shadowed the valid saved token and raised the paired-variable error. Supplying the secret through Nix would have put it at risk of entering a derivation/store path and was unnecessary.

The durable fix was to:

- Remove the `remoteUrl` module option and URL-injecting wrappers on both Darwin and NixOS.
- Install the upstream Desktop package unchanged.
- Preserve the clients' existing per-user connection settings and credentials.
- Keep MBP's client-only cleanup of stale gateway/serve LaunchAgents independent from Desktop connection configuration.
- Fully quit and reopen Desktop after rebuilding so the old wrapper environment is not inherited by the existing process.

Focused verification should evaluate `environment.systemPackages` for each client, select the actual `hermes-desktop-<version>` package rather than the similarly named `.desktop` launcher derivation, inspect the selected derivation for both remote environment-variable names, and assert the host role separately. Label this an ad-hoc targeted check, not suite-wide proof. Run one client as a runtime canary before fleet rollout.

## Tailscale Serve HTTPS for an authenticated Hermes dashboard

Hermes dashboard bind scope is part of its authentication behavior. Binding the primary remote dashboard to `127.0.0.1` can make Hermes treat it as a trusted local endpoint and disable the remote authentication gate. Do not migrate an authenticated remote backend to loopback merely because Tailscale Serve normally fronts loopback services.

The verified Studio topology keeps the dashboard bound to its non-loopback Tailscale IP and uses a loopback Caddy bridge:

1. Hermes dashboard listens on the Studio Tailscale IP and retains `auth_required: true`.
2. Caddy listens on an unused loopback port, proxies to the authenticated dashboard, sets `Host` to the dashboard's Tailscale-IP listener, and sets `X-Forwarded-Proto: https`.
3. Tailscale Serve terminates HTTPS on the MagicDNS hostname and forwards to Caddy's loopback port.
4. Existing direct Tailscale-IP clients remain usable while clients migrate to the HTTPS hostname.

On this host, configuring Tailscale Serve to proxy directly to the node's own `100.x` dashboard address produced a self-hairpin timeout. Always prove the complete path before changing clients: certificate validation, HTTPS `/api/status`, `auth_required: true`, an unauthenticated `/api/ws` upgrade rejected by Hermes rather than timing out, and a real authenticated Desktop WebSocket connection. Verify the legacy endpoint remains authenticated during migration, the generated Caddy configuration validates, the activated `/run/current-system` equals the evaluated Nix generation, and temporary recovery LaunchAgents/configs are removed.

Do not switch the dashboard bind and restart the active remote session before this canary. A Nix build or HTTP status response alone does not prove that authentication and WebSocket routing survived.

## Intel Darwin client packaging

The later inix rollout added an `x86_64-darwin` client-only host. The Hermes flake exposed package outputs for Apple Silicon Darwin and Linux but omitted `packages.x86_64-darwin`, even though its external overlay and package definitions supported Intel Darwin.

Durable pattern:

1. Do not blindly index `inputs.hermes-agent.packages.${system}` on an omitted system.
2. Make the shared client module derive Desktop from the selected CLI package's passthru (`cfg.package.hermesDesktop`). This keeps CLI/Desktop revisions and overrides coupled.
3. On the Intel host, instantiate Hermes's external overlay with **Hermes's pinned nixpkgs input**, not the homelab repo's independent nixpkgs revision:

   ```nix
   hermesPkgs = import inputs.hermes-agent.inputs.nixpkgs {
     system = pkgs.stdenv.hostPlatform.system;
     overlays = [ inputs.hermes-agent.overlays.default ];
   };
   ```

4. Set `services.hermes.package = hermesPkgs.hermes-agent`, enable Desktop and Tailscale, and retain the client-only role. Do not add gateway/serve or inject saved remote credentials.
5. Build the exact Intel Darwin system and inspect evaluated role flags and generated LaunchAgents.

Using Hermes's overlay with the homelab repo's newer nixpkgs selected a different Electron version than the source's pinned header hash and produced a fixed-output hash mismatch. Using Hermes's own pinned nixpkgs aligned Electron and its source hashes; the full Intel Darwin system then built successfully. This is a version-alignment technique, not a general claim that every upstream overlay supports omitted systems.
