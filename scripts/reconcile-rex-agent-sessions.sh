#!/usr/bin/env bash
# Install the Rex agent-session restorer: the Pi extension link and the launchd watcher.
# Usage: reconcile-rex-agent-sessions.sh --check | --apply
# Never replaces a foreign file or symlink. macOS only (Rex server + launchd).
set -e

MODE="${1:-}"
[[ "$MODE" == "--check" || "$MODE" == "--apply" ]] || { echo "Usage: $0 --check|--apply" >&2; exit 2; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_DIR="${REX_AGENT_SESSIONS_HOME:-$HOME}"
LABEL="com.snowboardtechie.rex-agent-sessions"
EXT_SRC="$REPO_ROOT/dot-pi/agent/extensions/rex-agent-sessions.ts"
EXT_DEST="$HOME_DIR/.pi/agent/extensions/rex-agent-sessions.ts"
PLIST_SRC="$REPO_ROOT/scripts/$LABEL.plist"
PLIST_DEST="$HOME_DIR/Library/LaunchAgents/$LABEL.plist"
STATE_DIR="$HOME_DIR/.local/state/rex-agent-sessions"
LAUNCHCTL="${REX_AGENT_SESSIONS_LAUNCHCTL:-launchctl}"
drift=0

if [[ "$OSTYPE" != darwin* ]]; then
    echo "  Skipped (Rex agent-session restore is macOS-only)"
    exit 0
fi

# Pi extension link
if [[ -L "$EXT_DEST" && "$(readlink "$EXT_DEST")" == "$EXT_SRC" ]]; then
    echo "  OK   $EXT_DEST"
elif [[ -e "$EXT_DEST" || -L "$EXT_DEST" ]]; then
    echo "  WARNING: $EXT_DEST is not managed by this repository, skipping"
elif [[ "$MODE" == "--apply" ]]; then
    mkdir -p "$(dirname "$EXT_DEST")"
    ln -s "$EXT_SRC" "$EXT_DEST"
    echo "  Linked $EXT_DEST"
else
    echo "  MISSING $EXT_DEST"; drift=1
fi

# launchd watcher (rendered: launchd plists need absolute paths)
rendered="$(sed -e "s|__REPO__|$REPO_ROOT|g" -e "s|__HOME__|$HOME_DIR|g" "$PLIST_SRC")"
if [[ -f "$PLIST_DEST" && "$(cat "$PLIST_DEST")" == "$rendered" ]]; then
    echo "  OK   $PLIST_DEST"
elif [[ -e "$PLIST_DEST" ]] && ! grep -q "rex-agent-sessions.py" "$PLIST_DEST"; then
    echo "  WARNING: $PLIST_DEST is not managed by this repository, skipping"
    exit 0
elif [[ "$MODE" == "--apply" ]]; then
    mkdir -p "$(dirname "$PLIST_DEST")" "$STATE_DIR"
    chmod 700 "$STATE_DIR"
    printf '%s\n' "$rendered" > "$PLIST_DEST"
    "$LAUNCHCTL" bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    "$LAUNCHCTL" bootstrap "gui/$(id -u)" "$PLIST_DEST"
    echo "  Installed and loaded $LABEL"
else
    echo "  STALE/MISSING $PLIST_DEST"; drift=1
fi

if [[ "$MODE" == "--apply" ]] && ! "$LAUNCHCTL" print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
    "$LAUNCHCTL" bootstrap "gui/$(id -u)" "$PLIST_DEST"
    echo "  Loaded $LABEL"
fi

exit $drift
