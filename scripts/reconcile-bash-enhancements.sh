#!/usr/bin/env bash
# reconcile-bash-enhancements.sh — add optional interactive Bash behavior to
# Omarchy without replacing or reordering its ~/.bashrc.
#
# Ble.sh provides inline history suggestions and syntax highlighting. The
# guarded source line is safe before the package is installed and becomes
# active in fresh interactive shells once /usr/share/blesh/ble.sh exists.
# It also links the repository's ble.sh settings to ~/.config/blesh/init.sh
# (ble.sh's user config), leaving any existing file of Bryan's untouched.

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: reconcile-bash-enhancements.sh (--check | --apply)

  --check   Report whether ~/.bashrc already loads Ble.sh and whether the
            Ble.sh settings link is in place. Never mutates.
  --apply   Append one marked, guarded Ble.sh source line when absent, and
            link ~/.config/blesh/init.sh to the repository's settings when
            absent. Never creates or rewrites ~/.bashrc, never replaces an
            existing settings file.
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

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASHRC="$HOME/.bashrc"
BLESH_RC_SOURCE="$REPO_ROOT/dot-config/blesh/init.sh"
BLESH_RC_TARGET="${XDG_CONFIG_HOME:-$HOME/.config}/blesh/init.sh"
MARKER="# Bash enhancements (managed by scripts/reconcile-bash-enhancements.sh)"
BLESH_LINE='if [[ $- == *i* && -r /usr/share/blesh/ble.sh ]]; then source /usr/share/blesh/ble.sh; fi'

printf 'Bash enhancements (%s) for %s\n' "$MODE" "$BASHRC"

reconcile_bashrc() {
    if [[ ! -f "$BASHRC" ]]; then
        echo "  WARNING: $BASHRC does not exist; nothing to do (this reconciler never creates it)"
        echo "  summary: 0 append, 0 ok, 1 skipped"
        return 0
    fi

    if grep -qF '/usr/share/blesh/ble.sh' "$BASHRC"; then
        if grep -qxF "$BLESH_LINE" "$BASHRC"; then
            echo "  ok: guarded Ble.sh source line already present"
            echo "  summary: 0 append, 1 ok, 0 skipped"
        else
            echo "  WARNING: $BASHRC references /usr/share/blesh/ble.sh with an unexpected line;"
            echo "  leaving it untouched — reconcile manually if the integration differs"
            echo "  summary: 0 append, 0 ok, 1 skipped"
        fi
        return 0
    fi

    if [[ "$MODE" == "check" ]]; then
        echo "  would append: guarded Ble.sh source line"
    else
        printf '\n%s\n%s\n' "$MARKER" "$BLESH_LINE" >> "$BASHRC"
        echo "  appended: guarded Ble.sh source line"
    fi
    echo "  summary: 1 append, 0 ok, 0 skipped"
}

# ~/.config is a real directory on Omarchy but a folded symlink to dot-config/
# on Stow hosts, where the target already resolves to the repository file.
reconcile_blesh_rc() {
    if [[ "$BLESH_RC_TARGET" -ef "$BLESH_RC_SOURCE" ]]; then
        echo "  ok: Ble.sh settings already linked ($BLESH_RC_TARGET)"
    elif [[ -e "$BLESH_RC_TARGET" || -L "$BLESH_RC_TARGET" ]]; then
        echo "  WARNING: $BLESH_RC_TARGET exists and is not this repository's file;"
        echo "  leaving it untouched — merge dot-config/blesh/init.sh into it manually"
    elif [[ -e "$HOME/.blerc" ]]; then
        echo "  WARNING: ~/.blerc exists and takes precedence over $BLESH_RC_TARGET;"
        echo "  leaving both untouched — merge dot-config/blesh/init.sh into ~/.blerc manually"
    elif [[ "$MODE" == "check" ]]; then
        echo "  would link: $BLESH_RC_TARGET -> $BLESH_RC_SOURCE"
    else
        mkdir -p "$(dirname "$BLESH_RC_TARGET")"
        ln -s "$BLESH_RC_SOURCE" "$BLESH_RC_TARGET"
        echo "  linked: $BLESH_RC_TARGET -> $BLESH_RC_SOURCE"
    fi
}

reconcile_bashrc
reconcile_blesh_rc

if [[ "$MODE" == "check" ]]; then
    echo "Check complete — no changes were made."
fi
