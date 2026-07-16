# Native execution, containers, and filesystem blast radius

Use this reference when an always-on, remotely triggered agent will run on a personal workstation, homelab server, NAS-adjacent media host, or AI server. The central question is not only **who can reach the agent**, but **what the resulting OS process can reach after authorization succeeds**.

## Calibrated risk model

Separate four dimensions:

1. **Activation:** Agents normally act because of a message, cron job, persistent goal, webhook, or local request. Randomly roaming through unrelated disks is not expected normal behavior.
2. **Decision risk:** A broad request such as “clean up media,” “make room,” or “fix imports” may reasonably cause a model to infer that moving or deleting files is part of the task. Prompt injection, malicious tool output, compromised credentials, bugs, and bad scheduled prompts can also induce unintended actions.
3. **Capability:** If the process identity can write a path, the agent can technically modify or delete it. Instructions such as “never touch the NAS” are behavioral policy, not an OS boundary.
4. **Impact:** A low-probability action can still be unacceptable when the account can write personal files, mounted shares, backups, credentials, repositories, or production services.

Report risk as likelihood **and** blast radius. For a LAN-only or outbound-messaging deployment with strict identity controls, spontaneous unrelated damage is usually low likelihood; same-user native execution against writable personal/NAS data can still make the impact high and the overall risk moderate.

## Native account semantics

- An administrator-group account is not automatically root. Ordinary agent commands run with that user’s normal permissions, and elevation usually still needs sudo authorization.
- Root is not required to damage user-owned data or a NAS share already mounted read-write for that user.
- A logged-in personal administrator account can coexist with a separate unprivileged service account. Existing services do not force the agent to share their process identity.
- On the same OS account, per-process filesystem restrictions are difficult. A separate account, container, VM, sandbox backend, separate NAS credential, or read-only mount creates the meaningful boundary.

## Requirement-first boundary selection

Start from the operator's non-negotiable capabilities and protected assets, not from the strongest available sandbox. Common examples include wanting unrestricted native host troubleshooting and Apple integrations while declaring one mounted NAS or backup tree out of scope.

When the agent and another service must share one OS account and that account already has a writable mount, there may be no hard per-process filesystem boundary without a sandbox, container, separate identity, or service redesign. Communicate that limitation once, then let the operator choose the residual risk. Do **not** translate “no hard boundary” into “the requested native setup is impossible,” and do not keep proposing homelab rearchitecture after it has been rejected.

A policy-based native posture can be proportionate when remote reachability is narrow, identity controls are strong, the host is recoverable, the protected mount is unrelated to expected tasks, and the operator explicitly accepts residual risk. Use layered likelihood controls:

1. Persist an exact never-touch rule naming the protected mount, host, and authorization condition.
2. State that broad requests such as “inspect the machine,” “find large files,” “clean storage,” or “troubleshoot services” do not imply access to the protected asset.
3. Require current-turn authorization for an exact path and operation; stop and ask on ambiguity.
4. Add unconditional command deny globs for known mount paths, hostnames/IPs, and mount/client utilities where compatible with the workflow.
5. Keep unattended sudo and YOLO disabled, use manual destructive-command approvals, and enable unattended loop hard stops.
6. Audit remote GUI/computer-use tools separately because Finder, AppleScript, or another host process may act as a confused deputy outside shell-path checks.
7. Ensure cron jobs and default working directories never point into the protected mount.

These measures reduce accidental and honest-but-wrong actions; they do not contain a deliberately adversarial process. Describe them as strong behavioral and command guardrails, not filesystem isolation.

If considering an OS process sandbox, test the proposed policy with both an allowed path and a denied path on the target OS version before trusting it. Do not infer enforcement from successful process startup or from profile syntax alone.

## Guardrails are not containment

Audit current implementation and defaults rather than assuming every destructive action prompts:

- Dangerous-command approvals are generally pattern-based. They may catch recursive deletion and catastrophic commands without covering every single-file delete, overwrite, application-specific delete API, GUI action, or alternate implementation.
- File-write safe roots and protected-path checks may govern dedicated file tools while terminal commands execute with the OS user’s permissions. Verify exact coverage.
- User-defined command deny rules help an honest-but-wrong model but are not a sandbox against an adversarial process.
- GUI/computer-use tools, MCP servers, browser automation, application APIs, plugins, and cron jobs may bypass assumptions based only on shell-command approval.
- YOLO/approval-off modes and permanent allowlists materially change the posture.
- Checkpoints and rollback mechanisms should not be assumed to protect non-project files, terminal-side mutations, NAS data, databases, or external services.

## Secret-safe live audit

Before recommending native execution, collect and report only non-secret posture:

- effective approval mode, cron approval mode, timeout, permanent allowlist count, and deny-rule count
- whether YOLO and unattended sudo are enabled; never print passwords
- terminal backend and working-directory policy
- whether a write-safe root exists and what classes of tools it actually constrains
- hard tool-loop stop settings and maximum turns
- enabled toolsets for the **remote messaging platform**, especially terminal, file, code execution, browser, cron, and computer use
- service account identity and whether it is admin/root
- writable home, repository, media, backup, and NAS paths
- current mount mode and the NAS identity/ACL being used
- snapshots, immutable backups, retention, and restore verification
- inbound listeners versus outbound messaging paths

Inspect the platform-specific toolset, not only the CLI toolset. A locked-down local profile can coexist with a much more powerful remote Matrix profile, or vice versa.

## Deployment choices

| Option | Isolation | Host integration | Main caveat |
|---|---:|---:|---|
| Native under personal admin | Low | Full | All ordinary user and mounted-share permissions become agent capabilities |
| Native under separate standard user | Good | High | Requires service setup and explicit ACLs/mount access |
| Full agent container | Strong practical boundary | Medium | Host GUI, Keychain, native CLIs, devices, and macOS-specific automation are limited |
| Native agent + isolated terminal backend | Partial | Medium–high | Core/plugins/non-terminal tools may still run on the host; verify which tool families are isolated |
| VM | Strongest common boundary | Lowest | Highest operational and integration cost |

## Container decision guidance

A full container is usually not too limiting for outbound messaging, cron, cloud models, browser automation, Git/SSH with dedicated credentials, and file workflows over selected bind mounts. It becomes limiting when the agent must operate macOS GUI applications, the personal Keychain, Homebrew-only host tools, audio/video devices, host service managers, or direct Apple Metal acceleration.

Host-native AI services can remain outside the container and be consumed through a deliberately exposed local API. On Docker Desktop, `host.docker.internal` is commonly used; verify the current platform behavior and secure the host listener. If both services are containers, prefer a private Docker network.

The security value of a container depends on its mounts and privileges:

- Never mount the Docker socket merely for convenience; it is effectively host control.
- Avoid `--privileged`, host PID/network namespaces, and blanket `/`, `/Users`, home, or NAS-root mounts.
- Mount source libraries read-only and use a dedicated writable output/staging directory.
- Use separate credentials or deploy keys rather than the personal SSH/Keychain stores.
- Apply resource/PID limits and `no-new-privileges` where compatible with the image’s documented init model.
- Do not publish ports when outbound messaging and cron are sufficient.
- Treat the persistent agent data volume as secret-bearing; it contains credentials and remote-control state.

On macOS, confirm current Docker Desktop GPU/device support before promising direct acceleration. A host model server accessed through an API is often the practical design.

## Minimum native baseline

If the operator accepts native same-user execution, recommend at least:

1. No public dashboard/API and no router port forwarding.
2. Strict messaging identity and room authorization, required E2EE where available, and requester-bound approvals.
3. No unattended sudo or passwordless elevation.
4. Manual approvals for remotely initiated destructive commands; cron dangerous-command behavior set to deny.
5. YOLO disabled, no broad permanent allowlists, and explicit deny rules for common catastrophic local operations.
6. Hard tool-loop stops enabled for unattended gateways.
7. Disable unnecessary remote-platform tools, especially computer use, terminal, code execution, or cron creation.
8. Use a restricted remote-facing profile and a separate local/admin profile when practical.
9. Read-only mounts or a separate read-only NAS identity for source libraries; dedicated write locations for outputs.
10. Tested NAS snapshots/versioning and an independent backup path the agent cannot alter.

A write-safe root is useful defense in depth but does not replace OS permissions or backend isolation when shell, GUI, or external API tools remain available.

## Communication guidance

Lead with the answer to the operator's actual question. If they ask whether a native agent can be instructed to avoid a mounted asset, say **yes**, then distinguish behavioral policy from hard containment. Do not begin with a redesign of their mounts, service accounts, containers, or homelab unless they requested architectural change.

Do not provide either false reassurance (“it will never touch unrelated files”) or vague fear (“admin means instant root compromise”). State plainly:

> The agent is not expected to roam or delete data spontaneously, but any writable path available to its process identity is within the technical blast radius of an authorized, mistaken, injected, or compromised turn.

Then connect each mitigation to either reduced **likelihood** (authentication, approvals, safer prompts) or reduced **impact** (service account, container, read-only mounts, snapshots).