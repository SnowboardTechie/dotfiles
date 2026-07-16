---
name: homelab-change-management
description: "Plan and execute homelab host changes, service migrations, package installs, storage-sensitive automation, and stateful agent cutovers using declarative architecture as the source of truth."
version: 1.9.0
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [homelab, nix, nix-darwin, migration, storage, change-management, launchd]
    related_skills: [plan, self-hosted-agent-security]
---

# Homelab Change Management

Use this skill for changes or questions involving Bryan's homelab architecture, Nix Darwin/NixOS hosts, background services, host package ownership, mounted storage, or migration of stateful automation between machines.

## Core rule: inspect the declared architecture first

Bryan's `~/code/nix-configs` repository is the source of truth for homelab architecture and system/software ownership. Dotfiles owns application and user configuration.

Before asking Bryan to restate architecture or recommending commands:

1. Read the repository guidance (`AGENTS.md`, nested guidance, and host documentation).
2. Read the target host leaf, such as `modules/hosts/studio.nix`.
3. Trace every relevant imported feature/service module rather than treating the host leaf as the complete implementation.
4. Search the repo for addresses, mounts, services, package declarations, launchd/systemd units, and overrides.
5. Evaluate the merged Nix configuration when defaults and host overrides could differ:

   ```bash
   nix eval --json '.#darwinConfigurations.<host>.config.<option>'
   ```

6. Compare the declared state with narrow, read-only checks on the actual target host.
7. Ask Bryan only for facts that are intentionally outside Git, secret, or genuinely unavailable from the target.

Do not infer homelab architecture from the currently connected machine. Always identify the source host, target host, and the machine your tools are actually operating.

## Declarative-first package workflow

Before recommending that Bryan install a third-party package, complete a proportionate security, maintenance, provenance, adoption, issue, permission, telemetry, dependency, and supply-chain review. Do this **before** presenting installation as the recommended next step—not after novelty or risk is challenged. You may identify an option as an **unreviewed candidate**, but keep that label explicit and withhold an install recommendation until the review is complete.

For privileged tools—agent integrations, macOS Automation/TCC clients, messaging/calendar/notes/mail utilities, daemons, plugins, and MCP servers—inspect sensitive source paths and release artifacts rather than relying on README claims. Treat stars as adoption context, not proof of safety, and manually classify broad search matches. Follow `references/third-party-package-review.md`.

Then place the reviewed package declaratively:

1. Search `nix-configs` for the package, tap, service, or equivalent capability.
2. Inspect package ownership and cleanup behavior. In particular, `homebrew.onActivation.cleanup = "zap"` can remove undeclared manual installs.
3. Place one-host packages in the host leaf; place shared capabilities in a feature module, following the repo's dendritic conventions.
4. Declare Homebrew taps and fully qualified third-party formula names together when appropriate.
5. Run the repo formatter only when it will not create unrelated churn; revert drive-by formatting.
6. Validate with `nix flake check`, evaluate the exact merged option, and run `git diff --check`.

If software has no Nixpkgs/Homebrew package and officially uses a managed user installation, do not force it into an activation script merely to appear declarative. Keep the supported install path, then decide separately whether Nix should manage its launchd/systemd supervision.

## Local model inventory and pruning

Treat local inference models as shared state with multiple consumers, not as isolated files:

1. Inventory installed tags, loaded models, total disk use, and Ollama API digests.
2. Cross-check Open WebUI visibility and historical use, Hermes provider/delegation/fallback references, and download recency.
3. Group aliases by digest before estimating savings; removing one tag may reclaim nothing when another tag references the same blobs.
4. Prefer one retained model per concrete role unless measured latency, memory, or quality differences justify adjacent sizes and quantizations.
5. Update every consumer configuration before deleting model data, then stop loaded retired models and remove only the approved tags.
6. Verify the exact retained model set, consumer config validity, runtime load state, and before/after storage.

Do not equate Open WebUI's disabled flag with safe deletion. A disabled model may still be called directly or referenced by another agent. Likewise, stale WebUI metadata for an absent tag is not meaningful model storage. For Hermes configuration, immediately inspect the resulting YAML shape after any structured edit; a successful CLI message does not prove that a list/map was written as structured YAML.

See `references/local-model-pruning.md` for digest-aware storage accounting, read-only Open WebUI usage checks, Hermes composite-config editing pitfalls, and a concrete Studio example.

## Local AI endpoint diagnosis

When Bryan names a homelab AI domain or UI, identify that endpoint's actual service chain before reasoning about models or limits. Do not substitute the model/provider backing the current Hermes conversation merely because Hermes is the surface where the question was asked.

1. Inspect the named endpoint first and identify its frontend, reverse proxy/tunnel, inference backend, and target host.
2. Trace the corresponding host and imported service modules in `nix-configs`, then verify the live service environment and APIs.
3. Keep Hermes provider context, Open WebUI retention settings, Ollama runtime allocation, model-native limits, and tunnel behavior as separate layers.
4. For context-limit reports, measure the native model maximum, allocated runtime context, current request tokens, actual truncation, compaction policy, and prompt-processing latency before concluding which limit was hit.
5. Prefer privacy-preserving metadata and narrow configuration queries; model capacity diagnosis does not require reading chat contents.

See `references/local-llm-context-diagnostics.md` for Ollama/Open WebUI probes, interpretation rules, remediation order, and the Studio example.

## Remote client packaging and fleet rollout

Treat package ownership, mutable connection settings, and credentials as separate concerns:

1. Let Nix own the client binary, launcher, host role, and service supervision.
2. Let the application own already-configured per-user connection state unless it provides a supported declarative configuration interface.
3. Keep tokens/passwords out of derivations, wrapper arguments, and the Nix store.
4. Before injecting any environment override, trace the application's full precedence chain and credential contract. Never inject one half of a paired setting such as endpoint-without-token; an override may shadow working saved authentication rather than complement it.
5. Inspect the evaluated package or generated wrapper/derivation for the actual environment and arguments. Source-level evaluation and successful builds do not prove runtime authentication.
6. Roll out to one canary client first. Fully quit and relaunch GUI clients after activation because an existing process retains its old environment and executable.
7. Verify a real authenticated connection on the canary before updating the remaining hosts.

If clients are already connected through saved settings, prefer installing the upstream client unchanged over creating a wrapper that replaces those settings. See `references/hermes-macos-migration.md` for the Hermes Desktop URL/token regression and focused verification pattern.

## Native macOS integration readiness

Treat native-app capability as a four-layer contract; never collapse these into a single “enabled” claim:

1. **Declared** — the package/toolset exists in Nix, Homebrew, dotfiles, or agent config.
2. **Installed** — the exact executable or app bundle is discoverable on the live target.
3. **Authorized** — macOS TCC grants the relevant Reminders, Calendars, Automation, Accessibility, or Screen Recording permission to the current executable identity.
4. **Exercised** — a privacy-preserving read probe and, when needed, an explicitly approved write probe succeed in the same runtime context the agent will use.

During host migration or rebuild:

- Recheck target-local TCC state even when configuration and agent state migrated successfully; TCC grants are host- and executable-specific and are not represented by a Nix declaration or agent backup.
- For optional runtime dependencies, verify both the agent toggle and the binary. An enabled toolset does not prove its external driver is installed. For Hermes Computer Use, run `hermes computer-use status` and `hermes computer-use doctor`; use the supported installer when absent unless a genuinely pinned package exists.
- Do not add an impure activation script that fetches an unpinned “latest” binary merely to make a mutable upstream installer look declarative. Distinguish a supported user-managed runtime dependency from Nix-managed service supervision.
- Run permission-triggering probes sequentially and with timeouts. A hanging AppleScript/EventKit probe may be waiting on a GUI permission dialog; do not launch several prompts in parallel, and never approve the dialog on the user's behalf.
- Test without exposing personal data: report authorization state, application availability, counts, or success/failure—not event titles, mail subjects, note titles, reminder text, account names, or identifiers.
- Keep external side effects separately gated. Read access does not authorize creating events, editing notes, or completing reminders; obtain Bryan's approval for significant mutations.
- **Apple Mail is read-only for Bryan:** reading, searching, and summarization are allowed; never compose, send, reply, forward, or otherwise transmit mail. Treat this as a behavioral boundary because macOS Automation authorization itself is broader than read-only.
- After toolset/config changes, start a fresh agent session; after package replacement, rerun authorization/status against the current executable before calling the integration ready.

See `references/macos-native-integrations.md` for a capability matrix and metadata-only verification checklist.

## Peer Git workspace replication

When one computer becomes the primary Hermes/work host while another permanently retains its checkouts, treat the operation as **peer replication**, not a stateful writer cutover:

1. Keep the source machine intact and name it as a permanent fallback; cleanup means target-local staging only.
2. Transfer the complete project tree into a dated staging directory outside active target roots. Preserve `.git`, untracked files, symlinks, and linked worktrees while excluding only clearly regenerable bulk.
3. Inventory both sides before activation. Compare Git HEADs, branch/upstream state, local modifications, untracked files, worktree registrations, symlinks, vaults, and project guidance.
4. Reconcile each overlap independently: clean same-HEAD checkouts may be swapped with a reversible backup; target-ahead checkouts stay authoritative; source-ahead or diverged checkouts require explicit Git reconciliation.
5. Expect linked-worktree metadata to contain absolute final paths. Do not prune it while staged merely because those paths are temporarily absent. Verify commit objects and local refs before importing individual worktrees.
6. Do not automatically activate transferred root-level agent state such as `.claude`, `.omc`, or `.sisyphus`; machine-local permission and path settings may differ.
7. Verify every Git object store, registered worktree path, active vault link, and desktop Project before acceptance.
8. After migration, use Git push/fetch/pull and one-writer-per-branch discipline for normal handoffs; do not bidirectionally live-sync mutable `.git` directories.

See `references/peer-git-workspace-migration.md` for rsync staging, checksum-aware overlap comparison, worktree repair/import rules, vault handling, verification commands, and precise cleanup language.

## Stateful migration workflow

### 1. Establish invariants

Write down:

- Source and target hosts
- Canonical state directory
- Credentials and encryption/device state included in backups
- Which process is the canonical writer
- Public versus outbound-only network exposure
- Critical resources that must remain out of scope
- Rollback constraints after the new writer processes state

### 2. Prepare the target without activating it

- Install the compatible runtime and native integrations.
- Run health checks.
- Do not start a duplicate gateway, scheduler, sync daemon, or other canonical writer.
- Classify safety controls before cutover:
  - **Transferable controls** stored in the migration backup—configuration, memories, platform tool settings, approval rules—should normally be applied and verified on the source before the final backup. Let the backup carry them rather than asking the offline operator to re-edit imported state.
  - **Target-local controls** not included in the backup—OS permissions, firewall rules, service supervision, target-only secrets—must be applied on the target.
- If tightening approval mode can block the agent's own terminal tools, validate the planned configuration against an isolated temporary home first, apply it as the final agent-operated step, and leave live verification to an independent operator terminal.

### 3. Quiesce and transfer

- Stop the source writer.
- Take the complete migration backup, not a selective or quick export when credentials/crypto are required.
- Verify that the backup was created after transferable hardening was applied.
- Treat archives as credential-bearing secrets.
- Transfer over encrypted transport and never live-sync mutable state directories.

### 4. Import and test

- Import on the target while its writer is stopped.
- Verify that transferred safety policy survived import; do not redundantly reapply it unless verification shows it is missing.
- Apply only target-local policy that the backup cannot carry.
- Validate config and dependencies.
- Run the service in the foreground first.
- Test authentication, encryption, sender authorization, required native capabilities, and one-response-only behavior.

### 5. Activate and clean up

- Install/start service supervision only after foreground validation.
- Confirm no unintended network listener exists.
- Leave the source writer disabled.
- Remove transient migration archives after acceptance.

### Rollback rule

Before the target processes new state, rollback may restart the source. After the target processes new encrypted or mutable state, first export the latest target state back to the source; never restart a stale clone and allow two stores to diverge.

## Critical-storage policy

Treat recoverable host configuration and hard-to-recover storage as different risk classes.

For Bryan's environment:

- Agents may access the Studio broadly.
- The Unraid NAS is out of scope unless Bryan explicitly authorizes an exact operation.
- Do not list, search, index, checksum, stat, write, move, delete, mount, or unmount NAS content merely to confirm a mount.
- Use declarative configuration and mount-table output for discovery whenever possible.
- A mounted share may live under a home-directory path rather than `/Volumes`; never conclude it is absent from Finder's `/Volumes` view alone.
- Behavioral policy and command-deny rules are useful guardrails, but do not misrepresent same-user access as an OS-enforced sandbox.
- If Bryan accepts the trusted-agent model, do not repeatedly push a homelab rearchitecture after the trade-off is understood.

## Planning quality gates

A migration plan must:

- Name exact files, hosts, state paths, and go/no-go gates.
- Distinguish prerequisites from cutover actions.
- Delay source shutdown until the target is ready.
- Include rollback before and after state divergence.
- Keep package declarations consistent with the host's declarative manager.
- Use live checks only on the correct target host.
- Clearly label ad-hoc verification as targeted evidence rather than full suite coverage.

### Progress and canary discipline

Do not turn verification into an open-ended loop:

1. Once the root cause is supported by source/evaluated evidence, make the smallest correction and run the canonical checks plus one focused regression probe.
2. If only the remote host can prove runtime behavior, stop local derivation archaeology and ask for—or perform—the canary deployment promptly.
3. Surface blockers and approval waits immediately; do not silently retry equivalent commands or keep narrating future checks without acting.
4. After the canary succeeds, record that runtime evidence and move on. Do not keep re-proving already-established layers unless a later result contradicts them.

### Offline handoff runbooks

When Bryan will lose access to the agent during a cutover, do not stop at a conceptual plan. Produce a self-contained offline runbook before shutdown:

1. Separate commands by machine and label every terminal block **source**, **target**, or **independent operator terminal**.
2. Use copy-pasteable commands with explicit variables, archive paths, checksums, expected output, and stop conditions. Keep placeholders to values that cannot be discovered in advance, and explain exactly how to obtain them.
3. Include encrypted transfer plus an offline fallback, credential-archive handling, and cleanup only after acceptance.
4. State when a command cannot be run from inside the service being stopped; require an independent terminal where needed.
5. Include foreground validation before service installation, one-response-only checks for cloned gateways, and rollback paths for both pre-divergence and post-divergence state.
6. Disable the stale source service after acceptance so a later login/reboot cannot silently start a second writer.
7. Syntax-check every fenced shell block without executing it. Use `scripts/verify-shell-runbook.py <runbook.md>` for the mechanical pass, then test configuration-editing snippets against an isolated temporary home/state directory.

The runbook must remain usable after Hermes/chat/browser access disappears; never rely on “ask me if this fails” as the only recovery path.

## Common mistakes

- Asking Bryan for architecture already present in `nix-configs`.
- Looking only at a host leaf and missing imported module defaults.
- Recommending `brew install` before checking Nix-managed Homebrew cleanup.
- Recommending a new package from README/repository metadata before reviewing sensitive source paths, issues, dependencies, permissions, telemetry, and release provenance.
- Inspecting the laptop and reporting it as Studio state.
- Listing mounted storage contents when mount metadata would answer the question.
- Treating parity as backup or snapshot protection.
- Treating peer Git workspace replication as a one-time source cutover, or implying that target staging cleanup deletes permanent source checkouts.
- Overlaying an incoming `~/code` tree directly onto active target projects before comparing overlaps.
- Running `git worktree prune` against staged repositories whose absolute final-path pointers are temporarily unresolved.
- Automatically activating transferred root-level agent state or rewriting broken historical worktree symlinks merely to make an audit green.
- Starting both old and new stateful gateways during migration.
- Conflating “not kernel-enforced” with “not a reasonable behavioral policy.”
- Expanding a migration into an unsolicited homelab redesign.
- Treating a successful Nix evaluation/build as proof that a remote GUI client can authenticate.
- Injecting a remote endpoint through a wrapper without its paired credential, thereby shadowing working per-user settings.
- Rolling a client configuration to every host before one runtime canary has connected successfully.
- Giving only a conceptual checklist when the operator must turn the agent off during the cutover.
- Matching command denials only against resolved absolute paths even though approval checks see raw shell syntax before `~` and `$HOME` expansion.

## References

- `references/peer-git-workspace-migration.md` — staged Mac-to-Mac project replication, Git overlap classification, absolute linked-worktree paths, vault verification, Hermes Project selection, integrity gates, and precise cleanup semantics.
- `references/hermes-macos-migration.md` — concrete laptop-to-Studio Hermes migration details, storage boundaries, command-denial aliases, and validated Nix locations from the July 2026 session. Revalidate the repository and live target before reuse.
- `references/macos-native-integrations.md` — four-layer readiness audit for macOS native apps, TCC permissions, optional drivers, privacy-preserving probes, and reboot verification.
- `references/apple-calendar-notes-cli-review.md` — July 2026 security and operability review of structured Calendar/Notes candidates, reconsideration gates, and safer helper design.
- `references/third-party-package-review.md` — pre-recommendation review checklist for source, issues, adoption, dependencies, release provenance, permissions, telemetry, destructive behavior, and safer alternatives.
- `references/local-model-pruning.md` — digest-aware Ollama pruning, Open WebUI usage evidence, Hermes consumer checks, structured-config pitfalls, and the July 2026 Studio example.
- `scripts/verify-shell-runbook.py` — non-executing `bash -n` syntax check for every fenced Bash block in an offline Markdown runbook.
