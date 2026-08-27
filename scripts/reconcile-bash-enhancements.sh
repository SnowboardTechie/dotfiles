#!/usr/bin/env bash
# reconcile-bash-enhancements.sh — add optional interactive Bash behavior to
# Omarchy without replacing or reordering its ~/.bashrc.
#
# Ble.sh provides inline history suggestions and syntax highlighting. The
# guarded source line is safe before the package is installed and becomes
# active in fresh interactive shells once /usr/share/blesh/ble.sh exists.

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: reconcile-bash-enhancements.sh (--check | --apply)

  --check   Report whether ~/.bashrc already loads Ble.sh. Never mutates.
  --apply   Append one marked, guarded Ble.sh source line when absent.
            Never creates or rewrites ~/.bashrc.
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

BASHRC="$HOME/.bashrc"
MARKER="# Bash enhancements (managed by scripts/reconcile-bash-enhancements.sh)"
BLESH_LINE='if [[ $- == *i* && -r /usr/share/blesh/ble.sh ]]; then source /usr/share/blesh/ble.sh; fi'

printf 'Bash enhancements (%s) for %s\n' "$MODE" "$BASHRC"

if [[ ! -f "$BASHRC" ]]; then
    echo "  WARNING: $BASHRC does not exist; nothing to do (this reconciler never creates it)"
    echo "  summary: 0 append, 0 ok, 1 skipped"
    exit 0
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
    exit 0
fi

if [[ "$MODE" == "check" ]]; then
    echo "  would append: guarded Ble.sh source line"
else
    printf '\n%s\n%s\n' "$MARKER" "$BLESH_LINE" >> "$BASHRC"
    echo "  appended: guarded Ble.sh source line"
fi
echo "  summary: 1 append, 0 ok, 0 skipped"

if [[ "$MODE" == "check" ]]; then
    echo "Check complete — no changes were made."
fi
