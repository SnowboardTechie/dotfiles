#!/usr/bin/env bash
# reconcile-omarchy-clipboard-bridge.sh — run the clipboard bridge
# (omarchy/clipboard-bridge/clipboard-bridge.sh) as a systemd user service.
#
# The Mac to bridge with is machine-local: its hostname is the first line of
# ~/.config/clipboard-bridge/host, which this reconciler never writes. Without
# that file the bridge is skipped.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BRIDGE="$REPO_ROOT/omarchy/clipboard-bridge/clipboard-bridge.sh"
HOST_FILE="$HOME/.config/clipboard-bridge/host"
UNIT_NAME="clipboard-bridge.service"
UNIT_DIR="$HOME/.config/systemd/user"
UNIT="$UNIT_DIR/$UNIT_NAME"
SYSTEMCTL="${CLIPBOARD_BRIDGE_SYSTEMCTL:-systemctl}"

usage() {
    cat <<'EOF'
Usage: reconcile-omarchy-clipboard-bridge.sh (--check | --apply)

  --check   Report what the clipboard bridge service needs. Never mutates.
  --apply   Write the systemd user unit and enable it. Skips when no Mac is
            named in ~/.config/clipboard-bridge/host.
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

if [[ ! -x "$BRIDGE" ]]; then
    echo "ERROR: clipboard bridge not found or not executable at $BRIDGE" >&2
    exit 1
fi

echo "Clipboard bridge ($MODE)"

for required in wl-paste wl-copy ssh; do
    if ! command -v "$required" >/dev/null 2>&1; then
        echo "  WARNING: $required is not installed; skipping the clipboard bridge"
        echo "  summary: 0 changed, 0 ok, 1 skipped"
        exit 0
    fi
done

if [[ ! -s "$HOST_FILE" ]]; then
    echo "  skipped: no Mac configured. To turn the bridge on, put the Mac's"
    echo "  SSH hostname on the first line of $HOST_FILE and run this again."
    echo "  summary: 0 changed, 0 ok, 1 skipped"
    exit 0
fi

WANTED="$(cat <<EOF
# Managed by scripts/reconcile-omarchy-clipboard-bridge.sh in the dotfiles repo.
[Unit]
Description=Share the text clipboard with a Mac (Universal Clipboard bridge)
After=graphical-session.target
PartOf=graphical-session.target
ConditionEnvironment=WAYLAND_DISPLAY

[Service]
Type=simple
ExecStart=$BRIDGE
Restart=always
RestartSec=5
UMask=0077

[Install]
WantedBy=graphical-session.target
EOF
)"

changed=0
ok=0

if [[ -f "$UNIT" && "$(cat "$UNIT")" == "$WANTED" ]]; then
    echo "  ok: $UNIT is current"
    ok=$((ok + 1))
elif [[ -e "$UNIT" || -L "$UNIT" ]] && ! grep -qF "reconcile-omarchy-clipboard-bridge.sh" "$UNIT" 2>/dev/null; then
    echo "  WARNING: $UNIT exists and is not managed by this script; leaving it untouched"
    echo "  summary: 0 changed, 0 ok, 1 skipped"
    exit 0
elif [[ "$MODE" == "check" ]]; then
    echo "  would write: $UNIT"
    changed=$((changed + 1))
else
    mkdir -p "$UNIT_DIR"
    printf '%s\n' "$WANTED" > "$UNIT"
    "$SYSTEMCTL" --user daemon-reload
    # Pick up a changed unit or script path.
    "$SYSTEMCTL" --user try-restart "$UNIT_NAME" || true
    echo "  wrote: $UNIT"
    changed=$((changed + 1))
fi

if "$SYSTEMCTL" --user is-enabled --quiet "$UNIT_NAME" 2>/dev/null \
    && "$SYSTEMCTL" --user is-active --quiet "$UNIT_NAME" 2>/dev/null; then
    echo "  ok: $UNIT_NAME is enabled and running"
    ok=$((ok + 1))
elif [[ "$MODE" == "check" ]]; then
    echo "  would enable and start: $UNIT_NAME"
    changed=$((changed + 1))
else
    "$SYSTEMCTL" --user enable --now "$UNIT_NAME"
    echo "  enabled and started: $UNIT_NAME"
    changed=$((changed + 1))
fi

echo "  summary: $changed changed, $ok ok, 0 skipped"
if [[ "$MODE" == "check" ]]; then
    echo "Check complete — no changes were made."
fi
