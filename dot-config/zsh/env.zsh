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

# Keep interactive gws calls on the same headless-safe credential backend as
# Hermes launchd jobs. Mixing this with the macOS keyring backend can make gws
# delete credentials.enc after a decryption mismatch (upstream issue #886).
export GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND="${GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND:-file}"

# PostgreSQL - Add libpq binaries to PATH (macOS Homebrew only, NixOS handles via system packages)
if [[ -d /opt/homebrew/opt/libpq/bin ]]; then
  export PATH="/opt/homebrew/opt/libpq/bin:$PATH"
fi
