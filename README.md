# Dotfiles

Personal development environment configuration, managed with GNU Stow.

Cross-platform compatible with macOS and NixOS.

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
   brew install bat eza fzf direnv tmux tpm
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
  tmux
  tmuxPlugins.tpm
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

### Fresh System Installation

From this repository's root directory:

```bash
stow . --dotfiles --target $HOME
./setup-platform-configs.sh
```

This will symlink all dotfiles to your home directory, configure platform-specific overrides (Alacritty), install tmux plugins, and set up the secrets directory (populating the OpenCode API key from Keychain on macOS).

**Additional Manual Step:**

**GPG configuration** - Link GPG agent config:

```bash
ln -s ~/code/dotfiles/dot-gnupg/gpg-agent.conf ~/.gnupg/gpg-agent.conf
```

If tmux is already running, reload the config to apply the newly installed plugins:

```bash
tmux source-file ~/.tmux.conf
```

### Initial Migration (Existing Dotfiles)

If you're setting up this repo for the first time and want to migrate existing dotfiles:

```bash
stow . --adopt --dotfiles --target $HOME
```

The `--adopt` flag will move any existing files in your home directory into the dotfiles repo. After adoption, review the changes and commit only the files you want to manage.

**Warning**: Be careful with `--adopt` as it will move existing files into the repo. Review changes before committing.

## Structure

```text
dotfiles/
├── dot-config/          # XDG config directory (~/.config/)
│   ├── alacritty/       # Terminal emulator
│   ├── direnv/          # Direnv configuration with nix-direnv
│   ├── nvim/            # Neovim configuration (Lazy.nvim)
│   ├── opencode/        # OpenCode AI assistant
│   │   ├── AGENTS.md            # Global agent instructions
│   │   ├── oh-my-openagent.json  # OhMyOpenAgent agent model assignments
│   │   └── opencode.json        # Provider config (uses {file:...} for API key)
│   └── zsh/             # Modular zsh configuration (~/.config/zsh/)
│       ├── aliases.zsh      # All aliases (git, tools, nix, navigation)
│       ├── env.zsh          # Environment variables
│       ├── functions.zsh    # Custom shell functions (worktree helpers, etc.)
│       ├── options.zsh      # Zsh options, vi-mode, completion styles
│       └── plugins.zsh      # Cross-platform plugin loading
├── dot-gnupg/           # GPG configuration (~/.gnupg/)
│   └── gpg-agent.conf   # GPG agent settings
├── dot-tmux/            # Tmux session templates (~/.tmux/)
│   ├── code-editor.sh   # Editor session launched by the `code` function
│   └── second-brain.sh  # Personal notes session
├── dot-gitconfig        # Git configuration (~/.gitconfig)
├── dot-gitconfig.local  # Git signing key (~/.gitconfig.local, not tracked)
├── dot-zshrc            # Zsh shell loader (~/.zshrc) - sources modular configs
├── dot-tmux.conf        # Tmux terminal multiplexer (~/.tmux.conf)
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
  - `functions.zsh` - git helpers, worktree (`wcode`) helper, `code` launcher
  - `env.zsh` - EDITOR, GPG_TTY, paths, NODE_OPTIONS
  - `options.zsh` - setopt, vi-mode, completion styles
  - `plugins.zsh` - Cross-platform plugin loading, direnv

### Terminal (Alacritty)

- GPU-accelerated terminal
- Custom theme and opacity
- MesloLGS NF font for Powerlevel10k

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
- **tmux**: Terminal multiplexer with vim keybindings

### AI / OpenCode

- Config lives in `dot-config/opencode/opencode.json` (tracked, stowed to `~/.config/opencode/`)
- API key is stored in `~/.secrets/opencode-api-key` (outside repo, never tracked)
- Config uses `{file:~/.secrets/opencode-api-key}` reference for safe stowing
- `setup-platform-configs.sh` creates `~/.secrets/` and populates the key from Keychain (macOS)
- On macOS, store your API key in Keychain:
  `security add-generic-password -a "$LOGNAME" -s ai.thompson.codes-openwebui -w '<api-key>'`
- On Linux, manually create `~/.secrets/opencode-api-key` with your API key
- For repo-specific tweaks (extra docs, different permissions, etc.), create `.opencode/project.json` inside the repo

### Tmux Session Templates

Pre-configured tmux sessions for common development workflows, in `dot-tmux/`:

- `code-editor.sh` — editor session launched by the `code` shell function
- `second-brain.sh` — personal notes session (`2nd-brain` alias)

## Updating Configurations

After modifying any dotfiles:

1. Changes are automatically reflected (symlinks point to this repo)
2. For shell changes: `source ~/.zshrc`
3. For tmux changes: `tmux source-file ~/.tmux.conf` or `prefix + r`

## Uninstalling

To remove symlinks:

```bash
cd ~/code/dotfiles
stow -D . --dotfiles --target $HOME
```

## Cross-Platform Compatibility

These dotfiles are designed to work on both macOS and NixOS with minimal platform-specific configuration.

### How It Works

**Shell configurations** (`dot-zshrc`, `dot-tmux.conf`) use a "source if exists" pattern that checks multiple paths:

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
