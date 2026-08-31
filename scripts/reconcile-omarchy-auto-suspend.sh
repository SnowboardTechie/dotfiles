#!/usr/bin/env bash
# reconcile-omarchy-auto-suspend.sh — add the repository-owned auto-suspend
# service to Omarchy without replacing the shell's configuration.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PLUGIN_ID="snowboardtechie.auto-suspend"
SOURCE="$REPO_ROOT/omarchy/plugins/$PLUGIN_ID"
PLUGIN_DIR="$HOME/.config/omarchy/plugins"
TARGET="$PLUGIN_DIR/$PLUGIN_ID"
SHELL_CONFIG="$HOME/.config/omarchy/shell.json"
BACKUP="$SHELL_CONFIG.pre-auto-suspend"
TMP_CONFIG=""

cleanup() {
    [[ -z "$TMP_CONFIG" ]] || rm -f "$TMP_CONFIG"
}
trap cleanup EXIT

usage() {
    cat <<'EOF'
Usage: reconcile-omarchy-auto-suspend.sh (--check | --apply)

  --check   Report plugin link and enablement changes without mutating.
  --apply   Link the repository-owned service and enable it additively in an
            existing, valid Omarchy shell.json. Foreign collisions survive.
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

for required in manifest.json Service.qml; do
    if [[ ! -f "$SOURCE/$required" ]]; then
        echo "ERROR: auto-suspend plugin is missing $SOURCE/$required" >&2
        exit 1
    fi
done
if ! command -v jq >/dev/null 2>&1; then
    echo "ERROR: jq is required to inspect Omarchy's shell configuration" >&2
    exit 1
fi
if ! jq -e --arg id "$PLUGIN_ID" '
    .schemaVersion == 1
    and .id == $id
    and (.kinds | index("service") != null)
    and .entryPoints.service == "Service.qml"
' "$SOURCE/manifest.json" >/dev/null; then
    echo "ERROR: invalid auto-suspend plugin manifest" >&2
    exit 1
fi

printf 'Omarchy auto suspend (%s) for %s\n' "$MODE" "$TARGET"

target_owned=0
if [[ -L "$TARGET" ]] \
    && [[ "$(realpath "$TARGET" 2>/dev/null || true)" == "$(realpath "$SOURCE")" ]]; then
    echo "  ok: plugin link"
    target_owned=1
elif [[ -e "$TARGET" || -L "$TARGET" ]]; then
    echo "  WARNING: preserved foreign plugin path: $TARGET"
    echo "  summary: 0 link, 0 enable, 1 skipped"
    [[ "$MODE" != "check" ]] || echo "Check complete — no changes were made."
    exit 0
elif [[ "$MODE" == "check" ]]; then
    echo "  would link: $TARGET -> $SOURCE"
    target_owned=1
else
    mkdir -p "$PLUGIN_DIR"
    ln -s "$SOURCE" "$TARGET"
    echo "  linked: $TARGET -> $SOURCE"
    target_owned=1
fi

if [[ $target_owned -ne 1 ]]; then
    echo "ERROR: internal ownership check failed for $TARGET" >&2
    exit 1
fi

if [[ ! -f "$SHELL_CONFIG" ]]; then
    echo "  WARNING: $SHELL_CONFIG does not exist; plugin was not enabled"
    echo "  summary: 0 enable, 1 skipped"
    [[ "$MODE" != "check" ]] || echo "Check complete — no changes were made."
    exit 0
fi
if ! jq -e '
    type == "object"
    and .version == 1
    and ((.plugins == null) or (.plugins | type == "array"))
' "$SHELL_CONFIG" >/dev/null 2>&1; then
    echo "  WARNING: preserved invalid or unsupported shell.json; plugin was not enabled"
    echo "  summary: 0 enable, 1 skipped"
    [[ "$MODE" != "check" ]] || echo "Check complete — no changes were made."
    exit 0
fi

entry_count="$(jq --arg id "$PLUGIN_ID" '[.plugins[]? | select(.id == $id)] | length' "$SHELL_CONFIG")"
if [[ "$entry_count" -gt 1 ]]; then
    echo "  WARNING: shell.json contains duplicate $PLUGIN_ID entries; preserved unchanged"
elif [[ "$entry_count" -eq 1 ]]; then
    echo "  ok: service enabled in shell.json"
elif [[ "$MODE" == "check" ]]; then
    echo "  would enable: $PLUGIN_ID in shell.json"
else
    if [[ ! -e "$BACKUP" ]]; then
        cp -p "$SHELL_CONFIG" "$BACKUP"
        echo "  backed up: $BACKUP"
    fi
    TMP_CONFIG="$(mktemp "$SHELL_CONFIG.tmp.XXXXXX")"
    jq --arg id "$PLUGIN_ID" '.plugins = ((.plugins // []) + [{id: $id}])' \
        "$SHELL_CONFIG" > "$TMP_CONFIG"
    chmod --reference="$SHELL_CONFIG" "$TMP_CONFIG"
    mv -f "$TMP_CONFIG" "$SHELL_CONFIG"
    TMP_CONFIG=""
    echo "  enabled: $PLUGIN_ID in shell.json"
fi

if [[ "$MODE" == "apply" ]]; then
    if [[ ${OMARCHY_AUTO_SUSPEND_SKIP_RELOAD:-0} == 1 ]]; then
        echo "  note: skipped Omarchy plugin registry reload"
    elif command -v omarchy >/dev/null 2>&1; then
        # The shell watches user plugin directories, but inotify does not
        # reliably follow edits through this managed directory symlink.
        if omarchy restart shell >/dev/null 2>&1; then
            echo "  restarted: Omarchy shell"
        else
            echo "  WARNING: shell restart unavailable; the service will load next login"
        fi
    elif command -v omarchy-shell >/dev/null 2>&1; then
        if omarchy-shell shell rescanPlugins >/dev/null 2>&1; then
            echo "  reloaded: Omarchy plugin registry"
        else
            echo "  WARNING: shell reload unavailable; the service will load next login"
        fi
    else
        echo "  note: omarchy-shell is not running here; the service will load next login"
    fi
else
    echo "Check complete — no changes were made."
fi
