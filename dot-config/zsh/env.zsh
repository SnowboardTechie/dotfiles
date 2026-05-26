# Environment variables

# Editor configuration
export EDITOR="nvim"
export VISUAL="nvim"
export PAGER="less"

# GPG configuration for commit signing
export GPG_TTY=$(tty)

# Directory paths (can be overridden by setting before sourcing)
export NIX_CONFIG_DIR="${NIX_CONFIG_DIR:-$HOME/code/nix-configs}"
export NOTES_VAULT_PATH="${NOTES_VAULT_PATH:-$HOME/notes}"

# Node
export NODE_OPTIONS="--max-old-space-size=4096"

# PostgreSQL - Add libpq binaries to PATH (macOS Homebrew only, NixOS handles via system packages)
if [[ -d /opt/homebrew/opt/libpq/bin ]]; then
  export PATH="/opt/homebrew/opt/libpq/bin:$PATH"
fi
