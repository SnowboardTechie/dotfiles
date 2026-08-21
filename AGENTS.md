# DOTFILES KNOWLEDGE BASE

**Generated:** 2026-02-12
**Commit:** f1c2eb6
**Branch:** main

## OVERVIEW

GNU Stow-managed dotfiles for macOS + NixOS, plus an additive-only deployment profile for Omarchy. On macOS/NixOS: single-package stow (`stow . --dotfiles --target $HOME`) with a post-stow setup script for what stow can't handle. On Omarchy: `scripts/setup-omarchy.sh` only — never root stow (see DEPLOYMENT PROFILES).

## STRUCTURE

```
dotfiles/
├── dot-agents/          # Shared agent-skill pool (Claude/Pi/OpenCode); curated per-tool. See dot-agents/README.md
├── dot-config/
│   ├── alacritty/       # Import-chain: base.toml + platform overlay (macOS/Linux)
│   ├── direnv/          # nix-direnv for fast Nix shell caching
│   ├── nvim/            # Neovim config (see nvim/AGENTS.md)
│   ├── opencode/        # AI agent system: agents/, model configs (skills live in dot-agents/)
│   └── zsh/             # Modular shell: env -> options -> plugins -> functions -> aliases
├── dot-gnupg/           # GPG agent (pinentry-mac hardcoded, NixOS must override)
├── dot-tmux/            # Tmux sessions: code-editor.sh, second-brain.sh
├── dot-git-hooks/       # Global pre-commit: validates user.email is set
├── dot-gitconfig        # Identity + GPG signing; includes snowboardtechie + local
├── dot-zshrc            # Shell loader: P10k + modular config sourcing
├── dot-tmux.conf        # Nightfly theme, vim keybinds, TPM plugin configuration
├── dot-p10k.zsh         # Powerlevel10k prompt theme
├── scripts/             # Repo-internal deployment scripts (stow-ignored, never stowed to ~)
│   ├── reconcile-agent-skills.sh  # OWNS skill distribution: canonical *_SKILLS arrays + linking
│   └── setup-omarchy.sh           # Additive Omarchy entry point (agent skills only)
├── tests/               # Integration tests for deployment scripts (stow-ignored)
├── setup-platform-configs.sh  # Post-stow compat entry point: alacritty, tmux plugins, secrets, AGENTS.md; delegates skills to scripts/reconcile-agent-skills.sh
└── zsa-keyboard-layouts/  # Binary firmware, stored but never stowed
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add shell alias | `dot-config/shell/aliases.sh` if portable (bash+zsh, `command -v`-guarded); `dot-config/zsh/aliases.zsh` for zsh/mac/nix-only (eza ls-family, Nix, ssh) | Shared file is sourced by zsh config and by Omarchy's ~/.bashrc |
| Add shell function | `dot-config/zsh/functions.zsh` | git/worktree helpers, `code` launcher |
| Add env variable | `dot-config/zsh/env.zsh` | Use `${VAR:-default}` pattern |
| Add zsh plugin | `dot-config/zsh/plugins.zsh` | Must add 3-path fallback (Homebrew/NixOS/Linux) |
| Add neovim plugin | `dot-config/nvim/lua/bryan/plugins/` | See `nvim/AGENTS.md` |
| Change color theme | See "Nightfly Theme" section below | 3 files must stay in sync |
| Add tmux session | `dot-tmux/` | Follow code-editor.sh pattern |
| Add git identity | `dot-gitconfig` | Add `includeIf` + new identity file |
| Change platform behavior | `setup-platform-configs.sh` | Handles stow edge cases |
| Add a shared agent skill | `dot-agents/skills/` | Pool shared by Claude/Pi/OpenCode/Hermes; curate which tool gets it in the `*_SKILLS` arrays in `scripts/reconcile-agent-skills.sh`. See `dot-agents/README.md` |
| Add Claude Code agent | `dot-claude/agents/` | User-global, personal |
| Add opencode agent | `dot-config/opencode/agents/` | See opencode/AGENTS.md for identity |
| Hindsight memory client wiring | `scripts/reconcile-hindsight.sh` + `hindsight/coding-agent.template.json` | Renders `~/.hindsight/coding-agent.json` (token from `~/.secrets/hindsight/api-bearer`, mode 0600, never in Git) and runs the pinned `@vectorize-io/hindsight-coding-agents` installer. Claude hooks / OpenCode plugin entries are committed in `dot-claude/settings.json` / `dot-config/opencode/opencode.json`; the installer is idempotent over them. |
| Adapt an upstream agent skill | `dot-agents/skills/<name>/` + `dot-agents/upstreams/<source>.json` | The ledger pins the upstream commit, maps upstream paths to local ones, records what diverged and which upstream rules were rejected, and lists the files worth watching. Updates are detected by `hermes/scripts/check-mattpocock-skill-updates.py`, never auto-applied; advancing a pin is a reviewed change. |
| Register/audit exact Git plans in Hindsight | `scripts/hindsight-plan-registry.py` | `register --plan PATH --banks a,b` upserts a deterministic reference doc (repo/path/commit/blob, `execution_authorized=false` unless `--authorize`); `audit --banks a,b` is read-only drift detection. Git stays the exact artifact transport. |

## DEPLOYMENT PROFILES

- **macOS / NixOS (full ownership)**: `stow . --dotfiles --target $HOME` then `./setup-platform-configs.sh`. The setup script remains the compatibility entry point; its agent-skill step delegates to `scripts/reconcile-agent-skills.sh --apply`.
- **Omarchy (additive only)**: `./scripts/setup-omarchy.sh --check` then `--apply`. Omarchy owns shell, terminal, Neovim, tmux, Git, GPG, and tool settings — full-replacement application configs are NOT deployed there by default. Never run `stow .` or `stow --adopt` on an Omarchy host. Additive payload: per-tool agent-skill links (`scripts/reconcile-agent-skills.sh`) + one marked `source` line in `~/.bashrc` loading `dot-config/shell/aliases.sh` (`scripts/reconcile-shell-additions.sh`). Omarchy's own aliases (eza ls-family, zoxide cd, etc.) keep priority — the shared file deliberately omits colliding names.
- **Skill distribution is owned by `scripts/reconcile-agent-skills.sh`**: its `*_SKILLS` arrays are the single curation authority (`dot-agents/README.md` documents rationale only, no mirrored lists). It prunes only symlinks resolving into `dot-agents/skills/` and preserves real dirs, files, foreign/broken symlinks (e.g. Omarchy's `omarchy`/`diagnose-crash` links).
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

### Lua (Neovim)
- `local` for all variables
- 2-space indentation, `expandtab`
- Follow existing plugin file patterns

### Git Commits
- Imperative mood: "Add feature" not "Added feature"
- First line: 50 chars max
- Blank line then details if needed

### Nightfly Theme (3-file sync)
Colors are centralized but defined in three places that MUST stay in sync:
1. **Neovim**: `dot-config/nvim/lua/bryan/core/colors.lua` (Lua table)
2. **Tmux**: `dot-tmux.conf` (top-level `NIGHTFLY_*` variables)
3. **Alacritty**: `dot-config/alacritty/alacritty-base.toml` (`[colors.primary]`)

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
- Tmux plugins are pinned as Git submodules under `dot-tmux/plugins/`; the setup script initializes them and exposes them at `~/.tmux/plugins`

## GIT IDENTITY

- **Default**: snowboardtechie (personal Forgejo + Gitea credential helper), pulled in via unconditional `[include]` of `~/.gitconfig.snowboardtechie` + `~/.gitconfig.local`
- GPG signing on by default (`commit.gpgsign = true`)
- To scope a different identity to a directory, add an `includeIf "gitdir:..."` block pointing at a new identity file
- Global pre-commit hook in `dot-git-hooks/pre-commit` blocks commits without `user.email`

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

# Shell reload
source ~/.zshrc

# Tmux reload
tmux source-file ~/.tmux.conf    # or prefix + r

# Project editor session
code <project>                   # Opens tmux with cli + opencode + nvim

# Nix rebuild (per-machine aliases)
update-mbp / update-a6mbp / update-studio / update-gnarbox
upgrade-mbp  # flake update + rebuild

# Validation
git diff --check                 # Trailing whitespace check
```

## NOTES

- `code` function shadows VS Code intentionally — opens tmux+opencode+nvim session
- `dot-config/opencode/` has its own `.gitignore` with selective whitelisting (track configs, ignore node_modules)
- `grb` function: `grb` = rebase last 3, `grb N` = rebase last N, `grb branch` = rebase onto branch
- `gpg-agent.conf` hardcodes `pinentry-mac` — NixOS users must override manually
- Global gitignore lives at `dot-config/git/ignore` → `~/.config/git/ignore` (XDG path, referenced by `dot-gitconfig` excludesfile)
- This repo syncs to 3 remotes: git.snowboardtechie.com (primary), Codeberg, GitHub
- `AGENTS.md` is globally gitignored via `dot-config/git/ignore`. Repos that need to track it (dotfiles, nix-configs) use `!AGENTS.md` in their `.gitignore` to override.
- `tea` (Forgejo CLI) fails inside this repo with `core.repositoryformatversion does not support extension: worktreeconfig`. The repo sets `extensions.worktreeconfig=true` (per-worktree hooks); tea's go-git backend doesn't support that extension. Workaround: run tea from a throwaway `git init` directory with an explicit `--repo`:
  ```
  TMPDIR=$(mktemp -d) && cd "$TMPDIR" && git init -q \
    && git remote add origin ssh://forgejo@git.snowboardtechie.com/bryan/dotfiles.git \
    && tea pulls create --login git.snowboardtechie.com --repo bryan/dotfiles --head <branch> --base main ...
  ```

## Notes vault

This repo has `vault/` — symlink to a private Obsidian vault at `~/code/notes/dotfiles/`.

Usage conventions: invoke the `vault-pkm` skill (Claude Code, opencode) or read
`~/code/dotfiles/dot-agents/skills/vault-pkm/SKILL.md` and its `references/`
directly (any agent — the skill content is plain markdown).
Per-vault overrides, if any, live at `vault/AGENTS.md` (advertised here; not
auto-loaded by agents — the skill checks for it explicitly in its Step 1).
