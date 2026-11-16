#!/usr/bin/env bash
# Link the repository's agent commands (dot-agents/bin/*) into ~/.local/bin,
# which is on PATH in Pi's tool shells.
# Usage: reconcile-agent-commands.sh --check | --apply
#
# A missing link is created. A link that already resolves to the command here
# is left as it is. A stale link of this repository's own, a dangling one whose
# target ends in dot-agents/bin/<same name> (a removed worktree, a moved
# checkout), is repointed here. A file, or a link to anything else, including a
# live link into another checkout, is never replaced: it is reported and the
# script exits 1, in both modes.
set -euo pipefail

MODE="${1:-}"
[[ "$MODE" == "--check" || "$MODE" == "--apply" ]] || { echo "Usage: $0 --check|--apply" >&2; exit 2; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
SRC_DIR="$REPO_ROOT/dot-agents/bin"
DEST_DIR="$HOME/.local/bin"
conflicts=0

echo "Agent commands (${MODE#--}) for $DEST_DIR"

for src in "$SRC_DIR"/*; do
    [[ -f "$src" && -x "$src" ]] || continue
    name="$(basename "$src")"
    dest="$DEST_DIR/$name"
    if [[ -L "$dest" ]]; then
        current="$(readlink "$dest")"
        if [[ "$dest" -ef "$src" ]]; then
            echo "  OK   $dest"
            continue
        fi
        if [[ -e "$dest" || "$current" != */dot-agents/bin/"$name" ]]; then
            echo "  CONFLICT: $dest links to $current, not this checkout; left alone"
            conflicts=$((conflicts + 1))
            continue
        fi
        if [[ "$MODE" == "--apply" ]]; then
            ln -sfn "$src" "$dest"
            echo "  Repaired $dest (was $current)"
        else
            echo "  STALE $dest -> $current (would repair)"
        fi
    elif [[ -e "$dest" ]]; then
        echo "  CONFLICT: $dest exists and is not a link to this repository; left alone"
        conflicts=$((conflicts + 1))
    elif [[ "$MODE" == "--apply" ]]; then
        mkdir -p "$DEST_DIR"
        ln -s "$src" "$dest"
        echo "  Linked $dest"
    else
        echo "  MISSING $dest (would link)"
    fi
done

case ":${PATH:-}:" in
    *":$DEST_DIR:"*) ;;
    *) echo "  NOTE: $DEST_DIR is not on PATH in this shell" ;;
esac

if [[ $conflicts -gt 0 ]]; then
    echo "  $conflicts conflict(s): move the file or link aside, then re-run" >&2
    exit 1
fi
exit 0
