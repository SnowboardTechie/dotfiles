# Shared Skill Distribution and Portability Patterns

Use these patterns when a canonical skill repository feeds several agent runtimes.

## Curated symlink distribution

A per-runtime allowlist is safer than exposing a mixed pool wholesale. Put links in a dedicated category such as `~/.hermes/skills/personal/` so bundled/local skills can retain precedence.

The installer must be conservative:

- Prune only symlinks whose resolved target is inside the canonical pool.
- Never replace a real directory, regular file, or foreign symlink automatically.
- On a collision, warn and skip. A real directory may contain local-only corpus or an independently managed skill.
- Count successful links, not requested names.
- Document that foreground edits through a symlink modify the canonical repository.

Test with a temporary `HOME` containing:

1. An empty destination: every curated item becomes a pool symlink.
2. A real directory colliding with a curated name: its sentinel file survives and the installer reports a warning.
3. A stale pool-owned symlink no longer in the allowlist: it is pruned.
4. A foreign symlink: it survives.

Run shell syntax validation before the sandbox test.

## Repository state versus runtime activation

Treat these as separate completion gates:

1. Distribution code is written and sandbox-tested.
2. The real runtime links/config are installed.
3. The destination re-scans skills or starts a new session.
4. The migrated skills appear in the destination index and can load their support files.

Do not report a runtime path as installed merely because the setup script would create it. If activation remains undone, say so explicitly.

## Portable forge remote parsing

Do not use lazy regex quantifiers such as `+?` with BSD/macOS `sed -E`; they are not portable. Prefer one deterministic Bash parser script shared by every forge-aware skill.

Handle at least:

- `git@github.com:owner/repo.git`
- `https://github.com/owner/repo.git`
- `ssh://git@github.com/owner/repo.git`
- self-hosted Forgejo/Gitea SSH and HTTPS
- Codeberg SCP-style SSH
- malformed input, which must fail rather than guess

Emit structured fields such as tab-delimited `host`, `owner/repo`, and
`instance URL`. Preserve an explicit HTTP/HTTPS scheme and non-default port in
the instance URL while keeping the host field suitable for forge detection.
Test exact output for every representative URL.

**Guard scheme parsing before the SCP-style `*:*` fallback.** Otherwise inputs
such as `file:///tmp/repo` or `ftp://host/owner/repo` look like SCP remotes and
can be misparsed as a forge host. Accept only the intended URL schemes, then
handle `user@host:path` separately. Negative fixtures should cover empty input,
unsupported schemes, host-only URLs, and path-only strings.

When the repository has no canonical test command, create a focused verifier
with `tempfile` under `/private/tmp` using a `hermes-verify-` prefix. Run shell
syntax plus positive and negative fixtures against the final edited script,
remove the verifier in a `finally` block, and report the result as **ad-hoc
verification**, not “suite green.” Re-run this after the last parser edit; an
earlier successful probe is stale evidence.

### Registering ad-hoc verification evidence

In Hermes coding sessions, make creation, execution, and cleanup distinct steps:

1. Create the OS-safe `hermes-verify-*.py` or `.sh` file with `tempfile`.
2. Execute that temporary verifier **directly** in a subsequent terminal call.
3. After the direct call reports success, remove the verifier in a final call.

Do not hide the verifier inside the Python process that creates it. Its nested
subprocess may pass while the runtime still retains an older failed verification
record. Direct execution lets the verification tracker associate the passing
result with the ad-hoc verifier; separate cleanup preserves that evidence while
leaving no temporary artifact.

Use authenticated forge CLIs (`gh`, `tea api`) for writes. Never scrape a token from a CLI config into shell output or examples. If a CLI cannot inspect the current checkout because of a Git extension, run it from a temporary initialized repository with explicit login/repository arguments.

## Multi-agent editing discipline

Partition delegated edits by non-overlapping paths. The parent may continue on unrelated files, but must not patch a delegated file until that worker has completed and its output has been read. After fan-out:

- inspect actual diffs rather than trusting summaries;
- validate every assigned path;
- search for requirements the workers only partially applied;
- run one consolidated independent review after all parent fixes.

A file appearing modified is not proof that its worker completed every requirement.
