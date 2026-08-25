#!/usr/bin/env bash
# setup-omarchy.sh — conservative, additive dotfiles setup for Omarchy hosts.
#
# Omarchy owns its own environment (shell, terminal, editor, Git, GPG,
# Zed, and tool settings). This entry point deploys only additive personal
# assets — currently the curated agent-skill links — and never runs Stow,
# installs packages, or uses elevated privileges.
#
# Future additive reconcilers get appended to the RECONCILERS list below;
# application-specific mutation logic never lives in this script itself.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    cat <<'EOF'
Usage: setup-omarchy.sh (--check | --apply) [--force]

  --check   Report what --apply would change. Never mutates the filesystem.
  --apply   Perform the additive setup (per-tool agent-skill links only).
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

RECONCILERS=(
    "$SCRIPT_DIR/reconcile-agent-skills.sh"
    "$SCRIPT_DIR/reconcile-shell-additions.sh"
    "$SCRIPT_DIR/reconcile-hindsight.sh"
)

for reconciler in "${RECONCILERS[@]}"; do
    "$reconciler" "--$MODE"
done

cat <<'EOF'

Ownership summary:
  This setup is additive. It links curated personal agent skills into
  ~/.claude/skills, ~/.config/opencode/skills, ~/.pi/agent/skills, and
  ~/.hermes/skills/personal, and appends one marked source line to an
  existing ~/.bashrc (Omarchy's designated personal-additions section)
  loading portable aliases from dot-config/shell/aliases.sh, and wires the
  Hindsight memory client (staged runtime in ~/.hindsight, merged Claude
  hooks / OpenCode plugin entry, token from ~/.secrets/hindsight) — nothing
  else.

  Intentionally left untouched (Omarchy owns these):
    - login shell selection and Omarchy's bash defaults
    - terminal configuration (foot/alacritty)
    - ~/.config/nvim
    - Git configuration (~/.config/git, ~/.gitconfig)
    - ~/.gnupg
    - Zed, OpenCode, and Claude settings files
    - anything under /usr/share/omarchy

  No Stow operation, package installation, or privileged command was run.
EOF
