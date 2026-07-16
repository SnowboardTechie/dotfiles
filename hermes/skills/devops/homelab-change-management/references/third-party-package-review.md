# Third-party package review before recommendation

Use this checklist before telling Bryan to install a third-party CLI, app, service, plugin, MCP server, tap, or agent integration. A candidate may be mentioned as **unreviewed**, but installation should not be recommended until the review is proportionate to its permissions and data access.

## 1. Set the risk tier

Increase review depth when software can access credentials, messages, calendars, notes, mail, browser sessions, files, networks, smart-home devices, or agent tools; runs persistently; requests macOS TCC/Automation; mutates user data; or executes downloaded code.

## 2. Establish identity and adoption

- Repository owner, maintainer identity, contributor concentration, creation date, release cadence, and latest meaningful maintenance.
- Stars, forks, downstream packaging, and real-world users are context—not security evidence.
- Read open and closed issues for security, privacy, data loss, broken permissions, stale dependencies, and update failures.
- Check `SECURITY.md`, advisories, branch protections when visible, and dependency-update automation.

## 3. Inspect sensitive source paths

Trace actual code—not README claims or broad grep counts—for:

- subprocess/shell/AppleScript execution and input escaping;
- filesystem reads, writes, deletion, export, caching, and temporary files;
- HTTP clients, telemetry, analytics, update checks, and uploaded data;
- credential/keychain/env access and log redaction;
- destructive commands, confirmation bypasses, invitations/messages, and external side effects;
- plugin loading, dynamic import/eval, install hooks, and self-update behavior;
- permission requests and what executable identity receives them.

Classify each match manually. A search count is not a finding.

## 4. Review dependencies and releases

- Inspect direct and transitive lockfiles/manifests and run the ecosystem vulnerability scanner when practical.
- Determine whether flagged code is reachable; report vulnerable-but-unreached separately from exploitable paths.
- Compare release tags/commits with packaged source.
- Verify asset and formula hashes, release immutability, commit/tag verification, and attestations.
- Inspect build/release workflows for mutable action tags, broad tokens, unpinned downloads, and single-account control of source, release, and tap.
- On macOS inspect code signing, Team ID, hardened runtime, notarization/Gatekeeper, entitlements, and TCC behavior in the intended runtime context.
- Prefer pinned source builds over unsigned opaque binaries, but do not assume a source build solves TCC identity or operational problems.

## 5. Exercise safely

- Do not install into the live environment merely to audit it. Clone/download into a temporary workspace first.
- Never execute an untrusted release binary just to inspect it; use hashes, `codesign`, `spctl`, `otool`, archive listing, and language metadata tools.
- Run tests/static checks with personal data and credentials absent.
- Distinguish package declaration, installation, authorization, successful read, and authorized mutation.
- Use metadata-only probes; never reveal private content in verification output.

## 6. Compare alternatives

Consider the native UI, an existing trusted tool, a read-only wrapper, a small locally auditable helper, or doing nothing. Prefer the least privilege and smallest data/command surface that meets the need.

## 7. Report a decision

State clearly:

- **Reviewed and recommended**, **conditionally acceptable**, or **not recommended**;
- exact revision/release and date inspected;
- adoption/maintenance context;
- decisive findings and mitigating facts;
- requested permissions, network behavior, destructive capabilities, and residual risk;
- installation method only after the recommendation is justified.

Separate “potential candidate” from “reviewed and recommended.” If the audit is incomplete, say so and do not present an install command as the next step.
