#!/usr/bin/env bash
# setup-omarchy.sh — conservative, additive dotfiles setup for Omarchy hosts.
#
# Omarchy owns its own environment (shell, terminal, editor, Git, GPG,
# Zed, and tool settings). This entry point deploys only additive personal
# assets — curated skills, portable aliases, guarded Bash enhancements,
# personal shell plugins, Pi's extensions and Claude Code provider, and retired
# agent-memory cleanup — and never runs Stow, installs system packages, or uses
# elevated privileges.
#
# Future additive reconcilers get appended to the RECONCILERS list below;
# application-specific mutation logic never lives in this script itself.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    cat <<'EOF'
Usage: setup-omarchy.sh (--check | --apply) [--force]

  --check   Report what --apply would change. Never mutates the filesystem.
  --apply   Perform the additive setup through the registered reconcilers.
  --force   Proceed even if this host does not identify as Omarchy.

Never run 'stow .' or 'stow --adopt' against your home on an Omarchy host;
this script is the supported installation path there.
EOF
}

MODE=""
FORCE=0
for arg in "$@"; do
    case "$arg" in
        --check|--apply)
            if [[ -n "$MODE" ]]; then
                echo "ERROR: expected exactly one of --check or --apply" >&2
                usage >&2
                exit 2
            fi
            MODE="${arg#--}"
            ;;
        --force) FORCE=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown argument: $arg" >&2; usage >&2; exit 2 ;;
    esac
done
if [[ -z "$MODE" ]]; then
    usage >&2
    exit 2
fi

is_omarchy() {
    if [[ -r /etc/os-release ]] && grep -q '^ID=omarchy$' /etc/os-release; then
        return 0
    fi
    command -v omarchy >/dev/null 2>&1
}

if ! is_omarchy; then
    if [[ $FORCE -eq 1 ]]; then
        echo "WARNING: host does not identify as Omarchy; continuing (--force)."
    else
        echo "ERROR: this host does not identify as Omarchy (/etc/os-release ID" >&2
        echo "or the omarchy command). Use --force to run anyway, or use the" >&2
        echo "documented macOS/NixOS installation instead." >&2
        exit 1
    fi
fi

echo "Omarchy additive setup ($MODE)"

# Omarchy hosts don't run Hermes; set RECONCILE_HERMES_SKILLS=1 to link its skills anyway.
export RECONCILE_HERMES_SKILLS="${RECONCILE_HERMES_SKILLS:-0}"

RECONCILERS=(
    "$SCRIPT_DIR/reconcile-agent-skills.sh"
    "$SCRIPT_DIR/reconcile-shell-additions.sh"
    "$SCRIPT_DIR/reconcile-bash-enhancements.sh"
    "$SCRIPT_DIR/reconcile-omarchy-auto-suspend.sh"
    "$SCRIPT_DIR/reconcile-omarchy-clipboard-bridge.sh"
    "$SCRIPT_DIR/reconcile-pi-extensions.sh"
    "$SCRIPT_DIR/reconcile-pi-claude-code.sh"
    "$SCRIPT_DIR/retire-agent-memory.py"
)

for reconciler in "${RECONCILERS[@]}"; do
    "$reconciler" "--$MODE"
done

cat <<'EOF'

Ownership summary:
  This setup is additive. It links curated personal agent skills into
  ~/.claude/skills, ~/.config/opencode/skills, and ~/.pi/agent/skills
  (Hermes only with RECONCILE_HERMES_SKILLS=1), and appends one marked source line to an
  existing ~/.bashrc (Omarchy's designated personal-additions section)
  loading portable aliases from dot-config/shell/aliases.sh plus an optional,
  guarded Ble.sh integration for inline suggestions/highlighting, enables a
  repository-owned 45-minute auto-suspend shell service, runs a clipboard
  bridge to a Mac as a user service when ~/.config/clipboard-bridge/host names
  one, links the repository's
  Pi extensions and global AGENTS.md into ~/.pi/agent, installs the
  pi-claude-code Pi package and makes claude-code Pi's default provider when
  it was unset or anthropic (so Claude turns count against the plan, not
  extra usage), and removes only the
  retired Hindsight / context-mode / claude-mem entries from Claude, Pi, and
  OpenCode JSON settings (native memory and data untouched) — nothing else.

  Intentionally left untouched (Omarchy owns these):
    - login shell selection and Omarchy's bash defaults
    - terminal configuration (foot/alacritty)
    - ~/.config/nvim
    - Git configuration (~/.config/git, ~/.gitconfig)
    - ~/.gnupg
    - Zed, OpenCode, and Claude settings files (beyond that retired-entry cleanup)
    - anything under /usr/share/omarchy

  No Stow operation, system package installation, or privileged command was run.
EOF
