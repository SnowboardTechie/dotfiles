# Apple Calendar and Notes CLI review

> Review snapshot: 2026-07-15. Revalidate current releases, source, dependencies, issues, signing, and macOS behavior before reconsidering either project.

## Current recommendation

Do not install the reviewed releases of `BRO3886/ical` or `antoniorodr/memo` for Hermes. Use native UI control through Computer Use for Calendar and Notes until a reviewed structured tool meets the gates below.

## `ical` v0.12.1

The direct EventKit implementation was generally reasonable, tests and `go vet` passed, release hashes matched, and no calendar-data telemetry was found. The blockers were packaging and operational safety:

- The distributed ARM binary was ad-hoc signed, lacked a Team ID and hardened runtime, was not notarized, and failed Gatekeeper assessment.
- An open macOS 26 issue documented unreliable Calendar TCC prompting, especially relevant to a LaunchAgent/responsible-process context.
- The binary used an outdated Go runtime with a reachable standard-library advisory in its GitHub update-check path. Practical exposure was limited, but the release still lagged a security fix.
- The repository was highly maintainer-concentrated and lacked test CI/security-policy/dependency-update signals at the reviewed revision.
- Commands can send invitations/RSVPs, delete events with force, and open meeting URLs. Those external/destructive paths require explicit policy gating before agent exposure.
- Interactive use performs a GitHub update check unless disabled with `ICAL_NO_UPDATE_CHECK=1`.

Reconsider after a signed/notarized release built with a current Go runtime works under the actual Hermes TCC context. Any agent wrapper should disable update checks where appropriate and separately deny invitation, RSVP, force-delete, and join behavior unless explicitly authorized.

## `memo` v0.6.0

Do not use this release for agent-mediated Notes access:

- Folder names, note HTML/body, IDs, and export paths were interpolated directly into AppleScript source. Crafted input can alter the program interpreted by `osascript`, including reaching shell execution.
- Editing replaced full note bodies and removed attachments before attempting restoration; moving created a new note and deleted the original. These paths were not transactional and could lose links, styles, attachments, metadata, or identity.
- Open issues reported dropped links, lost semantic styling, and incorrect note selection.
- Privileged add/edit/export paths had weak coverage, and several tests unexpectedly reached the live Notes application.
- Dependency and Homebrew-formula inconsistencies indicated stale packaging quality.
- No application telemetry or note-data network transmission was found, and release hashes matched, but those positives do not mitigate injection and data-loss risks.

Reconsider only after dynamic AppleScript interpolation is removed, values use `argv` or another data channel, writes preserve content transactionally with rollback, live Notes is isolated from normal tests, and current packaging passes dependency review.

## Safer structured-helper design

If native UI control is insufficient, prefer a small locally auditable helper that:

1. Starts read-only: list/search/read only.
2. Uses fixed AppleScript/JXA source with values passed through `on run argv`, never source interpolation.
3. Avoids shell execution, local caches, and writing note bodies to temporary files.
4. Keeps writes in separately invoked commands with explicit user authorization.
5. Preserves attachments, links, styling, metadata, and identity; destructive changes need rollback.
6. Passes metadata-only read verification and an explicitly approved mutation probe in the actual Hermes/TCC runtime context.
