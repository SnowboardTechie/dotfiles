# macOS Native Integrations: Capability Audit

Use this checklist when preparing a macOS host for an agent that must operate Apple Reminders, Calendar, Notes, Mail, or arbitrary native apps. It is deliberately metadata-only: capability audits should not dump personal content.

## Readiness model

Record each integration across four independent layers:

| Integration | Declared | Installed | TCC-authorized | Read exercised | Write exercised | Runtime context |
|---|---:|---:|---:|---:|---:|---|
| Reminders |  |  |  |  |  | interactive / gateway |
| Calendar |  |  |  |  |  | AppleScript / GUI / CLI |
| Notes |  |  |  |  |  | AppleScript / GUI / CLI |
| Mail |  |  |  |  |  | AppleScript / GUI / IMAP |
| Computer Use |  |  |  | capture | click/type | agent session |

Do not mark the row ready because only one column is true.

## Package and tool discovery

Inspect declarations before suggesting manual installation:

```bash
rg -n 'remindctl|cua-driver|computer_use|memo|himalaya|icalBuddy' ~/code/nix-configs
nix eval --json '.#darwinConfigurations.<host>.config.environment.systemPackages' \
  --apply 'xs: map (x: x.name or "") xs'
```

Homebrew packages may not appear in `environment.systemPackages`; evaluate the host's merged `homebrew.brews`, `homebrew.casks`, and taps separately.

Check the live target without reading application data:

```bash
command -v remindctl cua-driver memo himalaya icalBuddy osascript
hermes tools list
```

An enabled Hermes toolset and an installed dependency are different facts.

## Computer Use

Hermes Computer Use requires both the enabled toolset and the external driver:

```bash
hermes tools list
hermes computer-use status
hermes computer-use doctor
```

If the driver is absent, the supported setup path is:

```bash
hermes computer-use install
```

Then grant permissions and rerun the checks:

```bash
cua-driver permissions grant     # user approves the macOS dialogs
cua-driver permissions status
hermes computer-use status
hermes computer-use doctor
```

The installer may place the binary in `~/.local/bin` and update shell startup files. A same-process `status` check can still miss the new path; verify the absolute binary first and test with `PATH="$HOME/.local/bin:$PATH"` rather than declaring installation failed. Remove any duplicate PATH line the installer appended when dotfiles already own it.

Check the driver's telemetry setting explicitly; some releases enable content-free telemetry by default. For privacy-oriented hosts, disable it and verify the persisted setting:

```bash
cua-driver telemetry disable
cua-driver telemetry status
```

The user—not the agent—approves Accessibility, Screen Recording, or other macOS privacy dialogs. Toolset changes require a fresh agent session because tool schemas are fixed at session start.

When a declarative repository is the source of truth, first check whether a pinned Nix/Homebrew package exists. Do not hide an upstream “latest” download inside an activation script. A supported mutable user install can be acceptable when explicitly documented and kept separate from Nix-managed launchd supervision.

## Reminders

For `remindctl`, installation is not authorization:

```bash
remindctl --version
remindctl status
```

If status is `Not determined` or denied, run the current target binary's authorization flow and let the user approve the prompt:

```bash
remindctl authorize
remindctl status
```

TCC grants are target-local, executable- and host-context-specific. A prior authorization on another host—or against a replaced executable—does not prove the current binary is authorized. Run `status` from the same runtime context the agent will use; an interactive Terminal grant may not prove a launchd/Python caller can use EventKit.

On macOS Tahoe, `remindctl authorize` can hang or fail to surface a prompt. The upstream-documented workaround is to trigger Reminders automation from the same host application, let the user approve the resulting Terminal/Python prompt, and then rerun status:

```bash
osascript -e 'tell application "Reminders" to count reminders' >/dev/null
remindctl status
```

Once status reports full access, exercise a privacy-preserving read without exposing reminder text:

```bash
remindctl today --quiet >/dev/null
```

Do not list reminders during an access audit. Exercise creation/editing only after the user approves the specific mutation.

## Calendar, Notes, and Mail

Choose the mechanism before testing:

- **AppleScript/JXA:** native and flexible, but requires Automation permission per client/target app.
- **Computer Use:** broad GUI coverage; requires `cua-driver`, Accessibility, and Screen Recording.
- **Dedicated CLI:** often more structured, but installation and its own permissions/credentials must be verified separately. Complete the pre-recommendation source/provenance review in `third-party-package-review.md` before presenting an install command.
- **IMAP/SMTP for Mail:** accesses the mailbox rather than Mail.app and introduces separate credentials; do not conflate it with Apple Mail automation.

The July 2026 review rejected the then-current `ical` and `memo` releases for Hermes use: `ical` was blocked by signing/TCC/release concerns, while `memo` had AppleScript-injection and lossy-write risks. Use Computer Use as the current fallback and consult `apple-calendar-notes-cli-review.md` before reconsidering those projects.

For an AppleScript audit, query only counts and discard values. Run one application at a time with a timeout. If the command hangs, stop: macOS may be displaying an Automation prompt. Never launch simultaneous prompts and never click them for the user.

Examples of metadata-only probes:

```bash
osascript -e 'tell application "Calendar" to count calendars' >/dev/null
osascript -e 'tell application "Notes" to count notes' >/dev/null
osascript -e 'tell application "Mail" to count accounts' >/dev/null
```

A successful count proves read access for that AppleScript execution context; it does not prove GUI control, write access, or access from a differently identified launchd process.

If a Mail count hangs and no permission prompt appears, Mail may not yet be running. Launch it without stealing focus, wait for initialization, and retry with an AppleScript timeout:

```bash
open -g -a Mail
osascript \
  -e 'with timeout of 20 seconds' \
  -e 'tell application "Mail" to count accounts' \
  -e 'end timeout' >/dev/null
```

For Bryan, successful Apple Mail automation is still **read-only**: reading, searching, and summarization are allowed, but never compose, send, reply, forward, or transmit mail. macOS does not provide a read-only Automation grant, so this is a behavioral/tool-use boundary rather than a TCC-enforced permission.

## Local Network Privacy for launchd services

macOS keys Local Network permission to each executable path. A Nix rebuild that changes a service's store path (prometheus, blackbox_exporter, any LAN-dialing daemon) starts the new binary with no grant, even when it runs as a system-domain LaunchDaemon with `UserName`. Loopback, Tailscale (`utun`) and the default gateway keep working, so the failure looks like the remote host going down.

Signature: LAN dials fail instantly (<1 ms) with `connect: no route to host` (EHOSTUNREACH), starting exactly when the new process launched.

Differential (no remote-host access needed):

```bash
# 1. Find live LAN hosts (leave any out-of-scope host out of the probe set)
ping -c 2 -t 3 <subnet>.255 | grep -oE 'from [0-9.]+' | sort -u
# 2. Shell (has the grant): a live host without HTTP answers "Couldn't connect" (refused)
curl -sS -m 3 http://<live-lan-host>/
# 3. The service binary: blackbox's debug probe shows the error it actually got
curl -s "http://127.0.0.1:9115/probe?module=http_2xx&target=http://<live-lan-host>/&debug=true" | grep -i error
```

Refused from the shell but `no route to host` from the service means Local Network Privacy, not the network. The router succeeding from the service is expected and does not rule it out.

Corroborate without root:

```bash
plutil -p /Library/Preferences/com.apple.networkextension.plist \
  | grep -oE '/nix/store/[a-z0-9]+-(prometheus|blackbox_exporter)-[0-9.]+' | sort -u
log show --last 30m --style compact \
  --predicate 'subsystem == "com.apple.networkextension" AND eventMessage CONTAINS "LocalNetwork"' | tail
```

The plist holds one entry per previously granted store path. The running path missing from it confirms the diagnosis, and its modification time shows whether any grant happened since the rebuild.

Remedy: Bryan allows the binaries in System Settings > Privacy & Security > Local Network, or approves the prompt. Never click it for him. Running the service as a system-domain daemon does not fix this. A durable fix must give the dialing process a stable identity across rebuilds, and has to be verified across an actual version bump before anyone calls it fixed.

## Reboot and service verification

Before a reboot test:

1. Confirm user LaunchAgents have `RunAtLoad` and valid program paths.
2. Confirm target-local permissions and optional drivers before interpreting post-reboot failures.
3. Remember that FileVault unlock and user login happen before user LaunchAgents start.
4. After login, verify the supervised service, start a fresh agent session, and repeat metadata-only capability checks.
5. Keep external communications and destructive operations approval-gated even when the integration is technically authorized.
