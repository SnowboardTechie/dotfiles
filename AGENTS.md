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
├── dot-git-hooks/       # Global pre-commit: validates user.email is set
├── dot-gitconfig        # Identity + GPG signing; includes snowboardtechie + local
├── dot-zshrc            # Shell loader: P10k + modular config sourcing
├── dot-p10k.zsh         # Powerlevel10k prompt theme
├── omarchy/             # Personal Omarchy shell plugins (stow-ignored; deployed additively)
│   └── plugins/snowboardtechie.auto-suspend/  # 45-minute inhibited-idle suspend service
├── scripts/             # Repo-internal deployment scripts (stow-ignored, never stowed to ~)
│   ├── reconcile-agent-skills.sh  # OWNS skill distribution: canonical *_SKILLS arrays + linking
│   └── setup-omarchy.sh           # Additive Omarchy entry point
├── tests/               # Integration tests for deployment scripts (stow-ignored)
├── setup-platform-configs.sh  # Post-stow compat entry point: alacritty, retired-link cleanup, secrets, AGENTS.md; delegates skills to scripts/reconcile-agent-skills.sh
└── zsa-keyboard-layouts/  # Binary firmware, stored but never stowed
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add shell alias | `dot-config/shell/aliases.sh` if portable (bash+zsh, `command -v`-guarded); `dot-config/zsh/aliases.zsh` for zsh/mac/nix-only (eza ls-family, Nix, ssh) | Shared file is sourced by zsh config and by Omarchy's ~/.bashrc |
| Add shell function | `dot-config/zsh/functions.zsh` | Git, Obsidian, and host-guarded Nix helpers |
| Add env variable | `dot-config/zsh/env.zsh` | Use `${VAR:-default}` pattern |
| Add zsh plugin | `dot-config/zsh/plugins.zsh` | Must add 3-path fallback (Homebrew/NixOS/Linux) |
| Add neovim plugin | `dot-config/nvim/lua/bryan/plugins/` | See `nvim/AGENTS.md` |
| Change color theme | See "Nightfly Theme" section below | 2 files must stay in sync |
| Herdr status rail (Glyph Rail) | `dot-config/herdr/config.toml` `[ui] tab_bar_right` + the module scripts beside it (`claude-usage.sh`, `codex-usage.py`, `openrouter-spend.py`, `host-label.sh`) | One Nerd Font glyph per module, joined by `tab_bar_right_separator = " \ue0b3 "`. Keep that TOML escape spelling: U+E0B3 is BMP Private Use Area and text pipelines strip it far more readily than the Plane-15 Nerd Font glyphs, which is how it silently became two spaces once already. `tests/test-herdr-glyph-rail.py` is the regression guard. `theme.name = "terminal"` keeps Herdr on the host terminal's ANSI palette, so colors are NOT defined here — do not add a Nightfly hex table. Only `zoom`, `hostname`, `datetime`, `text`, `command` entry types exist; a glyph-prefixed module must be `command`, since `hostname` takes no prefix. Validate with `HERDR_CONFIG_PATH=$PWD/dot-config/herdr/config.toml herdr config check` (it rejects unknown themes and unsupported `strftime` directives). `codex-usage.py` reads the OpenAI OAuth credential from Hermes first, then Codex CLI, and reports the most-used base quota window as one compact percentage with its reset countdown; it is read-only and leaves refresh/rotation to the owning client. `tests/test-herdr-codex-usage.py` pins rendering and cache fallback. `openrouter-spend.py` reports **account-wide** spend via `POST /api/v1/analytics/query` — it needs an OpenRouter **management key** at `~/.secrets/openrouter/management-key` (mode 0600, never in Git); an `sk-or-v1` inference key gets `403 Only management keys can access analytics`. **Never drop `granularity: "hour"` from that query.** Without it the API snaps `time_range` out to whole UTC days — a one-minute window returns the entire day — so a trailing-24h request silently becomes "yesterday in full plus today so far", measured live at 42.4 hours and 2.04x the true figure. Hourly buckets are clipped to the requested range and are exactly additive (summing a day's hours reproduces the day total to the last decimal); quiet hours are omitted, so no rows means $0, not an error. `tests/test-herdr-openrouter-spend.py` pins the granularity. Do not "fix" it back to a local or simpler source: `/credits` is lifetime-only and `/auth/key`'s `usage_daily` is per-key and midnight-UTC-resetting, so neither is an account-wide rolling 24h. |
| Omarchy auto suspend | `omarchy/plugins/snowboardtechie.auto-suspend/` + `scripts/reconcile-omarchy-auto-suspend.sh` | Service-only Quickshell plugin with a version-controlled 45-minute timeout. It watches Omarchy's `~/.local/state/omarchy/indicators/stay-awake` state (so the stock indicator and `omarchy toggle idle` apply), uses `IdleMonitor.respectInhibitors = true`, and delegates pre-sleep locking to `omarchy-sleep-lock.service`. Keep it additive: link the plugin and add only its service ID to the existing `shell.json`; never replace Omarchy's idle service or edit `/usr/share/omarchy/`. |
| Add git identity | `dot-gitconfig` | Add `includeIf` + new identity file |
| Change platform behavior | `setup-platform-configs.sh` | Handles stow edge cases |
| Add a shared agent skill | `dot-agents/skills/` | Pool shared by Claude/Pi/OpenCode/Hermes; curate which tool gets it in the `*_SKILLS` arrays in `scripts/reconcile-agent-skills.sh`. See `dot-agents/README.md` |
| Personal second brain (Apple Notes) helper | `dot-agents/skills/apple-notes-pkm/scripts/` | `apple-notes-pkm.py` + static `notes.jxa`, hard-scoped to the iCloud folder `Second Brain`; bounded search, exact-id read, revision-guarded append/replace, no delete. `notes_markdown.py` is the Markdown↔Notes-HTML converter (stdlib only). Tests: `python3 tests/test-apple-notes-pkm.py` (offline). `scripts/migrate-second-brain-to-apple-notes.py` is the one-time stage/import/verify migration (2026-09-16); `~/second-brain` is a frozen archive. Skills: `apple-notes-pkm` (personal), `knowledge-capture` (router; replaced `vault-capture`), `vault-pkm` (project vaults only). |
| Apple Notes native Automation helper | `dot-agents/skills/apple-notes-pkm/helper/` + `scripts/reconcile-apple-notes-helper.sh` | `apple-notes-pkm.py` sends **no** Apple Events itself: it shells out to the signed native helper **Apple Notes PKM Helper** (`main.m`, Foundation+OSAKit), the only process that talks to Notes, so the macOS Automation TCC grant lands on a stable code identity instead of a Python runtime. The helper embeds `notes.jxa` in a `__TEXT,__notes_jxa` Mach-O section (no generic AppleScript surface), reads one JSON request on stdin, and disclaims responsibility (`responsibility_spawnattrs_setdisclaim`) so macOS attributes the grant to it, not to Herdr/Python. `identity.json` is the expected bundle id + signing CN; the Python CLI verifies the installed signature before use and fails closed (**exit 7** = missing/unsigned/mismatch). It is signed with the hardened runtime plus the one entitlement in `entitlements.plist` (`com.apple.security.automation.apple-events`); hardened apps cannot send Apple Events without it, so never drop either. JXA stringifies a TCC denial as just `Error: An error occurred.`, so denial detection keys on `errorNumber` (-1743) as well as the message. **Hard signing gate:** `--apply` installs only with a *stable* code-signing identity (CN in `~/.secrets/apple-notes-pkm/signing-identity`, mode 0600, never in Git); it refuses ad-hoc signing because a changing cdhash recreates the dead-TCC-row problem. Build binary and signing material are never committed. Setup + the one-time Notes-Automation approval are in `helper/README.md`. Tests: `bash tests/test-apple-notes-helper.sh` (macOS build/identity, no Notes contact). |
| Add Claude Code agent | `dot-claude/agents/` | User-global, personal |
| Add opencode agent | `dot-config/opencode/agents/` | See opencode/AGENTS.md for identity |
| Hermes personal routines read Apple Notes | `hermes/scripts/personal_notes.py` (+ the three `personal-*.py` collectors) | Bounded title search + exact-id read through the `apple-notes-pkm` helper; never the frozen vault. Weekly hub/spoke titles: `YYYY-MM-DD-weekly-plan`, `YYYY-MM-DD-daily-check-in` in `Second Brain/Journal`. `hermes/test_morning_brief_split.py` pins it. |
| Hindsight memory client wiring | `scripts/reconcile-hindsight.sh` + `hindsight/coding-agent.template.json` | Renders `~/.hindsight/coding-agent.json` (token from `~/.secrets/hindsight/api-bearer`, mode 0600, never in Git), installs the current `@vectorize-io/hindsight-coding-agents` release, and leaves its supported runtime auto-updater enabled. Claude hooks / OpenCode plugin entries are committed in `dot-claude/settings.json` / `dot-config/opencode/opencode.json`; the installer is idempotent over them. The shared `bryan-general` bank remains self-managed rather than receiving coding-specific default strategy changes. |
| Adapt an upstream agent skill | `dot-agents/skills/<name>/` + `dot-agents/upstreams/<source>.json` | The ledger pins the upstream commit, maps upstream paths to local ones, records what diverged and which upstream rules were rejected, and lists the files worth watching. Updates are detected by `hermes/scripts/check-mattpocock-skill-updates.py`, never auto-applied; advancing a pin is a reviewed change. |
| Register/audit exact Git plans in Hindsight | `scripts/hindsight-plan-registry.py` | `register --plan PATH --banks a,b` upserts a deterministic reference doc (repo/path/commit/blob, `execution_authorized=false` unless `--authorize`); `audit --banks a,b` is read-only drift detection. Git stays the exact artifact transport. |

## DEPLOYMENT PROFILES

- **macOS / NixOS (full ownership)**: Stow, then `./setup-platform-configs.sh`. On Gnarbox, use the README's tested Stow ignores for Mac-only `dot-gnupg`, `dot-claude`, and app-owned OpenCode package manifests; never use `--adopt`. The setup script remains the compatibility entry point; its agent-skill step delegates to `scripts/reconcile-agent-skills.sh --apply`.
- **Omarchy (additive only)**: `./scripts/setup-omarchy.sh --check` then `--apply`. Omarchy owns shell, terminal, Neovim, Git, GPG, and tool settings; full-replacement application configs are NOT deployed there by default. Never run `stow .` or `stow --adopt` on an Omarchy host. Additive payload includes per-tool agent-skill links (`scripts/reconcile-agent-skills.sh`), one marked `source` line in `~/.bashrc` loading `dot-config/shell/aliases.sh` (`scripts/reconcile-shell-additions.sh`), and repository-owned personal integrations such as the auto-suspend shell service. Omarchy's own aliases (eza ls-family, zoxide cd, etc.) keep priority; the shared file deliberately omits colliding names.
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
- `setup-platform-configs.sh` removes symlinks to the retired tmux configuration while preserving foreign files and links

## GIT IDENTITY

- **Default**: snowboardtechie (personal Forgejo + Gitea credential helper), with `~/.gitconfig.local` included last to override host-local identity/signing settings
- GPG signing on by default (`commit.gpgsign = true`)
- To scope a different identity to a directory, add an `includeIf "gitdir:..."` block pointing at a new identity file
- Global pre-commit hook in `dot-git-hooks/pre-commit` blocks commits without `user.email`

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

# Validate a Herdr config without touching the live one, then test its modules
HERDR_CONFIG_PATH="$PWD/dot-config/herdr/config.toml" herdr config check
python3 tests/test-herdr-glyph-rail.py   # guards the U+E0B3 divider + glyph-led rail
python3 tests/test-herdr-openrouter-spend.py   # stubs the analytics API; no key or network needed
bash tests/test-herdr-claude-usage.sh
bash tests/test-herdr-host-label.sh
bash tests/test-reconcile-omarchy-auto-suspend.sh
omarchy plugin validate omarchy/plugins/snowboardtechie.auto-suspend

# Shell reload
source ~/.zshrc

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
- `dot-config/opencode/` has its own `.gitignore` with selective whitelisting (track configs, ignore node_modules)
- `grb` function: `grb` = rebase last 3, `grb N` = rebase last N, `grb branch` = rebase onto branch
- `gpg-agent.conf` hardcodes `pinentry-mac` — NixOS users must override manually
- Global gitignore lives at `dot-config/git/ignore` → `~/.config/git/ignore` (XDG path, referenced by `dot-gitconfig` excludesfile)
- This repo syncs to 3 remotes: git.snowboardtechie.com (primary), Codeberg, GitHub
- `AGENTS.md` is globally gitignored via `dot-config/git/ignore`. Repos that need to track it (dotfiles, nix-configs) use `!AGENTS.md` in their `.gitignore` to override.
- `extensions.worktreeconfig` is deliberately OFF here (`core.repositoryformatversion = 0`). It was on with format version 1, which made strict git backends refuse to open the repo — `tea` errored with `does not support extension: worktreeconfig`, and p10k's bundled gitstatusd silently dropped the git prompt segment. Nothing used per-worktree config. If a `git worktree` or `sparse-checkout` operation re-enables it, the prompt goes quiet again: `git config --unset extensions.worktreeConfig && git config core.repositoryformatversion 0`.

## Notes vault

This repo has `vault/` — symlink to a private Obsidian vault at `~/code/notes/dotfiles/`.

Usage conventions: invoke the `vault-pkm` skill (Claude Code, opencode) or read
`~/code/dotfiles/dot-agents/skills/vault-pkm/SKILL.md` and its `references/`
directly (any agent — the skill content is plain markdown).
Per-vault overrides, if any, live at `vault/AGENTS.md` (advertised here; not
auto-loaded by agents — the skill checks for it explicitly in its Step 1).
