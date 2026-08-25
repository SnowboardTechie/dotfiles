#!/usr/bin/env bash
# Platform-specific dotfile configuration setup
# This script handles platform-specific overrides for dotfiles managed with stow

set -e

# Detect platform
if [[ "$OSTYPE" == "darwin"* ]]; then
    PLATFORM="macos"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    PLATFORM="linux"
else
    echo "Unknown platform: $OSTYPE"
    exit 1
fi

echo "Detected platform: $PLATFORM"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

resolve_path() {
    perl -MCwd -le 'print Cwd::abs_path($ARGV[0])' "$1"
}

# Alacritty configuration
echo ""
echo "Setting up Alacritty for $PLATFORM..."

ALACRITTY_CONFIG="$HOME/.config/alacritty/alacritty.toml"

if [[ "$PLATFORM" == "linux" ]]; then
    # Create symlink to Linux-specific config
    ln -sf alacritty-linux.toml "$ALACRITTY_CONFIG"
    echo "  Linked alacritty.toml -> alacritty-linux.toml"
    
elif [[ "$PLATFORM" == "macos" ]]; then
    # Create symlink to macOS-specific config
    ln -sf alacritty-macos.toml "$ALACRITTY_CONFIG"
    echo "  Linked alacritty.toml -> alacritty-macos.toml"
fi

# Retired tmux links from earlier stow deployments
echo ""
echo "Removing retired tmux links..."

remove_retired_tmux_link() {
    local link_path="$1"
    local link_target

    [[ -L "$link_path" ]] || return 0
    link_target=$(readlink "$link_path")
    case "$link_target" in
        *dotfiles*/dot-tmux.conf|*dotfiles*/dot-tmux|*dotfiles*/dot-tmux/*)
            rm "$link_path"
            echo "  Removed $link_path"
            ;;
        *)
            echo "  WARNING: $link_path is not managed by this repository, skipping"
            ;;
    esac
}

remove_retired_tmux_link "$HOME/.tmux.conf"
for retired_path in \
    "$HOME/.tmux/claude-status.sh" \
    "$HOME/.tmux/claude-usage.sh" \
    "$HOME/.tmux/code-editor.sh" \
    "$HOME/.tmux/pair-agents.sh" \
    "$HOME/.tmux/second-brain.sh" \
    "$HOME/.tmux/token-usage-cost.py" \
    "$HOME/.tmux/plugins" \
    "$HOME/.tmux"; do
    remove_retired_tmux_link "$retired_path"
done

# Secrets directory setup
echo ""
echo "Setting up secrets directory..."

SECRETS_DIR="$HOME/.secrets"

if [[ ! -d "$SECRETS_DIR" ]]; then
    mkdir -p "$SECRETS_DIR"
    chmod 700 "$SECRETS_DIR"
    echo "  Created $SECRETS_DIR with restricted permissions (700)"
else
    echo "  $SECRETS_DIR already exists"
fi

# Personal weather location (kept out of the public dotfiles repository)
PERSONAL_WEATHER_LOCATION_FILE="$SECRETS_DIR/personal-weather-location"

if [[ ! -f "$PERSONAL_WEATHER_LOCATION_FILE" ]]; then
    echo "  Please create $PERSONAL_WEATHER_LOCATION_FILE with a ZIP code or city name"
else
    chmod 600 "$PERSONAL_WEATHER_LOCATION_FILE"
    echo "  $PERSONAL_WEATHER_LOCATION_FILE already exists"
fi

# OpenCode AGENTS.md (stow can't selectively ignore root vs nested AGENTS.md)
echo ""
echo "Setting up OpenCode AGENTS.md..."

OPENCODE_AGENTS_SRC="$REPO_ROOT/dot-config/opencode/AGENTS.md"
OPENCODE_AGENTS_DEST="$HOME/.config/opencode/AGENTS.md"

if [[ -e "$OPENCODE_AGENTS_DEST" ]] &&
    [[ "$(resolve_path "$OPENCODE_AGENTS_DEST")" == "$(resolve_path "$OPENCODE_AGENTS_SRC")" ]]; then
    echo "  $OPENCODE_AGENTS_DEST already resolves to the repository source"
elif [[ -L "$OPENCODE_AGENTS_DEST" ]]; then
    echo "  WARNING: $OPENCODE_AGENTS_DEST is a foreign or broken symlink, skipping"
elif [[ -f "$OPENCODE_AGENTS_DEST" ]]; then
    if cmp -s "$OPENCODE_AGENTS_SRC" "$OPENCODE_AGENTS_DEST"; then
        rm "$OPENCODE_AGENTS_DEST"
        ln -s "$OPENCODE_AGENTS_SRC" "$OPENCODE_AGENTS_DEST"
        echo "  Replaced identical regular file with link to $OPENCODE_AGENTS_SRC"
    else
        echo "  WARNING: $OPENCODE_AGENTS_DEST differs from the source, skipping"
    fi
elif [[ -e "$OPENCODE_AGENTS_DEST" ]]; then
    echo "  WARNING: $OPENCODE_AGENTS_DEST is not a regular file, skipping"
else
    ln -s "$OPENCODE_AGENTS_SRC" "$OPENCODE_AGENTS_DEST"
    echo "  Linked $OPENCODE_AGENTS_DEST -> $OPENCODE_AGENTS_SRC"
fi

# Agent skills — shared pool in dot-agents/skills, curated per tool.
# Curation arrays and ownership logic live in scripts/reconcile-agent-skills.sh.
echo ""
echo "Setting up agent skills..."

"$REPO_ROOT/scripts/reconcile-agent-skills.sh" --apply

# Git-backed Hermes-local assets are installed explicitly rather than stowing
# ~/.hermes, which also contains credentials, databases, logs, and live state.
echo ""
echo "Setting up Hermes managed assets..."

HERMES_INSTALLER="$REPO_ROOT/hermes/install.py"
if [[ "$PLATFORM" != "macos" ]]; then
    echo "  Skipped (the managed Hermes runtime is on Studio)"
elif [[ ! -f "$HERMES_INSTALLER" ]]; then
    echo "  ERROR: Hermes installer not found at $HERMES_INSTALLER"
elif [[ "$(scutil --get LocalHostName 2>/dev/null || hostname -s)" != "Bryans-Mac-Studio" ]]; then
    echo "  Skipped (Studio-only assets)"
else
    python3 "$HERMES_INSTALLER" --adopt-identical
fi

echo ""
echo "Platform-specific configuration complete!"
echo ""
echo "Note: Run this script after 'stow . --dotfiles --target \$HOME'"
echo ""
echo "Additional manual steps:"
echo "  - GPG: ln -s ~/code/dotfiles/dot-gnupg/gpg-agent.conf ~/.gnupg/gpg-agent.conf"
