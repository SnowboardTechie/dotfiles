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

# Tmux plugin setup
echo ""
echo "Setting up Tmux plugins..."

TMUX_PLUGINS_DIR="$HOME/.tmux/plugins"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_PLUGINS_DIR="$REPO_ROOT/dot-tmux/plugins"

resolve_path() {
    perl -MCwd -le 'print Cwd::abs_path($ARGV[0])' "$1"
}

if [[ ! -f "$REPO_PLUGINS_DIR/tpm/tpm" ]]; then
    echo "  Initializing Tmux plugin submodules..."
    git -C "$REPO_ROOT" submodule update --init --recursive -- dot-tmux/plugins
fi

if [[ ! -f "$REPO_PLUGINS_DIR/tpm/tpm" ]]; then
    echo "  ERROR: TPM was not found at $REPO_PLUGINS_DIR/tpm/tpm."
    echo "  Ensure the repository and its submodules are intact before re-running this script."
    exit 1
fi

mkdir -p "$HOME/.tmux"
SOURCE_TARGET="$(resolve_path "$REPO_PLUGINS_DIR")"

if [[ -e "$TMUX_PLUGINS_DIR" ]]; then
    LINK_TARGET="$(resolve_path "$TMUX_PLUGINS_DIR")"
    if [[ "$LINK_TARGET" == "$SOURCE_TARGET" ]]; then
        echo "  ~/.tmux/plugins already resolves to the plugin submodules. Nothing to do."
    elif [[ -L "$TMUX_PLUGINS_DIR" ]]; then
        echo "  WARNING: ~/.tmux/plugins points to $LINK_TARGET (expected $SOURCE_TARGET)."
        echo "  Leaving the existing link untouched to avoid clobbering local data."
    elif [[ -d "$TMUX_PLUGINS_DIR" ]] &&
        [[ -z "$(find "$TMUX_PLUGINS_DIR" -mindepth 1 ! -type d -print -quit)" ]]; then
        find "$TMUX_PLUGINS_DIR" -depth -type d -exec rmdir {} \;
        ln -s "$REPO_PLUGINS_DIR" "$TMUX_PLUGINS_DIR"
        echo "  Replaced the empty local plugin tree with a link to the plugin submodules."
    else
        echo "  WARNING: Found existing data at ~/.tmux/plugins."
        echo "  Leaving it untouched to avoid clobbering locally managed plugins."
    fi
elif [[ -L "$TMUX_PLUGINS_DIR" ]]; then
    echo "  WARNING: ~/.tmux/plugins is a broken symlink."
    echo "  Leaving the existing link untouched to avoid clobbering local data."
else
    ln -s "$REPO_PLUGINS_DIR" "$TMUX_PLUGINS_DIR"
    echo "  Linked ~/.tmux/plugins -> $REPO_PLUGINS_DIR"
fi

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

# OpenCode API key from Keychain (macOS only)
OPENCODE_SECRET_FILE="$SECRETS_DIR/opencode-api-key"

if [[ ! -f "$OPENCODE_SECRET_FILE" ]]; then
    if [[ "$PLATFORM" == "macos" ]]; then
        echo "  Attempting to retrieve OpenCode API key from Keychain..."
        if API_KEY=$(security find-generic-password -a "$LOGNAME" -s ai.thompson.codes-openwebui -w 2>/dev/null); then
            echo "$API_KEY" > "$OPENCODE_SECRET_FILE"
            chmod 600 "$OPENCODE_SECRET_FILE"
            echo "  Wrote API key to $OPENCODE_SECRET_FILE from Keychain"
        else
            echo "  No Keychain entry found for ai.thompson.codes-openwebui"
            echo "  To add your API key to Keychain, run:"
            echo "    security add-generic-password -a \"\$LOGNAME\" -s ai.thompson.codes-openwebui -w '<api-key>'"
            echo "  Then re-run this script, or manually create $OPENCODE_SECRET_FILE"
        fi
    else
        echo "  Please create $OPENCODE_SECRET_FILE with your OpenCode API key"
    fi
else
    echo "  $OPENCODE_SECRET_FILE already exists"
fi

# OpenCode AGENTS.md (stow can't selectively ignore root vs nested AGENTS.md)
echo ""
echo "Setting up OpenCode AGENTS.md..."

OPENCODE_AGENTS_SRC="$REPO_ROOT/dot-config/opencode/AGENTS.md"
OPENCODE_AGENTS_DEST="$HOME/.config/opencode/AGENTS.md"

if [[ -L "$OPENCODE_AGENTS_DEST" ]]; then
    echo "  $OPENCODE_AGENTS_DEST already symlinked"
elif [[ -f "$OPENCODE_AGENTS_DEST" ]]; then
    echo "  WARNING: $OPENCODE_AGENTS_DEST exists as regular file, skipping"
else
    ln -s "$OPENCODE_AGENTS_SRC" "$OPENCODE_AGENTS_DEST"
    echo "  Linked $OPENCODE_AGENTS_DEST -> $OPENCODE_AGENTS_SRC"
fi

# Agent skills — shared pool in dot-agents/skills, curated per tool.
# See dot-agents/README.md for the per-tool rationale and the mirror of these lists.
echo ""
echo "Setting up agent skills..."

SKILLS_SRC="$(resolve_path "$REPO_ROOT/dot-agents/skills")"

# Common core shared by Claude, OpenCode, and Pi: dev/PR, PKM, and workflow learning.
COMMON_SKILLS=(ship worktrunk git-master update-pr-description pr-self-review agent-workspace
    vault-pkm vault-capture skill-retrospective obsidian)

PI_SKILLS=("${COMMON_SKILLS[@]}")

CLAUDE_SKILLS=("${COMMON_SKILLS[@]}"
    manual-merge issue-create issue-plan issue-work loop-issue sync-hold-branch
    adr-and-spec-coach conforming-tech-specs sprint-deliverable-update weekly-planning
    catalog-review dependency-review dependency-triage
    voice-bryan find-skills)

OPENCODE_SKILLS=("${COMMON_SKILLS[@]}"
    manual-merge issue-create issue-plan issue-work loop-issue
    adr-and-spec-coach conforming-tech-specs
    voice-bryan gamedev)

# Hermes keeps its bundled/local obsidian and vault-pkm implementations. Personal
# skills live in a dedicated category so the shared pool remains canonical while
# Hermes's curator and bundled-skill lifecycle stay separate.
HERMES_SKILLS=(
    ship worktrunk update-pr-description pr-self-review
    manual-merge issue-create issue-plan issue-work loop-issue
    vault-capture skill-retrospective adr-and-spec-coach voice-bryan
    dx-target dx-preview conforming-tech-specs
    catalog-review dependency-review dependency-triage sprint-deliverable-update
)

# Symlink a curated set of pool skills into a tool's skills dir.
# Idempotent: prunes pool-symlinks no longer wanted; never touches real dirs
# (e.g. Claude's plugin skills) or symlinks pointing outside the pool.
link_skills() {
    local label="$1" dest="$2" legacy_dest="$3"; shift 3
    local wanted=("$@")
    local existing name tgt w keep linked=0

    if [[ ! -d "$SKILLS_SRC" ]]; then
        echo "  ERROR: skill pool not found at $SKILLS_SRC"
        return
    fi

    # Replace known whole-directory layouts from before the per-skill pool.
    # A foreign destination symlink may be independently managed.
    if [[ -L "$dest" ]]; then
        tgt="$(resolve_path "$dest")"
        if [[ "$tgt" == "$SKILLS_SRC" || ( -n "$legacy_dest" && "$tgt" == "$legacy_dest" ) ]]; then
            rm "$dest"
        else
            echo "  WARNING: $label destination is a foreign symlink; skipping"
            return
        fi
    elif [[ -e "$dest" && ! -d "$dest" ]]; then
        echo "  WARNING: $label destination exists and is not a directory; skipping"
        return
    fi
    mkdir -p "$dest"

    # Prune stale links: only symlinks that resolve into the pool and are no
    # longer curated for this tool. Real dirs and foreign symlinks are left alone.
    for existing in "$dest"/*; do
        [[ -L "$existing" ]] || continue
        tgt="$(resolve_path "$existing")"
        case "$tgt" in
            "$SKILLS_SRC"/*)
                name="$(basename "$existing")"
                keep=0
                for w in "${wanted[@]}"; do
                    if [[ "$w" == "$name" ]]; then keep=1; break; fi
                done
                if [[ $keep -eq 0 ]]; then
                    rm "$existing"
                    echo "  pruned $label/$name (no longer curated)"
                fi
                ;;
        esac
    done

    # Link the curated skills as per-skill symlinks into the pool.
    for name in "${wanted[@]}"; do
        if [[ ! -d "$SKILLS_SRC/$name" ]]; then
            echo "  WARNING: skill '$name' not in pool, skipping"
            continue
        fi
        # Replace only links already owned by the pool. Preserve foreign links,
        # real directories, and files because they may be independently managed.
        if [[ -L "$dest/$name" ]]; then
            tgt="$(resolve_path "$dest/$name")"
            case "$tgt" in
                "$SKILLS_SRC"/*) ;;
                *)
                    echo "  WARNING: $label/$name is a foreign symlink; skipping"
                    continue
                    ;;
            esac
        elif [[ -e "$dest/$name" ]]; then
            echo "  WARNING: $label/$name exists and is not a symlink; skipping"
            continue
        fi
        ln -sfn "$SKILLS_SRC/$name" "$dest/$name"
        linked=$((linked + 1))
    done
    echo "  $label: $linked skills linked at $dest"
}

link_skills "Claude"   "$HOME/.claude/skills"          "$REPO_ROOT/dot-claude/skills"          "${CLAUDE_SKILLS[@]}"
link_skills "OpenCode" "$HOME/.config/opencode/skills" "$REPO_ROOT/dot-config/opencode/skills" "${OPENCODE_SKILLS[@]}"
link_skills "Pi"       "$HOME/.pi/agent/skills"        ""                                     "${PI_SKILLS[@]}"
link_skills "Hermes"   "$HOME/.hermes/skills/personal" ""                                     "${HERMES_SKILLS[@]}"

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
echo "  - Tmux: Run 'tmux source-file ~/.tmux.conf' if tmux is already running"

