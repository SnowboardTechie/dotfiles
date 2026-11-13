#!/usr/bin/env bash
# reconcile-pi-claude-code.sh — make Pi reach Claude through Claude Code.
#
# Pi's built-in `anthropic` provider with a Claude subscription login counts as
# third-party use: Anthropic bills it per token as extra usage, not against the
# plan. The pi-claude-code package adds a `claude-code` provider that runs the
# Claude Code CLI, which does count against the plan. This reconciler:
#   - installs that package (`pi install`) if ~/.pi/agent/settings.json lacks it;
#   - sets defaultProvider to claude-code when it is unset or `anthropic`
#     (any other explicit choice is left alone);
#   - reports, never removes, a direct Anthropic subscription login in
#     ~/.pi/agent/auth.json. Remove it with /logout inside Pi.
# Skips when pi or the claude CLI is missing.

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: reconcile-pi-claude-code.sh (--check | --apply)

  --check   Report the package, default provider, and Anthropic login state.
            Never mutates the filesystem.
  --apply   Install pi-claude-code and switch an unset/anthropic default
            provider to claude-code.
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
    usage >&2
    exit 2
fi

PACKAGE="https://github.com/earendil-works/pi-claude-code"
PROVIDER="claude-code"
AGENT_DIR="$HOME/.pi/agent"
SETTINGS="$AGENT_DIR/settings.json"
AUTH="$AGENT_DIR/auth.json"

echo "Pi Claude Code provider ($MODE)"

if ! command -v pi >/dev/null 2>&1; then
    echo "  Skipped (pi is not installed)"
    exit 0
fi
if ! command -v claude >/dev/null 2>&1; then
    echo "  Skipped (the claude CLI is not installed; the claude-code provider needs it)"
    exit 0
fi

# json_get <file> <expr>: prints the result of a small python expression over `d`.
json_get() {
    python3 - "$1" "$2" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except FileNotFoundError:
    d = {}
print(eval(sys.argv[2], {"d": d}))
PY
}

# Package
if [[ "$(json_get "$SETTINGS" "'$PACKAGE' in (d.get('packages') or [])")" == "True" ]]; then
    echo "  ok: package $PACKAGE"
elif [[ "$MODE" == "apply" ]]; then
    command pi install "$PACKAGE"
    echo "  Installed $PACKAGE"
else
    echo "  MISSING package $PACKAGE"
fi

# Default provider
current="$(json_get "$SETTINGS" "d.get('defaultProvider') or ''")"
if [[ "$current" == "$PROVIDER" ]]; then
    echo "  ok: defaultProvider $PROVIDER"
elif [[ -n "$current" && "$current" != "anthropic" ]]; then
    echo "  ok: defaultProvider $current (explicit choice, left alone)"
elif [[ "$MODE" == "apply" ]]; then
    mkdir -p "$AGENT_DIR"
    python3 - "$SETTINGS" "$PROVIDER" <<'PY'
import json, os, sys
path, provider = sys.argv[1], sys.argv[2]
try:
    d = json.load(open(path))
except FileNotFoundError:
    d = {}
d["defaultProvider"] = provider
tmp = path + ".tmp"
with open(tmp, "w") as f:
    json.dump(d, f, indent=2)
    f.write("\n")
if os.path.exists(path):
    os.chmod(tmp, os.stat(path).st_mode & 0o777)
os.replace(tmp, path)
PY
    echo "  Set defaultProvider ${current:-<unset>} -> $PROVIDER"
else
    echo "  WOULD SET defaultProvider ${current:-<unset>} -> $PROVIDER"
fi

# Direct Anthropic subscription login (reported only)
if [[ "$(json_get "$AUTH" "(d.get('anthropic') or {}).get('type') == 'oauth'")" == "True" ]]; then
    echo "  NOTE: $AUTH holds a direct Anthropic subscription login (billed as extra usage);"
    echo "        run /logout in Pi to remove it"
fi

exit 0
