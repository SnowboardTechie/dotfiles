#!/usr/bin/env bash
# reconcile-hindsight.sh — wire this machine's Claude Code + OpenCode into the
# self-hosted Hindsight memory server on Studio, additively and current.
#
# What it manages:
#   1. ~/.hindsight/coding-agent.json — rendered from hindsight/
#      coding-agent.template.json with the machine-local bearer from
#      ~/.secrets/hindsight/api-bearer and $HOME substituted (mode 0600).
#      The token never lives in this repository.
#   2. The current @vectorize-io/hindsight-coding-agents installer (--apply
#      only), which stages the runtime at ~/.hindsight/coding-agents, merges
#      Claude hooks / the OpenCode plugin entry, and registers the MCP server.
#      The staged runtime then follows the upstream-supported automatic updater.
#      On stow-managed machines those hook/plugin entries are already
#      committed in this repo; the installer is idempotent over them. On
#      Omarchy it merges additively into Omarchy-owned configs and backs the
#      originals up (*.hindsight-backup).


set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

API_URL="https://bryans-mac-studio.tail5ba690.ts.net:9443"
TEMPLATE="$REPO_ROOT/hindsight/coding-agent.template.json"
TOKEN_FILE="$HOME/.secrets/hindsight/api-bearer"
CONFIG="$HOME/.hindsight/coding-agent.json"

usage() {
    cat <<'EOF'
Usage: reconcile-hindsight.sh (--check | --apply)

  --check   Report token presence, rendered-config drift, staged runtime and
            hook/plugin wiring. Never mutates the filesystem.
  --apply   Render ~/.hindsight/coding-agent.json (mode 0600) and run the
            current coding-agents installer for claude-code + opencode.
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

echo "Hindsight client reconcile ($MODE) for $HOME"
issues=0

# --- 1. Preconditions -------------------------------------------------------
if ! command -v npx >/dev/null 2>&1; then
    echo "  ERROR: npx not found on PATH" >&2
    exit 1
fi
if [[ ! -s "$TOKEN_FILE" ]]; then
    echo "  ERROR: bearer missing at $TOKEN_FILE" >&2
    echo "  Copy it from Studio over Tailscale/SSH; chmod 600. Never paste it into chat or Git." >&2
    exit 1
fi
# GNU stat first (-c errors cleanly on BSD; BSD's -f means *filesystem* on GNU)
token_mode=$(stat -L -c %a "$TOKEN_FILE" 2>/dev/null || stat -L -f %Lp "$TOKEN_FILE")
if [[ "$token_mode" != "600" ]]; then
    echo "  ERROR: $TOKEN_FILE must be mode 0600 (is $token_mode)" >&2
    exit 1
fi
echo "  ok: bearer present (mode 0600)"

# --- 2. Render machine-local config ----------------------------------------
rendered=$(python3 - "$TEMPLATE" "$TOKEN_FILE" <<'PYEOF'
import json, os, sys
template_path, token_path = sys.argv[1], sys.argv[2]
with open(template_path, encoding="utf-8") as fh:
    text = fh.read()
with open(token_path, encoding="utf-8") as fh:
    token = fh.read().strip()
text = text.replace("{{API_TOKEN}}", token).replace("{{HOME}}", os.path.expanduser("~"))
json.loads(text)  # refuse to emit malformed config
print(text, end="")
PYEOF
)

if [[ -f "$CONFIG" ]] && [[ "$(cat "$CONFIG")" == "$rendered" ]]; then
    echo "  ok: $CONFIG matches template"
else
    if [[ "$MODE" == "check" ]]; then
        echo "  would render: $CONFIG from template + local bearer"
        issues=$((issues + 1))
    else
        mkdir -p "$(dirname "$CONFIG")"
        (umask 177; printf '%s' "$rendered" > "$CONFIG")
        chmod 600 "$CONFIG"
        echo "  rendered: $CONFIG (mode 0600)"
    fi
fi

# --- 3. Current installer (stages runtime, merges hooks/plugin, MCP) --------
if [[ "$MODE" == "apply" ]]; then
    # Isolated npm cache: ~/.npm carries root-owned files on several of these
    # machines (old npm bug), which makes npx fail with EACCES. The package is
    # small; a throwaway cache costs seconds and avoids the whole class.
    # Under $HOME, not /tmp: Omarchy's /tmp policy denies npm's cacache mkdirs.
    mkdir -p "$HOME/.cache"
    NPM_TMP_CACHE="$(mktemp -d "$HOME/.cache/hindsight-npx-cache-XXXXXX")"
    trap 'rm -rf "$NPM_TMP_CACHE"' EXIT
    npm_config_cache="$NPM_TMP_CACHE" \
        npx -y "@vectorize-io/hindsight-coding-agents@latest" \
        install claude-code opencode --server self-hosted --api-url "$API_URL"
else
    if [[ -d "$HOME/.hindsight/coding-agents/dist" ]]; then
        echo "  ok: runtime staged at ~/.hindsight/coding-agents"
    else
        echo "  would install: current coding-agents runtime"
        issues=$((issues + 1))
    fi
fi

# --- 4. Post-checks ----------------------------------------------------------
if grep -qs "coding-agents/dist/claude-hook.js" "$HOME/.claude/settings.json"; then
    echo "  ok: Claude hooks wired"
else
    echo "  missing: Claude hooks in ~/.claude/settings.json"
    issues=$((issues + 1))
fi
if grep -qs ".hindsight/coding-agents" "$HOME/.config/opencode/opencode.json"; then
    echo "  ok: OpenCode plugin wired"
else
    echo "  missing: OpenCode plugin entry in ~/.config/opencode/opencode.json"
    issues=$((issues + 1))
fi
if command -v curl >/dev/null 2>&1; then
    code=$(curl -s -o /dev/null -m 10 -w '%{http_code}' \
        -H "Authorization: Bearer $(cat "$TOKEN_FILE")" "$API_URL/v1/default/banks" || true)
    if [[ "$code" == "200" ]]; then
        echo "  ok: API reachable and bearer accepted ($API_URL)"
    else
        echo "  WARNING: API check returned '$code' (expected 200) — server down or wrong bearer"
        issues=$((issues + 1))
    fi
fi

echo "  summary: $issues issue(s)"
if [[ "$MODE" == "check" ]]; then
    echo "Check complete — no changes were made."
fi
exit 0
