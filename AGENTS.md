# DOTFILES KNOWLEDGE BASE

## OVERVIEW

GNU Stow-managed dotfiles for macOS + NixOS, plus an additive-only deployment profile for Omarchy. On macOS/NixOS: single-package stow (`stow . --dotfiles --target $HOME`) with a post-stow setup script for what stow can't handle. On Omarchy: `scripts/setup-omarchy.sh` only — never root stow (see DEPLOYMENT PROFILES).

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add shell alias | `dot-config/shell/aliases.sh` if portable (bash+zsh, `command -v`-guarded); `dot-config/zsh/aliases.zsh` for zsh/mac/nix-only (eza ls-family, Nix, ssh) | Shared file is sourced by zsh config and by Omarchy's ~/.bashrc |
| Add zsh plugin | `dot-config/zsh/plugins.zsh` | Must add 3-path fallback (Homebrew/NixOS/Linux) |
| Change color theme | See "Nightfly Theme" section below | 2 files must stay in sync |
| Herdr status rail (Glyph Rail) | `dot-config/herdr/` | Module gotchas, never-do rules, and test commands live in `dot-config/herdr/AGENTS.md` |
| Omarchy auto suspend | `omarchy/plugins/snowboardtechie.auto-suspend/` + `scripts/reconcile-omarchy-auto-suspend.sh` | Service-only Quickshell plugin with a version-controlled 45-minute timeout. It watches Omarchy's `~/.local/state/omarchy/indicators/stay-awake` state (so the stock indicator and `omarchy toggle idle` apply), uses `IdleMonitor.respectInhibitors = true`, and delegates pre-sleep locking to `omarchy-sleep-lock.service`. Keep it additive: link the plugin and add only its service ID to the existing `shell.json`; never replace Omarchy's idle service or edit `/usr/share/omarchy/`. |
| Add a shared agent skill | `dot-agents/skills/` | Pool shared by Claude/Pi/OpenCode/Hermes; curate which tool gets it in the `*_SKILLS` arrays in `scripts/reconcile-agent-skills.sh`. See `dot-agents/README.md` |
| Apple Notes helper + native Automation helper | `dot-agents/skills/apple-notes-pkm/` + `scripts/reconcile-apple-notes-helper.sh` | Helper contract, signing gate, and tests live in `dot-agents/skills/apple-notes-pkm/AGENTS.md` |
| Worktree guard for work repos | `dot-claude/scripts/require-worktree.sh` + its `PreToolUse` entry in `dot-claude/settings.json` | Denies tracked-file edits, commits, in-place branch switches, and `gh pr checkout` in the main checkout of repos whose `origin` is GitHub `HHS/`, `common-grants/`, or `agilesix/` (`GUARDED_ORIGIN`). Gitignored files and linked worktrees pass. Keys off the edited file's repo, not the session cwd. Bash parsing is split-on-separators, not a shell parser. Claude Code only; other agents are unguarded. Tests: `bash tests/test-require-worktree.sh`. |
| Hermes personal routines + Studio-native Matrix dependencies | `hermes/` | Details and tests live in `hermes/AGENTS.md` |
| Retired agent memory (Hindsight, context-mode, claude-mem) | `scripts/retire-agent-memory.py` | Retired 2026-09-29; no replacement. Agents use harness-native memory (Claude auto-memory, Hermes `MEMORY.md`/`USER.md`) plus project vaults and Apple Notes. The helper (`--check`/`--apply`, run by `setup-platform-configs.sh` and `setup-omarchy.sh`) removes only those tools' known hooks, plugins/marketplaces, MCP servers, and Pi/OpenCode entries from machine-local JSON; it never deletes data dirs or native memory and only reports leftovers. Tests: `python3 tests/test-retire-agent-memory.py`. Do not reintroduce a Hindsight installer or plan registry — exact plans stay in Git. |
| Adapt an upstream agent skill | `dot-agents/skills/<name>/` + `dot-agents/upstreams/<source>.json` | The ledger pins the upstream commit, maps upstream paths to local ones, records what diverged and which upstream rules were rejected, and lists the files worth watching. Updates are detected by `hermes/scripts/check-mattpocock-skill-updates.py`, never auto-applied; advancing a pin is a reviewed change. |

## DEPLOYMENT PROFILES

- **macOS / NixOS (full ownership)**: Stow, then `./setup-platform-configs.sh`. On Gnarbox, use the README's tested Stow ignores for Mac-only `dot-gnupg`, `dot-claude`, and OpenCode (Pi replaces it); never use `--adopt`. The setup script remains the compatibility entry point; its agent-skill step delegates to `scripts/reconcile-agent-skills.sh --apply` (with OpenCode pool links retired only on Gnarbox).
- **Omarchy (additive only)**: `./scripts/setup-omarchy.sh --check` then `--apply`. Omarchy owns shell, terminal, Neovim, Git, GPG, and tool settings; full-replacement application configs are NOT deployed there by default. Never run `stow .` or `stow --adopt` on an Omarchy host. Additive payload includes per-tool agent-skill links (`scripts/reconcile-agent-skills.sh`), one marked `source` line in `~/.bashrc` loading `dot-config/shell/aliases.sh` (`scripts/reconcile-shell-additions.sh`), and repository-owned personal integrations such as the auto-suspend shell service. Omarchy's own aliases (eza ls-family, zoxide cd, etc.) keep priority; the shared file deliberately omits colliding names.
- **Skill distribution is owned by `scripts/reconcile-agent-skills.sh`**: its `*_SKILLS` arrays are the single curation authority (`dot-agents/README.md` documents rationale only, no mirrored lists). It prunes only symlinks resolving into `dot-agents/skills/` and preserves real dirs, files, foreign/broken symlinks (e.g. Omarchy's `omarchy`/`diagnose-crash` links).
- **Gnarbox's Pi profile**: `dot-pi/agent/models.json` declares tailnet-only Studio Ollama models; `setup-platform-configs.sh` calls the skill reconciler with `RECONCILE_OPENCODE_SKILLS=0` so only pool-owned OpenCode links are retired. Other hosts retain OpenCode.
- **Future reconcilers and profile logic belong under `scripts/`**, invoked from `setup-omarchy.sh`'s reconciler list — never as inline mutation logic in an entry point. New root-level project dirs must get root-anchored `.stow-local-ignore` entries (`^/name$`) so legacy root stow can't deploy them.

## CONVENTIONS

### Shell Scripts (Bash/Zsh)
- Shebangs: `#!/usr/bin/env bash` or `#!/usr/bin/env zsh`
- Defaults: `${VAR:-default}` pattern
- Error handling: `|| return 1`, validate dirs exist before operating
- Color output: `GREEN/YELLOW/RED/BOLD/NC` variables for user-facing scripts
- `local` for all function variables
- `set -e` for scripts that should fail fast
- NO trailing whitespace on empty lines

### Cross-Platform Pattern (CRITICAL)
Three-path fallback for anything sourced from the system:
```bash
if [[ -f /opt/homebrew/share/TOOL/FILE ]]; then       # macOS Homebrew
  source /opt/homebrew/share/TOOL/FILE
elif [[ -f /run/current-system/sw/share/TOOL/FILE ]]; then  # NixOS
  source /run/current-system/sw/share/TOOL/FILE
elif [[ -f /usr/share/TOOL/FILE ]]; then               # Standard Linux
  source /usr/share/TOOL/FILE
fi
```
Platform detection: `[[ "$OSTYPE" == "darwin"* ]]`

### Git Commits
- Imperative mood: "Add feature" not "Added feature"
- First line: 50 chars max
- Blank line then details if needed

### Nightfly Theme (2-file sync)
Colors are centralized but defined in two places that MUST stay in sync:
1. **Neovim**: `dot-config/nvim/lua/bryan/core/colors.lua` (Lua table)
2. **Alacritty**: `dot-config/alacritty/alacritty-base.toml` (`[colors.primary]`)

## ANTI-PATTERNS

| Rule | Reason |
|------|--------|
| Never commit API keys/tokens/secrets | Use `~/.secrets/` + `{file:...}` references |
| Never add plugin path without 3-path fallback | Breaks on the other platform |
| Never edit `alacritty.toml` directly | Generated symlink; edit `alacritty-{macos,linux}.toml` or `alacritty-base.toml` |
| Never stow `~/.gnupg/` directory | Contains sensitive unmanaged files; manual symlink only |
| Never overwrite `dot-config/opencode/AGENTS.md` | Identity/behavioral file, not coding guidelines |
| Never add to `.stow-local-ignore` without checking nested impact | Root AGENTS.md ignore also blocks opencode/AGENTS.md |
| Never run Forgejo merges in parallel against the same base | API returns `HTTP 200` + `merged=true` for both, but only one advances `main`; the loser is recorded with a `merge_commit_sha` that doesn't exist in the repo and can't be reopened. Serialize merges. |

## STOW QUIRKS

- `.stow-local-ignore` blocks AGENTS.md at ALL levels (not just root)
- `setup-platform-configs.sh` compensates by manually symlinking `opencode/AGENTS.md`
- GPG config requires manual: `ln -s ~/code/dotfiles/dot-gnupg/gpg-agent.conf ~/.gnupg/gpg-agent.conf`
- `alacritty.toml` is a generated platform-conditional symlink, gitignored
- `~/.config` is one folded symlink to `dot-config/`, so `.gitignore` allowlists the managed tools (`dot-config/*` then `!dot-config/<tool>/`). Adopting a new tool needs its own `!` line; never switch back to per-tool deny lines
- `setup-platform-configs.sh` removes symlinks to the retired tmux configuration while preserving foreign files and links

## GIT IDENTITY

- **Default**: snowboardtechie (personal Forgejo + Gitea credential helper), with `~/.gitconfig.local` included last to override host-local identity/signing settings
- GPG signing on by default (`commit.gpgsign = true`)
- To scope a different identity to a directory, add an `includeIf "gitdir:..."` block pointing at a new identity file
- Global pre-commit hook in `dot-git-hooks/pre-commit` blocks commits without `user.email` and runs `gitleaks` on the staged diff in every repo (warns instead where gitleaks is missing). Tests: `bash tests/test-pre-commit-hook.sh`

## REPOSITORY DELIVERY

- **This repo is an explicit exception to the default wait-for-authorization rule.** Once requested work is complete and verified, commit the task-owned changes directly to `main` and push `origin main` without waiting for a separate commit or push request.
- A local commit is not completion. Verify that `origin/main` contains the pushed commit before reporting the work done.
- Preserve unrelated work: stage only the exact task-owned paths. Never absorb, discard, stash, reset, or rewrite unrelated changes to make the commit or push succeed.
- If `origin/main` has diverged or the push is rejected, stop and report the blocker rather than rebasing or rewriting user work automatically.

## COMMANDS

```bash
# Install (macOS/NixOS full ownership only — never on Omarchy)
stow . --dotfiles --target $HOME
./setup-platform-configs.sh

# Install (Omarchy, additive agent skills only)
./scripts/setup-omarchy.sh --check    # report, no mutation
./scripts/setup-omarchy.sh --apply

# Reconcile agent skills alone (any platform)
./scripts/reconcile-agent-skills.sh --check
./scripts/reconcile-agent-skills.sh --apply

# Test the reconciler (isolated temp homes)
bash tests/test-reconcile-agent-skills.sh

# Test the Omarchy auto-suspend plugin
bash tests/test-reconcile-omarchy-auto-suspend.sh
omarchy plugin validate omarchy/plugins/snowboardtechie.auto-suspend

# Herdr config + module tests: see dot-config/herdr/AGENTS.md

# SSH-first Studio workspace (use herdr-studio-remote for MBP-local image bridging)
herdr-studio

# Nix rebuild (auto-detects this machine's flake output and confirms it)
update-system   # rebuild with current flake inputs
upgrade-system  # flake update + rebuild

# Validation
git diff --check                 # Trailing whitespace check
```

## NOTES

- `herdr-studio` attaches over ordinary SSH to the persistent Studio server; `herdr-studio-remote` keeps Herdr's local-client remote mode for MBP-local image clipboard bridging
- `gpg-agent.conf` hardcodes `pinentry-mac` — NixOS users must override manually
- This repo syncs to 3 remotes: git.snowboardtechie.com (primary), Codeberg, GitHub
- `AGENTS.md` is globally gitignored via `dot-config/git/ignore`. Repos that need to track it (dotfiles, nix-configs) use `!AGENTS.md` in their `.gitignore` to override.
- `extensions.worktreeconfig` is deliberately OFF here (`core.repositoryformatversion = 0`). It was on with format version 1, which made strict git backends refuse to open the repo — `tea` errored with `does not support extension: worktreeconfig`, and p10k's bundled gitstatusd silently dropped the git prompt segment. Nothing used per-worktree config. If a `git worktree` or `sparse-checkout` operation re-enables it, the prompt goes quiet again: `git config --unset extensions.worktreeConfig && git config core.repositoryformatversion 0`.

## Notes vault

This repo has `vault/`.

Usage conventions: invoke the `vault-pkm` skill (Claude Code, opencode) or read
`~/code/dotfiles/dot-agents/skills/vault-pkm/SKILL.md` and its `references/`
directly (any agent — the skill content is plain markdown).
Per-vault overrides, if any, live at `vault/AGENTS.md` (advertised here; not
auto-loaded by agents — the skill checks for it explicitly in its Step 1).
