# Privileged local integration tool review

Use this when considering a CLI, MCP server, plugin, or helper that will receive Calendar, Notes, Mail, Reminders, Accessibility, Screen Recording, Keychain, browser, or comparable personal-data permissions.

## Review the exact artifact, not just the project

1. Record the exact release tag, commit, package-manager formula, and installed artifact. Diff the release tag against current main; do not review main while installing an older release.
2. Collect adoption and governance signals: repository age, stars/forks, open issues and PRs, maintainer concentration, maintenance recency, license, security policy, and published advisories. These are trust signals, not proof of safety.
3. Verify provenance: commit/tag verification, release mutability, asset digests, formula hashes, build workflow, CI gates, action pinning, code signing, notarization, and whether one account controls source, releases, and the package tap.
4. On macOS, inspect the actual binary with `codesign` and `spctl`. Record TeamIdentifier, hardened runtime, entitlements, notarization/Gatekeeper result, and build-toolchain version. Package installation does not prove TCC prompts will work from a launchd agent; test from the real responsible-process context.

## Source review priorities

- Treat calendar invitations, email, note bodies/titles, shared documents, filenames, and synced content as untrusted input.
- Search for network/telemetry calls, automatic update checks, shell execution, subprocesses, `osascript`, dynamic code loading, caches, temporary plaintext, path construction, deletes, and external communications.
- For AppleScript, an argument-array subprocess is not sufficient protection when values are interpolated into the AppleScript source. Prefer static scripts with `on run argv`.
- Enumerate side effects by command: read, local mutation, destructive mutation, and external communication. Calendar invites/RSVPs and Mail sends are communications, not ordinary local writes.
- Check whether read commands cache private titles, IDs, bodies, or event metadata with overly broad permissions.
- Review agent-specific convenience features such as skill installers, MCP registration, self-updaters, URL openers, and `curl | bash` suggestions as separate supply-chain/control surfaces.

## Verification

- Run the project tests and note coverage specifically for privileged paths.
- Diagnose hangs: tests that accidentally invoke live macOS apps or TCC are evidence of weak isolation, not a reason to keep retrying.
- Run language-appropriate static and dependency scans (`go vet`, `govulncheck`, Bandit, `pip-audit`, etc.). Distinguish reachable findings from vulnerable-but-unused dependencies.
- For distributed Go binaries, inspect `go version -m`; source scans using a newer local toolchain do not prove the released binary has patched standard-library code.
- Verify downloaded release hashes against both the package formula and hosting platform digest without executing the artifact.

## Decision posture

Do not recommend installation based only on a polished README, activity, or star count. Lead with whether the exact artifact is acceptable for the intended agent context. Prefer a narrow read-only helper or native GUI automation over a broad unaudited tool. For accepted tools, disable unnecessary update checks/telemetry and wrap dangerous commands so external communication and destructive mutations still require approval.
