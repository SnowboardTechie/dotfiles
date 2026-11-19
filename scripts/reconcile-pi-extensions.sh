#!/usr/bin/env bash
# Link repository-owned Pi files into ~/.pi/agent: the extensions and the
# global AGENTS.md instructions.
# Usage: reconcile-pi-extensions.sh --check | --apply
# Never replaces a foreign file or symlink. rex-agent-sessions.ts is owned by
# reconcile-rex-agent-sessions.sh and is not listed here. --check only reports
# and exits 0, like the other reconcilers setup-omarchy.sh runs.
# Files this repository renamed leave a link under the old name; --apply removes
# such a link only when it points at this repository's old path.
set -e

MODE="${1:-}"
[[ "$MODE" == "--check" || "$MODE" == "--apply" ]] || { echo "Usage: $0 --check|--apply" >&2; exit 2; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_DIR="${PI_EXTENSIONS_HOME:-$HOME}"
echo "Pi extensions (${MODE#--}) for $HOME_DIR/.pi/agent"
# Paths relative to dot-pi/agent and ~/.pi/agent.
PI_FILES=(
    AGENTS.md
    extensions/background-agent-watch.ts
    extensions/pi-rex.ts
    extensions/pi-split.ts
    extensions/pi-subscription.ts
    extensions/stream-rules.ts
)
# Old names, relative to dot-pi/agent and ~/.pi/agent, of files renamed above.
RENAMED_FROM=(
    extensions/pi-seat.ts
    extensions/worker-watch.ts
)

for rel in "${PI_FILES[@]}"; do
    src="$REPO_ROOT/dot-pi/agent/$rel"
    dest="$HOME_DIR/.pi/agent/$rel"
    if [[ -L "$dest" && "$(readlink "$dest")" == "$src" ]]; then
        echo "  OK   $dest"
    elif [[ -e "$dest" || -L "$dest" ]]; then
        echo "  WARNING: $dest is foreign (this repository did not make it), skipping"
    elif [[ "$MODE" == "--apply" ]]; then
        mkdir -p "$(dirname "$dest")"
        ln -s "$src" "$dest"
        echo "  Linked $dest"
    else
        echo "  MISSING $dest"
    fi
done

# True when link $1 names file $2 of this repository: the same file name in the
# same directory once both directories are resolved, so a link made through
# another path to this checkout (such as ~/code/dotfiles) still counts.
points_at_repo_file() {
    local target dir
    target="$(readlink "$1")"
    [[ "$(basename "$target")" == "$(basename "$2")" ]] || return 1
    dir="$(cd "$(dirname "$target")" 2>/dev/null && pwd -P)" || return 1
    [[ "$dir" == "$(cd "$(dirname "$2")" && pwd -P)" ]]
}

for rel in "${RENAMED_FROM[@]}"; do
    old="$REPO_ROOT/dot-pi/agent/$rel"
    dest="$HOME_DIR/.pi/agent/$rel"
    if [[ -L "$dest" ]] && points_at_repo_file "$dest" "$old"; then
        if [[ "$MODE" == "--apply" ]]; then
            rm "$dest"
            echo "  Removed stale $dest"
        else
            echo "  STALE $dest"
        fi
    elif [[ -e "$dest" || -L "$dest" ]]; then
        echo "  WARNING: $dest is foreign (this repository did not make it), skipping"
    fi
done

exit 0
