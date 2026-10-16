# APPLE NOTES PKM — MAINTAINER NOTES

Paths are relative to the dotfiles repo root. This file is for editing the skill, not for using it; usage lives in `SKILL.md`.

## Personal second brain (Apple Notes) helper

`dot-agents/skills/apple-notes-pkm/scripts/`

- `apple-notes-pkm.py` + static `notes.jxa`, hard-scoped to the iCloud folder `Second Brain`; bounded search, exact-id read, revision-guarded append/replace, no delete.
- `notes_markdown.py` is the Markdown↔Notes-HTML converter (stdlib only).
- Tests: `python3 tests/test-apple-notes-pkm.py` (offline).
- `scripts/migrate-second-brain-to-apple-notes.py` is the one-time stage/import/verify migration (2026-09-16); `~/second-brain` is a frozen archive.
- Skills: `apple-notes-pkm` (personal), `knowledge-capture` (router; replaced `vault-capture`), `vault-pkm` (project vaults only).

## Apple Notes native Automation helper

`dot-agents/skills/apple-notes-pkm/helper/` + `scripts/reconcile-apple-notes-helper.sh`

- `apple-notes-pkm.py` sends **no** Apple Events itself: it shells out to the signed native helper **Apple Notes PKM Helper** (`main.m`, Foundation+OSAKit), the only process that talks to Notes, so the macOS Automation TCC grant lands on a stable code identity instead of a Python runtime.
- The helper embeds `notes.jxa` in a `__TEXT,__notes_jxa` Mach-O section (no generic AppleScript surface), reads one JSON request on stdin, and disclaims responsibility (`responsibility_spawnattrs_setdisclaim`) so macOS attributes the grant to it, not to Herdr/Python.
- `identity.json` is the expected bundle id + signing CN; the Python CLI verifies the installed signature before use and fails closed (**exit 7** = missing/unsigned/mismatch).
- It is signed with the hardened runtime plus the one entitlement in `entitlements.plist` (`com.apple.security.automation.apple-events`); hardened apps cannot send Apple Events without it, so never drop either.
- JXA stringifies a TCC denial as just `Error: An error occurred.`, so denial detection keys on `errorNumber` (-1743) as well as the message.
- **Hard signing gate:** `--apply` installs only with a *stable* code-signing identity (CN in `~/.secrets/apple-notes-pkm/signing-identity`, mode 0600, never in Git); it refuses ad-hoc signing because a changing cdhash recreates the dead-TCC-row problem.
- Build binary and signing material are never committed.
- Setup + the one-time Notes-Automation approval are in `helper/README.md`.
- Tests: `bash tests/test-apple-notes-helper.sh` (macOS build/identity, no Notes contact).
