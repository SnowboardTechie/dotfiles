# DOTFILES KNOWLEDGE BASE

## OVERVIEW

GNU Stow-managed dotfiles for macOS + NixOS, plus an additive-only deployment profile for Omarchy. On macOS/NixOS: single-package stow (`stow . --dotfiles --target $HOME`) with a post-stow setup script for what stow can't handle. On Omarchy: `scripts/setup-omarchy.sh` only — never root stow (see DEPLOYMENT PROFILES).

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add shell alias | `dot-config/shell/aliases.sh` if portable (bash+zsh, `command -v`-guarded); `dot-config/zsh/aliases.zsh` for zsh/mac/nix-only (eza ls-family, Nix, ssh) | Shared file is sourced by zsh config and by Omarchy's ~/.bashrc |
| Add zsh plugin | `dot-config/zsh/plugins.zsh` | Must add 3-path fallback (Homebrew/NixOS/Linux) |
| Change color theme | See "Nightfly Theme" section below | |
| Omarchy auto suspend | `omarchy/plugins/snowboardtechie.auto-suspend/` + `scripts/reconcile-omarchy-auto-suspend.sh` | Service-only Quickshell plugin with a version-controlled 45-minute timeout. It watches Omarchy's `~/.local/state/omarchy/indicators/stay-awake` state (so the stock indicator and `omarchy toggle idle` apply), uses `IdleMonitor.respectInhibitors = true`, and delegates pre-sleep locking to `omarchy-sleep-lock.service`. Keep it additive: link the plugin and add only its service ID to the existing `shell.json`; never replace Omarchy's idle service or edit `/usr/share/omarchy/`. |
| Add a shared agent skill | `dot-agents/skills/` | Pool shared by Claude/Pi/OpenCode/Hermes; curate which tool gets it in the `*_SKILLS` arrays in `scripts/reconcile-agent-skills.sh`. See `dot-agents/README.md` |
| Worktree guard for work repos | `dot-claude/scripts/require-worktree.sh` + its `PreToolUse` entry in `dot-claude/settings.json` | Denies tracked-file edits, commits, in-place branch switches, and `gh pr checkout` in the main checkout of repos whose `origin` is GitHub `HHS/`, `common-grants/`, or `agilesix/` (`GUARDED_ORIGIN`). Gitignored files and linked worktrees pass. Keys off the edited file's repo, not the session cwd. Bash parsing is split-on-separators, not a shell parser. Claude Code only; other agents are unguarded. Tests: `bash tests/test-require-worktree.sh`. |
| Hermes personal routines + Studio-native Matrix dependencies | `hermes/` | Details and tests live in `hermes/AGENTS.md` |
| Retired agent memory (Hindsight, context-mode, claude-mem) | `scripts/retire-agent-memory.py` | Retired 2026-09-29; no replacement. Agents use harness-native memory (Claude auto-memory, Hermes `MEMORY.md`/`USER.md`) plus project vaults and the `~/second-brain` vault. The helper (`--check`/`--apply`, run by `setup-platform-configs.sh` and `setup-omarchy.sh`) removes only those tools' known hooks, plugins/marketplaces, MCP servers, and Pi/OpenCode entries from machine-local JSON; it never deletes data dirs or native memory and only reports leftovers. Tests: `python3 tests/test-retire-agent-memory.py`. Do not reintroduce a Hindsight installer or plan registry — exact plans stay in Git. |
| Where skills keep resumable state | `dot-agents/lib/agent_state.py` | `{trunk}/.agent-work/<skill>/<key>/` (issue-work, issue-create, pr-self-review, multiagent-pr-review). An existing legacy `{trunk}/.hermes/<skill>/<key>/` is resumed in place, never moved: recorded files hold absolute paths into it. Both are ignored globally (`dot-config/git/ignore`) and here. The issue-work context validator admits either root. Tests: `python3 tests/test-agent-state.py`. |
| Skill launches into Rex | `dot-agents/lib/terminal_host.py` | Shared host detection for skill scripts that open panes for other agents: Rex from `REX_BLOCK` + `REX_SESSION`, else none. Rex's `rex` isn't on PATH; the helper falls back to `$REX_BIN_DIR/rex`. `next-session` uses it; tests in `tests/test-next-session-launch.py`. Herdr was retired 2026-11-03; don't reintroduce a Herdr host. |
| Draw a picture in a Rex pane | `dot-agents/skills/draw-it/` (Pi only in `PI_SKILLS`) | `scripts/show.py` splits the caller's pane and draws a PNG there with the kitty graphics protocol; standard library only, Rex found through `terminal_host.py`. The pane process stays alive to redraw on resize. Rex leaves an unfocused new pane at 80x24 with no owner, so `show.py` sizes it from the caller's pane via the block `resize` method. Drawing is a throwaway Pillow script run with `uv run --with pillow`; `scripts/example.py` holds the sizes Bryan confirmed readable. Tests: `python3 -m unittest tests/test-draw-it.py`. |
| Hermes in Rex | `dot-agents/skills/rex/` (Hermes-only in `HERMES_SKILLS`) + `dot-config/zsh/env.zsh` | Rex Beta's `rex skill setup` hardcodes Claude/Codex/OpenCode/Pi, so Hermes gets a repo copy of Rex's thin skill stub. Hermes tools run under the gateway, so `REX_SESSION`/`REX_BLOCK`/`REX_SERVER`/`REX_BIN_DIR` reach them only via `terminal.client_env_passthrough` in `~/.hermes/config.yaml` (machine-local, set with `hermes config set`; `env_passthrough` is the wrong knob — it forwards the gateway's own env). `env.zsh` appends `$REX_BIN_DIR` to PATH in Rex panes so Claude's Rex hook finds `rex`; the gateway's tool PATH doesn't inherit it, so the skill falls back to `$REX_BIN_DIR/rex`. Tab activity/alerts come from the OSC 7501 runtime patch; tab names come from the `rex-tab-title` plugin; closing a tab archives its Hermes sessions via the `rex-tab-archive` plugin. See `hermes/AGENTS.md`. |
| Claude seat for Pi | `pi()` in `dot-config/shell/aliases.sh` + `dot-pi/agent/extensions/pi-seat.ts` (linked by `scripts/reconcile-pi-extensions.sh`) | Same rule as `claude()`: under `~/code/sgg` the work seat (`PI_CLAUDE_CODE_CONFIG_DIR` unset), elsewhere the personal plan (`~/.claude-personal`). Setting it to `~/.claude` breaks pi-claude-code, so the work seat is always "unset". Explicit `PI_CLAUDE_CODE_CONFIG_DIR`/`CLAUDE_CONFIG_DIR` wins; `command pi` bypasses. Defined only where `~/.claude-personal` exists. `/seat` in Pi prints the seat and its account; the footer shows it. Tests: `bash tests/test-pi-seat-wrapper.sh`. |
| Pi in Rex: briefing and names | `dot-pi/agent/extensions/pi-rex.ts` (linked by `scripts/reconcile-pi-extensions.sh`) | Pi's stand-in for the SessionStart hook `rex skill setup` gives Claude/Codex (Rex reports hooks as unsupported for Pi). In a Rex pane, a TUI Pi gets Rex's own briefing (`rex __internal session-start`) as a `rex` prompt section, plus a `rex_name` tool the model calls once to name its pane (slug, also the Pi session name), tab (lane) and Rex session (initiative). Each level is renamed only while it holds a placeholder: Rex's generated label or the `/split` launcher's `split-ab12`. The first Pi to name a Rex session leaves a marker in `~/.pi/agent/runtime/pi-rex/sessions/`, and no Pi names that session again. Headless children (`pi -p`) inherit `REX_BLOCK`, so everything is TUI-only. Tab activity is Pi's native OSC 7501, not this. Tests: `node --test tests/test-pi-rex.ts`. |
| Open another Pi beside this one | `dot-pi/agent/extensions/pi-split.ts` (linked by `scripts/reconcile-pi-extensions.sh`) | `/split [prompt]` opens a fresh Pi in a Rex pane to the right; `/split-fork [prompt]` opens one on a copy of this conversation (`pi --fork`). Both keep this session's model, thinking level and seat, and focus stays here. Adapted from `split-fork.ts` in `mitsuhiko/agent-stuff`; the Rex work is delegated to the next-session launcher (`--fork`, optional `--prompt-file` for Pi). Tests: `node --test tests/test-pi-split.ts` and `python3 -m unittest tests/test-next-session-launch.py`. |
| `bot <name>`: show a bot's tab | `bot()` in `dot-config/shell/aliases.sh` + `dot-config/shell/bot-tab.py`; trust in `scripts/reconcile-pi-bots-trust.mjs` (run by `setup-platform-configs.sh`) | The bots are the directories under `$PI_BOTS_DIR` (default `~/code/pi-bots/bots`) with an `AGENTS.md`, read on every call and completion, so `pi-bots bot create`/`retire` need no new shell. `bot` lists them; `bot <name>` makes the bot's tab active in the `bots` Rex session, then asks one Rex app to show it (`session.select`): the calling pane's block owner (the app that claimed it, not necessarily the machine you type on), else the only connected app; with neither, none. Remote Control must be on in that app, else the tab is still active. Completion and the list take only valid pi-bots names. It never opens, closes or restarts a tab: pi-bots owns them. The trust reconciler saves a Pi trust decision for the bots' parent through Pi's own `ProjectTrustStore`, so a desk Pi in a bot directory reads its `.pi/settings.json`; a saved "do not trust" on that directory is left alone, one on a parent is overridden (and says so). Keys are real paths (`~/code/pi-bots` is a symlink). Defined only where the bot directories exist. Tests: `bash tests/test-bot-alias.sh`. |
| Agents surviving a Rex server restart | `scripts/rex-agent-sessions.py` + `dot-pi/agent/extensions/rex-agent-sessions.ts` + `scripts/reconcile-rex-agent-sessions.sh` | A Rex server restart (upgrade, crash) restores panes as bare shells and kills their programs. A launchd watcher (`com.snowboardtechie.rex-agent-sessions`, installed by `setup-platform-configs.sh`) snapshots each pane's Claude/Hermes/Pi session every 30s, keyed by agent PID (Claude `~/.claude*/sessions/<pid>.json`, Hermes `runtime/active_sessions.json` per profile, Pi via the extension's `~/.pi/agent/runtime/rex-agent-sessions/<pid>.json`). When the server `instance_id` changes it types each resume command into its own pane, only once that pane is an idle shell. `stop`ping the Rex server still ends every running program; never restart it as a no-risk step. Tests: `python3 tests/test-rex-agent-sessions.py`. |
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

### Nightfly Theme
Colors are centralized in `dot-config/nvim/lua/bryan/core/colors.lua` (Lua table); gh-dash mirrors the palette in `dot-config/gh-dash/config.yml`.

## ANTI-PATTERNS

| Rule | Reason |
|------|--------|
| Never commit API keys/tokens/secrets | Use `~/.secrets/` + `{file:...}` references |
| Never add plugin path without 3-path fallback | Breaks on the other platform |
| Never stow `~/.gnupg/` directory | Contains sensitive unmanaged files; manual symlink only |
| Never overwrite `dot-config/opencode/AGENTS.md` | Identity/behavioral file, not coding guidelines |
| Never add to `.stow-local-ignore` without checking nested impact | Root AGENTS.md ignore also blocks opencode/AGENTS.md |
| Never run Forgejo merges in parallel against the same base | API returns `HTTP 200` + `merged=true` for both, but only one advances `main`; the loser is recorded with a `merge_commit_sha` that doesn't exist in the repo and can't be reopened. Serialize merges. |

## STOW QUIRKS

- `.stow-local-ignore` blocks AGENTS.md at ALL levels (not just root)
- `setup-platform-configs.sh` compensates by manually symlinking `opencode/AGENTS.md`
- GPG config requires manual: `ln -s ~/code/dotfiles/dot-gnupg/gpg-agent.conf ~/.gnupg/gpg-agent.conf`
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
- Stage only at commit time, in the same command as `git commit`. Automated pi-durable commits (`dot-config/pi-durable/*.json`) run `git commit` on this checkout and sweep up whatever is already in the index: `git rm` stages immediately, so prefer plain `rm` while editing.

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

# Nix rebuild (auto-detects this machine's flake output and confirms it)
update-system   # rebuild with current flake inputs
upgrade-system  # flake update + rebuild

# Validation
git diff --check                 # Trailing whitespace check
```

## NOTES

- `gpg-agent.conf` hardcodes `pinentry-mac` — NixOS users must override manually
- This repo syncs to 2 remotes: git.snowboardtechie.com (primary) and a GitHub push mirror
- `AGENTS.md` is globally gitignored via `dot-config/git/ignore`. Repos that need to track it (dotfiles, nix-configs) use `!AGENTS.md` in their `.gitignore` to override.
- `extensions.worktreeconfig` is deliberately OFF here (`core.repositoryformatversion = 0`). It was on with format version 1, which made strict git backends refuse to open the repo — `tea` errored with `does not support extension: worktreeconfig`, and p10k's bundled gitstatusd silently dropped the git prompt segment. Nothing used per-worktree config. If a `git worktree` or `sparse-checkout` operation re-enables it, the prompt goes quiet again: `git config --unset extensions.worktreeConfig && git config core.repositoryformatversion 0`.

## Notes vault

This repo has `vault/`.

Usage conventions: invoke the `vault-pkm` skill (Claude Code, opencode) or read
`~/code/dotfiles/dot-agents/skills/vault-pkm/SKILL.md` and its `references/`
directly (any agent — the skill content is plain markdown).
Per-vault overrides, if any, live at `vault/AGENTS.md` (advertised here; not
auto-loaded by agents — the skill checks for it explicitly in its Step 1).
