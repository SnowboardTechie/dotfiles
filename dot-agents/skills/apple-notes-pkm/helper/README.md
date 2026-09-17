# Apple Notes PKM Helper (native)

The one process allowed to send Apple Events to Notes on behalf of
`apple-notes-pkm`. `apple-notes-pkm.py` parses arguments, converts Markdown,
shapes results, and enforces policy; it delegates only the Notes/JXA request to
this helper over stdin. The helper exposes no generic AppleScript surface, has
no network/daemon/listener, and requests only Notes Automation.

## Why native

macOS attributes an Apple Events (Automation) TCC grant to a process's
*responsible* process. Under Herdr/Hermes the responsible process is the
terminal, Herdr, or the `python3` runtime — none of them a stable identity, so a
grant made against them dies on the next runtime upgrade (the stale `python3.11`
Automation rows that would not toggle). This helper calls
`responsibility_spawnattrs_setdisclaim` to become its own responsible process,
so the grant lands on one named, signed app and survives rebuilds.

## Contract

- Input: exactly one JSON object on **stdin** (no command-line arguments).
- Output: one JSON object on **stdout**; diagnostics on stderr.
- The only program it runs is `../scripts/notes.jxa`, embedded into the
  `__TEXT,__notes_jxa` Mach-O section at link time. A request can pick an `op`
  inside that program but can never select a script, application, path, or
  command.
- Exit: 0 ran (stdout JSON carries `ok`), 1 internal failure, 2 usage.

## Files

- `main.m` — the helper (Objective-C, ARC; Foundation + OSAKit).
- `Info.plist` — bundle metadata and `NSAppleEventsUsageDescription`.
- `identity.json` — the expected stable identity: bundle id, executable name,
  install path, and the code-signing certificate Common Name the build must sign
  with. `apple-notes-pkm.py` and the reconciler both verify against this.

No compiled binary and no signing material are committed.

## Build, sign, install

```bash
scripts/reconcile-apple-notes-helper.sh --check   # report identity + state
scripts/reconcile-apple-notes-helper.sh --apply   # build, sign, install, verify
```

`--apply` compiles `main.m` with `notes.jxa` embedded, assembles
`~/Applications/Apple Notes PKM Helper.app`, signs it, and verifies the result.
It is macOS-only and is also run by `setup-platform-configs.sh`.

## Required signing decision (one-time, human-owned)

The helper is installed only with a **stable** code-signing identity. Ad-hoc
signing is refused: its cdhash changes every rebuild and would recreate the dead
TCC row problem.

1. Create one self-signed **code-signing** certificate whose Common Name is
   exactly `Apple Notes PKM Helper` (Keychain Access → Certificate Assistant →
   Create a Certificate; Identity Type: *Self Signed Root*; Certificate Type:
   *Code Signing*), or provide a Developer ID Application identity and set
   `signing_common_name` in `identity.json` to its CN.
2. Record that CN in `~/.secrets/apple-notes-pkm/signing-identity` (mode 0600).
   The file holds only the certificate name, never key material, and is never
   committed.
3. Re-run `--apply`.

## One-time permission grant (human-owned)

The first helper call triggers a macOS prompt to let **Apple Notes PKM Helper**
control Notes. Approve it once in System Settings → Privacy & Security →
Automation. No agent grants, clicks, or widens this on your behalf.

## Verify an installed helper

```bash
codesign -dv --verbose=4 "$HOME/Applications/Apple Notes PKM Helper.app/Contents/MacOS/apple-notes-pkm-helper"
```

`Identifier=` must equal `bundle_id` and an `Authority=` line must contain
`signing_common_name` from `identity.json`.
