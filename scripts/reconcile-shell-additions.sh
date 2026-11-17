#!/usr/bin/env bash
# reconcile-shell-additions.sh — ensure the machine's own shell loads the repository's
# portable aliases (dot-config/shell/aliases.sh) additively.
#
# On Omarchy the login shell is Omarchy-owned bash; its stock ~/.bashrc ends
# with a designated "add your own exports, aliases, and functions" section.
# This reconciler appends exactly one marked, guarded source line there. It
# never creates, replaces, or reorders ~/.bashrc, and removing the line by
# hand is the complete uninstall.
#
# Fully-owned zsh machines do not need this: dot-config/zsh/aliases.zsh
# sources the shared file itself.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

usage() {
    cat <<'EOF'
Usage: reconcile-shell-additions.sh (--check | --apply)

  --check   Report whether ~/.bashrc already loads the shared aliases.
            Never mutates the filesystem.
  --apply   Append one marked source line to an existing ~/.bashrc if it is
            not already present. Never creates or rewrites ~/.bashrc.
EOF
}

MODE=""
if [[ $# -eq 1 ]]; then
    case "$1" in
        --check) MODE="check" ;;
        --apply) MODE="apply" ;;
        -h|--help) usage; exit 0 ;;
    esac
fi
if [[ -z "$MODE" ]]; then
    if [[ $# -gt 0 ]]; then
        echo "ERROR: expected exactly one of --check or --apply, got: $*" >&2
    fi
    usage >&2
    exit 2
fi

ALIASES_SRC="$REPO_ROOT/dot-config/shell/aliases.sh"
BASHRC="$HOME/.bashrc"
MARKER="# dotfiles shell additions (managed by scripts/reconcile-shell-additions.sh)"
SOURCE_LINE="[[ -f \"$ALIASES_SRC\" ]] && source \"$ALIASES_SRC\""

if [[ ! -f "$ALIASES_SRC" ]]; then
    echo "ERROR: shared aliases not found at $ALIASES_SRC" >&2
    exit 1
fi

echo "Shell additions ($MODE) for $BASHRC"

if [[ ! -f "$BASHRC" ]]; then
    echo "  WARNING: $BASHRC does not exist; nothing to do (this reconciler never creates it)"
    echo "  summary: 0 append, 0 ok, 1 skipped"
    exit 0
fi

if grep -qF "dot-config/shell/aliases.sh" "$BASHRC"; then
    if grep -qxF "$SOURCE_LINE" "$BASHRC"; then
        echo "  ok: managed source line already present"
        echo "  summary: 0 append, 1 ok, 0 skipped"
    else
        echo "  WARNING: $BASHRC references dot-config/shell/aliases.sh with an unexpected line;"
        echo "  leaving it untouched — reconcile manually if the repo has moved"
        echo "  summary: 0 append, 0 ok, 1 skipped"
    fi
    exit 0
fi

if [[ "$MODE" == "check" ]]; then
    echo "  would append: marked source line for $ALIASES_SRC"
else
    printf '\n%s\n%s\n' "$MARKER" "$SOURCE_LINE" >> "$BASHRC"
    echo "  appended: marked source line for $ALIASES_SRC"
fi
echo "  summary: 1 append, 0 ok, 0 skipped"

if [[ "$MODE" == "check" ]]; then
    echo "Check complete — no changes were made."
fi
