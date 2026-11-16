#!/usr/bin/env bash
# reconcile-pi-web-access.sh — give Pi its own web search and page fetch.
#
# Pi ships with no web tools. Without them an agent falls back to curl, and
# most search engines answer curl with a bot challenge. The pi-web-access
# package adds `web_search`, `fetch_content`, `get_search_content` and
# `source_check` as Pi tools, so every model Pi runs (Claude through
# pi-claude-code, Codex, local Ollama) gets the same web access. With no API
# keys it searches through Exa's public MCP endpoint; keys for other providers
# go in machine-local ~/.pi/agent/web-search.json, never in this repo.
#
# The version is pinned: Pi doesn't auto-update an exact npm version, so an
# upgrade is a reviewed change to PACKAGE below. An older pin of the same
# package is replaced.

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: reconcile-pi-web-access.sh (--check | --apply)

  --check   Report whether the pinned pi-web-access package is installed.
            Never mutates the filesystem.
  --apply   Install the pinned package, removing any other version of it.
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

NAME="pi-web-access"
PACKAGE="npm:$NAME@0.48.0"
SETTINGS="$HOME/.pi/agent/settings.json"

echo "Pi web access ($MODE)"

if ! command -v pi >/dev/null 2>&1; then
    echo "  Skipped (pi is not installed)"
    exit 0
fi

# Every configured source of this package, one per line.
installed="$(python3 - "$SETTINGS" "$NAME" <<'PY'
import json, re, sys
try:
    d = json.load(open(sys.argv[1]))
except FileNotFoundError:
    d = {}
name = sys.argv[2]
for p in d.get("packages") or []:
    src = p if isinstance(p, str) else (p.get("source") or "")
    if re.fullmatch(r"npm:" + re.escape(name) + r"(@.*)?", src):
        print(src)
PY
)"

if [[ "$installed" == "$PACKAGE" ]]; then
    echo "  ok: package $PACKAGE"
    exit 0
fi

while IFS= read -r other; do
    [[ -z "$other" || "$other" == "$PACKAGE" ]] && continue
    if [[ "$MODE" == "apply" ]]; then
        command pi remove "$other"
        echo "  Removed $other"
    else
        echo "  WOULD REMOVE $other"
    fi
done <<<"$installed"

if grep -qxF "$PACKAGE" <<<"$installed"; then
    echo "  ok: package $PACKAGE"
elif [[ "$MODE" == "apply" ]]; then
    command pi install "$PACKAGE"
    echo "  Installed $PACKAGE"
else
    echo "  MISSING package $PACKAGE"
fi

exit 0
