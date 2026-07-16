# Multi-host source-of-truth and protected-mount auditing

Use this reference when the user asks about an always-on homelab host while the agent session may be running on a laptop, jump host, container, SSH backend, or another desktop.

## 1. Prove the execution host first

The machine the user is looking at is not automatically the machine backing the current tool session. A desktop/project switch may change UI context or workspace without changing the execution host.

Before inspecting system state, collect non-secret identity evidence from the active backend:

```bash
hostname
uname -a
scutil --get ComputerName 2>/dev/null || true   # macOS
pwd
```

If the result names the wrong host, do not inspect that machine as a substitute. Attempt the documented remote connection only when one exists. If the target is unreachable, state that boundary and give the smallest read-only probe for the user to run there.

## 2. Read declared architecture before asking

When the operator maintains infrastructure as code, treat it as the first source for architecture and intent:

1. Read repository guidance (`AGENTS.md`, `CLAUDE.md`, etc.).
2. Read the target host composition/leaf.
3. Trace imported feature and service modules.
4. Search for addresses, mount options, service names, users, ports, and credentials-file paths.
5. Evaluate effective options instead of assuming defaults when the configuration system supports it.

For a flake-based nix-darwin host, effective-value probes can look like:

```bash
nix eval --raw '.#darwinConfigurations.<host>.config.system.primaryUser'
nix eval --raw '.#darwinConfigurations.<host>.config.services.<service>.mountPoint'
nix eval --raw '.#darwinConfigurations.<host>.config.services.<service>.credentialsFile'
```

Do not ask the user to restate facts already declared in their source-of-truth repository. Ask only for live state or intentionally untracked values that the repository cannot answer.

## 3. Discover mounts without traversing protected data

If a NAS or backup tree is declared out of scope, mount discovery itself should not enumerate its files. Avoid `ls`, recursive file search, glob expansion into the mount, indexing, checksums, or content reads.

Prefer metadata that does not traverse the share:

```bash
/sbin/mount -t smbfs 2>/dev/null || true
/sbin/mount -t nfs 2>/dev/null || true
readlink "$HOME/<declared-link>" 2>/dev/null || true
```

A service may mount directly under a home or service path, so Finder and `/Volumes` are not authoritative. A common nix-darwin pattern is:

- canonical mount at a path such as `$HOME/Media`
- direct `mount_smbfs` there when no mount exists
- optional symlink from that canonical path to `/Volumes/<share>` only when Finder/Bonjour mounted the share first

Therefore, seeing only `Macintosh HD` under `/Volumes` does not prove that no SMB mount exists.

Be cautious with `df`, `du`, `stat` on a live network mount, and health checks that access the share: they can perform remote I/O or hang. Use the mount table first.

## 4. Keep credentials opaque

A declarative module may reveal a credentials-file path without storing secrets in Git. Do not print or ingest the whole file. If one non-secret field such as a share name is required, retrieve only that field locally and keep usernames/passwords/tokens out of tool output, plans, logs, and chat.

## 5. Build narrow guardrails from concrete facts

For a policy-based native agent that must avoid one mounted asset, derive guardrails from:

- canonical mount path
- possible symlink/alternate mount path
- concrete NAS IP or DNS name
- mount/client utilities
- cron workdirs and default cwd

Use exact paths and addresses. Avoid broad textual deny patterns such as `*unraid*` when that word is also a harmless label in local monitoring configuration; such a rule can block legitimate source inspection without improving path isolation.

Command deny rules are defense in depth, not containment. Relative paths, GUI automation, application APIs, existing processes, or adversarial code can bypass command-text matching. Pair them with a persistent current-turn authorization policy and explicit operator acceptance of residual risk.

## 6. Communication rules

- Lead with what the declared architecture and live evidence actually show.
- Distinguish declared state from live state.
- Do not infer that a mount is absent because it is not in the conventional GUI location.
- Do not claim to have inspected a remote machine when tools are executing elsewhere.
- Do not browse protected data merely to prove it exists.
- If the operator accepts same-user native execution, stop repeatedly proposing containers, account splits, or homelab redesign unless new requirements justify revisiting the decision.
