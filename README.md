# Dotfiles

Personal development environment configuration.

Two deployment models are supported:

- **Full workstation ownership** (macOS, NixOS): GNU Stow symlinks the whole
  environment: shell, terminal, editor, Git, GPG, and agent tooling.
- **Additive assets** (Omarchy): the OS already owns the desktop and development
  environment; only curated personal agent skills are linked in. See
  [Omarchy Installation](#omarchy-installation-additive-only).

## Overview

This repository contains dotfiles organized into Stow packages for easy symlinking and management. Configurations are split between:

- `~/` (home directory) for traditional dotfiles
- `~/.config/` for XDG-compliant applications

## Prerequisites

### Required

- **GNU Stow** - Symlink manager for dotfiles

### Platform-Specific Setup

#### macOS

**Option A: Using Nix-Darwin (Recommended)**

If you're using [nix-configs](https://github.com/bryan-thompsoncodes/nix-configs):

- All dependencies (Powerlevel10k, zsh plugins, tools, fonts, etc.) are installed via nix-darwin configuration
- GNU Stow is included in the nix configuration

**Option B: Using Homebrew**

1. Install Homebrew:

   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

2. Install dependencies:
   ```bash
   brew install stow
   brew install powerlevel10k zsh-autosuggestions zsh-syntax-highlighting
   brew install bat eza fzf direnv herdr
   brew install neovim git gnupg
   brew install --cask font-meslo-lg-nerd-font
   ```

#### NixOS

**Option A: Using Nix Flakes (Recommended)**

If you're using [nix-configs](https://github.com/bryan-thompsoncodes/nix-configs):

- All dependencies (Powerlevel10k, zsh plugins, tools, fonts, etc.) are installed via NixOS configuration
- GNU Stow is included in the nix configuration

**Option B: Manual System Configuration**

Add the following packages to your `configuration.nix`:

```nix
environment.systemPackages = with pkgs; [
  stow
  zsh-powerlevel10k
  zsh-autosuggestions
  zsh-syntax-highlighting
  bat
  eza
  fzf
  direnv
  (nerdfonts.override { fonts = [ "Meslo" ]; })
  neovim
  git
  gnupg
  pinentry-curses  # or pinentry-gnome3, pinentry-qt
];
```

**Note:** Some configurations may need local overrides:

- `~/.gnupg/gpg-agent.conf` - Set correct pinentry program path for your system

## Installation

### Full Workstation Installation (macOS / NixOS)

From this repository's root directory:

```bash
stow . --dotfiles --target $HOME
./setup-platform-configs.sh
```

This symlinks the dotfiles, configures platform-specific Alacritty settings, removes retired tmux links, and sets up the secrets directory.

**Additional Manual Step:**

**GPG configuration** - Link GPG agent config:

```bash
ln -s ~/code/dotfiles/dot-gnupg/gpg-agent.conf ~/.gnupg/gpg-agent.conf
```

### Omarchy Installation (Additive Only)

Omarchy ships its own coherent Bash, Foot, Neovim, Git, and GPG configuration.
Do **not** run `stow .` or `stow --adopt` on an Omarchy host:

- `stow .` conflicts with files Omarchy already owns and, where it would
  succeed, shadows Omarchy's XDG configs (e.g. `~/.gitconfig` over
  `~/.config/git/config`) with macOS/Nix-oriented settings.
- `stow --adopt` is worse: it **moves** Omarchy's live configuration files into
  this repository, corrupting both.

Use the dedicated additive entry point instead:

```bash
./scripts/setup-omarchy.sh --check   # report what would change; mutates nothing
./scripts/setup-omarchy.sh --apply   # perform the additive setup
```

What it changes: per-tool symlinks for curated personal agent skills in
`~/.claude/skills`, `~/.config/opencode/skills`, `~/.pi/agent/skills`, and
`~/.hermes/skills/personal`, plus one marked `source` line appended to an
existing `~/.bashrc` (Omarchy's designated personal-additions section) that
loads the portable aliases from `dot-config/shell/aliases.sh` — nothing else.

What it intentionally leaves untouched: login shell selection, terminal, Neovim,
Git, GPG, Zed/OpenCode/Claude settings, installed packages, and everything under
`/usr/share/omarchy`. Omarchy-provided skill links (e.g. `omarchy`,
`diagnose-crash`) are preserved as-is.

Always run `--check` and review the report before running `--apply`.

### Initial Migration (Existing Dotfiles)

If you're setting up this repo for the first time and want to migrate existing dotfiles:

```bash
stow . --adopt --dotfiles --target $HOME
```

The `--adopt` flag will move any existing files in your home directory into the dotfiles repo. After adoption, review the changes and commit only the files you want to manage.

**Warning**: Be careful with `--adopt` as it will move existing files into the repo. Review changes before committing. Never use `--adopt` on an Omarchy host — it moves Omarchy-owned configuration into the repository.

## Structure

```text
dotfiles/
├── dot-config/          # XDG config directory (~/.config/)
│   ├── alacritty/       # Terminal emulator
│   ├── direnv/          # Direnv configuration with nix-direnv
│   ├── nvim/            # Neovim configuration (Lazy.nvim)
│   ├── opencode/        # OpenCode AI assistant
│   │   ├── AGENTS.md            # Global agent instructions
│   │   └── opencode.json        # Provider and model configuration
│   └── zsh/             # Modular zsh configuration (~/.config/zsh/)
│       ├── aliases.zsh      # All aliases (git, tools, nix, navigation)
│       ├── env.zsh          # Environment variables
│       ├── functions.zsh    # Custom shell functions (worktree helpers, etc.)
│       ├── options.zsh      # Zsh options, vi-mode, completion styles
│       └── plugins.zsh      # Cross-platform plugin loading
├── dot-gnupg/           # GPG configuration (~/.gnupg/)
│   └── gpg-agent.conf   # GPG agent settings
├── hermes/              # Curated Hermes skills, scripts, and cron definitions
├── scripts/             # Repo-internal deployment scripts (never stowed)
│   ├── reconcile-agent-skills.sh  # Canonical skill curation + per-tool linking
│   └── setup-omarchy.sh           # Additive Omarchy entry point
├── tests/               # Integration tests for the deployment scripts
├── dot-gitconfig        # Git configuration (~/.gitconfig)
├── dot-gitconfig.local  # Git signing key (~/.gitconfig.local, not tracked)
├── dot-zshrc            # Zsh shell loader (~/.zshrc) - sources modular configs
├── dot-p10k.zsh         # Powerlevel10k theme (~/.p10k.zsh)
└── zsa-keyboard-layouts/  # ZSA keyboard firmware
```

## Managed Configurations

### Shell (Zsh)

- Powerlevel10k theme (no Oh My Zsh)
- Plugins: zsh-autosuggestions, zsh-syntax-highlighting
- Direnv integration for per-project environments
- **Modular configuration** in `~/.config/zsh/`:
  - `aliases.zsh` - Git, tools (bat/eza/nvim), Nix rebuild, navigation
  - `functions.zsh` - git and Obsidian helpers
  - `env.zsh` - EDITOR, GPG_TTY, paths, NODE_OPTIONS
  - `options.zsh` - setopt, vi-mode, completion styles
  - `plugins.zsh` - Cross-platform plugin loading, direnv

### Terminal (Alacritty)

- GPU-accelerated terminal
- Custom theme and opacity
- MesloLGS NF font for Powerlevel10k

### Workspace Manager (Herdr)

- Persistent local and remote terminal workspaces
- `herdr-studio` attaches to the Studio server
- `theme.name = "terminal"` makes the UI follow the host terminal's ANSI palette, so it stays native under Nightfly on macOS and under whichever Omarchy theme is live on Arch
- The tab bar's right edge is the **Glyph Rail**: one Nerd Font glyph per module, joined by a single Powerline soft divider (``) — Claude quota with its reset countdown, account-wide rolling 24-hour OpenRouter spend, host identity, and the clock

  ```
  󰭹 14% ↻3:08  󰓅 $3.95  󰒋 Studio  󰥔 09:11
  ```

- The spend figure is **account-wide**, not per-machine: it comes from OpenRouter's analytics API over a trailing 24-hour window, so Studio and the MacBook show the same number. It needs a [management key](https://openrouter.ai/settings/management-keys) — an ordinary `sk-or-v1` inference key is refused with `403 Only management keys can access analytics`:

  ```bash
  mkdir -p ~/.secrets/openrouter
  chmod 600 ~/.secrets/openrouter/management-key   # after writing the key into it
  ```

  Without that file the module prints nothing and the rail simply drops the entry.

- Host identity glyphs come from hardware/OS, not a hostname list: 󰒋 server (Mac Studio), 󰌢 laptop (MacBook), 󰣇 Arch/Omarchy. See `dot-config/herdr/host-label.sh`
- A Nerd Font is required for the rail to render (MesloLGS NF on macOS)

### Editor (Neovim)

- Lazy.nvim plugin manager
- Custom keybindings and plugins
- LSP and completion setup

### Version Control (Git)

- GPG signing enabled
- Global gitignore for `.envrc` and `.direnv/`
- Signing key stored in `~/.gitconfig.local` (not tracked in git)

### GPG

- GPG agent configuration for password caching
- pinentry-mac for GUI password prompts
- Cache TTL settings (10 min default, 2 hour max)

### Tools

- **direnv**: Automatic environment switching with nix-direnv for fast Nix shell caching

### AI / OpenCode

- Config lives in `dot-config/opencode/opencode.json` (tracked, stowed to `~/.config/opencode/`)
- The default local model provider connects directly to Studio Ollama over Tailscale at `http://100.121.238.48:11434/v1`
- The Ollama endpoint is available only inside the tailnet and does not require an API key
- `plugins/ollama-models.js` refreshes the provider's model inventory from Studio whenever OpenCode starts
- For repo-specific tweaks (extra docs, different permissions, etc.), create `.opencode/project.json` inside the repo

### AI / Hermes

- `hermes/` preserves authored local skills, automation scripts, and declarative cron definitions.
- `~/.hermes` remains a real local runtime directory; it is intentionally not stowed because it contains credentials, databases, sessions, logs, caches, and Matrix encryption state.
- `setup-platform-configs.sh` installs only manifest-listed assets on Studio, compiles native helpers locally, and reconciles named cron jobs through Hermes's API.
- Built-in Hermes skills come from the Hermes installation rather than being copied into dotfiles.
- See [`hermes/README.md`](hermes/README.md) for the managed boundary and restore process.

## Updating Configurations

After modifying any dotfiles:

1. Changes are automatically reflected (symlinks point to this repo)
2. For shell changes: `source ~/.zshrc`
3. For Herdr changes: `herdr server reload-config`

## Uninstalling

To remove symlinks:

```bash
cd ~/code/dotfiles
stow -D . --dotfiles --target $HOME
```

## Cross-Platform Compatibility

These dotfiles are designed to work on both macOS and NixOS with minimal platform-specific configuration.

### How It Works

**Shell configuration** (`dot-zshrc`) uses a "source if exists" pattern that checks multiple paths:

- macOS (Homebrew): `/opt/homebrew/share/...`
- NixOS (system): `/run/current-system/sw/share/...`
- Linux (standard): `/usr/share/...`

### Platform-Specific Settings

Some settings require platform-specific handling:

1. **SSH Keychain (macOS only)** - `dot-zshrc` conditionally aliases SSH to use macOS keychain support
2. **GPG Pinentry** - `dot-gnupg/gpg-agent.conf` defaults to macOS pinentry-mac; NixOS users should override locally
3. **Alacritty Window Decorations** - `setup-platform-configs.sh` automatically configures:
   - macOS: No decorations (clean look, no traffic lights)
   - Linux: Buttonless decorations (title bar for window management)

### NixOS-Specific Notes

On NixOS, you may want to create local overrides for:

```bash
# Override GPG pinentry for NixOS
echo "pinentry-program /run/current-system/sw/bin/pinentry-curses" > ~/.gnupg/gpg-agent.conf.local
```

Or manage these via your NixOS system configuration.

## Related Repositories

- [nix-configs](https://git.snowboardtechie.com/bryan/nix-configs) - Nix system configuration for both macOS and NixOS
  - macOS: nix-darwin with declarative Homebrew package management
  - NixOS: System configuration with flakes
  - Per-project development environment shells (via flakes + direnv)
  - System settings and package management

### 3 gits, one repo

This repository syncs to multiple remotes. The primary repository is at [git.snowboardtechie.com](https://git.snowboardtechie.com/bryan/dotfiles), with backups on [Codeberg](https://codeberg.org/SnowboardTechie/dotfiles) and [GitHub](https://github.com/bryan-thompsoncodes/dotfiles).

## Notes

- Stow uses relative symlinks by default
- The `--dotfiles` flag converts `dot-` prefix to `.` for files/folders
- ZSA keyboard layouts are stored but not symlinked
- **AGENTS.md is ignored by Stow** via `.stow-local-ignore` to prevent symlinking documentation to the home directory
- **Repository files are ignored**: `.git`, `README.md`, `.gitignore`, and `.stow-local-ignore` are excluded via `.stow-local-ignore` to prevent symlinking repository metadata
- **GPG config files require manual symlinking**: Since `~/.gnupg/` contains sensitive unmanaged files (private keys, trustdb, sockets), stow cannot symlink the entire directory. Individual config files must be manually symlinked after running stow.
- **Package management**: Dependencies managed via [nix-configs](https://github.com/bryan-thompsoncodes/nix-configs) for both macOS (nix-darwin) and NixOS (system configuration), or manually via Homebrew on macOS
