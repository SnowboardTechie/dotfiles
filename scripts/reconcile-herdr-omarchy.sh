#!/usr/bin/env bash
# reconcile-herdr-omarchy.sh — manage the Omarchy-specific Herdr config and
# Glyph Rail module links without overwriting unknown custom configurations.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATE="$REPO_ROOT/dot-config/herdr/config-omarchy.toml"
HERDR_DIR="$HOME/.config/herdr"
CONFIG="$HERDR_DIR/config.toml"
BACKUP="$HERDR_DIR/config.toml.omarchy-backup"
MODULES=(claude-usage.sh openrouter-spend.py host-label.sh)
STOCK_RAIL='tab_bar_right = [{ type = "zoom" }, { type = "hostname" }]'

usage() {
    cat <<'EOF'
Usage: reconcile-herdr-omarchy.sh (--check | --apply)

  --check   Report config and Glyph Rail link changes without mutating.
  --apply   Back up a stock/identical Omarchy config, link the managed template,
            and link missing Glyph Rail modules. Unknown custom files survive.
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

if [[ ! -f "$TEMPLATE" ]]; then
    echo "ERROR: missing Omarchy Herdr template: $TEMPLATE" >&2
    exit 1
fi

printf 'Herdr Omarchy integration (%s) for %s\n' "$MODE" "$HERDR_DIR"

managed_config=0
if [[ -L "$CONFIG" ]] && [[ "$(realpath "$CONFIG")" == "$(realpath "$TEMPLATE")" ]]; then
    echo "  ok: config.toml uses the managed Omarchy template"
elif [[ -f "$CONFIG" ]] && { grep -qxF "$STOCK_RAIL" "$CONFIG" || cmp -s "$CONFIG" "$TEMPLATE"; }; then
    if [[ "$MODE" == "check" ]]; then
        echo "  would manage: config.toml (preserve one stock backup)"
    else
        mkdir -p "$HERDR_DIR"
        if [[ ! -e "$BACKUP" ]]; then
            cp -p "$CONFIG" "$BACKUP"
            echo "  backed up: config.toml.omarchy-backup"
        fi
        rm -f "$CONFIG"
        ln -s "$TEMPLATE" "$CONFIG"
        echo "  managed: config.toml -> $TEMPLATE"
    fi
    managed_config=1
elif [[ -e "$CONFIG" || -L "$CONFIG" ]]; then
    echo "  WARNING: preserved custom config.toml (not stock or managed)"
else
    if [[ "$MODE" == "check" ]]; then
        echo "  would manage: config.toml (no existing config)"
    else
        mkdir -p "$HERDR_DIR"
        ln -s "$TEMPLATE" "$CONFIG"
        echo "  managed: config.toml -> $TEMPLATE"
    fi
    managed_config=1
fi

for module in "${MODULES[@]}"; do
    source_path="$REPO_ROOT/dot-config/herdr/$module"
    target_path="$HERDR_DIR/$module"
    if [[ ! -f "$source_path" ]]; then
        echo "  ERROR: missing Glyph Rail module source: $source_path" >&2
        exit 1
    fi
    if [[ -L "$target_path" ]] && [[ "$(realpath "$target_path")" == "$(realpath "$source_path")" ]]; then
        echo "  ok: $module"
    elif [[ -e "$target_path" || -L "$target_path" ]]; then
        echo "  WARNING: preserved foreign module: $module"
    elif [[ "$MODE" == "check" ]]; then
        echo "  would link: $module"
    else
        mkdir -p "$HERDR_DIR"
        ln -s "$source_path" "$target_path"
        echo "  linked: $module"
    fi
done

if [[ "$MODE" == "check" ]]; then
    echo "Check complete — no changes were made."
fi
