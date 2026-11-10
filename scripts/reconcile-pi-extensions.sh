#!/usr/bin/env bash
# Link repository-owned Pi extensions into ~/.pi/agent/extensions.
# Usage: reconcile-pi-extensions.sh --check | --apply
# Never replaces a foreign file or symlink. rex-agent-sessions.ts is owned by
# reconcile-rex-agent-sessions.sh and is not listed here.
set -e

MODE="${1:-}"
[[ "$MODE" == "--check" || "$MODE" == "--apply" ]] || { echo "Usage: $0 --check|--apply" >&2; exit 2; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_DIR="${PI_EXTENSIONS_HOME:-$HOME}"
PI_EXTENSIONS=(
    pi-seat.ts
)
drift=0

for ext in "${PI_EXTENSIONS[@]}"; do
    src="$REPO_ROOT/dot-pi/agent/extensions/$ext"
    dest="$HOME_DIR/.pi/agent/extensions/$ext"
    if [[ -L "$dest" && "$(readlink "$dest")" == "$src" ]]; then
        echo "  OK   $dest"
    elif [[ -e "$dest" || -L "$dest" ]]; then
        echo "  WARNING: $dest is not managed by this repository, skipping"
    elif [[ "$MODE" == "--apply" ]]; then
        mkdir -p "$(dirname "$dest")"
        ln -s "$src" "$dest"
        echo "  Linked $dest"
    else
        echo "  MISSING $dest"; drift=1
    fi
done

exit $drift
